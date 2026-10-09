# Risks & Limitations

## Scientific limitations (state these publicly)

| Limitation | Effect | Mitigation / how communicated |
|-----------|--------|-------------------------------|
| 10 m pixels; mixed shoreline pixels | Area error, larger when reservoir is small | Edge sensitivity range; uncertainty band |
| DEM vertical error (metres) | Volume uncertainty, largest early in filling. At FSL, 1 m of offset ≈ 30 MCM (4.4%); SRTM averages 1.7 m below GLO-30 in the mask and gives +52 MCM at FSL (prompt 04) | Two DEMs; report ranges; sanity-check vs official capacity. Area→volume (the Phase 2 path) is much less sensitive to a uniform offset than level→volume |
| DEM may include early construction works | Valley shape slightly wrong near dam | GLO-30 tiles over Thwake acquired 2010-12 to 2014-05, before construction started (2018-03-27); SRTM is 2000 |
| Low reservoir rim (saddles) | In the pre-dam DEM the basin overflows ~1 m above FSL (open questions 17, 20), so DEM error can open or close a rim pass | Wall burned in as a barrier; downstream-leak and search-edge checks stop the pipeline; AOI closes passes explicitly and lists them |
| Clouds (S2) | Gaps | Sentinel-1 fills gaps; DEM gap-fill method |
| Wind / vegetation in water (S1) | Missed or false water | Otsu per scene; S1–S2 cross-check; QA flags |
| Water quality is a colour-based proxy | Not concentrations; can't prove pollution | Careful wording; zone/relative comparisons; seek in-situ data |
| No official operational data | Can't validate against true storage | Use official announcements when available; Global Water Watch |

## Project risks

| Risk | Likelihood | Impact | Response |
|------|-----------|--------|----------|
| Filling delayed or slow (poor rains, construction, funding) | Medium | Little change to show for months | Still a valid finding; focus on baseline and storytelling meanwhile |
| Key specs (FSL, capacity, coordinates) unavailable | Medium | Weaker AEV curve | Estimate FSL from crest height & DEM; document assumption; update when found |
| Earth Engine terms/quotas change | Low | Pipeline breaks | Port to Copernicus Data Space / Planetary Computer (open STAC) via ADR |
| Maintenance fatigue (ongoing project) | Medium | Project goes stale | Automate updates; keep human reviews to twice a year |
| Two-language drift (Python vs EE App JS) | Medium | App and CSV disagree | Shared thresholds in config; CSV is canonical; periodic comparison |
| Misinterpretation by public/media | Medium | Reputational / harm | Uncertainty on every number; "what this does and doesn't show" box on story page |
| Sensitive social topics (resettlement) | Low–Med | Harm to people | Area-level only; no household data; neutral tone |
