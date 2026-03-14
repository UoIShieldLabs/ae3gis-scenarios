#!/usr/bin/env python3
"""
ICS Network Platform Benchmark — Realistic IT/OT Topology

Builds a Purdue-model IT/OT network in GNS3, starts all services, and measures:
  - Boot time (per-phase breakdown + data transferred)
  - API latency (list nodes, single node, stop/start, telnet command)
  - Data transfer (boot phase + active student workflow)

Topology:
  IT side:  M workstations + 1 monitor WS + 1 web server + 1 FTP server
  DMZ:      1 firewall (3 interfaces) + 1 historian (MariaDB)
  OT side:  1 SCADA server + N PLCs

All configurable via command-line arguments. Run once per scenario config.

Usage:
  python3 run_ics_benchmark.py --n-plcs 5 --n-workstations 10 --trials 1 --duration 60
  python3 run_ics_benchmark.py --n-plcs 100 --n-workstations 200 --trials 20 --duration 180
"""

import argparse, json, math, os, re, socket, statistics, subprocess, sys, time
import threading
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    import telnetlib
except ImportError:
    telnetlib = None

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

GNS3_HOST = "localhost"
GNS3_PORT = 80
SWITCH_TEMPLATE_NAME = "Open vSwitch"
SWITCH_FIRST_DATA_PORT = 1  # port 0 is management, skip it

# Images
IMG_PLC = "itot-plc:latest"
IMG_SCADA = "itot-scada-v2:latest"
IMG_FIREWALL = "itot-firewall:latest"
IMG_HISTORIAN = "itot-historian:latest"
IMG_WEBSERVER = "itot-webserver:latest"
IMG_FTPSERVER = "itot-ftpserver:latest"
IMG_WORKSTATION = "itot-workstation:latest"

# Network addressing
IT_SUBNET = "192.168.1"
DMZ_SUBNET = "172.16.0"
OT_PREFIX = "10.0"

FIREWALL_IT_IP = f"{IT_SUBNET}.1"
FIREWALL_DMZ_IP = f"{DMZ_SUBNET}.1"
FIREWALL_OT_IP = f"{OT_PREFIX}.0.1"
WEBSERVER_IP = f"{IT_SUBNET}.2"
FTPSERVER_IP = f"{IT_SUBNET}.3"
MONITOR_IP = f"{IT_SUBNET}.4"
HISTORIAN_IP = f"{DMZ_SUBNET}.2"
SCADA_IP = f"{OT_PREFIX}.0.2"

# Latency test defaults
API_LATENCY_REQUESTS = 20
TELNET_LATENCY_REQUESTS = 10
TELNET_TIMEOUT = 10

# Layout
SPACING_X = 120
SPACING_Y = 80
GRID_COLS = 20


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
    def mean(self): return statistics.mean(self.times_ms) if self.times_ms else 0
    @property
    def std(self): return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0
    @property
    def p95(self):
        if not self.times_ms: return 0
        s = sorted(self.times_ms)
        return s[int(len(s) * 0.95)]
    @property
    def min_val(self): return min(self.times_ms) if self.times_ms else 0
    @property
    def max_val(self): return max(self.times_ms) if self.times_ms else 0

@dataclass
class TrialResult:
    n_plcs: int
    n_workstations: int
    trial: int
    boot_phases: List[BootPhase] = field(default_factory=list)
    total_boot_time: float = 0.0
    total_boot_bytes_sent: int = 0
    total_boot_bytes_received: int = 0
    total_boot_api_calls: int = 0
    api_latencies: List[LatencyMeasurement] = field(default_factory=list)
    telnet_latency: Optional[LatencyMeasurement] = None
    workflow_bytes_sent: int = 0
    workflow_bytes_received: int = 0
    workflow_api_calls: int = 0
    workflow_duration: float = 0.0
    success: bool = True
    error: str = ""

@dataclass
class ExperimentResult:
    n_plcs: int
    n_workstations: int
    trials: List[TrialResult] = field(default_factory=list)
    def _ok(self): return [t for t in self.trials if t.success]
    @property
    def n_success(self): return len(self._ok())
    def mean_std(self, attr):
        vals = [getattr(t, attr) for t in self._ok()]
        if not vals: return 0.0, 0.0
        m = statistics.mean(vals)
        s = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return m, s


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def run_cmd(cmd, check=True, timeout=300):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0: return None, r.stderr.strip()
        return r.stdout.strip(), ""
    except subprocess.TimeoutExpired: return None, "Timeout"
    except Exception as e: return None, str(e)

def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {level}: {msg}", flush=True)

def log_progress(current, total, label=""):
    pct = current / total * 100 if total > 0 else 0
    filled = int(30 * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (30 - filled)
    print(f"\r  [{bar}] {current}/{total} {label} ({pct:.0f}%)", end="", flush=True)
    if current == total: print(flush=True)

def plc_ip(i):
    z = i - 1
    return f"10.0.{z // 254 + 1}.{z % 254 + 1}"

def workstation_ip(i):
    """Workstation i (1-indexed) -> 192.168.1.20, .21, ..."""
    return f"{IT_SUBNET}.{19 + i}"

def docker_exec(container_id, cmd, timeout=30, detach=False):
    d = "-d " if detach else ""
    return run_cmd(f'docker exec {d}{container_id} sh -c "{cmd}"', check=False, timeout=timeout)


# ═══════════════════════════════════════════════════════════════════
# GNS3 API CLIENT WITH BYTE TRACKING
# ═══════════════════════════════════════════════════════════════════

class GNS3API:
    def __init__(self, host, port):
        self.base = f"http://{host}:{port}/v2"
        self.host = host
        self.port = port
        self._bytes_sent = 0
        self._bytes_received = 0
        self._call_count = 0
        self._tracking = False

    def start_tracking(self):
        self._bytes_sent = 0; self._bytes_received = 0; self._call_count = 0
        self._tracking = True

    def stop_tracking(self):
        self._tracking = False
        return self._bytes_sent, self._bytes_received, self._call_count

    def _request(self, method, path, data=None, timeout=60):
        url = f"{self.base}{path}"
        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        req_size = len(url) + len(method) + 50 + (len(body) if body else 0)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                resp_size = len(raw) + 200
                if self._tracking:
                    self._bytes_sent += req_size
                    self._bytes_received += resp_size
                    self._call_count += 1
                return json.loads(raw.decode()) if raw.strip() else {}
        except HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            raise RuntimeError(f"GNS3 API {method} {path} -> {e.code}: {body_text}")
        except URLError as e:
            raise RuntimeError(f"GNS3 API connection failed: {e}")

    def get(self, path, timeout=30): return self._request("GET", path, timeout=timeout)
    def post(self, path, data=None, timeout=60): return self._request("POST", path, data=data, timeout=timeout)
    def delete(self, path, timeout=60): return self._request("DELETE", path, timeout=timeout)

    def list_templates(self): return self.get("/templates")
    def find_template(self, name_contains):
        for t in self.list_templates():
            if name_contains.lower() in t.get("name", "").lower(): return t
        return None

    def create_docker_template(self, name, image, adapters=1, env=""):
        return self.post("/templates", {
            "name": name, "template_type": "docker", "compute_id": "local",
            "image": image, "adapters": adapters, "start_command": "",
            "console_type": "telnet", "environment": env,
        })

    def create_project(self, name): return self.post("/projects", {"name": name})
    def delete_project(self, pid): return self.delete(f"/projects/{pid}")
    def close_project(self, pid): return self.post(f"/projects/{pid}/close")

    def create_node(self, pid, tid, name, x=0, y=0):
        return self.post(f"/projects/{pid}/templates/{tid}",
                         {"x": x, "y": y, "name": name, "compute_id": "local"}, timeout=120)

    def get_nodes(self, pid): return self.get(f"/projects/{pid}/nodes")
    def get_node(self, pid, nid): return self.get(f"/projects/{pid}/nodes/{nid}")

    def start_node(self, pid, nid):
        return self.post(f"/projects/{pid}/nodes/{nid}/start", timeout=120)
    def stop_node(self, pid, nid):
        return self.post(f"/projects/{pid}/nodes/{nid}/stop", timeout=60)

    def start_all_nodes(self, pid):
        for n in self.get_nodes(pid):
            if n.get("status") != "started":
                self.start_node(pid, n["node_id"])

    def create_link(self, pid, n1_id, a1, p1, n2_id, a2, p2):
        return self.post(f"/projects/{pid}/links", {"nodes": [
            {"node_id": n1_id, "adapter_number": a1, "port_number": p1},
            {"node_id": n2_id, "adapter_number": a2, "port_number": p2},
        ]})


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def ensure_templates(api, switch_template_name, switch_adapters):
    templates = {}

    # Switch
    sw = api.find_template(switch_template_name)
    if not sw:
        print(f"  ✗ Switch template '{switch_template_name}' not found.")
        for t in api.list_templates():
            print(f"    - {t['name']}")
        return None
    templates["switch"] = sw["template_id"]
    print(f"  ✓ Switch: {sw['name']}")

    # Docker templates
    image_specs = [
        ("plc",         IMG_PLC,         1, "PLC_ID=1"),
        ("scada",       IMG_SCADA,       1, ""),
        ("firewall",    IMG_FIREWALL,    3, ""),  # 3 adapters: IT, DMZ, OT
        ("historian",   IMG_HISTORIAN,   1,
         "MARIADB_ROOT_PASSWORD=icslab\nMARIADB_DATABASE=ics_historian\nMARIADB_USER=scada\nMARIADB_PASSWORD=scada"),
        ("webserver",   IMG_WEBSERVER,   1, ""),
        ("ftpserver",   IMG_FTPSERVER,   1, ""),
        ("workstation", IMG_WORKSTATION, 1, ""),
    ]

    for role, image, adapters, env in image_specs:
        tname = f"ics-{role}"
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


# ═══════════════════════════════════════════════════════════════════
# TOPOLOGY BUILDER
# ═══════════════════════════════════════════════════════════════════

def compute_layout(n_plcs, n_ws):
    """Compute (x,y) positions for all nodes."""
    pos = {}
    # Core infrastructure in a column on the left
    pos["Web-Server"] = (0, 0)
    pos["FTP-Server"] = (0, SPACING_Y)
    pos["Monitor-WS"] = (0, SPACING_Y * 2)
    pos["IT-Switch"] = (SPACING_X * 2, SPACING_Y)
    pos["Firewall"] = (SPACING_X * 4, SPACING_Y)
    pos["Historian"] = (SPACING_X * 4, SPACING_Y * 3)
    pos["OT-Switch"] = (SPACING_X * 6, SPACING_Y)
    pos["SCADA"] = (SPACING_X * 8, 0)

    # Workstations in grid below IT switch
    ws_x_start = -SPACING_X * 2
    ws_y_start = SPACING_Y * 4
    for i in range(1, n_ws + 1):
        col = (i - 1) % GRID_COLS
        row = (i - 1) // GRID_COLS
        pos[f"WS-{i}"] = (ws_x_start + col * (SPACING_X // 2),
                           ws_y_start + row * (SPACING_Y // 2))

    # PLCs in grid to the right of OT switch
    plc_x_start = SPACING_X * 8
    plc_y_start = SPACING_Y * 2
    for i in range(1, n_plcs + 1):
        col = (i - 1) % GRID_COLS
        row = (i - 1) // GRID_COLS
        pos[f"PLC-{i}"] = (plc_x_start + col * (SPACING_X // 2),
                            plc_y_start + row * (SPACING_Y // 2))

    return pos


def build_topology(api, project_id, templates, n_plcs, n_ws):
    """Create all nodes and links. Returns dict of node info."""
    pos = compute_layout(n_plcs, n_ws)
    nodes = {}

    # ── Create nodes ──
    log("Creating infrastructure nodes...")
    for name, role in [("Web-Server", "webserver"), ("FTP-Server", "ftpserver"),
                       ("Monitor-WS", "workstation"), ("SCADA", "scada"),
                       ("Firewall", "firewall"), ("Historian", "historian")]:
        x, y = pos[name]
        n = api.create_node(project_id, templates[role], name, x, y)
        nodes[name] = n

    # Switches
    for name in ["IT-Switch", "OT-Switch"]:
        x, y = pos[name]
        n = api.create_node(project_id, templates["switch"], name, x, y)
        nodes[name] = n

    # PLCs
    log(f"Creating {n_plcs} PLCs...")
    for i in range(1, n_plcs + 1):
        name = f"PLC-{i}"
        x, y = pos[name]
        n = api.create_node(project_id, templates["plc"], name, x, y)
        nodes[name] = n
        if i % 20 == 0 or i == n_plcs:
            log_progress(i, n_plcs, "PLCs created")

    # Workstations
    log(f"Creating {n_ws} workstations...")
    for i in range(1, n_ws + 1):
        name = f"WS-{i}"
        x, y = pos[name]
        n = api.create_node(project_id, templates["workstation"], name, x, y)
        nodes[name] = n
        if i % 20 == 0 or i == n_ws:
            log_progress(i, n_ws, "workstations created")

    # ── Wiring ──
    it_sw = nodes["IT-Switch"]["node_id"]
    ot_sw = nodes["OT-Switch"]["node_id"]
    fw = nodes["Firewall"]["node_id"]

    log("Wiring IT side...")
    # OVS uses (adapter=PORT, port=0). Port 0 = management, skip it.
    next_it_port = SWITCH_FIRST_DATA_PORT  # starts at 1

    # IT-Switch port 1 → Firewall adapter 0 (eth0 = IT interface)
    api.create_link(project_id, it_sw, next_it_port, 0, fw, 0, 0)
    next_it_port += 1

    # IT-Switch port 2 → Web Server
    api.create_link(project_id, it_sw, next_it_port, 0,
                    nodes["Web-Server"]["node_id"], 0, 0)
    next_it_port += 1

    # IT-Switch port 3 → FTP Server
    api.create_link(project_id, it_sw, next_it_port, 0,
                    nodes["FTP-Server"]["node_id"], 0, 0)
    next_it_port += 1

    # IT-Switch port 4 → Monitor WS
    api.create_link(project_id, it_sw, next_it_port, 0,
                    nodes["Monitor-WS"]["node_id"], 0, 0)
    next_it_port += 1

    # IT-Switch ports 5..N → Workstations
    for i in range(1, n_ws + 1):
        api.create_link(project_id, it_sw, next_it_port, 0,
                        nodes[f"WS-{i}"]["node_id"], 0, 0)
        next_it_port += 1
        if i % 20 == 0 or i == n_ws:
            log_progress(i, n_ws, "workstations wired")

    log("Wiring DMZ...")
    # Firewall adapter 1 (eth1 = DMZ) → Historian
    api.create_link(project_id, fw, 1, 0,
                    nodes["Historian"]["node_id"], 0, 0)

    log("Wiring OT side...")
    next_ot_port = SWITCH_FIRST_DATA_PORT

    # OT-Switch port 1 → Firewall adapter 2 (eth2 = OT interface)
    api.create_link(project_id, ot_sw, next_ot_port, 0, fw, 2, 0)
    next_ot_port += 1

    # OT-Switch port 2 → SCADA
    api.create_link(project_id, ot_sw, next_ot_port, 0,
                    nodes["SCADA"]["node_id"], 0, 0)
    next_ot_port += 1

    # OT-Switch ports 3..N → PLCs
    for i in range(1, n_plcs + 1):
        api.create_link(project_id, ot_sw, next_ot_port, 0,
                        nodes[f"PLC-{i}"]["node_id"], 0, 0)
        next_ot_port += 1
        if i % 20 == 0 or i == n_plcs:
            log_progress(i, n_plcs, "PLCs wired")

    return nodes


# ═══════════════════════════════════════════════════════════════════
# NODE CONFIGURATION & SERVICE STARTUP
# ═══════════════════════════════════════════════════════════════════

def wait_all_started(api, project_id, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        nodes = api.get_nodes(project_id)
        if all(n.get("status") == "started" for n in nodes
               if n.get("node_type") == "docker"):
            return time.time() - t0
        time.sleep(2)
    return timeout


def get_container_ids(api, project_id):
    """Map node names to Docker container IDs."""
    cmap = {}
    for n in api.get_nodes(project_id):
        cid = n.get("properties", {}).get("container_id", "")
        if cid:
            cmap[n["name"]] = cid
    return cmap


def configure_and_start(cmap, n_plcs, n_ws, poll_interval, historian_push,
                         monitor_interval):
    """Configure networking and start all services."""

    # ── Firewall ──
    fw = cmap.get("Firewall", "")
    if fw:
        log("Configuring firewall...")
        docker_exec(fw, "/app/firewall_setup.sh")

    # ── IT fixed nodes ──
    for name, ip, extra_route in [
        ("Web-Server", WEBSERVER_IP, ""),
        ("FTP-Server", FTPSERVER_IP, ""),
        ("Monitor-WS", MONITOR_IP, f"ip route add {DMZ_SUBNET}.0/24 via {FIREWALL_IT_IP}"),
    ]:
        cid = cmap.get(name, "")
        if cid:
            docker_exec(cid, f"ip addr add {ip}/24 dev eth0 2>/dev/null; true")
            if extra_route:
                docker_exec(cid, f"{extra_route} 2>/dev/null; true")

    # ── Start web server (nginx) ──
    ws_cid = cmap.get("Web-Server", "")
    if ws_cid:
        log("Starting web server (nginx)...")
        docker_exec(ws_cid, "nginx", detach=True)

    # ── Start FTP server (vsftpd) ──
    ftp_cid = cmap.get("FTP-Server", "")
    if ftp_cid:
        log("Starting FTP server...")
        docker_exec(ftp_cid, "vsftpd /etc/vsftpd/vsftpd.conf", detach=True)

    # ── Historian (MariaDB starts automatically) — just configure IP ──
    hist_cid = cmap.get("Historian", "")
    if hist_cid:
        log("Configuring historian...")
        docker_exec(hist_cid, f"ip addr add {HISTORIAN_IP}/24 dev eth0 2>/dev/null; true")
        docker_exec(hist_cid,
                     f"ip route add {IT_SUBNET}.0/24 via {FIREWALL_DMZ_IP} 2>/dev/null; true")
        docker_exec(hist_cid,
                     f"ip route add {OT_PREFIX}.0.0/16 via {FIREWALL_DMZ_IP} 2>/dev/null; true")

    # ── SCADA ──
    scada_cid = cmap.get("SCADA", "")
    if scada_cid:
        log("Configuring SCADA...")
        docker_exec(scada_cid, f"ip addr add {SCADA_IP}/16 dev eth0 2>/dev/null; true")
        docker_exec(scada_cid,
                     f"ip route add {DMZ_SUBNET}.0/24 via {FIREWALL_OT_IP} 2>/dev/null; true")

    # ── PLCs ──
    log(f"Configuring {n_plcs} PLCs...")
    for i in range(1, n_plcs + 1):
        name = f"PLC-{i}"
        cid = cmap.get(name, "")
        if cid:
            ip = plc_ip(i)
            docker_exec(cid, f"ip addr add {ip}/16 dev eth0 2>/dev/null; true")
            docker_exec(cid,
                         f"ip route add {DMZ_SUBNET}.0/24 via {FIREWALL_OT_IP} 2>/dev/null; true")
            docker_exec(cid, f"PLC_ID={i} python /app/plc_simulator.py", detach=True)
        if i % 20 == 0 or i == n_plcs:
            log_progress(i, n_plcs, "PLCs configured")

    # ── Workstations ──
    log(f"Configuring {n_ws} workstations...")
    for i in range(1, n_ws + 1):
        name = f"WS-{i}"
        cid = cmap.get(name, "")
        if cid:
            ip = workstation_ip(i)
            docker_exec(cid, f"ip addr add {ip}/24 dev eth0 2>/dev/null; true")
            docker_exec(cid,
                (f"MODE=workstation WEB_SERVER={WEBSERVER_IP} FTP_SERVER={FTPSERVER_IP} "
                 f"python /app/traffic_gen.py"),
                detach=True)
        if i % 20 == 0 or i == n_ws:
            log_progress(i, n_ws, "workstations configured")

    # ── Start Monitor WS ──
    mon_cid = cmap.get("Monitor-WS", "")
    if mon_cid:
        log("Starting monitor workstation...")
        docker_exec(mon_cid,
            (f"MODE=monitor HISTORIAN_HOST={HISTORIAN_IP} "
             f"MONITOR_INTERVAL={monitor_interval} "
             f"python /app/traffic_gen.py"),
            detach=True)

    # ── Start SCADA (after PLCs are running) ──
    if scada_cid:
        plc_hosts = ",".join(plc_ip(i) for i in range(1, n_plcs + 1))
        log("Starting SCADA poller...")
        docker_exec(scada_cid,
            (f"PLC_HOSTS={plc_hosts} POLL_INTERVAL={poll_interval} "
             f"HISTORIAN_HOST={HISTORIAN_IP} HISTORIAN_PUSH={historian_push} "
             f"python /app/scada_v2.py"),
            detach=True)


# ═══════════════════════════════════════════════════════════════════
# MEASUREMENTS (same as platform metrics script)
# ═══════════════════════════════════════════════════════════════════

def measure_api_latency(api, project_id, nodes, n_requests):
    results = []
    plc_node = None
    for name, n in nodes.items():
        if "PLC" in name:
            plc_node = n
            break

    # GET /nodes (list all)
    lat = LatencyMeasurement(endpoint="GET /nodes (list all)")
    for _ in range(n_requests):
        t0 = time.time()
        api.get(f"/projects/{project_id}/nodes")
        lat.times_ms.append((time.time() - t0) * 1000)
    results.append(lat)

    # GET /nodes/{id} (single)
    if plc_node:
        lat = LatencyMeasurement(endpoint="GET /nodes/{id} (single)")
        for _ in range(n_requests):
            t0 = time.time()
            api.get(f"/projects/{project_id}/nodes/{plc_node['node_id']}")
            lat.times_ms.append((time.time() - t0) * 1000)
        results.append(lat)

    # POST stop/start
    if plc_node:
        lat = LatencyMeasurement(endpoint="POST stop/start (action)")
        for _ in range(n_requests):
            t0 = time.time()
            try:
                api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/stop", timeout=30)
                api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/start", timeout=30)
            except Exception:
                pass
            lat.times_ms.append((time.time() - t0) * 1000)
        results.append(lat)

    return results


def measure_telnet_latency(api_host, nodes, n_requests):
    lat = LatencyMeasurement(endpoint="Telnet command")
    if not telnetlib:
        log("telnetlib not available", "WARN")
        return lat

    console_port = None
    for name, n in nodes.items():
        if "PLC" in name and n.get("console"):
            console_port = n["console"]
            break
    if not console_port:
        log("No console port found", "WARN")
        return lat

    try:
        tn = telnetlib.Telnet(api_host, console_port, timeout=TELNET_TIMEOUT)
        time.sleep(1)
        try: tn.read_very_eager()
        except: pass
        tn.write(b"echo ready\n")
        try:
            tn.read_until(b"ready", timeout=5)
            tn.read_very_eager()
        except: pass

        for i in range(n_requests):
            try:
                try: tn.read_very_eager()
                except: pass
                marker = f"MARK{int(time.time()*1000)}"
                t0 = time.time()
                tn.write(f"echo {marker}\n".encode())
                tn.read_until(marker.encode(), timeout=TELNET_TIMEOUT)
                lat.times_ms.append((time.time() - t0) * 1000)
            except Exception as e:
                log(f"Telnet cmd {i+1} failed: {e}", "WARN")
        tn.close()
    except Exception as e:
        log(f"Telnet connection failed: {e}", "WARN")

    return lat


def measure_active_workflow(api, project_id, nodes):
    api.start_tracking()
    t0 = time.time()

    api.get(f"/projects/{project_id}/nodes")
    checked = 0
    for name, n in nodes.items():
        if checked >= 3: break
        api.get(f"/projects/{project_id}/nodes/{n['node_id']}")
        checked += 1

    plc_node = None
    for name, n in nodes.items():
        if "PLC" in name:
            plc_node = n
            break
    if plc_node:
        try:
            api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/stop", timeout=30)
            api.post(f"/projects/{project_id}/nodes/{plc_node['node_id']}/start", timeout=30)
        except: pass

    api.get(f"/projects/{project_id}/nodes")

    duration = time.time() - t0
    sent, received, calls = api.stop_tracking()
    return sent, received, calls, duration


# ═══════════════════════════════════════════════════════════════════
# SINGLE TRIAL
# ═══════════════════════════════════════════════════════════════════

def run_trial(api, templates, n_plcs, n_ws, trial_num, duration,
              poll_interval, historian_push, monitor_interval,
              n_api_requests, n_telnet_requests):
    result = TrialResult(n_plcs=n_plcs, n_workstations=n_ws, trial=trial_num)
    project_id = None

    try:
        # ══════ BOOT TIME ══════
        log("Phase: Boot time")
        boot_start = time.time()

        # Phase 1: Project creation
        api.start_tracking()
        t0 = time.time()
        pname = f"ics-p{n_plcs}-w{n_ws}-t{trial_num}-{int(time.time())}"
        project = api.create_project(pname)
        project_id = project["project_id"]
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Project creation", time.time() - t0, sent, recv, calls))

        # Phase 2: Node creation + wiring
        api.start_tracking()
        t0 = time.time()
        nodes = build_topology(api, project_id, templates, n_plcs, n_ws)
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Node creation & wiring", time.time() - t0, sent, recv, calls))

        # Phase 3: Start all nodes
        api.start_tracking()
        t0 = time.time()
        log("Starting all nodes...")
        api.start_all_nodes(project_id)
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Node startup", time.time() - t0, sent, recv, calls))

        # Phase 4: Wait for readiness
        api.start_tracking()
        t0 = time.time()
        log("Waiting for readiness...")
        wait_all_started(api, project_id)
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Readiness", time.time() - t0, sent, recv, calls))

        # Phase 5: Configure networking + start services
        api.start_tracking()
        t0 = time.time()
        log("Configuring nodes and starting services...")
        cmap = get_container_ids(api, project_id)
        log(f"  Found {len(cmap)} container IDs")
        configure_and_start(cmap, n_plcs, n_ws, poll_interval,
                            historian_push, monitor_interval)
        sent, recv, calls = api.stop_tracking()
        result.boot_phases.append(BootPhase("Service config", time.time() - t0, sent, recv, calls))

        result.total_boot_time = time.time() - boot_start
        for phase in result.boot_phases:
            result.total_boot_bytes_sent += phase.bytes_sent
            result.total_boot_bytes_received += phase.bytes_received
            result.total_boot_api_calls += phase.api_calls

        total_nodes = n_plcs + n_ws + 6  # PLCs + WSs + SCADA + FW + Historian + Web + FTP + Monitor
        log(f"Boot complete: {result.total_boot_time:.1f}s "
            f"({result.total_boot_api_calls} API calls, "
            f"{(result.total_boot_bytes_sent + result.total_boot_bytes_received) / 1024:.1f} KB, "
            f"{total_nodes} nodes)")

        # ══════ STABILIZATION ══════
        log(f"Stabilizing ({duration}s — services running)...")
        time.sleep(duration)

        # ══════ API LATENCY ══════
        log(f"Measuring API latency ({n_api_requests} requests/endpoint)...")
        api._tracking = False
        result.api_latencies = measure_api_latency(api, project_id, nodes, n_api_requests)
        for lat in result.api_latencies:
            log(f"  {lat.endpoint}: {lat.mean:.1f}±{lat.std:.1f}ms (p95={lat.p95:.1f}ms)")

        # ══════ TELNET LATENCY ══════
        log(f"Measuring telnet latency ({n_telnet_requests} attempts)...")
        fresh_nodes = {n["name"]: n for n in api.get_nodes(project_id)}
        result.telnet_latency = measure_telnet_latency(api.host, fresh_nodes, n_telnet_requests)
        if result.telnet_latency.times_ms:
            log(f"  Telnet: {result.telnet_latency.mean:.1f}±{result.telnet_latency.std:.1f}ms")
        else:
            log("  Telnet: no successful measurements", "WARN")

        # ══════ WORKFLOW THROUGHPUT ══════
        log("Measuring active workflow throughput...")
        (result.workflow_bytes_sent, result.workflow_bytes_received,
         result.workflow_api_calls, result.workflow_duration) = \
            measure_active_workflow(api, project_id, nodes)
        wf_total = result.workflow_bytes_sent + result.workflow_bytes_received
        log(f"  Workflow: {wf_total / 1024:.1f} KB in {result.workflow_duration:.1f}s")

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
    if mean == 0 and std == 0: return "N/A"
    return f"{mean:.1f}±{std:.1f}" if std > 0.05 else f"{mean:.1f}"

def fmt_int(mean, std):
    if mean == 0 and std == 0: return "N/A"
    return f"{int(mean)}±{int(std)}" if std > 0.5 else f"{int(mean)}"


def print_boot_time_table(er: ExperimentResult):
    print("\n" + "=" * 110)
    print(f"  BOOT TIME — {er.n_plcs} PLCs + {er.n_workstations} Workstations "
          f"({er.n_plcs + er.n_workstations + 6} total nodes)")
    print("=" * 110)

    ok = [t for t in er.trials if t.success]
    if not ok:
        print("  All trials failed.")
        return

    bt_m, bt_s = er.mean_std("total_boot_time")
    ac_m, ac_s = er.mean_std("total_boot_api_calls")
    total_bytes = [(t.total_boot_bytes_sent + t.total_boot_bytes_received) / 1024 for t in ok]
    kb_m = statistics.mean(total_bytes)
    kb_s = statistics.stdev(total_bytes) if len(total_bytes) > 1 else 0

    print(f"  Trials: {er.n_success}/{len(er.trials)}")
    print(f"  Total boot time:  {fmt(bt_m, bt_s)}s")
    print(f"  API calls:        {fmt_int(ac_m, ac_s)}")
    print(f"  Data transferred: {fmt(kb_m, kb_s)} KB")
    print()

    # Per-phase breakdown
    phase_names = set()
    for t in ok:
        for p in t.boot_phases:
            phase_names.add(p.name)

    print(f"  {'Phase':<25} │ {'Duration (s)':>15} │ {'Data (KB)':>12}")
    print(f"  {'─' * 58}")
    for pi in range(len(ok[0].boot_phases)):
        pname = ok[0].boot_phases[pi].name
        durations = [t.boot_phases[pi].duration for t in ok if len(t.boot_phases) > pi]
        datas = [(t.boot_phases[pi].bytes_sent + t.boot_phases[pi].bytes_received) / 1024
                 for t in ok if len(t.boot_phases) > pi]
        d_m = statistics.mean(durations) if durations else 0
        d_s = statistics.stdev(durations) if len(durations) > 1 else 0
        k_m = statistics.mean(datas) if datas else 0
        k_s = statistics.stdev(datas) if len(datas) > 1 else 0
        print(f"  {pname:<25} │ {fmt(d_m, d_s):>13}s │ {fmt(k_m, k_s):>12}")

    print()


def print_api_latency_table(er: ExperimentResult):
    ok = [t for t in er.trials if t.success]
    if not ok: return

    endpoints = [l.endpoint for l in ok[0].api_latencies] if ok[0].api_latencies else []
    if not endpoints: return

    print("=" * 80)
    print(f"  API & CONSOLE LATENCY — {er.n_plcs} PLCs + {er.n_workstations} WS")
    print("=" * 80)

    for endpoint in endpoints:
        all_times = []
        for t in ok:
            for lat in t.api_latencies:
                if lat.endpoint == endpoint:
                    all_times.extend(lat.times_ms)
        if not all_times: continue

        mean = statistics.mean(all_times)
        std = statistics.stdev(all_times) if len(all_times) > 1 else 0
        mn, mx = min(all_times), max(all_times)
        s = sorted(all_times)
        p95 = s[int(len(s) * 0.95)]

        print(f"  {endpoint}")
        print(f"    Mean: {mean:.1f}ms | Std: {std:.1f}ms | Min: {mn:.1f}ms | "
              f"Max: {mx:.1f}ms | p95: {p95:.1f}ms")

    # Telnet
    all_telnet = []
    for t in ok:
        if t.telnet_latency and t.telnet_latency.times_ms:
            all_telnet.extend(t.telnet_latency.times_ms)
    if all_telnet:
        mean = statistics.mean(all_telnet)
        std = statistics.stdev(all_telnet) if len(all_telnet) > 1 else 0
        mn, mx = min(all_telnet), max(all_telnet)
        s = sorted(all_telnet)
        p95 = s[int(len(s) * 0.95)]
        print(f"  Telnet command execution")
        print(f"    Mean: {mean:.1f}ms | Std: {std:.1f}ms | Min: {mn:.1f}ms | "
              f"Max: {mx:.1f}ms | p95: {p95:.1f}ms")

    print()


def print_throughput_table(er: ExperimentResult):
    ok = [t for t in er.trials if t.success]
    if not ok: return

    print("=" * 80)
    print(f"  DATA TRANSFER — {er.n_plcs} PLCs + {er.n_workstations} WS")
    print("=" * 80)

    bs = statistics.mean([t.total_boot_bytes_sent for t in ok])
    br = statistics.mean([t.total_boot_bytes_received for t in ok])
    bt = statistics.mean([t.total_boot_time for t in ok])
    ws = statistics.mean([t.workflow_bytes_sent for t in ok])
    wr = statistics.mean([t.workflow_bytes_received for t in ok])
    wd = statistics.mean([t.workflow_duration for t in ok])

    print(f"  Boot phase:")
    print(f"    Sent: {bs / 1024:.1f} KB | Received: {br / 1024:.1f} KB | "
          f"Total: {(bs + br) / 1024:.1f} KB")
    print(f"    Throughput: {(bs + br) / bt / 1024:.1f} KB/s over {bt:.1f}s")
    print(f"  Active workflow:")
    print(f"    Sent: {ws / 1024:.1f} KB | Received: {wr / 1024:.1f} KB | "
          f"Total: {(ws + wr) / 1024:.1f} KB")
    print(f"    Duration: {wd:.1f}s")
    print(f"  Idle (scenario running, no interaction):")
    print(f"    Near-zero — all simulated traffic stays within the GNS3 VM")
    print()


# ═══════════════════════════════════════════════════════════════════
# PREFLIGHT
# ═══════════════════════════════════════════════════════════════════

def preflight(api, switch_template_name):
    print("\n  Preflight checks...")
    try:
        v = api.get("/version")
        print(f"  ✓ GNS3 API v{v.get('version', '?')} at {api.host}:{api.port}")
    except Exception as e:
        print(f"  ✗ Cannot reach GNS3 API: {e}")
        return False

    for img in [IMG_PLC, IMG_SCADA, IMG_FIREWALL, IMG_HISTORIAN,
                IMG_WEBSERVER, IMG_FTPSERVER, IMG_WORKSTATION]:
        out, _ = run_cmd(f"docker image inspect {img}", check=False, timeout=10)
        if out is None:
            print(f"  ⚠ Image not found locally: {img}")
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
        description="ICS Network Platform Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_ics_benchmark.py --n-plcs 5 --n-workstations 10 --trials 1 --duration 60
  python3 run_ics_benchmark.py --n-plcs 100 --n-workstations 200 --trials 20
  python3 run_ics_benchmark.py --n-plcs 20 --n-workstations 50 --gns3-host 192.168.1.50
        """
    )
    parser.add_argument("--n-plcs", type=int, required=True, help="Number of PLCs")
    parser.add_argument("--n-workstations", type=int, required=True, help="Number of IT workstations")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--duration", type=int, default=180,
                        help="Seconds to let scenario run before measuring latency (default: 180)")
    parser.add_argument("--poll-interval", type=float, default=1.0,
                        help="SCADA poll interval in seconds (default: 1.0)")
    parser.add_argument("--historian-push", type=float, default=30,
                        help="SCADA → historian push interval (default: 30)")
    parser.add_argument("--monitor-interval", type=float, default=30,
                        help="Monitor WS → historian pull interval (default: 30)")
    parser.add_argument("--gns3-host", default=GNS3_HOST)
    parser.add_argument("--gns3-port", type=int, default=GNS3_PORT)
    parser.add_argument("--switch-template", default=SWITCH_TEMPLATE_NAME)
    parser.add_argument("--switch-adapters", type=int, default=256)
    parser.add_argument("--api-requests", type=int, default=API_LATENCY_REQUESTS)
    parser.add_argument("--telnet-requests", type=int, default=TELNET_LATENCY_REQUESTS)
    parser.add_argument("--label", type=str, default="")

    args = parser.parse_args()
    api = GNS3API(args.gns3_host, args.gns3_port)
    total_nodes = args.n_plcs + args.n_workstations + 6

    # ── Logging to file ──
    label = args.label or args.gns3_host.replace(".", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_filename = (f"ics_bench_{label}_p{args.n_plcs}_w{args.n_workstations}"
                    f"_t{args.trials}_{timestamp}.log")

    class Tee:
        def __init__(self, fn):
            self.terminal = sys.stdout
            self.log = open(fn, "w")
        def write(self, msg):
            self.terminal.write(msg)
            self.log.write(msg)
            self.log.flush()
        def flush(self):
            self.terminal.flush()
            self.log.flush()

    sys.stdout = Tee(log_filename)
    print(f"  Logging to: {log_filename}")

    est_min = args.trials * (args.duration / 60 + 5)
    print("\n" + "=" * 60)
    print("  ICS NETWORK PLATFORM BENCHMARK")
    print("=" * 60)
    print(f"  GNS3:           {args.gns3_host}:{args.gns3_port}")
    print(f"  PLCs:           {args.n_plcs}")
    print(f"  Workstations:   {args.n_workstations}")
    print(f"  Total nodes:    {total_nodes}")
    print(f"  Trials:         {args.trials}")
    print(f"  Duration/trial: {args.duration}s (stabilization)")
    print(f"  SCADA poll:     {args.poll_interval}s")
    print(f"  Historian push: {args.historian_push}s")
    print(f"  Monitor pull:   {args.monitor_interval}s")
    print(f"  Est. time:      ~{est_min:.0f} minutes")
    print("=" * 60)

    if not preflight(api, args.switch_template):
        print("  Preflight failed.")
        sys.exit(1)

    templates = ensure_templates(api, args.switch_template, args.switch_adapters)
    if not templates:
        sys.exit(1)

    # ── Run trials ──
    er = ExperimentResult(n_plcs=args.n_plcs, n_workstations=args.n_workstations)

    for trial in range(1, args.trials + 1):
        print(f"\n{'═' * 60}")
        print(f"  Trial {trial}/{args.trials} "
              f"({args.n_plcs} PLCs + {args.n_workstations} WS = {total_nodes} nodes)")
        print(f"{'═' * 60}")

        t0 = time.time()
        result = run_trial(api, templates, args.n_plcs, args.n_workstations, trial,
                           args.duration, args.poll_interval, args.historian_push,
                           args.monitor_interval, args.api_requests, args.telnet_requests)
        elapsed = time.time() - t0
        er.trials.append(result)

        if result.success:
            log(f"Trial complete in {elapsed:.0f}s — boot={result.total_boot_time:.1f}s")
        else:
            log(f"Trial FAILED: {result.error}", "ERROR")

        # Print cumulative results after each trial
        if er.n_success > 0:
            print_boot_time_table(er)
            print_api_latency_table(er)
            print_throughput_table(er)

    # ── Final output ──
    print("\n" + "=" * 110)
    print("  FINAL RESULTS")
    print("=" * 110)
    print_boot_time_table(er)
    print_api_latency_table(er)
    print_throughput_table(er)

    print(f"  Topology: {args.n_plcs} PLCs + SCADA + Historian (MariaDB) + Firewall + "
          f"Web Server + FTP Server + Monitor WS + {args.n_workstations} Workstations")
    print(f"  Workload: Modbus/TCP polling @{args.poll_interval}s, "
          f"historian push @{args.historian_push}s, "
          f"monitor pull @{args.monitor_interval}s")
    print(f"  IT traffic: HTTP (5-30s random) + FTP (60-120s random) per workstation")
    print(f"  Trials: {er.n_success}/{args.trials} successful")
    print(f"  Platform: GNS3 + Open vSwitch | Host: {args.gns3_host}:{args.gns3_port}")
    print()


if __name__ == "__main__":
    main()
