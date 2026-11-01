#!/usr/bin/env python3
"""Runs every scenario in both modes (each in a fresh process), then you run analyze_results.py.
Controller must be running first (ryu-manager controller/stats_monitor.py).
    sudo python3 experiments/run_all.py              # 1 repeat  (~12 min)
    sudo python3 experiments/run_all.py --repeats 3  # better averages
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_experiment import SCENARIOS  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--repeats", type=int, default=1)
ap.add_argument("--duration", type=int, default=30)
ap.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
a = ap.parse_args()
for r in range(a.repeats):
    for sc in a.scenarios:
        for mode in ("combined", "baseline"):
            print("\n===== %s / %s / repeat %d =====" % (sc, mode, r + 1), flush=True)
            subprocess.call([sys.executable, os.path.join(HERE, "run_experiment.py"), "--scenario", sc,
                             "--mode", mode, "--duration", str(a.duration)])
print("\nAll runs finished. Next: python3 experiments/analyze_results.py")
