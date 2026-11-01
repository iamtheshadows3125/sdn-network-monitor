# Test log v1.0  (fill with real results / screenshots)
Controller running first: `ryu-manager controller/stats_monitor.py`
| # | Test | How | Expected | Result |
|---|---|---|---|---|
| 1 | Mock GUI | `python3 gui/mock_feed.py &` + `python3 gui/server.py --log-dir /tmp/netmon_mock` | colours change through the 60 s loop | |
| 2 | Real GUI, idle | full system + `python3 alerts/alert_engine.py` + `python3 gui/server.py` | all green, NORMAL | |
| 3 | Real GUI, heavy | mininet> `h5 iperf3 -s -D`, `h1 iperf3 -c 10.0.0.5 -t 20` | s1-s2 / s2-s3 turn red, alert in table | |
| 4 | Single experiment | `sudo python3 experiments/run_experiment.py --scenario heavy --mode combined` | folder in experiments/results/ with meta.json + csvs | |
| 5 | Full experiment set | `sudo python3 experiments/run_all.py --repeats 3` | 36 run folders | |
| 6 | Analysis | `python3 experiments/analyze_results.py` | runs.csv, summary_by_scenario.csv, 5+ png graphs in experiments/summary/ | |
| 7 | Fresh-clone reproduction | all three members, new clone, README only | everything runs | |
