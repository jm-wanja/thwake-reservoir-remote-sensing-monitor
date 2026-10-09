# Background — Thwake Dam

> Facts gathered Oct 2026 from web sources; key figures checked against Ministry of Water documents on 2026-10-09 (prompt 01). Anything still marked ⚠️ verify must be confirmed against an official document (AfDB, Ministry of Water, NWHSA, contractor) before appearing publicly. Machine-readable values with sources: [`data/external/official_figures.csv`](../../data/external/official_figures.csv).

## Key facts

| Item | Value | Source / status |
|------|-------|-----------------|
| Name | Thwake Multipurpose Water Development Program (TMWDP), Phase 1: Thwake Multipurpose Dam | [S1], [S2] |
| Location | On the Athi River, ~1 km downstream of the Athi–Thwake confluence, Makueni–Kitui border; wall joins Kathukuni Hill (Makueni) and Kilisa Hill (Kitui); ~180 km SE of Nairobi | [S1], [S2] |
| Athi–Thwake confluence | −1.7810, 37.8403 (OSM river junction; GeoNames stream mouth within ~70 m) | [S10], [S11] — medium confidence |
| Dam-wall coordinates | **Digitised axis:** −1.79363, 37.84005 (SW, Makueni) → −1.78505, 37.85021 (NE, Kitui); midpoint ≈ −1.7893, 37.8451; length ≈1,476 m (ESIA crest 1,500 m) | ⚠️ verify — digitised on a Sentinel-2 composite (Jun–Sep 2026) in prompt 03, ±~20 m; not a published value. Prompt 01 estimate (≈ −1.789, 37.844) was ~110 m off. **Do not use** the ESIA's stated 1°46′S 37°43′E: it is the gazetteer point for a different feature ("Thwake Sub-Surface Dam"), ~14 km west [S1], [S11] |
| Full supply level (FSL) | **912 m a.s.l.** | [S1] §2.4 (current design); same FSL in the 2009 and 2014 designs [S1] §2.2, [S4] — high confidence |
| Storage capacity at FSL | **688 million m³** (current design) | [S1], [S2], [S3] — high confidence. Superseded designs at the same FSL: 681 MCM (CAS 2014) [S4], 825 MCM (Samez 2009) [S1]. SMEC web page shows "668" [S6], probably a typo |
| Reservoir area at FSL | ~29 km² (2,900 ha), extending ~12 km upstream | [S1], [S2] — design figure, medium confidence |
| Catchment area | 10,276 km² (10,272 km² in ESIA §2.4 and [S5]) | [S1], [S2] |
| Dam type | Concrete-face rockfill dam (CFRD) | [S1], [S5] |
| Dam height | **80.5 m** | [S1], [S2], [S3] — high confidence. History: 84 m (2009 design / 2013 NEMA licence) → 77–77.5 m (2014 design / 2016 tender) → 80.5 m (2018 detailed design) [S1] |
| Maximum flood level / crest | Max flood level 920.5 m a.s.l., freeboard 8.5 m above FSL [S1]; dam-safety consultant gives **crest** 920.5 m a.s.l. [S5] | Sources differ on whether 920.5 is crest or flood level — see open questions |
| Construction start | **27 March 2018** (site handover = works commencement) | [S2]; "started in March 2018" [S1] — high confidence |
| River diversion | Athi diverted into two diversion tunnels, late Dec 2021 | [S6] — medium |
| Status (Oct 2026) | ~95% complete; works resumed after ~2-year funding stall | [S7], [S8] — medium |
| Impoundment | **Not started** as of 2026-10-09. Current official target: gates closed **by end of January 2027** | [S7], [S8]. Earlier targets (Apr–Jun 2026; Oct–Nov 2026 [S12]) slipped. ⚠️ verify actual start date when it happens |
| Size rank | Expected to be Kenya's 2nd-largest reservoir | [S12] — ⚠️ verify against other Kenyan reservoirs' capacities before public use |
| Main inflow | Athi River (perennial; receives Nairobi wastewater/runoff upstream); Thwake River is seasonal | [S1]; Afrik21 on Athi clean-up |
| Purposes | Domestic water ~150,000 m³/day for ~1.3 million people (rural Kitui & Makueni, Konza Techno City in Machakos); irrigation up to 40,000 ha (~100,000 acres); hydropower ~20 MW; downstream flow regulation for flood control & drought mitigation | [S2], [S3], [S1] — high confidence (design targets, later phases) |
| Funding | Government of Kenya + African Development Bank (jointly funded); AfDB approved €68.39 M additional financing Jun 2026 | [S1], [S3]; [S9] |
| Contractor / engineer | China Gezhouba Group Company Ltd; supervised by SMEC | [S1] |

## Why the context matters for the method

- **Semi-arid climate** → clearer skies than the coast → Sentinel-2 optical will be usable more often than at Mwache; evaporation is a significant loss term.
- **Polluted inflow** → water-quality monitoring near the inflow arm is the distinctive angle.
- **Large reservoir, possibly multi-season fill** → the time series will be long; automation matters.
- **Pre-dam DEMs exist** (SRTM 2000; Copernicus GLO-30 from TanDEM-X; the tiles over Thwake were acquired 2010-12 to 2014-05) → valley shape before construction is known. Construction began 27 Mar 2018 [S2], so both DEMs predate the main works.
- **Design capacity at the same 912 m FSL has ranged 681–825 MCM across design stages** → the "official" figure is itself survey-dependent; the Phase 1 DEM check should be judged against that context, not a single number.
- **Impoundment slipped to ~end Jan 2027** → more time for the Phase 1 baseline; first filling may fall after the Oct–Dec 2026 short rains.

## Sources

Primary (Government of Kenya / project consultants):
- [S1] Ministry of Water, Sanitation & Irrigation — *Thwake MWDP Phase 1, Variation of the Project Works: ESIA Study Report*, May 2025: https://www.irrigation.go.ke/sites/default/files/downloads/ENVIRONMENT%20SOCIAL%20IMPACT%20ASSESSMENT%20(ESIA)%20-%20THWAKE%20MULTIPURPOSE%20WATER%20DEVELOPMENT%20PROGRAM%20(Final).pdf
- [S2] Ministry of Water — *ToR: stakeholder awareness on dam break and emergency preparedness*, Oct 2024: https://water.go.ke/sites/default/files/2025-01/TOR-CONSULTANCY%20SERVICES%20TO%20UNDERTAKE%20STAKEHOLDER%20AWARENESS%20AND%20COMMUNITY%20SENSITIZATION%20COMMUNICATION%20CAMPAIGNS%20ON%20DAM%20BREAK%20AND%20EMERGENCY%20PREPAREDNESS%20.pdf
- [S3] Ministry of Water — *ToR: institutional capacity assessment for O&M of TMWDP* (PDF dated Jun 2020): https://www.water.go.ke/sites/default/files/2025-01/TOR%20for%20identification%20of%20Dam%20Managament%20and%20Operations%20Agency.pdf
- [S4] Ministry of Water — *ToR: Athi River basin modelling* (PDF dated Jan 2019; describes the superseded CAS 2014 design, 77 m): https://water.go.ke/sites/default/files/2025-01/TERMS%20OF%20REFERENCE%20FOR%20CONSULTING%20SERVICES%20FOR%20ATHI%20RIVER%20BASIN%20MODELLING.pdf
- [S5] Studio Pietrangeli (dam-safety review consultant, 2019–) — project page, accessed 2026-10-09: https://www.pietrangeli.com/thwake-multipurpose-dam-kenya-africa/
- [S6] SMEC — project page, accessed 2026-10-09: https://www.smec.com/project/thwake-multipurpose-water-development-project-2/

News:
- [S7] The Star (credited to KNA), 1 Sep 2026 — construction resumes; filling expected by end Jan 2027: https://www.the-star.co.ke/counties/eastern/2026-09-01-construction-of-thwake-dam-resumes
- [S8] The County Diary, 9 Oct 2026 — 95% complete, January 2027 impounding target: https://thecountydiary.co.ke/2026/10/thwake-dam-hits-95-completion-as-government-targets-january-2027-for-water-impounding/
- [S9] EnergyGlobal, 18 Jun 2026 — AfDB €68.39 M additional financing: https://www.energyglobal.com/other-renewables/18062026/
- [S12] Kenya News Agency, Jul 2026 — impoundment expected Oct–Nov 2026 (since superseded): https://www.kenyanews.go.ke/?p=172593
- Engineering News — Thwake programme: https://www.engineeringnews.co.za/article/thwake-multipurpose-water-development-programme-kenya-2017-12-01
- Afrik21 — Athi River clean-up: https://afrik21.africa/en/kenya-the-state-is-cleaning-up-the-athi-river-the-main-source-of-the-thwake-dam
- Hydropower & Dams: https://www.hydropower-dams.com/?p=2965

Geographic:
- [S10] OpenStreetMap (ODbL) — Athi River way 327750821 (starts at confluence) and Thwake River way 261335962, accessed 2026-10-09: https://www.openstreetmap.org/way/327750821
- [S11] GeoNames search "Thwake" (Kenya) — stream mouth −1.780517, 37.839671; "Thwake Sub-Surface Dam" −1.766667, 37.716667: https://www.geonames.org/search.html?q=Thwake&country=KE

## Documents still to find (for verification)

Could not be retrieved automatically (AfDB site returns 403 to scripts; kenyanews.go.ke and thwakedam.go.ke failed TLS from the agent's machine) — human to download/read (HUMAN-STEPS H6):
- AfDB Phase I appraisal report: https://www.afdb.org/fileadmin/uploads/afdb/Documents/Project-and-Operations/Kenya_-_Thwake_Multi-Purpose_Water_Development_Program_%E2%80%93_Phase_I_-_Appraisal_Report.pdf
- AfDB Implementation Progress Report, Jun 2024: https://www.afdb.org/sites/default/files/documents/projects-and-operations/kenya_-_thwake_multipurpose_water_development_program_phase_1_-_p-ke-e00-008_-_ipr_june_2024.pdf
- AfDB ESIA summary and RAP summary (area-level context only)
- SMEC 2018 detailed design report — ideally its **area–elevation–capacity table**, the best independent check for the Phase 1 AEV curve
- Any official reservoir level / storage releases once impoundment begins

## Related global examples (method references)

See [03-methodology.md §References](03-methodology.md#references) — GERD satellite filling studies, multi-reservoir Sentinel-1/2 GEE study, Global Water Watch.
