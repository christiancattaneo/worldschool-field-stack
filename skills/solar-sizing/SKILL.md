---
name: solar-sizing
description: Size an off-grid solar microgrid for a World School field site. Use when a student needs panel count, battery bank, charge controller, inverter, wiring, a bill of materials, or an install guide from a site profile and its coordinates. Works offline.
---

# Solar microgrid sizing

Turn a site profile into a real, buildable off-grid solar system. The heavy math lives in `solar_size.py` so results are deterministic and verifiable, not guessed.

## When to use this

A student gives you a site (coordinates plus a list of electrical loads) and wants to know what to buy and how to install it. The site lives in `field-stack/sites/*.json`.

## How to run it

From `field-stack/skills/solar-sizing/`:

```
python3 solar_size.py ../../sites/kenya-sample.json --out report.md
```

Add `--offline` to force the cached or bundled irradiance, which is the field condition when Starlink is down. The script caches every live NASA POWER fetch into `data/irradiance_cache.json`, so once a site has been sized online it sizes offline forever.

## What you must do, not the script

1. Read the produced report and sanity check it against the loads. If the fridge runs 24h, confirm it dominates the battery bank, and say so.
2. Name the single biggest load and ask the student whether it is truly necessary, since cutting it shrinks the whole system and cost.
3. Flag the worst-month assumption out loud. The system is sized for the cloudiest month, on purpose.
4. Offer to translate the install guide into Swahili or Spanish for the local crew.
5. Never invent a number the script did not produce. If a value is missing, fix the input or the script, do not paper over it.

## Inputs

A site profile is JSON with `latitude`, `longitude`, `system_voltage_v`, `autonomy_days`, and a `loads` array of `{name, watts, qty, hours_per_day}`. See `field-stack/sites/kenya-sample.json`.

## Constants worth challenging

Derate, depth of discharge, and efficiency factors are defined at the top of `solar_size.py` with comments. If a student disagrees with one, change it there and re-run, do not hand-edit the report.
