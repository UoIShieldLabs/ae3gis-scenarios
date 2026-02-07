# Scenario 2: Denial of Service (DoS) — Availability Attack

## Overview

In this scenario, you will explore multiple **Denial of Service (DoS)** attack vectors against an IT web server. DoS attacks aim to make a service unavailable to legitimate users by overwhelming the target with traffic or exploiting resource exhaustion vulnerabilities.

You will:
1. Establish baseline server performance metrics
2. Execute three different DoS attack types: **SYN flood**, **ICMP flood**, and **UDP flood**
3. Measure the impact on service availability from a legitimate client
4. Detect each attack type using network monitoring tools
5. Apply kernel-level and firewall-based mitigations
6. Verify that mitigations restore service availability

> **Difficulty:** ⭐⭐ Intermediate  
> **Estimated Time:** 60–90 minutes  
> **Network Layer:** IT

---

## Learning Objectives

By the end of this scenario, students will be able to:

- [ ] Explain how SYN flood, ICMP flood, and UDP flood attacks work
- [ ] Measure the impact of a DoS attack on service availability (response times, packet loss)
- [ ] Detect an active DoS attack using `tcpdump`, `netstat`/`ss`, and Wireshark
- [ ] Implement SYN cookies as a kernel-level defense
- [ ] Configure `iptables` rate-limiting rules to mitigate flood attacks
- [ ] Compare the effectiveness of different attack types and their mitigations

---

## Background: DoS Attack Types

### SYN Flood
Exploits the TCP three-way handshake. The attacker sends massive numbers of SYN packets but never completes the handshake (no ACK). The server allocates resources for each half-open connection until its connection table is exhausted.

```
Attacker                          Server
   │── SYN ──────────────────────►│  (server allocates resources)
   │── SYN ──────────────────────►│  (server allocates more)
   │── SYN ──────────────────────►│  (server allocates more)
   │── SYN ──────────────────────►│  (connection table full!)
   │     ... thousands more ...   │  (legitimate clients rejected)
```

### ICMP Flood (Ping Flood)
Sends a massive volume of ICMP Echo Request packets. The target must process and respond to each one, consuming CPU cycles and bandwidth.

### UDP Flood
Sends large volumes of UDP packets to the target. Since UDP is connectionless, the target must process each packet to determine if any application is listening, consuming resources.

---

## Topology

This scenario uses the **same topology as the ARP Spoofing scenario**. You can reuse that topology or create a new one.

### Nodes

| Node Name | Template | Layer | Role |
|-----------|----------|-------|------|
| **IT-Server** | Ubuntu / Workstation | IT | Web server (attack target) |
| **IT-Workstation** | Ubuntu / Workstation | IT | Legitimate client (measures impact) |
| **Attacker** | Ubuntu / Workstation | IT | Attacker machine (launches floods) |
| **IT-Switch** | Ethernet Switch | IT | Network switch connecting all nodes |

### Links

| Connection | Description |
|------------|-------------|
| IT-Server ↔ IT-Switch | Server connected to switch |
| IT-Workstation ↔ IT-Switch | Legitimate client connected to switch |
| Attacker ↔ IT-Switch | Attacker connected to switch |

### Network Diagram

```
                    ┌──────────────┐
                    │  IT-Switch   │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └────────┐
              │            │            │
     ┌────────┴───┐  ┌────┴─────┐  ┌───┴────────┐
     │ IT-Server  │  │ IT-Work  │  │  Attacker  │
     │ (target)   │  │ station  │  │  (floods)  │
     └────────────┘  └──────────┘  └────────────┘
```

<!-- TODO: Add screenshot of the topology as built in AE³GIS Topology Creator (can reuse ARP topology screenshot if identical) -->

### Building the Topology in AE³GIS

1. You may reuse the topology from the **ARP Spoofing** scenario if the nodes are the same
2. Otherwise, create a new topology following the same steps: 3 hosts + 1 switch, all on the **IT** layer
3. Deploy the topology and ensure all nodes are running

---

## Scripts Reference

The following scripts are provided in the [`scripts/`](scripts/) folder. Upload them as **script steps** when building the scenario in the AE³GIS Scenario Editor.

| Script | Target Node | Purpose |
|--------|-------------|---------|
| [`setup_server.sh`](scripts/setup_server.sh) | IT-Server | Installs nginx and monitoring tools |
| [`syn_flood.sh`](scripts/syn_flood.sh) | Attacker | Launches a TCP SYN flood attack |
| [`icmp_flood.sh`](scripts/icmp_flood.sh) | Attacker | Launches an ICMP ping flood attack |
| [`udp_flood.sh`](scripts/udp_flood.sh) | Attacker | Launches a UDP flood attack |
| [`detect_attack.sh`](scripts/detect_attack.sh) | IT-Server | Runs detection checks for active DoS attacks |
| [`mitigate_rate_limit.sh`](scripts/mitigate_rate_limit.sh) | IT-Server | Applies iptables rate-limiting and SYN cookies |

---

## Building the Scenario in AE³GIS

Recommended scenario structure using the **AE³GIS Scenario Editor**:

| Step # | Type | Content |
|--------|------|---------|
| 1 | Markdown | Phase 1 instructions (deploy, setup, baseline) |
| 2 | Script | `setup_server.sh` → IT-Server |
| 3 | Markdown | Baseline measurement instructions |
| 4 | Markdown | Phase 2 — SYN Flood explanation |
| 5 | Script | `syn_flood.sh` → Attacker |
| 6 | Markdown | Instructions to observe impact and detect |
| 7 | Script | `detect_attack.sh` → IT-Server |
| 8 | Markdown | Stop SYN flood, Phase 3 — ICMP Flood explanation |
| 9 | Script | `icmp_flood.sh` → Attacker |
| 10 | Markdown | Observe and detect ICMP flood |
| 11 | Markdown | Stop ICMP flood, Phase 4 — UDP Flood explanation |
| 12 | Script | `udp_flood.sh` → Attacker |
| 13 | Markdown | Observe and detect UDP flood |
| 14 | Markdown | Phase 5 — Mitigation explanation |
| 15 | Script | `mitigate_rate_limit.sh` → IT-Server |
| 16 | Markdown | Verify mitigation, cleanup, submit |

---

## Step-by-Step Student Instructions

### Phase 1: Setup and Baseline

#### Step 1.1 — Deploy the Topology

1. In AE³GIS, deploy your topology and wait for all nodes to start
2. Navigate to the **Scenarios** page and open this scenario

#### Step 1.2 — Set Up the Web Server

Run the **`setup_server.sh`** script on **IT-Server** via the AE³GIS scenario runner.

#### Step 1.3 — Discover IP Addresses

On **each node**, determine the IP address:

```bash
ip addr show eth0
```

> **📋 Checkpoint:** Record the IP address of each node:
>
> | Node | IP Address |
> |------|-----------|
> | IT-Server | __________ |
> | IT-Workstation | __________ |
> | Attacker | __________ |

#### Step 1.4 — Measure Baseline Performance

On **IT-Workstation**, measure the server's normal response time:

```bash
# Single request with timing
curl -o /dev/null -s -w "Response time: %{time_total}s\n" http://<IT-Server-IP>

# 5 consecutive requests to establish a baseline average
echo "=== Baseline Response Times ==="
for i in $(seq 1 5); do
    TIME=$(curl -o /dev/null -s -w "%{time_total}" --max-time 5 http://<IT-Server-IP>)
    echo "  Request $i: ${TIME}s"
    sleep 1
done
```

Also measure baseline ping latency:

```bash
ping -c 10 <IT-Server-IP>
```

> **📋 Checkpoint:** Record the baseline metrics:
>
> | Metric | Baseline Value |
> |--------|---------------|
> | Average HTTP response time | __________ seconds |
> | Average ping RTT | __________ ms |
> | Ping packet loss | __________ % |
>
> You'll compare these to the values during an active attack.

---

### Phase 2: SYN Flood Attack

#### Step 2.1 — Understand the Attack

A SYN flood exploits the TCP three-way handshake. The attacker sends thousands of SYN packets per second. The server responds with SYN-ACK and waits for the final ACK that never comes. Each pending connection consumes server memory until the connection table is full.

#### Step 2.2 — Launch the SYN Flood

Run the **`syn_flood.sh`** script on **Attacker**:

```bash
./syn_flood.sh <IT-Server-IP>
```

> **⚠️ Note:** The flood runs until you press `Ctrl+C`. Keep it running while you observe the impact.

#### Step 2.3 — Measure Impact (While Attack is Running)

On **IT-Workstation**, measure the degraded performance:

```bash
echo "=== Response Times During SYN Flood ==="
for i in $(seq 1 5); do
    TIME=$(curl -o /dev/null -s -w "%{time_total}" --max-time 10 http://<IT-Server-IP> 2>&1)
    echo "  Request $i: ${TIME}s"
    sleep 1
done
```

```bash
ping -c 10 <IT-Server-IP>
```

> **📋 Checkpoint:** Compare with your baseline:
>
> | Metric | Baseline | During Attack |
> |--------|----------|--------------|
> | HTTP response time | __________ | __________ |
> | Ping RTT | __________ | __________ |
> | Packet loss | __________ | __________ |
>
> You should see significantly higher response times, timeouts, and/or packet loss.

#### Step 2.4 — Detect the SYN Flood

On **IT-Server**, run the **`detect_attack.sh`** script:

```bash
./detect_attack.sh
```

Also run these commands manually to understand what each check does:

```bash
# Count half-open connections (SYN_RECV state)
netstat -an | grep SYN_RECV | wc -l
# Normal: 0-2. During SYN flood: dozens or hundreds.

# Watch the flood in real-time
tcpdump -i eth0 'tcp[tcpflags] & tcp-syn != 0' -c 20
```

> **📋 Checkpoint:** How many `SYN_RECV` connections did you see? In a `tcpdump` capture of 20 packets, how many were SYN packets?

#### Step 2.5 — Open Wireshark (If Available)

If your GNS3 setup supports Wireshark packet capture on the switch or server:

1. Right-click on the link between IT-Switch and IT-Server
2. Select **Start Capture** → **Wireshark**
3. Apply display filter: `tcp.flags.syn == 1 && tcp.flags.ack == 0`

<!-- TODO: Add screenshot of Wireshark showing SYN flood traffic pattern -->

> **📋 Checkpoint:** What patterns do you observe? Notice the massive number of SYN packets with different (or same) source ports but no corresponding ACK packets.

#### Step 2.6 — Stop the SYN Flood

On **Attacker**, press `Ctrl+C` to stop the `hping3` process, or:

```bash
killall hping3 2>/dev/null
```

Wait 30–60 seconds for the server's half-open connections to time out, then verify recovery:

```bash
# On IT-Workstation
curl -o /dev/null -s -w "Response time: %{time_total}s\n" http://<IT-Server-IP>
```

---

### Phase 3: ICMP Flood Attack

#### Step 3.1 — Launch the ICMP Flood

Run the **`icmp_flood.sh`** script on **Attacker**:

```bash
./icmp_flood.sh <IT-Server-IP>
```

#### Step 3.2 — Measure Impact

On **IT-Workstation**:

```bash
echo "=== Response Times During ICMP Flood ==="
for i in $(seq 1 5); do
    TIME=$(curl -o /dev/null -s -w "%{time_total}" --max-time 10 http://<IT-Server-IP> 2>&1)
    echo "  Request $i: ${TIME}s"
    sleep 1
done
```

> **❓ Question:** Is the impact of the ICMP flood on HTTP response times more or less severe than the SYN flood? Why might this be the case?

#### Step 3.3 — Detect the ICMP Flood

On **IT-Server**:

```bash
# Watch ICMP traffic
tcpdump -i eth0 icmp -c 20

# Count ICMP packets per second
echo "Counting ICMP packets for 5 seconds..."
timeout 5 tcpdump -i eth0 icmp 2>/dev/null | wc -l
```

> **📋 Checkpoint:** How many ICMP packets per second is the server receiving? In normal operation, you'd expect very few (if any).

#### Step 3.4 — Stop the ICMP Flood

On **Attacker**:
```bash
killall hping3 2>/dev/null
```

---

### Phase 4: UDP Flood Attack

#### Step 4.1 — Launch the UDP Flood

Run the **`udp_flood.sh`** script on **Attacker**:

```bash
./udp_flood.sh <IT-Server-IP>
```

#### Step 4.2 — Observe and Detect

On **IT-Workstation**, check HTTP availability:

```bash
curl -o /dev/null -s -w "Response time: %{time_total}s\n" --max-time 10 http://<IT-Server-IP>
```

On **IT-Server**, observe the flood:

```bash
# Watch UDP traffic
tcpdump -i eth0 udp -c 20

# Check for ICMP Port Unreachable responses (server responds to each UDP packet)
tcpdump -i eth0 'icmp[icmptype] == 3' -c 10
```

> **❓ Question:** Why does the server send ICMP "Port Unreachable" messages in response to UDP flood packets? How does this amplify the resource consumption?

#### Step 4.3 — Stop the UDP Flood

On **Attacker**:
```bash
killall hping3 2>/dev/null
```

---

### Phase 5: Mitigation

#### Step 5.1 — Apply Mitigations

Run the **`mitigate_rate_limit.sh`** script on **IT-Server**:

```bash
./mitigate_rate_limit.sh
```

This script applies three layers of defense:
1. **SYN cookies** — Kernel-level defense that doesn't allocate resources for SYN requests until the handshake is completed
2. **SYN rate limiting** — `iptables` rule limiting SYN packets to 10/sec with a burst of 20
3. **ICMP rate limiting** — `iptables` rule limiting ICMP to 5/sec
4. **UDP rate limiting** — `iptables` rule limiting UDP on port 80 to 10/sec

#### Step 5.2 — Verify iptables Rules

On **IT-Server**, examine the applied rules:

```bash
iptables -L -n -v
```

> **📋 Checkpoint:** You should see ACCEPT rules with rate limits and DROP rules for each protocol. Examine the packet counters — they should be at zero (will increase once an attack starts).

---

### Phase 6: Test Mitigations Under Attack

#### Step 6.1 — Re-launch SYN Flood

On **Attacker**:

```bash
./syn_flood.sh <IT-Server-IP>
```

#### Step 6.2 — Measure Performance with Mitigations Active

On **IT-Workstation**:

```bash
echo "=== Response Times During SYN Flood (WITH MITIGATIONS) ==="
for i in $(seq 1 5); do
    TIME=$(curl -o /dev/null -s -w "%{time_total}" --max-time 10 http://<IT-Server-IP> 2>&1)
    echo "  Request $i: ${TIME}s"
    sleep 1
done
```

> **📋 Checkpoint:** Compare all three measurements:
>
> | Metric | Baseline | Under Attack (no mitigation) | Under Attack (with mitigation) |
> |--------|----------|------------------------------|-------------------------------|
> | HTTP Response Time | __________ | __________ | __________ |
>
> The mitigated response time should be close to the baseline.

#### Step 6.3 — Check Drop Counters

On **IT-Server**:

```bash
iptables -L -n -v
```

> **📋 Checkpoint:** Look at the packet and byte counters on the DROP rules. How many packets have been dropped? This shows the mitigation is actively blocking flood traffic while allowing legitimate requests through.

#### Step 6.4 — Stop the Attack

On **Attacker**:
```bash
killall hping3 2>/dev/null
```

---

### Phase 7: Cleanup and Submission

#### Step 7.1 — Remove Mitigation Rules

On **IT-Server** (to reset for other labs):
```bash
iptables -F
echo 0 > /proc/sys/net/ipv4/tcp_syncookies
echo "[+] All iptables rules flushed and SYN cookies disabled."
```

#### Step 7.2 — Stop All Attack Processes

On **Attacker**:
```bash
killall hping3 2>/dev/null
```

#### Step 7.3 — Submit Your Work

1. In AE³GIS, navigate to the **Telemetry** page
2. Click **Preview Logs** to review your command history
3. Verify that your key commands are captured (baseline measurements, attacks, detection, mitigation)
4. Click **Submit** to send your logs to the instructor

---

## Discussion Questions

After completing the lab, consider the following:

1. **Which attack type had the greatest impact** on HTTP availability? Why?
2. **What is the difference between a DoS and a DDoS attack?** How would mitigations differ?
3. **Explain how SYN cookies work.** Why don't they require connection table entries?
4. **What are the trade-offs of rate limiting?** Could it affect legitimate users during high-traffic events?
5. **What other mitigations exist** beyond what was covered? Research: `fail2ban`, CDN/cloud scrubbing, BGP blackholing, anycast.
6. **In an ICS/OT environment**, what would be the impact of a DoS attack on a PLC or SCADA server? Could it cause physical damage?
7. **Why is `--rand-source` significant** for SYN floods? How does source IP randomization affect detection and mitigation?

---

## Appendix: Comparing Attack Types

| Attack Type | Protocol | Target Resource | Difficulty to Execute | Difficulty to Mitigate |
|-------------|----------|----------------|----------------------|----------------------|
| SYN Flood | TCP | Connection table (memory) | Easy | Moderate (SYN cookies help) |
| ICMP Flood | ICMP | CPU, bandwidth | Easy | Easy (block/rate-limit ICMP) |
| UDP Flood | UDP | CPU, bandwidth | Easy | Moderate (application-dependent) |

---

## Appendix: Troubleshooting

| Problem | Solution |
|---------|----------|
| `hping3: command not found` | Run `apt-get update && apt-get install -y hping3` on the Attacker |
| SYN flood has no visible impact | The container may have very low resource limits; try increasing the flood rate or reducing server resources |
| `iptables: command not found` | Run `apt-get install -y iptables` on IT-Server |
| `curl` works fine during flood | Some container setups handle floods efficiently; try `--rand-source` flag with hping3, or increase payload size |
| Mitigation blocks legitimate traffic | Adjust the rate limits in `mitigate_rate_limit.sh` (increase `--limit` and `--limit-burst` values) |