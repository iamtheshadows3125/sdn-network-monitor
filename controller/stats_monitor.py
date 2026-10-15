"""
Stage 2 controller: MonitorController (learning switch from Stage 1) + periodic
OpenFlow stats polling. It does NOT compute utilization - it only collects raw
counters and writes logs/port_stats.json; alerts/alert_engine.py does the maths.

Run from the repo root:   ryu-manager controller/stats_monitor.py
(Run THIS file, not monitor_controller.py - it already includes it.)
"""
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ryu.controller import ofp_event
from ryu.controller.handler import DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub

from app import common as C
from controller.monitor_controller import MonitorController


class StatsMonitor(MonitorController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.latest = {}         # {(dpid, port): record}
        self.flow_summary = {}   # {dpid: {"flows": n, "packets": n, "bytes": n}}
        os.makedirs(C.LOG_DIR, exist_ok=True)
        self._csv_new = not os.path.exists(C.PORT_STATS_CSV) or os.path.getsize(C.PORT_STATS_CSV) == 0
        self.poll_thread = hub.spawn(self._poll_loop)

    # ---- keep self.datapaths accurate when a switch disconnects ----
    @set_ev_cls(ofp_event.EventOFPStateChange, DEAD_DISPATCHER)
    def _on_dead(self, ev):
        dp = getattr(ev, "datapath", None)
        if dp is not None and self.datapaths.pop(dp.id, None) is not None:
            self.logger.info("switch disconnected: dpid=%s", dp.id)

    # ---- polling ----
    def _poll_loop(self):
        while True:
            for dp in list(self.datapaths.values()):
                parser, ofp = dp.ofproto_parser, dp.ofproto
                dp.send_msg(parser.OFPPortStatsRequest(dp, 0, ofp.OFPP_ANY))
                dp.send_msg(parser.OFPFlowStatsRequest(dp))
            hub.sleep(C.POLL_INTERVAL_S)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply(self, ev):
        dpid, now = ev.msg.datapath.id, time.time()
        peers = C.PORT_MAP.get(dpid, {})
        for st in ev.msg.body:
            if st.port_no not in peers:      # skip the LOCAL port etc.
                continue
            self.latest[(dpid, st.port_no)] = {
                "dpid": dpid, "port": st.port_no, "peer": peers[st.port_no], "ts": now,
                "tx_bytes": st.tx_bytes, "rx_bytes": st.rx_bytes,
                "tx_packets": st.tx_packets, "rx_packets": st.rx_packets,
                "tx_dropped": st.tx_dropped, "rx_dropped": st.rx_dropped}
        self._write_snapshot(dpid)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply(self, ev):
        # NOTE: assumes the reply fits in one message (true for our tiny flow tables).
        body = ev.msg.body
        self.flow_summary[ev.msg.datapath.id] = {
            "flows": len(body),
            "packets": sum(f.packet_count for f in body),
            "bytes": sum(f.byte_count for f in body)}

    # ---- output ----
    def _write_snapshot(self, dpid):
        ports = [self.latest[k] for k in sorted(self.latest)]
        snap = {"updated": max((p["ts"] for p in ports), default=time.time()), "ports": ports,
                "flows": {str(k): v for k, v in self.flow_summary.items()}}
        tmp = C.PORT_STATS_JSON + ".tmp"
        with open(tmp, "w") as f:
            json.dump(snap, f, indent=1)
        os.replace(tmp, C.PORT_STATS_JSON)       # atomic
        with open(C.PORT_STATS_CSV, "a", newline="") as f:
            w = csv.writer(f)
            if self._csv_new:
                w.writerow(["ts", "dpid", "port", "peer", "tx_bytes", "rx_bytes", "tx_dropped", "rx_dropped"])
                self._csv_new = False
            for p in ports:
                if p["dpid"] == dpid:
                    w.writerow([round(p["ts"], 3), p["dpid"], p["port"], p["peer"],
                                p["tx_bytes"], p["rx_bytes"], p["tx_dropped"], p["rx_dropped"]])
