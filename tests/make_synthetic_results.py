#!/usr/bin/env python3
"""Creates FAKE experiment results in the same format run_experiment.py produces, so you can write and
test experiments/analyze_results.py before the real system works.
    python3 tests/make_synthetic_results.py /tmp/synth
    python3 experiments/analyze_results.py --results /tmp/synth --out /tmp/synth_summary
The numbers are invented (they follow what we expect to see), so NEVER put them in the report."""
import csv
import json
import os
import random
import sys

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/synth"
WARM, DUR, COOL = 10, 30, 10


def lvl(v): return "ALERT" if v >= 80 else "WARNING" if v >= 50 else "NORMAL"


def util(sc, mode, link, t):          # t = seconds since scenario start
    on = 0 <= t < DUR
    ramp = min(1.0, max(0.0, (t + 0.5) / 2.0)) if on else 0
    base = random.uniform(1, 6)
    if sc == "moderate" and on:
        if link in ("s1-s2", "s2-s3", "h1-s1", "h5-s3"): return 52 * ramp + base * (1 - ramp)
    if sc == "heavy" and on:
        if link in ("s1-s2", "s2-s3", "h1-s1", "h5-s3"): return 94 * ramp + base * (1 - ramp)
    if sc == "aggregate" and on:
        if link in ("s1-s2", "s2-s3", "h5-s3"): return 97 * ramp + base * (1 - ramp)
        if link in ("h1-s1", "h2-s1"): return 58 * ramp + base * (1 - ramp)
    return base


for sc in ("idle", "moderate", "heavy", "aggregate", "host_down", "loss"):
    for mode in ("combined", "baseline"):
        run = "%s_%s_1" % (sc, mode); d = os.path.join(out, run); os.makedirs(d, exist_ok=True)
        t0 = 1_000_000.0 + WARM; t1 = t0 + DUR
        links = ["h1-s1", "h2-s1", "h3-s2", "h4-s2", "h5-s3"] + (["s1-s2", "s2-s3"] if mode == "combined" else [])
        an, al, last = [], [], {}
        for s in range(-WARM, DUR + COOL):
            ts = t0 + s
            if mode == "baseline" and s < 0: pass
            active = {}
            for l in links:
                u = util(sc, mode, l, s)
                if mode == "baseline" and l in ("s1-s2", "s2-s3"): continue
                an.append([round(ts, 3), mode, "link", l, round(u, 2), lvl(u)])
                if lvl(u) != "NORMAL": active[("link_utilization", l)] = (lvl(u), round(u, 1), "link %s utilization %.1f%%" % (l, u))
            for h in ("h1", "h2", "h3", "h4"):
                loss = 30.0 if (sc == "loss" and h == "h3" and 3 <= s < DUR) else 0.0
                down = sc == "host_down" and h == "h2" and 8 <= s
                lv = "ALERT" if down else lvl(loss * 3.3)  # 30% loss -> ALERT-ish
                lv = "ALERT" if down else ("ALERT" if loss >= 20 else "NORMAL")
                an.append([round(ts, 3), mode, "host", h, loss, lv])
                if lv != "NORMAL": active[("host_down" if down else "packet_loss", h)] = (lv, loss, "host %s problem" % h)
            for k, (lv, v, msg) in active.items():
                if last.get(k) != lv: al.append([round(ts + 1, 3), lv, k[0], k[1], v, msg]); last[k] = lv
            for k in [k for k in last if k not in active]:
                al.append([round(ts + 1, 3), "RESOLVED", k[0], k[1], "", "back to normal"]); del last[k]
        csv.writer(open(os.path.join(d, "analysis.csv"), "w", newline="")).writerows([["ts", "mode", "kind", "target", "value", "level"]] + an)
        csv.writer(open(os.path.join(d, "alerts.csv"), "w", newline="")).writerows([["ts", "level", "type", "target", "value", "message"]] + al)
        tele = [["recv_ts", "host", "seq", "send_ts", "tx_bytes", "rx_bytes", "lost_since_last"]]
        for s in range(-WARM, DUR + COOL):
            for h in ("h1", "h2", "h3", "h4"):
                if sc == "host_down" and h == "h2" and s >= 5: continue
                lost = 1 if (sc == "loss" and h == "h3" and random.random() < .3) or (sc in ("heavy", "aggregate") and 0 <= s < DUR and random.random() < .08) else 0
                tele.append([round(t0 + s + .1, 3), h, s + WARM + 1, round(t0 + s, 3), s * 1000, s * 900, lost])
        csv.writer(open(os.path.join(d, "telemetry.csv"), "w", newline="")).writerows(tele)
        mbps = {"moderate": [4.9], "heavy": [9.4], "aggregate": [4.7, 4.6]}.get(sc)
        json.dump({"run_id": run, "scenario": sc, "mode": mode, "duration": DUR, "t_start": t0, "t_end": t1,
                   "cooldown": COOL, "iperf_mbps": mbps or [], "link_capacity_mbps": 10}, open(os.path.join(d, "meta.json"), "w"))
print("synthetic results in", out)
