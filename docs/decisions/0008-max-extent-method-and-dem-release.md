# 0008 — Max-extent method (wall barrier + rim-pass closure) and DEM release

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Julie Mugira (method implemented in prompt 03; recorded retroactively)

## Context
The max-extent mask (methodology §1.2) must contain only ground at or below the full supply level (912 m a.s.l.) that the reservoir can actually reach. The pre-dam DEM has no dam wall, and the reservoir rim is low: with only the valley shape, a flood fill at 912 m leaks downstream past the wall, and at FSL + 5 m (the AOI level) it spills through rim passes into neighbouring valleys (~212 km²). On the ground, the wall and two saddle dams close these gaps. Separately, Earth Engine marks `COPERNICUS/DEM/GLO30` as deprecated in favour of the `GLO30_2024_1` release.

## Decision
1. **DEM:** use `COPERNICUS/DEM/GLO30_2024_1` (tiles acquired 2010–2014, before construction began on 27 Mar 2018). SRTM (2000) remains the cross-check.
2. **Wall as barrier:** burn the digitised dam axis (extended 300 m into both abutments) into the DEM as a 90 m-wide barrier strip, too wide for an 8-connected fill to cross.
3. **Max extent:** the 8-connected polygon of pixels ≤ FSL containing the reservoir seed (Athi–Thwake confluence). **No rim-pass closures** are applied to the max extent, so it is exactly what the DEM and wall define.
4. **AOI only:** at FSL + margin, find overflow passes lowest-first (bisect the level where the fill reaches a downstream check point, close the joining rim pixels with a disk) until no leak; record each closure in the AOI metadata.
5. **Safety checks:** the step fails if the fill contains the downstream check point or reaches the search-square edge.

## Alternatives considered
- **Hand-drawn reservoir outline** — subjective, not reproducible.
- **Official reservoir outline** — not available in usable form (no published shapefile found).
- **Apply rim-pass closures to the max extent too** — would hide the low-rim sensitivity that matters for uncertainty; kept for AOI only.
- **Keep deprecated `GLO30` ID** — same underlying data but would break when removed.

## Consequences
- Max extent 30.36 km² vs official ~29 km² (+4.7%); AOI 35.11 km².
- The rim is only ~1 m above FSL (first overflow ≈913 m at −1.79667, 37.82917), smaller than DEM vertical error. Volume uncertainty and the SRTM cross-check (prompt 04) must account for this — open questions 17, 20.
- The digitised wall axis (±~20 m) becomes a config input; verification on high-resolution imagery is a human step (open question 1).
- Changing any of this after the baseline freeze requires a new ADR (AGENTS.md rule 8).
