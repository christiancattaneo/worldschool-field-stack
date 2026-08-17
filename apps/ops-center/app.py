#!/usr/bin/env python3
"""School Operations Center.

One pane of glass for a World School site: power, water, and connectivity in a
single readiness view. It reuses the same engines as the standalone dashboards
(solar sizing, the water sensor) plus a light link simulator, and rolls them
into one status: Operational, Degraded, or Critical. stdlib only, offline-first.

Run:  python3 app.py [--port 8055]
Open: http://127.0.0.1:8055
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SITES = ROOT / "sites"
sys.path.insert(0, str(ROOT / "skills" / "solar-sizing"))
sys.path.insert(0, str(ROOT / "mcp" / "water-sensor"))
import solar_size  # noqa: E402
import server as sensor  # noqa: E402

SITE = json.loads((SITES / "kenya-sample.json").read_text())
_BATTERY_SOC = {"v": 0.78}   # state of charge, drifts over time
_LINK = {"online": True}


def power_status() -> dict:
    monthly, source = solar_size.get_irradiance(SITE["latitude"], SITE["longitude"], offline=True)
    sizing = solar_size.size_system(SITE, monthly)
    # Model generation by time of day (sun curve) and drift the battery SoC.
    hour = datetime.now(timezone.utc).hour
    sun = max(0.0, math.sin((hour - 6) / 12 * math.pi))  # 0 at night, ~1 midday
    gen_w = round(sizing["pv_installed_wp"] * sun * 0.8)
    load_w = round(sum(l["watts"] * l["qty"] for l in SITE["loads"]) * 0.4)
    soc = _BATTERY_SOC["v"] + (0.02 if gen_w > load_w else -0.015) + random.uniform(-0.01, 0.01)
    _BATTERY_SOC["v"] = max(0.15, min(1.0, soc))
    state = "ok" if _BATTERY_SOC["v"] > 0.35 else ("warn" if _BATTERY_SOC["v"] > 0.2 else "crit")
    return {"battery_soc": round(_BATTERY_SOC["v"] * 100), "gen_w": gen_w, "load_w": load_w,
            "array_w": sizing["pv_installed_wp"], "irradiance_source": source, "state": state}


def water_status() -> dict:
    r = sensor.read_sensor()
    a = sensor.assess(r["turbidity_ntu"], r["ph"], r["tds_ppm"], r.get("temp_c", 20.0))
    state = "ok" if a["safe_without_treatment"] else "crit"
    return {"safe": a["safe_without_treatment"], "verdict": a["verdict"], "turbidity_ntu": r["turbidity_ntu"],
            "ph": r["ph"], "tds_ppm": r["tds_ppm"], "source": r["source"], "state": state}


def link_status() -> dict:
    if random.random() < 0.12:
        _LINK["online"] = not _LINK["online"]
    online = _LINK["online"]
    latency = random.randint(35, 80) if online else 0
    state = "ok" if online else "warn"  # offline is degraded, not critical: academics continue
    return {"online": online, "latency_ms": latency, "state": state}


def overview() -> dict:
    power = power_status()
    water = water_status()
    link = link_status()
    states = [power["state"], water["state"], link["state"]]
    if "crit" in states:
        overall = "CRITICAL"
    elif "warn" in states:
        overall = "DEGRADED"
    else:
        overall = "OPERATIONAL"
    return {"site": SITE["name"], "country": SITE["country"], "overall": overall,
            "power": power, "water": water, "link": link,
            "ts": time.strftime("%H:%M:%S")}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/overview":
            self._send(200, json.dumps(overview()).encode(), "application/json")
        else:
            self._send(404, b'{"error":"not found"}', "application/json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8055)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Ops center on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
