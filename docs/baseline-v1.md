# Baseline v1: Thwake reservoir before filling

> **Status: FROZEN on 2026-10-10.** Approved by the author. The SHA-256 of every frozen file is in [`data/baseline/baseline_v1.sha256`](../data/baseline/baseline_v1.sha256), and CI fails if any of them changes (`tests/test_freeze.py`). The git tag `baseline-v1` marks the commit on `main` ([human-steps.md](human-steps.md) H3). Any change now needs an ADR and a new version, `v2` ([AGENTS.md](../AGENTS.md) rule 8, [ADR 0006](decisions/0006-dem-based-volume-estimation.md)).

The baseline is everything the filling tracker (Phase 2) measures against: where water may be counted, how area converts to volume, and what the valley looked like before the gates closed. It is frozen **before** any filling data is analysed, so it cannot be tuned to fit the results.

Generated on 2026-10-09 with `python -m thwake baseline` (all steps); extent and AEV regenerated on 2026-10-10 to record the author's verification of the design figures (provenance fields only: geometry and curve unchanged). Methods: [methodology §1](methodology.md#1-phase-1--baseline-before-filling). Mask decision: [ADR 0011](decisions/0011-shared-aev-mask-and-reported-rim-leaks.md) (accepted 2026-10-10).

## Reproduce

```bash
make install                    # or: uv sync
earthengine authenticate        # once; EE_PROJECT in .env (human-steps.md H2)
python -m thwake baseline       # all steps, in order: extent, aev, landcover, river, composite
python -m thwake baseline --step river   # or one step
python -m thwake baseline --verify       # check the frozen files against the manifest
shasum -a 256 -c data/baseline/baseline_v1.sha256   # same check without Python
```

Once frozen, `thwake baseline` refuses to run (and to rewrite the manifest) unless given `--force`. Use that only to check reproducibility, then restore the frozen files with `git restore`: the `generated` dates in the metadata change on every run.

Parameters live in `config/settings.yaml` (FSL, wall axis, seed, pre-filling window, paths, asset ID) and `config/thresholds.yaml` (`baseline:` section). Re-running on 2026-10-09 reproduced the extent and AEV outputs from prompts 03–04 byte for byte. The only changes were the AEV `status` text and one added design-capacity source row; no numbers changed.

## Files

| File | What | Size |
|------|------|------|
| `data/baseline/aoi.geojson` | Area of interest: valley ≤ FSL + 5 m (917 m), rim pass (a) closed, islands filled | 66 kB |
| `data/baseline/max_extent.geojson` | Max-extent mask: pre-dam GLO-30 ≤ 912 m, connected upstream of the wall | 54 kB |
| `data/baseline/aev_curve_v1.csv` (+ `.json`) | Area–elevation–volume curve every 0.5 m, GLO-30 and SRTM; provenance, capacity and rim checks | 11 kB + 7 kB |
| `media/aev_curve_v1.png` | AEV figure | 144 kB |
| `data/baseline/landcover_flood_zone.csv` (+ `.json`) | Hectares per land-cover class inside the max extent: WorldCover 2021, Dynamic World Jun–Sep 2026 | 2 kB + 3 kB |
| `data/baseline/river_channel.geojson` | Historic river channel: JRC occurrence ≥ 10% inside the AOI | 18 kB |
| `media/before_composite.png` | True-colour "before" image, Sentinel-2 median Jun–Sep 2026, ~12 m/pixel | 3.4 MB |
| `data/baseline/before_composite.json` | Provenance of the composite (scenes, clear observations, rainfall, asset, task) | 2 kB |
| EE asset `projects/thwake-monitor/assets/thwake/before_composite_s2_v1` | Full-resolution composite: B2, B3, B4, B8, B11, B12 (reflectance ×10⁴, uint16) + `clear_obs`, 10 m, EPSG:32737, 1417 × 1626 px | 22.5 MB, in Earth Engine |
| `data/baseline/baseline_v1.sha256` | Freeze manifest: SHA-256 of the 10 files above (all but the asset) | 1 kB |

All files are under the 10 MB budget (checked in `tests/test_reference.py`). The asset cannot be hashed in the repository. On 2026-10-10 its metadata was checked against `before_composite.json`, and all of these matched:
- export task `W4JZINKN5GAL6TXQEDGSWC7O`, COMPLETED, asset updated 2026-10-09T21:03:54Z;
- the 7 bands, as uint16 on EPSG:32737 at 10 m;
- the properties `window` 2026-06-01/2026-10-01, `cloud_score_min` 0.6, `granules` 74, `baseline_version` v1;
- `clear_obs` min 8, median 15.

Re-exporting overwrites it, so the asset is not frozen by checksum. Do not re-export without a new version.

## Inputs

| Input | Value | Status |
|-------|-------|--------|
| Full supply level (FSL) | **912 m a.s.l.** | Sourced, **not a fallback**, and **human-verified by the author on 2026-10-10**: ESIA May 2025 §2.4 "New Design Parameters" (FSL 912 m a.s.l., freeboard 8.5 m, maximum flood level 920.5 m) and §2.3 ("the contour line 912 MASl represents this volume"). Unchanged across the 2009, 2014 and 2018 designs ([official_figures.csv](../data/external/official_figures.csv)). Vertical datum not stated in the sources ([open question 22](open-questions.md)). |
| Design capacity at FSL | 688 MCM (earlier designs 681 and 825 MCM) | Sourced (ESIA 2025; Ministry ToRs 2020, 2024; AfDB 2013); 688 MCM **human-verified 2026-10-10** (ESIA §2.4, reservoir storage). Used only as a check, never to fit the curve. |
| Official reservoir area | ~29 km² ("2,900 ha") | ESIA 2025, medium confidence ([open question 21](open-questions.md)). |
| Dam wall axis | −1.79363, 37.84005 → −1.78505, 37.85021 (≈1,476 m) | Digitised on Sentinel-2 (prompt 03), **human-verified** on Google Earth imagery from 25 Jun 2024 ([open question 1](open-questions.md)). |
| Reservoir seed / downstream check point | Athi–Thwake confluence / −1.81, 37.86 | Flood-fill start / leak check. |
| Pre-filling window | 2026-06-01 to 2026-10-01 (end exclusive) | Main dry season (Makindu WMO normals: ≤2 mm/month Jun–Sep, [climate table](https://en.wikipedia.org/wiki/Makindu); CHIRPS 7.1 mm Jun–Aug 2026). Impoundment had not started as of 2026-10-09; target end of January 2027 ([open question 5](open-questions.md)). |

## Earth Engine datasets and versions

| Role | Collection / image | Data used |
|------|--------------------|-----------|
| Primary DEM (extent, AOI, AEV) | `COPERNICUS/DEM/GLO30_2024_1` | Tiles acquired 2010-12-15 to 2014-05-24 (before construction, 2018-03-27); heights EGM2008 |
| Cross-check DEM (AEV) | `USGS/SRTMGL1_003` | Acquired 2000-02-11 to 2000-02-22; heights EGM96 |
| Land cover | `ESA/WorldCover/v200` | Image `ESA/WorldCover/v200/2021` (year 2021) |
| Land cover | `GOOGLE/DYNAMICWORLD/V1` | 18 images, 2026-06-01 to 2026-09-24, EPSG:32737 |
| River channel | `JRC/GSW1_4/GlobalSurfaceWater` | Occurrence over March 1984 to December 2021 |
| "Before" composite | `COPERNICUS/S2_SR_HARMONIZED` | 74 granules (tiles 37MCT, 37MCU) on 37 dates, 2026-06-01 to 2026-09-29 |
| Cloud mask | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | `cs` ≥ 0.6 counts as clear |
| Dry-season check | `UCSB-CHG/CHIRPS/DAILY` | 92 days available in the window, to 2026-08-31 |

All IDs are in `config/ee_collections.yaml`.

## Results

### Extent ([methodology §1.1–1.2](methodology.md#11-area-of-interest-aoi))

| | Value | Compared with |
|---|---|---|
| Max extent (≤ 912 m, upstream of the wall) | **30.36 km²** | Official ~29 km²: **+4.7%** |
| AOI (≤ 917 m, FSL + 5 m) | 35.11 km² | One rim pass closed: (a) −1.79667, 37.82917, overflows at ≈913.0 m (± 0.1 m search precision, plus DEM error of a few metres) |

### AEV curve vs official capacity ([methodology §1.3](methodology.md#13-areaelevationvolume-aev-curve))

| | Copernicus GLO-30 (2010–14) | SRTM (Feb 2000) |
|---|---|---|
| Area at FSL | 30.36 km² | 30.04 km² |
| **Volume at FSL** | **743.4 MCM** | **795.8 MCM** |
| vs design 688 MCM | +8.1% | +15.7% |
| Inside design history 681–825 MCM? | yes | yes |
| Volume at the official area (29 km²) | 696.4 MCM (level 910.4 m) | 696.2 MCM (level 908.6 m) |
| dV/dh at FSL | 30.1 MCM per m | 29.9 MCM per m |
| First rim overflow (wall barrier only) | ≈913.0 m | **≈910.0 m, below FSL** |

GLO-30 is the primary curve; SRTM is the cross-check. The difference between them (743–796 MCM at FSL, ±3.4% around their mean) is one part of the volume uncertainty that Phase 2 (prompt 07) will propagate. At the same *area*, the two curves agree within 1% near FSL. Since Phase 2 converts measured area to volume, the gap at FSL matters less in practice than it looks here.

### Land cover in the flood zone ([methodology §1.4](methodology.md#14-pre-filling-reference))

Inside the 30.36 km² max extent: the land the full reservoir would cover. Pixel centres inside the mask, geodesic pixel areas. The classes add up to the mask area (30.37 and 30.36 km²).

| Class | ESA WorldCover (2021) | Dynamic World (Jun–Sep 2026) | Range |
|-------|---:|---:|---|
| Shrub and scrub | 1,183 ha | 1,670 ha | 1,183–1,670 ha |
| Cropland | 854 ha | 348 ha | 348–854 ha |
| Grassland | 553 ha | 1 ha | 1–553 ha |
| Bare / sparse vegetation | 296 ha | 189 ha | 189–296 ha |
| Trees | 107 ha | 624 ha | 107–624 ha |
| Water | 43 ha | 167 ha | 43–167 ha |
| Built-up | 1 ha | 31 ha | 1–31 ha |
| Flooded vegetation | 0 ha | 6 ha | 0–6 ha |

Published accuracy: WorldCover 2021 v200 has 76.7% global overall accuracy ([ESA](https://worldcover2021.esa.int), [validation report](https://pure.iiasa.ac.at/18981/1/WorldCover_PVR_V2.0.pdf)). Dynamic World has 73.8% agreement with an expert-consensus test set ([Brown et al. 2022, *Scientific Data*](https://doi.org/10.1038/s41597-022-01307-4)). These are global figures, not Thwake-specific.

**How to read this:** the products agree that the flood zone is mostly **shrubland, farmland and bare ground**, with little built-up land. They disagree on how it splits between shrub, grass, crops and trees. Part of that is real change between 2021 and 2026 (construction, clearing ahead of filling). Part is method: Dynamic World almost never labels dryland grass, and the dry-season window shows fields as bare or shrub. **Do not publish a single figure per class.** Use the range, or say "roughly 350–850 ha of cropland", until checked ([open question 23](open-questions.md)). Figures are at area level only (rule 9).

### Historic river channel

`river_channel.geojson`: pixels inside the AOI where JRC saw water in at least 10% of valid observations, 1984–2021.

| JRC occurrence ≥ | 5% | **10% (used)** | 25% | 50% |
|---|---:|---:|---:|---:|
| Area in AOI (km²) | 0.426 | **0.353** | 0.141 | 0.017 |

At 10%, the channel covers 0.353 km² in 50 pieces, 0.271 km² of it inside the max extent. The full sensitivity range is **0.02–0.43 km²**, and the area ever seen as water is 0.467 km². Occurrence never exceeds 59% here: the Athi is narrow and seasonal, so its 30 m pixels are mixed. The channel is broken, and the Thwake arm barely shows. In Phase 2, water inside this layer before impoundment is the river, not the reservoir.

### "Before" composite

`media/before_composite.png`: Sentinel-2 median, **2026-06-01 to 2026-09-29**, 37 acquisition dates, Cloud Score+ ≥ 0.6. Every pixel has at least 8 clear observations (median 15). CHIRPS rainfall over the AOI was 7.1 mm for Jun–Aug 2026, confirming a dry window; September was not yet in CHIRPS. The image shows the finished wall and spillway, the construction site, and a dark pond just upstream of the wall. The pond is ≈16 ha of water by Dynamic World, which suggests construction water, not impoundment. Full-resolution bands are in the Earth Engine asset (export task ID in `before_composite.json`, run 2026-10-09).

## Known issues

1. **SRTM's rim leaks below FSL.** With only the wall as a barrier, the SRTM basin overflows at ≈910 m through pass (a), 1.1 km WSW of the wall. The SRTM curve uses the GLO-30 mask, so this is reported, not re-masked. The saddle dams (new 2025 scope) are not yet visible on imagery ([open questions 17, 20](open-questions.md)).
2. **Volume at FSL is 8–16% above the 688 MCM design.** This is consistent with a ~1.8 m vertical offset between the DEMs and the design survey or its datum. The cause is unknown ([open questions 15, 21, 22](open-questions.md)).
3. **Max extent is 4.7% larger than the official ~29 km².** Possible causes are the same as in item 2, plus 30 m pixel edges.
4. **Land-cover products disagree strongly per class** (table above). The range is wide for grass, crops and trees.
5. **Dynamic World labels the dry sandy Thwake riverbed and the Athi channel as water** (167 ha). Its water class here is river channel, not impounded water.
6. **JRC river channel is fragmented** at 30 m. Its area is sensitive to the threshold (0.02–0.43 km²).
7. **JRC occurrence includes 2018–2021, after construction started.** These are 4 of ~38 years and carry little weight.
8. **WorldCover is from 2021, three years into construction**, so the construction site may already show as bare or built.
9. **The composite PNG has no burned-in date or outline.** That keeps it usable for a before/after slider; captions must give the dates (rule 4).

## Freeze record

- [x] Outputs reviewed by the author (2026-10-10).
- [x] FSL 912 m and 688 MCM human-verified against ESIA May 2025 §2.3–2.4 (2026-10-10).
- [x] Earth Engine asset export completed; metadata matches `before_composite.json` (2026-10-10).
- [x] Mask decision recorded as [ADR 0011](decisions/0011-shared-aev-mask-and-reported-rim-leaks.md), accepted by the author on 2026-10-10.
- [x] Freeze manifest `data/baseline/baseline_v1.sha256` written; CI gate `tests/test_freeze.py`.
- [ ] Author: merge the PR into `main` with a **merge commit** (not squash), then tag that commit on `main`: `git tag baseline-v1` and `git push origin baseline-v1` ([human-steps.md](human-steps.md) H3).
