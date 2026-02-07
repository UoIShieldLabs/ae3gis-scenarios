# Scenario 3: Stuxnet — Industrial Control System Attack Simulation

## Overview

In this advanced scenario, you will deploy a simulated **Industrial Control System (ICS)** — a PLC controlling a motor via a SCADA HMI — and then execute a **Stuxnet-inspired attack** that manipulates the PLC's process logic. The attack creates a **deception layer**: the HMI dashboard shows the operator that the motor is running normally, while in reality the motor is being destructively oscillated between start and stop at high frequency.

This scenario demonstrates the most dangerous class of cyberattacks — those that **lie to the operator** while causing physical damage to industrial equipment.

You will:
1. Build and deploy an OT (Operational Technology) network topology
2. Deploy a PLC running motor control logic (IEC 61131-3 Structured Text)
3. Deploy an HMI (ScadaBR) to monitor and control the motor
4. Verify normal motor operation via the HMI dashboard
5. Inspect Modbus communication between the PLC and HMI
6. Deploy the Stuxnet payload that manipulates the PLC's hardware abstraction layer
7. Observe the deception — the HMI shows normal operation while the real motor is under attack
8. Detect the attack by analyzing Modbus register discrepancies

> **Difficulty:** ⭐⭐⭐ Advanced  
> **Estimated Time:** 90–120 minutes  
> **Network Layer:** OT / Field

---

## Learning Objectives

By the end of this scenario, students will be able to:

- [ ] Describe the components of an ICS/SCADA system (PLC, HMI, Modbus protocol)
- [ ] Deploy and configure an OpenPLC with IEC 61131-3 Structured Text logic
- [ ] Deploy and configure a ScadaBR HMI dashboard with Modbus data points
- [ ] Explain how Modbus TCP communication works between PLCs and HMIs
- [ ] Describe the Stuxnet attack pattern: manipulation of process data with operator deception
- [ ] Detect a Stuxnet-style attack by comparing reported vs. actual process values
- [ ] Discuss the implications of cyberattacks on physical industrial processes

---

## Background

### What Was Stuxnet?

**Stuxnet** (discovered in 2010) was the world's first known cyberweapon designed to cause physical destruction. It targeted Iran's Natanz uranium enrichment facility, specifically the Siemens S7-300 PLCs controlling centrifuge motors.

The attack was revolutionary because:
1. **It manipulated the physical process** — It changed the centrifuge motor speeds to cause mechanical damage
2. **It deceived the operators** — It replayed normal sensor readings to the HMI while the actual process was under attack
3. **The operators saw nothing wrong** — Their dashboards showed normal operation while centrifuges were being destroyed

### How This Simulation Works

This lab recreates the core Stuxnet concept in a simplified environment:

```
┌─────────────────────────────────────────────────────────────────┐
│                    NORMAL OPERATION                              │
│                                                                 │
│  Operator ──► HMI ──── Modbus ────► PLC ──────► Motor          │
│  (sees RPM)  (ScadaBR)   TCP      (OpenPLC)   (simulated)     │
│                                                                 │
│  The HMI shows target_freq=60Hz, motor_rpm=1775                │
│  The motor actually runs at 1775 RPM — everything matches      │
├─────────────────────────────────────────────────────────────────┤
│                    STUXNET ATTACK                                │
│                                                                 │
│  Operator ──► HMI ──── Modbus ────► PLC ──┬──► "Visible" Motor │
│  (sees 1775 RPM, normal)                  │    (fake, stable)  │
│                                           │                    │
│                                           └──► "True" Motor    │
│                                                (oscillating    │
│                                                 0↔120Hz!)      │
│                                                                 │
│  The HMI shows target_freq=60Hz, motor_rpm=1775 (FAKE)        │
│  The real motor oscillates violently between 0 and 3546 RPM    │
└─────────────────────────────────────────────────────────────────┘
```

The attack works by replacing the PLC's **Hardware Abstraction Layer** (called the PSM — Python SubModule in OpenPLC) with a malicious version that:
- Maintains a **"visible" motor simulation** that reports normal values to the HMI
- Runs a **"true" motor simulation** that oscillates the motor destructively
- The operator sees normal readings and has no reason to suspect anything is wrong

---

## Topology

Build the following topology using the **AE³GIS Topology Creator**.

### Nodes

| Node Name | Template | Layer | Role |
|-----------|----------|-------|------|
| **PLC** | OpenPLC Docker | OT | Programmable Logic Controller running motor control |
| **HMI** | ScadaBR Docker | OT | Human-Machine Interface (operator dashboard) |
| **Engineering-Workstation** | Ubuntu / Workstation | OT | Used to deploy configurations and run attacks |
| **OT-Switch** | Ethernet Switch | OT | Network switch connecting OT devices |

### Links

| Connection | Description |
|------------|-------------|
| PLC ↔ OT-Switch | PLC connected to OT network |
| HMI ↔ OT-Switch | HMI connected to OT network |
| Engineering-Workstation ↔ OT-Switch | Engineer's workstation on OT network |

### Network Diagram

```
                    ┌──────────────┐
                    │  OT-Switch   │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └────────┐
              │            │            │
     ┌────────┴───┐  ┌────┴─────┐  ┌───┴────────────┐
     │    PLC     │  │   HMI    │  │  Engineering    │
     │ (OpenPLC)  │  │(ScadaBR) │  │  Workstation    │
     │            │  │          │  │                 │
     │ Modbus:502 │  │ Web:8080 │  │ (deploy tools) │
     └────────────┘  └──────────┘  └─────────────────┘
```

<!-- TODO: Add screenshot of the OT topology as built in AE³GIS Topology Creator -->

### Building the Topology in AE³GIS

1. Open **AE³GIS** → **Instructor** → **Topologies** → **Create New Topology**
2. Set the project name (e.g., `stuxnet-lab`)
3. Add all four nodes, assigning them to the **OT** layer
4. Connect each node to the OT-Switch
5. Save and deploy the topology
6. Wait for all nodes to fully boot (OpenPLC and ScadaBR containers take longer to start)

---

## Deployment Scripts Reference

This scenario uses deployment scripts from subfolders. These are run from the **Engineering-Workstation** node to configure the PLC and HMI remotely.

| Folder | Script | Purpose |
|--------|--------|---------|
| [`deploy_plc/`](deploy_plc/) | `deploy_motor_plc.sh` | Uploads PLC logic (Structured Text) and hardware layer (PSM) to OpenPLC |
| [`deploy_plc/`](deploy_plc/) | `motor.st` | IEC 61131-3 Structured Text — Motor control program |
| [`deploy_plc/`](deploy_plc/) | `motor_psm.py` | Python SubModule — Normal motor physics simulation |
| [`deploy_hmi/`](deploy_hmi/) | `deploy_hmi.sh` | Configures ScadaBR with Modbus data points |
| [`deploy_hmi/`](deploy_hmi/) | `motor_hmi.json` | ScadaBR configuration (data sources, points, watchlist) |
| [`deploy_stuxnet/`](deploy_stuxnet/) | `deploy_stuxnet.sh` | Replaces normal PSM with Stuxnet payload |
| [`deploy_stuxnet/`](deploy_stuxnet/) | `motor_stuxnet_psm.py` | Malicious PSM — dual motor simulation with deception |

---

## Building the Scenario in AE³GIS

Recommended scenario structure using the **AE³GIS Scenario Editor**:

| Step # | Type | Content |
|--------|------|---------|
| 1 | Markdown | Overview and background on Stuxnet and ICS |
| 2 | Markdown | Phase 1 — Start PLC and HMI instructions |
| 3 | Markdown | Phase 2 — Deploy PLC logic instructions |
| 4 | Script | `deploy_motor_plc.sh` → Engineering-Workstation |
| 5 | Markdown | Instructions to verify PLC via web interface |
| 6 | Markdown | Phase 3 — Deploy HMI configuration |
| 7 | Script | `deploy_hmi.sh` → Engineering-Workstation |
| 8 | Markdown | Instructions to verify HMI and observe normal motor operation |
| 9 | Markdown | Phase 4 — Inspect Modbus traffic (Wireshark) |
| 10 | Markdown | Phase 5 — Deploy Stuxnet attack |
| 11 | Script | `deploy_stuxnet.sh` → Engineering-Workstation |
| 12 | Markdown | Instructions to manually restart PLC and observe attack |
| 13 | Markdown | Phase 6 — Detection and analysis |
| 14 | Markdown | Discussion questions and cleanup |

---

## Step-by-Step Student Instructions

### Phase 1: Start the ICS Components

#### Step 1.1 — Deploy the Topology

1. In AE³GIS, deploy your saved OT topology
2. Wait for all nodes to start — **OpenPLC and ScadaBR containers may take 1–2 minutes to fully initialize**

#### Step 1.2 — Start the OpenPLC Runtime

On the **PLC** node, open a console and start the OpenPLC runtime:

```bash
./start_openplc.sh
```

> **💡 Note:** The OpenPLC web interface will be available at `http://<PLC-IP>:8080` once started.

#### Step 1.3 — Start ScadaBR

On the **HMI** node, open a console and start ScadaBR:

```bash
./ScadaBR_Installer/scadabr.sh start
```

> **💡 Note:** ScadaBR may take 1–2 minutes to fully start. The web interface will be at `http://<HMI-IP>:8080/ScadaBR`.

#### Step 1.4 — Discover IP Addresses

On the **Engineering-Workstation**, determine the IP addresses of all nodes:

```bash
# Find your own IP
ip addr show eth0

# Ping or scan to find PLC and HMI IPs
# (alternatively, check each node's console directly)
```

On the **PLC** node:
```bash
hostname -I
```

On the **HMI** node:
```bash
hostname -I
```

> **📋 Checkpoint:** Record all IP addresses:
>
> | Node | IP Address |
> |------|-----------|
> | PLC | __________ |
> | HMI | __________ |
> | Engineering-Workstation | __________ |

---

### Phase 2: Deploy Normal PLC Logic

#### Step 2.1 — Understand the Motor Control Program

Before deploying, review what the PLC program does. The Structured Text program (`motor.st`) implements:

- **`run_motor`** — Coil that starts the motor (rising edge triggered)
- **`stop_motor`** — Coil that stops the motor
- **`motor_error`** — Input that indicates a motor fault
- **`motor_running`** — Output status: is the motor currently running?
- **`target_freq`** — Output: the frequency (Hz) to drive the motor at
- **`motor_rpm`** — Input: the actual motor RPM (feedback from the simulated motor)

The **PSM** (Python SubModule) `motor_psm.py` simulates realistic induction motor physics — it converts the target frequency to RPM using the motor's slip characteristics, poles, and ramp rates.

> **❓ Think About It:** What is the relationship between frequency (Hz) and motor RPM? For a 2-pole induction motor, what RPM would you expect at 60 Hz?
>
> *Hint: Synchronous speed = (120 × frequency) / poles. Actual speed is slightly less due to slip.*

#### Step 2.2 — Deploy the PLC Program

On the **Engineering-Workstation**, navigate to the directory containing the deployment scripts and run:

```bash
./deploy_motor_plc.sh "<PLC-IP>:8080"
```

Replace `<PLC-IP>` with the actual IP address of the PLC.

This script:
1. Logs into the OpenPLC web interface (credentials: `openplc` / `openplc`)
2. Uploads the Python SubModule (`motor_psm.py`) as the hardware layer
3. Uploads the Structured Text program (`motor.st`)
4. Compiles the PLC program
5. Starts the PLC runtime

#### Step 2.3 — Verify PLC Deployment via Web Interface

Open a web browser (on the Engineering-Workstation or your local machine) and navigate to:

```
http://<PLC-IP>:8080
```

Login with:
- **Username:** `openplc`
- **Password:** `openplc`

<!-- TODO: Add screenshot of OpenPLC web interface showing the motor program loaded and running -->

> **📋 Checkpoint:**
> - Is the PLC program listed under **Programs**?
> - Does the **Dashboard** show the PLC status as **Running**?
> - Can you see the I/O variables (motor_rpm, target_freq, motor_running)?

---

### Phase 3: Deploy the HMI

#### Step 3.1 — Verify PLC IP in HMI Configuration

Before deploying the HMI, you need to ensure the HMI configuration points to the correct PLC IP address.

On the **Engineering-Workstation**, check the `motor_hmi.json` configuration:

```bash
# Look for the host field in the Modbus data source
grep -i "host" motor_hmi.json
```

If the IP address doesn't match your PLC's IP, update it:

```bash
# Replace the IP address in the configuration
# (Use the actual PLC IP you recorded earlier)
sed -i 's/"host":"[^"]*"/"host":"<PLC-IP>"/' motor_hmi.json
```

#### Step 3.2 — Deploy the HMI Configuration

On the **Engineering-Workstation**, run:

```bash
./deploy_hmi.sh "<HMI-IP>:8080/ScadaBR"
```

Replace `<HMI-IP>` with the actual IP address of the HMI.

This script:
1. Logs into ScadaBR (credentials: `admin` / `admin`)
2. Obtains a DWR session token
3. Pushes the complete Modbus data source configuration
4. Sets up data points for motor control and monitoring

#### Step 3.3 — Verify HMI and Observe Normal Motor Operation

Open the ScadaBR web interface:

```
http://<HMI-IP>:8080/ScadaBR
```

Login with:
- **Username:** `admin`
- **Password:** `admin`

Navigate to the **Watch List** page. You should see the following data points:

| Data Point | Type | Description |
|------------|------|-------------|
| `motor_start` | Coil (settable) | Start the motor |
| `motor_running` | Coil (read-only) | Is the motor running? |
| `motor_stop` | Coil (settable) | Stop the motor |
| `target_freq` | Holding Register (settable) | Target frequency in Hz |
| `rpm` | Input Register (read-only) | Current motor RPM |
| `stuxnet_rpm` | Input Register (read-only) | RPM of the "true" motor (will differ from `rpm` during attack) |
| `stuxnet_target_freq` | Holding Register | Target freq of the "true" motor |

<!-- TODO: Add screenshot of ScadaBR Watch List showing all data points with normal values -->

#### Step 3.4 — Test Normal Motor Control

Using the ScadaBR Watch List:

1. **Start the motor**: Set `motor_start` to `1` (click the set icon next to the value)
2. **Observe**: Watch `motor_running` change to `1` and `rpm` ramp up from 0 to ~1775 RPM (for a 60Hz target)
3. **Change frequency**: Set `target_freq` to `90` and watch the RPM increase to ~2660 RPM
4. **Stop the motor**: Set `motor_stop` to `1`
5. **Observe**: Watch `motor_running` change to `0` and `rpm` ramp down to 0

> **📋 Checkpoint:**
>
> | Action | Expected `motor_running` | Expected `rpm` (approx.) |
> |--------|------------------------|--------------------------|
> | Start motor (60 Hz) | 1 | ~1775 |
> | Change to 90 Hz | 1 | ~2660 |
> | Stop motor | 0 | 0 |
>
> **❓ Question:** Note the `stuxnet_rpm` value. At this point (before the attack), it should be the **same** as `rpm`. Why?

---

### Phase 4: Inspect Modbus Traffic

#### Step 4.1 — Capture Modbus Communication

Before deploying the attack, capture normal Modbus traffic to understand the baseline communication pattern.

On the **Engineering-Workstation** (or by capturing on the OT-Switch):

```bash
# Install tcpdump if needed
apt-get update && apt-get install -y tcpdump

# Capture Modbus traffic (port 502)
tcpdump -i eth0 port 502 -c 50 -n
```

> **📋 Checkpoint:** Observe the communication pattern:
> - The HMI polls the PLC every ~500ms
> - You'll see Modbus TCP packets between the HMI IP and PLC IP on port 502
> - Each exchange is a request/response pair (read coils, read registers)

#### Step 4.2 — Use Wireshark for Deep Analysis (If Available)

If Wireshark is available on GNS3:

1. Right-click the link between OT-Switch and PLC
2. Select **Start Capture** → **Wireshark**
3. Apply display filter: `modbus`

<!-- TODO: Add screenshot of Wireshark showing Modbus TCP communication between HMI and PLC -->

> **📋 Checkpoint:** In Wireshark, identify:
> - **Function Code 1** (Read Coils) — Reading `motor_running`, `motor_start`, `motor_stop`
> - **Function Code 3** (Read Holding Registers) — Reading `target_freq`
> - **Function Code 4** (Read Input Registers) — Reading `motor_rpm`
> - **Function Code 5** (Write Single Coil) — When the operator starts/stops the motor
> - **Function Code 6** (Write Single Register) — When the operator changes `target_freq`

---

### Phase 5: Deploy the Stuxnet Attack

> **⚠️ WARNING:** From this point forward, you are simulating a cyber attack on an industrial control system. In a real environment, this could cause physical damage to equipment and endanger human safety.

#### Step 5.1 — Understand the Attack

The Stuxnet payload replaces the PLC's normal hardware layer (PSM) with a malicious version. The key differences:

| Aspect | Normal PSM | Stuxnet PSM |
|--------|-----------|-------------|
| Motor simulations | 1 (real) | 2 (visible + hidden) |
| `motor_rpm` (IW0) | Real RPM | **Fake RPM** (looks normal) |
| `stuxnet_rpm` (IW1) | Same as RPM | **Real RPM** (oscillating) |
| `target_freq` (QW0) | Operator-controlled | Operator-controlled (visible) |
| `stuxnet_target_freq` (QW1) | Same as target | **Attacker-controlled** (0↔120Hz) |

The attack oscillation logic:
- When the true motor reaches its target speed → set target to 0 Hz (stop)
- When the true motor reaches 0 RPM → set target to 120 Hz (full speed)
- This creates continuous violent start/stop cycling

#### Step 5.2 — Ensure the Motor is Running

Before deploying the attack, make sure the motor is currently running via the HMI:

1. In ScadaBR, set `motor_start` to `1`
2. Wait for `rpm` to stabilize at ~1775 RPM
3. Note the current `rpm` and `stuxnet_rpm` values — they should be **identical**

#### Step 5.3 — Deploy the Stuxnet Payload

On the **Engineering-Workstation**, run:

```bash
./deploy_stuxnet.sh "<PLC-IP>:8080"
```

Replace `<PLC-IP>` with the actual IP address of the PLC.

This script:
1. Stops the running PLC
2. Retrieves the currently loaded Structured Text program
3. Replaces the normal PSM with the malicious `motor_stuxnet_psm.py`
4. Recompiles the PLC program
5. **Does NOT auto-restart** — you must manually restart the PLC

#### Step 5.4 — Manually Restart the PLC

The PLC must be manually restarted for the attack to take effect. This is because the old PSM process is still holding the Modbus port.

On the **PLC** node, open a console:

```bash
# Switch to root
su

# Find the process holding port 2605 (the PSM process)
netstat -tulnp | grep 2605

# Note the PID from the output, then kill it
kill <PID>
```

> **⚠️ Important:** Replace `<PID>` with the actual process ID from the `netstat` output.

Then, via the **OpenPLC Web Interface**:

1. Navigate to `http://<PLC-IP>:8080`
2. Login with `openplc` / `openplc`
3. Click the **Start PLC** button in the navigation bar

<!-- TODO: Add screenshot of OpenPLC web interface showing the Start PLC button -->

---

### Phase 6: Observe the Attack

#### Step 6.1 — Watch the HMI (The Operator's View)

Go back to the **ScadaBR Watch List** (`http://<HMI-IP>:8080/ScadaBR`).

Start the motor if it's not already running (set `motor_start` to `1`).

Watch the data points carefully:

> **📋 Checkpoint — The Deception:**
>
> | Data Point | What You See | What's Really Happening |
> |------------|-------------|------------------------|
> | `motor_running` | `1` (running) | ✅ Appears correct |
> | `target_freq` | `60` Hz (normal) | ✅ Operator-set value |
> | `rpm` | ~1775 RPM (stable) | ❌ **FAKE** — This is the "visible" motor |
> | `stuxnet_rpm` | Oscillating wildly! | ⚠️ **REAL** — The actual motor RPM |
> | `stuxnet_target_freq` | Alternating 0↔120 Hz | ⚠️ **ATTACK** — Attacker-controlled |
>
> **The operator (looking at `rpm`) sees a perfectly stable motor at 1775 RPM.**  
> **In reality (`stuxnet_rpm`), the motor is being violently cycled between 0 and 3546 RPM.**

<!-- TODO: Add screenshot of ScadaBR Watch List during the attack showing the discrepancy between rpm and stuxnet_rpm -->

#### Step 6.2 — Observe the Oscillation Pattern

Watch `stuxnet_rpm` over about 60 seconds. You should see a pattern like:

```
stuxnet_rpm: 0 → 500 → 1200 → 2000 → 2800 → 3546 → 3000 → 2000 → 1000 → 0 → 500 → ...
```

The motor ramps up to 120 Hz (3546 RPM), then immediately drops to 0, then ramps up again. This continuous oscillation would cause:
- **Extreme mechanical stress** on bearings and coupling
- **Thermal damage** from rapid current changes
- **Eventual mechanical failure** of the motor and connected equipment

> **❓ Question:** Why is this type of attack more dangerous than simply shutting down the motor? What makes the deception component critical?

#### Step 6.3 — Analyze Modbus Traffic During Attack

On the **Engineering-Workstation**, capture Modbus traffic during the attack:

```bash
tcpdump -i eth0 port 502 -c 100 -n
```

> **📋 Checkpoint:** The Modbus traffic pattern should look normal — same polling interval, same function codes. The attack is **invisible at the network level** because the PLC itself is generating the fake values. This is fundamentally different from a man-in-the-middle attack on the network.

---

### Phase 7: Detection

#### Step 7.1 — Compare Reported vs. Actual Values

The key detection method for a Stuxnet-style attack is **cross-referencing process data from independent sources**.

In the ScadaBR Watch List, compare:

| Parameter | Register | Expected (Normal) | Observed (Attack) |
|-----------|----------|-------------------|-------------------|
| `rpm` | IW0 | Matches `stuxnet_rpm` | Stable ~1775 |
| `stuxnet_rpm` | IW1 | Matches `rpm` | Oscillating 0↔3546 |
| `target_freq` | QW0 | Matches `stuxnet_target_freq` | Stable 60 Hz |
| `stuxnet_target_freq` | QW1 | Matches `target_freq` | Oscillating 0↔120 |

> **📋 Checkpoint:** The discrepancy between `rpm` and `stuxnet_rpm` is the **smoking gun**. In normal operation, these values are always identical. During the attack, they diverge completely.

#### Step 7.2 — Detection Discussion

> **❓ Questions for Analysis:**
>
> 1. In the real Stuxnet attack, the operators didn't have a `stuxnet_rpm` data point to compare against. How was the attack eventually discovered?
> 2. What physical indicators might alert plant operators to this type of attack? (Hint: vibration, temperature, noise, power consumption)
> 3. How could you implement automated detection? What threshold or comparison logic would you use?
> 4. Why is this attack undetectable from the network level? What would a network IDS see?

---

### Phase 8: Recovery and Cleanup

#### Step 8.1 — Stop the PLC

Via the OpenPLC web interface, click **Stop PLC**.

#### Step 8.2 — Restore Normal Operation

To restore normal operation, you would need to:
1. Stop the current PLC program
2. Re-deploy the original PSM (`motor_psm.py`) using `deploy_motor_plc.sh`
3. Restart the PLC

On the **Engineering-Workstation**:

```bash
./deploy_motor_plc.sh "<PLC-IP>:8080"
```

#### Step 8.3 — Verify Recovery

In ScadaBR:
1. Start the motor (`motor_start` = 1)
2. Verify that `rpm` and `stuxnet_rpm` are now **identical** again
3. Verify that `target_freq` and `stuxnet_target_freq` match

#### Step 8.4 — Submit Your Work

1. In AE³GIS, navigate to the **Telemetry** page
2. Click **Preview Logs** to review your command history
3. Click **Submit** to send your logs to the instructor

---

## Discussion Questions

After completing the lab, consider the following:

1. **Why is the PSM (hardware layer) the ideal attack vector?** What makes it different from attacking the Structured Text logic directly?
2. **How did the real Stuxnet worm propagate** to reach air-gapped centrifuge control systems?
3. **What defense mechanisms could prevent** unauthorized PSM replacement? (Code signing, file integrity monitoring, access control)
4. **Compare this to the ARP spoofing scenario.** Both are man-in-the-middle attacks, but at very different layers. What are the similarities and differences?
5. **What is "defense in depth"** and how would it apply to protecting an ICS environment?
6. **Could a network-based IDS detect this attack?** Why or why not? What about a host-based IDS on the PLC?
7. **What are the real-world consequences** of attacks on industrial control systems? Research: Ukraine power grid attacks (2015, 2016), Triton/TRISIS (2017), Oldsmar water treatment (2021).

---

## Technical Reference

### PLC Program Variables

The Structured Text program (`motor.st`) uses dual variable sets — a "visible" set (shown to the operator) and a "true" set (actual physical state):

| Variable | Address | Type | Visible Set | True Set |
|----------|---------|------|-------------|----------|
| `run_motor` | %QX0.0 | BOOL | ✅ | |
| `motor_running` | %QX0.1 | BOOL | ✅ | |
| `stop_motor` | %QX0.2 | BOOL | ✅ | |
| `run_motor_true` | %QX0.3 | BOOL | | ✅ |
| `motor_running_true` | %QX0.4 | BOOL | | ✅ |
| `stop_motor_true` | %QX0.5 | BOOL | | ✅ |
| `target_freq` | %QW0 | INT | ✅ | |
| `stuxnet_target_freq` | %QW1 | INT | | ✅ (init=120) |
| `motor_rpm` | %IW0 | INT | ✅ | |
| `stuxnet_rpm` | %IW1 | INT | | ✅ |

### Modbus Register Mapping

| Register Type | Offset | Data Point | Description |
|--------------|--------|------------|-------------|
| Coil | 0 | `motor_start` | Start the motor |
| Coil | 1 | `motor_running` | Motor running status |
| Coil | 2 | `motor_stop` | Stop the motor |
| Holding Register | 0 | `target_freq` | Target frequency (Hz) |
| Holding Register | 1 | `stuxnet_target_freq` | True target frequency |
| Input Register | 0 | `motor_rpm` | Reported motor RPM |
| Input Register | 1 | `stuxnet_rpm` | Actual motor RPM |

### Motor Physics (PSM Simulation)

The Python SubModule simulates an induction motor with:
- **Poles:** 2
- **Rated slip:** 0.025
- **Ramp-up rate:** 500 RPM/sec
- **Ramp-down rate:** 300 RPM/sec
- **Formula:** Synchronous speed = (120 × frequency) / poles; Actual speed = synchronous × (1 - slip)

---

## Appendix: File Descriptions

| File | Description |
|------|-------------|
| [`deploy_plc/deploy_motor_plc.sh`](deploy_plc/deploy_motor_plc.sh) | Automates PLC deployment: login, upload PSM, upload ST, compile, start |
| [`deploy_plc/motor.st`](deploy_plc/motor.st) | IEC 61131-3 Structured Text motor control program |
| [`deploy_plc/motor_psm.py`](deploy_plc/motor_psm.py) | Normal PSM — single motor simulation with realistic physics |
| [`deploy_hmi/deploy_hmi.sh`](deploy_hmi/deploy_hmi.sh) | Automates ScadaBR configuration via DWR API |
| [`deploy_hmi/motor_hmi.json`](deploy_hmi/motor_hmi.json) | ScadaBR configuration: Modbus data source, data points, watchlist |
| [`deploy_stuxnet/deploy_stuxnet.sh`](deploy_stuxnet/deploy_stuxnet.sh) | Replaces normal PSM with Stuxnet PSM, recompiles PLC |
| [`deploy_stuxnet/motor_stuxnet_psm.py`](deploy_stuxnet/motor_stuxnet_psm.py) | Stuxnet PSM — dual motor simulation with oscillation attack and operator deception |
| [`motor_plc_stuxnet/motor.st`](motor_plc_stuxnet/motor.st) | Reference copy of the ST program |
| [`motor_plc_stuxnet/plc.xml`](motor_plc_stuxnet/plc.xml) | PLCOpen XML — visual representation of the PLC program (Beremiz project) |
| [`motor_plc_stuxnet/beremiz.xml`](motor_plc_stuxnet/beremiz.xml) | Beremiz project configuration |

---

## Appendix: Troubleshooting

| Problem | Solution |
|---------|----------|
| OpenPLC web interface not loading | Wait 1–2 minutes after starting; run `./start_openplc.sh` again |
| ScadaBR not loading | Wait 1–2 minutes; check that Tomcat is running: `ps aux | grep tomcat` |
| `deploy_motor_plc.sh` fails to login | Verify PLC IP is correct; check credentials (default: `openplc`/`openplc`) |
| HMI shows "Data source disabled" | Enable the Modbus data source in ScadaBR → Data Sources |
| `rpm` stays at 0 after starting motor | Check PLC is running (Dashboard → Running); verify PSM was uploaded |
| Port 2605 not found in `netstat` | The old PSM may have already stopped; proceed with starting the PLC |
| All values are 0 in ScadaBR | Check that the Modbus host IP in the data source matches the PLC IP |
| HMI can't connect to PLC | Verify network connectivity: `ping <PLC-IP>` from HMI |