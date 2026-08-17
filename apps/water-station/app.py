#!/usr/bin/env python3
"""Water Quality monitoring station.

A real web app students build to operate a field water source: poll the sensor
(live or simulated), gauge each reading against WHO limits, chart history, and
throw a loud UNSAFE banner when the water is not drinkable. Wraps the
water-sensor logic in a UI. stdlib only.

Run:  python3 app.py [--port 8052]
Open: http://127.0.0.1:8052
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "mcp" / "water-sensor"))
import server as sensor  # noqa: E402

HISTORY: deque = deque(maxlen=120)


def sample() -> dict:
    r = sensor.read_sensor()
    a = sensor.assess(r["turbidity_ntu"], r["ph"], r["tds_ppm"], r.get("temp_c", 20.0))
    rec = {**r, "assessment": a}
    HISTORY.append({"t": r["timestamp"], "turbidity_ntu": r["turbidity_ntu"], "ph": r["ph"],
                    "tds_ppm": r["tds_ppm"], "safe": a["safe_without_treatment"]})
    return rec


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/reading":
            self._json(sample())
        elif path == "/api/history":
            self._json({"history": list(HISTORY), "thresholds": sensor.THRESHOLDS,
                        "fault": os.environ.get("WATER_SENSOR_SIM_FAULT") == "1"})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/fault":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            os.environ["WATER_SENSOR_SIM_FAULT"] = "1" if body.get("on") else "0"
            self._json({"fault": os.environ["WATER_SENSOR_SIM_FAULT"] == "1"})
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8052)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Water station on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
