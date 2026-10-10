#!/usr/bin/env python3
r"""
Mininet topology (linear, loop-free so a plain learning switch is safe):

  h1 --\                                   
        s1 ---- s2 ---- s3 -- h5 (monitoring server)
  h2 --/        /  \
          h3 --'    '-- h4

Start the controller first (ryu-manager controller/monitor_controller.py), then:
    sudo python3 topology/topo.py            # starts server + agents, opens CLI
    sudo python3 topology/topo.py --no-apps  # topology only
    sudo python3 topology/topo.py --pingall  # connectivity test before the CLI
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController

from app import common as C


def build(args):
    net = Mininet(controller=None, switch=OVSKernelSwitch, link=TCLink, autoSetMacs=True)
    net.addController("c0", controller=RemoteController, ip=C.CONTROLLER_IP, port=C.CONTROLLER_PORT)
    s = {n: net.addSwitch(n, dpid="%016x" % d, protocols="OpenFlow13") for n, d in C.DPIDS.items()}
    h = {n: net.addHost(n, ip=ip + "/24") for n, ip in C.HOSTS.items()}
    bw = C.LINK_CAPACITY_MBPS
    # Ports are given explicitly so they ALWAYS match C.PORT_MAP.
    net.addLink(h["h1"], s["s1"], port2=1, bw=bw)
    net.addLink(h["h2"], s["s1"], port2=2, bw=bw)
    net.addLink(h["h3"], s["s2"], port2=1, bw=bw)
    net.addLink(h["h4"], s["s2"], port2=2, bw=bw)
    net.addLink(h["h5"], s["s3"], port2=1, bw=bw)
    net.addLink(s["s1"], s["s2"], port1=3, port2=3, bw=bw)
    net.addLink(s["s2"], s["s3"], port1=4, port2=2, bw=bw)
    return net


def start_apps(net):
    os.makedirs(C.LOG_DIR, exist_ok=True)
    srv = os.path.join(C.REPO_ROOT, "app", "server.py")
    agt = os.path.join(C.REPO_ROOT, "app", "agent.py")
    net.get(C.SERVER_HOST).cmd(f"python3 {srv} --quiet --log-dir {C.LOG_DIR} > {C.LOG_DIR}/server.out 2>&1 &")
    time.sleep(1)
    for name in C.AGENT_HOSTS:
        net.get(name).cmd(f"python3 {agt} --host-id {name} > {C.LOG_DIR}/agent_{name}.out 2>&1 &")
    info("*** server on %s and agents on %s started; logs in %s\n" % (C.SERVER_HOST, C.AGENT_HOSTS, C.LOG_DIR))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-apps", action="store_true", help="do not start server/agents")
    ap.add_argument("--pingall", action="store_true")
    args = ap.parse_args()
    setLogLevel("info")
    net = build(args)
    net.start()
    try:
        net.waitConnected(timeout=15)
    except Exception:
        info("*** warning: switches did not all connect - is ryu-manager running?\n")
    if args.pingall:
        net.pingAll()
    if not args.no_apps:
        start_apps(net)
    CLI(net)
    os.system("pkill -f app/agent.py; pkill -f app/server.py")
    net.stop()


if __name__ == "__main__":
    main()
