# Deployment (free)

**Can GitHub host it?** Partly. GitHub Pages hosts **static** sites only (HTML/JS/CSS + data files) — it can't run Python or Earth Engine on demand. So the project uses two free hosts, both linked from the README:

| Surface | Host | Why |
|---------|------|-----|
| **Interactive satellite app** | **Earth Engine Apps** (Google) | Runs live EE computation in the browser; free for non-commercial use; public URL, no login needed for viewers |
| **Story page + downloadable data** | **GitHub Pages** | Free for public repos; serves the Quarto-built site and CSV/GeoJSON |
| **Scheduled updates** | **GitHub Actions** | Free minutes for public repos; runs the Python pipeline monthly |

No custom domain (by choice). Default URLs:
- App: `https://<cloud-project-id>.projects.earthengine.app/view/thwake`
- Story page: `https://<github-username>.github.io/thwake-reservoir-remote-sensing-monitor/`

## One-time setup checklist

### Earth Engine
1. Sign up for Earth Engine with a Google account; create/choose a Google Cloud project and **register it for non-commercial use**.
2. Create Earth Engine assets folder for baseline layers (AOI, max-extent, AEV-related rasters if needed).
3. In the Code Editor: Apps → New App → select the script (copied from `app/ee-app/main.js`) → set app name `thwake` → publish. Make baseline assets readable by the app.
4. For GitHub Actions: create a **service account** in the Cloud project, register it for Earth Engine access, download its key **once**, store it as GitHub secret `EE_SERVICE_ACCOUNT_KEY`, then delete the local copy (or keep it outside the repo).

### GitHub
1. Create a **public** repo `thwake-reservoir-remote-sensing-monitor`.
2. Settings → Pages → Source: **GitHub Actions**.
3. Add secret `EE_SERVICE_ACCOUNT_KEY` (and `EE_PROJECT` as a variable).
4. Workflows (to be written in Phase 2): `ci.yml`, `update.yml` (cron monthly + manual), `pages.yml` (build Quarto → deploy).

### README
Top of README must show:
- 🛰️ **Live app:** link to EE App
- 📖 **Story page:** link to GitHub Pages
- 📊 **Data:** link to `data/processed/thwake_timeseries.csv`
- Last updated date + latest % full (can be auto-updated by the update workflow)

## Alternatives considered
See [ADR 0003](decisions/0003-free-deployment-ee-app-and-github-pages.md) (Streamlit Community Cloud, Hugging Face Spaces, ArcGIS StoryMaps).

## Free-tier limits to keep in mind
- GitHub Pages: site ≤ 1 GB, soft bandwidth ~100 GB/month — keep media compressed.
- GitHub repo: files > 50 MB warn, > 100 MB blocked — never commit rasters.
- Earth Engine non-commercial, **Community tier: 150 EECU-hours per month** (540,000 EECU-seconds), no billing account. Check usage at Cloud console → IAM & Admin → Quotas (filter `earthengine.googleapis.com`, "Noncommercial EECU-seconds per month"). Email alert at 80% configured 2026-10-10. Exceeding the limit → restricted mode (no charges; work pauses until the monthly reset). Development runs are the expensive part (one full Masinga validation ≈ 42 EECU-hours; 2026-10-10 used ~72 EECU-hours, 48%); routine Thwake updates (small AOI, new scenes only) should be far cheaper. Also: quotas on concurrent requests; the app may be slow under heavy traffic — acceptable.
- Actions: generous for public repos; keep jobs short (aggregate in EE, export small tables).
