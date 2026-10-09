# Data Sources

All free. Earth Engine IDs are as known at planning time — ⚠️ verify current versions in the EE Data Catalog before use and record them in `config/ee_collections.yaml`.

| Dataset | Use | Earth Engine ID | Resolution / cadence | Licence / terms |
|---------|-----|-----------------|----------------------|-----------------|
| Sentinel-2 L2A (surface reflectance) | Water mask, water quality, NDVI, true colour | `COPERNICUS/S2_SR_HARMONIZED` | 10–20 m, ~5 days | Copernicus open licence |
| Cloud Score+ for S2 | Cloud masking | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | 10 m, per scene | Google / open |
| Sentinel-1 GRD | Cloud-proof water mask | `COPERNICUS/S1_GRD` | 10 m, ~6–12 days | Copernicus open licence |
| Copernicus DEM GLO-30 | AOI, max extent, AEV curve (primary), slope mask | `COPERNICUS/DEM/GLO30_2024_1` (2024_1 release; the older `COPERNICUS/DEM/GLO30` is deprecated in EE) | 30 m; tiles over Thwake acquired 2010-12-15 to 2014-05-24 (EE tile metadata, checked 2026-10-09) | Copernicus DEM licence (free, attribution) |
| SRTM | AEV curve cross-check | `USGS/SRTMGL1_003` | 30 m; acquired 2000 | Public domain |
| JRC Global Surface Water | Historic river channel / prior water | `JRC/GSW1_4/GlobalSurfaceWater` | 30 m, 1984–2021 | Copernicus / JRC open |
| ESA WorldCover | Baseline land cover | `ESA/WorldCover/v200` | 10 m, 2021 | CC BY 4.0 |
| Dynamic World | Near-real-time land cover | `GOOGLE/DYNAMICWORLD/V1` | 10 m, per S2 scene | CC BY 4.0 |
| CHIRPS daily | Catchment rainfall | `UCSB-CHG/CHIRPS/DAILY` | ~5 km, daily | Public domain-like (cite) |
| ERA5-Land daily | Evaporation, temperature | `ECMWF/ERA5_LAND/DAILY_AGGR` | ~11 km, daily | Copernicus licence |
| HydroSHEDS / HydroBASINS | Catchment boundary | `WWF/HydroSHEDS/v1/Basins/hybas_*` | Vector | Free with attribution |
| OpenStreetMap | Basemap, dam wall/roads | (tiles / Overpass, not EE) | Vector | ODbL — attribution required |
| Planet NICFI tropical basemaps | Visual validation (optional) | `projects/planet-nicfi/assets/basemaps/africa` | ~4.7 m monthly | Free with NICFI sign-up; non-commercial; check terms |

## Non-satellite sources

- Official dam specs and announcements (AfDB, Ministry of Water / NWHSA, Kenya News Agency) → `data/external/official_figures.csv` with a `source_url` column.
- Any in-situ water quality (WRA, academic) → `data/external/` with provenance.

## Attribution

The story page and README must include attribution for Copernicus (Sentinel, DEM), CHIRPS, ESA WorldCover, OpenStreetMap, and any others used.
