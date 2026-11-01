#!/usr/bin/env python3
"""
Turns experiments/results/<run>/ folders into metrics tables and graphs.
    python3 experiments/analyze_results.py                          # real results
    python3 experiments/analyze_results.py --results /tmp/synth     # try it on fake data first
Writes (into experiments/summary/ - commit these, results/ is git-ignored):
    runs.csv                  one row per run
    summary_by_scenario.csv   averaged per scenario and mode
    detection_latency.png, telemetry_loss.png, utilization_<scenario>.png
Metrics
    detect_any_s    seconds from scenario start to the first WARNING/ALERT (blank = never detected)
    detect_alert_s  seconds from scenario start to the first ALERT
    localized       was the real problem spot flagged? (link s1-s2 for traffic scenarios, h2 / h3 for host scenarios)
    false_alarms    alerts raised BEFORE the scenario started
    resolve_s       seconds after the scenario ended until the last alert resolved
    util_s1s2_pct / util_truth_pct / util_error_pct   engine's mean utilization of s1-s2 vs. iperf ground truth
    telemetry_loss_pct   telemetry packets lost (sequence gaps) during the scenario
    telemetry_pkts_per_s monitoring overhead on the network (agents -> server)
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED = {"moderate": "s1-s2", "heavy": "s1-s2", "aggregate": "s1-s2", "host_down": "h2", "loss": "h3", "idle": None}
POLL_REQUESTS_PER_S = 3 * 2 / 2.0     # 3 switches x (port + flow stats request) every 2 s (POLL_INTERVAL_S)


def rows(path):
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def analyze_run(d):
    m = json.load(open(os.path.join(d, "meta.json")))
    t0, t1 = m["t_start"], m["t_end"]
    alerts = rows(os.path.join(d, "alerts.csv"))
    analysis = rows(os.path.join(d, "analysis.csv"))
    tele = rows(os.path.join(d, "telemetry.csv"))
    out = {"run_id": m["run_id"], "scenario": m["scenario"], "mode": m["mode"]}

    inside = [a for a in alerts if t0 <= float(a["ts"]) <= t1 + m.get("cooldown", 10) and a["level"] != "RESOLVED"]
    out["detect_any_s"] = round(float(inside[0]["ts"]) - t0, 2) if inside else ""
    al = [a for a in inside if a["level"] == "ALERT"]
    out["detect_alert_s"] = round(float(al[0]["ts"]) - t0, 2) if al else ""
    exp = EXPECTED[m["scenario"]]
    out["localized"] = (any(a["target"] == exp for a in inside) if exp else "")
    out["false_alarms"] = sum(1 for a in alerts if float(a["ts"]) < t0 and a["level"] != "RESOLVED")
    res = [float(a["ts"]) for a in alerts if a["level"] == "RESOLVED" and float(a["ts"]) >= t1]
    out["resolve_s"] = round(max(res) - t1, 2) if res else ""

    vals = [float(r["value"]) for r in analysis if r["kind"] == "link" and r["target"] == "s1-s2"
            and t0 + 5 <= float(r["ts"]) <= t1 - 2]
    truth = None
    if m["scenario"] in ("moderate", "heavy", "aggregate") and all(x is not None for x in m["iperf_mbps"] or [None]):
        truth = min(100.0, sum(m["iperf_mbps"]) / m["link_capacity_mbps"] * 100)
    out["util_s1s2_pct"] = round(sum(vals) / len(vals), 1) if vals else ""
    out["util_truth_pct"] = round(truth, 1) if truth is not None else ""
    out["util_error_pct"] = round(abs(sum(vals) / len(vals) - truth), 1) if (vals and truth is not None) else ""

    win = [r for r in tele if t0 <= float(r["recv_ts"]) <= t1]
    lost = sum(int(r["lost_since_last"]) for r in win)
    out["telemetry_loss_pct"] = round(100.0 * lost / (len(win) + lost), 2) if (win or lost) else ""
    out["telemetry_pkts_per_s"] = round(len(win) / max(1e-9, t1 - t0), 2)
    out["stats_polls_per_s"] = POLL_REQUESTS_PER_S if m["mode"] == "combined" else 0
    return out


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(ROOT, "experiments", "results"))
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments", "summary"))
    args = ap.parse_args()
    dirs = sorted(os.path.join(args.results, x) for x in os.listdir(args.results)
                  if os.path.exists(os.path.join(args.results, x, "meta.json")))
    if not dirs: sys.exit("no runs found in " + args.results)
    os.makedirs(args.out, exist_ok=True)
    runs = [analyze_run(d) for d in dirs]
    cols = list(runs[0].keys())
    with open(os.path.join(args.out, "runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(runs)

    groups = defaultdict(list)
    for r in runs: groups[(r["scenario"], r["mode"])].append(r)
    summ = []
    for (sc, mode), rs in sorted(groups.items()):
        row = {"scenario": sc, "mode": mode, "runs": len(rs)}
        for c in cols[3:]:
            v = [num(r[c]) if c != "localized" else (1.0 if r[c] is True else 0.0 if r[c] is False else None) for r in rs]
            v = [x for x in v if x is not None]
            row[c] = round(sum(v) / len(v), 2) if v else ""
        summ.append(row)
    with open(os.path.join(args.out, "summary_by_scenario.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(summ[0].keys())); w.writeheader(); w.writerows(summ)
    print("wrote runs.csv and summary_by_scenario.csv in", args.out)
    for s in summ: print(s)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib missing (pip3 install matplotlib) - skipped graphs"); return
    scs = [s for s in ("idle", "moderate", "heavy", "aggregate", "host_down", "loss") if any(r["scenario"] == s for r in summ)]
    look = {(r["scenario"], r["mode"]): r for r in summ}

    def bars(metric, ylabel, title, fname):
        fig, ax = plt.subplots(figsize=(8, 4)); wd = 0.38
        for k, (mode, col) in enumerate((("combined", "#0e7c86"), ("baseline", "#f2a541"))):
            ys = [num(look.get((s, mode), {}).get(metric)) for s in scs]
            ax.bar([i + (k - .5) * wd for i in range(len(scs))], [y or 0 for y in ys], wd, label=mode, color=col)
            for i, y in enumerate(ys):
                if y is None: ax.text(i + (k - .5) * wd, 0.1, "none", ha="center", fontsize=8, rotation=90)
        ax.set_xticks(range(len(scs))); ax.set_xticklabels(scs); ax.set_ylabel(ylabel); ax.set_title(title); ax.legend()
        fig.tight_layout(); fig.savefig(os.path.join(args.out, fname), dpi=140); plt.close(fig)

    bars("detect_any_s", "seconds", "Time to first alert (lower is better)", "detection_latency.png")
    bars("telemetry_loss_pct", "% of telemetry packets", "Telemetry loss during scenario", "telemetry_loss.png")

    for sc in ("moderate", "heavy", "aggregate"):
        fig, ax = plt.subplots(figsize=(8, 4)); drawn = False
        for mode, target, col in (("combined", "s1-s2", "#0e7c86"), ("baseline", "h1-s1", "#f2a541")):
            ds = [d for d in dirs if json.load(open(os.path.join(d, "meta.json")))["scenario"] == sc
                  and json.load(open(os.path.join(d, "meta.json")))["mode"] == mode]
            if not ds: continue
            m = json.load(open(os.path.join(ds[0], "meta.json")))
            pts = [(float(r["ts"]) - m["t_start"], float(r["value"])) for r in rows(os.path.join(ds[0], "analysis.csv"))
                   if r["kind"] == "link" and r["target"] == target]
            if pts:
                ax.plot(*zip(*pts), label="%s mode: link %s" % (mode, target), color=col); drawn = True
        if drawn:
            ax.axhline(50, ls="--", c="#f2a541", lw=1); ax.axhline(80, ls="--", c="#c8553d", lw=1)
            ax.axvline(0, c="grey", lw=1)
            ax.set_xlabel("seconds since scenario start"); ax.set_ylabel("utilization (%)"); ax.set_ylim(0, 105)
            ax.set_title("Link utilization seen by each approach - %s scenario" % sc); ax.legend()
            fig.tight_layout(); fig.savefig(os.path.join(args.out, "utilization_%s.png" % sc), dpi=140)
        plt.close(fig)
    print("graphs saved in", args.out)


if __name__ == "__main__":
    main()
