# ============================================================
# AE3GIS Zeek Local Policy
# ============================================================
# Loads protocol analyzers for all traffic types in the network.
# Generates structured logs: conn.log, dns.log, http.log, ftp.log,
# ssh.log, mysql.log, notice.log, etc.
# ============================================================

# --- Base protocol analyzers ---
@load base/protocols/conn
@load base/protocols/dns
@load base/protocols/ftp
@load base/protocols/http
@load base/protocols/ssh
@load base/protocols/mysql
@load base/protocols/ssl

# --- Logging framework ---
@load base/frameworks/logging
@load base/frameworks/notice

# --- Detection scripts ---
# Detect port scans (will fire when attacker runs nmap)
@load misc/scan

# Detect traceroute
@load misc/detect-traceroute

# Detect software versions from traffic
@load frameworks/software/vulnerable
@load frameworks/software/version-changes

# --- File analysis ---
# Extract and log file transfers (FTP uploads/downloads)
@load frameworks/files/hash-all-files

# --- Connection duration tracking ---
# Useful for identifying long-lived connections (reverse shells, tunnels)
@load policy/protocols/conn/known-hosts
@load policy/protocols/conn/known-services

# --- SSH detection ---
# Log SSH login attempts (useful for detecting lateral movement)
@load policy/protocols/ssh/detect-bruteforcing
@load policy/protocols/ssh/interesting-hostnames

# --- Notice policy ---
# Make sure all notices are logged
@load policy/frameworks/notice/extend-email/hostnames

# --- Custom settings ---
# Rotate logs every hour
redef Log::default_rotation_interval = 1 hr;

# Set local network ranges (adjust to match your topology)
redef Site::local_nets += {
    10.10.0.0/16
};
