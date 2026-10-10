#!/usr/bin/env python3
"""UDP monitoring server. Runs on h5. Receives telemetry, tracks per-host stats,
writes logs/telemetry.csv (every packet) and logs/hosts_state.json (snapshot, 1 Hz)."""
import argparse
import csv
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import common as C


def write_state(path, hosts, now):
    out = {"updated": now, "hosts": {}}
    for name, h in sorted(hosts.items()):
        total = h["received"] + h["lost"]
        out["hosts"][name] = {
            "ip": h["ip"],
            "liveness": "UP" if now - h["last_seen"] <= C.SILENT_TIMEOUT_S else "DOWN",
            "last_seen": h["last_seen"],
            "packets_received": h["received"],
            "packets_lost": h["lost"],
            "loss_pct": round(100.0 * h["lost"] / total, 2) if total else 0.0,
            "tx_bytes": h["tx_bytes"], "rx_bytes": h["rx_bytes"],
            "tx_rate_mbps": round(h["tx_rate_mbps"], 4),
            "rx_rate_mbps": round(h["rx_rate_mbps"], 4),
        }
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=1)
    os.replace(tmp, path)  # atomic: readers never see a half-written file
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=C.SERVER_PORT)
    ap.add_argument("--log-dir", default=C.LOG_DIR)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.log_dir, exist_ok=True)
    csv_path = os.path.join(args.log_dir, "telemetry.csv")
    state_path = os.path.join(args.log_dir, "hosts_state.json")
    new_file = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    csv_f = open(csv_path, "a", newline="")
    w = csv.writer(csv_f)
    if new_file:
        w.writerow(["recv_ts", "host", "seq", "send_ts", "tx_bytes", "rx_bytes", "lost_since_last"])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.port))
    sock.settimeout(0.5)
    print(f"monitoring server listening on {args.bind}:{args.port}", flush=True)

    hosts, last_write = {}, 0.0
    while True:
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            data = None
        except KeyboardInterrupt:
            break
        now = time.time()
        pkt = C.decode_packet(data) if data else None
        if pkt:
            h = hosts.setdefault(pkt["host"], {
                "ip": addr[0], "received": 0, "lost": 0, "last_seq": 0, "last_seen": 0.0,
                "tx_bytes": 0, "rx_bytes": 0, "tx_rate_mbps": 0.0, "rx_rate_mbps": 0.0,
                "prev": None})
            gap = 0
            if h["received"] > 0 and pkt["seq"] > h["last_seq"] + 1:
                gap = pkt["seq"] - h["last_seq"] - 1   # missing packets
                h["lost"] += gap
            # seq <= last_seq means the agent restarted: not counted as loss
            h["last_seq"], h["last_seen"] = pkt["seq"], now
            h["received"] += 1
            if h["prev"] and pkt["ts"] > h["prev"][0]:
                dt = pkt["ts"] - h["prev"][0]
                h["tx_rate_mbps"] = max(0, pkt["tx_bytes"] - h["prev"][1]) * 8 / dt / 1e6
                h["rx_rate_mbps"] = max(0, pkt["rx_bytes"] - h["prev"][2]) * 8 / dt / 1e6
            h["prev"] = (pkt["ts"], pkt["tx_bytes"], pkt["rx_bytes"])
            h["tx_bytes"], h["rx_bytes"] = pkt["tx_bytes"], pkt["rx_bytes"]
            w.writerow([round(now, 3), pkt["host"], pkt["seq"], pkt["ts"],
                        pkt["tx_bytes"], pkt["rx_bytes"], gap])
            csv_f.flush()
        if now - last_write >= 1.0:
            state = write_state(state_path, hosts, now)
            last_write = now
            if not args.quiet:
                print(f"--- {time.strftime('%H:%M:%S')} ---")
                for n, s in state["hosts"].items():
                    print(f"{n} {s['ip']:<10} {s['liveness']:<4} rx_pkts={s['packets_received']:<5} "
                          f"lost={s['packets_lost']:<4} loss={s['loss_pct']:>5}% tx={s['tx_rate_mbps']:.3f}Mbps",
                          flush=True)


if __name__ == "__main__":
    main()
