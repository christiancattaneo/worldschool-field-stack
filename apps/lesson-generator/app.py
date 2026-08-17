#!/usr/bin/env python3
"""Lesson Plan Generator (Claude-powered).

The cohort teaches local kids. This generates a one-page, low-resource lesson
plan on any topic, at a chosen age, in English, Swahili, or Spanish, ready to
run in a classroom with no internet and solar power. Uses the shared Claude
client (claude-opus-4-8).

Run:  python3 app.py [--port 8061]
Open: http://127.0.0.1:8061
Needs ANTHROPIC_API_KEY in env or repo .env.local.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
try:
    import claude_client
except ImportError:
    claude_client = None

LANG_NAME = {"en": "English", "sw": "Swahili", "es": "Spanish"}


def generate(topic: str, age: int, lang: str) -> dict:
    if not (claude_client and claude_client.available()):
        return {"lesson": "Offline: no ANTHROPIC_API_KEY found. Add it to .env.local to enable lesson generation.",
                "available": False}
    name = LANG_NAME.get(lang, "English")
    system = (
        f"You are an experienced primary and secondary teacher writing for a rural, "
        f"low-resource classroom in Kenya or Ecuador: no internet, limited supplies, "
        f"solar power. Write the entire lesson in {name}. Keep it to one page. Use only "
        f"cheap, local materials. Be concrete and kind. Do not use emojis. "
        f"Use these sections with clear headings: Objective, Materials, Warm-up (5 min), "
        f"Teach (10-15 min), Practice (10 min), Check for understanding (5 min), and one "
        f"Extension for fast learners."
    )
    prompt = f"Write a lesson plan on '{topic}' for students about {age} years old."
    try:
        text = claude_client.ask([{"role": "user", "content": prompt}], system=system,
                                 max_tokens=900, effort="medium")
        return {"lesson": text, "available": True}
    except claude_client.ClaudeError as exc:
        return {"lesson": f"(Claude error, try again: {exc})", "available": True}


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
        elif path == "/api/health":
            self._json({"available": bool(claude_client and claude_client.available()),
                        "model": claude_client.DEFAULT_MODEL if claude_client else None})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path == "/api/generate":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "bad json"}, 400)
                return
            topic = str(body.get("topic", "")).strip()[:200] or "counting to ten"
            try:
                age = max(4, min(18, int(body.get("age", 9))))
            except (TypeError, ValueError):
                age = 9
            self._json(generate(topic, age, body.get("lang", "en")))
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8061)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Lesson generator on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
