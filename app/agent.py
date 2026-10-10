#!/usr/bin/env python3
"""UDP telemetry agent. Runs on h1..h4 inside Mininet."""
import argparse
import os
import random
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import common as C


def read_counters(iface=None):
    """(tx_bytes, rx_bytes) of this host's first non-loopback interface.
    /proc/net/dev is per network namespace, so inside a Mininet host it shows
    that host's own interface (e.g. h1-eth0)."""
    try:
        with open("/proc/net/dev") as f:
            for line in f.readlines()[2:]:
                name, data = line.split(":", 1)
                name = name.strip()
                if name == "lo" or (iface and name != iface):
                    continue
                fields = data.split()
                return int(fields[8]), int(fields[0])
    except Exception:
        pass
    return 0, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host-id", required=True)
    ap.add_argument("--server-ip", default=C.SERVER_IP)
    ap.add_argument("--server-port", type=int, default=C.SERVER_PORT)
    ap.add_argument("--interval", type=float, default=C.TELEMETRY_INTERVAL_S)
    ap.add_argument("--iface", default=None)
    ap.add_argument("--drop-rate", type=float, default=0.0,
                    help="testing only: fraction of packets NOT sent (seq still increments)")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq, next_t = 0, time.time()
    while True:
        seq += 1
        tx, rx = read_counters(args.iface)
        if random.random() >= args.drop_rate:
            try:
                sock.sendto(C.encode_packet(args.host_id, seq, time.time(), tx, rx),
                            (args.server_ip, args.server_port))
            except OSError as e:
                print("send error:", e, file=sys.stderr)
        next_t += args.interval
        time.sleep(max(0.0, next_t - time.time()))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
