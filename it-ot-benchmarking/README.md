# ICS Network Platform Benchmark

## Architecture

```
IT Network (192.168.1.0/24)        DMZ (172.16.0.0/24)        OT Network (10.0.0.0/16)

 M × Workstations (.20+) ─┐                                  ┌─ N × PLCs (10.0.1.x)
 1 × Monitor WS (.4) ─────┤                                  │   (Modbus/TCP, 10 regs)
 1 × Web Server (.2) ─────┼── IT-Switch ── Firewall ── Historian ── OT-Switch ──┤
 1 × FTP Server (.3) ─────┘   (OVS)      eth0/eth1/eth2  (MariaDB)   (OVS)     └─ 1 × SCADA (.0.2)
                                          .1.1/.0.1/.0.1   172.16.0.2              (polls PLCs @1s)
```

Traffic:
  - PLCs ← SCADA: Modbus/TCP poll every 1s
  - SCADA → Historian: MySQL INSERT every 30s (crosses OT→DMZ)
  - Monitor WS → Historian: MySQL SELECT every 30s (crosses IT→DMZ)
  - Workstations → Web Server: HTTP GET random pages (5-30s random)
  - Workstations → FTP Server: file download (60-120s random)

## Step 1: Build Docker Images (on your Mac)

```bash
cd ics-benchmark
export DHUB=YOUR_DOCKERHUB_USERNAME

docker build -t $DHUB/itot-plc:latest         ./plc
docker build -t $DHUB/itot-scada-v2:latest     ./scada
docker build -t $DHUB/itot-firewall:latest     ./firewall
docker build -t $DHUB/itot-historian:latest    ./historian
docker build -t $DHUB/itot-webserver:latest    ./webserver
docker build -t $DHUB/itot-ftpserver:latest    ./ftpserver
docker build -t $DHUB/itot-workstation:latest  ./workstation
```

## Step 2: Push to Docker Hub

```bash
for img in itot-plc itot-scada-v2 itot-firewall itot-historian itot-webserver itot-ftpserver itot-workstation; do
  docker push $DHUB/$img:latest
done
```

## Step 3: Pull on GNS3 VM + tag

```bash
ssh gns3@<vm-ip>
DHUB=YOUR_DOCKERHUB_USERNAME
for img in itot-plc itot-scada-v2 itot-firewall itot-historian itot-webserver itot-ftpserver itot-workstation; do
  docker pull $DHUB/$img:latest
  docker tag $DHUB/$img:latest $img:latest
done
```

## Step 4: GNS3 Setup

In GNS3: Edit → Preferences → Docker containers → your Open vSwitch template:
  - Set adapters to **256** (or however many you need)

The script auto-creates Docker templates for all 7 images. The firewall template
gets 3 adapters (IT/DMZ/OT).

## Step 5: Copy script to VM

```bash
scp run_ics_benchmark.py gns3@<vm-ip>:/home/gns3/
```

## Step 6: Quick test

```bash
python3 run_ics_benchmark.py --n-plcs 5 --n-workstations 5 --trials 1 --duration 60
```

## Step 7: Run scenarios

```bash
# Small
python3 run_ics_benchmark.py --n-plcs 5 --n-workstations 10 --trials 20 --label small-local

# Medium
python3 run_ics_benchmark.py --n-plcs 20 --n-workstations 50 --trials 20 --label medium-local

# Large
python3 run_ics_benchmark.py --n-plcs 100 --n-workstations 200 --trials 20 --label large-local

# Remote (Mac Studio)
python3 run_ics_benchmark.py --n-plcs 100 --n-workstations 200 --trials 20 \
  --gns3-host 192.168.1.50 --label large-remote
```

Logs saved automatically with descriptive filenames.

## Command-Line Options

| Flag | Default | Description |
|------|---------|-------------|
| --n-plcs | (required) | Number of OT PLCs |
| --n-workstations | (required) | Number of IT workstations |
| --trials | 20 | Number of independent trials |
| --duration | 180 | Seconds to run scenario before measuring latency |
| --poll-interval | 1.0 | SCADA → PLC poll interval (seconds) |
| --historian-push | 30 | SCADA → historian push interval (seconds) |
| --monitor-interval | 30 | Monitor WS → historian pull interval (seconds) |
| --gns3-host | localhost | GNS3 API host |
| --gns3-port | 80 | GNS3 API port |
| --switch-template | Open vSwitch | OVS template name in GNS3 |
| --switch-adapters | 256 | Max ports on OVS (just a template config) |
| --api-requests | 20 | Requests per endpoint for latency test |
| --telnet-requests | 10 | Telnet commands for console latency test |
| --label | (host IP) | Label for log filename |
