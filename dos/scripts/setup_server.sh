#!/bin/bash
# =============================================================================
# setup_server.sh — Install and start a web server on IT-Server
# Target Node: IT-Server
# =============================================================================
# Sets up nginx with monitoring tools. This is the target for DoS attacks.
# =============================================================================

apt-get update && apt-get install -y nginx net-tools tcpdump iptables
service nginx start

# Create a test web page
cat > /var/www/html/index.html << 'EOF'
<html>
<head><title>IT-Server</title></head>
<body>
<h1>IT-Server — Web Application</h1>
<p>This server is the target for the DoS lab exercise.</p>
<p>Server Status: <strong>ONLINE</strong></p>
</body>
</html>
EOF

echo "[+] Nginx web server is running on port 80."
echo "[+] Monitoring tools installed: tcpdump, netstat, iptables"
echo "[+] Test with: curl http://$(hostname -I | awk '{print $1}')"
