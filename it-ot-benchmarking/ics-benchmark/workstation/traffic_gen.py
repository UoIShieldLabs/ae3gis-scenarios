"""
IT Workstation traffic generator.

MODE=workstation:
    Simulates enterprise user browsing intranet pages and downloading files.
    HTTP requests at random intervals (5-30s), FTP downloads at random intervals (60-120s).

MODE=monitor:
    Simulates a monitoring dashboard pulling data from the historian database.
    MySQL SELECT query every MONITOR_INTERVAL seconds.

Environment variables:
    MODE              "workstation" or "monitor" (default: workstation)
    WEB_SERVER        IP of web server (default: 192.168.1.2)
    FTP_SERVER        IP of FTP server (default: 192.168.1.3)
    HISTORIAN_HOST    IP of historian (default: 172.16.0.2)
    MONITOR_INTERVAL  seconds between monitor pulls (default: 30)
    DB_USER           MySQL user (default: scada)
    DB_PASS           MySQL password (default: scada)
    DB_NAME           MySQL database (default: ics_historian)
"""
import os, sys, time, random, threading
from urllib.request import urlopen
from urllib.error import URLError
from ftplib import FTP
from io import BytesIO

MODE = os.environ.get("MODE", "workstation")
WEB_SERVER = os.environ.get("WEB_SERVER", "192.168.1.2")
FTP_SERVER = os.environ.get("FTP_SERVER", "192.168.1.3")
HISTORIAN_HOST = os.environ.get("HISTORIAN_HOST", "172.16.0.2")
MONITOR_INTERVAL = float(os.environ.get("MONITOR_INTERVAL", 30))
DB_USER = os.environ.get("DB_USER", "scada")
DB_PASS = os.environ.get("DB_PASS", "scada")
DB_NAME = os.environ.get("DB_NAME", "ics_historian")

PAGES = ["index.html", "safety.html", "network.html", "directory.html",
         "reports.html", "policies.html", "training.html"]
FTP_FILES = ["plc_config_backup.bin", "quarterly_report.bin", "firmware_v2.1.bin",
             "network_diagram.bin", "maintenance_log.bin"]


def http_loop():
    """Browse intranet pages at random intervals."""
    while True:
        page = random.choice(PAGES)
        try:
            resp = urlopen(f"http://{WEB_SERVER}/{page}", timeout=10)
            data = resp.read()
        except Exception:
            pass
        time.sleep(random.uniform(5, 30))


def ftp_loop():
    """Download files from FTP at random intervals."""
    while True:
        try:
            ftp = FTP(FTP_SERVER, timeout=10)
            ftp.login()  # anonymous
            ftp.cwd("pub")
            filename = random.choice(FTP_FILES)
            buf = BytesIO()
            ftp.retrbinary(f"RETR {filename}", buf.write)
            ftp.quit()
        except Exception:
            pass
        time.sleep(random.uniform(60, 120))


def monitor_loop():
    """Pull latest readings from historian database."""
    import pymysql
    conn = None
    while True:
        try:
            if conn is None:
                conn = pymysql.connect(
                    host=HISTORIAN_HOST, port=3306,
                    user=DB_USER, password=DB_PASS, database=DB_NAME,
                    connect_timeout=5
                )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT plc_ip, register_values, timestamp FROM plc_readings "
                "ORDER BY id DESC LIMIT 50"
            )
            rows = cursor.fetchall()
            cursor.close()
        except Exception as e:
            conn = None
        time.sleep(MONITOR_INTERVAL)


def main():
    if MODE == "monitor":
        print(f"Monitor mode | Historian: {HISTORIAN_HOST} every {MONITOR_INTERVAL}s")
        monitor_loop()
    else:
        print(f"Workstation mode | Web: {WEB_SERVER} | FTP: {FTP_SERVER}")
        t1 = threading.Thread(target=http_loop, daemon=True)
        t2 = threading.Thread(target=ftp_loop, daemon=True)
        t1.start()
        t2.start()
        # Keep main thread alive
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()
