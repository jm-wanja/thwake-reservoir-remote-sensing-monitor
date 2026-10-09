# Methodology

How the science works, in enough detail to implement and to explain publicly. Thresholds and parameters listed here are **starting points**; final values go in `config/thresholds.yaml` and any change after Phase 2 starts needs an ADR.

## 1. Phase 1 — Baseline (before filling)

### 1.1 Area of interest (AOI)
- Locate the dam wall: the axis is digitised on Sentinel-2 imagery (`dam.wall_axis` in `config/settings.yaml`; ⚠️ verify, open question 1).
- Delineate the valley upstream using the DEM; buffer above the full supply level (FSL) by a margin (`baseline.aoi_buffer_above_fsl_m`, +5 m) to allow for uncertainty.
- *Implementation (prompt 03, `src/thwake/baseline.py`):* the AOI is the same flood fill as the max extent (§1.2), run at FSL + margin. The pre-dam rim has low passes (saddles) between FSL and the 920.5 m maximum flood level, and on the ground saddle dams close them. Without closures the fill at 917 m spills into the downstream valleys (~212 km²). The step therefore searches for each overflow pass, lowest first: it bisects the level at which the fill first reaches a downstream check point, locates the rim pixels joining the two sides, and closes them with a disk (`pass_closure_radius_m`). It repeats until FSL + margin no longer leaks. Closed passes are listed in the AOI metadata. The AOI is the union of this fill and the max extent, with islands filled.

### 1.2 Max-extent mask
- DEM pixels with elevation ≤ FSL **and** hydrologically connected to the dam site (flood-fill from the dam).
- Water detected outside this mask is never counted → removes farm ponds, shadows, wet soil.
- *Implementation (prompt 03):* Copernicus GLO-30 (2024_1 release; tiles acquired 2010–2014, before construction). The DEM has no wall, so the digitised axis is extended 300 m into both abutments and burned in as a 90 m barrier strip, too wide for an 8-connected fill to cross diagonally. Pixels ≤ FSL outside the barrier are vectorised as 8-connected polygons in Earth Engine. The polygon containing the reservoir seed (the Athi–Thwake confluence, ~1 km upstream of the wall) is the max extent. No pass closures are applied, so the max extent is exactly what the DEM and wall define.
- *Checks (stop with an error):* the fill must not contain the downstream check point (~2.5 km down the Athi) or reach the edge of the search square (`search_radius_km`). Outputs: `data/baseline/max_extent.geojson` and `aoi.geojson` (WGS84, one feature each, metadata in properties, area computed geodesically).

### 1.3 Area–Elevation–Volume (AEV) curve
- For level *h* from the river-bed minimum to FSL in 0.5 m steps:
  - `area(h)` = sum of pixel areas in mask with elevation ≤ *h*
  - `volume(h)` = Σ over those pixels of (*h* − elevation) × pixel area
- Compute with **Copernicus GLO-30** (primary) and **SRTM** (cross-check). The spread between them is one input to volume uncertainty.
- Sanity check: volume at FSL should be in the same ballpark as the official ~681–688 MCM. A large mismatch indicates wrong FSL, AOI, or DEM issues — investigate before freezing.
- **Freeze** as `aev_curve_v1.csv` before analysing filling data.

### 1.4 Pre-filling reference
- Land cover in the flood zone (ESA WorldCover 10 m; Dynamic World for recent dates) → hectares of cropland, shrub, trees, built-up to be flooded.
- Cloud-free Sentinel-2 median composite (dry season) as the "before" image.
- JRC Global Surface Water → historic river channel (so pre-existing river water isn't counted as reservoir).

## 2. Phase 2 — Filling tracker

### 2.1 Sentinel-2 (optical)
1. Filter scenes over AOI; mask clouds/shadows (Cloud Score+ recommended).
2. Compute **MNDWI** = (Green − SWIR1) / (Green + SWIR1) (also NDWI for comparison).
3. Threshold with **Otsu** on the histogram within a buffer around the expected shoreline (bimodal histograms work best there); fall back to a fixed value (~0) if Otsu fails.
4. Record `valid_fraction` (share of max-extent not cloud-masked). Scenes below a minimum (e.g. 0.7) are flagged `low_coverage`.

### 2.2 Sentinel-1 (radar)
1. GRD, IW mode, VV (+VH) polarisation; consistent orbit direction where possible.
2. Speckle filter (e.g. focal median or refined Lee).
3. Calm water = low backscatter. Otsu threshold on VV; reference fixed threshold ≈ −18 dB (as used in GERD studies).
4. Watch for false negatives from wind-roughened water and false positives from smooth surfaces / radar shadow (mask steep slopes using DEM).

### 2.3 Post-processing (both sensors)
- Clip to max-extent mask.
- Keep the connected component(s) attached to the dam wall; remove isolated specks below a minimum size.
- Exclude the pre-existing river channel from "new reservoir" area (report both totals).
- Optional gap-fill for partially cloudy S2 scenes: estimate the level from the visible shoreline's DEM elevation, then derive the full extent from the AEV curve. Mark such rows (`method: dem_gapfill`).

### 2.4 Area → level → volume → % full
- Area from pixel-area sum (km²).
- Interpolate the AEV curve: area → level (m a.s.l.) → volume (MCM).
- % full = volume ÷ design capacity (record which capacity figure is used; ⚠️ verify official value).

### 2.5 Uncertainty
Combine (report as low / best / high):
- **Threshold sensitivity:** recompute area at Otsu ± a margin.
- **Edge (mixed) pixels:** ± half a pixel ring along the shoreline.
- **DEM error:** Copernicus vs SRTM AEV curves.
- Present as a shaded band on charts. Never show a bare single number publicly.

### 2.6 QA checks (flag, don't silently drop)
- S1 vs S2 area disagreement > X% on dates within ±2 days → `sensor_disagree`.
- Area exceeds max-extent or drops sharply without a dry spell → `jump`.
- Low valid coverage → `low_coverage`.
- Periodic visual review of a sample of scenes.

### 2.7 Context
- **CHIRPS** daily rainfall, aggregated over the upstream catchment (catchment polygon from HydroSHEDS/HydroBASINS), plotted alongside volume.

## 3. Phase 3 — Water-quality indicators

> Indicators only. Language: "higher turbidity signal", "possible algal bloom signal". Never "contaminated"/"safe".

- Use Sentinel-2 surface reflectance over **water pixels only**, excluding a shoreline buffer (mixed pixels, shallow-bottom reflectance).
- **Turbidity proxy:** red-band reflectance and/or NDTI = (Red − Green)/(Red + Green).
- **Chlorophyll / algae proxy:** NDCI = (RedEdge1 − Red)/(RedEdge1 + Red) — red-edge bands are a Sentinel-2 strength.
- Optional: floating algae / surface scum indices; colour (Forel-Ule) classification for a public-friendly "water colour" map.
- Summarise by **zone**: Athi inflow arm, Thwake inflow arm, central basin, near-dam. Track over time and against rainfall (first-flush events).
- Validation: seek any in-situ data (WRA, operator, academic sampling). Without it, report relative changes and spatial patterns, not absolute concentrations.

## 4. Phase 4 — Regional change

- **Flooded land:** baseline land-cover × final/max observed extent → hectares by class.
- **Evaporation:** ERA5-Land (or open-water evaporation estimate) × reservoir area over time → MCM lost per month/season. State the method's simplifications.
- **Downstream irrigation:** dry-season NDVI (Sentinel-2) in command areas (⚠️ need irrigation scheme boundaries) compared to pre-dam years.
- **Shoreline change:** seasonal max/min extents as a "bathtub ring" map.

## 5. Validation strategy

| What | Against |
|------|---------|
| Water masks | Visual inspection; S1 vs S2 agreement; Planet NICFI basemaps (free tropical monthly mosaics) if accessible |
| Volume | Official storage/level announcements; Global Water Watch if Thwake appears |
| Water quality | Any in-situ samples; plausibility vs rainfall/inflow events |

## References

- Kansara et al. (2021), *Remote Sensing* — GERD storage from Sentinel-1: https://doaj.org/article/96a6380ae0874e958da0921c36e963c7
- Abou Samra & Ali (2021), *Egyptian J. Remote Sensing & Space Sciences* — GERD S1 −18 dB VV threshold: https://doaj.org/article/02171b2566294321aa95c98187e21c09
- NRIAG (2022) — GERD S1/S2/Landsat-9 volume monitoring: https://library.nriag.sci.eg/paper/302
- University of Twente thesis (2024) — S1 edge-Otsu, SWOT altimetry for GERD: https://essay.utwente.nl/essays/106406
- *Remote Sensing* (Jun 2025) — 17 reservoirs, S1/S2, NDWI + Otsu in GEE: https://doaj.org/article/3e8ba48190a8455f910b385e4dacef89
- INRAE — Sentinel-1/2 reservoir volume monitoring: https://hal.inrae.fr/hal-04066655
- Global Water Watch (WRI/Deltares/WWF): https://www.wri.org/initiatives/global-water-watch
