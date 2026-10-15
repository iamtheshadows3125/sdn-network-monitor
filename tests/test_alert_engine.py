"""Offline unit tests (no Mininet/Ryu needed).  Run from repo root:  python3 -m unittest tests.test_alert_engine -v"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from alerts import alert_engine as A
from app import common as C

THR = dict(A.DEFAULTS)


def snap(ts, s1p3_tx):
    return {"updated": ts, "ports": [
        {"dpid": 1, "port": 3, "ts": ts, "tx_bytes": s1p3_tx, "rx_bytes": 0},
        {"dpid": 2, "port": 3, "ts": ts, "tx_bytes": 0, "rx_bytes": s1p3_tx}]}


def hosts(h1_liveness="UP", loss=0.0, tx=0.0):
    return {"updated": 100, "hosts": {"h1": {"liveness": h1_liveness, "loss_pct": loss,
            "tx_rate_mbps": tx, "rx_rate_mbps": 0.0}}}


class T(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(A.level_for(49.9, 50, 80), "NORMAL")
        self.assertEqual(A.level_for(50, 50, 80), "WARNING")
        self.assertEqual(A.level_for(80, 50, 80), "ALERT")

    def test_utilization_alert_and_dedupe(self):
        tr = A.RateTracker(); tr.update(snap(100.0, 0)); tr.update(snap(101.0, 1_250_000))  # 10 Mbps
        links = tr.link_table()
        self.assertAlmostEqual(links["s1-s2"]["utilization_pct"], 100.0, places=1)
        self.assertEqual(len(links), 1)   # both ends of s1-s2 collapse into one link

    def test_warning(self):
        tr = A.RateTracker(); tr.update(snap(100.0, 0)); tr.update(snap(101.0, 750_000))   # 6 Mbps
        st = A.build_status(hosts(), tr.link_table(), THR, "combined", 101.0, False, False)
        self.assertEqual(st["links"]["s1-s2"]["status"], "WARNING")
        self.assertEqual(st["overall"], "WARNING")

    def test_same_snapshot_twice_keeps_rate(self):
        tr = A.RateTracker(); tr.update(snap(100.0, 0)); tr.update(snap(101.0, 1_250_000)); tr.update(snap(101.0, 1_250_000))
        self.assertAlmostEqual(tr.link_table()["s1-s2"]["utilization_pct"], 100.0, places=1)

    def test_host_down_and_loss(self):
        st = A.build_status(hosts("DOWN"), {}, THR, "combined", 100, False, False)
        self.assertEqual(st["hosts"]["h1"]["status"], "ALERT"); self.assertEqual(st["overall"], "ALERT")
        st = A.build_status(hosts(loss=10), {}, THR, "combined", 100, False, False)
        self.assertEqual(st["hosts"]["h1"]["status"], "WARNING")

    def test_baseline_only_sees_access_links(self):
        links = A.baseline_links(hosts(tx=9.0))
        self.assertEqual(list(links), ["h1-s1"]); self.assertAlmostEqual(links["h1-s1"]["utilization_pct"], 90.0)

    def test_stale_controller_is_unknown(self):
        tr = A.RateTracker(); tr.update(snap(100.0, 0)); tr.update(snap(101.0, 1_250_000))
        st = A.build_status(hosts(), tr.link_table(), THR, "combined", 200, True, False)
        self.assertEqual(st["links"]["s1-s2"]["status"], "UNKNOWN"); self.assertEqual(st["overall"], "NORMAL")

    def test_alert_log_transitions(self):
        with tempfile.TemporaryDirectory() as d:
            log = A.AlertLog(os.path.join(d, "alerts.csv"))
            bad = A.build_status(hosts("DOWN"), {}, THR, "combined", 1, False, False)
            good = A.build_status(hosts("UP"), {}, THR, "combined", 2, False, False)
            self.assertEqual(log.process(bad, 1)[0][1], "ALERT")
            self.assertEqual(log.process(bad, 2), [])           # no repeat while unchanged
            self.assertEqual(log.process(good, 3)[0][1], "RESOLVED")

    def test_link_id(self):
        self.assertEqual(C.link_id(1, "h1"), "h1-s1"); self.assertEqual(C.link_id(3, "s2"), "s2-s3")


if __name__ == "__main__":
    unittest.main()
