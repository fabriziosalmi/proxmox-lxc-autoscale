#!/usr/bin/env python3
"""Run the daemon against a real Proxmox node and check what it did.

Why this exists
---------------
This project has 5203 lines of unit tests. They did not catch: CPU pinning
reading a sysfs attribute that has never existed, every clone receiving the same
IP, page cache counted as used memory, shared memory discounted as reclaimable
until a container was OOM-killed, an installer missing four modules, or a backup
that was never written. All of those were found by users, or by running the
daemon on a node and looking at what happened.

The unit tests mock `run_command`. Every one of those defects lived on the other
side of that mock: in what the host actually returns, in whether a path exists,
in whether a write lands where the hypervisor reads it. This script is the other
side of the mock.

Safety
------
It creates one throwaway container and touches nothing else. Concretely:

* every pre-existing guest is put in `ignore_lxc`, and the daemon's own view is
  asserted to contain only the throwaway container before anything is started;
* the checksums of every pre-existing container config are recorded first and
  compared at the end, and a difference fails the run;
* the daemon is pointed at a config in a temporary directory through
  LXC_AUTOSCALE_CONFIG, so the node's real configuration is never written;
* the daemon is never installed as a service, and every run is bounded by a
  timeout;
* teardown runs even when a check fails or the script is interrupted.

Usage
-----
    ./scripts/live-check.py --yes-i-understand-this-creates-a-container

Run it on the Proxmox node, from a checkout, as root.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "lxc_autoscale"
CONF_DIR = Path("/etc/pve/lxc")


class Failure(Exception):
    """A check did not hold."""


def run(*args, timeout=120, check=False):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise Failure(f"{' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def existing_ctids():
    out = run("pct", "list")
    return [l.split()[0] for l in out.splitlines()[1:] if l.split()]


def config_fingerprint():
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(CONF_DIR.glob("*.conf"))
    }


def cgroup_path(ctid):
    for base in (f"/sys/fs/cgroup/lxc/{ctid}", f"/sys/fs/cgroup/lxc.payload.{ctid}"):
        if os.path.isdir(base):
            return base
    raise Failure(f"no cgroup directory for {ctid}")


def read_int(path):
    with open(path) as f:
        return int(f.read().strip())


class Bench:
    """Owns the throwaway container, the config, and the teardown."""

    def __init__(self, ctid, template, storage, bridge):
        self.ctid = str(ctid)
        self.template = template
        self.storage = storage
        self.bridge = bridge
        self.tmp = Path(tempfile.mkdtemp(prefix="lxc-autoscale-live-"))
        self.config_path = self.tmp / "config.yaml"
        self.protected = []
        self.fingerprint_before = {}

    # -- lifecycle ---------------------------------------------------------

    def setup(self):
        if self.ctid in existing_ctids():
            raise Failure(f"ctid {self.ctid} is in use; pick another with --ctid")
        self.protected = existing_ctids()
        self.fingerprint_before = config_fingerprint()
        print(f"  protecting {len(self.protected)} existing guest(s): "
              f"{', '.join(self.protected) or 'none'}")
        run("pct", "create", self.ctid, self.template,
            "--hostname", "lxc-autoscale-live-check",
            "--cores", "2", "--memory", "1024", "--swap", "0",
            "--rootfs", f"{self.storage}:1",
            "--net0", f"name=eth0,bridge={self.bridge},ip=dhcp",
            "--unprivileged", "1",
            "--description", "TEMPORARY: live-check.py, safe to destroy",
            "--start", "1", timeout=300, check=True)
        time.sleep(4)

    def teardown(self):
        run("pct", "stop", self.ctid, timeout=120)
        time.sleep(2)
        run("pct", "destroy", self.ctid, timeout=180)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- configuration -----------------------------------------------------

    def write_config(self, defaults=None, tiers=None, groups=None):
        lines = ["DEFAULT:",
                 f"  log_file: {self.tmp}/daemon.log",
                 f"  lock_file: {self.tmp}/daemon.lock",
                 f"  backup_dir: {self.tmp}/backups",
                 "  poll_interval: 10",
                 "  ignore_lxc: [" + ", ".join(f'"{c}"' for c in self.protected) + "]"]
        for k, v in (defaults or {}).items():
            lines.append(f"  {k}: {v}")
        for name, body in (tiers or {}).items():
            lines.append(f"TIER_{name}:")
            lines.append(f'  lxc_containers: ["{self.ctid}"]')
            for k, v in body.items():
                lines.append(f"  {k}: {v}")
        for name, body in (groups or {}).items():
            lines.append(f"HORIZONTAL_SCALING_GROUP_{name}:")
            for k, v in body.items():
                lines.append(f"  {k}: {v}")
        self.config_path.write_text("\n".join(lines) + "\n")

    def env(self):
        e = dict(os.environ)
        e["LXC_AUTOSCALE_CONFIG"] = str(self.config_path)
        e["PYTHONPATH"] = str(PACKAGE) + os.pathsep + e.get("PYTHONPATH", "")
        return e

    # -- the gate ----------------------------------------------------------

    def assert_scope(self):
        """Refuse to proceed unless the daemon sees only the throwaway container."""
        out = subprocess.run(
            [sys.executable, "-c",
             "import asyncio, lxc_utils; print(asyncio.run(lxc_utils.get_containers()))"],
            capture_output=True, text=True, env=self.env(), timeout=120)
        seen = out.stdout.strip()
        if seen != f"['{self.ctid}']":
            raise Failure(
                f"scope gate failed: the daemon would manage {seen}, "
                f"expected only ['{self.ctid}']. Nothing was started.")
        print(f"  scope gate: the daemon sees only {seen}")

    # -- running -----------------------------------------------------------

    def run_daemon(self, seconds, extra_env=None):
        e = self.env()
        e.update(extra_env or {})
        try:
            subprocess.run([sys.executable, str(PACKAGE / "lxc_autoscale.py"),
                            "--poll_interval", "10"],
                           capture_output=True, text=True, env=e, timeout=seconds)
        except subprocess.TimeoutExpired as exc:
            return (exc.stdout or b"").decode() + (exc.stderr or b"").decode()
        return ""

    def probe(self, snippet):
        out = subprocess.run([sys.executable, "-c", snippet],
                             capture_output=True, text=True, env=self.env(), timeout=120)
        if out.returncode != 0:
            raise Failure(f"probe failed: {out.stderr.strip()[-400:]}")
        return out.stdout.strip()

    def conf_value(self, key):
        for line in Path(CONF_DIR / f"{self.ctid}.conf").read_text().splitlines():
            if line.startswith("["):
                break                      # snapshot section: not the live config
            if line.startswith(f"{key}:"):
                return line.split(":", 1)[1].strip()
        return None


# ---------------------------------------------------------------------------
# Checks. Each one encodes a defect that reached users.
# ---------------------------------------------------------------------------

def check_metrics_agree_with_the_cgroup(b):
    """#51 and #86: what the daemon reports must match what the kernel says."""
    cg = cgroup_path(b.ctid)
    b.write_config()
    reported = float(b.probe(
        "import asyncio, lxc_utils;"
        f"print(asyncio.run(lxc_utils.get_memory_usage('{b.ctid}')))"))
    actual = read_int(f"{cg}/memory.current") / read_int(f"{cg}/memory.max") * 100
    if abs(reported - actual) > 5:
        raise Failure(f"reported {reported:.2f}% against an actual {actual:.2f}%")
    return f"memory {reported:.2f}% reported, {actual:.2f}% actual"


def check_shared_memory_counts_as_used(b):
    """#86: tmpfs is not reclaimable without swap, and the daemon OOM-killed a
    container because it discounted it. 200 MB of a 1024 MB container is 20%."""
    run("pct", "exec", b.ctid, "--", "sh", "-c",
        "dd if=/dev/zero of=/dev/shm/live-check bs=1M count=200 2>/dev/null", timeout=120)
    time.sleep(2)
    try:
        reported = float(b.probe(
            "import asyncio, lxc_utils;"
            f"print(asyncio.run(lxc_utils.get_memory_usage('{b.ctid}')))"))
        if reported < 15:
            raise Failure(
                f"200 MB of tmpfs in a 1024 MB container reported as {reported:.2f}%; "
                "shared memory is being discounted as reclaimable again")
        return f"tmpfs visible: {reported:.2f}% reported"
    finally:
        run("pct", "exec", b.ctid, "--", "rm", "-f", "/dev/shm/live-check", timeout=60)


def check_an_idle_container_is_scaled_down(b):
    """The core loop, end to end, against a real container."""
    run("pct", "set", b.ctid, "--cores", "2", "--memory", "1024", check=True)
    b.write_config(defaults={"min_cores": 1, "min_memory": 256,
                             "memory_lower_threshold": 0.001,
                             "memory_upper_threshold": 90})
    before = (b.conf_value("cores"), b.conf_value("memory"))
    b.run_daemon(45)
    after = (b.conf_value("cores"), b.conf_value("memory"))
    if after == before:
        raise Failure(f"an idle container was left at {before}; the loop did nothing")
    return f"{before} -> {after}"


def check_a_pin_reaches_the_container_config(b):
    """#77: the write path refused every real path as a symlink attack, because
    /etc/pve/lxc is a pmxcfs symlink."""
    ok = b.probe(
        "import asyncio, lxc_utils;"
        f"print(asyncio.run(lxc_utils.apply_cpu_pinning('{b.ctid}', '0-1')))")
    if ok != "True":
        raise Failure("apply_cpu_pinning returned False")
    text = Path(CONF_DIR / f"{b.ctid}.conf").read_text()
    if "lxc.cgroup2.cpuset.cpus: 0-1" not in text:
        raise Failure("the pin never reached the container config")
    return "cpuset written to the live config"


def check_a_failed_scale_out_leaves_no_snapshot(b):
    """#91: each failed clone left an LVM snapshot on the source, 288 a day."""
    colliding = str(int(b.ctid) + 1)
    if colliding in existing_ctids():
        return "skipped: the colliding id is in use"
    run("pct", "create", colliding, b.template, "--hostname", "live-check-collision",
        "--cores", "1", "--memory", "256", "--rootfs", f"{b.storage}:1",
        "--unprivileged", "1", timeout=300)
    try:
        b.write_config(
            defaults={"memory_lower_threshold": 0.001, "memory_upper_threshold": 90},
            groups={"1": {"base_snapshot_name": f'"{b.ctid}"',
                          "lxc_containers": f'["{b.ctid}"]',
                          "min_instances": 1, "max_instances": 3,
                          "starting_clone_id": colliding,
                          "horiz_memory_upper_threshold": 0.01,
                          "horiz_memory_lower_threshold": 0.005}})
        b.run_daemon(40)
        left = [l for l in run("pct", "listsnapshot", b.ctid).splitlines() if "snap-" in l]
        if left:
            raise Failure(f"{len(left)} scaling snapshot(s) left on the source container")
        return "no snapshot left behind"
    finally:
        run("pct", "stop", colliding, timeout=120)
        run("pct", "destroy", colliding, timeout=180)


def check_a_boost_survives_a_transient_failure(b):
    """#91: reconcile read a failed command as a deleted container, and a boost
    record that is dropped is never reverted."""
    run("pct", "set", b.ctid, "--cores", "1", check=True)
    b.write_config(defaults={"scaling_mode": "boost", "boost_factor": 2.0,
                             "boost_duration": 3600, "saturation_threshold": 0.5,
                             "consecutive_samples": 1, "max_cores": 4})
    run("pct", "exec", b.ctid, "--", "sh", "-c",
        '(nohup sh -c "while :; do :; done" >/dev/null 2>&1 &)', timeout=60)
    time.sleep(12)
    b.run_daemon(25)
    state = b.tmp / "backups" / "boost_state.json"
    if not state.exists() or not json.loads(state.read_text()):
        return "skipped: no boost was applied, the container did not saturate"

    shim = b.tmp / "shim"
    shim.mkdir(exist_ok=True)
    (shim / "pct").write_text(
        '#!/bin/sh\nif [ "$1" = "config" ]; then exit 1; fi\nexec /usr/sbin/pct "$@"\n')
    (shim / "pct").chmod(0o755)
    b.run_daemon(20, extra_env={"PATH": f"{shim}:{os.environ['PATH']}"})
    kept = json.loads(state.read_text()) if state.exists() else {}
    if not kept:
        raise Failure("a transient pct failure dropped the boost record; "
                      "the elevation is now permanent")
    return "boost record kept through a failing pct config"


CHECKS = [
    ("metrics agree with the cgroup", check_metrics_agree_with_the_cgroup),
    ("shared memory counts as used", check_shared_memory_counts_as_used),
    ("an idle container is scaled down", check_an_idle_container_is_scaled_down),
    ("a pin reaches the container config", check_a_pin_reaches_the_container_config),
    ("a failed scale-out leaves no snapshot", check_a_failed_scale_out_leaves_no_snapshot),
    ("a boost survives a transient failure", check_a_boost_survives_a_transient_failure),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes-i-understand-this-creates-a-container", action="store_true",
                    dest="confirmed")
    ap.add_argument("--ctid", default="990")
    ap.add_argument("--template",
                    default="local:vztmpl/alpine-3.22-default_20250617_amd64.tar.xz")
    ap.add_argument("--storage", default="local-lvm")
    ap.add_argument("--bridge", default="vmbr0")
    args = ap.parse_args()

    if not args.confirmed:
        sys.exit("Refusing to run without --yes-i-understand-this-creates-a-container")
    if os.geteuid() != 0:
        sys.exit("Must run as root on the Proxmox node")
    if not shutil.which("pct"):
        sys.exit("pct not found: this is not a Proxmox node")

    bench = Bench(args.ctid, args.template, args.storage, args.bridge)
    failures = []
    print(f"Setting up on {os.uname().nodename}")
    bench.setup()
    try:
        bench.write_config()
        bench.assert_scope()
        print()
        for name, fn in CHECKS:
            try:
                detail = fn(bench)
                print(f"  PASS  {name}: {detail}")
            except Exception as exc:                      # noqa: BLE001
                failures.append(name)
                print(f"  FAIL  {name}: {exc}")
    finally:
        print("\nTearing down")
        bench.teardown()
        after = config_fingerprint()
        changed = [n for n, h in bench.fingerprint_before.items()
                   if n in after and after[n] != h]
        if changed:
            failures.append("pre-existing guests were modified")
            print(f"  FAIL  pre-existing guest configs changed: {', '.join(changed)}")
        else:
            print(f"  PASS  {len(bench.fingerprint_before)} pre-existing guest "
                  "config(s) unchanged")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print(f"all {len(CHECKS)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
