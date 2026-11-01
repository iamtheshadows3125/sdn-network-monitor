#!/usr/bin/env python3
"""Tiny dashboard server (Python standard library only - nothing to install).
    python3 gui/server.py                      # reads logs/status.json + logs/alerts.csv
    python3 gui/server.py --log-dir /tmp/netmon_mock   # use with gui/mock_feed.py
Open http://localhost:8080 in a browser."""
import argparse
import csv
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def make_handler(log_dir):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            data = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif u.path == "/api/status":
                try:
                    with open(os.path.join(log_dir, "status.json")) as f:
                        self._send(200, f.read(), "application/json")
                except (OSError, ValueError):
                    self._send(200, json.dumps({"error": "no status.json yet - is alert_engine.py running?"}), "application/json")
            elif u.path == "/api/alerts":
                n = int(parse_qs(u.query).get("n", ["15"])[0])
                rows = []
                try:
                    with open(os.path.join(log_dir, "alerts.csv"), newline="") as f:
                        rows = list(csv.DictReader(f))[-n:][::-1]
                except OSError:
                    pass
                self._send(200, json.dumps(rows), "application/json")
            else:
                self._send(404, "not found", "text/plain")

        def log_message(self, *a):
            pass
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--log-dir", default=os.path.join(ROOT, "logs"))
    args = ap.parse_args()
    print("dashboard on http://localhost:%d  (reading %s)" % (args.port, args.log_dir))
    ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(args.log_dir)).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
