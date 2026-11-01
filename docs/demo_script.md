# Final demo script (about 8 minutes) - rehearse it 2-3 times
Setup before the demo (3 terminals + browser, all from the repo folder):
1. `ryu-manager controller/stats_monitor.py`
2. `sudo python3 topology/topo.py`
3. `python3 alerts/alert_engine.py`
4. `python3 gui/server.py`  -> open http://localhost:8080
Each step: WHAT TO DO | WHAT TO SAY | WHAT TO SHOW
| # | Do | Say | Show |
|---|---|---|---|
| 1 | Open dashboard (idle) | "Four hosts send UDP telemetry to h5; the Ryu controller polls switch counters; the analysis combines both." | all green, NORMAL |
| 2 | `h1 ping -c3 h5`, `dump-flows s1` | "The controller installed flow rules; the SDN network is functional." | pings OK, flow table |
| 3 | `h5 iperf3 -s -D` then `h1 iperf3 -c 10.0.0.5 -u -b 5M -t 20` | "Moderate load: 50% utilization." | links turn amber, WARNING alert |
| 4 | `h1 iperf3 -c 10.0.0.5 -t 20` | "Heavy load saturates the path." | s1-s2, s2-s3 red, ALERT in table, chart rises |
| 5 | wait for it to finish | "Alerts resolve automatically." | RESOLVED rows |
| 6 | `h2 pkill -f "host-id h2"` | "Silent host detection from missing telemetry." | h2 turns red (DOWN) after ~3 s |
| 7 | Show `experiments/summary/` graphs | "Baseline = app-only monitoring. For two flows of 6 Mbps, baseline sees two 60% access links; the SDN view sees the shared link at ~100%." | utilization_aggregate.png, detection_latency.png |
| 8 | Show GitHub repo, tags v0.1 / v0.2 / v1.0 | "Everything is reproducible from the README." | repo |
Viva: each member must be able to explain EVERY row above.
