#!/usr/bin/env python3
"""Procurement and logistics planner.

Turn a bill of materials into a real landed-cost plan: line costs, total weight,
freight to Nairobi or Quito, duty and VAT estimate, and a grand total. The kind
of tool that decides whether a build is affordable before anyone ships a pallet.
stdlib only. All rates are labeled estimates, edit them in CATALOG and DEST.

Run:  python3 app.py [--port 8058]
Open: http://127.0.0.1:8058
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent

# sku: (label, unit_usd, weight_kg, category)
CATALOG = {
    "panel450": ("Solar panel 450 W", 165.0, 23.0, "power"),
    "batt12v200": ("Battery 12V 200Ah LiFePO4", 480.0, 19.0, "power"),
    "mppt60": ("MPPT charge controller 60 A", 210.0, 3.2, "power"),
    "inv5k": ("Pure-sine inverter 5 kW", 540.0, 14.0, "power"),
    "combiner": ("Combiner box + breakers", 120.0, 4.0, "power"),
    "wire6awg": ("DC cable 6 AWG, 30 m spool", 95.0, 6.5, "power"),
    "rail": ("Mounting rail set", 140.0, 12.0, "power"),
    "ground": ("Grounding kit", 45.0, 3.0, "power"),
    "starlink": ("Starlink kit", 599.0, 5.0, "connectivity"),
    "biosand": ("Biosand filter kit", 85.0, 18.0, "water"),
    "uv": ("UV water purifier (DC)", 175.0, 4.5, "water"),
    "watertest": ("Water test kit", 60.0, 1.5, "water"),
    "tank": ("Water storage tank 1000 L", 230.0, 22.0, "water"),
}

# destination: (label, freight_usd_per_kg, base_freight_usd, duty_pct, vat_pct, transit_days)
DEST = {
    "nairobi": ("Nairobi, Kenya", 9.5, 120.0, 0.25, 0.16, "10-21"),
    "quito": ("Quito, Ecuador", 8.0, 140.0, 0.20, 0.12, "12-24"),
}


def quote(items: list[dict], dest_key: str) -> dict:
    dest = DEST.get(dest_key, DEST["nairobi"])
    label, per_kg, base, duty_pct, vat_pct, transit = dest
    lines = []
    subtotal = weight = 0.0
    for it in items:
        sku, qty = it.get("sku"), int(it.get("qty", 0))
        if sku not in CATALOG or qty <= 0:
            continue
        name, unit, wkg, cat = CATALOG[sku]
        line_cost, line_wt = unit * qty, wkg * qty
        subtotal += line_cost
        weight += line_wt
        lines.append({"sku": sku, "name": name, "qty": qty, "unit": unit,
                      "line_cost": round(line_cost, 2), "line_weight": round(line_wt, 1), "category": cat})
    freight = base + per_kg * weight if lines else 0.0
    duty = subtotal * duty_pct
    vat = (subtotal + freight + duty) * vat_pct
    grand = subtotal + freight + duty + vat
    return {
        "destination": label, "transit_days": transit,
        "lines": lines,
        "subtotal": round(subtotal, 2),
        "weight_kg": round(weight, 1),
        "freight": round(freight, 2),
        "duty": round(duty, 2), "duty_pct": round(duty_pct * 100),
        "vat": round(vat, 2), "vat_pct": round(vat_pct * 100),
        "grand_total": round(grand, 2),
    }


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
        elif path == "/api/catalog":
            self._json({"catalog": [{"sku": k, "label": v[0], "unit": v[1], "weight": v[2], "category": v[3]}
                                    for k, v in CATALOG.items()],
                        "destinations": [{"key": k, "label": v[0]} for k, v in DEST.items()]})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path == "/api/quote":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            self._json(quote(body.get("items", []), body.get("dest", "nairobi")))
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8058)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Procurement planner on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
