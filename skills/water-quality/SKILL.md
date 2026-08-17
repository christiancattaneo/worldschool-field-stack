---
name: water-quality
description: Read a live water sensor over MCP and decide if the water is safe to drink. Use when a student needs to assess a water source, recommend filtration, or flag unsafe water at a World School field site.
---

# Water quality assessment

Read the real sensor, compare to WHO drinking-water thresholds, and tell the student plainly whether the water is safe and what treatment it needs.

## When to use this

A student is standing at a water source (or a bench rig) with the `water-sensor` MCP server connected, and wants to know: can people drink this, and what do we build to make it safe.

## How to do it

1. Call the `water-sensor` MCP tool `read_sensor` to get the latest turbidity, pH, TDS, and temperature.
2. Call `who_thresholds` so you state the limits you are judging against, do not rely on memory.
3. Call `assess` with the reading, or reason it yourself from the thresholds, and explain each failing parameter in one sentence a non-engineer understands.
4. Give a clear verdict: safe to treat-and-drink, or unsafe without treatment. Never soften an unsafe verdict.
5. Recommend a concrete treatment train in build order (pre-filter, main filtration, disinfection). UV disinfection runs on the site's solar and Starlink power, tie it back to the energy build.

## Non-negotiables

- This sensor does not measure pathogens. Always recommend disinfection before anyone drinks, even when chemistry looks clean.
- If the reading source is `simulated`, say so. Do not present simulated water as a real measurement.
- If `read_sensor` returns a `live_error`, surface it. A failed probe is itself a field finding, not something to hide.
- Re-read before declaring a source safe. One sample is a snapshot, not a trend.

## Demoing a fault

Set `WATER_SENSOR_SIM_FAULT=1` in the MCP env to force an unsafe reading, so students see the AI catch high turbidity, bad pH, or high TDS and refuse to call it drinkable.
