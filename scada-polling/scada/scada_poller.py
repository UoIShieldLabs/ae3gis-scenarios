"""
SCADA server — polls all PLCs over Modbus/TCP, logs performance metrics.

Usage:
    export PLC_HOSTS=10.0.2.11,10.0.2.12,10.0.2.13,10.0.2.14
    export POLL_INTERVAL=0.5
    export RUN_DURATION=300
    python scada_poller.py

Output:
    /tmp/scada_polls.csv   — one row per poll (timestamp, plc, rtt, bytes)
    /tmp/scada_summary.log — 30-second summaries to stderr (also printed live)
    stdout                 — live summary output
"""
import os
import sys
import time
import csv
import signal

from pymodbus.client import ModbusTcpClient

# ── Config ──────────────────────────────────────────────
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", 0.5))
PLC_HOSTS = [h.strip() for h in os.environ.get("PLC_HOSTS", "").split(",") if h.strip()]
PLC_PORT = 502
NUM_REGISTERS = 10
SUMMARY_INTERVAL = 30  # seconds
RUN_DURATION = int(os.environ.get("RUN_DURATION", 0))  # 0 = run forever

# Modbus/TCP sizes (approximate)
REQUEST_SIZE = 12   # 7 MBAP + 5 PDU
RESPONSE_SIZE = 9 + NUM_REGISTERS * 2  # 7 MBAP + 2 PDU header + data

CSV_PATH = "/tmp/scada_polls.csv"
SUMMARY_PATH = "/tmp/scada_summary.log"

running = True

def handle_signal(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def main():
    if not PLC_HOSTS:
        print("ERROR: Set PLC_HOSTS env var (comma-separated IPs)")
        print("Example: export PLC_HOSTS=10.0.2.11,10.0.2.12")
        sys.exit(1)

    print(f"╔══════════════════════════════════════════╗")
    print(f"║         SCADA Modbus/TCP Poller          ║")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║  PLCs:          {len(PLC_HOSTS):<24} ║")
    print(f"║  Poll interval: {POLL_INTERVAL:<24} ║")
    print(f"║  Duration:      {'infinite' if RUN_DURATION == 0 else str(RUN_DURATION) + 's':<24} ║")
    print(f"║  CSV output:    {CSV_PATH:<24} ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"PLC targets: {PLC_HOSTS}")
    print()

    # Open CSV file
    csv_file = open(CSV_PATH, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow(["timestamp", "plc_ip", "rtt_ms", "success", "req_bytes", "resp_bytes"])

    # Open summary log
    summary_file = open(SUMMARY_PATH, "w")

    # Connect to all PLCs
    clients = {}
    for host in PLC_HOSTS:
        c = ModbusTcpClient(host, port=PLC_PORT, timeout=3)
        clients[host] = c
        print(f"  Target: {host}:{PLC_PORT}")

    # Counters
    total_requests = 0
    total_success = 0
    total_fail = 0
    total_bytes_sent = 0
    total_bytes_recv = 0
    rtt_samples = []
    summary_start = time.time()
    run_start = time.time()
    summary_count = 0

    print(f"\nPolling started at {time.strftime('%H:%M:%S')}...")
    print(f"Summaries every {SUMMARY_INTERVAL}s. Ctrl+C to stop.\n")

    global running
    while running:
        # Check duration
        if RUN_DURATION > 0 and (time.time() - run_start) >= RUN_DURATION:
            print(f"\nRun duration ({RUN_DURATION}s) reached. Stopping.")
            break

        for host, client in clients.items():
            if not client.connected:
                try:
                    client.connect()
                except Exception:
                    pass

            t0 = time.time()
            try:
                result = client.read_holding_registers(0, NUM_REGISTERS)
                t1 = time.time()
                rtt_ms = (t1 - t0) * 1000
                success = not result.isError()

                if success:
                    total_success += 1
                    total_bytes_sent += REQUEST_SIZE
                    total_bytes_recv += RESPONSE_SIZE
                    rtt_samples.append(rtt_ms)
                else:
                    total_fail += 1

                total_requests += 1
                writer.writerow([
                    f"{t1:.3f}", host, f"{rtt_ms:.2f}",
                    success, REQUEST_SIZE if success else 0,
                    RESPONSE_SIZE if success else 0
                ])
                csv_file.flush()

            except Exception:
                t1 = time.time()
                total_requests += 1
                total_fail += 1
                writer.writerow([f"{t1:.3f}", host, "-1", False, 0, 0])
                csv_file.flush()

        # Periodic summary
        elapsed = time.time() - summary_start
        if elapsed >= SUMMARY_INTERVAL:
            summary_count += 1
            avg_rtt = sum(rtt_samples) / len(rtt_samples) if rtt_samples else 0
            max_rtt = max(rtt_samples) if rtt_samples else 0
            min_rtt = min(rtt_samples) if rtt_samples else 0
            p95_rtt = sorted(rtt_samples)[int(len(rtt_samples) * 0.95)] if rtt_samples else 0
            total_bytes = total_bytes_sent + total_bytes_recv
            throughput_bps = total_bytes / elapsed if elapsed > 0 else 0
            req_per_min = total_requests / elapsed * 60 if elapsed > 0 else 0
            success_pct = 100 * total_success / max(total_requests, 1)

            summary = (
                f"┌─ Summary #{summary_count} ({time.strftime('%H:%M:%S')}) ────────────\n"
                f"│  PLCs polled:      {len(PLC_HOSTS)}\n"
                f"│  Requests:         {total_requests}\n"
                f"│  Success/Fail:     {total_success} / {total_fail} ({success_pct:.1f}%)\n"
                f"│  RTT avg:          {avg_rtt:.2f} ms\n"
                f"│  RTT min/max:      {min_rtt:.2f} / {max_rtt:.2f} ms\n"
                f"│  RTT p95:          {p95_rtt:.2f} ms\n"
                f"│  Bytes sent:       {total_bytes_sent}\n"
                f"│  Bytes received:   {total_bytes_recv}\n"
                f"│  Total bytes:      {total_bytes}\n"
                f"│  Throughput:       {throughput_bps:.1f} B/s\n"
                f"│  Requests/min:     {req_per_min:.1f}\n"
                f"└──────────────────────────────────────\n"
            )
            print(summary)
            summary_file.write(summary + "\n")
            summary_file.flush()

            # Reset for next interval
            total_requests = 0
            total_success = 0
            total_fail = 0
            total_bytes_sent = 0
            total_bytes_recv = 0
            rtt_samples = []
            summary_start = time.time()

        time.sleep(POLL_INTERVAL)

    # Cleanup
    for client in clients.values():
        client.close()
    csv_file.close()
    summary_file.close()

    print(f"\nDone. Results saved to:")
    print(f"  {CSV_PATH}")
    print(f"  {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
