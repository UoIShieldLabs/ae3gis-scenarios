#!/usr/bin/env python3
"""
IT/OT Network Scalability Test — Automated Experiment Runner

Runs Modbus/TCP polling experiments at increasing PLC counts, collecting:
  - Latency (RTT): avg, min, max, p95
  - Throughput: bytes/sec
  - Reliability: success rate %
  - Requests/min
  - Boot time per PLC
  - Per-container CPU and memory usage
  - Host resource usage

Each scale point runs multiple trials. Results show mean ± std.
Stops automatically at saturation.

Prerequisites:
  - Docker accessible (user in docker group)
  - Images pulled: itot-plc, itot-scada, itot-dmz
  - Python 3.6+

Usage:
  python3 run_scalability_test.py
  python3 run_scalability_test.py --scales 4,8,16,32 --trials 3 --duration 180
  python3 run_scalability_test.py --image-prefix myuser/
"""

import argparse
import json
import math
import os
import re
import socket
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Default image names — override with --image-prefix or env vars
PLC_IMAGE = os.environ.get("PLC_IMAGE", "itot-plc:v0.2")
SCADA_IMAGE = os.environ.get("SCADA_IMAGE", "itot-scada:v0.2")
DMZ_IMAGE = os.environ.get("DMZ_IMAGE", "itot-dmz:v0.2")

# Network addressing
IT_NET_NAME = "itot-it-net"
OT_NET_NAME = "itot-ot-net"
IT_SUBNET = "192.168.1.0/24"
IT_GATEWAY = "192.168.1.254"
OT_SUBNET = "10.0.0.0/16"
OT_GATEWAY = "10.0.255.254"
DMZ_IT_IP = "192.168.1.1"
DMZ_OT_IP = "10.0.0.1"
SCADA_IP = "192.168.1.10"

# Saturation thresholds
SAT_SUCCESS_RATE = 90.0      # below this % = saturated
SAT_RTT_MULTIPLIER = 10.0    # avg RTT > baseline * this = saturated
SAT_HOST_MEMORY_PCT = 85.0   # host mem usage above this = saturated
SAT_BOOT_TIME_SEC = 120.0    # avg boot time above this = saturated

# Container naming prefix (used for cleanup)
PREFIX = "itot-"


# ═══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TrialResult:
    """Results from a single trial."""
    scale: int
    trial: int
    avg_rtt: float = 0.0
    min_rtt: float = 0.0
    max_rtt: float = 0.0
    p95_rtt: float = 0.0
    throughput_bps: float = 0.0
    total_bytes: int = 0
    requests_per_min: float = 0.0
    success_rate: float = 0.0
    total_requests: int = 0
    avg_boot_time: float = 0.0
    max_boot_time: float = 0.0
    plc_avg_cpu: float = 0.0
    plc_avg_mem_mb: float = 0.0
    scada_cpu: float = 0.0
    scada_mem_mb: float = 0.0
    dmz_cpu: float = 0.0
    dmz_mem_mb: float = 0.0
    host_mem_pct: float = 0.0
    success: bool = True
    error: str = ""


@dataclass
class ScaleResult:
    """Aggregated results for a scale point (across trials)."""
    scale: int
    trials: List[TrialResult] = field(default_factory=list)

    def _successful_trials(self):
        return [t for t in self.trials if t.success]

    def _stat(self, attr):
        vals = [getattr(t, attr) for t in self._successful_trials()]
        if not vals:
            return 0.0, 0.0
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return mean, std

    @property
    def n_success(self):
        return len(self._successful_trials())

    def mean_std(self, attr):
        return self._stat(attr)


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def run_cmd(cmd, check=True, timeout=300):
    """Run a shell command, return stdout."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        if check and result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout.strip(), ""
    except subprocess.TimeoutExpired:
        return None, "Command timed out"
    except Exception as e:
        return None, str(e)


def run_cmd_strict(cmd, timeout=300):
    """Run command, raise on failure."""
    out, err = run_cmd(cmd, check=True, timeout=timeout)
    if out is None:
        raise RuntimeError(f"Command failed: {cmd}\n{err}")
    return out


def plc_ip(i):
    """
    Compute IP for PLC number i (1-indexed).
    PLC 1 -> 10.0.1.1, PLC 254 -> 10.0.1.254, PLC 255 -> 10.0.2.1, etc.
    """
    i_zero = i - 1
    third = i_zero // 254 + 1
    fourth = i_zero % 254 + 1
    return f"10.0.{third}.{fourth}"


def get_host_memory_pct():
    """Get host memory usage percentage."""
    try:
        out = run_cmd_strict("free -m")
        # Parse: Mem: total used free shared buff/cache available
        for line in out.splitlines():
            if line.startswith("Mem:"):
                parts = line.split()
                total = int(parts[1])
                available = int(parts[6])
                used_pct = (total - available) / total * 100
                return used_pct
    except Exception:
        pass
    return 0.0


def log(msg, level="INFO"):
    """Print timestamped log message."""
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {level}: {msg}", flush=True)


def log_progress(current, total, label=""):
    """Print progress bar."""
    pct = current / total * 100 if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {current}/{total} {label} ({pct:.0f}%)", end="", flush=True)


# ═══════════════════════════════════════════════════════════════════
# DOCKER STATS COLLECTOR (background thread)
# ═══════════════════════════════════════════════════════════════════

class StatsCollector:
    """Collects docker stats in a background thread."""

    def __init__(self, interval=10):
        self.interval = interval
        self.running = False
        self.thread = None
        # Accumulated stats: {container_name: [{cpu, mem_mb}, ...]}
        self.samples: Dict[str, List[Dict]] = {}

    def start(self):
        self.running = True
        self.samples = {}
        self.thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=15)

    def _collect_loop(self):
        while self.running:
            try:
                out, _ = run_cmd(
                    'docker stats --no-stream --format \'{"name":"{{.Name}}","cpu":"{{.CPUPerc}}","mem":"{{.MemUsage}}"}\'',
                    check=False, timeout=30
                )
                if out:
                    for line in out.strip().splitlines():
                        try:
                            data = json.loads(line)
                            name = data["name"]
                            if not name.startswith(PREFIX):
                                continue
                            cpu = float(data["cpu"].replace("%", ""))
                            # Parse mem: "12.5MiB / 8GiB" -> 12.5
                            mem_str = data["mem"].split("/")[0].strip()
                            mem_mb = self._parse_mem(mem_str)
                            if name not in self.samples:
                                self.samples[name] = []
                            self.samples[name].append({"cpu": cpu, "mem_mb": mem_mb})
                        except (json.JSONDecodeError, ValueError, KeyError):
                            continue
            except Exception:
                pass
            time.sleep(self.interval)

    @staticmethod
    def _parse_mem(s):
        """Parse memory string like '12.5MiB' or '1.2GiB' to MB."""
        s = s.strip()
        if s.endswith("GiB"):
            return float(s[:-3]) * 1024
        elif s.endswith("MiB"):
            return float(s[:-3])
        elif s.endswith("KiB"):
            return float(s[:-3]) / 1024
        elif s.endswith("B"):
            return float(s[:-1]) / (1024 * 1024)
        return 0.0

    def get_averages(self):
        """Return average CPU/mem per container category."""
        plc_cpus, plc_mems = [], []
        scada_cpu, scada_mem = 0.0, 0.0
        dmz_cpu, dmz_mem = 0.0, 0.0

        for name, samples in self.samples.items():
            if not samples:
                continue
            avg_cpu = statistics.mean(s["cpu"] for s in samples)
            avg_mem = statistics.mean(s["mem_mb"] for s in samples)

            if "plc" in name:
                plc_cpus.append(avg_cpu)
                plc_mems.append(avg_mem)
            elif "scada" in name:
                scada_cpu = avg_cpu
                scada_mem = avg_mem
            elif "dmz" in name:
                dmz_cpu = avg_cpu
                dmz_mem = avg_mem

        return {
            "plc_avg_cpu": statistics.mean(plc_cpus) if plc_cpus else 0.0,
            "plc_avg_mem_mb": statistics.mean(plc_mems) if plc_mems else 0.0,
            "scada_cpu": scada_cpu,
            "scada_mem_mb": scada_mem,
            "dmz_cpu": dmz_cpu,
            "dmz_mem_mb": dmz_mem,
        }


# ═══════════════════════════════════════════════════════════════════
# INFRASTRUCTURE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def cleanup():
    """Remove all itot- containers and networks. Always safe to call."""
    # Stop and remove all containers with our prefix
    out, _ = run_cmd(f'docker ps -a --filter "name={PREFIX}" -q', check=False)
    if out and out.strip():
        container_ids = out.strip().replace("\n", " ")
        run_cmd(f"docker rm -f {container_ids}", check=False, timeout=120)

    # Remove networks
    run_cmd(f"docker network rm {IT_NET_NAME}", check=False)
    run_cmd(f"docker network rm {OT_NET_NAME}", check=False)

    # Small delay for Docker to release resources
    time.sleep(2)


def setup_networks():
    """Create Docker networks for IT and OT segments."""
    run_cmd_strict(
        f"docker network create --subnet={IT_SUBNET} --gateway={IT_GATEWAY} {IT_NET_NAME}"
    )
    run_cmd_strict(
        f"docker network create --subnet={OT_SUBNET} --gateway={OT_GATEWAY} {OT_NET_NAME}"
    )

    # Disable Docker's inter-network isolation so DMZ can route between them.
    # These may fail on older Docker versions — that's OK.
    run_cmd("iptables -I DOCKER-ISOLATION-STAGE-1 1 -j RETURN", check=False)
    run_cmd("iptables -I DOCKER-ISOLATION-STAGE-2 1 -j RETURN", check=False)
    # Older Docker:
    run_cmd("iptables -I DOCKER-ISOLATION 1 -j RETURN", check=False)


def start_dmz():
    """Start DMZ router container on both networks with IP forwarding."""
    run_cmd_strict(
        f"docker run -d --name {PREFIX}dmz --cap-add NET_ADMIN --privileged "
        f"--network {IT_NET_NAME} --ip {DMZ_IT_IP} "
        f"{DMZ_IMAGE} tail -f /dev/null"
    )
    run_cmd_strict(
        f"docker network connect --ip {DMZ_OT_IP} {OT_NET_NAME} {PREFIX}dmz"
    )
    run_cmd_strict(f"docker exec {PREFIX}dmz sysctl -w net.ipv4.ip_forward=1")
    run_cmd_strict(f"docker exec {PREFIX}dmz iptables -P FORWARD ACCEPT")
    run_cmd_strict(f"docker exec {PREFIX}dmz iptables -F FORWARD")


def start_plcs(n):
    """
    Start n PLC containers. Returns list of (plc_name, plc_ip, start_time).
    PLCs start with route + Modbus server in one command.
    """
    plcs = []
    for i in range(1, n + 1):
        ip = plc_ip(i)
        name = f"{PREFIX}plc-{i}"
        t0 = time.time()

        out, err = run_cmd(
            f"docker run -d --name {name} --cap-add NET_ADMIN "
            f"--network {OT_NET_NAME} --ip {ip} "
            f"-e PLC_ID={i} "
            f'{PLC_IMAGE} sh -c "'
            f"ip route add {IT_SUBNET} via {DMZ_OT_IP} && "
            f'exec python /app/plc_simulator.py"',
            check=True
        )
        if out is None:
            raise RuntimeError(f"Failed to start {name}: {err}")

        plcs.append((name, ip, t0))

        if i % 10 == 0 or i == n:
            log_progress(i, n, "PLCs started")

    print(flush=True)  # newline after progress bar
    return plcs


def measure_boot_times(plcs, timeout=120):
    """
    Probe each PLC's Modbus port (502) and measure boot time.
    Returns list of boot times in seconds.
    """
    boot_times = []
    for idx, (name, ip, start_time) in enumerate(plcs):
        elapsed = time.time() - start_time
        boot_time = timeout  # default: timeout

        # If a lot of time already passed (e.g., we started 300 PLCs before this),
        # many will already be booted. Quick-check first.
        remaining = timeout - elapsed
        if remaining <= 0:
            # Already past timeout window — try once
            remaining = 5

        deadline = time.time() + remaining
        while time.time() < deadline:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((ip, 502))
                s.close()
                boot_time = time.time() - start_time
                break
            except (socket.timeout, ConnectionRefusedError, OSError):
                time.sleep(0.3)

        boot_times.append(boot_time)

        if (idx + 1) % 10 == 0 or (idx + 1) == len(plcs):
            log_progress(idx + 1, len(plcs), "PLCs probed")

    print(flush=True)
    return boot_times


def start_scada(plc_ips, poll_interval, run_duration):
    """Start SCADA poller container."""
    hosts_str = ",".join(plc_ips)

    run_cmd_strict(
        f"docker run -d --name {PREFIX}scada --cap-add NET_ADMIN "
        f"--network {IT_NET_NAME} --ip {SCADA_IP} "
        f"-e PLC_HOSTS={hosts_str} "
        f"-e POLL_INTERVAL={poll_interval} "
        f"-e RUN_DURATION={run_duration} "
        f'{SCADA_IMAGE} sh -c "'
        f"ip route add {OT_SUBNET} via {DMZ_IT_IP} && "
        f'exec python -u /app/scada_poller.py"'
    )


def get_scada_logs():
    """Retrieve SCADA container logs."""
    out, _ = run_cmd(f"docker logs {PREFIX}scada", check=False, timeout=30)
    return out or ""


# ═══════════════════════════════════════════════════════════════════
# LOG PARSING
# ═══════════════════════════════════════════════════════════════════

def parse_scada_summaries(logs):
    """
    Parse SCADA summary blocks from docker logs.
    Returns aggregated metrics across all summary intervals.
    """
    results = {
        "avg_rtt": [], "min_rtt": [], "max_rtt": [], "p95_rtt": [],
        "throughput_bps": [], "total_bytes": [], "requests_per_min": [],
        "success_rate": [], "total_requests": [],
    }

    # Split into summary blocks
    blocks = re.findall(
        r"┌─ Summary.*?└──+",
        logs,
        re.DOTALL
    )

    for block in blocks:
        # RTT avg
        m = re.search(r"RTT avg:\s+([\d.]+)", block)
        if m:
            results["avg_rtt"].append(float(m.group(1)))

        # RTT min/max
        m = re.search(r"RTT min/max:\s+([\d.]+)\s*/\s*([\d.]+)", block)
        if m:
            results["min_rtt"].append(float(m.group(1)))
            results["max_rtt"].append(float(m.group(2)))

        # RTT p95
        m = re.search(r"RTT p95:\s+([\d.]+)", block)
        if m:
            results["p95_rtt"].append(float(m.group(1)))

        # Throughput
        m = re.search(r"Throughput:\s+([\d.]+)", block)
        if m:
            results["throughput_bps"].append(float(m.group(1)))

        # Total bytes
        m = re.search(r"Total bytes:\s+(\d+)", block)
        if m:
            results["total_bytes"].append(int(m.group(1)))

        # Requests/min
        m = re.search(r"Requests/min:\s+([\d.]+)", block)
        if m:
            results["requests_per_min"].append(float(m.group(1)))

        # Success rate
        m = re.search(r"Success/Fail:\s+\d+\s*/\s*\d+\s*\(([\d.]+)%\)", block)
        if m:
            results["success_rate"].append(float(m.group(1)))

        # Total requests
        m = re.search(r"Requests:\s+(\d+)", block)
        if m:
            results["total_requests"].append(int(m.group(1)))

    # Average across all summary intervals
    aggregated = {}
    for key, vals in results.items():
        if vals:
            if key == "total_bytes" or key == "total_requests":
                aggregated[key] = sum(vals)
            elif key == "min_rtt":
                aggregated[key] = min(vals)
            elif key == "max_rtt":
                aggregated[key] = max(vals)
            else:
                aggregated[key] = statistics.mean(vals)
        else:
            aggregated[key] = 0.0

    return aggregated


# ═══════════════════════════════════════════════════════════════════
# SINGLE TRIAL
# ═══════════════════════════════════════════════════════════════════

def run_trial(scale, trial_num, poll_interval, duration):
    """
    Run a single trial: setup, run, collect, teardown.
    Returns TrialResult.
    """
    result = TrialResult(scale=scale, trial=trial_num)

    try:
        # ── Setup ──
        log(f"Creating networks...")
        setup_networks()

        log(f"Starting DMZ router...")
        start_dmz()

        log(f"Starting {scale} PLCs...")
        plcs = start_plcs(scale)
        plc_ips = [ip for _, ip, _ in plcs]

        log(f"Measuring boot times...")
        boot_times = measure_boot_times(plcs)
        result.avg_boot_time = statistics.mean(boot_times) if boot_times else 0
        result.max_boot_time = max(boot_times) if boot_times else 0
        log(f"Boot times: avg={result.avg_boot_time:.1f}s, max={result.max_boot_time:.1f}s")

        # ── Start stats collector ──
        stats_collector = StatsCollector(interval=10)
        stats_collector.start()

        # ── Start SCADA ──
        log(f"Starting SCADA poller (duration={duration}s, interval={poll_interval}s)...")
        start_scada(plc_ips, poll_interval, duration)

        # ── Wait for run to complete ──
        log(f"Running experiment for {duration}s...")
        wait_start = time.time()
        while time.time() - wait_start < duration + 30:  # +30s buffer
            # Check if SCADA is still running
            out, _ = run_cmd(
                f'docker ps --filter "name={PREFIX}scada" --filter "status=running" -q',
                check=False
            )
            if not out or not out.strip():
                # SCADA stopped (finished its run)
                break
            time.sleep(10)

        # ── Collect results ──
        stats_collector.stop()

        log(f"Collecting metrics...")

        # Parse SCADA logs
        scada_logs = get_scada_logs()
        metrics = parse_scada_summaries(scada_logs)

        result.avg_rtt = metrics.get("avg_rtt", 0)
        result.min_rtt = metrics.get("min_rtt", 0)
        result.max_rtt = metrics.get("max_rtt", 0)
        result.p95_rtt = metrics.get("p95_rtt", 0)
        result.throughput_bps = metrics.get("throughput_bps", 0)
        result.total_bytes = int(metrics.get("total_bytes", 0))
        result.requests_per_min = metrics.get("requests_per_min", 0)
        result.success_rate = metrics.get("success_rate", 0)
        result.total_requests = int(metrics.get("total_requests", 0))

        # Docker stats
        stavgs = stats_collector.get_averages()
        result.plc_avg_cpu = stavgs["plc_avg_cpu"]
        result.plc_avg_mem_mb = stavgs["plc_avg_mem_mb"]
        result.scada_cpu = stavgs["scada_cpu"]
        result.scada_mem_mb = stavgs["scada_mem_mb"]
        result.dmz_cpu = stavgs["dmz_cpu"]
        result.dmz_mem_mb = stavgs["dmz_mem_mb"]

        # Host memory
        result.host_mem_pct = get_host_memory_pct()

        if result.total_requests == 0 and result.avg_rtt == 0:
            result.success = False
            result.error = "No metrics collected — SCADA may have failed to poll"
            log(f"WARNING: No metrics collected!", "WARN")

    except Exception as e:
        result.success = False
        result.error = str(e)
        log(f"Trial failed: {e}", "ERROR")

    finally:
        # Always clean up
        log(f"Cleaning up...")
        cleanup()

    return result


# ═══════════════════════════════════════════════════════════════════
# RESULTS TABLE
# ═══════════════════════════════════════════════════════════════════

def fmt_mean_std(mean, std):
    """Format mean ± std."""
    if mean == 0 and std == 0:
        return "N/A"
    if std == 0:
        return f"{mean:.1f}"
    return f"{mean:.1f}±{std:.1f}"


def fmt_mean_std_int(mean, std):
    if mean == 0 and std == 0:
        return "N/A"
    if std == 0:
        return f"{int(mean)}"
    return f"{int(mean)}±{int(std)}"


def print_results_table(scale_results: List[ScaleResult], baseline_rtt: float = None):
    """Print the full results table."""
    print("\n")
    print("=" * 120)
    print("  IT/OT SCALABILITY TEST RESULTS")
    print("=" * 120)

    # Header
    print(f"{'PLCs':>6} │ {'Trials':>6} │ {'RTT avg(ms)':>12} │ {'RTT p95(ms)':>12} │ "
          f"{'Throughput':>14} │ {'Success%':>10} │ {'Req/min':>10} │ "
          f"{'Boot(s)':>10} │ {'PLC CPU%':>10} │ {'PLC Mem':>10} │ {'Host Mem%':>10}")
    print("─" * 120)

    for sr in scale_results:
        if sr.n_success == 0:
            print(f"{sr.scale:>6} │ {'FAILED':>6} │ {'—':>12} │ {'—':>12} │ "
                  f"{'—':>14} │ {'—':>10} │ {'—':>10} │ "
                  f"{'—':>10} │ {'—':>10} │ {'—':>10} │ {'—':>10}")
            continue

        rtt_m, rtt_s = sr.mean_std("avg_rtt")
        p95_m, p95_s = sr.mean_std("p95_rtt")
        tp_m, tp_s = sr.mean_std("throughput_bps")
        suc_m, suc_s = sr.mean_std("success_rate")
        rpm_m, rpm_s = sr.mean_std("requests_per_min")
        boot_m, boot_s = sr.mean_std("avg_boot_time")
        pcpu_m, pcpu_s = sr.mean_std("plc_avg_cpu")
        pmem_m, pmem_s = sr.mean_std("plc_avg_mem_mb")
        hmem_m, hmem_s = sr.mean_std("host_mem_pct")

        tp_str = fmt_mean_std(tp_m, tp_s) + " B/s"

        print(f"{sr.scale:>6} │ {sr.n_success:>4}/{len(sr.trials):<1} │ "
              f"{fmt_mean_std(rtt_m, rtt_s):>12} │ {fmt_mean_std(p95_m, p95_s):>12} │ "
              f"{tp_str:>14} │ {fmt_mean_std(suc_m, suc_s):>10} │ "
              f"{fmt_mean_std(rpm_m, rpm_s):>10} │ "
              f"{fmt_mean_std(boot_m, boot_s):>10} │ "
              f"{fmt_mean_std(pcpu_m, pcpu_s):>10} │ "
              f"{fmt_mean_std(pmem_m, pmem_s):>8}MB │ "
              f"{fmt_mean_std(hmem_m, hmem_s):>10}")

    print("─" * 120)

    # Saturation note
    if baseline_rtt and baseline_rtt > 0:
        print(f"\n  Baseline RTT (first scale): {baseline_rtt:.2f} ms")
        print(f"  Saturation thresholds: success <{SAT_SUCCESS_RATE}%, "
              f"RTT >{SAT_RTT_MULTIPLIER}x baseline, "
              f"host mem >{SAT_HOST_MEMORY_PCT}%, "
              f"boot time >{SAT_BOOT_TIME_SEC}s")

    print()


def print_container_detail_table(scale_results: List[ScaleResult]):
    """Print per-container-type resource table."""
    print("=" * 90)
    print("  PER-CONTAINER RESOURCE USAGE")
    print("=" * 90)
    print(f"{'PLCs':>6} │ {'PLC CPU%':>12} │ {'PLC Mem(MB)':>12} │ "
          f"{'SCADA CPU%':>12} │ {'SCADA Mem':>12} │ {'DMZ CPU%':>12} │ {'DMZ Mem':>12}")
    print("─" * 90)

    for sr in scale_results:
        if sr.n_success == 0:
            continue
        pcpu_m, pcpu_s = sr.mean_std("plc_avg_cpu")
        pmem_m, pmem_s = sr.mean_std("plc_avg_mem_mb")
        scpu_m, scpu_s = sr.mean_std("scada_cpu")
        smem_m, smem_s = sr.mean_std("scada_mem_mb")
        dcpu_m, dcpu_s = sr.mean_std("dmz_cpu")
        dmem_m, dmem_s = sr.mean_std("dmz_mem_mb")

        print(f"{sr.scale:>6} │ {fmt_mean_std(pcpu_m, pcpu_s):>12} │ "
              f"{fmt_mean_std(pmem_m, pmem_s):>12} │ "
              f"{fmt_mean_std(scpu_m, scpu_s):>12} │ "
              f"{fmt_mean_std(smem_m, smem_s):>10}MB │ "
              f"{fmt_mean_std(dcpu_m, dcpu_s):>12} │ "
              f"{fmt_mean_std(dmem_m, dmem_s):>10}MB")

    print("─" * 90)
    print()


# ═══════════════════════════════════════════════════════════════════
# SATURATION DETECTION
# ═══════════════════════════════════════════════════════════════════

def check_saturation(scale_result: ScaleResult, baseline_rtt: float):
    """Check if saturation has been reached. Returns (saturated, reason)."""
    if scale_result.n_success == 0:
        return True, "All trials failed"

    suc_m, _ = scale_result.mean_std("success_rate")
    rtt_m, _ = scale_result.mean_std("avg_rtt")
    boot_m, _ = scale_result.mean_std("avg_boot_time")
    hmem_m, _ = scale_result.mean_std("host_mem_pct")

    reasons = []

    if suc_m < SAT_SUCCESS_RATE:
        reasons.append(f"success rate {suc_m:.1f}% < {SAT_SUCCESS_RATE}%")

    if baseline_rtt > 0 and rtt_m > baseline_rtt * SAT_RTT_MULTIPLIER:
        reasons.append(f"RTT {rtt_m:.1f}ms > {SAT_RTT_MULTIPLIER}x baseline ({baseline_rtt:.1f}ms)")

    if hmem_m > SAT_HOST_MEMORY_PCT:
        reasons.append(f"host memory {hmem_m:.1f}% > {SAT_HOST_MEMORY_PCT}%")

    if boot_m > SAT_BOOT_TIME_SEC:
        reasons.append(f"boot time {boot_m:.1f}s > {SAT_BOOT_TIME_SEC}s")

    if reasons:
        return True, "; ".join(reasons)

    return False, ""


# ═══════════════════════════════════════════════════════════════════
# PREFLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════════

def preflight():
    """Verify prerequisites."""
    print("\n  Preflight checks...")

    # Docker
    out, err = run_cmd("docker info", check=False, timeout=10)
    if out is None:
        print("  ✗ Docker is not accessible. Make sure:")
        print("    - Docker is running")
        print("    - Your user is in the 'docker' group (run: sudo usermod -aG docker $USER)")
        return False
    print("  ✓ Docker accessible")

    # Images
    all_ok = True
    for img_name, img in [("PLC", PLC_IMAGE), ("SCADA", SCADA_IMAGE), ("DMZ", DMZ_IMAGE)]:
        out, _ = run_cmd(f"docker image inspect {img}", check=False, timeout=10)
        if out is None:
            print(f"  ✗ Image not found: {img}")
            print(f"    Run: docker pull {img}")
            all_ok = False
        else:
            print(f"  ✓ Image found: {img}")

    if not all_ok:
        return False

    # iptables (needed for disabling Docker isolation)
    out, _ = run_cmd("which iptables", check=False)
    if out is None:
        print("  ⚠ iptables not found — cross-network routing may not work")
        print("    Try: sudo apt install iptables")
    else:
        print("  ✓ iptables available")

    # Memory
    mem_pct = get_host_memory_pct()
    print(f"  ✓ Host memory usage: {mem_pct:.1f}%")
    if mem_pct > 80:
        print("  ⚠ Memory already above 80% — may hit saturation quickly")

    # Clean slate
    print("  Cleaning up any leftover containers from previous runs...")
    cleanup()
    print("  ✓ Clean slate")

    print()
    return True


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="IT/OT Network Scalability Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_scalability_test.py
  python3 run_scalability_test.py --scales 4,8,16,32,64 --trials 2 --duration 120
  python3 run_scalability_test.py --image-prefix myuser/
        """
    )
    parser.add_argument(
        "--scales", type=str,
        default="4,8,16,32,64,100,150,200,250,300,350,400",
        help="Comma-separated PLC counts (default: 4,8,16,...,400)"
    )
    parser.add_argument(
        "--trials", type=int, default=3,
        help="Number of trials per scale point (default: 3)"
    )
    parser.add_argument(
        "--duration", type=int, default=180,
        help="Seconds per trial (default: 180)"
    )
    parser.add_argument(
        "--poll-interval", type=float, default=0.5,
        help="SCADA poll interval in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--image-prefix", type=str, default="",
        help="Docker Hub username prefix (e.g., 'myuser/' -> 'myuser/itot-plc:v0.2')"
    )

    args = parser.parse_args()

    # Apply image prefix
    global PLC_IMAGE, SCADA_IMAGE, DMZ_IMAGE
    if args.image_prefix:
        PLC_IMAGE = f"{args.image_prefix}itot-plc:v0.2"
        SCADA_IMAGE = f"{args.image_prefix}itot-scada:v0.2"
        DMZ_IMAGE = f"{args.image_prefix}itot-dmz:v0.2"

    scales = [int(s.strip()) for s in args.scales.split(",")]
    n_trials = args.trials
    duration = args.duration
    poll_interval = args.poll_interval

    total_time_est = len(scales) * n_trials * (duration + 120)  # +120s overhead per trial
    hours = total_time_est / 3600

    print("\n" + "=" * 60)
    print("  IT/OT NETWORK SCALABILITY TEST")
    print("=" * 60)
    print(f"  Scales:         {scales}")
    print(f"  Trials/scale:   {n_trials}")
    print(f"  Duration/trial: {duration}s")
    print(f"  Poll interval:  {poll_interval}s")
    print(f"  Images:         {PLC_IMAGE}, {SCADA_IMAGE}, {DMZ_IMAGE}")
    print(f"  Est. total time: ~{hours:.1f} hours")
    print("=" * 60)

    # Preflight
    if not preflight():
        print("\n  Preflight failed. Fix the issues above and re-run.")
        sys.exit(1)

    # ── Run experiments ──
    all_results: List[ScaleResult] = []
    baseline_rtt = None
    saturated = False

    for scale_idx, scale in enumerate(scales):
        print(f"\n{'═' * 60}")
        print(f"  SCALE: {scale} PLCs ({scale_idx + 1}/{len(scales)})")
        print(f"{'═' * 60}")

        # Check host memory before starting
        mem_pct = get_host_memory_pct()
        if mem_pct > SAT_HOST_MEMORY_PCT:
            print(f"\n  ⚠ Host memory at {mem_pct:.1f}% — stopping to prevent OOM.")
            saturated = True
            break

        scale_result = ScaleResult(scale=scale)

        for trial in range(1, n_trials + 1):
            print(f"\n  ── Trial {trial}/{n_trials} ({scale} PLCs) ──")

            trial_start = time.time()
            result = run_trial(scale, trial, poll_interval, duration)
            trial_elapsed = time.time() - trial_start

            scale_result.trials.append(result)

            if result.success:
                log(f"Trial {trial} complete in {trial_elapsed:.0f}s — "
                    f"RTT={result.avg_rtt:.1f}ms, "
                    f"Success={result.success_rate:.1f}%, "
                    f"Throughput={result.throughput_bps:.0f} B/s")
            else:
                log(f"Trial {trial} FAILED: {result.error}", "ERROR")

        all_results.append(scale_result)

        # Set baseline RTT from first successful scale
        if baseline_rtt is None and scale_result.n_success > 0:
            baseline_rtt, _ = scale_result.mean_std("avg_rtt")
            if baseline_rtt == 0:
                baseline_rtt = None

        # Print cumulative results
        print_results_table(all_results, baseline_rtt)
        print_container_detail_table(all_results)

        # Check saturation
        if baseline_rtt:
            sat, reason = check_saturation(scale_result, baseline_rtt)
            if sat:
                print(f"  *** SATURATION DETECTED at {scale} PLCs: {reason} ***\n")
                saturated = True
                break

    # ── Final output ──
    print("\n" + "=" * 120)
    print("  FINAL RESULTS")
    print("=" * 120)
    print_results_table(all_results, baseline_rtt)
    print_container_detail_table(all_results)

    if saturated:
        last_good = None
        for sr in reversed(all_results):
            sat, _ = check_saturation(sr, baseline_rtt or 1)
            if not sat and sr.n_success > 0:
                last_good = sr.scale
                break
        if last_good:
            print(f"  Saturation point: between {last_good} and {all_results[-1].scale} PLCs")
        else:
            print(f"  Saturation point: at or below {all_results[0].scale} PLCs")
    else:
        print(f"  No saturation detected up to {scales[-1]} PLCs")

    print(f"\n  Workload: Modbus/TCP read (10 registers), poll interval {poll_interval}s")
    print(f"  Request size: 12 bytes, Response size: 29 bytes per poll")
    print(f"  Trials per scale: {n_trials}, Duration per trial: {duration}s")
    print()

    # Final cleanup
    cleanup()


if __name__ == "__main__":
    main()
