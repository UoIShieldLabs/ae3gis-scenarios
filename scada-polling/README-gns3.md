# IT/OT Scalability Test — GNS3 Automated Version

## What Changed

Previous version used raw Docker networking (shared memory, no real switch).
This version creates full GNS3 topologies via the REST API with Open vSwitch,
so traffic traverses real L2 forwarding pipelines. Expect higher RTT, more
variance, and more realistic saturation behavior.

## New Metrics

| Metric | Description |
|--------|-------------|
| RTT avg (ms) | Mean round-trip time across all polls in the interval |
| RTT p95 (ms) | 95th percentile RTT — captures tail latency/spikes the average hides |
| Throughput (B/s) | Aggregate bytes/sec across all PLCs |
| Per-PLC (B/s) | Throughput ÷ N — shows if per-node throughput degrades |
| Success % | Percentage of polls that got a valid Modbus response |
| Req/min | Polling rate — drops when SCADA can't keep up |
| Boot (s) | Time from container start to first successful Modbus connection |
| Host CPU % | Overall host CPU usage (from /proc/stat) |
| Host Mem % | Overall host memory usage |
| Total CPU % | Sum of all container CPU percentages (aggregate load) |
| Total Mem | Sum of all container memory (aggregate footprint) |
| PLC CPU % | Average CPU per PLC container |
| PLC Mem | Average memory per PLC container |
| SCADA/DMZ | Per-container stats for SCADA and DMZ |

## Prerequisites

### Already Done (from previous experiment)
- Docker images built and pushed to Docker Hub
- Images pulled on GNS3 VM and tagged as itot-plc:latest, itot-scada:latest, itot-dmz:latest

### Verify Before Running

SSH into your GNS3 VM and check these:

```bash
# 1. GNS3 is running and API is accessible
curl http://localhost:80/v2/version
# Should return JSON with GNS3 version

# 2. Docker images are present
docker images | grep itot
# Should show itot-plc, itot-scada, itot-dmz

# 3. Python 3.6+ available
python3 --version

# 4. Open vSwitch template exists in GNS3
# Open GNS3 GUI, check that you can drag an "Open vSwitch" onto canvas
# Note the exact template name — you may need it for --switch-template

# 5. No leftover projects from previous runs
# Check GNS3 GUI — close/delete any old itot-* projects
```

### If API Port Is Different

The default is port 80. If your GNS3 API is on a different port:
```bash
# Check which port GNS3 is listening on
curl http://localhost:80/v2/version    # try 80
curl http://localhost:3080/v2/version  # try 3080
```

## Running the Experiment

### Step 1: Copy script to VM

From your Mac:
```bash
scp run_gns3_scalability_test.py gns3@<vm-ip>:/home/gns3/
```

### Step 2: Quick test (do this first!)

```bash
ssh gns3@<vm-ip>
python3 run_gns3_scalability_test.py --scales 4 --trials 1 --duration 60
```

This creates a GNS3 project with 4 PLCs, runs for 1 minute, prints results,
and cleans up. Should take ~3-4 minutes total.

**What to look for:**
- Preflight checks all pass (✓)
- Nodes created and started
- Boot times measured (should be a few seconds)
- SCADA metrics appear (RTT, throughput, success rate)
- Project deleted at end

**If it fails:** check the error message and see Troubleshooting below.

### Step 3: Full experiment

```bash
python3 run_gns3_scalability_test.py \
  --scales 100,150,200,250,300,350,400, 450, 500 \
  --trials 3 \
  --duration 240
```

Estimated time: ~3-4 hours. Stops automatically at saturation.

### Step 4: Copy results

Results print directly to your terminal. Copy the tables into your paper.
No files to download.

## Command-Line Options

| Flag | Default | Description |
|------|---------|-------------|
| --gns3-host | localhost | GNS3 API host |
| --gns3-port | 80 | GNS3 API port |
| --switch-template | "Open vSwitch" | Name of your OVS template in GNS3 |
| --scales | 4,8,...,400 | Comma-separated PLC counts |
| --trials | 3 | Trials per scale point |
| --duration | 180 | Seconds per trial |
| --poll-interval | 0.5 | SCADA poll interval (seconds) |

## Troubleshooting

**"Cannot reach GNS3 API"**
→ Check port: `curl http://localhost:80/v2/version`
→ Try port 3080: `--gns3-port 3080`

**"Switch template not found"**
→ The script prints all available templates. Use the exact name with --switch-template
→ E.g., `--switch-template "Open vSwitch Management"`

**"Image not found"**
→ `docker images | grep itot` — re-tag if needed
→ `docker tag YOUR_USER/itot-plc:latest itot-plc:latest`

**"Could not find DMZ or SCADA container IDs"**
→ GNS3 may need more time to start containers
→ Try running again — the script cleans up between trials

**No metrics collected (RTT = 0, success = 0)**
→ Likely a routing issue. The DMZ may need privileged mode.
→ Try: `sudo python3 run_gns3_scalability_test.py`
→ Or manually test: start a 4-PLC topology in GNS3 GUI, configure IPs, ping between SCADA and a PLC

**Leftover projects after crash**
→ Open GNS3 GUI, close/delete any itot-* projects
→ Or: `docker rm -f $(docker ps -a -q)` (nuclear option — kills ALL containers)

**"Cannot create more than N nodes"**
→ VM memory limit. Increase VirtualBox VM memory allocation.

## How the Switch Tree Works

OVS has 16 ports. Port 0 = management (unused). Ports 1-15 = data.

```
4 PLCs:    DMZ ─[port1]─ OT-Switch ─[port2..5]─ PLC1-4

32 PLCs:   DMZ ─[port1]─ OT-Root ─[port2]─ Branch1 ─[port2..14]─ PLC1-13
                                  ─[port3]─ Branch2 ─[port2..14]─ PLC14-26
                                  ─[port4]─ Branch3 ─[port2..8]─  PLC27-32

200 PLCs:  DMZ ─ Root ─ Spine1 ─ Leaf1 ─ PLCs
                       ─ Spine2 ─ Leaf2 ─ PLCs
                       ...
```

Max per level: 13 children (14 usable ports minus 1 for uplink).
2-level max: 13 × 13 = 169 PLCs. 3-level max: 13³ = 2197 PLCs.
