#!/bin/bash
# Congestion script: runs iperf3 traffic from h1 to h5 to saturate the 10 Mbps links
echo "Starting iperf3 server on h5 (10.0.0.5:5201)..."
echo "Run inside the Mininet CLI:"
echo "  h5 iperf3 -s -D"
echo "  h1 iperf3 -c 10.0.0.5 -u -b 15M -t 30"
