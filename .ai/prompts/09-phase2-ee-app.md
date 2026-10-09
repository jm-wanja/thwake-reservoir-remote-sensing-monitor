# 09 — Phase 2: Earth Engine App

**Requires:** prompts 06–08 done. Human publishes the app (H5).

```
Task: Write the Earth Engine App (JavaScript) in app/ee-app/main.js (ARCHITECTURE §3C, ADR 0003).

Read first: ADR 0003, .ai/docs/03-methodology.md §2, config/thresholds.yaml,
config/ee_collections.yaml.

Requirements:
- Same thresholds and collection IDs as the Python pipeline. Put them in a clearly marked
  constants block at the top with a comment: "Must match config/thresholds.yaml".
- UI: title + one-line explanation; date picker/slider of available scenes; layers:
  true colour, water outline (S2 or S1 toggle), max-extent outline, before/after swipe
  (baseline composite vs selected date); chart of area over time; info panel with
  "what this shows / doesn't show" and a link to the story page and data CSV.
- Uses baseline assets (AOI, max-extent, composite) from the EE asset paths in config.
- Mobile-friendly layout where EE UI allows; colour-blind-safe palette.
- app/ee-app/README.md: how to paste into the Code Editor, which assets must be shared
  publicly, and how to publish (Apps → New App, name "thwake").

Acceptance criteria:
- Script runs in the Code Editor without errors (I will test and publish).
- A short note listing any place the app's logic deliberately differs from Python.
Stop; I'll publish and give you the URL to add to README.md.
```
