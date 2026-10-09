# Project Brief — Thwake Reservoir Remote Sensing Monitor

## What is it?

An **independent, satellite-based monitor of Thwake Dam reservoir** in lower eastern Kenya. Using only free, public satellite and climate data, it tracks the reservoir from its empty valley (before filling) through filling (from first impoundment, currently targeted for early 2027) into operation — and publishes the results as a free interactive app and a public story page.

## Why does it need to exist?

1. **A major public investment with little independent visibility.** Thwake is planned to be Kenya's second-largest reservoir (~681–688 million m³). Progress information reaches the public mainly through press statements, and reported dates and figures shift over time. Satellites give independent, verifiable evidence of what is actually happening.
2. **No one is monitoring it from space.** A search (Oct 2026) found no satellite study, dashboard or story page for Thwake (or Mwache). Global reservoir tools (Global Water Watch, DAHITI, G-REALM, GRSAD) mostly cover established reservoirs and likely miss new ones.
3. **Rare timing.** A large reservoir filling for the first time, with a decade of pre-dam imagery in the archive, is an uncommon chance to document a landscape change from day one.
4. **A real water-quality question.** The Athi River — the main inflow — carries wastewater and runoff from Nairobi. Whether that shows up as turbid or algae-rich water in the new reservoir matters to downstream users.
5. **Semi-arid context.** In a hot, dry region, evaporation losses and dry-season behaviour of a large open reservoir matter for how much water is actually delivered.
6. **Global products are weakest exactly here.** A 2025 intercomparison of five global satellite reservoir-storage datasets (Cooley et al., *Environmental Research Letters*) found agreement is worst for **new reservoirs, highly variable reservoirs and reservoirs in developing countries** (median absolute-storage disagreement ~19% of capacity vs ~9% for relative storage). Thwake is all three — a focused, validated monitor fills that gap.
7. **Portfolio value.** Demonstrates in-demand skills: Earth Engine, radar + optical remote sensing, DEM-based volume modelling, time-series analysis, automation, and science communication.

## Who is it for?

**Primary audiences: portfolio (employers) and research.** The public is served too, but when trade-offs arise (naming, depth, terminology), favour rigour and field vocabulary — see [ADR 0007](decisions/0007-name-and-primary-audience.md).

| Audience | What they need | How the project serves them |
|----------|----------------|-----------------------------|
| **Public** — residents of Makueni, Kitui, Machakos; journalists | "Is it filling? Is the water clean? What does it mean for us?" | Plain-language story page, visuals first, no jargon |
| **Employers / portfolio reviewers** (water, climate, GIS, data roles) | Evidence of skill and rigour | Clean repo, documented architecture, reproducible pipeline, live app |
| **Researchers / water sector** (WRA, NGOs, academics, students) | Usable data and transparent methods | Downloadable CSV/GeoJSON, methods doc, uncertainty, citations |

## Main questions (answered in phases)

1. **How fast is it filling?** — area, level, volume, % full over time. *(Phase 2)*
2. **Is the water clean?** — turbidity and algae-bloom signals, especially near the Athi inflow. *(Phase 3)*
3. **What has the dam changed?** — land flooded, evaporation, downstream irrigation. *(Phase 4)*
4. Underpinning all: **what did the valley look like before?** *(Phase 1 baseline)*

## Goals

- G1. A credible, continuously updated time series of reservoir area / level / volume / % full with uncertainty.
- G2. A free, public, interactive app and story page linked from the README.
- G3. Seasonal water-quality indicator maps with careful, plain-language interpretation.
- G4. A frozen, documented pre-filling baseline.
- G5. Low-maintenance automation so the project survives for years.

## Non-goals

- Not a real-time or operational dam-management system.
- Not a lab-grade water-quality assessment; no claims that water is "safe" or "unsafe".
- No household-level or personally identifying information about displaced or local people.
- No paid data, services, or custom domain.
- Not covering Mwache Dam or the Mombasa water dashboard — those are **separate projects** (see [ADR 0001](decisions/0001-thwake-as-standalone-project.md)).

## Success criteria

| Phase | Done when… |
|-------|-----------|
| 1 Baseline | AOI, max-extent mask and AEV curve exist, are versioned, and the method is written up |
| 2 Filling | Public links (EE App + story page) show area & volume up to the latest image, with uncertainty |
| 3 Quality | At least one full season of water-quality indicator maps with interpretation |
| 4 Regional | Flooded land-cover summary, evaporation estimate, first downstream irrigation analysis |
| Overall | Someone outside the project (journalist, researcher, employer) can understand and cite it |

## Time commitment

**Ongoing.** Build the core, then update after each rainy season (Mar–May long rains, Oct–Dec short rains). Automation does the routine work; the human work is interpretation and writing.

## Owner

Julie Mugira — personal project.
