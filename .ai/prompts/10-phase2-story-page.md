# 10 — Phase 2: Story page (Quarto)

**Requires:** prompt 08 done; Quarto installed (H1).

```
Task: Build the public story page in site/ with Quarto (ARCHITECTURE §3E, ADR 0003).

Read first: .ai/docs/01-project-brief.md (audience!), ADR 0003, AGENTS.md rules 4, 5, 7,
.ai/docs/07-risks-and-limitations.md, .ai/docs/04-data-sources.md (attribution).

Structure (scroll narrative, plain language, visuals first):
1. Hero: latest % full (with range) and image date.
2. "The valley before" — before composite, land cover to be flooded.
3. "The dam" — short context with cited facts only.
4. "The lake forms" — time-lapse, before/after slider (JuxtaposeJS), area/volume chart
   with uncertainty band, rainfall.
5. "Is the water clean?" — placeholder section "coming in Phase 3".
6. "What this does and doesn't show" — limitations box.
7. Methods (short, link to .ai/docs/03-methodology.md on GitHub), data download links,
   attribution, link to the Earth Engine App.

Technical:
- Reads data/processed/*.csv and *.geojson; no hard-coded numbers in prose — compute them.
- Map: Leaflet or MapLibre with OSM tiles (resolve open question 11 via ADR if needed);
  charts: Plotly or Observable Plot (open question 10).
- Accessible: alt text, colour-blind-safe, works on mobile, light/dark friendly.
- `quarto render site/` builds locally to site/_site (git-ignored).

Acceptance criteria:
- Renders locally without errors; every number on the page has a date and range.
- Wording passes AGENTS.md rule 7 (no "safe"/"contaminated"). Update roadmap. Stop.
```
