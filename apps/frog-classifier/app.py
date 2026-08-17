#!/usr/bin/env python3
"""Bioacoustics frog-call classifier (Ecuador research build).

Upload a WAV of a night soundscape and the app builds a spectrogram and pulls
research features: call activity, dominant frequency, an estimated call count,
and a heuristic frequency-band label. Generates a synthetic demo clip so the app
works with no recording on hand. stdlib only, runs offline.

Run:  python3 app.py [--port 8056]
Open: http://127.0.0.1:8056
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import analyze as A

HERE = Path(__file__).resolve().parent
DEMO = HERE / "demo.wav"


def make_demo(path: Path, rate: int = 8000, seconds: float = 4.0):
    """Synthesize chirps in a tree-frog band with gaps, plus low background noise."""
    import random
    n = int(rate * seconds)
    samples = [0.0] * n
    rng = random.Random(7)
    # background hiss
    for i in range(n):
        samples[i] += rng.uniform(-0.02, 0.02)
    # chirps: amplitude-enveloped tones around 2200 Hz, every ~0.7 s
    chirp_hz, chirp_len = 2200, int(0.18 * rate)
    t = int(0.3 * rate)
    while t + chirp_len < n:
        for k in range(chirp_len):
            env = math.sin(math.pi * k / chirp_len) ** 2  # smooth attack/decay
            wob = 1 + 0.04 * math.sin(2 * math.pi * 12 * k / rate)  # slight wobble
            samples[t + k] += 0.7 * env * math.sin(2 * math.pi * chirp_hz * wob * k / rate)
        t += int(rng.uniform(0.6, 0.85) * rate)
    peak = max(abs(s) for s in samples) or 1
    pcm = b"".join(struct.pack("<h", int(max(-1, min(1, s / peak)) * 32000)) for s in samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


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
        elif path == "/api/demo":
            try:
                self._json(A.analyze(DEMO.read_bytes()))
            except Exception as exc:  # noqa: BLE001
                self._json({"error": f"{exc.__class__.__name__}: {exc}"}, 500)
        elif path == "/demo.wav":
            self._send(200, DEMO.read_bytes(), "audio/wav")
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path == "/api/analyze":
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length)
            try:
                self._json(A.analyze(data))
            except Exception as exc:  # noqa: BLE001
                self._json({"error": f"{exc.__class__.__name__}: {exc}"}, 400)
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8056)
    args = ap.parse_args(argv)
    if not DEMO.exists():
        make_demo(DEMO)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Frog classifier on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
