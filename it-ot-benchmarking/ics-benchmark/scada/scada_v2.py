"""
SCADA server v2 — polls PLCs via Modbus/TCP + pushes readings to MySQL historian.

Environment variables:
    PLC_HOSTS       comma-separated PLC IPs
    POLL_INTERVAL   seconds between polls (default: 1.0)
    HISTORIAN_HOST  historian IP (default: 172.16.0.2)
    HISTORIAN_PUSH  seconds between historian pushes (default: 30)
    DB_USER         MySQL user (default: scada)
    DB_PASS         MySQL password (default: scada)
    DB_NAME         MySQL database (default: ics_historian)
"""
import os, sys, time, threading, json
from pymodbus.client import ModbusTcpClient

# ── Config ──
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", 1.0))
PLC_HOSTS = [h.strip() for h in os.environ.get("PLC_HOSTS", "").split(",") if h.strip()]
PLC_PORT = 502
NUM_REGISTERS = 10
HISTORIAN_HOST = os.environ.get("HISTORIAN_HOST", "172.16.0.2")
HISTORIAN_PUSH = float(os.environ.get("HISTORIAN_PUSH", 30))
DB_USER = os.environ.get("DB_USER", "scada")
DB_PASS = os.environ.get("DB_PASS", "scada")
DB_NAME = os.environ.get("DB_NAME", "ics_historian")

# Buffer for readings to push
readings_buffer = []
buffer_lock = threading.Lock()


def connect_db():
    """Connect to MySQL with retries."""
    import pymysql
    for attempt in range(60):
        try:
            conn = pymysql.connect(
                host=HISTORIAN_HOST, port=3306,
                user=DB_USER, password=DB_PASS, database=DB_NAME,
                connect_timeout=5
            )
            print(f"  Connected to historian at {HISTORIAN_HOST}")
            return conn
        except Exception as e:
            if attempt % 10 == 0:
                print(f"  Waiting for historian ({attempt}s): {e}")
            time.sleep(1)
    print("  ERROR: Could not connect to historian after 60s")
    return None


def historian_push_loop():
    """Push buffered readings to MySQL every HISTORIAN_PUSH seconds."""
    import pymysql
    conn = connect_db()
    if not conn:
        return

    while True:
        time.sleep(HISTORIAN_PUSH)
        with buffer_lock:
            batch = list(readings_buffer)
            readings_buffer.clear()

        if not batch:
            continue

        try:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO plc_readings (plc_ip, register_values) VALUES (%s, %s)",
                [(r["plc"], json.dumps(r["values"])) for r in batch]
            )
            conn.commit()
            cursor.close()
            print(f"  Historian: pushed {len(batch)} readings")
        except Exception as e:
            print(f"  Historian push error: {e}")
            try:
                conn = connect_db()
            except Exception:
                pass


def poll_loop():
    """Poll all PLCs every POLL_INTERVAL seconds."""
    clients = {h: ModbusTcpClient(h, port=PLC_PORT, timeout=3) for h in PLC_HOSTS}

    while True:
        for host, client in clients.items():
            if not client.connected:
                try:
                    client.connect()
                except Exception:
                    continue
            try:
                result = client.read_holding_registers(0, NUM_REGISTERS)
                if not result.isError():
                    with buffer_lock:
                        readings_buffer.append({
                            "plc": host,
                            "values": result.registers,
                            "ts": time.time()
                        })
            except Exception:
                pass
        time.sleep(POLL_INTERVAL)


def main():
    if not PLC_HOSTS:
        print("ERROR: Set PLC_HOSTS env var")
        sys.exit(1)

    print(f"SCADA v2 | Polling {len(PLC_HOSTS)} PLCs every {POLL_INTERVAL}s")
    print(f"  Historian: {HISTORIAN_HOST} (push every {HISTORIAN_PUSH}s)")

    # Start historian push thread
    t = threading.Thread(target=historian_push_loop, daemon=True)
    t.start()

    # Main poll loop
    poll_loop()


if __name__ == "__main__":
    main()
