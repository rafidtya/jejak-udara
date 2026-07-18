# JejakUdara API — reference for the frontend

Base URL (dev): `http://localhost:8000` · Interactive docs: `http://localhost:8000/docs` (Swagger)
CORS is open in dev. All responses JSON. Timestamps ISO-8601 UTC. Coordinates `[lon, lat]` (GeoJSON order).

> **Honesty contract (must surface in the UI, agents.md §5):** station points are **measured**;
> surfaces and twin outputs are **estimasi/simulasi**; every attribution carries a **confidence**;
> hotspot claims are **district-level**. Each relevant endpoint returns a `disclaimer` string — show it.

Run the backend: `docker compose -f infra/docker-compose.yml up -d db` → `make migrate` → `make seed`
→ `make run-batch` → `make api`. Data refreshes via the ingestion scheduler (`make run-ingest`).

---

## GET /health
`{ "status": "ok" }` — liveness probe.

## GET /meta
System + freshness banner.
```json
{ "station_count": 105,
  "ingestion": [{ "source": "spku", "last_success": "2026-07-16T…Z", "rows_24h": 4200 }, …],
  "disclaimer": "Data snapshot dari sumber publik (DLH SPKU, BMKG, Open-Meteo)." }
```

## GET /stations  → GeoJSON FeatureCollection (MEASURED points)
Every station with its latest dominant ISPU. Use for the map markers.
```json
{ "type": "FeatureCollection", "features": [
  { "type": "Feature", "geometry": { "type": "Point", "coordinates": [106.83, -6.16] },
    "properties": { "station_id": "DKI1", "name": "Bundaran HI", "kind": "reference",
                    "kecamatan": "MENTENG", "ispu": 103, "ts": "2026-07-16T03:00:00Z",
                    "stale": false } } ] }
```
`kind` ∈ `reference|low_cost`. `stale=true` → render grayed; do not treat as current. `ispu` is 0–500 (ISPU index; color by the standard bands — Baik ≤50, Sedang ≤100, Tidak Sehat ≤200, Sangat Tidak Sehat ≤300, Berbahaya >300).

## GET /surface?pollutant=pm25&kind=measured  → interpolated grid (ESTIMASI)
Row-major grid, **row 0 = SOUTH** (flip for a north-up canvas). Render as a heatmap overlay.
```json
{ "available": true, "run_ts": "…", "bbox": [106.65,-6.40,107.00,-6.05],
  "nrows": 70, "ncols": 70, "cell_m": 500, "metric": "ISPU (indeks, dominan)",
  "n_stations": 92, "values": [/* nrows*ncols floats */],
  "disclaimer": "Permukaan interpolasi (estimasi spasial), bukan pengukuran langsung." }
```
`available:false` (with `reason`) until the batch job has produced a surface. `kind` ∈ `measured|plume|ml|whatif`.

## GET /hotspots  → district-level (ESTIMASI)
```json
[ { "district": "MENTENG", "pollutant": "pm25", "gi_z": 2.1, "ts": "…", "flagged": true }, … ]
```
`gi_z` = z-score of the district mean vs city mean; `flagged` = notably elevated. **District, not street.**

## GET /sources  → attribution (PROBABILISTIC)
```json
{ "candidates": [ { "geometry": { "type": "Polygon", … }, "method": "polar_dominant",
                    "notes": "DKI1: arah 270 deg, CPF=0.62", "ts": "…" } ],
  "factors":    [ { "label": "traffic", "confidence": 0.72, "profile": {…}, "diurnal": {…},
                    "evidence": ["jalan besar 300m NE"], "run_ts": "…" } ],
  "disclaimer": "Atribusi bersifat probabilistik; setiap sumber punya tingkat keyakinan." }
```
`candidates` = directional/triangulated source *areas* (polygons, not pins). `factors` = source-type guesses (Layer C) — **always show `confidence`, never the bare `label`.** Both arrays may be empty on a fresh DB (attribution needs accumulated history).

## GET /polar/{station_id}  → wind-rose bins for one station
```json
[ { "wd_bin": 270, "ws_bin": 3, "mean_conc": 48.2, "n": 40, "cpf": 0.61 }, … ]
```
`wd_bin` = wind direction the pollution came FROM (° from N); `cpf` = P(high pollution | this bin). Drives the polar plot in the Sumber view.

## GET /validation  → the "how do we know it's right" numbers (SHOW THESE)
```json
[ { "kind": "loocv", "pollutant": "pm25",
    "metrics": { "rmse": 28.5, "mae": 20.1, "r2": -0.05, "n": 92, "metric": "ISPU (indeks, dominan)" },
    "run_ts": "…" } ]
```
Latest per (kind, pollutant). `kind` ∈ `loocv|forecast_skill|nmf_stability|aod_calibration`. **Surface these honestly** — a low R² with an explanation reads as methodological maturity; hiding it reads as a black box.

## POST /twin/whatif  → scenario simulation (SIMULASI, real plume engine)
Request:
```json
{ "disable": ["industri"], "scale": { "lalu_lintas": 0.5 }, "rain_mm": 5.0,
  "wd_deg": 270, "ws": 3.0 }
```
All fields optional. `disable`/`scale` keys are source labels from the response's `sources[].label`
(`lalu_lintas|industri|pembakaran`). Response:
```json
{ "available": true, "delta_mean_pct": -0.3, "delta_max_local_ugm3": -29.6,
  "sources": [ { "lon":…, "lat":…, "label": "lalu_lintas" }, … ],
  "bbox": […], "nrows": 29, "ncols": 30, "before": [/*grid*/], "after": [/*grid*/],
  "scenario": {…}, "disclaimer": "Simulasi Gaussian plume … estimasi." }
```
`before`/`after` are row-major grids (row 0 = SOUTH) — render as 3D columns (height = value above the 18 µg/m³ background) or a 2D heatmap. `delta_max_local_ugm3` = biggest local reduction (the visceral headline); `delta_mean_pct` is tiny by design (dispersion impact is local — say so).

---

### Notes for the frontend build
- **Grid orientation:** every grid (`/surface`, `/twin/whatif`) is row-major, **row 0 = SOUTH**. Flip vertically for a north-up image, or map row→lat directly.
- **Empty-state first:** `/surface`, `/sources`, `/validation` can be empty/`available:false` on a fresh DB — design the empty states; they fill as the batch job and ingestion run.
- **Never drop the disclaimers** — they're the credibility layer, not fine print.
- **Everything is swappable to live:** these are the exact shapes the demo fixtures mirror, so a Figma design built against this contract drops straight onto the real backend.
