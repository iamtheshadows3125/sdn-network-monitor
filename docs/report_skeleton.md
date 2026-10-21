# Report skeleton (fill in as you go - the rubric has 6 marks for documentation + 5 for evaluation)
1. **Problem statement and objectives** (reuse the Phase 1 slides)
2. **Literature survey** (the papers you actually read, one paragraph each, gap -> our approach)
3. **System architecture** (diagram, components, data flow, shared formats - copy from docs/spec.md)
4. **Implementation**
   4.1 Mininet topology (diagram, IPs, port map, 10 Mbps links)
   4.2 UDP telemetry agents and server (packet format, loss and liveness detection)
   4.3 SDN controller (learning switch, stats polling, what OpenFlow messages are used)
   4.4 Analysis engine (utilization formula, thresholds, NORMAL/WARNING/ALERT, alert log)
   4.5 Dashboard
5. **Test cases** (docs/test_log_v0.1.md, v0.2, v1.0 tables, with screenshots)
6. **Challenging scenarios** (heavy congestion, aggregate congestion, host failure, telemetry loss: what happens and why)
7. **Performance evaluation** (metrics definitions from the header of experiments/analyze_results.py; experiments/summary graphs and tables; compare combined vs baseline; explain WHY)
8. **Discussion and limitations** (polling interval vs detection delay, 10 Mbps emulation, single-machine clocks, thresholds are static)
9. **How to reproduce** (SETUP.md + README commands)
10. **Individual contributions** (who did which stage - the Git history backs this up)
11. **References**
