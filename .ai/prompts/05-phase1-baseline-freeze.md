# 05 — Phase 1: Baseline reference layers and freeze

**Requires:** prompt 04 done; human reviews results before freeze.

```
Task: Produce pre-filling reference layers, write up the baseline, and prepare the freeze
(methodology §1.4).

Read first: .ai/docs/03-methodology.md §1.4, ADR 0006, AGENTS.md rule 8.

Implement:
- Land cover inside max-extent from ESA WorldCover (and Dynamic World for the most
  recent pre-filling dates): hectares per class → data/baseline/landcover_flood_zone.csv.
- Cloud-free Sentinel-2 dry-season median composite of the AOI before impoundment →
  save as an EE asset (path in config); export a small PNG to media/before_composite.png.
- Historic river channel from JRC Global Surface Water (occurrence threshold from config)
  → data/baseline/river_channel.geojson.
- Write .ai/docs/baseline-v1.md: inputs, versions of EE collections, FSL used (and whether
  assumed), AEV results vs official capacity, known issues.
- CLI: `python -m thwake baseline` runs all baseline steps.

Then STOP and ask me to review. After I approve:
- Mark baseline-v1 as frozen in baseline-v1.md and AGENTS.md "Current status".
- Suggest the git tag command `git tag baseline-v1` (I will run it).

Acceptance criteria: all outputs small (<10 MB each), reproducible from the CLI,
documented. Update roadmap.
```
