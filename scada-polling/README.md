# IT/OT Network Scalability Test — Complete Guide

## What This Does

Automated scalability experiment for an IT/OT network topology. A SCADA server
polls N Modbus/TCP PLC simulators through a DMZ router. The test increases N
from 4 to 400, runs 3 trials at each scale, and reports performance metrics
with mean ± std. Stops automatically at saturation.

## Architecture

```
IT Network (192.168.1.0/24)              OT Network (10.0.0.0/16)

  ┌──────────┐      ┌──────────┐      ┌───────────────────────────┐
  │  SCADA   │      │   DMZ    │      │  PLC 1  (10.0.1.1)       │
  │  Server  │──────│  Router  │──────│  PLC 2  (10.0.1.2)       │
  │192.168.1.10│    │  .1.1 / │      │  ...                      │
  └──────────┘      │  10.0.0.1│      │  PLC N  (10.0.x.y)       │
                    └──────────┘      └───────────────────────────┘
```

Traffic: SCADA reads 10 Modbus holding registers from each PLC every 0.5s.
Request: 12 bytes. Response: 29 bytes. All traffic crosses the DMZ.

---

## PREREQUISITES

### On your Mac (local machine)

- Docker Desktop installed and running
- Docker Hub account (free)
- Terminal / shell access

Verify:
```bash
docker --version    # should show Docker version
docker login        # log in to Docker Hub
```

### On the GNS3 VM (inside VirtualBox)

- SSH access to the VM
- Docker available (comes with GNS3 VM)
- Python 3.6+ (comes with GNS3 VM's Ubuntu)
- iptables (comes with GNS3 VM)

Verify (SSH into the VM first):
```bash
# Find your VM's IP — shown on the GNS3 VM console screen
ssh gns3@<vm-ip>

# Check prerequisites
python3 --version   # need 3.6+
docker --version    # should work
docker ps           # should work without sudo (gns3 user is in docker group)
```

If `docker ps` needs sudo, fix it:
```bash
sudo usermod -aG docker gns3
# Then log out and back in
```

If python3 is missing (unlikely):
```bash
sudo apt update && sudo apt install -y python3
```

---

## STEP 1: Build Docker Images (on your Mac)

Download or create this project folder structure:
```
it-ot-lab/
├── plc/
│   ├── Dockerfile
│   └── plc_simulator.py
├── scada/
│   ├── Dockerfile
│   └── scada_poller.py
├── dmz/
│   ├── Dockerfile
│   └── dmz_setup.sh
└── run_scalability_test.py
```

Build all three images:
```bash
cd it-ot-lab

# Set your Docker Hub username
export DHUB=YOUR_DOCKERHUB_USERNAME

docker build -t $DHUB/itot-plc:latest    ./plc
docker build -t $DHUB/itot-scada:latest  ./scada
docker build -t $DHUB/itot-dmz:latest    ./dmz
```

---

## STEP 2: Push to Docker Hub (on your Mac)

```bash
docker push $DHUB/itot-plc:latest
docker push $DHUB/itot-scada:latest
docker push $DHUB/itot-dmz:latest
```

---

## STEP 3: Pull Images on GNS3 VM

SSH into the VM:
```bash
ssh gns3@<vm-ip>
```

Pull the images:
```bash
docker pull YOUR_DOCKERHUB_USERNAME/itot-plc:latest
docker pull YOUR_DOCKERHUB_USERNAME/itot-scada:latest
docker pull YOUR_DOCKERHUB_USERNAME/itot-dmz:latest
```

Tag them without the username prefix (so the script finds them):
```bash
docker tag YOUR_DOCKERHUB_USERNAME/itot-plc:latest   itot-plc:latest
docker tag YOUR_DOCKERHUB_USERNAME/itot-scada:latest  itot-scada:latest
docker tag YOUR_DOCKERHUB_USERNAME/itot-dmz:latest    itot-dmz:latest
```

Verify:
```bash
docker images | grep itot
# Should show all three images
```

---

## STEP 4: Copy the Test Script to the VM

From your Mac:
```bash
scp run_scalability_test.py gns3@<vm-ip>:/home/gns3/
```

Or, if SCP doesn't work, SSH in and paste the script:
```bash
ssh gns3@<vm-ip>
vi run_scalability_test.py
# Press 'i' for insert mode, paste the script, press Esc, type :wq
```

Make it executable:
```bash
chmod +x run_scalability_test.py
```

---

## STEP 5: Run the Experiment

### Quick test (1 scale, 1 trial, 1 minute)

Do this first to make sure everything works:
```bash
python3 run_scalability_test.py --scales 4 --trials 1 --duration 60
```

You should see:
- Preflight checks pass
- 4 PLCs start, boot times measured
- SCADA polls for 60 seconds
- Results table printed
- Everything cleaned up

### Full experiment

```bash
python3 run_scalability_test.py \
  --scales 4,8,16,32,64,100,150,200,250,300,350,400 \
  --trials 3 \
  --duration 180
```

This runs automatically until saturation or completion. Estimated time: ~2-3 hours.

### If you want to use your Docker Hub prefix directly:

```bash
python3 run_scalability_test.py --image-prefix YOUR_DOCKERHUB_USERNAME/
```

---

## STEP 6: Copy Results

The script prints all results directly to your SSH terminal. No files to
download. Just copy the tables from your terminal into your paper.

You'll get:

**Main results table:**
```
  PLCs │ Trials │  RTT avg(ms) │  RTT p95(ms) │     Throughput │  Success% │    Req/min │    Boot(s) │   PLC CPU% │    PLC Mem │  Host Mem%
  ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
     4 │   3/3  │     1.2±0.1  │     2.1±0.3  │   928±12 B/s   │  100±0.0  │  480±5.2   │   2.1±0.3  │   0.3±0.1  │   12±1MB   │  45.2±0.5
     8 │   3/3  │     1.8±0.2  │     3.0±0.4  │  1840±25 B/s   │  100±0.0  │  960±8.1   │   2.4±0.2  │   0.3±0.0  │   12±1MB   │  47.1±0.3
   ...
```

**Per-container resource table:**
```
  PLCs │     PLC CPU% │  PLC Mem(MB) │   SCADA CPU% │    SCADA Mem │     DMZ CPU% │      DMZ Mem
  ─────────────────────────────────────────────────────────────────────────────────────────────
     4 │      0.3±0.1 │     12.5±0.5 │      1.2±0.3 │     15.2MB   │      0.1±0.0 │      5.1MB
```

**Saturation detection:**
```
  *** SATURATION DETECTED at 256 PLCs: success rate 87.3% < 90% ***
  Saturation point: between 200 and 256 PLCs
```

---

## What the Reviewer Gets

| Reviewer concern | How it's addressed |
|---|---|
| Per-container resource footprint | CPU% and memory per PLC, SCADA, DMZ — collected via docker stats every 10s |
| Workload characterization | Modbus/TCP, 10 registers, 12B request / 29B response, 0.5s poll interval |
| Repeat trials / variance | 3 trials per scale, reported as mean ± std |
| Boot-time metrics under load | Time from docker run to first successful TCP connect on port 502 |
| Latency | RTT per poll: avg, min, max, p95 |
| Throughput | Bytes/sec measured at SCADA |
| Network performance at scale | Auto-scales to saturation point with detection |

---

## Troubleshooting

**"Docker is not accessible"**
→ `sudo usermod -aG docker gns3` then re-login

**"Image not found"**
→ `docker images | grep itot` — if missing, pull again

**PLCs fail to boot (timeout)**
→ Check: `docker logs itot-plc-1` for errors. Usually means pymodbus failed.

**All trials fail at a scale**
→ Likely OOM. Check `free -m`. Reduce scales or close other applications.

**Cross-network routing doesn't work**
→ The script disables Docker isolation via iptables. If running as non-root,
  you may need: `sudo python3 run_scalability_test.py`

**Script interrupted (Ctrl+C)**
→ Containers may be left running. Clean up manually:
  `docker rm -f $(docker ps -a -q --filter name=itot-)`
