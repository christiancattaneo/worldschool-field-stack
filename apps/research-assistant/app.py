#!/usr/bin/env python3
"""Field Research Assistant (Claude-powered chatbot).

A research mentor for the cohort: turns a curiosity into a sharp question, names
what evidence would confirm it, points to primary sources, and applies the
source-evaluation rubric. It will not fabricate citations. Multi-turn chat,
history kept on the client. Uses the shared Claude client (claude-opus-4-8).

Run:  python3 app.py [--port 8060]
Open: http://127.0.0.1:8060
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

SYSTEM = (
    "You are a sharp, encouraging research mentor for high school students in the "
    "Alpha World School program, who do real field research in Kenya and Ecuador and "
    "aim to publish a peer-reviewed paper. Your job is method, not answers: help them "
    "turn a curiosity into a focused, researchable question. For any claim, name what "
    "evidence would confirm or refute it and where to find PRIMARY sources. Apply the "
    "source-evaluation rubric out loud when relevant: authority, currency, methodology, "
    "bias, primary vs secondary. Steelman the strongest counterargument. Never invent "
    "citations, authors, or statistics; if you are unsure, say so and tell them exactly "
    "how to verify. Keep replies concise and practical. Do not use emojis."
)
MAX_TURNS = 16  # cap history sent to the model to bound cost


def reply(messages: list[dict]) -> dict:
    if not (claude_client and claude_client.available()):
        return {"reply": "Research assistant is offline: no ANTHROPIC_API_KEY found. "
                         "Add it to .env.local to enable Claude. The tutor and dashboards still work offline.",
                "available": False}
    clean = [{"role": m["role"], "content": str(m["content"])[:4000]}
             for m in messages if m.get("role") in ("user", "assistant")][-MAX_TURNS:]
    try:
        text = claude_client.ask(clean, system=SYSTEM, max_tokens=700, effort="high")
        return {"reply": text, "available": True}
    except claude_client.ClaudeError as exc:
        return {"reply": f"(Claude error, try again: {exc})", "available": True}


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
        if urlparse(self.path).path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "bad json"}, 400)
                return
            self._json(reply(body.get("messages", [])))
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8060)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Research assistant on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
