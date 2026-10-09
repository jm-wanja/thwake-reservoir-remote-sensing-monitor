# 0011 — One max-extent mask for both AEV curves; rim leaks are reported, not re-masked

- **Status:** Accepted
- **Date:** 2026-10-10
- **Deciders:** Julie Mugira

## Context
The AEV curve ([ADR 0006](0006-dem-based-volume-estimation.md)) is built from Copernicus GLO-30 (primary) and checked against SRTM. The max-extent mask ([ADR 0008](0008-max-extent-method-and-dem-release.md)) is the GLO-30 flood fill to FSL 912 m with the dam wall burned in as a barrier.

Each DEM has its own rim. With only the wall as a barrier, GLO-30's basin first overflows at ≈913.0 m, and SRTM's at **≈910.0 m, below FSL**. Both overflow through rim pass (a) at −1.79667, 37.829, about 1.1 km WSW of the wall. If SRTM were masked by its own fill, its "reservoir" at 912 m would spill into the next valley. On the ground, saddle dams (new 2025 scope, not yet visible on imagery) are meant to close these low points up to the 920.5 m maximum flood level ([open questions 17, 20](../open-questions.md)).

## Decision
1. **One mask for every DEM.** Both the GLO-30 and SRTM curves are computed inside the same GLO-30 max-extent mask (`data/baseline/max_extent.geojson`), rasterised on each DEM's native grid (pixel centre inside). Curve differences therefore reflect valley shape only.
2. **Rim leaks are reported, never used to re-mask.** For each DEM, `thwake baseline --step aev` flood-fills with the wall barrier only and records in `aev_curve_v1.json`:
   - the first overflow level;
   - the rim pixels joining the basin to the downstream valley;
   - if the DEM holds at FSL, how its own fill differs from the mask.

   Neither the mask nor the curves change because of this check.
3. The SRTM pixels inside the mask but above FSL (0.31 km²) are dry at every level.

This records the method used in prompt 04 and frozen in baseline v1 ([baseline-v1.md](../baseline-v1.md)).

## Alternatives considered
- **Each DEM uses its own fill as its mask.** This mixes valley shape with rim artefacts. For SRTM the fill at 912 m leaks past pass (a), so there is no closed reservoir to integrate unless passes are closed by hand.
- **Close SRTM's pass (a) with a disk, as the AOI step does.** This would make the two masks differ by an arbitrary closure shape and size, and the saddle dam's position and crest are not known yet.
- **Drop SRTM because it leaks.** This loses the only independent DEM cross-check. The leak is a fact about the 2000 DEM at one pass, not about the valley volume.

## Consequences
- The two curves are directly comparable. Their spread (743.4 vs 795.8 MCM at FSL; within ~1% at the same area near FSL) is a clean input to the Phase 2 volume uncertainty (prompt 07).
- The SRTM curve describes the valley as if the rim held at FSL, as the saddle dams are designed to make it. If the saddle dams are not built or sit elsewhere, water could leave the reservoir near pass (a) at high levels. Phase 2 QA should watch for water outside the mask near pass (a).
- How the rim margin (GLO-30 holds by only ~1 m at FSL) enters the volume uncertainty is still to be decided in prompt 07 (open question 20).
- Changing either point needs a new ADR and a new baseline version (`v2`), as for any frozen baseline change (AGENTS.md rule 8).
