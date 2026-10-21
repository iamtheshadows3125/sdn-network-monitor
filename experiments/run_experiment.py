#!/usr/bin/env python3
"""
Runs ONE experiment (one scenario in one mode) and saves its logs to experiments/results/<run_id>/.

PREREQUISITE: the controller must already be running in another terminal:
    ryu-manager controller/stats_monitor.py
Then (Mininet needs root):
    sudo python3 experiments/run_experiment.py --scenario heavy --mode combined
    sudo python3 experiments/run_experiment.py --scenario heavy --mode baseline
This script itself starts Mininet, the UDP server/agents, and alerts/alert_engine.py (with --baseline
when --mode baseline), so do NOT start those by hand.

Scenarios: idle | moderate (UDP 5 Mbps) | heavy (TCP iperf3) | aggregate (two UDP 6 Mbps flows)
           | host_down (kills h2's agent) | loss (h3's agent drops 30% of its packets)
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from app import common as C                      # noqa: E402

SCENARIOS = ("idle", "moderate", "heavy", "aggregate", "host_down", "loss")
LOG_FILES = ["telemetry.csv", "hosts_state.json", "port_stats.json", "status.json", "alerts.csv", "analysis.csv"]
WARMUP_S, COOLDOWN_S = 10, 10


def controller_up():
    try:
        socket.create_connection((C.CONTROLLER_IP, C.CONTROLLER_PORT), timeout=2).close()
        return True
    except OSError:
        return False


def iperf_mbps(path):
    """Received throughput (Mbps) from an iperf3 -J output file, or None."""
    try:
        txt = open(path).read()
        data = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        end = data["end"]
        bps = (end.get("sum_received") or end.get("sum"))["bits_per_second"]
        return round(bps / 1e6, 3)
    except Exception:
        return None


def run_scenario(net, name, dur, run_dir):
    h1, h2, h3, h5 = net.get("h1"), net.get("h2"), net.get("h3"), net.get("h5")
    flows = []                                   # (client host, port, iperf3 args)
    if name == "moderate":
        flows = [(h1, 5201, "-u -b 5M")]
    elif name == "heavy":
        flows = [(h1, 5201, "")]
    elif name == "aggregate":
        flows = [(h1, 5201, "-u -b 6M"), (h2, 5202, "-u -b 6M")]
    files = []
    for i, (host, port, extra) in enumerate(flows):
        h5.cmd("iperf3 -s -p %d -D" % port)
        f = os.path.join(run_dir, "iperf_%d.json" % i)
        files.append(f)
        host.cmd("iperf3 -c %s -p %d %s -t %d -J > %s 2>&1 &" % (C.SERVER_IP, port, extra, dur, f))
    if name == "host_down":
        time.sleep(5)
        h2.cmd('pkill -f "host-id h2"')          # NOT "pkill -f agent.py": that would kill every agent
        time.sleep(dur - 5)
    elif name == "loss":
        h3.cmd('pkill -f "host-id h3"')
        agt = os.path.join(ROOT, "app", "agent.py")
        h3.cmd("python3 %s --host-id h3 --drop-rate 0.3 > /dev/null 2>&1 &" % agt)
        time.sleep(dur)
    else:
        time.sleep(dur + (3 if flows else 0))
    h5.cmd("pkill iperf3")
    return [iperf_mbps(f) for f in files]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, choices=SCENARIOS)
    ap.add_argument("--mode", required=True, choices=("combined", "baseline"))
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    if os.geteuid() != 0:
        sys.exit("run with sudo (Mininet needs root)")
    if not controller_up():
        sys.exit("controller not reachable on %s:%d - start: ryu-manager controller/stats_monitor.py" %
                 (C.CONTROLLER_IP, C.CONTROLLER_PORT))

    from mininet.net import Mininet                       # imported late so --help works anywhere
    from topology.topo import build, start_apps
    run_id = args.run_id or "%s_%s_%d" % (args.scenario, args.mode, int(time.time()))
    run_dir = os.path.join(ROOT, "experiments", "results", run_id)
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(C.LOG_DIR, exist_ok=True)
    for f in LOG_FILES:
        try: os.remove(os.path.join(C.LOG_DIR, f))
        except OSError: pass

    net = build(None)
    net.start()
    try: net.waitConnected(timeout=15)
    except Exception: print("warning: not all switches connected")
    start_apps(net)
    engine = subprocess.Popen([sys.executable, os.path.join(ROOT, "alerts", "alert_engine.py"), "--quiet"] +
                              (["--baseline"] if args.mode == "baseline" else []), cwd=ROOT)
    try:
        print("warm-up %ds ..." % WARMUP_S); time.sleep(WARMUP_S)
        t_start = time.time()
        print("scenario '%s' for %ds (%s mode) ..." % (args.scenario, args.duration, args.mode))
        iperf = run_scenario(net, args.scenario, args.duration, run_dir)
        t_end = time.time()
        print("cool-down %ds ..." % COOLDOWN_S); time.sleep(COOLDOWN_S)
    finally:
        engine.terminate()
        os.system("pkill -f app/agent.py; pkill -f app/server.py")
        net.stop()
    for f in LOG_FILES:
        src = os.path.join(C.LOG_DIR, f)
        if os.path.exists(src): shutil.copy(src, run_dir)
    meta = {"run_id": run_id, "scenario": args.scenario, "mode": args.mode, "duration": args.duration,
            "t_start": t_start, "t_end": t_end, "cooldown": COOLDOWN_S, "iperf_mbps": iperf,
            "link_capacity_mbps": C.LINK_CAPACITY_MBPS}
    json.dump(meta, open(os.path.join(run_dir, "meta.json"), "w"), indent=1)
    print("saved ->", run_dir)


if __name__ == "__main__":
    main()
