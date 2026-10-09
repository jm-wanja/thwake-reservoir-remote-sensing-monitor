---
description: "Phase 1.5: thwake evaluate command and CI accuracy gate"
---

<!-- Prompt 05c — Phase 1.5 Validation (ADR 0009). Run in a fresh session: /05c-validation-evaluation-harness -->

Prerequisites (human must have done these): 05b done; labels in data/validation/labels/ committed.
If a prerequisite is not met, stop and tell the human.

Earth Engine budget (AGENTS.md rule 11): free Community tier, 150 EECU-hours/month; one full
Masinga run ≈ 42 EECU-hours. Estimate this task's Earth Engine cost before running anything;
if it would exceed 10 EECU-hours, stop and ask me. Prefer offline/cached re-analysis and small
test windows first. Report the actual cost at the end.

Task: Make accuracy a repeatable, enforced check.

Read first: docs/decisions/0009-validation-phase.md, docs/validation.md, docs/engineering-roadmap.md A3.

Do:
1. Add `python -m thwake evaluate`: runs the current water-detection method on every labelled
   scene and reports IoU/precision/recall/F1 per sensor and overall; writes
   data/validation/metrics.csv and prints a summary table.
2. Thresholds in config/thresholds.yaml (`evaluation.min_iou_s2`, `min_iou_s1`, …), set from the
   05b results minus a small tolerance — propose values, the human approves.
3. CI: an offline evaluation job that uses cached predictions/labels (no Earth Engine
   credentials in CI for pull requests) and fails if metrics fall below thresholds. Document
   how to refresh cached predictions locally.
4. Add the "accuracy" line to the README (values + date + link to docs/validation.md).

Acceptance criteria:
- CI fails when a deliberately degraded prediction is used (show this in a test).
- `make check` passes. CHANGELOG + roadmap + engineering-roadmap (A3) updated. Suggest commit message. Stop.
