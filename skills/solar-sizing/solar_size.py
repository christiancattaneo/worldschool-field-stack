#!/usr/bin/env python3
"""Off-grid solar microgrid sizer for World School field sites.

Pulls real solar irradiance from NASA POWER (no API key needed), sizes a
standalone PV system for a site's load, and writes a bill of materials plus a
plain-language install guide. Works offline: fetched irradiance is cached to
data/irradiance_cache.json, and a bundled sample lets the field brain run with
the wifi off.

Usage:
    python3 solar_size.py ../../sites/kenya-sample.json
    python3 solar_size.py ../../sites/kenya-sample.json --offline
    python3 solar_size.py ../../sites/kenya-sample.json --out report.md

stdlib only, no third-party packages.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE / "data" / "irradiance_cache.json"

# Engineering constants. Documented so students can see and challenge them.
PV_DERATE = 0.75          # losses: temperature, dust, wiring, mismatch, age
BATTERY_DOD = 0.80        # LiFePO4 usable depth of discharge
BATTERY_RT_EFF = 0.95     # round-trip charge/discharge efficiency
INVERTER_EFF = 0.92       # DC to AC conversion
CONTROLLER_SAFETY = 1.25  # NEC-style 125% factor on continuous current
INVERTER_SURGE = 1.25     # headroom over peak simultaneous AC load

PANEL_WP = 450            # one PV module, watts
BATTERY_NOMINAL_V = 12    # one battery block, volts
BATTERY_AH = 200          # one battery block, amp-hours (LiFePO4)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/climatology/point"
    "?parameters=ALLSKY_SFC_SW_DWN&community=RE"
    "&longitude={lon}&latitude={lat}&format=JSON"
)


def site_key(lat: float, lon: float) -> str:
    return f"{round(lat, 2)},{round(lon, 2)}"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def fetch_irradiance(lat: float, lon: float, timeout: int = 20) -> list[float]:
    """Return 12 monthly peak-sun-hour values (kWh/m2/day) from NASA POWER."""
    url = NASA_POWER_URL.format(lat=lat, lon=lon)
    req = urllib.request.Request(url, headers={"User-Agent": "worldschool-fieldstack/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted gov URL)
        payload = json.loads(resp.read().decode())
    param = payload["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    monthly = [float(param[m.upper()]) for m in MONTHS]
    if any(v < 0 for v in monthly):
        raise ValueError("NASA POWER returned a fill value (-999); bad coordinates?")
    return monthly


def get_irradiance(lat: float, lon: float, offline: bool) -> tuple[list[float], str]:
    """Resolve monthly irradiance, preferring live data, then cache, then bundle."""
    key = site_key(lat, lon)
    cache = load_cache()

    if not offline:
        try:
            monthly = fetch_irradiance(lat, lon)
            cache[key] = {
                "monthly": monthly,
                "source": "nasa-power-live",
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            save_cache(cache)
            return monthly, "NASA POWER (live)"
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            print(f"  live fetch failed ({exc.__class__.__name__}), falling back to cache", file=sys.stderr)

    entry = cache.get(key)
    if entry:
        label = "cache (previously fetched)" if entry.get("source") == "nasa-power-live" else "bundled sample (offline)"
        return entry["monthly"], label

    raise SystemExit(
        f"No irradiance for {key}. Run once online to cache it, or add it to "
        f"{CACHE_PATH.name}."
    )


def daily_load_wh(loads: list[dict]) -> float:
    return sum(l["watts"] * l["qty"] * l["hours_per_day"] for l in loads)


def peak_ac_watts(loads: list[dict]) -> float:
    return sum(l["watts"] * l["qty"] for l in loads)


def ceil_div(a: float, b: float) -> int:
    return int(math.ceil(a / b))


def size_system(site: dict, monthly: list[float]) -> dict:
    worst_psh = min(monthly)
    worst_month = MONTHS[monthly.index(worst_psh)]
    voltage = site.get("system_voltage_v", 48)
    autonomy = site.get("autonomy_days", 2)

    load_wh = daily_load_wh(site["loads"])
    # Energy the array must deliver after inverter and system losses.
    required_wh = load_wh / INVERTER_EFF

    pv_wp = required_wh / (worst_psh * PV_DERATE)
    panel_count = ceil_div(pv_wp, PANEL_WP)
    pv_installed_wp = panel_count * PANEL_WP

    # Battery bank for the autonomy window.
    batt_wh = (load_wh * autonomy) / (BATTERY_DOD * BATTERY_RT_EFF)
    batt_ah_at_voltage = batt_wh / voltage
    blocks_series = ceil_div(voltage, BATTERY_NOMINAL_V)
    strings_parallel = ceil_div(batt_ah_at_voltage, BATTERY_AH)
    battery_count = blocks_series * strings_parallel
    installed_batt_wh = battery_count * BATTERY_NOMINAL_V * BATTERY_AH

    controller_a = (pv_installed_wp / voltage) * CONTROLLER_SAFETY
    inverter_w = peak_ac_watts(site["loads"]) * INVERTER_SURGE

    # Main DC conductor sizing from continuous current (simple ampacity bands).
    main_dc_a = pv_installed_wp / voltage
    wire = wire_gauge(main_dc_a * CONTROLLER_SAFETY)

    return {
        "worst_psh": worst_psh,
        "worst_month": worst_month,
        "annual_avg_psh": round(sum(monthly) / 12, 2),
        "voltage": voltage,
        "autonomy": autonomy,
        "load_wh": round(load_wh),
        "required_wh": round(required_wh),
        "pv_wp_needed": round(pv_wp),
        "panel_count": panel_count,
        "pv_installed_wp": pv_installed_wp,
        "battery_count": battery_count,
        "blocks_series": blocks_series,
        "strings_parallel": strings_parallel,
        "installed_batt_wh": installed_batt_wh,
        "controller_a": ceil_to(controller_a, 10),
        "inverter_w": ceil_to(inverter_w, 100),
        "main_dc_a": round(main_dc_a, 1),
        "wire_gauge": wire,
    }


def ceil_to(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step)


def wire_gauge(amps: float) -> str:
    """Rough copper ampacity bands (AWG) for short DC runs at ~75C."""
    bands = [(20, "14 AWG"), (30, "12 AWG"), (40, "10 AWG"), (55, "8 AWG"),
             (75, "6 AWG"), (95, "4 AWG"), (130, "2 AWG"), (170, "1/0 AWG"),
             (195, "2/0 AWG"), (260, "4/0 AWG")]
    for limit, gauge in bands:
        if amps <= limit:
            return gauge
    return "consult an electrician (>260 A)"


def render_report(site: dict, sizing: dict, source: str, lang_note: str) -> str:
    s = sizing
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Solar microgrid sizing: {site['name']}",
        "",
        f"Country: {site['country']}  |  Coordinates: {site['latitude']}, {site['longitude']}",
        f"Irradiance source: {source}  |  Generated: {now}",
        "",
        "## Design basis",
        f"- Worst-month sun: **{s['worst_psh']} peak sun hours/day** ({s['worst_month']}). Annual average {s['annual_avg_psh']}.",
        f"- System voltage: **{s['voltage']} V**  |  Battery autonomy: **{s['autonomy']} days**",
        f"- Daily load: **{s['load_wh']} Wh/day**  |  After inverter losses: {s['required_wh']} Wh/day",
        f"- Derate {PV_DERATE}, battery usable {int(BATTERY_DOD*100)}%, inverter {int(INVERTER_EFF*100)}%.",
        "",
        "## Bill of materials",
        f"- **Solar panels**: {s['panel_count']} x {PANEL_WP} W = {s['pv_installed_wp']} W array (need {s['pv_wp_needed']} W)",
        f"- **Batteries**: {s['battery_count']} x {BATTERY_NOMINAL_V} V {BATTERY_AH} Ah LiFePO4 "
        f"({s['blocks_series']} in series x {s['strings_parallel']} parallel = {s['installed_batt_wh']} Wh)",
        f"- **Charge controller**: MPPT, at least {s['controller_a']} A at {s['voltage']} V",
        f"- **Inverter**: pure sine, at least {s['inverter_w']} W continuous at {s['voltage']} V",
        f"- **Main DC wiring**: {s['wire_gauge']} for the ~{s['main_dc_a']} A array run (sized with 125% factor)",
        "- **Balance of system**: combiner box, DC and AC breakers, fuses, busbars, grounding rod, MC4 connectors, mounting rails",
        "",
        "## Loads counted",
    ]
    for l in site["loads"]:
        wh = l["watts"] * l["qty"] * l["hours_per_day"]
        lines.append(f"- {l['qty']} x {l['name']} @ {l['watts']} W x {l['hours_per_day']} h = {wh} Wh/day")
    lines += [
        "",
        "## Install guide (plain language)",
        "1. Mount panels facing the equator, tilted to roughly the site latitude, with no shade from 9am to 3pm.",
        "2. Wire panels to the combiner box, then to the MPPT charge controller. Never connect panels straight to batteries.",
        "3. Build the battery bank: series first to reach system voltage, then parallel strings. Match all batteries.",
        "4. Connect controller to battery bank, then the inverter to the battery bank, each through its own breaker and fuse.",
        "5. Ground the array frame and the system negative to a grounding rod.",
        "6. Power on in order: batteries, then controller, then inverter. Check controller shows charging in sun.",
        "7. Log the controller's daily Wh for a week and compare to the design load. Adjust if real use is higher.",
        "",
        f"_{lang_note}_",
        "",
        "## Safety",
        "- DC arcs do not self-extinguish. Always open breakers before touching wiring.",
        "- Lithium batteries need correct BMS settings and ventilation. Do not exceed the controller and inverter ratings.",
        "- Have the wilderness-first-aid-trained team member on site during commissioning.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Off-grid solar microgrid sizer.")
    ap.add_argument("site", help="path to a site profile JSON")
    ap.add_argument("--offline", action="store_true", help="skip the live fetch, use cache or bundle")
    ap.add_argument("--out", help="write the markdown report to this path")
    args = ap.parse_args(argv)

    site_path = Path(args.site)
    if not site_path.exists():
        print(f"site profile not found: {site_path}", file=sys.stderr)
        return 2
    site = json.loads(site_path.read_text())

    monthly, source = get_irradiance(site["latitude"], site["longitude"], args.offline)
    sizing = size_system(site, monthly)
    lang_note = "Translate this guide into Swahili or Spanish for the local build crew before install."
    report = render_report(site, sizing, source, lang_note)

    if args.out:
        Path(args.out).write_text(report)
        print(f"wrote {args.out}")
    else:
        print(report)

    print(
        f"summary: {sizing['panel_count']} panels, {sizing['battery_count']} batteries, "
        f"{sizing['controller_a']} A controller, {sizing['inverter_w']} W inverter "
        f"(worst month {sizing['worst_month']}, {sizing['worst_psh']} PSH, via {source})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
