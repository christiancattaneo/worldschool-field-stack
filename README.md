# Field Stack

The portable build brain students carry to Kenya and Ecuador. Fork it on Day 1, extend it across the workshop, and run it in the field with the internet off.

## Day 1 setup (1:20–1:45) — the checklist

1. Fork this repo, then clone your fork.
2. Open it in **Claude Code** and authenticate.
3. Fill in `CLAUDE.md` — your name, your site, your Day 1 pillar.
4. Your subagent team is already in `.claude/agents/` (scout, skeptic, synthesist, devils-advocate, interviewer, translator, visualizer). Say hi to the Skeptic.
5. If your pillar needs the water sensor: copy `mcp/water-sensor/.mcp.json.example` to `.mcp.json` and run the selftest.
6. For Claude-backed apps: copy `.env.example` to `.env.local` and paste the workshop key. **Never commit it** — the `.gitignore` already covers it.

Stuck at 1:35? Raise a hand. Don't burn build time on setup.

**The rule of two builds:** across Monday and Tuesday you ship two dashboards. One must run the school — solar, Starlink + Timeback, the village tutor, or the lesson generator. The other comes from your pillar: food, water, education, empowerment, or healthcare. You build your own from scratch with your AI; the reference apps below are for studying, stealing patterns, and rescue.

## Project 1: solar microgrid sizer (Claude Code Skill)

`skills/solar-sizing/` turns a site profile into a real off-grid solar system: panel count, battery bank, charge controller, inverter, wiring, a bill of materials, and a plain-language install guide. It pulls live irradiance from NASA POWER (no API key) and caches it, so it sizes offline once a site has been seen online.

```
cd skills/solar-sizing
python3 solar_size.py ../../sites/kenya-sample.json --out report.md
python3 solar_size.py ../../sites/ecuador-sample.json --offline
```

stdlib only. The Skill (`SKILL.md`) tells Claude Code how to run it, sanity check the numbers, and translate the guide.

## Project 2: water-quality sensor (MCP server the AI reads live)

`mcp/water-sensor/` exposes a live water sensor to Claude Code over MCP. The AI reads turbidity, pH, and TDS, compares them to WHO drinking-water limits, and flags unsafe water. Hardware optional: set `WATER_SENSOR_URL` for a real probe (ESP32, Pi, lab sensor with an HTTP shim), or run with no hardware and it simulates.

```
cd mcp/water-sensor
python3 server.py selftest                      # normal reading
WATER_SENSOR_SIM_FAULT=1 python3 server.py selftest   # forced unsafe reading
pip install -r requirements.txt && python3 server.py  # serve to Claude Code
```

Wire it into Claude Code by copying `.mcp.json.example` to your project `.mcp.json`. The paired Skill is `skills/water-quality/SKILL.md`.

## The 4-hour build: operations dashboards

The scripts above are the engine, the easy 20 minutes. The real workshop build is the web app that wraps them, which is what runs in a browser tab and takes an afternoon. Three reference dashboards ship in `apps/`, stdlib only, no pip:

```
cd apps/solar-dashboard       && python3 app.py --port 8051   # http://127.0.0.1:8051
cd apps/water-station         && python3 app.py --port 8052   # http://127.0.0.1:8052
cd apps/connectivity-monitor  && python3 app.py --port 8053   # http://127.0.0.1:8053
cd apps/village-tutor         && python3 app.py --port 8054   # http://127.0.0.1:8054
cd apps/ops-center            && python3 app.py --port 8055   # http://127.0.0.1:8055
cd apps/frog-classifier       && python3 app.py --port 8056   # http://127.0.0.1:8056
cd apps/health-survey         && python3 app.py --port 8057   # http://127.0.0.1:8057
cd apps/procurement-planner   && python3 app.py --port 8058   # http://127.0.0.1:8058
cd apps/phrasebook            && python3 app.py --port 8059   # http://127.0.0.1:8059
cd apps/research-assistant    && python3 app.py --port 8060   # http://127.0.0.1:8060  (Claude)
cd apps/lesson-generator      && python3 app.py --port 8061   # http://127.0.0.1:8061  (Claude)
```

- **solar-dashboard**: pick a site, pull live NASA irradiance, edit the loads, watch the bill of materials resize. Toggle offline to size with the wifi off.
- **water-station**: polls the sensor over MCP, gauges turbidity, pH, and TDS against WHO limits, charts history, and has a force-a-contaminated-sample button.
- **connectivity-monitor**: drop the Starlink link and watch Timeback lessons queue locally, then drain on reconnect. Uptime, latency, and a live event log.
- **village-tutor**: the leave-behind tutor for local kids. Trilingual (English, Swahili, Spanish), works fully offline from a bundled lesson corpus, solves arithmetic, and optionally uses a local model (set `OLLAMA_MODEL`) when one is reachable.
- **ops-center**: one pane of glass. Aggregates power, water, and connectivity into a single Operational / Degraded / Critical readiness status, with links into each full dashboard. The Wednesday demo capstone.
- **frog-classifier**: Ecuador research build. Upload a WAV (or analyze the bundled demo clip), get a spectrogram, call activity, dominant frequency, estimated call count, and a heuristic band label. Hand-written FFT, fully offline.
- **health-survey**: offline-first community health data collection. Save responses with no connection, see a live dashboard of aggregates, sync to the study database when the link returns.
- **procurement-planner**: turn a bill of materials into a landed-cost plan, freight, duty, and VAT to Nairobi or Quito, with total weight and transit time.
- **phrasebook**: offline job-site phrasebook, Swahili and Spanish terms for electrical, water, medical, and worksite work, searchable by word or category.

- **research-assistant**: a Claude-powered chatbot research mentor. Turns a curiosity into a researchable question, names what evidence would confirm it, applies the source-evaluation rubric, and refuses to fabricate citations.
- **lesson-generator**: Claude writes a one-page, low-resource lesson plan on any topic, at a chosen age, in English, Swahili, or Spanish, ready to teach offline.

The village tutor also ships an Ollama API stub (`apps/village-tutor/ollama_stub.py`) and `LOCAL_MODEL.md` so you can verify and then enable a real local model. Online, the tutor uses Claude; offline it falls back to a local model, then the bundled corpus.

## Claude API key and cost

The Claude-backed apps (tutor online mode, research assistant, lesson generator) read `ANTHROPIC_API_KEY` from the repo-root `.env.local`, which is gitignored and never committed. Copy `.env.example` to `.env.local` and fill it in. The shared client is `field-stack/claude_client.py`.

Cost is controlled on purpose. Default model `claude-opus-4-8` is about $5 per million input tokens and $25 per million output. Output is hard-capped per call, so a worst-case message is roughly $0.017. At a 1500-message/month classroom cap that is about $26/month. Set `CLAUDE_MODEL=claude-sonnet-4-6` to cut chat cost roughly 5x. Nothing in the apps self-triggers, so there is no runaway loop.

## Layout

```
field-stack/
  sites/                     site profiles (Kenya, Ecuador samples)
  skills/solar-sizing/       solar engine: Skill + sizing script + irradiance cache
  skills/water-quality/      water Skill: read sensor, judge safety
  mcp/water-sensor/          water MCP server: live or simulated readings
  apps/solar-dashboard/      4-hour build: solar operations dashboard
  apps/water-station/        4-hour build: water quality monitoring station
  apps/connectivity-monitor/ 4-hour build: Starlink + Timeback link monitor
  apps/village-tutor/        leave-behind offline trilingual tutor for local kids
  apps/ops-center/           capstone: unified power/water/link readiness pane
  apps/frog-classifier/      Ecuador research: bioacoustic call analysis (FFT)
  apps/health-survey/        offline-first community health collection + dashboard
  apps/procurement-planner/  landed-cost planner: freight, duty, VAT to KE/EC
  apps/phrasebook/           offline build-crew phrasebook (Swahili/Spanish)
  apps/research-assistant/   Claude chatbot: research mentor, source-skeptic
  apps/lesson-generator/     Claude: trilingual low-resource lesson plans
  claude_client.py           shared Claude API client (reads .env.local)
```

## Field notes

- Both projects run offline by design. That is the requirement, not a nice-to-have.
- Constants (derate, depth of discharge, WHO thresholds) are in the code with comments. Challenge them, change them there, re-run. Do not hand-edit outputs.
- No secrets in this repo. A real sensor URL or any key goes in the MCP env or a local `.env`, never committed.
