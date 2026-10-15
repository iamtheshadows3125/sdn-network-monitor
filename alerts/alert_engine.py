#!/usr/bin/env python3
"""
Central analysis. Reads
   logs/port_stats.json   (controller: raw switch port counters)   <- SDN view
   logs/hosts_state.json  (server: what the agents report)          <- application view
computes link utilization, applies thresholds, and writes
   logs/status.json (GUI feed), logs/alerts.csv (state changes), logs/analysis.csv (every cycle).

    python3 alerts/alert_engine.py              # combined mode (SDN stats + app telemetry)
    python3 alerts/alert_engine.py --baseline   # app-only baseline (ignores controller stats)
    python3 alerts/alert_engine.py --once       # one cycle, then exit (for tests)
Run from the repo root.
"""
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import common as C

LEVEL_ORDER = {"UNKNOWN": -1, "NORMAL": 0, "WARNING": 1, "ALERT": 2}
DEFAULTS = {"warning_pct": 50, "alert_pct": 80, "loss_warning_pct": 5,
            "loss_alert_pct": 20, "interval_s": 1.0, "stale_after_s": 6.0}


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_thresholds(path=None):
    thr = dict(DEFAULTS)
    data = load_json(path or C.THRESHOLDS_JSON)
    if isinstance(data, dict):
        thr.update(data)
    return thr


def level_for(value, warn, alert):
    return "ALERT" if value >= alert else "WARNING" if value >= warn else "NORMAL"


def worst(levels):
    levels = [l for l in levels if l != "UNKNOWN"]
    return max(levels, key=lambda l: LEVEL_ORDER[l]) if levels else "NORMAL"


class RateTracker:
    """Turns cumulative byte counters into Mbps using the delta between samples."""

    def __init__(self):
        self.prev, self.rates = {}, {}

    def update(self, snapshot):
        for p in (snapshot or {}).get("ports", []):
            key, ts = (p["dpid"], p["port"]), p["ts"]
            old = self.prev.get(key)
            if old is None:
                self.prev[key] = (ts, p["tx_bytes"], p["rx_bytes"])
                self.rates[key] = (0.0, 0.0)
            elif ts > old[0]:
                dt = ts - old[0]
                tx = max(0, p["tx_bytes"] - old[1]) * 8 / dt / 1e6
                rx = max(0, p["rx_bytes"] - old[2]) * 8 / dt / 1e6
                self.prev[key] = (ts, p["tx_bytes"], p["rx_bytes"])
                self.rates[key] = (tx, rx)

    def link_table(self):
        links = {}
        for (dpid, port), (tx, rx) in self.rates.items():
            peer = C.PORT_MAP.get(dpid, {}).get(port)
            if peer is None:
                continue
            lid = C.link_id(dpid, peer)
            util = max(tx, rx) / C.LINK_CAPACITY_MBPS * 100
            # inter-switch links are seen from both ends: keep the busier reading
            if lid not in links or util > links[lid]["utilization_pct"]:
                links[lid] = {"utilization_pct": round(util, 2),
                              "tx_rate_mbps": round(tx, 3), "rx_rate_mbps": round(rx, 3)}
        return links


def baseline_links(hosts_state):
    """App-only view: a host's own reported rate is the only link information."""
    links = {}
    host_link = {peer: C.link_id(dpid, peer) for dpid, ports in C.PORT_MAP.items()
                 for peer in ports.values() if peer.startswith("h")}
    for h, s in ((hosts_state or {}).get("hosts") or {}).items():
        if h in host_link:
            util = max(s["tx_rate_mbps"], s["rx_rate_mbps"]) / C.LINK_CAPACITY_MBPS * 100
            links[host_link[h]] = {"utilization_pct": round(util, 2),
                                   "tx_rate_mbps": s["tx_rate_mbps"], "rx_rate_mbps": s["rx_rate_mbps"]}
    return links


def build_status(hosts_state, links, thr, mode, now, controller_stale, app_stale):
    status = {"updated": now, "mode": mode, "controller_stale": controller_stale,
              "app_stale": app_stale, "links": {}, "hosts": {}, "alerts": [], "thresholds": thr}
    link_stale = controller_stale if mode == "combined" else app_stale
    for lid, l in sorted(links.items()):
        lvl = "UNKNOWN" if link_stale else level_for(l["utilization_pct"], thr["warning_pct"], thr["alert_pct"])
        status["links"][lid] = dict(l, status=lvl)
        if lvl in ("WARNING", "ALERT"):
            status["alerts"].append({"type": "link_utilization", "target": lid, "level": lvl,
                                     "value": l["utilization_pct"],
                                     "message": "link %s utilization %.1f%% (warning>=%s%%, alert>=%s%%)" % (
                                         lid, l["utilization_pct"], thr["warning_pct"], thr["alert_pct"])})
    for h, s in sorted(((hosts_state or {}).get("hosts") or {}).items()):
        if app_stale:
            lvl, atype, msg = "UNKNOWN", None, None
        elif s["liveness"] == "DOWN":
            lvl, atype, msg = "ALERT", "host_down", "host %s silent (no telemetry for >%ss)" % (h, C.SILENT_TIMEOUT_S)
        else:
            lvl = level_for(s["loss_pct"], thr["loss_warning_pct"], thr["loss_alert_pct"])
            atype, msg = "packet_loss", "host %s telemetry loss %.1f%%" % (h, s["loss_pct"])
        status["hosts"][h] = {"liveness": s["liveness"], "loss_pct": s["loss_pct"],
                              "tx_rate_mbps": s["tx_rate_mbps"], "status": lvl}
        if lvl in ("WARNING", "ALERT"):
            status["alerts"].append({"type": atype, "target": h, "level": lvl,
                                     "value": s["loss_pct"] if atype == "packet_loss" else None, "message": msg})
    status["overall"] = worst([x["status"] for x in status["links"].values()] +
                              [x["status"] for x in status["hosts"].values()])
    return status


class AlertLog:
    """Writes one row to alerts.csv whenever a link/host changes level."""

    def __init__(self, path):
        self.path, self.last = path, {}
        self.new = not os.path.exists(path) or os.path.getsize(path) == 0

    def process(self, status, now):
        active = {(a["type"], a["target"]): a for a in status["alerts"]}
        events = []
        for key, a in active.items():
            if self.last.get(key) != a["level"]:
                events.append([round(now, 3), a["level"], key[0], key[1], a["value"], a["message"]])
                self.last[key] = a["level"]
        for key in [k for k in self.last if k not in active]:
            events.append([round(now, 3), "RESOLVED", key[0], key[1], "", "%s %s back to normal" % key])
            del self.last[key]
        if events:
            with open(self.path, "a", newline="") as f:
                w = csv.writer(f)
                if self.new:
                    w.writerow(["ts", "level", "type", "target", "value", "message"])
                    self.new = False
                w.writerows(events)
        return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--log-dir", default=C.LOG_DIR)
    ap.add_argument("--thresholds", default=C.THRESHOLDS_JSON)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    d = args.log_dir
    os.makedirs(d, exist_ok=True)
    p_ports, p_hosts = os.path.join(d, "port_stats.json"), os.path.join(d, "hosts_state.json")
    p_status, p_analysis = os.path.join(d, "status.json"), os.path.join(d, "analysis.csv")
    alert_log = AlertLog(os.path.join(d, "alerts.csv"))
    tracker, mode = RateTracker(), "baseline" if args.baseline else "combined"
    an_new = not os.path.exists(p_analysis) or os.path.getsize(p_analysis) == 0

    while True:
        thr, now = load_thresholds(args.thresholds), time.time()
        hosts = load_json(p_hosts)
        ports = None if args.baseline else load_json(p_ports)
        app_stale = hosts is None or now - hosts.get("updated", 0) > thr["stale_after_s"]
        controller_stale = (not args.baseline) and (ports is None or now - ports.get("updated", 0) > thr["stale_after_s"])
        if args.baseline:
            links = baseline_links(hosts)
        else:
            tracker.update(ports)
            links = tracker.link_table()
        status = build_status(hosts, links, thr, mode, now, controller_stale, app_stale)
        tmp = p_status + ".tmp"
        with open(tmp, "w") as f:
            json.dump(status, f, indent=1)
        os.replace(tmp, p_status)
        with open(p_analysis, "a", newline="") as f:
            w = csv.writer(f)
            if an_new:
                w.writerow(["ts", "mode", "kind", "target", "value", "level"])
                an_new = False
            for lid, l in status["links"].items():
                w.writerow([round(now, 3), mode, "link", lid, l["utilization_pct"], l["status"]])
            for h, s in status["hosts"].items():
                w.writerow([round(now, 3), mode, "host", h, s["loss_pct"], s["status"]])
        for e in alert_log.process(status, now):
            print("[%s] %s  %s" % (time.strftime("%H:%M:%S", time.localtime(now)), e[1], e[5]), flush=True)
        if not args.quiet:
            line = " | ".join("%s %.0f%% %s" % (k, v["utilization_pct"], v["status"]) for k, v in status["links"].items())
            print("overall=%s  %s" % (status["overall"], line), flush=True)
        if args.once:
            break
        time.sleep(thr["interval_s"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
