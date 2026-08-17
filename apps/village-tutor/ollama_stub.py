#!/usr/bin/env python3
"""Tiny Ollama API stub for verifying the village tutor's local-model path.

Mimics the two endpoints the tutor and a setup check touch:
  POST /api/generate  -> {"response": "..."}
  GET  /api/tags      -> {"models": [...]}

It is NOT a model. It exists so we can prove the tutor talks to a local model
server correctly without downloading gigabytes. For the real thing, install
Ollama (see LOCAL_MODEL.md) and point OLLAMA_URL at it instead.

Run:  python3 ollama_stub.py [--port 11500]
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/api/tags":
            self._json({"models": [{"name": "stub:latest"}]})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path == "/api/generate":
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            prompt = req.get("prompt", "")
            tail = prompt.split("Question:")[-1].strip()[:80]
            self._json({"model": req.get("model", "stub"), "done": True,
                        "response": f"[local-model stub] Here is a short answer about: {tail}"})
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=11500)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Ollama stub on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
