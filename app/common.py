"""
SHARED CONTRACT - Person 2 and Person 3 import this file.
Do NOT rename or change existing names/values without telling the whole group
and updating docs/spec.md in the same commit. New names may be added.
"""
import json
import os

# ---- Addressing -----------------------------------------------------------
HOSTS = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3",
         "h4": "10.0.0.4", "h5": "10.0.0.5"}
AGENT_HOSTS = ["h1", "h2", "h3", "h4"]      # run UDP telemetry agents
SERVER_HOST = "h5"                          # runs the monitoring server
SERVER_IP = HOSTS[SERVER_HOST]
SERVER_PORT = 5005                          # UDP

# ---- Telemetry timing -----------------------------------------------------
TELEMETRY_INTERVAL_S = 1.0                  # agent send period
SILENT_TIMEOUT_S = 3 * TELEMETRY_INTERVAL_S # no packet for this long -> DOWN

# ---- Network model --------------------------------------------------------
LINK_CAPACITY_MBPS = 10                     # every link is shaped to this (TCLink)
CONTROLLER_IP = "127.0.0.1"
CONTROLLER_PORT = 6653                      # ryu-manager default, OpenFlow 1.3
DPIDS = {"s1": 1, "s2": 2, "s3": 3}         # datapath IDs seen by the controller

# PORT_MAP[dpid][port_no] -> what that port connects to.
# Person 2 uses this to turn per-port byte counters into per-link utilization.
PORT_MAP = {
    1: {1: "h1", 2: "h2", 3: "s2"},
    2: {1: "h3", 2: "h4", 3: "s1", 4: "s3"},
    3: {1: "h5", 2: "s2"},
}

# ---- Files (all relative to repo root) -----------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(REPO_ROOT, "logs")
TELEMETRY_CSV = os.path.join(LOG_DIR, "telemetry.csv")
HOSTS_STATE_JSON = os.path.join(LOG_DIR, "hosts_state.json")

# ---- Telemetry packet (UDP payload = one JSON object) ---------------------
# {"host": "h1", "seq": 17, "ts": 1730000000.123, "tx_bytes": 123456, "rx_bytes": 98765}
#   seq      starts at 1, +1 per packet (gaps = loss)
#   ts       sender wall-clock, Unix epoch seconds (float)
#   tx_bytes cumulative bytes transmitted by the host's interface
#   rx_bytes cumulative bytes received by the host's interface
PACKET_FIELDS = ("host", "seq", "ts", "tx_bytes", "rx_bytes")


def encode_packet(host, seq, ts, tx_bytes, rx_bytes):
    return json.dumps({"host": host, "seq": seq, "ts": ts,
                       "tx_bytes": tx_bytes, "rx_bytes": rx_bytes}).encode()


def decode_packet(data):
    """Return the packet dict, or None if malformed."""
    try:
        pkt = json.loads(data.decode())
        if not all(k in pkt for k in PACKET_FIELDS):
            return None
        pkt["seq"] = int(pkt["seq"])
        pkt["ts"] = float(pkt["ts"])
        pkt["tx_bytes"] = int(pkt["tx_bytes"])
        pkt["rx_bytes"] = int(pkt["rx_bytes"])
        return pkt
    except (ValueError, UnicodeDecodeError, TypeError, AttributeError):
        return None
