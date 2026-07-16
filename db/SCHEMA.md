# SCHEMA.md — data contracts (update in the same PR as any schema change)

Conventions: **UTC timestamps everywhere**; EPSG:4326 storage, EPSG:32748 (UTM 48S) for metric math; concentrations µg/m³ unless `is_index=true`.

## Source contracts

### SPKU (udara.jakarta.go.id) — ✅ VERIFIED 2026-07-03 (cross-referenced from a sibling project's live research, `D:\Jalan.in\udara.md`)
- **No JSON API** — the portal was redesigned to Server-Side Rendered HTML; the old `POST /api/lokasi_stasiun_udara` is dead (404). This explains workflow.md B2's ECONNRESET: active WAF/bot protection, not a transient fault.
- **Two-stage scrape:**
  1. `GET /lokasi-spku` — one request returns **all 105 stations** (client-side pagination only slices already-rendered rows). Extract each row's `/spku/<uuid>` link.
  2. `GET /spku/<uuid>` — embeds `var SPKU_DETAIL_DATA = {...};` in the HTML. Regex out the JSON object (brace-balanced, do not use a naive non-greedy regex — `metrics[]`/`forecast[]` contain nested objects), `json.loads` it. No DOM parser needed for stage 2.
- **Station count: 105** (verified via scrape) — **not 111** as press releases claim. Trust the scrape.
- **Per-station fields (from `SPKU_DETAIL_DATA`):**
  - `datasourceKode` → `stations.station_id`; `datasourceName` → name; `type` (`"Reference"`/other) → `stations.kind`
  - `latitude`/`longitude` — **only on the detail page**, real floats (not on the list page)
  - `ispuValue` (int, composite ISPU) + `ispuParameter` (the dominant pollutant) + `ispuConcentration` (µg/m³, **dominant pollutant only**)
  - `metrics[]` — reference stations report up to 6 parameters (CO, NO2, SO2, PM25, O3, PM10) as `{metricName, currentIspu, currentRaw, history}`; low-cost (`DKI_PM25_*`, `LCS-*`) are PM25-only. **`currentRaw` was `null` in the one captured sample** — do not assume full per-pollutant concentrations are reliably populated; verify across more live samples before leaning on it for Layer C.
  - `lastUpdate` — **no timezone suffix, treat as WIB (UTC+7)**, convert to UTC before storing.
  - `dailyIspu30Days` — 30-day rolling history embedded on every detail fetch. **⚠ exact field shape not yet captured** (elided in source research as "…30 rows…") — a genuine opportunity to bootstrap history without waiting weeks (relevant to the July MVP timeline), but **do not build a parser until one live sample's shape is confirmed**. New TODO: P0.1c.
  - `forecast[]` — DLH's own posted forecast, shape IS known: `{label, date, icon, ispu, category}`. Opportunity: score `twin/backtest.py` against DLH's own forecast, not just persistence — a sharper validation claim than the original plan.
- **Critical quirks (must implement, not optional):**
  1. **Staleness**: a station can show a plausible `ispuValue` while `lastUpdate` is **months old** (one sample was ~6 months stale) — indistinguishable from live except by checking `lastUpdate`. Apply a recency cutoff (a tuning choice, not a hard fact — sibling project used 6h); tag stale reads `qa_flag='stale'` rather than silently dropping them (uncertainty-is-a-feature, agents.md §5.3) so analytics can filter deliberately.
  2. **Two Kepulauan Seribu stations are out of scope** (`DKI_TANJONGTIMOR`, `LCS-14`) — filter by mainland lat/lon bounds, not by name.
  3. **WAF/bot protection is active** — gentle scraping only: honest UA (already in `.env.example`), bounded concurrency, spacing between requests. Aggressive polling gets connections reset, even on `robots.txt`.
- Historical cold-start (separate from `dailyIspu30Days`): yearly ISPU datasets — old `data.jakarta.go.id` deep links 302 to `satudata.jakarta.go.id` (workflow.md B1); re-locate datasets there if `dailyIspu30Days` alone isn't enough depth.

### BMKG (api.bmkg.go.id/publik/prakiraan-cuaca) — ✅ VERIFIED (D:\Jalan.in\bmkg.md, 2026-06-25)
- Query: `?adm4=<code>` ONLY (adm1/adm2 → 301). Rate ≤60/min; we poll 267 codes 2×/day.
- Response: `data[0].cuaca` = **nested per-day arrays** (3 days × 8 × 3-hourly). Fields used: `wd_deg` (wind FROM, ° cw from N), `ws` (m/s), `hu` (%), `t` (°C), `tcc` (%), `tp` (mm/3h), `utc_datetime`.
- Every run stored (pseudo-nowcast archive; no historical API exists).
- adm4 master list: `cahyadsn/wilayah` Kemendagri mirror → `kelurahan` table (267 rows for province 31).

### NASA FIRMS — key required
- VIIRS/MODIS active fire, Jakarta bbox (~ -6.6..-5.9 lat, 106.3..107.2 lon incl. upwind margin), daily pull → `fire_events`. Attribution required.

### GEE satellite — noncommercial tier, service-account auth
- Products → `satellite_grids.product`: `s5p_no2|s5p_so2|s5p_co|s5p_aer_ai` (COPERNICUS/S5P L3), `maiac_aod` (MODIS/061/MCD19A2), `derived_pm25` (our AOD calibration output, with `validation_runs.kind='aod_calibration'` R²).
- Column values ≠ ground truth: derived PM2.5 is model output; cloud gaps stored as NULL + `qa='cloud'`, never interpolated silently.

### CAMS (ADS) — key required
- Regional PM2.5 analysis+forecast, Jakarta-region mean → `regional_background`; twin background term. Attribution "Copernicus Atmosphere Monitoring Service".

## Results tables
`polar_stats` (Layer A), `hotspots` (Layer B, district-level + population), `source_factors`/`source_candidates` (Layer C/A), `forecast_surfaces` (twin: plume|ml|whatif), `validation_runs` (LOOCV, forecast skill, NMF stability, AOD calibration). See analytics module docstrings for method assumptions.
