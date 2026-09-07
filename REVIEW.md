# Critical review — proxmox-lxc-autoscale

**Reviewed at** `41e5253` (2026-09-07) · **Scope** entire repository: 4,005 lines of production Python, 5,203 lines of tests, 2,050 lines of documentation across 17 files, installer, packaging, CI, project history and issue record.

**Method.** Every claim below was checked against the source at the reviewed commit, against primary upstream sources (Linux kernel tree, Proxmox VE documentation) where the code depends on external behaviour, and against the repository's own history. Nothing here is inferred from the documentation, because the documentation is one of the things under review.

**Purpose.** This document enumerates weaknesses. It deliberately proposes no remedies: naming the defect and choosing the fix are separate exercises, and mixing them tends to shrink the defect to the size of the fix that came to mind.

---

## 0. Verdict

The project is a competent-looking daemon whose headline features have, for extended periods, done nothing at all while reporting success. That is not a collection of bugs. It is a single systemic property: **this codebase has no mechanism that can tell the difference between working and not working**, and it never had one. Every individual defect below is downstream of that.

The evidence is not circumstantial. Between March and September 2026 the project shipped, as documented and advertised features:

- CPU core pinning that read a sysfs attribute which has never existed in any Linux kernel, on any vendor. It pinned every container to every core and called that success, for five months, across two releases.
- Horizontal scaling that assigned the same IP address to every clone it created.
- Memory accounting that counted reclaimable page cache as used, so containers doing file I/O never scaled down.
- An installer that, for the whole of v2.0.0 and v2.0.1, downloaded nine of the thirteen modules the daemon imports, so a fresh install could not start.
- A backup-and-rollback safety net that has never written a single backup file.
- A secret-masking log filter, listed as a security feature, attached in a way that means it never sees the output of any module in the daemon.

And two that are not historical but current, found by running the daemon against a live Proxmox node rather than by reading it. The daemon shrank a container holding 200 MB of unreclaimable shared memory, which it measured as 0.4% used, until the kernel OOM-killed a process inside it — see §16.5, and note that this defect was introduced by the author of this review. And: enabling CPU pinning on a tier silently disables that tier's CPU scaling, permanently, from the next container restart. Both features remain documented, separately, as working. See §16.1.

Four of those five were found by **users**, not by the project's 5,203 lines of tests, and not by CI. The fifth is still unfixed and still advertised.

A tool that rewrites the configuration of running guests on a hypervisor, as root, and cannot detect its own failure, is not a small-stakes tool. The correct posture toward the current codebase is that its output should not be trusted without independent verification on the host.

---

## 1. Scorecard

Dimensions chosen because they are the ones that decide whether infrastructure software survives contact with production. Scores are absolute, not relative to project size or maintainer count.

| # | Dimension | Score | One-line assessment |
|---|---|---|---|
| 1 | Truthfulness of the artifact | **2/10** | Documentation describes a system that does not exist, in the present tense, today. |
| 2 | Functional correctness of headline features | **2/10** | Three of the six advertised capabilities were fully non-functional at some point in 2026; one still is. |
| 3 | Resource model and control theory | **1/10** | Not a controller. No feedback, no hysteresis, no admission control; the accounting is arithmetically wrong and the decrement path mixes units. |
| 4 | Failure semantics | **1/10** | Memory mismeasurement drove a container to an OOM kill under test. The daemon dies permanently on any unanticipated exception. |
| 5 | State durability and recovery | **1/10** | Critical state lives in process memory. The documented recovery mechanism has never functioned. |
| 6 | Architecture and cohesion | **4/10** | Reasonable shapes, undermined by dead abstractions, duplicated logic and module-level global state. |
| 7 | Test assurance (as distinct from test volume) | **3/10** | More test code than production code, and it caught none of the five outages above. |
| 8 | Security and blast radius | **3/10** | Genuine hardening effort, misdirected: the guards are real, the exposures are elsewhere, and the advertised log masking does not run. |
| 9 | Distribution and release engineering | **3/10** | `curl \| bash` from an unpinned branch, no packaging, releases that do not correspond to working software. |
| 10 | Observability and operability | **4/10** | Logs are plentiful and say the wrong thing. Nothing measures outcomes. |
| 11 | Product definition and market fit | **3/10** | Solves a problem whose severity is asserted rather than demonstrated, for a user who is never characterised. |
| 12 | Governance and sustainability | **2/10** | Bus factor 1, no independent review, and a documented pattern of fabricated technical claims in commit messages. |

---

## 2. Truthfulness of the artifact

This is the first dimension because it is the one that makes all the others unauditable. A reader cannot use the documentation to understand the system, which means every future contributor, and the maintainer after enough time has passed, must read the source to learn what the software does.

These are **current**, at the reviewed commit, not historical:

| Claim | Location | Reality |
|---|---|---|
| "Dual backend: CLI or Proxmox REST API" | `README.md:25` | `lxc_autoscale/backends/` is 372 lines of ABC, two implementations and a factory that **no production module imports**. `defaults.backend` is read only by `tests/test_backend_factory.py`. Selecting `backend: api` changes nothing. |
| "backs up container settings before making changes and supports rollback via `--rollback`" | `README.md:160` | `backup_container_settings` is reachable only from `get_container_data` (`lxc_autoscale/lxc_utils.py:1186`), which nothing calls. No backup file is ever written. `--rollback` iterates every container, finds nothing, logs "Rollback process completed." |
| "The detected groups are logged at startup" | `README.md:114`, `lxc_autoscale/lxc_autoscale.yaml:159` | Detection is lazy, reached only from `resolve_cpu_pinning` (`lxc_utils.py:593`). A host with no tier configuring `cpu_pinning` never logs it at all. |
| "CPU core pinning for Intel hybrid CPUs (Alder Lake+): pin containers to P-cores or E-cores" | `README.md:30` | Describes the feature as it was before the vendor-neutral rework. The `l3:N` and `numa:N` groups, which are the ones that work on the majority of hosts, do not appear in the feature list at all. |
| "Python 3.9+", with a badge | `README.md:5`, `README.md:53`, `docs/guide/getting-started.md:6` | The project's own CI comment in `.github/workflows/tests.yml` states the daemon **does not run** on 3.9, because a module-scope `asyncio.Lock()` binds an event loop that `asyncio.run()` then replaces. The test matrix starts at 3.10. `install.sh` performs no version check. Proxmox VE 7 ships Python 3.9. |
| "Tested with Proxmox 8.x (8.3.3+)" | `README.md:13` | There is no integration test in the repository. Every test mocks `run_command`. No artifact substantiates the word "tested" in the sense a reader will understand it. |
| "Host CPU and memory reservation to prevent over-allocation" | `README.md:33` | See §4. The reservation is applied twice and the budget ignores what containers already hold, so it prevents nothing. |

The mechanism that lets these survive is still in place. All three configuration models set Pydantic to accept unknown keys (`config.py:134`, `:193`, `:226`), and the warning added when this was last diagnosed covers **only** horizontal scaling groups (`config.py:384`). Reproduced: a tier declaring `cpu_upper_treshold: 95` is accepted, the misspelled key is stored on the model, the effective threshold silently falls back to the default 80, and nothing is logged at any level. The defect that produced the `min_instances` incident was fixed in one of the three places it lives.

A neighbouring case has no guard at all: a container listed in two tier blocks resolves to whichever tier the YAML parser reached last, with no warning. Reproduced with the same container in a two-core tier and a sixteen-core tier — the sixteen-core tier wins, because of key ordering in a file. The safe assumption and the actual behaviour point in opposite directions.

The pattern is consistent enough to be diagnostic. Documentation is written at the moment of intent and never revisited against behaviour, and no process exists that would force the comparison. The `min_instances` defect (#71) is the purest specimen: the guide documented one key name, the code read another, and the configuration model was set to silently swallow unknown keys, so the three could disagree indefinitely without a single log line.

Note the second-order effect. When an external contributor filed #75, they spent two days debugging against a premise — "`topology/core_type` is available on kernel 5.18+", from commit `0052ff3` — that had been invented and never verified. Untrue documentation does not merely fail to help; it actively consumes the goodwill of the few people who try to contribute.

---

## 3. Functional correctness of the headline features

An audit of what the software actually does, feature by feature, ignoring what it says it does.

| Feature | Status | Notes |
|---|---|---|
| Vertical CPU/memory scaling | Works, model is unsound, disabled by pinning | The mechanism issues `pct set`. Whether it should is §4. Setting `cpu_pinning` on the tier silently stops it having any effect: §16.1. |
| Memory measurement | Fixed 2026-08-12 | Counted page cache as used until #51. Broken since the cgroup rewrite. |
| CPU core pinning | Fixed 2026-09-06, incompletely | Read a nonexistent kernel attribute from March to September. Now reads the hybrid perf PMU, but `/sys/devices/cpu_lowpower` is not enumerated, so on Lunar Lake and Arrow Lake-H parts the low-power E-cores belong to no group. |
| Horizontal scaling | **Non-functional**, still shipped | See below. |
| REST API backend | **Non-functional**, still advertised | Dead code since it was written. |
| Backup / rollback | **Non-functional**, still advertised | Never wrote a file. |
| Boost mode | Works, fails permanently | 281 lines whose every failure path converts a temporary boost into a permanent one. See §4.1. |

Horizontal scaling deserves its own paragraph because it is documented as experimental and that word is doing more work than it can bear. `scale_in` (`lxc_autoscale/scaling_manager.py:599`) stops the last container and never destroys it, while the next `scale_out` derives the new container id by adding the member count to a base id. After one scale-in the arithmetic returns an id that still exists, so the clone fails, deterministically, every time. Group membership is mutated in a module-level dictionary (`scaling_manager.py:28`, `:583`), so a daemon restart forgets every container it ever created: they are not counted, not scaled in, and their ids are recomputed and reused. The feature cannot survive its second scaling event or its first restart. "Experimental" implies rough edges, not a two-event lifetime.

---

## 4. The resource model is not a control system

This is the deepest design problem, and unlike the others it will not be fixed by patches.

**The reservation is applied twice.** `get_total_cores` (`lxc_autoscale/lxc_utils.py`) subtracts `reserve_cpu_percent` before returning. `adjust_resources` (`scaling_manager.py:230-234`) then subtracts it again from that result, and does the same with `reserve_memory_mb`. With the shipped defaults a declared 10% CPU reserve is 19% and a declared 2048 MB memory reserve is 4096 MB. Nobody noticed because nothing measures the outcome.

**The budget is fictional.** `available_cores` and `available_memory` start each cycle at host capacity and are decremented only by the increments granted *within that cycle*. They are never reduced by what containers already hold. On a 32-core host running twenty containers with four cores each, the daemon believes it has roughly twenty-six cores free. For CPU this is defensible, since `cores` is a cpulimit and overcommit is normal — but then the reservation is theatre. For memory it is not defensible: LXC memory is a hard cap, and handing out memory the host does not have is how a host starts OOM-killing.

**There is no controller.** The loop compares an instantaneous sample against a fixed threshold and acts. There is no hysteresis beyond the gap between the upper and lower thresholds, no cooldown on vertical scaling (only horizontal scaling has grace periods), no damping, no rate limit, and no notion of a setpoint. A container oscillating around a threshold receives a `pct set` on every poll, indefinitely. On a cluster that means a write to `/etc/pve` — a replicated Corosync-backed filesystem — every poll interval, per flapping container, forever. The cost of that write is borne by every node in the cluster.

**The measurement and the actuator interact perversely.** CPU usage is normalised by the container's core count. Adding a core mechanically reduces the reported percentage without any change in workload, which is precisely the input that will later trigger a scale-down. The system's own actions move its measurement. Nothing in the design acknowledges this.

### 4.1 A temporary feature with no failure path that stays temporary

Boost mode elevates a container's resources for a bounded duration and reverts them. The entire value of the feature is the reversion. Not one of its failure paths preserves it.

`BoostManager.reconcile` (`lxc_autoscale/boost.py:222`) runs once at startup and asks the host for each boosted container's live configuration. When that command returns nothing it treats the container as gone and drops the record. But `run_command` returns nothing on timeout, on non-zero exit and on OS error, not only on absence. A single slow `pct config` during startup — the moment the host is least responsive — makes the daemon forget that a container is boosted, and a forgotten boost is never reverted: the elevated allocation silently becomes the new permanent baseline.

The persistence layer fails the same way. The state file is written with truncate-then-write and no atomic replace (`boost.py:193`), so a crash mid-write leaves malformed JSON; `load` catches the decode error, logs it, and continues with no boosts at all. Adding a field to `BoostRecord` produces the same outcome through `TypeError`. In every case the containers stay boosted and nothing remembers that they should not be.

The reconcile also does not persist the removals it makes when it adopts an admin's manual change; only the "container disappeared" branch saves. The file and memory diverge, and the next restart re-litigates a decision already taken.

Finally, the docstring of `reconcile` states that an expired boost is queued for revert. The function contains no expiry branch. Expiry happens to be handled later in the scaling loop, so the behaviour is covered — but the documentation of a function does not match the function, in the module whose correctness depends entirely on things being undone on time.

### 4.2 The arithmetic climbs in steps and falls off a cliff

`calculate_increment` and `calculate_decrement` (`lxc_autoscale/scaling_manager.py`) are not symmetric, and nothing in the configuration exposes the asymmetry.

Scale-up is capped by `core_max_increment`, default 2. A container at 95% CPU and one at 200% receive the same two cores.

Scale-down has no ceiling at all. The `min_decrease_chunk` setting is a floor, not a limit. A container holding eight cores and reporting 0% usage is decremented by **seven in a single cycle**, straight to the minimum.

Read that together with §5: a measurement failure reports 0%. So one failed sample takes a container from eight cores to one, in one poll, and the climb back is two cores per five-minute interval. The system is built to descend twenty times faster than it ascends, on the input it produces when it is broken.

The memory path is worse, because the same function is reused across two different units. Its proportional term divides a percentage difference by `CPU_SCALE_DIVISOR`, a CPU-domain constant, and then compares the result against a delta expressed in megabytes. The comparison is dimensionally meaningless, and the consequence is measurable: a 1 GB container and a 16 GB container, both reporting 0% memory usage, are both decremented by exactly `min_decrease_chunk`. The proportional logic never wins and never has. Memory scale-down is a constant with the appearance of a calculation.

**Nothing closes the loop.** No metric records whether a scaling decision improved anything. The daemon cannot distinguish a container that was helped from one that was resized pointlessly, so no configuration can ever be shown to be better than another. The `calculate_dynamic_thresholds` function, which would have been the beginning of adaptivity, exists in `scaling_manager.py` and is called by nothing but a test.

---

## 5. Failure semantics: everything degrades toward shrinking

Infrastructure software is judged by what it does when its inputs are wrong. Here the answer is uniform and dangerous.

`get_cpu_usage` returns **0.0** when every measurement method fails. `get_memory_usage` does the same. Zero is below `cpu_lower_threshold`, so a total measurement failure is indistinguishable from an idle container and the daemon responds by removing resources.

**How likely that is was measured rather than assumed, and the answer moderates this section.** With `pvesh` and the cgroup reads both broken by injected failure on a live host, the chain fell through to the `pct exec` method and reported 78–92% on a container that was genuinely saturated. Nothing was scaled down. The four-method fallback is real and it works. Reaching 0.0 requires all four to fail while `pct config` and `pct status` still succeed — realistic mainly for a container with no shell for `pct exec` to use, on a host where the cgroup path is also unreadable. That is a narrow window, and the earlier drafts of this review overstated it.

What survives the correction is the *direction*: when the window is entered, the value chosen is the one that means "idle", and idle means shrink. A system may reasonably fail closed or fail open; this one fails toward taking resources away, and that choice is nowhere stated.

The same measurement showed that the first cycle after a start does **not** return 0.0 on a normal host: `pvesh` is tried first and yields an instantaneous value with no delta, so a freshly started daemon read 97.57% on a loaded container. The "every restart shrinks every container" claim applies only when the cgroup method is the one used, and is withdrawn as a general statement.

The `pvesh` method is tried first for every container, and when the container is not present in the cluster resource list it returns 0.0 rather than raising (`lxc_utils.py:975-978`). Because the caller accepts any value `>= 0.0` as a successful measurement, that path is treated as success and the three fallback methods are never consulted. The most fragile branch of the measurement chain is also the one that silently pre-empts the others.

On the remote-managed path there is a way for the daemon to manufacture this failure itself. `AsyncSSHPool` (`lxc_autoscale/ssh.py:60`) is described as a pool with `max_connections=4`, but that bound applies only to the *idle* queue: `_acquire` opens a new client whenever the queue is empty, and `_release` closes anything that will not fit back in. Live concurrency is therefore bounded not by the configured limit but by the default thread executor, which is `min(32, cpu_count + 4)` — twelve to twenty on a typical node. Since container data is collected with a single `asyncio.gather` across every container, a host with more than about ten containers opens more simultaneous SSH connections than a default `sshd` will accept: OpenSSH's `MaxStartups` defaults to `10:30:100`, which begins refusing at random past ten unauthenticated connections. Each refusal returns nothing from `run_command`, which becomes a 0.0 measurement, which becomes a scale-down. The transport does not merely fail under load; it fails in the direction that removes resources, and the load is self-inflicted.

Two further properties compound this:

- `main_loop` catches only `ValueError`, `OSError` and `KeyError` (`resource_manager.py:178`). Any other exception escapes the `while True` and terminates the process.
- The unit file sets `Restart=no` (`lxc_autoscale/lxc_autoscale.service:8`). The daemon that just died stays dead until a human notices.

A `TypeError` from a malformed `pct` output therefore ends autoscaling for that host silently and permanently. The only signal is the absence of log lines, which is the one signal no one monitors.

---

## 6. State and durability

The daemon keeps its consequential state in module-level dictionaries: horizontal group membership and last-action timestamps (`scaling_manager.py:28`), applied CPU pinning, cgroup path caches, previous CPU readings. All of it dies with the process, and none of it is reconciled against the cluster on start.

The consequences are not symmetrical. Losing a cache costs a re-read. Losing group membership means the daemon disowns containers it created, which continue to run and consume resources while being invisible to the system that made them. That is a resource leak with a persistent footprint on a hypervisor.

The one durable mechanism that exists — the backup directory, the `--rollback` flag, the pruning helper — is entirely unreachable. `backup_container_settings` is called from a dead function; `prune_old_backups` is called from nothing at all and, were it called, implements semantics its own parameter name contradicts, since there is exactly one file per container and pruning by modification time would delete other containers' backups rather than older versions of the same one.

So the system has: no persistence for what matters, and an elaborate persistence mechanism for what it does not do.

---

## 7. Architecture

The shapes are mostly sensible. `asyncio` throughout, Pydantic configuration models, a state-cache object replacing scattered globals, a backend abstraction, per-container locks. This is a maintainer who knows what good structure looks like.

The execution undermines it:

- **A 372-line abstraction with no consumers.** `lxc_autoscale/backends/` exists, is tested, is advertised, and is imported by nothing. It is the largest single piece of dead weight, and its existence in the README is what makes it dangerous rather than merely wasteful.
- **Two implementations of memory scaling.** `scale_memory` in `scaling_manager.py` is dead; `adjust_resources` contains its own inline copy of the same logic. They differ. Only one runs.
- **Two implementations of container data collection.** `lxc_utils.get_container_data` and `resource_manager.collect_data_for_container` do the same work; the first is dead, and its death is what silently disabled backups.
- **`errors.py`**, 51 lines of exception hierarchy, is imported by no production module.
- **Configuration is a module-level singleton evaluated at import.** `config.py` builds `DEFAULTS`, `LXC_TIER_ASSOCIATIONS` and `HORIZONTAL_SCALING_GROUPS` as dictionaries at import time, and `scaling_manager` mutates the last of these at runtime. This is why the horizontal-scaling state problem exists at all, and it makes reload-without-restart structurally impossible.
- **The energy-saving branch fights the scaling branch.** Within a single iteration of `adjust_resources`, a container can be granted more cores by the threshold logic and then immediately reset to minimum by the off-peak block, which evaluates against the pre-change values. Two `pct set` calls per cycle, in opposite directions.

Roughly 13% of the production Python is unreachable: 527 lines, measured. That is not a tidiness complaint: three of the defects in this review exist *because* code that looked live was dead, and nothing in the toolchain distinguishes the two.

---

## 8. Testing: volume without assurance

5,203 lines of tests against 4,005 lines of production code, green across five Python versions in CI at the reviewed commit.

This suite did not catch: pinning reading a nonexistent kernel file for five months; every clone receiving the same IP; page cache counted as used memory; an installer missing four modules; backups never being written. All five were found by users or by adversarial review.

The reasons are structural, not incidental:

- **The tests mock the boundary the defects live behind.** `run_command` is patched in 30 places in `tests/test_lxc_utils.py` alone. Every defect above lived in what happens *outside* that mock — in what the host actually returns, in whether the path exists, in whether the write lands.
- **Fixtures were invented rather than captured.** PR #76 shipped a hybrid Intel fixture synthesised from `core_type:` lines no kernel emits. Three tests certified the feature green precisely because the input was fictional. A test whose fixture is authored by the same belief that produced the bug cannot detect the bug.
- **Until 2026-09-06, CI never ran the suite at all.** The only Python workflow ran `pylint`. Every change that broke a test reached `main` with all checks green, for the entire life of the test suite.
- **Until 2026-08-25, pull requests from forks ran no checks whatsoever**, because the workflow triggered on `push` only. External contributions — the ones most in need of verification — were the only ones that received none.
- **No integration test exists.** Nothing exercises a real `pct`, a real sysfs tree or a real config file, with the honourable exception of `tests/test_cpu_pinning_write.py`, added on 2026-09-06, which does construct a real symlinked directory. That file is the template the rest of the suite is not.

The suite measures whether the code still does what it did yesterday. It has never been able to measure whether what it does is right.

---

## 9. Security and blast radius

The security work in this repository is real and better than average for the category: host-key policy defaulting to reject, secret masking in logs, `${ENV_VAR}` expansion so secrets need not sit in YAML, native file I/O instead of shell interpolation, symlink guards, a non-root Docker path. The v2.0 hardening was a serious effort.

It is also aimed slightly to the left of the actual exposure.

- **The installer never protects the configuration file.** `install.sh` downloads `lxc_autoscale.yaml` into `/etc/lxc_autoscale/` and never chmods it. That file is where `ssh_password` and `token_value` are documented to live. `config.py` only *warns* at startup if the file is group- or world-readable, which is a message in a log nobody reads, on a hypervisor.
- **The symlink guard was aimed at the wrong threat and blocked the legitimate path.** Until 2026-09-06, the pinning write path refused every write on every Proxmox node, because `/etc/pve/lxc` is a pmxcfs symlink to `nodes/<hostname>/lxc/` — documented behaviour of the product this daemon exists to manage. A guard against an attack nobody was mounting prevented the only operation the feature performs.
- **The daemon runs as root with no systemd confinement.** The unit sets `User=root` and nothing else: no `ProtectSystem`, `PrivateTmp`, `NoNewPrivileges`, `ReadWritePaths`. A daemon that writes guest configuration and executes `pct` has an obvious hardening surface that is entirely unused.
- **The advertised secret masking does not run on the loggers that produce the output.** `logging_setup.py:74` attaches `SecretMaskingFilter` to the root *logger*. In Python, a filter on a logger applies only to records emitted through that logger; records from child loggers reach the root logger's *handlers* without passing its filters. Every module in this project uses `logging.getLogger(__name__)`. Reproduced: of three log lines containing a password, the one emitted on the root logger is redacted and the two from module loggers are written verbatim. The README lists this control as a feature.
- **There is a live path for that leak.** The Uptime Kuma integration is documented with the push identifier inside the URL path (`docs/guide/notifications.md:32`). On any failure, `notification.py:124` logs the `requests` exception through a module logger, and that exception message embeds the full URL including the identifier. So a Kuma outage writes the push token in clear text into `/var/log/lxc_autoscale.log`. Even if the filter did run, the pattern set would not catch it: the token is not adjacent to a keyword it recognises and is shorter than its 32-character generic threshold.
- **The `auto` SSH host-key policy still exists**, marked deprecated with a loud warning and no removal date. Deprecation without a date is a permanent feature with a disclaimer.
- **The Docker entrypoint does the thing the comment directly above it forbids.** `lxc_autoscale/entrypoint.sh:41` states, in the imperative, never to disable strict host key checking and to supply a `known_hosts` file. Fifteen lines later, when no such file is found, it runs `ssh-keyscan` against the target host and writes whatever key comes back. That is trust-on-first-use: it accepts an unverified key at exactly the moment an interception would be mounted, which is the property the comment exists to prevent. The warning is printed and the insecure path is taken anyway.
- **The Docker image runs as root by default.** The non-root user exists and is opt-in via an environment variable, which inverts the default that matters.

The blast radius deserves stating plainly, because none of the individual items above convey it: this software runs as root on a hypervisor, rewrites the configuration files of running guests, and — as demonstrated repeatedly — cannot tell when its own writes are wrong. A malformed cpuset written into a container config prevents that container from starting. That specific failure was reachable from a typo in a tier definition until 2026-09-07.

---

## 10. Distribution and release engineering

- **There is no package.** `pyproject.toml` contains a pytest section and nothing else: no project metadata, no build backend, no entry point. The software cannot be installed with `pip`, cannot be published, and cannot be pinned by any standard dependency mechanism.
- **The distribution channel is `curl | bash` as root, from an unpinned branch.** `install.sh:7` defaults `REF` to `main`. The README documents only the unpinned form. An installation performed today receives whatever was merged this morning, including work that has never appeared in a release.
- **Releases do not correspond to working software.** The current tag, `v2.0.2` (2026-08-13), contains the pinning feature in its fully non-functional state. Eleven commits, including four fixes to that feature, sit unreleased on `main`. A user who does the responsible thing and pins a tag gets the broken version; a user who does the reckless thing and installs from `main` gets the fixed one.
- **The module list in the installer is maintained by hand.** `install.sh` carries an explicit array of every Python file to download. This list drifting out of sync with the package is exactly what broke installation for the whole of v2.0.0 and v2.0.1, and nothing in CI compares the two.
- **Dependencies are installed system-wide on the hypervisor**, including `pip3 install --break-system-packages` when Debian's pydantic is too old, plus `git` and `flask` that the daemon does not use. The web UI those Flask packages are for is not installed by the installer at all.
- **No uninstall verification, no upgrade path, no migration story** for configuration between versions.

---

## 11. Observability and operability

Logging is abundant: a rotating text log, a rotating JSON event log, structured scaling events, notification backoff across three channels. The plumbing is good.

What it lacks is any signal that would have caught a single defect in this review. The logs record *intentions* — "Increase Cores 2", "Scale Out" — and never outcomes. There is no verification that a `pct set` took effect, no metric for how many decisions were made or reversed, no health or readiness endpoint, no Prometheus surface, and no counter that would go flat when the daemon silently stops doing anything. During the five months when pinning did nothing, the logs stated at INFO that pinning was being applied.

The web UI compounds this. `lxc_autoscale/ui/templates/index.html:82` builds log rows by assigning a template literal to `innerHTML`, interpolating fields straight from the JSON event log with no escaping. The current sources of those fields are constrained — a numeric container id, the host's own nodename — so the exposure today is narrow, but the construction is unsafe by default and will not stay narrow as fields are added. The same file loads two decorative icons from `upload.wikimedia.org` and `svgrepo.com` on every render: a management interface for a hypervisor making outbound requests to public sites on page load, in a project that took the trouble to vendor Bootstrap and its fonts locally. It also breaks entirely on an air-gapped node.

Operationally: no dry-run mode anywhere; no way to validate a configuration file without starting the daemon; no reload without restart, and restart carries the shrink-everything behaviour of §5; and the web UI in `lxc_autoscale/ui/` is present in the repository, documented nowhere in the installation path, and not installed by the installer.

---

## 12. Product definition and market

Three uncomfortable questions the project has never answered in writing.

**Who is the user?** Not stated anywhere. The two plausible populations want opposite things. A homelab operator with eight containers on one box wants set-and-forget and will never notice a 10% misallocation — but also will not notice the daemon silently doing nothing, which is precisely the failure mode that shipped. A small hosting operation with a real cluster needs cross-node awareness, auditability and predictable failure, none of which exist. The software is currently built for neither, and the absence of a stated user is why: with no user in mind, "add a feature" always beats "verify a feature".

**Is the problem real at the severity claimed?** LXC `cores` is a cpulimit, not an allocation; on an idle host, an over-provisioned container costs approximately nothing. Memory is a genuine cap, so memory autoscaling has real value — and memory is exactly where the accounting is fictional (§4). Nowhere does the project demonstrate the benefit it delivers: no benchmark, no before/after, no case study. For a tool whose entire value proposition is efficiency, the absence of a single number is telling.

**What is the competitive reality?** Proxmox ships no native autoscaling, so the niche is real. But the alternatives are strong for the likely user: doing nothing, a fifteen-line cron script with `pct set`, or simply provisioning generously since RAM is cheap relative to the operational risk of a root daemon rewriting guest configs. This project must be *more* reliable than a fifteen-line cron script to be worth its blast radius. On the evidence of the last six months, it has not been.

The adoption numbers are consistent with this reading. 258 stars, 15 forks, **5 watchers**, and 19 third-party issues in the 25 months since the repository was created. The ratio of stars to watchers is the signature of a repository that circulates in listicles rather than one that runs in production. Of those 19 issues, at least three report a feature silently doing nothing — a high proportion of a small sample, and the strongest available evidence that the real deployed population is small and encountering fundamental problems immediately.

---

## 13. Governance and sustainability

- **Bus factor 1.** 684 commits, of which roughly 668 are the owner's and 10 are a Copilot agent's. Two external humans have one commit each. Nobody else can review this codebase, and nobody does.
- **No independent review exists in the history.** No approving review from a second person appears on any pull request. Everything merged has been self-approved.
- **Fabricated technical claims in commit messages.** Commit `0052ff3` asserts that a kernel attribute is "available on kernel 5.18+". That attribute has never existed in any kernel version; the claim was checked against the source at ten release tags spanning v4.19 to v6.17 and is false at every one. The claim then propagated into the user-facing guide and cost an external contributor two days. This is a governance finding, not a technical one: a project where unverified assertions enter the permanent record unchallenged will accumulate them.
- **AI-assisted authorship without a verification step.** 21 commits carry an AI co-author trailer. The problem is not the assistance; it is that the assistance produced confident, specific, false technical claims and no part of the process was positioned to catch them. The same tooling that raises output volume also raises the rate of plausible-sounding fiction, and this repository has no counterweight.
- **Contribution friction is high and the return is low.** The single substantial external contribution of 2026 arrived with hardware the maintainer does not own, correct root-cause analysis, and a self-authored correction. It received zero CI checks on arrival, because the workflow could not run for forks. A project this dependent on rare external contributors cannot afford to waste them.
- **Roadmap risk.** `docs/design/asg-horizontal-scaling.md` specifies an AWS-style Auto Scaling Group implementation across 14 open issues, self-estimated at roughly 18 person-days. It is a good document. It is also being built on a foundation where horizontal scaling cannot survive a restart, group state lives in a dictionary, the backup mechanism has never run, and the resource accounting is wrong — and its own issue list has not moved since 2026-08-13. The pattern the project keeps repeating is that new capability is designed while existing capability remains unverified. The ASG milestone is currently the largest instance of that pattern.

---

## 14. Systemic causes

Every finding above reduces to four properties, in descending order of consequence.

1. **Nothing verifies effect.** Not the tests, which mock the boundary; not CI, which until three weeks ago never ran them; not the logs, which record intent; not the code, which never re-reads what it wrote. When effect is unverified, a feature that does nothing is indistinguishable from one that works, and the only detector left is a user with unusual hardware and unusual patience.
2. **Failure is silent and biased in one direction.** Missing measurement becomes zero, which becomes idle, which becomes shrink — by seven cores in one step, where the recovery is two cores per interval. A boost whose bookkeeping is lost becomes permanent rather than being reverted. A write that is refused, a keyword that will not resolve, a state file that will not parse: each produces a log line at most, and the daemon proceeds as if nothing happened. Absent files, unresolvable keywords, and refused writes all produce a log line at most, and the daemon continues as if nothing happened. Silence is the default outcome of every error path in the system, and where the error path has a direction, it points at the operator's expense.
3. **Assertion substitutes for verification.** Documentation, commit messages, README badges and CHANGELOG entries state properties nobody checked. Because the project also lacks mechanism 1, the assertions are never contradicted by evidence, so they persist and compound.
4. **Scope expands faster than the foundation is validated.** Boost mode, tier associations, dual backends, energy mode, horizontal scaling, CPU pinning, an ASG design — while memory measurement was wrong, backups never wrote, and the installer was incomplete. Each new surface adds documentation that will not be revisited and code that may be dead.

---

## 15. Risk register

| Risk | Likelihood | Impact | Notes |
|---|---|---|---|
| Silent no-op: the daemon runs and changes nothing anyone wants | **Occurred, repeatedly** | High | Five instances documented in this review. |
| Resource removal triggered by a monitoring failure | High | High | §5. Requires only a transient `pct` failure. |
| Daemon dies permanently on an unhandled exception | Medium | High | §5. `Restart=no` plus a three-type except clause. |
| Container OOM caused by shmem discounted as reclaimable cache | **Occurred under test** | Critical | §16.5. Any tmpfs or shared-memory workload. |
| Memory over-commitment leading to host OOM | Medium | Critical | §4. No real admission control; LXC memory is a hard cap. |
| Orphaned containers from horizontal scaling | High where enabled | Medium | §3, §6. Restart forgets every clone created. |
| Config-file secret exposure on the hypervisor | Medium | High | §9. Installer sets no mode; code only warns. |
| A pinned release containing a fully broken feature | **Currently true** | Medium | §10. `v2.0.2` is the only tag and pinning is dead in it. |
| Unbounded snapshot accumulation on a failing scale-out | Certain once a group has scaled out and the daemon restarts | High | §16.2. 288 per day at the default interval, never pruned. |
| Capacity stranded below the configured maximum | Certain for many threshold/increment combinations | Low | §16.3. |
| Self-inflicted SSH refusals on a remote-managed host | High above ~10 containers | High | §5. Ends in a fleet-wide scale-down. |
| A configuration typo silently taking effect as a default | Certain over time | Medium | §2. No warning in two of three models. |
| A temporary boost silently becomes permanent | High wherever boost is enabled | Medium | §4.1. One slow command at startup is enough. |
| Notification token written in clear text to the log | High wherever Uptime Kuma is configured | Medium | §9. Every failure logs it. |
| Loss of the single maintainer | Low per year, certain eventually | Critical | §13. No second reviewer, no packaging, no handover surface. |
| ASG milestone built on unverified foundations | High if started as specified | High | §13. 18 person-days on top of the defects above. |

---

## 16. Empirical verification on a live host

Everything above this section was derived from source. This section was measured, on Proxmox VE 9.1.7, kernel 6.17.13-2-pve, an Intel i5-6500 (four cores, no SMT, non-hybrid, single L3, single NUMA node), 32 GB RAM. A throwaway Alpine container was created for the purpose; every pre-existing guest was placed in `ignore_lxc` and the filter was verified before anything was started. The daemon was run in the foreground with a twenty-second interval and never installed as a service. The host was restored afterwards and the pre-existing guests' configuration files were confirmed byte-identical by checksum.

**The kernel attribute is absent, as expected.** The topology directory on this machine contains the seventeen attributes `drivers/base/topology.c` creates and no `core_type`. The hybrid PMU directories are likewise absent, correctly yielding no `p-cores` or `e-cores` group, which is the negative control for the current detection.

**The two new pinning keywords are a no-op on this host, silently.** `l3:0` and `numa:0` both resolve to every online CPU, identically to `all`. Any single-socket machine with one L3 domain — the overwhelming majority of hosts this project runs on — gets a pin to everything, with no warning, from the keywords introduced to replace a bug whose defining symptom was a pin to everything.

**The double reservation is real and large.** On a four-core host with the shipped ten-percent reserve, the daemon's own accounting reports three cores after the first subtraction and two after the second. Half the machine disappears into a reserve the operator configured as a tenth. Memory: 32 GB less 2 GB, less 2 GB again.

**An idle container was stripped in sixty seconds.** Starting at two cores and 1024 MB, with no load, the container reached one core and 512 MB after four cycles — the CPU floor and half the memory, in a minute. Every memory step was exactly 128 MB regardless of the container's size, confirming that the proportional term never participates. Note also that 128 MB is the model's default while the shipped sample configuration states 256: a third value the documentation and the code disagree on.

**No backup was ever written.** The backup directory did not exist when the run finished. The README's claim that settings are backed up before changes is now disproven on live hardware, not merely traced to a dead call site.

**The per-container cost is 1.6 seconds per cycle**, of which 0.9 is a complete `pvesh get /cluster/resources` — the entire cluster resource list, fetched once per container, per cycle, to read one number. Fifty containers is roughly eighty seconds of continuous querying every interval.

### 16.1 The two features that disable each other

This is the finding that only a live host could produce, and it is the most consequential one in this document.

Proxmox derives a container's CPU affinity from its `cores` setting, but `PVE::LXC.pm` guards that assignment: it first scans the configuration for an explicit `lxc.cgroup2.cpuset.cpus` entry, and when one is present it skips the `cores`-derived assignment entirely. The daemon writes exactly that entry whenever `cpu_pinning` is set on a tier.

The consequence was confirmed directly. A container carrying `cores: 1` and a pin of `0-1` reported an effective cpuset of `0` while running, because the live `cores` change had been applied. After a restart, the same container reported an effective cpuset of `0-1` and its own `nproc` returned **2**. The `cores` value had become decorative.

So enabling `cpu_pinning` on a tier silently disables that tier's CPU scaling from the next container start onward, permanently. The daemon goes on computing increments, writing `cores`, and logging "Increase Cores" and "Decrease Cores" for a setting the hypervisor is no longer reading. Two features of the same daemon, each documented on its own page, each working as designed in isolation, cancel each other when combined — and nothing in the code, the configuration or the documentation mentions the interaction.

It also means the vertical scaling this project exists to provide and the pinning it added as a headline feature are mutually exclusive, and no user has been told.

### 16.2 Horizontal scaling, run twice

The group was configured with one member and a clone id base, and the daemon was allowed to scale out. It cloned correctly on the first attempt: a new container appeared and started.

The daemon was then restarted with the same configuration. Because group membership is held in a module-level dictionary and never persisted, the restarted daemon re-read the original YAML and did not know the clone existed. It recomputed the next clone id from the member count it could see, arrived at the id already in use, and `pct clone` failed with "CT 991 already exists on node". It then retried **on every poll**, indefinitely.

Two mechanisms turn that into damage rather than noise.

First, the grace period does not apply. `scale_last_action` is recorded only after a *successful* scale-out, so a failing one is retried at full poll frequency forever, with no throttle at all. The configured five-minute window never engages on the path that needs it.

Second, and worse: each attempt takes an LVM snapshot of the source container *before* attempting the clone, and nothing removes it when the clone fails. Four snapshots accumulated on the source container in ninety seconds of retrying. At the default five-minute interval that is **288 snapshots per day, growing without bound**, on the container the operator nominated as the group's template, on thin-provisioned storage. No code in the project prunes them. This is a slow disk-exhaustion vector on a hypervisor, armed automatically by a documented feature the moment its first scale-out succeeds and the daemon is subsequently restarted.

### 16.3 What the scaling is worth, measured

This is the number the project has never published, and it is a genuine positive.

A container pinned at one core, running two spinning loops, was consuming 97% of a single core: saturated, with the second loop starved. The daemon raised it from one core to three. Throughput measured from the container's own cgroup accounting went to **200% of a core** — both loops running in parallel. The mechanism does what it claims, and the benefit is real and immediate.

Two defects surfaced in the same run.

**The reported percentage moved because the daemon moved it.** With the workload held exactly constant, the CPU figure fell from 97.6% to 66.5% as soon as the core count rose, because the metric is normalised by core count. The controller's own action changes its input in the direction that will later argue for reversing that action. This is the oscillation risk of §4 made visible on the first attempt.

**A container cannot reach its own configured maximum.** With `max_cores: 4`, the container settled at three and stayed there across four further cycles while still reporting 65% against a 50% upper threshold. The reason is in the decision itself: the computed increment is checked with `current + increment <= max_cores` and, when that fails, the increment is **discarded rather than clamped**. At three cores with an increment of two, five exceeds four, so nothing happens — permanently. Any tier whose ceiling is not reachable by exact multiples of the increment leaves capacity stranded, silently, while logging high utilisation every cycle.

### 16.4 Log noise that trains operators to ignore errors

On this host every container produced two `ERROR`-level lines on first sight, for reads of a cgroup path that does not exist on this Proxmox version, before the code fell through to the path that does. The condition is normal, expected, and handled. Logging it at `ERROR` in a daemon whose real failures are silent is precisely backwards.

### 16.5 The memory fix that can kill a container

This is the most severe finding in this document, and it was introduced by the change that fixed the previous most severe one.

Issue #51 was correct: cgroup counters include reclaimable page cache, so containers doing file I/O never appeared idle and never scaled down. The fix, in `aaa502d`, subtracts the `file` key of `memory.stat` from the raw counter. But in cgroup v2, `file` includes **shmem** — tmpfs, `/dev/shm`, and POSIX shared memory. Shmem is not reclaimable when there is no swap: those pages can only be released by deleting the data or by the OOM killer. `memory.stat` publishes `shmem` as its own key, immediately next to `file`. The code subtracts `file` whole.

Measured, on a 512 MB container with swap disabled and 200 MB written to `/dev/shm`:

- the cgroup reported 205 MB in use of 512, that is **39.9% full**, with `file` at 202 MB of which `shmem` was 200 MB;
- `get_memory_usage` returned **0.41%**;
- the daemon, seeing a container two orders of magnitude below its lower threshold, shrank it from 512 MB to the 256 MB floor across four cycles;
- the workload then requested a further 60 MB, an ordinary amount, and `memory.events` recorded `max 38 oom 1 oom_kill 1`. **The kernel killed a process inside the container.**
- at that moment, with the cgroup at 254 MB of 256, the daemon reported **0.79%**.

It cannot recover from this, because the state it created is invisible to it: it will not scale the container back up, since by its own measurement there is nothing to relieve.

The workloads this describes are not exotic. `/run` is tmpfs in every systemd container. PostgreSQL's shared buffers are shared memory. Redis, Chrome, build systems using `/dev/shm` for scratch, anything mounting `/tmp` as tmpfs — all of it is invisible to this accounting. A database container sized for its shared buffers would be reported as empty and scaled into an OOM.

There is a second, quieter fact in the same measurement. The `pct exec` procfs fallback read the container's virtualised `/proc/meminfo` correctly and would have reported roughly 38%, the true figure. The daemon prefers the cgroup path, and the cgroup path is the one that is wrong here.

For the record and by the same standard applied to commit `0052ff3` in §13: this defect was introduced by the author of this review, in PR #52, while fixing a user's correctly-reported bug. The original defect made containers never shrink. Its replacement makes them shrink until the kernel intervenes. That is a worse failure, shipped as a fix, and it passed a test suite, a code review and a CHANGELOG entry that described the change as matching what the Proxmox UI reports — which it does, for page cache, and does not, for shared memory.

### 16.6 Boost: proven permanent on a transient failure

The prediction in §4.1 was tested by injection. A container was boosted from one core to two, with the original value and a one-hour duration correctly persisted to the state file. The daemon was then restarted with `pct config` failing, and nothing else — the container was running and every other command worked.

The reconcile pass logged `Reconcile: container 990 no longer exists, removing boost`, wrote an empty state file, and continued. The container remained at two cores. Its original value of one now exists nowhere: not in the state file, not in memory, not in the configuration. The elevation is permanent, the log line that caused it is false, and nothing will ever revert it.

One failed command, at startup, on a host under load, is all it takes.

### 16.7 Deployment friction, measured

`python3-pydantic` is not present on a stock Proxmox VE 9.1 node. It is available from Debian 13, and installing it pulls **twenty** packages onto the hypervisor, including an email validator and an async HTTP stack, none of which the daemon uses. `install.sh` performs that installation unconditionally, alongside `git` and Flask, on a machine whose package surface is normally kept deliberately small.

## 17. What this review does not claim

Stated explicitly, because a document this negative is easy to over-read.

The code is not badly written. It is legible, consistently styled, typed in places, thoughtfully commented, and the recent work — the pinning investigation, the kernel-source verification in the CHANGELOG, `tests/test_cpu_pinning_write.py`, the CI matrix rationale in `tests.yml` — is of a distinctly higher standard than what preceded it. The v2.0 hardening was real. The response to #75 was fast, honest and technically correct.

The repository history is also clean of committed credentials, which is not universal in this category and is worth stating.

The problem is not competence. It is that this project has been operating without the one mechanism that separates infrastructure software from a script: a way to find out whether it worked. Everything in §14 follows from that absence, and nothing in this review will be durably fixed while it persists.
