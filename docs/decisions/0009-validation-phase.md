# 0009 — Add Phase 1.5: Validation before the filling tracker

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira

## Context
The primary audiences are portfolio and research (ADR 0007). A senior reviewer's first question will be "how do you know the water detection and volumes are accurate?" Unit tests prove the code runs on synthetic data, not that the method is right on real imagery. Thwake has no ground truth yet (not filled), so accuracy must be shown elsewhere first.

## Decision
Insert **Phase 1.5 — Validation** between the baseline freeze (Phase 1) and the filling tracker (Phase 2):
1. **Reference reservoir** (`/05a`): run the planned water-detection + DEM-volume method on an existing reservoir with published figures (candidate: Masinga Dam, Kenya; alternative: reproduce a published GERD Sentinel-1 result) and report agreement.
2. **Labelled test set** (`/05b`): human-digitised shorelines for ~20–30 scenes (mix of Sentinel-1/2, dry/wet, clear/cloudy) → IoU, precision, recall per sensor.
3. **Evaluation harness** (`/05c`): `thwake evaluate` computes the metrics; CI fails if they drop below thresholds in `config/thresholds.yaml`.
Water-detection code needed for validation is built here and reused by Phase 2 (prompts 06–07 then extend it, not rewrite it).

## Alternatives considered
- **Validate only after Thwake fills** — no early evidence; risks building Phase 2 on an unproven method.
- **Visual inspection only** — not quantitative; not credible for research.
- **Compare only with Global Water Watch** — useful later (engineering roadmap D4) but external products have their own errors and may not cover Thwake.

## Consequences
- Phase 2 starts later but on a measured method; accuracy numbers can go in the README.
- Labelling is a human task (H6) — roughly 2–4 hours.
- Enables the Otsu-vs-ML comparison (engineering roadmap C1) on the same labelled set.
- Thresholds become part of CI; method changes must not reduce accuracy silently.
