#!/usr/bin/env python3
"""Offline Community Health survey + dashboard.

An offline-first field data tool: collect household health responses with no
connection (saved locally to a JSONL file), then a dashboard aggregates them
live, and a sync button marks them uploaded when the link returns. Ties to the
community health study research example. stdlib only.

Run:  python3 app.py [--port 8057]
Open: http://127.0.0.1:8057
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
STORE = HERE / "responses.jsonl"

SCHEMA = [
    {"id": "household_size", "label": "People in household", "type": "number", "min": 1},
    {"id": "children_under5", "label": "Children under 5", "type": "number", "min": 0},
    {"id": "water_source", "label": "Main water source", "type": "select",
     "options": ["piped", "borehole", "well", "river", "rain"]},
    {"id": "minutes_to_water", "label": "Minutes to water source", "type": "number", "min": 0},
    {"id": "bed_net", "label": "Sleeps under a treated net", "type": "bool"},
    {"id": "fever_last_2wk", "label": "Fever in last 2 weeks", "type": "bool"},
    {"id": "minutes_to_clinic", "label": "Minutes to nearest clinic", "type": "number", "min": 0},
    {"id": "child_vaccinated", "label": "Under-5s vaccinated", "type": "bool"},
]
BOOL_IDS = {f["id"] for f in SCHEMA if f["type"] == "bool"}
NUM_IDS = {f["id"] for f in SCHEMA if f["type"] == "number"}


def load() -> list[dict]:
    if not STORE.exists():
        return []
    out = []
    for line in STORE.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"count": 0}
    def avg(key):
        vals = [r["answers"].get(key) for r in rows if isinstance(r["answers"].get(key), (int, float))]
        return round(sum(vals) / len(vals), 1) if vals else 0
    def pct(key):
        vals = [bool(r["answers"].get(key)) for r in rows]
        return round(100 * sum(vals) / len(vals)) if vals else 0
    water = {}
    for r in rows:
        w = r["answers"].get("water_source", "unknown")
        water[w] = water.get(w, 0) + 1
    pending = sum(1 for r in rows if not r.get("synced"))
    return {
        "count": n,
        "pending_sync": pending,
        "avg_household": avg("household_size"),
        "avg_children_u5": avg("children_under5"),
        "avg_minutes_to_clinic": avg("minutes_to_clinic"),
        "avg_minutes_to_water": avg("minutes_to_water"),
        "pct_bed_net": pct("bed_net"),
        "pct_fever": pct("fever_last_2wk"),
        "pct_vaccinated": pct("child_vaccinated"),
        "water_sources": water,
    }


def sanitize(answers: dict) -> dict:
    clean = {}
    for f in SCHEMA:
        v = answers.get(f["id"])
        if f["id"] in NUM_IDS:
            try:
                clean[f["id"]] = max(f.get("min", 0), float(v))
            except (TypeError, ValueError):
                clean[f["id"]] = 0
        elif f["id"] in BOOL_IDS:
            clean[f["id"]] = bool(v)
        else:
            opts = f.get("options", [])
            clean[f["id"]] = v if v in opts else (opts[0] if opts else None)
    return clean


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
        elif path == "/api/schema":
            self._json({"schema": SCHEMA})
        elif path == "/api/summary":
            self._json(aggregate(load()))
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        if path == "/api/submit":
            rec = {"answers": sanitize(body.get("answers", {})), "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "synced": False}
            with STORE.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            self._json({"ok": True, "summary": aggregate(load())})
        elif path == "/api/sync":
            rows = load()
            for r in rows:
                r["synced"] = True
            STORE.write_text("".join(json.dumps(r) + "\n" for r in rows))
            self._json({"ok": True, "synced": len(rows), "summary": aggregate(rows)})
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8057)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Health survey on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
