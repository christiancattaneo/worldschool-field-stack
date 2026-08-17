#!/usr/bin/env python3
"""Offline Village Tutor.

The leave-behind tutor for the local kids the cohort teaches. Trilingual
(English, Swahili, Spanish), works with zero internet from a bundled lesson
corpus, solves arithmetic, and can optionally pass free-form questions to a
local model (Ollama) when one is reachable. Low bandwidth on purpose.

Run:  python3 app.py [--port 8054]
Open: http://127.0.0.1:8054

Optional local model: set OLLAMA_URL (default http://localhost:11434/api/generate)
is tried only when OLLAMA_MODEL is set, with a short timeout, then it falls back
to the corpus. Nothing hangs if there is no model.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # field-stack root for claude_client
try:
    import claude_client
except ImportError:
    claude_client = None
CORPUS = json.loads((HERE / "corpus.json").read_text())["entries"]
LANGS = ("en", "sw", "es")
WORD = re.compile(r"[a-z']+")
MATH = re.compile(r"^\s*-?\d+(\.\d+)?\s*([+\-x*/])\s*-?\d+(\.\d+)?\s*$", re.I)


def try_math(q: str):
    if not MATH.match(q):
        return None
    expr = q.lower().replace("x", "*")
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)\s*", expr)
    a, op, b = float(m.group(1)), m.group(2), float(m.group(3))
    try:
        val = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else None}[op]
    except ZeroDivisionError:
        val = None
    if val is None:
        return "You cannot divide by zero. Try a different number."
    val = int(val) if val == int(val) else round(val, 3)
    sym = "x" if op == "*" else op
    return f"{m.group(1)} {sym} {m.group(3)} = {val}"


def retrieve(q: str, lang: str) -> dict:
    tokens = set(WORD.findall(q.lower()))
    best, score = None, 0
    for e in CORPUS:
        s = len(tokens & set(k.lower() for k in e["keywords"]))
        if s > score:
            best, score = e, s
    if best and score > 0:
        return {"answer": best[lang], "topic": best["topic"], "source": "corpus"}
    topics = sorted({e["topic"] for e in CORPUS})
    fallback = {
        "en": f"I can help with: {', '.join(topics)}. Ask about one, or type a sum like '7 + 5'.",
        "sw": f"Naweza kusaidia na: {', '.join(topics)}. Uliza moja, au andika '7 + 5'.",
        "es": f"Puedo ayudar con: {', '.join(topics)}. Pregunta sobre uno, o escribe '7 + 5'.",
    }
    return {"answer": fallback[lang], "topic": "help", "source": "corpus"}


def try_local_model(q: str, lang: str):
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        return None
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
    name = {"en": "English", "sw": "Swahili", "es": "Spanish"}[lang]
    prompt = (f"You are a kind tutor for a child in a rural school. Answer in {name}, "
              f"in two short sentences a 10 year old understands. Question: {q}")
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        text = (data.get("response") or "").strip()
        return {"answer": text, "topic": "local-model", "source": f"local-model ({model})"} if text else None
    except Exception:  # noqa: BLE001 - offline is the normal case
        return None


def try_claude(q: str, lang: str):
    if not (claude_client and claude_client.available()):
        return None
    name = {"en": "English", "sw": "Swahili", "es": "Spanish"}[lang]
    system = (f"You are a warm, patient tutor for a child in a rural school in Kenya or Ecuador. "
              f"Always answer in {name}. Use two or three short sentences a 10 year old understands. "
              f"Be encouraging. If the question is math, show the steps simply. Do not use emojis.")
    try:
        text = claude_client.ask([{"role": "user", "content": q}], system=system, max_tokens=200)
        return {"answer": text, "topic": "claude", "source": "claude"}
    except claude_client.ClaudeError:
        return None  # offline or error: fall back to local model or corpus


def answer(q: str, lang: str) -> dict:
    if lang not in LANGS:
        lang = "en"
    math = try_math(q)
    if math:
        return {"answer": math, "topic": "math", "source": "calculator"}
    # Best available, degrading gracefully to fully offline: Claude, then local model, then corpus.
    return try_claude(q, lang) or try_local_model(q, lang) or retrieve(q, lang)


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
            if claude_client and claude_client.available():
                mode = "claude"
            elif os.environ.get("OLLAMA_MODEL"):
                mode = "local-model"
            else:
                mode = "offline-corpus"
            self._json({"mode": mode, "topics": sorted({e["topic"] for e in CORPUS}), "entries": len(CORPUS)})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/ask":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "bad json"}, 400)
                return
            self._json(answer(str(body.get("q", "")), body.get("lang", "en")))
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8054)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    mode = "local model" if os.environ.get("OLLAMA_MODEL") else "offline corpus"
    print(f"Village tutor on http://127.0.0.1:{args.port} ({mode})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
