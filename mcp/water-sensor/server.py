#!/usr/bin/env python3
"""Water-quality sensor MCP server for World School field sites.

Exposes a live water sensor to Claude Code over MCP so the AI can read real
readings, compare them to WHO drinking-water thresholds, and flag unsafe water.

Hardware optional. If WATER_SENSOR_URL is set, the server GETs JSON readings
from a real sensor gateway (an ESP32, a Pi, or a lab probe with an HTTP shim).
With no hardware it returns realistic simulated readings so the workshop runs
anywhere, and the same code deploys unchanged once a real probe is wired.

Tools exposed:
  read_sensor()      -> latest reading, live or simulated
  who_thresholds()   -> the limits the assessment uses
  assess(...)        -> verdict + reasons + recommended filtration for a reading

Run as an MCP server (used by Claude Code):
  python3 server.py
Quick local check with no MCP client:
  python3 server.py selftest
  WATER_SENSOR_SIM_FAULT=1 python3 server.py selftest

Requires: mcp  (pip install -r requirements.txt). selftest needs only stdlib.
"""

from __future__ import annotations

import json
import os
import random
import sys
import urllib.request
from datetime import datetime, timezone

# WHO / typical drinking-water guideline values used for the verdict.
THRESHOLDS = {
    "turbidity_ntu": {"ideal": 1.0, "max": 5.0},   # WHO: <1 ideal, 5 upper bound
    "ph": {"min": 6.5, "max": 8.5},
    "tds_ppm": {"good": 600.0, "max": 1000.0},
    "temp_c": {"note": "context only, not a safety limit"},
}


def _read_live(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "worldschool-watersensor/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        data = json.loads(resp.read().decode())
    return {
        "turbidity_ntu": float(data["turbidity_ntu"]),
        "ph": float(data["ph"]),
        "tds_ppm": float(data["tds_ppm"]),
        "temp_c": float(data["temp_c"]),
        "source": "live",
        "url": url,
    }


def _read_simulated() -> dict:
    fault = os.environ.get("WATER_SENSOR_SIM_FAULT") == "1"
    if fault:
        reading = {
            "turbidity_ntu": round(random.uniform(8.0, 45.0), 1),
            "ph": round(random.choice([random.uniform(4.5, 6.2), random.uniform(8.8, 9.6)]), 2),
            "tds_ppm": round(random.uniform(1100, 2200)),
        }
    else:
        reading = {
            "turbidity_ntu": round(random.uniform(0.2, 3.5), 1),
            "ph": round(random.uniform(6.7, 8.1), 2),
            "tds_ppm": round(random.uniform(120, 520)),
        }
    reading["temp_c"] = round(random.uniform(16.0, 27.0), 1)
    reading["source"] = "simulated"
    return reading


def read_sensor() -> dict:
    """Return the latest water reading from the real gateway or the simulator."""
    url = os.environ.get("WATER_SENSOR_URL")
    if url:
        try:
            reading = _read_live(url)
        except Exception as exc:  # noqa: BLE001 - degrade to sim, never crash a field tool
            reading = _read_simulated()
            reading["live_error"] = f"{exc.__class__.__name__}: {exc}"
    else:
        reading = _read_simulated()
    reading["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return reading


def who_thresholds() -> dict:
    """Return the WHO-style thresholds used by assess()."""
    return THRESHOLDS


def assess(turbidity_ntu: float, ph: float, tds_ppm: float, temp_c: float = 20.0) -> dict:
    """Classify a reading and recommend filtration. Drinking water, not just clear water."""
    reasons: list[str] = []
    treatments: list[str] = []
    safe = True

    t = THRESHOLDS["turbidity_ntu"]
    if turbidity_ntu > t["max"]:
        safe = False
        reasons.append(f"turbidity {turbidity_ntu} NTU exceeds WHO max {t['max']}")
        treatments.append("sediment pre-filter then biosand or coagulation-flocculation")
    elif turbidity_ntu > t["ideal"]:
        reasons.append(f"turbidity {turbidity_ntu} NTU above the {t['ideal']} NTU ideal but within limits")
        treatments.append("sediment pre-filter recommended")

    p = THRESHOLDS["ph"]
    if ph < p["min"] or ph > p["max"]:
        safe = False
        reasons.append(f"pH {ph} outside the safe {p['min']}-{p['max']} range")
        treatments.append("pH neutralization (acid: soda ash dosing; alkaline: aeration or acid dosing)")

    d = THRESHOLDS["tds_ppm"]
    if tds_ppm > d["max"]:
        safe = False
        reasons.append(f"TDS {tds_ppm} ppm exceeds the {d['max']} ppm acceptability limit")
        treatments.append("reverse osmosis or distillation for dissolved solids")
    elif tds_ppm > d["good"]:
        reasons.append(f"TDS {tds_ppm} ppm above the {d['good']} ppm good band but drinkable")

    # Sensors here do not measure pathogens. For drinking water, always disinfect.
    treatments.append("disinfection before drinking: chlorination or UV (UV runs on the solar/Starlink power)")

    verdict = "SAFE to treat-and-drink with disinfection" if safe else "UNSAFE without treatment"
    if not safe:
        reasons.insert(0, "do not drink as-is")

    return {
        "verdict": verdict,
        "safe_without_treatment": safe,
        "reasons": reasons,
        "recommended_treatment": treatments,
    }


def _selftest() -> int:
    reading = read_sensor()
    result = assess(reading["turbidity_ntu"], reading["ph"], reading["tds_ppm"], reading["temp_c"])
    print(json.dumps({"reading": reading, "assessment": result}, indent=2))
    return 0


def _serve() -> int:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("the 'mcp' package is required to serve. pip install -r requirements.txt", file=sys.stderr)
        return 1

    mcp = FastMCP("water-sensor")
    mcp.tool()(read_sensor)
    mcp.tool()(who_thresholds)
    mcp.tool()(assess)
    mcp.run()
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(_selftest())
    raise SystemExit(_serve())
