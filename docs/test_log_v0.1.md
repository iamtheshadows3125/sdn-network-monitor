# Test log v0.1  (fill in with real output / screenshots before tagging)
| # | Test | Command | Expected | Result |
|---|---|---|---|---|
| 1 | Controller up | `ryu-manager controller/monitor_controller.py` | "switch connected" x3 |switch connected: dpid=1, dpid=2, dpid=3 |
| 2 | Connectivity | `sudo python3 topology/topo.py --pingall` | 0% dropped |0% dropped, (20/20 received) |
| 3 | Server receives all agents | `cat logs/hosts_state.json` | h1-h4 liveness UP | h1-h4 liveliness UP in hosts_state.json |
| 4 | Flow rules installed | `sudo ovs-ofctl -O OpenFlow13 dump-flows s1` | flows with in_port/eth_dst |Flows dumped on s1 showing acitons=OUTPUT |
| 5 | Loss detection | `h1 python3 app/agent.py --host-id h9 --drop-rate 0.3 &` | h9 loss_pct about 30 |h9 loss_pct: 30.94% (packets_rcv: 183, lost: 82) |
| 6 | Host silent | `h2 pkill -f "host-id h2"` then wait 4 s | h2 liveness DOWN |h2 liveliness down after 4 secs silence |
