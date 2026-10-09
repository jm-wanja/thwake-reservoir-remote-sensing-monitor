# 92 — Docs sync check (after each phase)

```
Task: Check that .ai/ docs match the code and repo. Report first, then fix with my approval.

Check:
- ARCHITECTURE.md §5 layout vs actual folders; §3B modules vs src/thwake/; §6 schemas vs
  actual CSV headers.
- AGENTS.md "Current status" and stack table are current.
- 05-roadmap.md checkboxes reflect reality.
- 04-data-sources.md IDs match config/ee_collections.yaml.
- 03-methodology.md thresholds match config/thresholds.yaml (and app/ee-app/main.js).
- README.md live links work and "last updated" is current.
- Every ⚠️ verify item is either still listed in 08-open-questions.md or resolved.

Output a table: item | doc says | reality | proposed fix. Wait for approval before editing.
```
