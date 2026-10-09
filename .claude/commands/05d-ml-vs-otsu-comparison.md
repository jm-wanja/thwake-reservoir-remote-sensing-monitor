---
description: "Optional: compare Otsu thresholding with a machine-learning water classifier"
---

<!-- Prompt 05d — optional, engineering roadmap C1. Run in a fresh session: /05d-ml-vs-otsu-comparison -->

Prerequisites (human must have done these): 05c done (labelled set + evaluate harness exist).
If a prerequisite is not met, stop and tell the human.

Task: Show ML judgement — does a learned classifier beat Otsu thresholding, and is it worth it?

Read first: docs/validation.md, docs/engineering-roadmap.md C1, docs/decisions/0005-dual-sensor-water-detection.md.

Do:
1. Propose 1–2 candidates (e.g. Earth Engine random forest on S1/S2 bands + indices trained on
   labels from scenes NOT in the test split; Google Dynamic World water probability). Propose an
   ADR draft for the comparison design (train/test split, features, metrics). STOP for approval.
2. Implement behind the same interface as the Otsu method; evaluate with `thwake evaluate`.
3. Write the comparison into docs/validation.md: metrics table, compute/complexity, failure
   cases (with small images), recommendation. Do not switch the production method without an ADR.

Acceptance criteria:
- No test-set leakage (scenes used for training are excluded from evaluation; show the split).
- `make check` passes. CHANGELOG + roadmap + engineering-roadmap (C1) updated. Suggest commit message. Stop.
