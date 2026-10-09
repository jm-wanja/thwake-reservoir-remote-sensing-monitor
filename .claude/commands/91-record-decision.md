---
description: "Record a decision (ADR)"
---

<!-- Prompt 91 — Record a decision (ADR). Run in a fresh session: /91-record-decision -->

Task: Record a decision as an ADR.

Decision topic: <describe>

Do:
- Read docs/decisions/ to find the next number and any related ADRs.
- Copy docs/decisions/0000-template.md to docs/decisions/NNNN-short-title.md.
- Fill Context, Decision, Alternatives (at least two, with reasons), Consequences.
- Status: "Proposed" — I will change it to "Accepted".
- If it supersedes an ADR, update the old one's Status to "Superseded by NNNN"
  (don't edit its decision text).
- Update any docs that the decision changes (AGENTS.md stack table, architecture.md, etc.)
  and, if it resolves an open question, strike it in open-questions.md.
Stop and show me the ADR.
