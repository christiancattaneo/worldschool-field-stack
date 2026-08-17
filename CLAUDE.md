# Field Stack — [YOUR NAME]'s Build Brain

This file is what your AI knows about your build. Fill in the brackets on Day 1 setup (1:20–1:45). Keep it updated as your build evolves — this file travels to Kenya and Ecuador with you.

## My site

- Site: [Loita Hills, Kenya (-1.75, 35.85) / Tena, Ecuador (-0.99, -77.81)]
- Site profile: `sites/[kenya|ecuador]-sample.json`
- Day 1 build (pillar): [solar / water / connectivity]
- Day 2 build (different pillar): [filled in Tuesday at lunch]
- The rule: one of my two builds runs the school (solar, Starlink + Timeback, tutor, or lesson generator). The other is my chosen pillar: [food / water / education / empowerment / healthcare]

## What lives where

- `skills/solar-sizing/` — sizes a real off-grid solar system from a site profile. Caches NASA irradiance so it works offline.
- `skills/water-quality/` — the procedure for judging water against WHO limits via the sensor.
- `mcp/water-sensor/` — the MCP server that reads the (simulated or real) water sensor. `WATER_SENSOR_SIM_FAULT=1` forces an unsafe reading.
- `apps/` — eleven working reference dashboards. Study them, steal patterns. My build is my own.
- `source-evaluation-rubric.md` — the Skeptic subagent reads this when scoring any source.
- `.claude/agents/` — my specialist team: scout, skeptic, synthesist, devils-advocate, interviewer, translator, visualizer.

## Rules for my AI

1. **Offline is the requirement.** Everything we build must load and compute with the wifi off, from cached or bundled data. Design for it from the first hour.
2. **Never invent a number a script did not produce.** If a value is missing, fix the input or the code — do not paper over it.
3. **Label simulated data as simulated.** Never present it as a real measurement.
4. **Every cited claim traces to a primary source I can produce.** Hallucinations caught in a demo mean a redo.
5. **No secrets in the repo.** Keys live in `.env.local` (gitignored). Check before every commit.

## Build log

- [date] — [what shipped]
