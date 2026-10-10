# SDN Network Monitor (CN Mini Project 6)

UDP telemetry agents + monitoring server + Ryu SDN controller in a Mininet network.
Stage 1 (v0.1) = foundation. See docs/spec.md for the shared contract.

## Run (needs 2 terminals, both from the repo root)
1. Controller:  `ryu-manager controller/monitor_controller.py`
2. Network + apps:  `sudo python3 topology/topo.py`   (add `--pingall` to test first)

In the Mininet CLI: `pingall`, `h1 ping -c3 h5`, `iperf h1 h5`.
Watch telemetry: `tail -f logs/telemetry.csv` or `cat logs/hosts_state.json`.
Inspect flow rules: `sudo ovs-ofctl -O OpenFlow13 dump-flows s1`.
Clean up after a crash: `sudo mn -c`.

See SETUP.md for installation.
