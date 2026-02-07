#!/bin/bash
# =============================================================================
# setup_server.sh — Install and start a web server on IT-Server
# Target Node: IT-Server
# =============================================================================
# This script sets up an nginx web server that the workstation will access.
# Run this FIRST before starting the scenario.
# =============================================================================

apt-get update && apt-get install -y nginx net-tools
service nginx start

# Create a simple web page for testing
cat > /var/www/html/index.html << 'EOF'
<html>
<head><title>IT-Server</title></head>
<body>
<h1>IT-Server — Secure Page</h1>
<p>If you can see this page, the connection between your workstation and the server is working correctly.</p>
<p>Server Time: <script>document.write(new Date().toLocaleString())</script></p>
</body>
</html>
EOF

echo "[+] Nginx web server is running."
echo "[+] Test with: curl http://$(hostname -I | awk '{print $1}')"
