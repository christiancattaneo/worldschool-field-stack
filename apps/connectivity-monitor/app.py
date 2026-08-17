#!/usr/bin/env python3
"""Starlink + Timeback connectivity monitor.

A real web app students build to prove academics survive an intermittent link.
A background simulator models a Starlink connection (up/down, latency). Timeback
lessons are completed locally and queued; when the link is up the queue syncs,
when it drops the queue grows but learning never stops. Students can drop and
restore the link to watch the recovery. stdlib only.

Run:  python3 app.py [--port 8053]
Open: http://127.0.0.1:8053
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent

LESSONS = ["Algebra II mastery", "AP Bio reading", "Spanish unit", "Essay draft",
           "Geometry quiz", "Chemistry lab notes", "History timeline", "Calc problem set"]


class Sim:
    """Models a flaky Starlink link and a local-first Timeback sync queue."""

    def __init__(self):
        self.online = True
        self.manual_down = False
        self.latency_ms = 45
        self.queue: deque = deque()       # pending lessons awaiting sync
        self.synced_total = 0
        self.samples: deque = deque(maxlen=60)   # 1 = online, 0 = offline
        self.latencies: deque = deque(maxlen=60)
        self.log: deque = deque(maxlen=40)
        self.lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _note(self, msg):
        self.log.appendleft(f"{time.strftime('%H:%M:%S')}  {msg}")

    def _run(self):
        while True:
            time.sleep(1.5)
            with self.lock:
                # Link behavior: honor a manual drop, else random Starlink-like blips.
                if self.manual_down:
                    self.online = False
                elif self.online:
                    self.online = random.random() > 0.06   # ~6% chance to blip out
                else:
                    self.online = random.random() > 0.4     # tends to recover

                self.samples.append(1 if self.online else 0)
                self.latency_ms = random.randint(35, 75) if self.online else 0
                self.latencies.append(self.latency_ms)

                # Students keep doing academics regardless of the link (local-first).
                if random.random() > 0.35:
                    self.queue.append({"lesson": random.choice(LESSONS),
                                       "at": time.strftime("%H:%M:%S")})

                # When the link is up, drain the queue (sync to Timeback cloud).
                if self.online and self.queue:
                    n = min(len(self.queue), random.randint(2, 5))
                    for _ in range(n):
                        self.queue.popleft()
                    self.synced_total += n
                    self._note(f"link up · synced {n} item(s) to Timeback")
                elif not self.online:
                    self._note(f"offline · {len(self.queue)} item(s) queued, learning continues")

    def status(self):
        with self.lock:
            up = sum(self.samples)
            uptime = round(up / len(self.samples) * 100) if self.samples else 100
            return {
                "online": self.online,
                "manual_down": self.manual_down,
                "latency_ms": self.latency_ms,
                "uptime_pct": uptime,
                "queue_len": len(self.queue),
                "queue": list(self.queue)[:8],
                "synced_total": self.synced_total,
                "samples": list(self.samples),
                "latencies": list(self.latencies),
                "log": list(self.log)[:12],
            }

    def toggle(self):
        with self.lock:
            self.manual_down = not self.manual_down
            self._note("manual link DROP" if self.manual_down else "manual link RESTORE")
            return self.manual_down


SIM = Sim()


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
        elif path == "/api/status":
            self._json(SIM.status())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/toggle":
            self._json({"manual_down": SIM.toggle()})
        else:
            self._json({"error": "not found"}, 404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8053)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Connectivity monitor on http://127.0.0.1:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
