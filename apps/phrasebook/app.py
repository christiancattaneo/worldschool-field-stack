#!/usr/bin/env python3
"""Offline build-crew phrasebook.

The job-site phrasebook the cohort needs in Kenya (Swahili) and Ecuador
(Spanish): electrical, water, medical, and worksite terms. Search and browse by
category, big readable cards for the field. Fully offline. stdlib only.

Run:  python3 app.py [--port 8059]
Open: http://127.0.0.1:8059
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
PHRASES = json.loads((HERE / "phrases.json").read_text())["phrases"]
CATS = []
for p in PHRASES:
    if p["cat"] not in CATS:
        CATS.append(p["cat"])


def search(cat: str, q: str) -> list[dict]:
    q = q.lower().strip()
    out = []
    for p in PHRASES:
        if cat and cat != "all" and p["cat"] != cat:
            continue
        if q and not any(q in p[k].lower() for k in ("en", "sw", "es")):
            continue
        out.append(p)
    return out


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
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif parsed.path == "/api/phrases":
            qs = parse_qs(parsed.query)
            cat = qs.get("cat", ["all"])[0]
            q = qs.get("q", [""])[0]
            self._json({"cats": CATS, "phrases": search(cat, q), "total": len(PHRASES)})
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8059)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Phrasebook on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
