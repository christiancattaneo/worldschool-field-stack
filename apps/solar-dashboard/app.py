#!/usr/bin/env python3
"""Solar Microgrid operations dashboard.

A real web app students build to operate a field solar system: pick a site, pull
live irradiance, edit the loads, and watch the bill of materials resize. Wraps
the solar-sizing engine in a UI. stdlib only, so it runs with the broken pip and
in the field offline.

Run:  python3 app.py [--port 8051]
Open: http://127.0.0.1:8051
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # field-stack
SITES = ROOT / "sites"
sys.path.insert(0, str(ROOT / "skills" / "solar-sizing"))
import solar_size  # noqa: E402


def list_sites() -> list[dict]:
    out = []
    for p in sorted(SITES.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            out.append({"file": p.name, "name": data.get("name", p.stem), "country": data.get("country", "")})
        except json.JSONDecodeError:
            continue
    return out


def size_for(site: dict, offline: bool) -> dict:
    monthly, source = solar_size.get_irradiance(site["latitude"], site["longitude"], offline)
    sizing = solar_size.size_system(site, monthly)
    per_load = [
        {"name": l["name"], "wh": l["watts"] * l["qty"] * l["hours_per_day"], **l}
        for l in site["loads"]
    ]
    return {"site": site, "sizing": sizing, "monthly": monthly, "months": solar_size.MONTHS,
            "source": source, "per_load": per_load}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/sites":
            self._json(list_sites())
            return
        if parsed.path == "/api/size":
            q = parse_qs(parsed.query)
            fname = q.get("site", ["kenya-sample.json"])[0]
            offline = q.get("offline", ["0"])[0] == "1"
            path = SITES / fname
            if not path.exists():
                self._json({"error": "site not found"}, 404)
                return
            try:
                self._json(size_for(json.loads(path.read_text()), offline))
            except Exception as exc:  # noqa: BLE001
                self._json({"error": f"{exc.__class__.__name__}: {exc}"}, 500)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/size":
            length = int(self.headers.get("Content-Length", 0))
            try:
                site = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "bad json"}, 400)
                return
            q = parse_qs(parsed.query)
            offline = q.get("offline", ["1"])[0] == "1"  # edits default offline (fast)
            try:
                self._json(size_for(site, offline))
            except Exception as exc:  # noqa: BLE001
                self._json({"error": f"{exc.__class__.__name__}: {exc}"}, 500)
            return
        self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8051)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Solar dashboard on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
