#!/usr/bin/env python3
"""
IT/OT Network Scalability Test — GNS3 Automated Runner

Creates GNS3 topologies via the REST API with Open vSwitch networking,
runs Modbus/TCP polling experiments at increasing PLC counts, and reports
performance metrics with mean ± std. Stops at saturation.

Traffic flows through real OVS L2 forwarding — not Docker bridge networking.

Prerequisites:
  - GNS3 running with API accessible
  - Docker images pulled: itot-plc:v0.2, itot-scada:v0.2, itot-dmz:v0.2
  - Open vSwitch template available in GNS3
  - Python 3.6+ (standard library only, no pip installs)

Usage:
  python3 run_gns3_scalability_test.py
  python3 run_gns3_scalability_test.py --scales 4,8,16 --trials 1 --duration 60
  python3 run_gns3_scalability_test.py --gns3-port 3080 --switch-template "Open vSwitch"
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
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION DEFAULTS
# ═══════════════════════════════════════════════════════════════════

GNS3_HOST = "localhost"
GNS3_PORT = 80
SWITCH_TEMPLATE_NAME = "Open-vSwitch"
SWITCH_PORTS = 16          # total ports on each switch (0-15)
SWITCH_FIRST_DATA_PORT = 1  # port 0 is management, skip it
SWITCH_USABLE_PORTS = SWITCH_PORTS - SWITCH_FIRST_DATA_PORT  # 15

PLC_IMAGE = "itot-plc:v0.2"
SCADA_IMAGE = "itot-scada:v0.2"
DMZ_IMAGE = "itot-dmz:v0.2"

IT_SUBNET = "192.168.1"
OT_SUBNET_PREFIX = "10.0"
DMZ_IT_IP = f"{IT_SUBNET}.1"
DMZ_OT_IP = f"{OT_SUBNET_PREFIX}.0.1"
SCADA_IP = f"{IT_SUBNET}.10"

# Saturation thresholds
SAT_SUCCESS_RATE = 90.0
SAT_RTT_MULTIPLIER = 10.0
SAT_HOST_MEMORY_PCT = 85.0
SAT_BOOT_TIME_SEC = 120.0

# Layout
NODE_SPACING_X = 120
NODE_SPACING_Y = 80
PLC_GRID_COLS = 20


# ═══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TrialResult:
    scale: int
    trial: int
    avg_rtt: float = 0.0
    min_rtt: float = 0.0
    max_rtt: float = 0.0
    p95_rtt: float = 0.0
    throughput_bps: float = 0.0
    per_plc_throughput: float = 0.0
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
    total_container_cpu: float = 0.0
    total_container_mem_mb: float = 0.0
    host_cpu_pct: float = 0.0
    host_mem_pct: float = 0.0
    success: bool = True
    error: str = ""


@dataclass
class ScaleResult:
    scale: int
    trials: List[TrialResult] = field(default_factory=list)

    def _ok(self):
        return [t for t in self.trials if t.success]

    @property
    def n_success(self):
        return len(self._ok())

    def mean_std(self, attr):
        vals = [getattr(t, attr) for t in self._ok()]
        if not vals:
            return 0.0, 0.0
        m = statistics.mean(vals)
        s = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return m, s


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def run_cmd(cmd, check=True, timeout=300):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            return None, r.stderr.strip()
        return r.stdout.strip(), ""
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def plc_ip(i):
    """PLC i (1-indexed) -> IP. PLC 1 = 10.0.1.1, PLC 255 = 10.0.2.1, etc."""
    z = i - 1
    return f"10.0.{z // 254 + 1}.{z % 254 + 1}"


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {level}: {msg}", flush=True)


def log_progress(current, total, label=""):
    pct = current / total * 100 if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {current}/{total} {label} ({pct:.0f}%)", end="", flush=True)
    if current == total:
        print(flush=True)


# ═══════════════════════════════════════════════════════════════════
# HOST METRICS
# ═══════════════════════════════════════════════════════════════════

def get_host_memory_pct():
    try:
        out, _ = run_cmd("free -m", check=False, timeout=5)
        if out:
            for line in out.splitlines():
                if line.startswith("Mem:"):
                    p = line.split()
                    return (int(p[1]) - int(p[6])) / int(p[1]) * 100
    except Exception:
        pass
    return 0.0


def get_host_cpu_pct():
    """Sample host CPU over 1 second using /proc/stat."""
    try:
        def read_cpu():
            with open("/proc/stat") as f:
                line = f.readline()
            parts = line.split()
            idle = int(parts[4])
            total = sum(int(x) for x in parts[1:])
            return idle, total

        idle1, total1 = read_cpu()
        time.sleep(1)
        idle2, total2 = read_cpu()

        idle_delta = idle2 - idle1
        total_delta = total2 - total1
        if total_delta == 0:
            return 0.0
        return (1.0 - idle_delta / total_delta) * 100
    except Exception:
        return 0.0


# ═══════════════════════════════════════════════════════════════════
# GNS3 API CLIENT
# ═══════════════════════════════════════════════════════════════════

class GNS3API:
    def __init__(self, host, port):
        self.base = f"http://{host}:{port}/v2"

    def _request(self, method, path, data=None, timeout=60):
        url = f"{self.base}{path}"
        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            raise RuntimeError(f"GNS3 API {method} {path} -> {e.code}: {body_text}")
        except URLError as e:
            raise RuntimeError(f"GNS3 API connection failed: {e}")

    def get(self, path, timeout=30):
        return self._request("GET", path, timeout=timeout)

    def post(self, path, data=None, timeout=60):
        return self._request("POST", path, data=data, timeout=timeout)

    def delete(self, path, timeout=60):
        return self._request("DELETE", path, timeout=timeout)

    # ── Templates ──

    def list_templates(self):
        return self.get("/templates")

    def find_template(self, name_contains):
        """Find a template whose name contains the given string (case-insensitive)."""
        templates = self.list_templates()
        for t in templates:
            if name_contains.lower() in t.get("name", "").lower():
                return t
        return None

    def create_docker_template(self, name, image, adapters=1, start_cmd="",
                                env="", cap_add=None):
        data = {
            "name": name,
            "template_type": "docker",
            "compute_id": "local",
            "image": image,
            "adapters": adapters,
            "start_command": start_cmd,
            "console_type": "telnet",
            "environment": env,
        }
        if cap_add:
            data["extra_hosts"] = ""  # required field
        return self.post("/templates", data)

    # ── Projects ──

    def create_project(self, name):
        return self.post("/projects", {"name": name})

    def delete_project(self, project_id):
        return self.delete(f"/projects/{project_id}")

    def close_project(self, project_id):
        return self.post(f"/projects/{project_id}/close")

    def open_project(self, project_id):
        return self.post(f"/projects/{project_id}/open")

    # ── Nodes ──

    def create_node(self, project_id, template_id, name, x=0, y=0,
                     compute_id="local", properties=None):
        """Create a node from a template. Works with GNS3 v2.2.x."""
        data = {
            "x": x,
            "y": y,
            "name": name,
            "compute_id": compute_id,
        }
        # v2.2.x uses POST /projects/{id}/templates/{template_id}
        return self.post(f"/projects/{project_id}/templates/{template_id}", data, timeout=120)

    def get_node(self, project_id, node_id):
        return self.get(f"/projects/{project_id}/nodes/{node_id}")

    def get_nodes(self, project_id):
        return self.get(f"/projects/{project_id}/nodes")

    def start_node(self, project_id, node_id):
        return self.post(f"/projects/{project_id}/nodes/{node_id}/start", timeout=120)

    def stop_node(self, project_id, node_id):
        return self.post(f"/projects/{project_id}/nodes/{node_id}/stop", timeout=60)

    def start_all_nodes(self, project_id):
        nodes = self.get_nodes(project_id)
        for n in nodes:
            if n.get("status") != "started":
                self.start_node(project_id, n["node_id"])

    # ── Links ──

    def create_link(self, project_id, node1_id, adapter1, port1,
                     node2_id, adapter2, port2):
        data = {
            "nodes": [
                {"node_id": node1_id, "adapter_number": adapter1, "port_number": port1},
                {"node_id": node2_id, "adapter_number": adapter2, "port_number": port2},
            ]
        }
        return self.post(f"/projects/{project_id}/links", data)


# ═══════════════════════════════════════════════════════════════════
# TOPOLOGY PLANNER
# ═══════════════════════════════════════════════════════════════════

class TopologyPlanner:
    """
    Plans switch tree, node placement, and wiring for N PLCs.

    Each OVS has 16 ports. Port 0 = management (unused). Ports 1-15 = 15 data ports.
    Each switch reserves 1 data port for uplink (DMZ or parent switch).
    So each switch can connect 14 children (PLCs or sub-switches).

    Switch tree:
      - N ≤ 14:   1 OT switch (port 1 = DMZ, ports 2-15 = PLCs)
      - N ≤ 196:  1 root + ceil(N/14) branches (14 branches × 14 PLCs)
      - N > 196:  1 root + spines + leaves (14 × 14 × 14 = 2744 max)
    """

    def __init__(self, n_plcs, total_ports=16, first_data_port=1):
        self.n = n_plcs
        self.data_ports = total_ports - first_data_port  # 15 data ports (1-15)
        self.child_ports = self.data_ports - 1  # 14 (one data port used for uplink/DMZ)

    def plan_switches(self):
        """Returns list of switch dicts with roles and PLC assignments."""
        n = self.n
        cp = self.child_ports  # 14

        if n <= cp:
            return [{"name": "OT-Switch", "role": "root+leaf", "children": [],
                      "plc_start": 1, "plc_end": n}]

        if n <= cp * cp:  # ≤ 196: 2-level tree
            n_branches = math.ceil(n / cp)
            switches = [{"name": "OT-Root", "role": "root", "children": [],
                          "plc_start": 0, "plc_end": 0}]
            assigned = 0
            for i in range(n_branches):
                count = min(cp, n - assigned)
                sw = {"name": f"OT-Branch-{i+1}", "role": "branch",
                      "parent": "OT-Root", "children": [],
                      "plc_start": assigned + 1, "plc_end": assigned + count}
                switches.append(sw)
                switches[0]["children"].append(sw["name"])
                assigned += count
            return switches

        # 3-level tree: root → spines → leaves
        plcs_per_spine = cp * cp  # 196
        max_3level = cp * cp * cp  # 2744

        if n > max_3level:
            raise ValueError(f"Cannot support {n} PLCs (max {max_3level} with 3-level tree)")

        n_spines = math.ceil(n / plcs_per_spine)
        switches = [{"name": "OT-Root", "role": "root", "children": [],
                      "plc_start": 0, "plc_end": 0}]
        assigned = 0

        for si in range(n_spines):
            spine = {"name": f"OT-Spine-{si+1}", "role": "spine",
                     "parent": "OT-Root", "children": [],
                     "plc_start": 0, "plc_end": 0}
            switches.append(spine)
            switches[0]["children"].append(spine["name"])

            remaining = min(plcs_per_spine, n - assigned)
            n_leaves = math.ceil(remaining / cp)

            for li in range(n_leaves):
                count = min(cp, n - assigned)
                leaf = {"name": f"OT-Leaf-{si+1}-{li+1}", "role": "leaf",
                        "parent": spine["name"], "children": [],
                        "plc_start": assigned + 1, "plc_end": assigned + count}
                switches.append(leaf)
                spine["children"].append(leaf["name"])
                assigned += count

        return switches

    def plan_layout(self, switches):
        """Compute (x, y) positions for all nodes."""
        positions = {}

        # Core infrastructure (horizontal at top)
        positions["SCADA"] = (0, 0)
        positions["IT-Switch"] = (NODE_SPACING_X * 2, 0)
        positions["DMZ"] = (NODE_SPACING_X * 4, 0)

        # Switches — arranged in rows below core
        sw_x_start = NODE_SPACING_X * 6
        switch_names = [s["name"] for s in switches]

        # Root at fixed position
        if switch_names:
            positions[switch_names[0]] = (sw_x_start, 0)

        # Non-root switches arranged vertically
        non_root = switch_names[1:] if len(switch_names) > 1 else []
        for i, name in enumerate(non_root):
            y_offset = (i - len(non_root) // 2) * NODE_SPACING_Y
            positions[name] = (sw_x_start + NODE_SPACING_X * 2, y_offset)

        # PLCs in a grid
        plc_x_start = sw_x_start + NODE_SPACING_X * 4
        plc_y_start = -((self.n // PLC_GRID_COLS) * NODE_SPACING_Y) // 2

        for i in range(1, self.n + 1):
            col = (i - 1) % PLC_GRID_COLS
            row = (i - 1) // PLC_GRID_COLS
            x = plc_x_start + col * (NODE_SPACING_X // 2)
            y = plc_y_start + row * (NODE_SPACING_Y // 2)
            positions[f"PLC-{i}"] = (x, y)

        return positions


# ═══════════════════════════════════════════════════════════════════
# DOCKER STATS COLLECTOR
# ═══════════════════════════════════════════════════════════════════

class StatsCollector:
    def __init__(self, container_ids: Dict[str, str], interval=10):
        """container_ids: {role_name: docker_container_id}"""
        self.container_ids = container_ids
        self.interval = interval
        self.running = False
        self.thread = None
        self.samples: Dict[str, List[Dict]] = {}
        self.host_cpu_samples: List[float] = []

    def start(self):
        self.running = True
        self.samples = {}
        self.host_cpu_samples = []
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=20)

    def _loop(self):
        while self.running:
            # Docker stats
            try:
                out, _ = run_cmd(
                    'docker stats --no-stream --format \'{"name":"{{.Name}}","cpu":"{{.CPUPerc}}","mem":"{{.MemUsage}}"}\'',
                    check=False, timeout=30
                )
                if out:
                    for line in out.strip().splitlines():
                        try:
                            d = json.loads(line)
                            name = d["name"]
                            cpu = float(d["cpu"].replace("%", ""))
                            mem_mb = self._parse_mem(d["mem"].split("/")[0].strip())
                            if name not in self.samples:
                                self.samples[name] = []
                            self.samples[name].append({"cpu": cpu, "mem_mb": mem_mb})
                        except (json.JSONDecodeError, ValueError, KeyError):
                            continue
            except Exception:
                pass

            # Host CPU
            try:
                cpu = get_host_cpu_pct()
                self.host_cpu_samples.append(cpu)
            except Exception:
                pass

            time.sleep(self.interval)

    @staticmethod
    def _parse_mem(s):
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

    def get_results(self, container_map: Dict[str, str]):
        """
        container_map: {role: container_name} e.g. {"PLC-1": "abcdef...", "SCADA": "..."}
        Returns dict with per-category and aggregate stats.
        """
        plc_cpus, plc_mems = [], []
        scada_cpu, scada_mem = 0.0, 0.0
        dmz_cpu, dmz_mem = 0.0, 0.0
        all_cpus, all_mems = [], []

        for container_name, samples in self.samples.items():
            if not samples:
                continue
            avg_cpu = statistics.mean(s["cpu"] for s in samples)
            avg_mem = statistics.mean(s["mem_mb"] for s in samples)
            all_cpus.append(avg_cpu)
            all_mems.append(avg_mem)

            # Identify role from container name
            role = None
            for r, cname in container_map.items():
                if cname and cname in container_name:
                    role = r
                    break

            if role and "PLC" in role.upper():
                plc_cpus.append(avg_cpu)
                plc_mems.append(avg_mem)
            elif role and "SCADA" in role.upper():
                scada_cpu = avg_cpu
                scada_mem = avg_mem
            elif role and "DMZ" in role.upper():
                dmz_cpu = avg_cpu
                dmz_mem = avg_mem

        host_cpu = statistics.mean(self.host_cpu_samples) if self.host_cpu_samples else 0.0

        return {
            "plc_avg_cpu": statistics.mean(plc_cpus) if plc_cpus else 0.0,
            "plc_avg_mem_mb": statistics.mean(plc_mems) if plc_mems else 0.0,
            "scada_cpu": scada_cpu,
            "scada_mem_mb": scada_mem,
            "dmz_cpu": dmz_cpu,
            "dmz_mem_mb": dmz_mem,
            "total_container_cpu": sum(all_cpus),
            "total_container_mem_mb": sum(all_mems),
            "host_cpu_pct": host_cpu,
        }


# ═══════════════════════════════════════════════════════════════════
# SCADA LOG PARSER
# ═══════════════════════════════════════════════════════════════════

def parse_scada_summaries(logs):
    results = {
        "avg_rtt": [], "min_rtt": [], "max_rtt": [], "p95_rtt": [],
        "throughput_bps": [], "total_bytes": [], "requests_per_min": [],
        "success_rate": [], "total_requests": [],
    }

    blocks = re.findall(r"┌─ Summary.*?└──+", logs, re.DOTALL)

    for block in blocks:
        for key, pattern in [
            ("avg_rtt", r"RTT avg:\s+([\d.]+)"),
            ("p95_rtt", r"RTT p95:\s+([\d.]+)"),
            ("throughput_bps", r"Throughput:\s+([\d.]+)"),
            ("requests_per_min", r"Requests/min:\s+([\d.]+)"),
        ]:
            m = re.search(pattern, block)
            if m:
                results[key].append(float(m.group(1)))

        m = re.search(r"RTT min/max:\s+([\d.]+)\s*/\s*([\d.]+)", block)
        if m:
            results["min_rtt"].append(float(m.group(1)))
            results["max_rtt"].append(float(m.group(2)))

        m = re.search(r"Success/Fail:\s+\d+\s*/\s*\d+\s*\(([\d.]+)%\)", block)
        if m:
            results["success_rate"].append(float(m.group(1)))

        m = re.search(r"Total bytes:\s+(\d+)", block)
        if m:
            results["total_bytes"].append(int(m.group(1)))

        m = re.search(r"Requests:\s+(\d+)", block)
        if m:
            results["total_requests"].append(int(m.group(1)))

    agg = {}
    for key, vals in results.items():
        if not vals:
            agg[key] = 0.0
        elif key in ("total_bytes", "total_requests"):
            agg[key] = sum(vals)
        elif key == "min_rtt":
            agg[key] = min(vals)
        elif key == "max_rtt":
            agg[key] = max(vals)
        else:
            agg[key] = statistics.mean(vals)

    return agg


# ═══════════════════════════════════════════════════════════════════
# TOPOLOGY BUILDER
# ═══════════════════════════════════════════════════════════════════

def ensure_templates(api, switch_template_name):
    """Find or create all required templates. Returns template IDs."""
    templates = {}

    # Find switch template
    sw = api.find_template(switch_template_name)
    if not sw:
        print(f"\n  ✗ Switch template '{switch_template_name}' not found in GNS3.")
        print(f"    Available templates:")
        for t in api.list_templates():
            print(f"      - {t['name']} ({t.get('template_type', '?')})")
        print(f"\n    Use --switch-template to specify the correct name.")
        return None
    templates["switch"] = sw["template_id"]
    print(f"  ✓ Switch template: {sw['name']} ({sw['template_id'][:8]}...)")

    # Docker templates for PLC, SCADA, DMZ
    for role, image, adapters, env in [
        ("plc", PLC_IMAGE, 1, "PLC_ID=1"),
        ("scada", SCADA_IMAGE, 1, ""),
        ("dmz", DMZ_IMAGE, 2, ""),
    ]:
        tname = f"itot-{role}"
        existing = api.find_template(tname)
        if existing:
            templates[role] = existing["template_id"]
            print(f"  ✓ Template exists: {tname} ({existing['template_id'][:8]}...)")
        else:
            try:
                t = api.create_docker_template(tname, image, adapters, env=env)
                templates[role] = t["template_id"]
                print(f"  ✓ Template created: {tname}")
            except Exception as e:
                print(f"  ✗ Failed to create template {tname}: {e}")
                return None

    return templates


def build_topology(api, project_id, templates, n_plcs, switch_template_name):
    """
    Create all nodes and links for the topology.
    Returns {role_name: {node_id, container_id (empty until started), ...}}
    """
    planner = TopologyPlanner(n_plcs)
    switches = planner.plan_switches()
    positions = planner.plan_layout(switches)

    nodes = {}  # role -> {node_id, ...}
    switch_nodes = {}  # switch_name -> node_id

    # ── Create infrastructure nodes ──
    log("Creating SCADA node...")
    x, y = positions["SCADA"]
    n = api.create_node(project_id, templates["scada"], "SCADA", x, y)
    nodes["SCADA"] = {"node_id": n["node_id"], "name": n["name"]}

    log("Creating IT-Switch...")
    x, y = positions["IT-Switch"]
    n = api.create_node(project_id, templates["switch"], "IT-Switch", x, y)
    nodes["IT-Switch"] = {"node_id": n["node_id"], "name": n["name"]}
    switch_nodes["IT-Switch"] = n["node_id"]

    log("Creating DMZ router...")
    x, y = positions["DMZ"]
    n = api.create_node(project_id, templates["dmz"], "DMZ", x, y)
    nodes["DMZ"] = {"node_id": n["node_id"], "name": n["name"]}

    # ── Create OT switches ──
    for sw in switches:
        log(f"Creating {sw['name']}...")
        x, y = positions.get(sw["name"], (800, 0))
        n = api.create_node(project_id, templates["switch"], sw["name"], x, y)
        switch_nodes[sw["name"]] = n["node_id"]
        nodes[sw["name"]] = {"node_id": n["node_id"], "name": n["name"]}

    # ── Create PLC nodes ──
    for i in range(1, n_plcs + 1):
        name = f"PLC-{i}"
        x, y = positions[name]
        n = api.create_node(project_id, templates["plc"], name, x, y)
        nodes[name] = {"node_id": n["node_id"], "name": n["name"]}
        if i % 20 == 0 or i == n_plcs:
            log_progress(i, n_plcs, "PLCs created")

    # ── Create links ──
    # GNS3 port addressing:
    #   Docker containers: eth0 = (adapter=0, port=0), eth1 = (adapter=1, port=0)
    #   Open vSwitch:      port N = (adapter=N, port=0)
    # So switch port references use (adapter=PORT_NUM, port=0)

    log("Wiring IT side...")
    # SCADA eth0 -> IT-Switch port 1
    api.create_link(project_id,
                    nodes["SCADA"]["node_id"], 0, 0,
                    switch_nodes["IT-Switch"], SWITCH_FIRST_DATA_PORT, 0)
    # IT-Switch port 2 -> DMZ eth0 (IT side)
    api.create_link(project_id,
                    switch_nodes["IT-Switch"], SWITCH_FIRST_DATA_PORT + 1, 0,
                    nodes["DMZ"]["node_id"], 0, 0)

    log("Wiring OT side...")
    root_sw = switches[0]
    root_id = switch_nodes[root_sw["name"]]

    # DMZ eth1 (OT side) -> Root OT switch port 1
    api.create_link(project_id,
                    nodes["DMZ"]["node_id"], 1, 0,
                    root_id, SWITCH_FIRST_DATA_PORT, 0)

    if root_sw["role"] == "root+leaf":
        # Single switch: port 1 = DMZ (already wired), ports 2..n+1 = PLCs
        for i in range(1, n_plcs + 1):
            sw_adapter = SWITCH_FIRST_DATA_PORT + i  # adapters 2, 3, 4, ...
            api.create_link(project_id,
                            root_id, sw_adapter, 0,
                            nodes[f"PLC-{i}"]["node_id"], 0, 0)
            if i % 20 == 0 or i == n_plcs:
                log_progress(i, n_plcs, "PLCs wired")
    else:
        # Multi-level: track next available adapter per switch
        next_adapter = {}  # switch_name -> next available adapter number
        # Root: adapter 1 used for DMZ, so next is adapter 2
        next_adapter[switches[0]["name"]] = SWITCH_FIRST_DATA_PORT + 1

        plcs_wired = 0
        for sw in switches[1:]:  # skip root
            parent_name = sw.get("parent")
            if parent_name:
                parent_id = switch_nodes[parent_name]
                child_id = switch_nodes[sw["name"]]

                # Get next adapter on parent switch
                p_adapter = next_adapter.get(parent_name, SWITCH_FIRST_DATA_PORT + 1)
                next_adapter[parent_name] = p_adapter + 1

                # Parent switch adapter -> Child switch uplink (adapter 1 = first data port)
                api.create_link(project_id,
                                parent_id, p_adapter, 0,
                                child_id, SWITCH_FIRST_DATA_PORT, 0)

                # Initialize child's adapter tracking (after uplink)
                next_adapter[sw["name"]] = SWITCH_FIRST_DATA_PORT + 1

            # Wire PLCs to this switch
            if sw.get("plc_start", 0) > 0:
                for plc_i in range(sw["plc_start"], sw["plc_end"] + 1):
                    sw_adapter = next_adapter.get(sw["name"], SWITCH_FIRST_DATA_PORT + 1)
                    next_adapter[sw["name"]] = sw_adapter + 1

                    api.create_link(project_id,
                                    switch_nodes[sw["name"]], sw_adapter, 0,
                                    nodes[f"PLC-{plc_i}"]["node_id"], 0, 0)
                    plcs_wired += 1

                    if plcs_wired % 20 == 0 or plcs_wired == n_plcs:
                        log_progress(plcs_wired, n_plcs, "PLCs wired")

    return nodes, switches


# ═══════════════════════════════════════════════════════════════════
# NODE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

def get_container_ids(api, project_id, nodes):
    """After nodes are started, query GNS3 for Docker container IDs."""
    container_map = {}
    all_nodes = api.get_nodes(project_id)

    for n in all_nodes:
        node_id = n["node_id"]
        name = n["name"]
        # Docker nodes have properties.container_id
        cid = n.get("properties", {}).get("container_id", "")
        if not cid:
            # Try alternate location
            cid = n.get("container_id", "")
        if cid:
            container_map[name] = cid

    return container_map


def docker_exec(container_id, cmd, timeout=30, detach=False):
    """Run a command inside a Docker container."""
    d_flag = "-d " if detach else ""
    full_cmd = f'docker exec {d_flag}{container_id} sh -c "{cmd}"'
    return run_cmd(full_cmd, check=False, timeout=timeout)


def configure_nodes(container_map, n_plcs, poll_interval, duration):
    """Configure IP addresses and start scripts on all nodes."""

    # ── DMZ Router ──
    dmz_cid = container_map.get("DMZ", "")
    if dmz_cid:
        log("Configuring DMZ router...")
        cmds = [
            f"ip addr add {DMZ_IT_IP}/24 dev eth0 2>/dev/null; true",
            f"ip addr add {DMZ_OT_IP}/16 dev eth1 2>/dev/null; true",
            "ip link set eth0 up",
            "ip link set eth1 up",
            "sysctl -w net.ipv4.ip_forward=1",
            "iptables -P FORWARD ACCEPT",
            "iptables -F FORWARD",
        ]
        for cmd in cmds:
            docker_exec(dmz_cid, cmd)

    # ── SCADA ──
    scada_cid = container_map.get("SCADA", "")
    if scada_cid:
        log("Configuring SCADA...")
        docker_exec(scada_cid, f"ip addr add {SCADA_IP}/24 dev eth0 2>/dev/null; true")
        docker_exec(scada_cid, f"ip route add 10.0.0.0/16 via {DMZ_IT_IP} 2>/dev/null; true")

    # ── PLCs ──
    log(f"Configuring {n_plcs} PLCs...")
    boot_start_times = {}
    for i in range(1, n_plcs + 1):
        name = f"PLC-{i}"
        cid = container_map.get(name, "")
        if not cid:
            continue

        ip = plc_ip(i)
        docker_exec(cid, f"ip addr add {ip}/16 dev eth0 2>/dev/null; true")
        docker_exec(cid, f"ip route add 192.168.1.0/24 via {DMZ_OT_IP} 2>/dev/null; true")

        # Start PLC script in background (detach mode)
        docker_exec(cid, f"PLC_ID={i} python /app/plc_simulator.py", detach=True)
        boot_start_times[name] = time.time()

        if i % 20 == 0 or i == n_plcs:
            log_progress(i, n_plcs, "PLCs configured")

    return boot_start_times


def measure_boot_times(container_map, n_plcs, boot_start_times, timeout=120):
    """
    Probe each PLC's Modbus port from inside the PLC container itself.
    Uses boot_start_times to compute actual time from script start to ready.
    """
    boot_times = []
    probe_cmd = "python -c \"import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', 502)); s.close(); print('OK')\""

    for i in range(1, n_plcs + 1):
        name = f"PLC-{i}"
        cid = container_map.get(name, "")
        start = boot_start_times.get(name, time.time())

        if not cid:
            boot_times.append(timeout)
            continue

        deadline = start + timeout
        booted = False

        while time.time() < deadline:
            out, _ = run_cmd(
                f'docker exec {cid} sh -c \'{probe_cmd}\' 2>/dev/null',
                check=False, timeout=5
            )
            if out and "OK" in out:
                boot_times.append(time.time() - start)
                booted = True
                break
            time.sleep(0.5)

        if not booted:
            boot_times.append(timeout)

        if i % 20 == 0 or i == n_plcs:
            log_progress(i, n_plcs, "PLCs probed")

    return boot_times


def start_scada_poller(container_map, n_plcs, poll_interval, duration):
    """Start the SCADA polling script."""
    scada_cid = container_map.get("SCADA", "")
    if not scada_cid:
        return

    plc_hosts = ",".join(plc_ip(i) for i in range(1, n_plcs + 1))

    cmd = (
        f"PLC_HOSTS={plc_hosts} "
        f"POLL_INTERVAL={poll_interval} "
        f"RUN_DURATION={duration} "
        f"python -u /app/scada_poller.py > /tmp/results.log 2>&1"
    )
    docker_exec(scada_cid, cmd, detach=True)


def get_scada_results(container_map):
    """Read SCADA results from inside the container."""
    scada_cid = container_map.get("SCADA", "")
    if not scada_cid:
        return ""
    out, _ = run_cmd(f"docker exec {scada_cid} cat /tmp/results.log",
                     check=False, timeout=30)
    return out or ""


# ═══════════════════════════════════════════════════════════════════
# SINGLE TRIAL
# ═══════════════════════════════════════════════════════════════════

def run_trial(api, templates, n_plcs, trial_num, poll_interval, duration,
              switch_template_name):
    """Run one trial: create topology, experiment, collect, teardown."""
    result = TrialResult(scale=n_plcs, trial=trial_num)
    project_id = None

    try:
        # ── Create project ──
        project_name = f"itot-s{n_plcs}-t{trial_num}-{int(time.time())}"
        log(f"Creating GNS3 project: {project_name}")
        project = api.create_project(project_name)
        project_id = project["project_id"]

        # ── Build topology ──
        log(f"Building topology ({n_plcs} PLCs)...")
        nodes, switches = build_topology(api, project_id, templates, n_plcs,
                                          switch_template_name)

        # ── Start all nodes ──
        log("Starting all nodes (this may take a while)...")
        api.start_all_nodes(project_id)
        log("Waiting for nodes to initialize...")
        time.sleep(10)  # give Docker containers time to start

        # ── Get container IDs ──
        log("Discovering container IDs...")
        container_map = get_container_ids(api, project_id, nodes)
        log(f"Found {len(container_map)} container IDs")

        if "DMZ" not in container_map or "SCADA" not in container_map:
            raise RuntimeError("Could not find DMZ or SCADA container IDs. "
                               "Nodes may not have started properly.")

        # ── Configure networking ──
        boot_start_times = configure_nodes(container_map, n_plcs, poll_interval, duration)

        # ── Measure boot times ──
        log("Measuring PLC boot times...")
        boot_times = measure_boot_times(container_map, n_plcs, boot_start_times)
        result.avg_boot_time = statistics.mean(boot_times) if boot_times else 0
        result.max_boot_time = max(boot_times) if boot_times else 0
        log(f"Boot: avg={result.avg_boot_time:.1f}s, max={result.max_boot_time:.1f}s")

        # ── Start stats collector ──
        stats = StatsCollector(container_map, interval=10)
        stats.start()

        # ── Start SCADA ──
        log(f"Starting SCADA poller ({duration}s, {poll_interval}s interval)...")
        start_scada_poller(container_map, n_plcs, poll_interval, duration)

        # ── Wait ──
        log(f"Running experiment for {duration}s...")
        time.sleep(duration + 15)  # +15s buffer

        # ── Collect ──
        stats.stop()
        log("Collecting metrics...")

        scada_logs = get_scada_results(container_map)
        metrics = parse_scada_summaries(scada_logs)

        result.avg_rtt = metrics.get("avg_rtt", 0)
        result.min_rtt = metrics.get("min_rtt", 0)
        result.max_rtt = metrics.get("max_rtt", 0)
        result.p95_rtt = metrics.get("p95_rtt", 0)
        result.throughput_bps = metrics.get("throughput_bps", 0)
        result.per_plc_throughput = result.throughput_bps / n_plcs if n_plcs > 0 else 0
        result.total_bytes = int(metrics.get("total_bytes", 0))
        result.requests_per_min = metrics.get("requests_per_min", 0)
        result.success_rate = metrics.get("success_rate", 0)
        result.total_requests = int(metrics.get("total_requests", 0))

        stat_results = stats.get_results(container_map)
        result.plc_avg_cpu = stat_results["plc_avg_cpu"]
        result.plc_avg_mem_mb = stat_results["plc_avg_mem_mb"]
        result.scada_cpu = stat_results["scada_cpu"]
        result.scada_mem_mb = stat_results["scada_mem_mb"]
        result.dmz_cpu = stat_results["dmz_cpu"]
        result.dmz_mem_mb = stat_results["dmz_mem_mb"]
        result.total_container_cpu = stat_results["total_container_cpu"]
        result.total_container_mem_mb = stat_results["total_container_mem_mb"]
        result.host_cpu_pct = stat_results["host_cpu_pct"]
        result.host_mem_pct = get_host_memory_pct()

        if result.total_requests == 0 and result.avg_rtt == 0:
            result.success = False
            result.error = "No metrics collected — SCADA may have failed to connect"
            log("WARNING: No metrics collected!", "WARN")

    except Exception as e:
        result.success = False
        result.error = str(e)
        log(f"Trial failed: {e}", "ERROR")

    finally:
        if project_id:
            log("Deleting GNS3 project (cleanup)...")
            try:
                api.close_project(project_id)
                time.sleep(2)
                api.delete_project(project_id)
            except Exception as e:
                log(f"Cleanup warning: {e}", "WARN")
        time.sleep(5)

    return result


# ═══════════════════════════════════════════════════════════════════
# RESULTS TABLE
# ═══════════════════════════════════════════════════════════════════

def fmt(mean, std):
    if mean == 0 and std == 0:
        return "N/A"
    return f"{mean:.1f}±{std:.1f}" if std > 0.05 else f"{mean:.1f}"


def print_results_table(results: List[ScaleResult], baseline_rtt=None):
    print("\n" + "=" * 140)
    print("  IT/OT SCALABILITY TEST RESULTS (GNS3 + Open vSwitch)")
    print("=" * 140)

    hdr = (f"{'PLCs':>6} │ {'Trials':>6} │ {'RTT avg':>10} │ {'RTT p95':>10} │ "
           f"{'Throughput':>14} │ {'Per-PLC':>10} │ {'Success%':>9} │ "
           f"{'Req/min':>10} │ {'Boot(s)':>10} │ {'HostCPU%':>9} │ {'HostMem%':>9}")
    print(hdr)
    print("─" * 140)

    for sr in results:
        if sr.n_success == 0:
            print(f"{sr.scale:>6} │ {'FAIL':>6} │ " + "─" * 120)
            continue

        print(f"{sr.scale:>6} │ {sr.n_success:>4}/{len(sr.trials):<1} │ "
              f"{fmt(*sr.mean_std('avg_rtt')):>8}ms │ "
              f"{fmt(*sr.mean_std('p95_rtt')):>8}ms │ "
              f"{fmt(*sr.mean_std('throughput_bps')):>11}B/s │ "
              f"{fmt(*sr.mean_std('per_plc_throughput')):>8}B/s │ "
              f"{fmt(*sr.mean_std('success_rate')):>9} │ "
              f"{fmt(*sr.mean_std('requests_per_min')):>10} │ "
              f"{fmt(*sr.mean_std('avg_boot_time')):>10} │ "
              f"{fmt(*sr.mean_std('host_cpu_pct')):>9} │ "
              f"{fmt(*sr.mean_std('host_mem_pct')):>9}")

    print("─" * 140)
    if baseline_rtt:
        print(f"\n  Baseline RTT: {baseline_rtt:.2f} ms")
    print()


def print_resource_table(results: List[ScaleResult]):
    print("=" * 130)
    print("  PER-CONTAINER & AGGREGATE RESOURCE USAGE")
    print("=" * 130)
    hdr = (f"{'PLCs':>6} │ {'PLC CPU%':>10} │ {'PLC Mem':>10} │ "
           f"{'SCADA CPU%':>11} │ {'SCADA Mem':>10} │ "
           f"{'DMZ CPU%':>9} │ {'DMZ Mem':>9} │ "
           f"{'Total CPU%':>11} │ {'Total Mem':>11}")
    print(hdr)
    print("─" * 130)

    for sr in results:
        if sr.n_success == 0:
            continue
        print(f"{sr.scale:>6} │ "
              f"{fmt(*sr.mean_std('plc_avg_cpu')):>10} │ "
              f"{fmt(*sr.mean_std('plc_avg_mem_mb')):>8}MB │ "
              f"{fmt(*sr.mean_std('scada_cpu')):>11} │ "
              f"{fmt(*sr.mean_std('scada_mem_mb')):>8}MB │ "
              f"{fmt(*sr.mean_std('dmz_cpu')):>9} │ "
              f"{fmt(*sr.mean_std('dmz_mem_mb')):>7}MB │ "
              f"{fmt(*sr.mean_std('total_container_cpu')):>11} │ "
              f"{fmt(*sr.mean_std('total_container_mem_mb')):>9}MB")

    print("─" * 130)
    print()


def print_bottleneck(results: List[ScaleResult], baseline_rtt):
    """Identify and print the bottleneck at saturation."""
    if not results:
        return

    last = results[-1]
    if last.n_success == 0:
        print(f"  Bottleneck: All trials failed at {last.scale} PLCs\n")
        return

    issues = []
    suc_m, _ = last.mean_std("success_rate")
    rtt_m, _ = last.mean_std("avg_rtt")
    hmem_m, _ = last.mean_std("host_mem_pct")
    hcpu_m, _ = last.mean_std("host_cpu_pct")
    boot_m, _ = last.mean_std("avg_boot_time")

    if suc_m < SAT_SUCCESS_RATE:
        issues.append(f"Success rate dropped to {suc_m:.1f}%")
    if baseline_rtt and rtt_m > baseline_rtt * SAT_RTT_MULTIPLIER:
        issues.append(f"RTT degraded to {rtt_m:.1f}ms ({rtt_m/baseline_rtt:.1f}x baseline)")
    if hmem_m > SAT_HOST_MEMORY_PCT:
        issues.append(f"Host memory at {hmem_m:.1f}%")
    if hcpu_m > 90:
        issues.append(f"Host CPU at {hcpu_m:.1f}%")
    if boot_m > SAT_BOOT_TIME_SEC:
        issues.append(f"Boot time at {boot_m:.1f}s")

    if issues:
        print(f"  Bottleneck at {last.scale} PLCs:")
        for issue in issues:
            print(f"    → {issue}")
    else:
        print(f"  No clear bottleneck detected at {last.scale} PLCs")
    print()


# ═══════════════════════════════════════════════════════════════════
# SATURATION CHECK
# ═══════════════════════════════════════════════════════════════════

def check_saturation(sr: ScaleResult, baseline_rtt):
    if sr.n_success == 0:
        return True, "All trials failed"

    reasons = []
    suc_m, _ = sr.mean_std("success_rate")
    rtt_m, _ = sr.mean_std("avg_rtt")
    boot_m, _ = sr.mean_std("avg_boot_time")
    hmem_m, _ = sr.mean_std("host_mem_pct")

    if suc_m < SAT_SUCCESS_RATE:
        reasons.append(f"success {suc_m:.1f}% < {SAT_SUCCESS_RATE}%")
    if baseline_rtt and baseline_rtt > 0 and rtt_m > baseline_rtt * SAT_RTT_MULTIPLIER:
        reasons.append(f"RTT {rtt_m:.1f}ms > {SAT_RTT_MULTIPLIER}x baseline")
    if hmem_m > SAT_HOST_MEMORY_PCT:
        reasons.append(f"host mem {hmem_m:.1f}% > {SAT_HOST_MEMORY_PCT}%")
    if boot_m > SAT_BOOT_TIME_SEC:
        reasons.append(f"boot {boot_m:.1f}s > {SAT_BOOT_TIME_SEC}s")

    return (True, "; ".join(reasons)) if reasons else (False, "")


# ═══════════════════════════════════════════════════════════════════
# PREFLIGHT
# ═══════════════════════════════════════════════════════════════════

def preflight(api, switch_template_name):
    print("\n  Preflight checks...")

    # GNS3 API
    try:
        version = api.get("/version")
        print(f"  ✓ GNS3 API accessible (version {version.get('version', '?')})")
    except Exception as e:
        print(f"  ✗ Cannot reach GNS3 API: {e}")
        print(f"    Check: is GNS3 running? Is the API port correct?")
        return False

    # Docker
    out, err = run_cmd("docker info", check=False, timeout=10)
    if out is None:
        print("  ✗ Docker not accessible")
        return False
    print("  ✓ Docker accessible")

    # Images
    for img in [PLC_IMAGE, SCADA_IMAGE, DMZ_IMAGE]:
        out, _ = run_cmd(f"docker image inspect {img}", check=False, timeout=10)
        if out is None:
            print(f"  ✗ Image not found: {img}")
            print(f"    Run: docker pull <your-dockerhub-user>/{img}")
            return False
        print(f"  ✓ Image: {img}")

    # Switch template
    sw = api.find_template(switch_template_name)
    if not sw:
        print(f"  ✗ Switch template '{switch_template_name}' not found")
        print(f"    Available templates:")
        for t in api.list_templates():
            print(f"      - {t['name']}")
        print(f"    Use --switch-template to specify the correct name")
        return False
    print(f"  ✓ Switch template: {sw['name']}")

    # Host resources
    mem = get_host_memory_pct()
    cpu = get_host_cpu_pct()
    print(f"  ✓ Host: CPU {cpu:.1f}%, Memory {mem:.1f}%")

    print()
    return True


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="IT/OT Scalability Test via GNS3 API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_gns3_scalability_test.py --scales 4 --trials 1 --duration 60
  python3 run_gns3_scalability_test.py --scales 4,8,16,32,64 --trials 3
  python3 run_gns3_scalability_test.py --gns3-port 3080 --switch-template "Open vSwitch"
        """
    )
    parser.add_argument("--gns3-host", default=GNS3_HOST)
    parser.add_argument("--gns3-port", type=int, default=GNS3_PORT)
    parser.add_argument("--switch-template", default=SWITCH_TEMPLATE_NAME,
                        help="Name of OVS template in GNS3 (default: 'Open vSwitch')")
    parser.add_argument("--scales", type=str,
                        default="4,8,16,32,64,100,150,200,250,300,350,400")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--duration", type=int, default=180,
                        help="Seconds per trial (default: 180)")
    parser.add_argument("--poll-interval", type=float, default=0.5)

    args = parser.parse_args()

    scales = [int(s.strip()) for s in args.scales.split(",")]
    api = GNS3API(args.gns3_host, args.gns3_port)

    est_hours = len(scales) * args.trials * (args.duration + 180) / 3600

    print("\n" + "=" * 60)
    print("  IT/OT SCALABILITY TEST (GNS3 + Open vSwitch)")
    print("=" * 60)
    print(f"  GNS3:           {args.gns3_host}:{args.gns3_port}")
    print(f"  Switch:         {args.switch_template}")
    print(f"  Scales:         {scales}")
    print(f"  Trials/scale:   {args.trials}")
    print(f"  Duration/trial: {args.duration}s")
    print(f"  Poll interval:  {args.poll_interval}s")
    print(f"  Est. time:      ~{est_hours:.1f} hours")
    print("=" * 60)

    # Preflight
    if not preflight(api, args.switch_template):
        print("  Preflight failed. Fix issues above and re-run.")
        sys.exit(1)

    # Ensure templates
    templates = ensure_templates(api, args.switch_template)
    if not templates:
        sys.exit(1)

    # ── Run experiments ──
    all_results: List[ScaleResult] = []
    baseline_rtt = None

    for si, scale in enumerate(scales):
        print(f"\n{'═' * 60}")
        print(f"  SCALE: {scale} PLCs ({si + 1}/{len(scales)})")
        print(f"{'═' * 60}")

        mem = get_host_memory_pct()
        if mem > SAT_HOST_MEMORY_PCT:
            print(f"\n  ⚠ Host memory at {mem:.1f}% before starting — stopping.")
            break

        sr = ScaleResult(scale=scale)

        for trial in range(1, args.trials + 1):
            print(f"\n  ── Trial {trial}/{args.trials} ({scale} PLCs) ──")
            t0 = time.time()
            result = run_trial(api, templates, scale, trial,
                               args.poll_interval, args.duration,
                               args.switch_template)
            elapsed = time.time() - t0
            sr.trials.append(result)

            if result.success:
                log(f"Trial complete in {elapsed:.0f}s — "
                    f"RTT={result.avg_rtt:.1f}ms, "
                    f"Success={result.success_rate:.1f}%, "
                    f"HostCPU={result.host_cpu_pct:.1f}%, "
                    f"HostMem={result.host_mem_pct:.1f}%")
            else:
                log(f"Trial FAILED: {result.error}", "ERROR")

        all_results.append(sr)

        if baseline_rtt is None and sr.n_success > 0:
            baseline_rtt, _ = sr.mean_std("avg_rtt")
            if baseline_rtt == 0:
                baseline_rtt = None

        # Print cumulative results
        print_results_table(all_results, baseline_rtt)
        print_resource_table(all_results)

        # Check saturation
        if baseline_rtt:
            sat, reason = check_saturation(sr, baseline_rtt)
            if sat:
                print(f"  *** SATURATION DETECTED at {scale} PLCs: {reason} ***\n")
                break

    # ── Final output ──
    print("\n" + "=" * 140)
    print("  FINAL RESULTS")
    print("=" * 140)
    print_results_table(all_results, baseline_rtt)
    print_resource_table(all_results)
    print_bottleneck(all_results, baseline_rtt)

    # Find saturation point
    sat_scale = None
    last_good = None
    for sr in all_results:
        sat, _ = check_saturation(sr, baseline_rtt or 1)
        if sat:
            sat_scale = sr.scale
            break
        last_good = sr.scale

    if sat_scale:
        if last_good:
            print(f"  Saturation point: between {last_good} and {sat_scale} PLCs")
        else:
            print(f"  Saturation point: at or below {sat_scale} PLCs")
    else:
        print(f"  No saturation detected up to {all_results[-1].scale} PLCs")

    print(f"\n  Workload: Modbus/TCP read (10 holding registers), poll interval {args.poll_interval}s")
    print(f"  Request: 12 bytes, Response: 29 bytes per poll")
    print(f"  Trials per scale: {args.trials}, Duration per trial: {args.duration}s")
    print(f"  Network: GNS3 + Open vSwitch (L2 forwarded, not Docker bridge)")
    print()


if __name__ == "__main__":
    main()