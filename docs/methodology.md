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
- *Implementation (prompt 04, `thwake baseline --step aev`; `src/thwake/volume.py`, `baseline.py`):*
  - **Mask:** both DEMs use the same frozen GLO-30 max extent (`max_extent.geojson`), rasterised on each DEM's native 1″ grid (pixel centre inside). The two grids coincide. Curve differences therefore reflect valley shape only. SRTM pixels inside the mask but above FSL (0.31 km²) are simply dry at every level.
  - **Server-side reduction:** Earth Engine sums, per 0.5 m elevation bin *k* = ⌊(FSL − z)/step⌋, the pixel area Σa and Σa·(FSL − z) (`ee.Image.pixelArea`, one grouped `reduceRegion`). Area and volume at every level then follow exactly by cumulative sums: volume(*h*ⱼ) = Σ_{k≥j} Σa·(FSL − z) − j·step·area(*h*ⱼ). The pure-Python reference (`volume.bin_sums`) is unit-tested on a synthetic cone and V-trough, where the build is within 0.5% (cone, at FSL) and within one pixel column (trough) of the exact geometry.
  - **Curve:** from one step below the lowest pixel in the mask (area 0) to FSL. As defined above, pixels ≤ *h* inside the mask count even if a local sill would cut them off at that level. This has a small effect at low levels.
  - **Interpolation (Phase 2):** linear between levels for area→level, level→volume and area→volume. With 0.5 m steps, the volume interpolation error is ≤ Δarea·step/8 (≈0.02 MCM near FSL). Values outside the curve raise an error rather than being extrapolated.
  - **Rim check (reported, never used to re-mask):** each DEM is flood-filled with the wall barrier only (§1.2), and the step reports the level at which its basin first reaches the downstream check point and the rim pixels joining it to the downstream basin. If the DEM holds at FSL, the step also compares its own fill with the mask.
  - **Outputs:** `data/baseline/aev_curve_v1.csv` (both DEMs, schema in architecture §6), `aev_curve_v1.json` (provenance, capacity check, rim check, DEM difference) and `media/aev_curve_v1.png`.
  - **Results (draft, 2026-10-09; not frozen):**

    | | Copernicus GLO-30 (2010–14) | SRTM (Feb 2000) |
    |---|---|---|
    | Lowest elevation in mask | 836.5 m | 828.0 m |
    | Area at FSL | 30.36 km² | 30.04 km² |
    | Volume at FSL | **743.4 MCM** | **795.8 MCM** |
    | vs design 688 MCM | +8.1% | +15.7% |
    | vs design history 681 / 825 MCM | +9.2% / −9.9% (inside range) | +16.9% / −3.5% (inside range) |
    | dV/dh at FSL | 30.1 MCM per m | 29.9 MCM per m |
    | First rim overflow (wall barrier only) | ≈913.0 m, pass (a) | **≈910.0 m, pass (a): below FSL** |

    Inside the mask, SRTM − GLO-30 = −1.7 m on average (median −1.9 m, 5–95% −5.9 to +3.4 m). Within 500 m of the wall it is −1.8 m: there is no sign of a local artefact at the dam site. Both volumes are within 20% of the design value, so no investigation was triggered.
  - **Reading the gap:** dV/dh ≈ 30 MCM per metre at FSL, so GLO-30's +55 MCM is equivalent to a uniform vertical offset of ≈1.8 m between the DEM and the design survey (or in the FSL datum). That is within "a few metres" of DEM error. Possible contributors, none of them quantified: different vertical datums (GLO-30 EGM2008, SRTM EGM96; the datum of the 912 m design FSL is unknown, open question 22); the mask being 4.7% larger than the official ~29 km²; and the design curve coming from a different survey. Converting area to volume, the way Phase 2 uses the curve, is much less sensitive to such offsets. For the same area the two DEMs agree closely: 29 km² gives 696.4 (GLO-30) vs 696.2 MCM (SRTM), and 15 km² gives 262.6 vs 249.4 MCM.

### 1.4 Pre-filling reference
- Land cover in the flood zone (ESA WorldCover 10 m; Dynamic World for recent dates) → hectares of cropland, shrub, trees, built-up to be flooded.
- Cloud-free Sentinel-2 median composite (dry season) as the "before" image.
- JRC Global Surface Water → historic river channel (so pre-existing river water isn't counted as reservoir).
- *Implementation (prompt 05, `thwake baseline --step landcover | river | composite`; `src/thwake/reference.py`):* results and known issues are in [baseline-v1.md](baseline-v1.md).
  - **Pre-filling window:** 2026-06-01 to 2026-10-01 (`dates.pre_filling_window`), the latest long dry season before impoundment. The config check refuses a window that ends after `impoundment_start`.
  - **Land cover:** hectares per class inside the max extent, pixel centres inside, geodesic pixel area. Sources: ESA WorldCover v200 (2021), and the per-pixel most frequent Dynamic World label over the window. Each class is matched to a common (Dynamic World) class, and the WorldCover–Dynamic World range is the reported uncertainty, with the products' published accuracies. Each product's classes must add up to the max-extent area within 2%. An "expected area" from mean Dynamic World probabilities was tried and dropped: the probabilities are not calibrated (it gave ~119 ha of snow and ice).
  - **"Before" composite:** Sentinel-2 L2A median over the window, pixels with Cloud Score+ `cs` < 0.6 masked. The extent is the AOI bounding box + 1 km. Exported as a versioned EE asset (B2, B3, B4, B8, B11, B12 as uint16 reflectance ×10⁴, plus a `clear_obs` count, 10 m, UTM 37S) and as a 1,200 px true-colour PNG. The step fails if any pixel has no clear observation. CHIRPS rainfall over the window is recorded as evidence that it was dry.
  - **River channel:** JRC GSW 1.4 `occurrence` ≥ 10% inside the AOI, vectorised (8-connected) on the native 30 m grid. The Athi here is narrow and seasonal, so occurrence peaks at ~59% and ≥ 50% would keep almost nothing. The areas at 5, 25 and 50% are stored with the output as its sensitivity.

## 2. Phase 2 — Filling tracker

### 2.1 Sentinel-2 (optical)
1. Filter scenes over AOI; mask clouds/shadows (Cloud Score+ recommended).
2. Compute **MNDWI** = (Green − SWIR1) / (Green + SWIR1) (also NDWI for comparison).
3. Threshold with **Otsu** on the histogram within a buffer around the expected shoreline (bimodal histograms work best there); fall back to a fixed value (~0) if Otsu fails.
4. Record `valid_fraction` (share of max-extent not cloud-masked). Scenes below a minimum (e.g. 0.7) are flagged `low_coverage`.
- *Implemented for the validation (prompt 05a, `src/thwake/water_s2.py`, `otsu.py`); Phase 2 extends it:* granules of one day are mosaicked; Cloud Score+ `cs` ≥ 0.6. The Otsu histogram (MNDWI, 200 bins over −1…1, 20 m) covers the max extent plus a 1 km land ring (`validation.otsu_buffer_m`), so both classes are present even when the reservoir is full. An Otsu threshold outside −0.5…0.5 is treated as failed and the fallback (0) is used; the choice is recorded per scene.

### 2.2 Sentinel-1 (radar)
1. GRD, IW mode, VV (+VH) polarisation; consistent orbit direction where possible.
2. Speckle filter (e.g. focal median or refined Lee).
3. Calm water = low backscatter. Otsu threshold on VV; reference fixed threshold ≈ −18 dB (as used in GERD studies).
4. Watch for false negatives from wind-roughened water and false positives from smooth surfaces / radar shadow (mask steep slopes using DEM).
- *Implemented for the validation (prompt 05a, `src/thwake/water_s1.py`):* IW GRD VV, both orbit directions, slices of one day and pass mosaicked; focal median, 50 m radius. Otsu on a VV histogram (400 bins over −35…5 dB, 20 m) over the same region as for Sentinel-2; outside −25…−12 dB, the −18 dB fallback is used. Slope masking is not applied yet (prompt 06).

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
- **Obscured pixels** (clouds, no data; prompt 05a, `src/thwake/area.py`): low = none of them water, high = all of them water; best = the clear part's water share applied to them.
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
| Area → level (method) | **Reference reservoir** (Masinga, KenGen gauge levels): our level from satellite area via DEM curves vs published levels, absolute and relative agreement. Results: [validation.md](validation.md) (prompt 05a) |

## References

- Kansara et al. (2021), *Remote Sensing* — GERD storage from Sentinel-1: https://doaj.org/article/96a6380ae0874e958da0921c36e963c7
- Abou Samra & Ali (2021), *Egyptian J. Remote Sensing & Space Sciences* — GERD S1 −18 dB VV threshold: https://doaj.org/article/02171b2566294321aa95c98187e21c09
- NRIAG (2022) — GERD S1/S2/Landsat-9 volume monitoring: https://library.nriag.sci.eg/paper/302
- University of Twente thesis (2024) — S1 edge-Otsu, SWOT altimetry for GERD: https://essay.utwente.nl/essays/106406
- *Remote Sensing* (Jun 2025) — 17 reservoirs, S1/S2, NDWI + Otsu in GEE: https://doaj.org/article/3e8ba48190a8455f910b385e4dacef89
- INRAE — Sentinel-1/2 reservoir volume monitoring: https://hal.inrae.fr/hal-04066655
- Global Water Watch (WRI/Deltares/WWF): https://www.wri.org/initiatives/global-water-watch

### Comparable monitoring systems
- **Mekong Dam Monitor** (Stimson Center + Eyes on Earth) — weekly public monitoring of ~27 Mekong dams; Sentinel-1 primary, Sentinel-2 backup, Earth Engine classification, ALOS AW3D30 DEM for storage. The closest precedent for this project's method. Methods: https://www.stimson.org/2020/mekong-dam-monitor-methods-and-processes/ · HESS 2022: https://hess.copernicus.org/articles/26/2345/2022/
- **Reservoir Assessment Tool (RAT)** (University of Washington, SASWE) — open-source framework for storage change, inflow, evaporation and outflow from multi-sensor satellite data; operational for the Mekong River Commission (v2); packaged in v3. Docs: https://rat-satellitedams.readthedocs.io/ · RAT 3.0 paper: https://depts.washington.edu/saswe/rat/user_manual/RAT30PaperGMD.pdf

### Method references
- Pena-Luque et al. (2021), *Remote Sensing* — Sentinel-1 vs Sentinel-2 water extent on 29 reservoirs; both show increased negative bias near full: https://doaj.org/article/c9906843336643f3aad490b42e0175ba
- *Remote Sensing* 17(13), 2128 (2025) — S1/S2 NDWI + Otsu reservoir areas: https://www.mdpi.com/2072-4292/17/13/2128
- Water level from Sentinel-1 SAR + DEMs (arXiv 2012.07627): https://arxiv.org/pdf/2012.07627

### Global reservoir products (context / possible external checks)
- Altimetry levels: **DAHITI** (TU Munich; Schwatke et al., 2015, doi:10.5194/hess-19-4345-2015), **Hydroweb** (LEGOS/CNES), **G-REALM** (USDA/NASA), **HydroSat** (Univ. Stuttgart).
- Area/storage: **GRSAD** and the NASA MODIS/VIIRS reservoir product (Texas A&M/NASA), **GloLakes**, GRS, GRDL, **Global Water Watch**; **Pre-SWOT storage V2** (NASA PO.DAAC): https://podaac.jpl.nasa.gov/dataset/PRESWOT_HYDRO_L4_LAKE_STORAGE_TIME_SERIES_V2 ; **SWOT** (NASA/CNES, launched Dec 2022) measures water height and extent directly.
- Intercomparison: Cooley et al. (2025), *Environmental Research Letters* — five global storage datasets agree on relative storage (median RMSE ~8.7% of capacity) far better than absolute storage (~19.4%), and worst for new, highly variable and developing-country reservoirs.

### Sedimentation (long-term limitation)
- Bunyasi et al. (2013) — Masinga lost ~215 MCM (13.6%) of design capacity by 2011: https://ir-library.ku.ac.ke/handle/123456789/9784
- Maingi (2012), University of Nairobi — Masinga sediment budget (~6% loss in first 7 years): https://erepository.uonbi.ac.ke/items/bbdb43b8-38d8-4bd3-b07a-86fb9742adf2
