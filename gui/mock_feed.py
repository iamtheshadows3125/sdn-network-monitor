#!/usr/bin/env python3
"""Writes FAKE status.json / alerts.csv (same format as alerts/alert_engine.py) so you can build and
demo the GUI before Stage 2 is finished.   Uses /tmp/netmon_mock so it never touches the real logs/.
    python3 gui/mock_feed.py &
    python3 gui/server.py --log-dir /tmp/netmon_mock
60 s loop: normal -> WARNING on the main path -> ALERT -> host h2 down -> normal."""
import argparse
import csv
import json
import os
import random
import time

LINKS = ["h1-s1", "h2-s1", "h3-s2", "h4-s2", "h5-s3", "s1-s2", "s2-s3"]
HOSTS = ["h1", "h2", "h3", "h4"]


def lvl(v, w=50, a=80):
    return "ALERT" if v >= a else "WARNING" if v >= w else "NORMAL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", default="/tmp/netmon_mock")
    args = ap.parse_args()
    os.makedirs(args.log_dir, exist_ok=True)
    alerts_path = os.path.join(args.log_dir, "alerts.csv")
    with open(alerts_path, "w", newline="") as f:
        csv.writer(f).writerow(["ts", "level", "type", "target", "value", "message"])
    last, t0 = {}, time.time()
    while True:
        now = time.time()
        ph = (now - t0) % 60
        busy = {"s1-s2", "s2-s3", "h1-s1", "h5-s3"}
        links = {}
        for l in LINKS:
            u = random.uniform(2, 8)
            if 10 <= ph < 20 and l in busy: u = random.uniform(52, 60)
            if 20 <= ph < 35 and l in busy: u = random.uniform(90, 97)
            links[l] = {"utilization_pct": round(u, 2), "tx_rate_mbps": round(u / 10, 3),
                        "rx_rate_mbps": round(u / 20, 3), "status": lvl(u)}
        hosts = {h: {"liveness": "DOWN" if (h == "h2" and 35 <= ph < 45) else "UP", "loss_pct": 0.0,
                     "tx_rate_mbps": round(random.uniform(.01, .05), 3), "status": "NORMAL"} for h in HOSTS}
        hosts["h2"]["status"] = "ALERT" if hosts["h2"]["liveness"] == "DOWN" else "NORMAL"
        alerts = [{"type": "link_utilization", "target": k, "level": v["status"], "value": v["utilization_pct"],
                   "message": "link %s utilization %.1f%%" % (k, v["utilization_pct"])}
                  for k, v in links.items() if v["status"] != "NORMAL"]
        alerts += [{"type": "host_down", "target": k, "level": "ALERT", "value": None,
                    "message": "host %s silent" % k} for k, v in hosts.items() if v["status"] == "ALERT"]
        overall = max([x["status"] for x in list(links.values()) + list(hosts.values())],
                      key=["NORMAL", "WARNING", "ALERT"].index)
        status = {"updated": now, "mode": "combined", "overall": overall, "controller_stale": False,
                  "app_stale": False, "links": links, "hosts": hosts, "alerts": alerts, "thresholds": {}}
        tmp = os.path.join(args.log_dir, "status.json.tmp")
        with open(tmp, "w") as f: json.dump(status, f)
        os.replace(tmp, os.path.join(args.log_dir, "status.json"))
        active = {(a["type"], a["target"]): a for a in alerts}
        rows = [[round(now, 3), a["level"], k[0], k[1], a["value"], a["message"]]
                for k, a in active.items() if last.get(k) != a["level"]]
        rows += [[round(now, 3), "RESOLVED", k[0], k[1], "", "%s %s back to normal" % k] for k in last if k not in active]
        last = {k: a["level"] for k, a in active.items()}
        if rows:
            with open(alerts_path, "a", newline="") as f: csv.writer(f).writerows(rows)
        time.sleep(1)


if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
