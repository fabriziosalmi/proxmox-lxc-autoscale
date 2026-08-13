# ASG-style horizontal scaling

Status: draft
Milestone: `ASG-style horizontal scaling`
Author: fabriziosalmi
Date: 2026-08-13

## 1. Why

The horizontal scaling that ships today clones a container on the node where
the daemon happens to run, stops the last clone when load drops, and keeps the
group membership in a module-level dictionary. It is marked experimental for
good reason.

The gap was named precisely by `starttoaster` in
[forum.proxmox.com/threads/auto-scalability-feature.42208](https://forum.proxmox.com/threads/auto-scalability-feature.42208):
what is missing is not "more cloning", it is the Auto Scaling Group model.
An ASG owns a desired count, provisions instances from a launch template,
places them across the available capacity, health checks them, replaces the
unhealthy ones, and reconciles its own state after a restart. This document
defines that model for Proxmox VE and the MVP that earns the removal of the
experimental warning.

## 2. What exists today, verified

Read before designing. These are facts about the code at `f10e2ea`, not
assumptions.

### 2.1 Horizontal scaling

`scaling_manager.py` implements:

- `calculate_group_metrics` averages CPU and memory over the group members.
- `should_scale_out` / `should_scale_in` compare the averages against
  `horiz_*_threshold` and apply grace periods.
- `scale_out` runs `pct snapshot`, `pct clone --snapname`, `pct set -net0`,
  `pct start`.
- `scale_in` runs `pct stop` on the highest ctid. There is no destroy.

Defects found while reading, each of which the new design must not inherit:

| Defect | Location | Effect |
|---|---|---|
| Static IP filter compares IP strings against integer ctids | `scaling_manager.py:520` | Every clone gets `static_ip_range[0]`. Duplicate IP from the second clone on. |
| Docs document `min_instances`, code reads `min_containers`, model allows extras | `scaling_manager.py:482`, `docs/guide/horizontal-scaling.md` | The documented minimum is silently ignored. |
| `new_ctid = starting_clone_id + len(...)` combined with stop-without-destroy | `scaling_manager.py:492` | After one scale-in, the next scale-out recomputes an id that still exists and the clone fails deterministically. |
| `base_snapshot_name` is validated as numeric | `config.py:230` | It is a source CTID, not a snapshot name. The name already misled the documentation. |
| No readiness gate after `pct start` | `scaling_manager.py:526` | A booting instance enters the group average immediately with high CPU, which pushes towards another scale-out. |
| Group metrics only iterate over members visible in `pct list` | `scaling_manager.py:557` | A member on another node lowers the average silently instead of failing loudly. |
| Group membership mutated in a module-level `model_dump()` | `scaling_manager.py:528`, `config.py:406` | Clones are invisible after a restart: not counted, not scaled in, ids reused. |

### 2.2 The Proxmox backends

`lxc_autoscale/backends/` contains `ProxmoxBackend` (ABC), `CLIBackend`,
`RESTBackend` (proxmoxer) and a factory, with tests. It is dead code: no
production module imports `backends`, `defaults.backend` is read only by
`tests/test_backend_factory.py`, and `run_command` goes straight to a local
subprocess or to SSH against a single host. The README nonetheless advertises
the REST API as a supported backend.

`RESTBackend` is also single-node by construction: `_get_node()` caches
`nodes[0]["node"]` and addresses every container through it. The ABC has no
`migrate`, no `destroy`, no target node on `clone`, and no notion of a QEMU
guest.

This is good news for the plan. The work is not "write an API client", it is
"finish and wire an abstraction that already exists, and extend it".

### 2.3 The neighbouring repositories

`proxmox-cluster-balancer` cannot be called into. `main.py` imports
`ssh_connect` from `functions.py`, which defines a class `SSHClient` and no
such function, so the entrypoint fails at import. `suggest_migrations`
references `cpu_score` and `memory_score`, which are locals of
`evaluate_migration_target`, so it would raise `NameError` on the first
suggestion it produced. It prints suggestions and never migrates:
`trigger_migration` is only called from a `__main__` demo block. Reusing its
scorer is a rewrite, not an integration, and the reusable part is roughly 40
lines of weighted arithmetic aimed at migration rather than initial placement.

`proxmox-vm-autoscale` has zero lifecycle primitives: no `qm clone`, `create`,
`migrate` or `destroy` anywhere. It is synchronous, paramiko based, binds each
VM statically to one host in the config, and has no concept of a group. ASG for
VMs there is entirely greenfield.

## 3. The model

### 3.1 Objects

```
LaunchTemplate      immutable description of how to build one instance
ScalingGroup        min / max / thresholds / template ref / health / hooks
GroupState          desired count + members, derived from the cluster
Instance            one guest, with a lifecycle state
```

`LaunchTemplate` is deliberately a separate object from the group. Rolling a
new image version is the operation you will want next, and it is not
expressible when the template is inlined into the group.

```yaml
ASG_TEMPLATE_web:
  guest_type: lxc          # qemu reserved, rejected by validation in the MVP
  source_vmid: 101
  source_snapshot: null    # null clones the current state
  clone_mode: full         # full | linked
  target_storage: shared-nvme
  net0: "name=eth0,bridge=vmbr0,ip=dhcp"
  provision: none          # none | hookscript
  hookscript: null
  tags: ["web"]
```

### 3.2 Desired count is state, not configuration

`min` and `max` are configuration. `desired` is the value the controller moves
and therefore belongs to state. Putting it in the YAML would mean rewriting the
user's configuration file on every scale event.

### 3.3 State lives in Proxmox tags

Every instance the controller creates is tagged:

```
asg-group=<group name>
asg-created=<unix timestamp>
```

The tag set is the source of truth for group membership. Reconciliation is one
query to `/cluster/resources?type=vm` filtered by tag, which returns vmid,
node, status and tags cluster-wide in a single call.

The alternative, a local JSON state file, was rejected: it does not survive a
reinstall, it is invisible to anyone looking at the PVE UI, it cannot be
corrected by hand, and two daemons would silently disagree. Tags cost one extra
privilege (`VM.Config.Options`) and can be removed by a human, which is an
acceptable failure mode because it is visible and correctable.

A local file remains, but only as a cache of non-critical metadata: last action
timestamps and consecutive health counters. Losing it costs one grace period,
not correctness.

### 3.4 Instance lifecycle

```
                  +-------------+
                  |  Pending    |  clone task submitted, UPID tracked
                  +------+------+
                         |  task ok
                  +------v------+
                  | Provisioned |  config applied, tagged, started
                  +------+------+
                         |  readiness probe passes
                  +------v------+
     +----------->|   InService |<-----------+
     |            +------+------+            |
     |                   |  health fails N times
     |            +------v------+            |
     |            |  Unhealthy  |            |
     |            +------+------+            |
     |                   |  replacement InService
     |            +------v------+            |
     |            | Terminating |  deregister hook, then destroy
     |            +------+------+            |
     |                   |                   |
     |            +------v------+            |
     +------------|  Terminated |------------+
                  +-------------+
```

A guest that carries the group tag but is in none of these states, for example
one that a human stopped, is reported as drifted and left alone unless
`reconcile_adopt` is enabled.

### 3.5 Health checks

Three levels with very different costs:

1. **PVE level**, always on: `status == running` and no `lock` set. Free,
   works for LXC and QEMU, needs only `VM.Audit`.
2. **Guest agent level**: `qemu-guest-agent` ping for VMs, `pct exec` for
   containers. Requires an agent and much higher privileges.
3. **Application probe**, optional: TCP connect or HTTP GET against
   `ip:port`, with `healthy_threshold` and `unhealthy_threshold` consecutive
   results.

The MVP implements 1 and 3. Level 2 is deliberately not the default: on LXC it
means the daemon executes commands inside the guest, which is exactly the
surface a user does not expect to grant in order to get autoscaling.

### 3.6 Replace without a managed load balancer

There is no ELB here, so "replace" is: mark unhealthy, launch the replacement,
wait for it to reach InService, then terminate the old one. The missing piece
is registration, and the right answer is not to integrate HAProxy or nginx but
to expose two hooks:

```yaml
hooks:
  on_instance_ready: "/usr/local/bin/asg-register {{vmid}} {{ip}}"
  on_instance_terminating: "/usr/local/bin/asg-deregister {{vmid}} {{ip}}"
  timeout: 30
```

Failure semantics must be explicit: a failing `on_instance_ready` marks the
instance unhealthy, a failing `on_instance_terminating` blocks the destroy and
raises an alert. Anything else silently drops traffic on the floor.

## 4. Architectural decisions

### D1. API token transport, cluster-wide. pct is not extended.

Cross-node work is impossible through a local `pct`, and the API additionally
returns a UPID for `clone` and `migrate`, which turns "did the clone finish" from
guesswork into a structured poll of `/nodes/{node}/tasks/{upid}/status`.

ASG requires `backend: api`. SSH and pct remain supported for the existing
vertical scaling on a single node. There will be no degraded pct mode for ASG:
it would reproduce the class of defects in section 2.1 in new forms.

### D2. Full clone by default, linked as an explicit opt-in.

Linked clones are faster and cheaper, but they bind the clone to the source
storage, which rules out placing it on another node with local storage, and
they make the template undeletable while any clone exists. For a group whose
instances are created and destroyed continuously, a permanent dependency on the
template is an operational trap. Linked mode stays available and is validated
as single-node only.

### D3. A small internal placement scorer. cluster-balancer is not a dependency.

What is actually needed is free cores, free memory and a weighted score from
`/nodes/{node}/status`, roughly 60 lines. Turning cluster-balancer into a
library means fixing its broken entrypoint, packaging it, giving it a stable
API and versioning it, for a single consumer.

```
score(node) = w_cpu * (1 - cpu_used_ratio) + w_mem * (free_mem / total_mem)
```

Nodes that fail a hard filter are excluded before scoring: insufficient free
memory for the template, node not `online`, node in the group's `exclude_nodes`,
or storage from the template not available on that node.

### D4. Tags are the source of truth. See 3.3.

### D5. IDs come from `/cluster/nextid`.

`starting_clone_id + len(members)` is the direct cause of the deterministic
failure in section 2.1. `/cluster/nextid` is allocated cluster-side.
`id_range` survives only as an optional validation constraint, not as an
allocator.

## 5. Security

### 5.1 No new SSH surface

ASG adds no SSH capability. The API token path is additive and the token is
read from the existing `proxmox_api` config block, which already supports
`${ENV_VAR}` expansion for secrets.

### 5.2 Token privileges

Create a dedicated role and a token that is not `root@pam`:

```
pveum role add ASGOperator -privs "VM.Audit,VM.Allocate,VM.Clone,\
VM.Config.CPU,VM.Config.Memory,VM.Config.Network,VM.Config.Options,\
VM.PowerMgmt,Datastore.AllocateSpace,Datastore.Audit,Sys.Audit"
pveum user add asg@pve
pveum user token add asg@pve autoscale --privsep 1
pveum acl modify /vms  -user asg@pve -role ASGOperator
pveum acl modify /nodes -user asg@pve -role PVEAuditor
pveum acl modify /storage/<store> -user asg@pve -role ASGOperator
```

Why each privilege is needed:

| Privilege | Needed for |
|---|---|
| `VM.Audit` | read config and status, list guests |
| `VM.Allocate` | create the clone target, and destroy it on scale-in |
| `VM.Clone` | the clone itself |
| `VM.Config.CPU`, `VM.Config.Memory` | existing vertical scaling through the API backend |
| `VM.Config.Network` | set `net0` on a new instance |
| `VM.Config.Options` | write the `asg-group` tags that hold the state |
| `VM.PowerMgmt` | start and stop |
| `Datastore.AllocateSpace`, `Datastore.Audit` | allocate the clone's disk, check the store exists on the target node |
| `Sys.Audit` on `/nodes` | read `/nodes/{node}/status` for placement |

Note that `VM.Allocate` is what permits destroy. There is no narrower privilege
for it, which is precisely why the destroy path needs the opt-in of section 5.3.

Deliberately not granted: `VM.Console`, `VM.Monitor`, `VM.Migrate`,
`Sys.Modify`, `VM.Snapshot.Rollback`, and anything that permits executing
commands inside a guest.

The exact privilege list is asserted by a startup preflight check
(`asg --check-permissions`) that reports what is missing instead of failing on
the first clone at 3am.

### 5.3 Destructive operations

`destroy` on scale-in requires two independent opt-ins:

```yaml
scale_in_policy: destroy      # stop | destroy, default stop
allow_destroy: true           # must be explicitly true
```

`stop` remains the default so an upgrade never starts deleting guests. In
addition:

- `--dry-run` on the daemon and a `dry_run: true` per group log every planned
  action with its full parameters and execute nothing.
- Destroy refuses to run on a guest that does not carry the `asg-group` tag of
  the group performing the scale-in, even if it appears in the member list.
  This is the single guard that prevents a config error from destroying an
  unrelated guest.
- Destroy is preceded by the `on_instance_terminating` hook and a configurable
  drain period.

## 6. Idempotency and reconciliation

Every cycle begins with reconciliation, before any decision:

1. Query `/cluster/resources?type=vm`, filter by the group's tag.
2. Build the observed member set with node, status and lock for each.
3. Compare with the last known desired count from the cache file.
4. Classify: `InService`, `Pending` (a clone task still running), `Orphan`
   (tagged, not in the last known set), `Missing` (in the last known set,
   no longer present).
5. Adopt orphans into the group, log missing ones, then decide.

Consequences that must hold:

- A restart mid-clone finds the task through its UPID or finds the tagged
  guest, and does not create a second one.
- Two daemons pointed at the same group converge instead of doubling, because
  membership is read from the cluster rather than from process memory.
- A user who removes a tag by hand removes the guest from the group. That is
  documented as the supported way to take an instance out of management.

Scale actions are keyed by an idempotency token derived from
`(group, desired_transition, cycle)` and logged before execution, so a crash
between "decided" and "executed" is visible in the log.

## 7. Configuration and migration path

New shape, additive:

```yaml
ASG_TEMPLATE_web:
  guest_type: lxc
  source_vmid: 101
  clone_mode: full
  target_storage: shared-nvme
  net0: "name=eth0,bridge=vmbr0,ip=dhcp"

ASG_GROUP_web:
  template: web
  min_size: 2
  max_size: 8
  cpu_upper_threshold: 80
  cpu_lower_threshold: 25
  memory_upper_threshold: 80
  memory_lower_threshold: 25
  scale_out_grace_period: 300
  scale_in_grace_period: 600
  scale_in_policy: stop
  allow_destroy: false
  placement:
    strategy: least_loaded     # least_loaded | round_robin | pinned
    exclude_nodes: []
  health:
    probe: none                # none | tcp | http
    port: 80
    path: /healthz
    healthy_threshold: 2
    unhealthy_threshold: 3
    grace_period: 60
  hooks:
    on_instance_ready: null
    on_instance_terminating: null
```

Backward compatibility:

- `HORIZONTAL_SCALING_GROUP_*` keeps working exactly as it does now, on the
  pct path, and keeps its experimental warning.
- On startup, any legacy group logs a one-line deprecation notice with the
  equivalent `ASG_GROUP_*` block, generated from its own values.
- A `scripts/migrate-horizontal-groups.py` prints the converted YAML to stdout.
  It does not rewrite the user's file.
- Removal of the legacy path is not part of this milestone. It gets announced
  here and executed no earlier than the release after the MVP ships stable.

## 8. MVP scope

In scope, and this is the whole list:

1. LXC only. `guest_type: qemu` is parsed and rejected with a clear message.
2. API transport, wired for real, cluster-aware node resolution.
3. Placement across nodes with the `least_loaded` scorer and hard filters.
4. Full create lifecycle: nextid, clone, wait on UPID, apply config, tag,
   start, readiness gate.
5. Scale-in with `stop` by default and `destroy` behind the two opt-ins.
6. Reconciliation from tags on every cycle.
7. Health checks at PVE level, with optional TCP or HTTP probe.
8. Replace of an unhealthy instance, launch before terminate.
9. Ready and terminating hooks.
10. `--dry-run` and `--check-permissions`.
11. Migration path and documentation, experimental warning removed only for
    the new path.

## 9. Explicitly out of scope for this milestone

Listed so that the milestone can actually close:

- QEMU VMs and mixed groups. The data model reserves `guest_type`, nothing more.
- Migration and rebalancing of existing instances.
- Load balancer integrations. Hooks are the integration point.
- cloud-init user-data templating.
- Scheduled scaling and predictive or ML-driven scaling.
- Warm pools and pre-baked standby instances.
- Multi-cluster.
- Template version rollout, that is, replacing all instances when the template
  changes.
- Any dependency on proxmox-cluster-balancer.
- Extraction of a shared core package with proxmox-vm-autoscale. Revisit after
  the MVP has shipped stable, extracting proven code rather than a guess.

## 10. Risks

| Risk | Mitigation |
|---|---|
| The API token lacks a privilege and it only surfaces mid-incident | `--check-permissions` preflight, run at startup and logged |
| A destroy hits a guest outside the group | Tag guard, two opt-ins, dry-run, drain hook |
| Clone storms during a flapping metric | Grace periods, `max_size`, one action per cycle per group |
| Reconciliation adopts a guest a human tagged by accident | Adoption is logged loudly and can be disabled with `reconcile_adopt: false` |
| The MVP grows to include VMs mid-flight | Section 9 is the contract, and `guest_type: qemu` is rejected in code, not by convention |

## 11. Issue map

Milestone [ASG-style horizontal scaling](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/milestone/1).
The chain is tight: #58 is the bottleneck, #56 and #59 are the only two that
can start in parallel.

| Issue | Title | Blocked by | Est. |
|---|---|---|---|
| #56 | ASG-1 wire the backend abstraction into the runtime | - | 1.5 d |
| #57 | ASG-2 resolve the owning node per guest | #56 | 1 d |
| #58 | ASG-3 extend ProxmoxBackend with the ASG primitives | #56 | 2 d |
| #59 | ASG-4 ASG_TEMPLATE_* and ASG_GROUP_* config models | - | 1.5 d |
| #60 | ASG-5 node placement scorer with hard filters | #58 | 1 d |
| #61 | ASG-6 instance create lifecycle | #58 #59 #60 | 2 d |
| #62 | ASG-7 reconcile group state from tags | #58 #59 | 1.5 d |
| #63 | ASG-8 health checks and readiness gate | #61 | 1.5 d |
| #64 | ASG-9 scale-in with stop or destroy, guarded | #61 #62 | 1.5 d |
| #65 | ASG-10 replace unhealthy instances | #63 #64 | 1 d |
| #66 | ASG-11 ready and terminating hooks | #61 #64 | 1 d |
| #67 | ASG-12 --check-permissions preflight | #58 | 0.5 d |
| #68 | ASG-13 controller loop for ASG groups | #60 to #66 | 1 d |
| #69 | ASG-14 docs, migration script, drop experimental | #68 | 1 d |

Roughly 18 person-days.

Outside the milestone, not blocked by it, and worth shipping first because they
affect the current path: #70 (every clone gets the same static IP) and #71
(`min_instances` silently ignored). In the neighbouring repository,
[proxmox-cluster-balancer#3](https://github.com/fabriziosalmi/proxmox-cluster-balancer/issues/3)
records the broken entrypoint that is the reason its placement logic is not
reused here.
