---
description: "Docs sync check (after each phase)"
---

<!-- Prompt 92 — Docs sync check (after each phase). Run in a fresh session: /92-docs-sync-check -->

Task: Check that docs/ docs match the code and repo. Report first, then fix with my approval.

Check:
- architecture.md §5 layout vs actual folders; §3B modules vs src/thwake/; §6 schemas vs
  actual CSV headers.
- AGENTS.md "Current status" and stack table are current.
- roadmap.md checkboxes reflect reality.
- data-sources.md IDs match config/ee_collections.yaml.
- methodology.md thresholds match config/thresholds.yaml (and app/ee-app/main.js).
- README.md live links work and "last updated" is current.
- Every ⚠️ verify item is either still listed in open-questions.md or resolved.

Output a table: item | doc says | reality | proposed fix. Wait for approval before editing.
