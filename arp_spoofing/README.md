# Scenario 1: ARP Spoofing — Man-in-the-Middle Attack

## Overview

In this scenario, you will perform a classic **ARP (Address Resolution Protocol) spoofing** attack on an IT network. ARP spoofing allows an attacker to intercept network traffic between two hosts by poisoning their ARP caches, effectively positioning themselves as a man-in-the-middle.

You will:
1. Build and deploy a simple IT network topology
2. Establish a baseline of normal network behavior
3. Execute an ARP spoofing attack to intercept traffic
4. Observe the attack's effects using Wireshark and command-line tools
5. Detect the attack by analyzing ARP tables and packet captures
6. Mitigate the attack using static ARP entries
7. Verify that the mitigation is effective

> **Difficulty:** ⭐ Beginner  
> **Estimated Time:** 45–60 minutes  
> **Network Layer:** IT

---

## Learning Objectives

By the end of this scenario, students will be able to:

- [ ] Explain how ARP works and why it is vulnerable to spoofing
- [ ] Execute an ARP spoofing attack using `arpspoof`
- [ ] Use Wireshark or `tcpdump` to identify ARP anomalies (duplicate MAC addresses, gratuitous ARP replies)
- [ ] Detect a man-in-the-middle attack by inspecting ARP tables
- [ ] Apply static ARP entries as a mitigation technique
- [ ] Discuss the limitations of static ARP and other potential defenses

---

## Background: How ARP Works

ARP maps IP addresses to MAC (hardware) addresses on a local network. When a host wants to communicate with another host on the same subnet, it broadcasts an ARP request: *"Who has IP X.X.X.X? Tell me your MAC address."* The target host replies with its MAC address, and the requesting host caches this mapping.

**The vulnerability:** ARP has **no authentication**. Any host can send unsolicited ARP replies (called *gratuitous ARP*), and other hosts will accept them without verification. An attacker can send fake ARP replies to poison the ARP cache of a victim, redirecting their traffic through the attacker's machine.

```
NORMAL:                              ATTACK:

Workstation ──── Switch ──── Server  Workstation ──── Switch ──── Server
    ARP: Server = AA:BB:CC              ARP: Server = [ATTACKER's MAC]
                                                  │
                                              Attacker
                                         (forwards traffic)
```

---

## Topology

Build the following topology using the **AE³GIS Topology Creator**.

### Nodes

| Node Name | Template | Layer | Role |
|-----------|----------|-------|------|
| **IT-Server** | Ubuntu / Workstation | IT | Web server (target) |
| **IT-Workstation** | Ubuntu / Workstation | IT | Legitimate client (victim) |
| **Attacker** | Ubuntu / Workstation | IT | Attacker machine |
| **IT-Switch** | Ethernet Switch | IT | Network switch connecting all nodes |

### Links

Connect all three hosts to the switch:

| Connection | Description |
|------------|-------------|
| IT-Server ↔ IT-Switch | Server connected to switch |
| IT-Workstation ↔ IT-Switch | Workstation connected to switch |
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
     │            │  │ station  │  │            │
     └────────────┘  └──────────┘  └────────────┘
```

<!-- TODO: Add screenshot of the topology as built in AE³GIS Topology Creator -->

### Building the Topology in AE³GIS

1. Open the **AE³GIS** web interface and navigate to the **Instructor** panel
2. Go to **Topologies** → **Create New Topology**
3. Set the project name (e.g., `arp-spoofing-lab`)
4. Add each node, selecting the appropriate GNS3 template and assigning all nodes to the **IT** layer
5. Create links between each host node and the IT-Switch
6. Save the topology
7. Deploy the topology and wait for all nodes to start

---

## Scripts Reference

The following scripts are provided in the [`scripts/`](scripts/) folder. When building the scenario in the **AE³GIS Scenario Editor**, upload each script as a **script step** targeting the appropriate node.

| Script | Target Node | Purpose |
|--------|-------------|---------|
| [`setup_server.sh`](scripts/setup_server.sh) | IT-Server | Installs and starts nginx web server |
| [`enable_forwarding.sh`](scripts/enable_forwarding.sh) | Attacker | Enables IP forwarding and installs attack tools |
| [`arp_spoof.sh`](scripts/arp_spoof.sh) | Attacker | Launches the ARP spoofing attack |
| [`capture_traffic.sh`](scripts/capture_traffic.sh) | Attacker | Captures intercepted HTTP traffic |
| [`static_arp.sh`](scripts/static_arp.sh) | IT-Workstation | Adds static ARP entries for mitigation |

---

## Building the Scenario in AE³GIS

Use the **Scenario Editor** to create a new scenario with alternating **markdown steps** (instructions) and **script steps** (executable scripts). Below is the recommended structure:

| Step # | Type | Content |
|--------|------|---------|
| 1 | Markdown | Phase 1 instructions (setup, discover IPs) |
| 2 | Script | `setup_server.sh` → IT-Server |
| 3 | Markdown | Instructions to discover IPs, verify connectivity, record ARP tables |
| 4 | Script | `enable_forwarding.sh` → Attacker |
| 5 | Markdown | Phase 2 instructions (attack explanation, what to observe) |
| 6 | Script | `arp_spoof.sh` → Attacker |
| 7 | Markdown | Phase 3 instructions (observe attack, check ARP tables, run Wireshark) |
| 8 | Script | `capture_traffic.sh` → Attacker |
| 9 | Markdown | Phase 4 instructions (detection techniques) |
| 10 | Markdown | Phase 5 instructions (mitigation explanation) |
| 11 | Script | `static_arp.sh` → IT-Workstation |
| 12 | Markdown | Phase 6 instructions (verify mitigation, cleanup, submit) |

---

## Step-by-Step Student Instructions

### Phase 1: Setup and Baseline

#### Step 1.1 — Deploy the Topology

1. In AE³GIS, go to your saved topology and click **Deploy**
2. Wait for all nodes to start (status indicators should turn green)
3. If you are a student, navigate to the **Scenarios** page and open this scenario

#### Step 1.2 — Set Up the Web Server

Run the **`setup_server.sh`** script on **IT-Server** via the AE³GIS scenario runner.

This installs nginx and creates a test web page.

#### Step 1.3 — Discover IP Addresses

On **each node**, open a terminal (via AE³GIS node console) and run:

```bash
ip addr show eth0
```

> **📋 Checkpoint:** Write down the IP address **and** MAC address of each node. You will need these throughout the lab.
>
> | Node | IP Address | MAC Address |
> |------|-----------|-------------|
> | IT-Server | __________ | __________ |
> | IT-Workstation | __________ | __________ |
> | Attacker | __________ | __________ |

#### Step 1.4 — Verify Connectivity

On **IT-Workstation**, test access to the web server:

```bash
curl http://<IT-Server-IP>
```

You should see the HTML page content. If not, check that all nodes are on the same subnet and the server is running.

#### Step 1.5 — Record Baseline ARP Tables

On **IT-Workstation**, record the current ARP table:

```bash
arp -a
```

On **IT-Server**, also check:

```bash
arp -a
```

> **📋 Checkpoint:** Note the MAC address associated with the IT-Server's IP address on the IT-Workstation. This is the **legitimate** MAC address. Write it down — you will compare this to the poisoned entry later.

#### Step 1.6 — Start a Packet Capture (Background)

On **IT-Workstation**, start a background ARP packet capture:

```bash
tcpdump -i eth0 arp -w /tmp/arp_capture.pcap &
```

> **💡 Tip:** Keep this running in the background throughout the lab. You'll analyze the captured ARP traffic later.

---

### Phase 2: Execute the ARP Spoofing Attack

#### Step 2.1 — Prepare the Attacker

Run the **`enable_forwarding.sh`** script on **Attacker** via the AE³GIS scenario runner.

This enables IP forwarding and installs `arpspoof` and `tcpdump`.

> **❓ Think About It:** Why is IP forwarding necessary for this attack? What would happen to the victim's traffic if forwarding were disabled?

#### Step 2.2 — Launch the ARP Spoof

Run the **`arp_spoof.sh`** script on **Attacker**. When prompted (or via the AE³GIS script parameters), provide:
- `VICTIM_IP` = IP of IT-Workstation
- `SERVER_IP` = IP of IT-Server

Example:
```bash
./arp_spoof.sh 192.168.1.10 192.168.1.1
```

You should see output indicating that spoofed ARP replies are being sent continuously.

> **⚠️ Important:** The script runs two `arpspoof` processes in the background — one for each direction. Both are needed for a complete man-in-the-middle.

---

### Phase 3: Observe the Attack

#### Step 3.1 — Check the Poisoned ARP Table

On **IT-Workstation**, check the ARP table:

```bash
arp -a
```

> **📋 Checkpoint:** Compare the MAC address for IT-Server's IP to what you recorded in Step 1.5.
>
> | | MAC Address for Server IP |
> |---|---|
> | **Before attack** | __________ (should be IT-Server's real MAC) |
> | **After attack** | __________ (should now be Attacker's MAC!) |
>
> **❓ Question:** What does this change mean? Where will IT-Workstation's traffic actually go now when it tries to reach IT-Server?

#### Step 3.2 — Intercept Traffic

Run the **`capture_traffic.sh`** script on **Attacker**:

```bash
./capture_traffic.sh <IT-Workstation-IP> <IT-Server-IP>
```

This starts listening for HTTP traffic flowing through the Attacker.

#### Step 3.3 — Generate Traffic to Intercept

On **IT-Workstation**, make several web requests:

```bash
curl http://<IT-Server-IP>
curl http://<IT-Server-IP>
```

> **📋 Checkpoint:** Go back to the Attacker's terminal. You should see the HTTP request and response content in plain text flowing through the Attacker's machine. **The attacker can now read all unencrypted traffic!**

#### Step 3.4 — Analyze ARP Traffic

On **IT-Workstation**, examine the ARP traffic you've been capturing:

```bash
# Stop the background tcpdump
kill %1 2>/dev/null

# Read the capture
tcpdump -r /tmp/arp_capture.pcap -n
```

> **📋 Checkpoint:** Look for these indicators of ARP spoofing:
> - **Gratuitous ARP replies** — Unsolicited ARP responses from the Attacker's MAC address
> - **Duplicate IP-to-MAC mappings** — The same IP address associated with two different MAC addresses
> - **High frequency of ARP replies** — `arpspoof` sends continuous replies to maintain the poisoned cache
>
> **❓ Question:** How could a network monitoring tool automatically detect this kind of anomaly?

---

### Phase 4: Detection Techniques

#### Step 4.1 — ARP Table Inspection

The simplest detection: compare current ARP entries against known-good values.

On **IT-Workstation**:
```bash
arp -a
```

Look for:
- Multiple IP addresses resolving to the **same MAC address** (the Attacker's)
- MAC addresses that don't match the known hardware addresses of your devices

#### Step 4.2 — Monitor ARP Traffic Volume

On **IT-Workstation**:
```bash
tcpdump -i eth0 arp -c 30
```

> **📋 Checkpoint:** In a normal network, ARP traffic is infrequent — only a few requests/replies per minute. During an active ARP spoofing attack, you'll see a **flood** of unsolicited ARP replies (one every 1–2 seconds). This high volume is a strong indicator.

---

### Phase 5: Mitigation

#### Step 5.1 — Stop the Attack (Temporarily)

On **Attacker**, stop the arpspoof processes:

```bash
killall arpspoof 2>/dev/null
```

On **IT-Workstation**, flush the ARP cache to remove poisoned entries:

```bash
ip -s -s neigh flush all
```

Verify the ARP table is now clean:
```bash
arp -a
```

#### Step 5.2 — Apply Static ARP Entries

Run the **`static_arp.sh`** script on **IT-Workstation**:

```bash
./static_arp.sh <IT-Server-IP> <IT-Server-REAL-MAC>
```

> **⚠️ Important:** Use the **real** MAC address you recorded in Step 1.5, not the spoofed one!

The script will display the updated ARP table. The entry should show as `PERM` (permanent).

> **💡 Tip:** In a real production environment, you would also set static entries on the IT-Server to protect traffic in both directions.

---

### Phase 6: Verify the Mitigation

#### Step 6.1 — Re-attempt the Attack

On **Attacker**, launch the ARP spoof again:

```bash
arpspoof -i eth0 -t <IT-Workstation-IP> <IT-Server-IP> &
```

#### Step 6.2 — Check ARP Table with Static Entry

On **IT-Workstation**:

```bash
arp -a
```

> **📋 Checkpoint:** The static entry should remain unchanged despite the spoofing attempt. The MAC address for IT-Server should still show the **real** MAC address, marked as `PERM`.

#### Step 6.3 — Verify Traffic is Normal

On **IT-Workstation**, access the web server:

```bash
curl http://<IT-Server-IP>
```

On **Attacker**, check if traffic is being intercepted — it should **not** be:

```bash
tcpdump -i eth0 -c 10 -n "host <IT-Workstation-IP> and host <IT-Server-IP> and port 80"
```

> **❓ Question:** Why does the static entry prevent the attack? What are the practical limitations of using static ARP entries in a large enterprise network with hundreds of devices?

---

### Phase 7: Cleanup and Submission

#### Step 7.1 — Stop All Attack Processes

On **Attacker**:
```bash
killall arpspoof 2>/dev/null
echo 0 > /proc/sys/net/ipv4/ip_forward
```

#### Step 7.2 — Submit Your Work

1. In AE³GIS, navigate to the **Telemetry** page
2. Click **Preview Logs** to review your command history
3. Verify that your key commands are captured (ARP inspections, attack commands, mitigation steps)
4. Click **Submit** to send your logs to the instructor

---

## Discussion Questions

After completing the lab, consider the following:

1. **Why is ARP vulnerable to spoofing?** What design decisions in the ARP protocol make this attack possible?
2. **What is the difference between ARP spoofing and ARP poisoning?** Are they the same thing?
3. **What other mitigations exist** beyond static ARP entries? Research: Dynamic ARP Inspection (DAI), 802.1X port-based authentication, ARP-Guard, VLAN segmentation.
4. **Would this attack work on a routed (Layer 3) network?** Why or why not?
5. **How does HTTPS protect against this type of MitM attack?** Would the attacker still see anything useful?
6. **In an ICS/OT environment**, what would be the impact of an ARP spoofing attack between a PLC and an HMI?

---

## Appendix: Troubleshooting

| Problem | Solution |
|---------|----------|
| `arpspoof: command not found` | Run `apt-get update && apt-get install -y dsniff` on the Attacker |
| Nodes can't ping each other | Verify all nodes are connected to the switch and on the same subnet |
| ARP table doesn't change after attack | Make sure `arpspoof` is running with the correct IPs and interface |
| `curl` times out during attack | Check that IP forwarding is enabled on Attacker (`cat /proc/sys/net/ipv4/ip_forward` should return `1`) |
| Static ARP entry isn't `PERM` | Try `ip neigh replace <IP> lladdr <MAC> dev eth0 nud permanent` instead |