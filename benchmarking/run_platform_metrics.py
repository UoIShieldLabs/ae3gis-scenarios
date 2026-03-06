#!/usr/bin/env python3
"""
IT/OT Platform Performance Metrics — Boot Time, API Latency, Throughput

Measures student-facing performance of the GNS3 platform:
  - Boot time: wall-clock time to build and start a scenario (per-phase breakdown)
  - API latency: response time for common REST API operations under load
  - Telnet latency: time to execute a command via container console
  - Throughput: bytes transferred between client and server during boot and workflows
  - Resource usage: host CPU/memory and aggregate container stats (when available)

Works both locally (on the GNS3 VM) and remotely (from a student laptop).
Only requires GNS3 REST API access and telnet to console ports.

Usage:
  python3 run_platform_metrics.py --scales 50,100,250 --trials 10
  python3 run_platform_metrics.py --gns3-host 192.168.1.50 --scales 50,100 --trials 5
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
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="telnetlib")
import telnetlib
import threading
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

GNS3_HOST = "localhost"
GNS3_PORT = 80
SWITCH_TEMPLATE_NAME = "Open-vSwitch"
SWITCH_PORTS = 16
SWITCH_FIRST_DATA_PORT = 1

PLC_IMAGE = "itot-plc:v0.2"
SCADA_IMAGE = "itot-scada:v0.2"
DMZ_IMAGE = "itot-dmz:v0.2"

# Layout
NODE_SPACING_X = 120
NODE_SPACING_Y = 80
PLC_GRID_COLS = 20

# Latency test
API_LATENCY_REQUESTS = 20
TELNET_LATENCY_REQUESTS = 20
TELNET_TIMEOUT = 10


# ═══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BootPhase:
    name: str
    duration: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0
    api_calls: int = 0


@dataclass
class LatencyMeasurement:
    endpoint: str
    times_ms: List[float] = field(default_factory=list)

    @property
    def mean(self):
        return statistics.mean(self.times_ms) if self.times_ms else 0

    @property
    def std(self):
        return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0

    @property
    def p95(self):
        if not self.times_ms:
            return 0
        s = sorted(self.times_ms)
        return s[int(len(s) * 0.95)]

    @property
    def min_val(self):
        return min(self.times_ms) if self.times_ms else 0

    @property
    def max_val(self):
        return max(self.times_ms) if self.times_ms else 0


@dataclass
class TrialResult:
    scale: int
    trial: int
    # Boot time
    boot_phases: List[BootPhase] = field(default_factory=list)
    total_boot_time: float = 0.0
    total_boot_bytes_sent: int = 0
    total_boot_bytes_received: int = 0
    total_boot_api_calls: int = 0
    # API latency
    api_latencies: List[LatencyMeasurement] = field(default_factory=list)
    # Telnet latency
    telnet_latency: Optional[LatencyMeasurement] = None
    # Active workflow
    workflow_bytes_sent: int = 0
    workflow_bytes_received: int = 0
    workflow_api_calls: int = 0
    workflow_duration: float = 0.0
    # Resources
    host_cpu_pct: float = 0.0
    host_mem_pct: float = 0.0
    total_container_cpu: float = 0.0
    total_container_mem_mb: float = 0.0
    # Status
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
        d_total = total2 - total1
        if d_total == 0:
            return 0.0
        return (1.0 - (idle2 - idle1) / d_total) * 100
    except Exception:
        return 0.0


def get_docker_stats():
    """Try to get aggregate docker stats. Returns (total_cpu, total_mem_mb) or (0,0)."""
    try:
        out, _ = run_cmd(
            'docker stats --no-stream --format \'{{.CPUPerc}},{{.MemUsage}}\'',
            check=False, timeout=30
        )
        if not out:
            return 0.0, 0.0

        total_cpu = 0.0
        total_mem = 0.0
        for line in out.strip().splitlines():
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    cpu = float(parts[0].replace("%", ""))
                    mem_str = parts[1].split("/")[0].strip()
                    if mem_str.endswith("GiB"):
                        mem = float(mem_str[:-3]) * 1024
                    elif mem_str.endswith("MiB"):
                        mem = float(mem_str[:-3])
                    elif mem_str.endswith("KiB"):
                        mem = float(mem_str[:-3]) / 1024
                    else:
                        mem = 0
                    total_cpu += cpu
                    total_mem += mem
                except ValueError:
                    continue
        return total_cpu, total_mem
    except Exception:
        return 0.0, 0.0


def plc_ip(i):
    z = i - 1
    return f"10.0.{z // 254 + 1}.{z % 254 + 1}"


# ═══════════════════════════════════════════════════════════════════
# GNS3 API CLIENT WITH BYTE TRACKING
# ═══════════════════════════════════════════════════════════════════

class GNS3API:
    def __init__(self, host, port):
        self.base = f"http://{host}:{port}/v2"
        self.host = host
        self.port = port
        # Byte tracking
        self._bytes_sent = 0
        self._bytes_received = 0
        self._call_count = 0
        self._tracking = False

    def start_tracking(self):
        self._bytes_sent = 0
        self._bytes_received = 0
        self._call_count = 0
        self._tracking = True

    def stop_tracking(self):
        self._tracking = False
        return self._bytes_sent, self._bytes_received, self._call_count

    def get_tracked(self):
        return self._bytes_sent, self._bytes_received, self._call_count

    def _request(self, method, path, data=None, timeout=60):
        url = f"{self.base}{path}"
        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")

        # Track bytes sent
        request_size = len(url) + len(method) + 50  # headers estimate
        if body:
            request_size += len(body)

        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                response_size = len(raw) + 200  # headers estimate

                if self._tracking:
                    self._bytes_sent += request_size
                    self._bytes_received += response_size
                    self._call_count += 1

                return json.loads(raw.decode()) if raw.strip() else {}
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

    def list_templates(self):
        return self.get("/templates")

    def find_template(self, name_contains):
        for t in self.list_templates():
            if name_contains.lower() in t.get("name", "").lower():
                return t
        return None

    def create_docker_template(self, name, image, adapters=1, start_cmd="",
                                env=""):
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
        return self.post("/templates", data)

    def create_project(self, name):
        return self.post("/projects", {"name": name})

    def delete_project(self, project_id):
        return self.delete(f"/projects/{project_id}")

    def close_project(self, project_id):
        return self.post(f"/projects/{project_id}/close")

    def create_node(self, project_id, template_id, name, x=0, y=0,
                     compute_id="local"):
        data = {"x": x, "y": y, "name": name, "compute_id": compute_id}
        return self.post(f"/projects/{project_id}/templates/{template_id}",
                         data, timeout=120)

    def get_nodes(self, project_id):
        return self.get(f"/projects/{project_id}/nodes")

    def get_node(self, project_id, node_id):
        return self.get(f"/projects/{project_id}/nodes/{node_id}")

    def start_node(self, project_id, node_id):
        return self.post(f"/projects/{project_id}/nodes/{node_id}/start",
                         timeout=120)

    def stop_node(self, project_id, node_id):
        return self.post(f"/projects/{project_id}/nodes/{node_id}/stop",
                         timeout=60)

    def start_all_nodes(self, project_id):
        nodes = self.get_nodes(project_id)
        for n in nodes:
            if n.get("status") != "started":
                self.start_node(project_id, n["node_id"])

    def create_link(self, project_id, node1_id, adapter1, port1,
                     node2_id, adapter2, port2):
        data = {
            "nodes": [
                {"node_id": node1_id, "adapter_number": adapter1,
                 "port_number": port1},
                {"node_id": node2_id, "adapter_number": adapter2,
                 "port_number": port2},
            ]
        }
        return self.post(f"/projects/{project_id}/links", data)


# ═══════════════════════════════════════════════════════════════════
# TOPOLOGY PLANNER (same as scalability script)
# ═══════════════════════════════════════════════════════════════════

class TopologyPlanner:
    def __init__(self, n_plcs, total_ports=16, first_data_port=1):
        self.n = n_plcs
        self.data_ports = total_ports - first_data_port
        self.child_ports = self.data_ports - 1  # 14

    def plan_switches(self):
        n = self.n
        cp = self.child_ports

        if n <= cp:
            return [{"name": "OT-Switch", "role": "root+leaf", "children": [],
                      "plc_start": 1, "plc_end": n}]

        if n <= cp * cp:
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

        plcs_per_spine = cp * cp
        max_3level = cp * cp * cp
        if n > max_3level:
            raise ValueError(f"Cannot support {n} PLCs (max {max_3level})")

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
        positions = {}
        positions["SCADA"] = (0, 0)
        positions["IT-Switch"] = (NODE_SPACING_X * 2, 0)
        positions["DMZ"] = (NODE_SPACING_X * 4, 0)

        sw_x_start = NODE_SPACING_X * 6
        switch_names = [s["name"] for s in switches]
        if switch_names:
            positions[switch_names[0]] = (sw_x_start, 0)
        non_root = switch_names[1:] if len(switch_names) > 1 else []
        for i, name in enumerate(non_root):
            y_off = (i - len(non_root) // 2) * NODE_SPACING_Y
            positions[name] = (sw_x_start + NODE_SPACING_X * 2, y_off)

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
# TOPOLOGY BUILDER
# ═══════════════════════════════════════════════════════════════════

def ensure_templates(api, switch_template_name):
    templates = {}
    sw = api.find_template(switch_template_name)
    if not sw:
        print(f"  ✗ Switch template '{switch_template_name}' not found.")
        for t in api.list_templates():
            print(f"    - {t['name']}")
        return None
    templates["switch"] = sw["template_id"]
    print(f"  ✓ Switch: {sw['name']}")

    for role, image, adapters, env in [
        ("plc", PLC_IMAGE, 1, "PLC_ID=1"),
        ("scada", SCADA_IMAGE, 1, ""),
        ("dmz", DMZ_IMAGE, 2, ""),
    ]:
        tname = f"itot-{role}"
        existing = api.find_template(tname)
        if existing:
            templates[role] = existing["template_id"]
            print(f"  ✓ {tname}")
        else:
            try:
                t = api.create_docker_template(tname, image, adapters, env=env)
                templates[role] = t["template_id"]
                print(f"  ✓ Created {tname}")
            except Exception as e:
                print(f"  ✗ Failed: {tname}: {e}")
                return None
    return templates


def build_topology(api, project_id, templates, n_plcs):
    """Create nodes and links. Returns dict of nodes."""
    planner = TopologyPlanner(n_plcs)
    switches = planner.plan_switches()
    positions = planner.plan_layout(switches)

    nodes = {}
    switch_nodes = {}

    # Infrastructure
    x, y = positions["SCADA"]
    n = api.create_node(project_id, templates["scada"], "SCADA", x, y)
    nodes["SCADA"] = n

    x, y = positions["IT-Switch"]
    n = api.create_node(project_id, templates["switch"], "IT-Switch", x, y)
    nodes["IT-Switch"] = n
    switch_nodes["IT-Switch"] = n["node_id"]

    x, y = positions["DMZ"]
    n = api.create_node(project_id, templates["dmz"], "DMZ", x, y)
    nodes["DMZ"] = n

    for sw in switches:
        x, y = positions.get(sw["name"], (800, 0))
        n = api.create_node(project_id, templates["switch"], sw["name"], x, y)
        switch_nodes[sw["name"]] = n["node_id"]
        nodes[sw["name"]] = n

    # PLCs
    for i in range(1, n_plcs + 1):
        name = f"PLC-{i}"
        x, y = positions[name]
        n = api.create_node(project_id, templates["plc"], name, x, y)
        nodes[name] = n
        if i % 20 == 0 or i == n_plcs:
            log_progress(i, n_plcs, "PLCs created")

    # ── Wiring ──
    # IT side
    api.create_link(project_id,
                    nodes["SCADA"]["node_id"], 0, 0,
                    switch_nodes["IT-Switch"], SWITCH_FIRST_DATA_PORT, 0)
    api.create_link(project_id,
                    switch_nodes["IT-Switch"], SWITCH_FIRST_DATA_PORT + 1, 0,
                    nodes["DMZ"]["node_id"], 0, 0)

    # OT side
    root_sw = switches[0]
    root_id = switch_nodes[root_sw["name"]]
    api.create_link(project_id,
                    nodes["DMZ"]["node_id"], 1, 0,
                    root_id, SWITCH_FIRST_DATA_PORT, 0)

    if root_sw["role"] == "root+leaf":
        for i in range(1, n_plcs + 1):
            sw_adapter = SWITCH_FIRST_DATA_PORT + i
            api.create_link(project_id,
                            root_id, sw_adapter, 0,
                            nodes[f"PLC-{i}"]["node_id"], 0, 0)
            if i % 20 == 0 or i == n_plcs:
                log_progress(i, n_plcs, "PLCs wired")
    else:
        next_adapter = {switches[0]["name"]: SWITCH_FIRST_DATA_PORT + 1}
        plcs_wired = 0

        for sw in switches[1:]:
            parent_name = sw.get("parent")
            if parent_name:
                parent_id = switch_nodes[parent_name]
                child_id = switch_nodes[sw["name"]]
                p_adapter = next_adapter.get(parent_name, SWITCH_FIRST_DATA_PORT + 1)
                next_adapter[parent_name] = p_adapter + 1
                api.create_link(project_id,
                                parent_id, p_adapter, 0,
                                child_id, SWITCH_FIRST_DATA_PORT, 0)
                next_adapter[sw["name"]] = SWITCH_FIRST_DATA_PORT + 1

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

    return nodes


def wait_all_started(api, project_id, timeout=300):
    """Poll until all nodes report status='started'. Returns time taken."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        nodes = api.get_nodes(project_id)
        all_started = True
        for n in nodes:
            if n.get("node_type") == "docker" and n.get("status") != "started":
                all_started = False
                break
        if all_started:
            return time.time() - t0
        time.sleep(2)
    return timeout


# ═══════════════════════════════════════════════════════════════════
# MEASUREMENTS
# ═══════════════════════════════════════════════════════════════════

def measure_api_latency(api, project_id, nodes, n_requests):
    """Measure response time for common API operations."""
    results = []

    # Pick a PLC node for single-node and start/stop tests
    plc_node = None
    for name, n in nodes.items():
        if "PLC" in name:
            plc_node = n
            break

    # 1. GET /nodes (list all)
    lat = LatencyMeasurement(endpoint="GET /nodes (list all)")
    for _ in range(n_requests):
        t0 = time.time()
        api.get(f"/projects/{project_id}/nodes")
        lat.times_ms.append((time.time() - t0) * 1000)
    results.append(lat)

    # 2. GET /nodes/{id} (single node)
    if plc_node:
        lat = LatencyMeasurement(endpoint="GET /nodes/{id} (single)")
        for _ in range(n_requests):
            t0 = time.time()
            api.get(f"/projects/{project_id}/nodes/{plc_node['node_id']}")
            lat.times_ms.append((time.time() - t0) * 1000)
        results.append(lat)

    # 3. POST stop + start (action)
    if plc_node:
        lat = LatencyMeasurement(endpoint="POST stop/start (action)")
        for _ in range(n_requests):
            t0 = time.time()
            try:
                api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/stop",
                         timeout=30)
                api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/start",
                         timeout=30)
            except Exception:
                pass
            lat.times_ms.append((time.time() - t0) * 1000)
        results.append(lat)

    return results


def measure_telnet_latency(api_host, nodes, n_requests):
    """Measure time to execute a command via telnet console."""
    lat = LatencyMeasurement(endpoint="Telnet command (hostname)")

    # Find a PLC node with console info
    console_port = None
    for name, n in nodes.items():
        if "PLC" in name and n.get("console"):
            console_port = n["console"]
            break

    if not console_port:
        log("No console port found for telnet test", "WARN")
        return lat

    try:
        # Connect once
        tn = telnetlib.Telnet(api_host, console_port, timeout=TELNET_TIMEOUT)
        time.sleep(1)  # wait for shell to be ready
        # Clear any initial output (MOTD, prompt, etc.)
        try:
            tn.read_very_eager()
        except Exception:
            pass

        # Send a dummy command first to ensure shell is responsive
        tn.write(b"echo ready\n")
        try:
            tn.read_until(b"ready", timeout=5)
            tn.read_very_eager()  # clear remaining output
        except Exception:
            pass

        # Now measure individual commands
        for i in range(n_requests):
            try:
                # Clear any buffered output
                try:
                    tn.read_very_eager()
                except Exception:
                    pass

                # Time only the command execution
                marker = f"MARK{int(time.time()*1000)}"
                t0 = time.time()
                tn.write(f"echo {marker}\n".encode())
                tn.read_until(marker.encode(), timeout=TELNET_TIMEOUT)
                t1 = time.time()
                lat.times_ms.append((t1 - t0) * 1000)
            except Exception as e:
                log(f"Telnet command {i+1} failed: {e}", "WARN")

        tn.close()

    except Exception as e:
        log(f"Telnet connection failed: {e}", "WARN")

    return lat


def measure_active_workflow(api, project_id, nodes):
    """Simulate a student workflow and track bytes transferred."""
    api.start_tracking()
    t0 = time.time()

    # 1. List all nodes (student opens topology view)
    api.get(f"/projects/{project_id}/nodes")

    # 2. Get details of 3 specific nodes (student clicks on nodes)
    checked = 0
    for name, n in nodes.items():
        if checked >= 3:
            break
        api.get(f"/projects/{project_id}/nodes/{n['node_id']}")
        checked += 1

    # 3. Stop a node (student stops a container)
    plc_node = None
    for name, n in nodes.items():
        if "PLC" in name:
            plc_node = n
            break

    if plc_node:
        try:
            api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/stop",
                     timeout=30)
        except Exception:
            pass

    # 4. Start it back (student restarts it)
    if plc_node:
        try:
            api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/start",
                     timeout=30)
        except Exception:
            pass

    # 5. List nodes again (student checks status)
    api.get(f"/projects/{project_id}/nodes")

    duration = time.time() - t0
    sent, received, calls = api.stop_tracking()
    return sent, received, calls, duration


# ═══════════════════════════════════════════════════════════════════
# SINGLE TRIAL
# ═══════════════════════════════════════════════════════════════════

def run_trial(api, templates, n_plcs, trial_num, n_latency_requests,
              n_telnet_requests):
    """Run one complete trial."""
    result = TrialResult(scale=n_plcs, trial=trial_num)
    project_id = None

    try:
        # ══════════ BOOT TIME ══════════
        log("Phase: Boot time measurement")
        boot_start = time.time()

        # Phase 1: Create project
        api.start_tracking()
        t0 = time.time()
        project_name = f"metrics-s{n_plcs}-t{trial_num}-{int(time.time())}"
        project = api.create_project(project_name)
        project_id = project["project_id"]
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Project creation",
                                             time.time() - t0, sent, recv, calls))

        # Phase 2: Create nodes
        api.start_tracking()
        t0 = time.time()
        log(f"Creating {n_plcs} PLCs + infrastructure...")
        nodes = build_topology(api, project_id, templates, n_plcs)
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Node creation",
                                             time.time() - t0, sent, recv, calls))

        # Phase 3: Wiring is done inside build_topology
        # (already tracked above — wiring is part of node creation phase)

        # Phase 4: Start all nodes
        api.start_tracking()
        t0 = time.time()
        log("Starting all nodes...")
        api.start_all_nodes(project_id)
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Node startup",
                                             time.time() - t0, sent, recv, calls))

        # Phase 5: Wait for readiness
        api.start_tracking()
        t0 = time.time()
        log("Waiting for all nodes to be ready...")
        readiness_time = wait_all_started(api, project_id)
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Readiness",
                                             time.time() - t0, sent, recv, calls))

        result.total_boot_time = time.time() - boot_start
        for phase in result.boot_phases:
            result.total_boot_bytes_sent += phase.bytes_sent
            result.total_boot_bytes_received += phase.bytes_received
            result.total_boot_api_calls += phase.api_calls

        log(f"Boot complete: {result.total_boot_time:.1f}s "
            f"({result.total_boot_api_calls} API calls, "
            f"{(result.total_boot_bytes_sent + result.total_boot_bytes_received) / 1024:.1f} KB)")

        # ══════════ STABILIZATION ══════════
        log("Stabilizing (15s)...")
        time.sleep(15)

        # ══════════ API LATENCY ══════════
        log(f"Measuring API latency ({n_latency_requests} requests/endpoint)...")
        # Disable tracking during latency tests (we want clean timing)
        api._tracking = False
        result.api_latencies = measure_api_latency(
            api, project_id, nodes, n_latency_requests)

        for lat in result.api_latencies:
            log(f"  {lat.endpoint}: {lat.mean:.1f}±{lat.std:.1f}ms "
                f"(p95={lat.p95:.1f}ms)")

        # ══════════ TELNET LATENCY ══════════
        log(f"Measuring telnet latency ({n_telnet_requests} attempts)...")
        # Re-fetch nodes to get console ports (they're assigned after start)
        fresh_nodes = {}
        for n in api.get_nodes(project_id):
            fresh_nodes[n["name"]] = n

        result.telnet_latency = measure_telnet_latency(
            api.host, fresh_nodes, n_telnet_requests)

        if result.telnet_latency.times_ms:
            log(f"  Telnet: {result.telnet_latency.mean:.1f}±"
                f"{result.telnet_latency.std:.1f}ms")
        else:
            log("  Telnet: no successful measurements", "WARN")

        # ══════════ ACTIVE WORKFLOW THROUGHPUT ══════════
        log("Measuring active workflow throughput...")
        (result.workflow_bytes_sent, result.workflow_bytes_received,
         result.workflow_api_calls, result.workflow_duration) = \
            measure_active_workflow(api, project_id, nodes)

        total_wf_bytes = result.workflow_bytes_sent + result.workflow_bytes_received
        log(f"  Workflow: {total_wf_bytes / 1024:.1f} KB in "
            f"{result.workflow_duration:.1f}s "
            f"({result.workflow_api_calls} API calls)")

        # ══════════ RESOURCE SNAPSHOT ══════════
        log("Collecting resource snapshot...")
        result.host_cpu_pct = get_host_cpu_pct()
        result.host_mem_pct = get_host_memory_pct()
        result.total_container_cpu, result.total_container_mem_mb = get_docker_stats()
        log(f"  Host: CPU={result.host_cpu_pct:.1f}%, Mem={result.host_mem_pct:.1f}%")
        if result.total_container_cpu > 0 or result.total_container_mem_mb > 0:
            log(f"  Containers: CPU={result.total_container_cpu:.1f}%, "
                f"Mem={result.total_container_mem_mb:.0f}MB")

    except Exception as e:
        result.success = False
        result.error = str(e)
        log(f"Trial failed: {e}", "ERROR")

    finally:
        if project_id:
            log("Cleaning up...")
            try:
                api.close_project(project_id)
                time.sleep(2)
                api.delete_project(project_id)
            except Exception as e:
                log(f"Cleanup warning: {e}", "WARN")
        time.sleep(5)

    return result


# ═══════════════════════════════════════════════════════════════════
# RESULTS PRINTING
# ═══════════════════════════════════════════════════════════════════

def fmt(mean, std):
    if mean == 0 and std == 0:
        return "N/A"
    return f"{mean:.1f}±{std:.1f}" if std > 0.05 else f"{mean:.1f}"


def fmt_int(mean, std):
    if mean == 0 and std == 0:
        return "N/A"
    return f"{int(mean)}±{int(std)}" if std > 0.5 else f"{int(mean)}"


def print_boot_time_table(results: List[ScaleResult]):
    print("\n" + "=" * 100)
    print("  BOOT TIME (seconds)")
    print("=" * 100)
    print(f"{'PLCs':>6} │ {'Trials':>7} │ {'Total Boot':>12} │ "
          f"{'Node Creation':>14} │ {'Node Startup':>14} │ {'Readiness':>12} │ "
          f"{'API Calls':>10} │ {'Data (KB)':>10}")
    print("─" * 100)

    for sr in results:
        if sr.n_success == 0:
            print(f"{sr.scale:>6} │ {'FAIL':>7} │ " + "─" * 80)
            continue

        # Get phase-level means
        ok_trials = [t for t in sr.trials if t.success]

        # Total boot
        bt_m, bt_s = sr.mean_std("total_boot_time")

        # Per-phase (index into boot_phases)
        def phase_stat(phase_idx):
            vals = [t.boot_phases[phase_idx].duration for t in ok_trials
                    if len(t.boot_phases) > phase_idx]
            if not vals:
                return 0, 0
            return statistics.mean(vals), statistics.stdev(vals) if len(vals) > 1 else 0

        _, _ = phase_stat(0)  # project creation (negligible)
        nc_m, nc_s = phase_stat(1)  # node creation + wiring
        ns_m, ns_s = phase_stat(2)  # node startup
        rd_m, rd_s = phase_stat(3)  # readiness

        ac_m, ac_s = sr.mean_std("total_boot_api_calls")
        total_bytes = [(t.total_boot_bytes_sent + t.total_boot_bytes_received) / 1024
                       for t in ok_trials]
        kb_m = statistics.mean(total_bytes) if total_bytes else 0
        kb_s = statistics.stdev(total_bytes) if len(total_bytes) > 1 else 0

        print(f"{sr.scale:>6} │ {sr.n_success:>5}/{len(sr.trials):<1} │ "
              f"{fmt(bt_m, bt_s):>10}s │ "
              f"{fmt(nc_m, nc_s):>12}s │ "
              f"{fmt(ns_m, ns_s):>12}s │ "
              f"{fmt(rd_m, rd_s):>10}s │ "
              f"{fmt_int(ac_m, ac_s):>10} │ "
              f"{fmt(kb_m, kb_s):>10}")

    print("─" * 100)
    print()


def print_api_latency_table(results: List[ScaleResult]):
    print("=" * 110)
    print("  API LATENCY (milliseconds)")
    print("=" * 110)

    # Collect endpoint names from first successful trial
    endpoints = []
    for sr in results:
        for t in sr.trials:
            if t.success and t.api_latencies:
                endpoints = [l.endpoint for l in t.api_latencies]
                break
        if endpoints:
            break

    for endpoint in endpoints:
        print(f"\n  Endpoint: {endpoint}")
        print(f"  {'PLCs':>6} │ {'Mean':>10} │ {'Std':>10} │ {'Min':>10} │ "
              f"{'Max':>10} │ {'p95':>10}")
        print(f"  {'─' * 70}")

        for sr in results:
            ok = [t for t in sr.trials if t.success]
            if not ok:
                print(f"  {sr.scale:>6} │ {'FAIL':>10}")
                continue

            # Aggregate all measurements across trials
            all_times = []
            for t in ok:
                for lat in t.api_latencies:
                    if lat.endpoint == endpoint:
                        all_times.extend(lat.times_ms)

            if all_times:
                mean = statistics.mean(all_times)
                std = statistics.stdev(all_times) if len(all_times) > 1 else 0
                mn = min(all_times)
                mx = max(all_times)
                s = sorted(all_times)
                p95 = s[int(len(s) * 0.95)]
                print(f"  {sr.scale:>6} │ {mean:>8.1f}ms │ {std:>8.1f}ms │ "
                      f"{mn:>8.1f}ms │ {mx:>8.1f}ms │ {p95:>8.1f}ms")

    print()


def print_telnet_latency_table(results: List[ScaleResult]):
    print("=" * 70)
    print("  TELNET COMMAND LATENCY (milliseconds)")
    print("=" * 70)
    print(f"{'PLCs':>6} │ {'Mean':>10} │ {'Std':>10} │ {'Min':>10} │ "
          f"{'Max':>10} │ {'p95':>10}")
    print("─" * 70)

    for sr in results:
        ok = [t for t in sr.trials if t.success]
        if not ok:
            print(f"{sr.scale:>6} │ {'FAIL':>10}")
            continue

        all_times = []
        for t in ok:
            if t.telnet_latency and t.telnet_latency.times_ms:
                all_times.extend(t.telnet_latency.times_ms)

        if all_times:
            mean = statistics.mean(all_times)
            std = statistics.stdev(all_times) if len(all_times) > 1 else 0
            mn = min(all_times)
            mx = max(all_times)
            s = sorted(all_times)
            p95 = s[int(len(s) * 0.95)]
            print(f"{sr.scale:>6} │ {mean:>8.1f}ms │ {std:>8.1f}ms │ "
                  f"{mn:>8.1f}ms │ {mx:>8.1f}ms │ {p95:>8.1f}ms")
        else:
            print(f"{sr.scale:>6} │ {'N/A':>10}")

    print("─" * 70)
    print()


def print_throughput_table(results: List[ScaleResult]):
    print("=" * 90)
    print("  DATA TRANSFER (bytes)")
    print("=" * 90)
    print(f"{'PLCs':>6} │ {'Boot Sent':>12} │ {'Boot Recv':>12} │ {'Boot Total':>12} │ "
          f"{'Wkflow Sent':>12} │ {'Wkflow Recv':>12} │ {'Wkflow Total':>12}")
    print("─" * 90)

    for sr in results:
        ok = [t for t in sr.trials if t.success]
        if not ok:
            print(f"{sr.scale:>6} │ {'FAIL':>12}")
            continue

        bs = statistics.mean([t.total_boot_bytes_sent for t in ok])
        br = statistics.mean([t.total_boot_bytes_received for t in ok])
        ws = statistics.mean([t.workflow_bytes_sent for t in ok])
        wr = statistics.mean([t.workflow_bytes_received for t in ok])

        print(f"{sr.scale:>6} │ {bs:>10.0f}B │ {br:>10.0f}B │ {bs+br:>10.0f}B │ "
              f"{ws:>10.0f}B │ {wr:>10.0f}B │ {ws+wr:>10.0f}B")

    print("─" * 90)
    print("  Note: Idle throughput (scenario running, no user interaction) is near-zero")
    print("  since all simulated network traffic stays within the GNS3 VM.")
    print()


def print_resource_table(results: List[ScaleResult]):
    print("=" * 70)
    print("  HOST & CONTAINER RESOURCES")
    print("=" * 70)
    print(f"{'PLCs':>6} │ {'Host CPU%':>12} │ {'Host Mem%':>12} │ "
          f"{'Total CPU%':>12} │ {'Total Mem':>12}")
    print("─" * 70)

    for sr in results:
        if sr.n_success == 0:
            continue
        hc_m, hc_s = sr.mean_std("host_cpu_pct")
        hm_m, hm_s = sr.mean_std("host_mem_pct")
        tc_m, tc_s = sr.mean_std("total_container_cpu")
        tm_m, tm_s = sr.mean_std("total_container_mem_mb")

        print(f"{sr.scale:>6} │ {fmt(hc_m, hc_s):>12} │ {fmt(hm_m, hm_s):>12} │ "
              f"{fmt(tc_m, tc_s):>12} │ {fmt(tm_m, tm_s):>10}MB")

    print("─" * 70)
    print()


# ═══════════════════════════════════════════════════════════════════
# PREFLIGHT
# ═══════════════════════════════════════════════════════════════════

def preflight(api, switch_template_name):
    print("\n  Preflight checks...")

    try:
        version = api.get("/version")
        print(f"  ✓ GNS3 API v{version.get('version', '?')} at "
              f"{api.host}:{api.port}")
    except Exception as e:
        print(f"  ✗ Cannot reach GNS3 API: {e}")
        return False

    for img in [PLC_IMAGE, SCADA_IMAGE, DMZ_IMAGE]:
        out, _ = run_cmd(f"docker image inspect {img}", check=False, timeout=10)
        if out is None:
            print(f"  ⚠ Image not found locally: {img} (OK if running remotely)")
        else:
            print(f"  ✓ Image: {img}")

    sw = api.find_template(switch_template_name)
    if not sw:
        print(f"  ✗ Switch template '{switch_template_name}' not found")
        return False
    print(f"  ✓ Switch: {sw['name']}")

    print()
    return True


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="IT/OT Platform Performance Metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_platform_metrics.py --scales 50,100,250 --trials 10
  python3 run_platform_metrics.py --gns3-host 192.168.1.50 --scales 50,100 --trials 5
  python3 run_platform_metrics.py --scales 50 --trials 1  # quick test
        """
    )
    parser.add_argument("--gns3-host", default=GNS3_HOST)
    parser.add_argument("--gns3-port", type=int, default=GNS3_PORT)
    parser.add_argument("--switch-template", default=SWITCH_TEMPLATE_NAME)
    parser.add_argument("--scales", type=str, default="50,100,250")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--api-requests", type=int, default=API_LATENCY_REQUESTS,
                        help="Number of API requests per endpoint for latency test")
    parser.add_argument("--telnet-requests", type=int, default=TELNET_LATENCY_REQUESTS,
                        help="Number of telnet commands for latency test")

    args = parser.parse_args()

    scales = [int(s.strip()) for s in args.scales.split(",")]
    api = GNS3API(args.gns3_host, args.gns3_port)

    est_minutes = len(scales) * args.trials * 5  # rough: ~5 min per trial
    print("\n" + "=" * 60)
    print("  IT/OT PLATFORM PERFORMANCE METRICS")
    print("=" * 60)
    print(f"  GNS3:           {args.gns3_host}:{args.gns3_port}")
    print(f"  Switch:         {args.switch_template}")
    print(f"  Scales:         {scales}")
    print(f"  Trials/scale:   {args.trials}")
    print(f"  API requests:   {args.api_requests}/endpoint")
    print(f"  Telnet tests:   {args.telnet_requests}")
    print(f"  Est. time:      ~{est_minutes} minutes")
    print("=" * 60)

    if not preflight(api, args.switch_template):
        print("  Preflight failed.")
        sys.exit(1)

    templates = ensure_templates(api, args.switch_template)
    if not templates:
        sys.exit(1)

    # ── Run experiments ──
    all_results: List[ScaleResult] = []

    for si, scale in enumerate(scales):
        print(f"\n{'═' * 60}")
        print(f"  SCALE: {scale} PLCs ({si + 1}/{len(scales)})")
        print(f"{'═' * 60}")

        sr = ScaleResult(scale=scale)

        for trial in range(1, args.trials + 1):
            print(f"\n  ── Trial {trial}/{args.trials} ({scale} PLCs) ──")
            t0 = time.time()
            result = run_trial(api, templates, scale, trial,
                               args.api_requests, args.telnet_requests)
            elapsed = time.time() - t0
            sr.trials.append(result)

            if result.success:
                log(f"Trial complete in {elapsed:.0f}s — "
                    f"boot={result.total_boot_time:.1f}s")
            else:
                log(f"Trial FAILED: {result.error}", "ERROR")

        all_results.append(sr)

        # Print cumulative results
        print_boot_time_table(all_results)
        print_api_latency_table(all_results)
        print_telnet_latency_table(all_results)
        print_throughput_table(all_results)
        print_resource_table(all_results)

    # ── Final output ──
    print("\n" + "=" * 110)
    print("  FINAL RESULTS")
    print("=" * 110)
    print_boot_time_table(all_results)
    print_api_latency_table(all_results)
    print_telnet_latency_table(all_results)
    print_throughput_table(all_results)
    print_resource_table(all_results)

    print(f"  Platform: GNS3 v2.2.x + Open vSwitch")
    print(f"  GNS3 host: {args.gns3_host}:{args.gns3_port}")
    print(f"  Scales tested: {scales}")
    print(f"  Trials per scale: {args.trials}")
    print(f"  API latency: {args.api_requests} requests/endpoint")
    print(f"  Telnet latency: {args.telnet_requests} commands/trial")
    print()


if __name__ == "__main__":
    main()
