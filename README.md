# AE³GIS Cybersecurity Scenarios

A collection of hands-on cybersecurity lab scenarios designed for the [AE³GIS](https://github.com/your-org/ae3gis) (Agile Emulated Educational Environment for Guided Industrial Security Training) platform. Each scenario guides students through building network topologies, deploying services, executing real attacks, observing their effects, and applying mitigations — all within emulated GNS3 environments managed by AE³GIS.

---

## Scenarios Overview

| # | Scenario | Network Layer | Attack Type | Difficulty | Folder |
|---|----------|---------------|-------------|------------|--------|
| 1 | **ARP Spoofing** | IT | Man-in-the-Middle | ⭐ Beginner | [`arp_spoofing/`](arp_spoofing/) |
| 2 | **Denial of Service (DoS)** | IT | Availability Attack | ⭐⭐ Intermediate | [`dos/`](dos/) |
| 3 | **Stuxnet (ICS Attack)** | OT / Field | PLC Logic Manipulation | ⭐⭐⭐ Advanced | [`stuxnet/`](stuxnet/) |

---

## How These Scenarios Work

Each scenario in this repository is designed to be used with the **AE³GIS platform**. The general workflow is:

```
┌────────────────────────────────────────────────────────────────────┐
│  1. BUILD TOPOLOGY     Use AE³GIS Topology Creator to define      │
│                        nodes, links, and network layers            │
├────────────────────────────────────────────────────────────────────┤
│  2. CREATE SCENARIO    Use AE³GIS Scenario Editor to build a      │
│                        step-by-step lab with markdown + scripts    │
├────────────────────────────────────────────────────────────────────┤
│  3. DEPLOY             Deploy the topology to GNS3 via AE³GIS     │
│                        and start all nodes                         │
├────────────────────────────────────────────────────────────────────┤
│  4. EXECUTE            Students follow scenario steps, run         │
│                        scripts on nodes, observe results           │
├────────────────────────────────────────────────────────────────────┤
│  5. LOG & SUBMIT       Enable telemetry logging, then submit       │
│                        command history for instructor review       │
└────────────────────────────────────────────────────────────────────┘
```

### What's in Each Scenario Folder

- **`README.md`** — Detailed walkthrough with topology description, learning objectives, step-by-step student instructions, and checkpoint tasks
- **`scripts/`** (or deployment subfolders) — Small, focused shell scripts to be uploaded as scenario script steps in AE³GIS. Each script performs a single task; students are guided to run them, inspect results, and answer questions between steps

### Key Principles

- **Interactive, not automated**: Scripts are intentionally small. Students must observe outputs, check Wireshark captures, compare ARP tables, measure response times, and think critically between each step.
- **AE³GIS-native**: Topologies are built using the AE³GIS Topology Creator. Scenarios are assembled in the AE³GIS Scenario Editor with markdown instructions and script steps.
- **Instructor flexibility**: The READMEs provide a complete reference. Instructors can adapt, reorder, or extend steps when building their AE³GIS scenarios.

---

## Prerequisites

Before using these scenarios, ensure the following:

### Platform Requirements
- **AE³GIS** platform running (frontend + backend)
- **GNS3 Server** accessible and configured in AE³GIS settings
- Network templates/images loaded in GNS3 (Ubuntu containers, switches, etc.)

### Student Requirements
- Basic familiarity with the AE³GIS interface (topology viewer, scenario runner)
- Basic Linux command-line skills
- Understanding of fundamental networking concepts (IP addressing, MAC addresses, ARP, TCP/IP)

### Recommended GNS3 Templates
The scenarios reference generic node names. Map them to whatever Docker/VM templates you have in your GNS3 environment:

| Scenario Node | Suggested GNS3 Template | Purpose |
|---------------|------------------------|---------|
| Workstation / Client | Ubuntu Docker | General-purpose endpoint |
| Server | Ubuntu Docker | Web server, target host |
| Attacker | Kali Linux or Ubuntu Docker | Attack tools pre-installed |
| Switch | Open vSwitch or Ethernet Switch | L2 switching |
| PLC | OpenPLC Docker | Programmable Logic Controller |
| HMI | ScadaBR Docker | Human-Machine Interface |

---

## Scenario Summaries

### 1. ARP Spoofing (`arp_spoofing/`)

Students perform a classic ARP spoofing man-in-the-middle attack on an IT network. They learn to intercept traffic between a server and a workstation, observe the attack in Wireshark, and apply mitigations using static ARP entries.

**Key learning outcomes:**
- Understand how ARP works and its weaknesses
- Execute and observe an ARP spoofing attack
- Detect ARP anomalies using packet captures
- Mitigate using static ARP table entries

👉 [Go to ARP Spoofing Scenario](arp_spoofing/)

---

### 2. Denial of Service (`dos/`)

Students explore multiple DoS attack vectors (SYN flood, ICMP flood, UDP flood) against a web server. They measure the impact on service availability, detect attacks using network analysis tools, and implement kernel-level and firewall-based mitigations.

**Key learning outcomes:**
- Understand different DoS attack mechanisms
- Measure attack impact on service availability
- Detect floods using `tcpdump`, `netstat`, and Wireshark
- Mitigate using SYN cookies and `iptables` rate limiting

👉 [Go to DoS Scenario](dos/)

---

### 3. Stuxnet — ICS Attack Simulation (`stuxnet/`)

Students deploy a simulated industrial control system (PLC + HMI controlling a motor) and then deploy a Stuxnet-inspired attack that manipulates the PLC logic. The attack creates a deception layer — the HMI shows normal motor operation while the physical motor is being destructively oscillated.

**Key learning outcomes:**
- Understand ICS/SCADA architecture (PLC, HMI, Modbus)
- Deploy and configure an OpenPLC with IEC 61131-3 Structured Text
- Deploy and configure a ScadaBR HMI dashboard
- Understand the Stuxnet attack pattern (man-in-the-middle on process data)
- Detect discrepancies between reported and actual process values

👉 [Go to Stuxnet Scenario](stuxnet/)

---

## Repository Structure

```
ae3gis-scenarios/
├── README.md                        # This file
├── AE3GIS_reference.md              # AE³GIS platform reference
│
├── arp_spoofing/
│   ├── README.md                    # Full scenario walkthrough
│   └── scripts/                     # Upload these as AE³GIS script steps
│       ├── setup_server.sh
│       ├── enable_forwarding.sh
│       ├── arp_spoof.sh
│       ├── capture_traffic.sh
│       └── static_arp.sh
│
├── dos/
│   ├── README.md                    # Full scenario walkthrough
│   └── scripts/                     # Upload these as AE³GIS script steps
│       ├── setup_server.sh
│       ├── syn_flood.sh
│       ├── icmp_flood.sh
│       ├── udp_flood.sh
│       ├── detect_attack.sh
│       └── mitigate_rate_limit.sh
│
└── stuxnet/
    ├── README.md                    # Full scenario walkthrough
    ├── deploy_plc/                  # PLC deployment scripts
    │   ├── deploy_motor_plc.sh
    │   ├── motor.st
    │   └── motor_psm.py
    ├── deploy_hmi/                  # HMI deployment scripts
    │   ├── deploy_hmi.sh
    │   └── motor_hmi.json
    ├── deploy_stuxnet/              # Stuxnet payload scripts
    │   ├── deploy_stuxnet.sh
    │   └── motor_stuxnet_psm.py
    └── motor_plc_stuxnet/           # PLC project source (reference)
        ├── beremiz.xml
        ├── motor.st
        └── plc.xml
```

---

## Contributing

To add a new scenario:

1. Create a new folder with a descriptive name (e.g., `sql_injection/`)
2. Add a `README.md` following the structure of existing scenarios
3. Add small, focused scripts in a `scripts/` subfolder
4. Update this root README with the new scenario entry

---

## License

This project is part of the AE³GIS educational platform. See the main AE³GIS repository for license details.
