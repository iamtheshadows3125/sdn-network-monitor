# Shared contract (Person 1 proposes, everyone agrees on Day 1)
Source of truth in code: `app/common.py`. Changing anything below = tell the group + update this file in the same commit.

| Item | Value | Used by |
|---|---|---|
| Hosts / IPs | h1-h5 = 10.0.0.1-10.0.0.5 (/24) | all |
| Agents / server | agents on h1-h4, server on h5, UDP port 5005 | P2 baseline, P3 harness |
| Telemetry interval | 1.0 s; host DOWN after 3 s silence | P2, P3 |
| Packet (UDP payload, JSON) | `{host, seq, ts, tx_bytes, rx_bytes}`; seq starts at 1; ts = Unix epoch float; bytes cumulative | P2, P3 |
| Controller | OpenFlow 1.3, 127.0.0.1:6653, class `MonitorController`, dict `self.datapaths` | P2 extends it |
| DPIDs | s1=1, s2=2, s3=3 | P2 |
| Port map | s1: 1=h1 2=h2 3=s2 / s2: 1=h3 2=h4 3=s1 4=s3 / s3: 1=h5 2=s2 | P2 (per-link utilization), P3 (GUI link names) |
| Link capacity | 10 Mbps on every link (TCLink) | P2 utilization formula |
| Files | `logs/telemetry.csv`, `logs/hosts_state.json` | P2, P3 |
| telemetry.csv columns | recv_ts, host, seq, send_ts, tx_bytes, rx_bytes, lost_since_last | P3 harness |
| hosts_state.json | `{updated, hosts:{hN:{ip, liveness UP/DOWN, last_seen, packets_received, packets_lost, loss_pct, tx_bytes, rx_bytes, tx_rate_mbps, rx_rate_mbps}}}` written atomically every 1 s | P2, P3 GUI |
| Timestamps | Unix epoch seconds (float), one machine so clocks agree | all |
| Status labels (P2 owns, defined later) | NORMAL / WARNING / ALERT | P2, P3 |
| Run from | repo root; entry points `topology/topo.py` (flags `--no-apps`, `--pingall`), `app/agent.py`, `app/server.py` | all |

# Stage 2 additions (Person 2: monitoring and analysis)
Source of truth in code: `app/common.py` (section "Added in Stage 2"). Same rule as above: change a value here = tell the group + update this file in the same commit.

| Item | Value | Used by |
|---|---|---|
| Controller app | `controller/stats_monitor.py` (Ryu), polls every `POLL_INTERVAL_S` = 2.0 s with OFPPortStatsRequest and OFPFlowStatsRequest | P2 |
| Alert engine | `alerts/alert_engine.py`; modes: default (combined), `--baseline` (host telemetry only), `--once` | P2, P3 |
| Thresholds | `config/thresholds.json`: warning_pct 50, alert_pct 80, loss_warning_pct 5, loss_alert_pct 20, interval_s 1.0, stale_after_s 6.0 | P2, P3 |
| Status labels | NORMAL / WARNING / ALERT; UNKNOWN when the input data is stale | P2, P3 GUI |
| Link names | `link_id(dpid, peer)` gives sorted names: h1-s1, h2-s1, h3-s2, h4-s2, h5-s3, s1-s2, s2-s3 | P2, P3 |
| Utilization | max(tx_rate, rx_rate) / 10 Mbps x 100, rates from byte-counter deltas between polls | P2 |
| port_stats.json | `{updated, ports:[{dpid, port, peer, ts, tx_bytes, rx_bytes, tx_packets, rx_packets, tx_dropped, rx_dropped}], flows:{dpid:{flows, packets, bytes}}}` written by the controller | P2 |
| status.json (GUI feed) | `{updated, mode, controller_stale, app_stale, links:{id:{utilization_pct, tx_rate_mbps, rx_rate_mbps, status}}, hosts:{hN:{liveness, loss_pct, tx_rate_mbps, status}}, alerts, thresholds, overall}` rewritten every second | P3 GUI |
| alerts.csv | one row per alert state change; columns: ts,level,type,target,value,message | P2, P3 |
| analysis.csv | every cycle, every link/host; columns: ts, mode, kind, target, value, level | P2 |
| port_stats.csv | controller counters appended; columns: ts, dpid, port, peer, tx_bytes, rx_bytes, tx_dropped, rx_dropped | P2 |
| Hand-restarting agents | at the `mininet>` prompt use `--host-id=hN` (with `=`); the CLI replaces a lone `hN` word with its IP | all |
