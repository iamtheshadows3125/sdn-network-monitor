# Setup (Ubuntu 22.04 VM, 4 GB RAM, 2 CPUs)
```
sudo apt update && sudo apt upgrade -y
sudo apt install -y mininet openvswitch-switch iperf3 git python3-pip wireshark
git clone <REPO_URL> && cd sdn-network-monitor
pip3 install -r requirements.txt
ryu-manager --version      # must print a version, not an error
sudo mn --test pingall     # Mininet sanity check
```
If `ryu-manager` fails with an eventlet error: `pip3 install eventlet==0.30.2`.
If it fails with pkg_resources/setuptools: `pip3 install setuptools==67.6.1`.
All three members use the SAME Ubuntu version and these pinned packages.
