# Test log v0.2 (Stage 2: monitoring and analysis)

| # | Test | Command | Expected | Result |
|---|---|---|---|---|
| 0 | Unit tests | `python3 -m unittest tests.test_alert_engine -v` | 9 tests pass | 9 tests OK |
| 1 | Stats collection | `ryu-manager controller/stats_monitor.py`, then `cat logs/port_stats.json` twice | per-port counters for s1-s3, growing every ~2 s | 8 ports and 3 switches listed; s1 port 1 tx_bytes 10735 then 11588 |
| 2 | Alert engine idle | `python3 alerts/alert_engine.py`, then `cat logs/status.json` | 7 links listed, all NORMAL | all 7 links NORMAL, utilization under 0.1% |
| 3 | Moderate load | `h5 iperf3 -s -D` then `h1 iperf3 -c 10.0.0.5 -u -b 5M -t 20` | WARNING at about 50% | WARNING at 51.5-51.6% on h1-s1, s1-s2, s2-s3, h5-s3 (ts 1791993487.58); RESOLVED at 1791993505.66 |
| 4 | Heavy load | `h1 iperf3 -c 10.0.0.5 -t 20` | ALERT at 80% or more | ALERT at 94.2-94.4% on the same 4 links (ts 1791993555.872); RESOLVED at 1791993575.967 |
| 5 | Host silent | `h2 pkill -f "host-id h2"` then restart with `--host-id=h2` | ALERT host_down after about 3-5 s, RESOLVED after restart | ALERT at 1792045040.925, RESOLVED at 1792045086.169 |
| 6 | Packet loss | `h1 python3 app/agent.py --host-id=h1 --drop-rate 0.3 &` | loss near 30%, ALERT above 20% | WARNING at 7.14% (ts 1792045355.85), ALERT at 21.78% (ts 1792045364.896), RESOLVED at 1792045452.437 |
| 7 | Baseline mode | `python3 alerts/alert_engine.py --baseline`, then heavy load | only host-facing links visible; s1-s2 and s2-s3 missed | only h1-s1 alerted (93.98%, ts 1792045558.397); no alerts for s1-s2, s2-s3 or h5-s3; compare Test 4 where all 4 alerted |

## Notes
- Utilization = max(tx_rate, rx_rate) / 10 Mbps x 100, from byte-counter differences between polls.
- Thresholds (config/thresholds.json): warning 50%, alert 80%, loss warning 5%, loss alert 20%.
- Loss is cumulative on the server, so the reading climbs slowly toward the drop rate (21.8% was recorded before it reached 30%).
- When restarting an agent by hand at the `mininet>` prompt, use `--host-id=h2` (with `=`). The CLI replaces a lone `h2` word with 10.0.0.2, which makes the server create a separate 10.0.0.2 host and keeps h2 DOWN.
- Baseline vs combined: controller flow/port stats expose the inner links (s1-s2, s2-s3) that host telemetry alone cannot see.

Screenshots: add files under docs/screenshots/ and link them here.
