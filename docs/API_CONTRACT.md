# JejakUdara — Full API Contract (project-complete, not just MVP)

The complete endpoint surface for the finished product, with per-endpoint status so the
Figma frontend can design against the *final* shape while the backend fills in behind it.
The MVP subset is documented in [`API.md`](./API.md); this file is the canonical target.

**Conventions:** JSON; ISO-8601 UTC timestamps; GeoJSON `[lon, lat]`; grids row-major with
**row 0 = SOUTH**; every estimate/simulation carries a `disclaimer`; every attribution carries
a `confidence`. Base (dev) `http://localhost:8000`, Swagger at `/docs`.

**Status legend**
- 🟢 **Live** — implemented and returning real data today
- 🟡 **Built, pending data** — implemented; returns real content after the batch job runs / history accumulates
- 🔵 **Planned** — designed, not built
- ⚪ **Stretch** — post-competition / nice-to-have

---

## 1. System & metadata

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/health` | 🟢 | Liveness probe → `{status}` |
| GET | `/meta` | 🟢 | Station count + per-source ingestion freshness |
| GET | `/validation` | 🟡 | Latest metrics per kind: `loocv`, `forecast_skill`, `nmf_stability`, `aod_calibration` |
| GET | `/ingestion/status` | 🔵 | Detailed heartbeat + gap report (ops dashboard) |

## 2. Measured air quality (the ground truth)

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/stations` | 🟢 | GeoJSON of all stations + latest dominant ISPU |
| GET | `/stations/{id}` | 🔵 | One station: metadata, all current pollutants, `metrics[]` breakdown |
| GET | `/stations/{id}/readings` | 🔵 | Time series `?pollutant=&from=&to=` (drives per-station trend charts) |
| GET | `/readings/latest` | 🔵 | Flat latest readings `?pollutant=` (non-GeoJSON convenience) |

## 3. Layer B — spatial surface & hotspots

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/surface` | 🟡 | Interpolated grid `?pollutant=&kind=measured` |
| GET | `/surface/uncertainty` | 🔵 | Kriging variance grid (where the surface is trustworthy) |
| GET | `/hotspots` | 🟡 | District-level elevated areas (`gi_z`, `flagged`) |
| GET | `/exposure` | 🔵 | Population affected per hotspot (WorldPop join) — "X ribu warga terpapar" |

## 4. Layer A — wind attribution (direction)

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/polar/{station_id}` | 🟡 | Bivariate polar / CPF bins for the wind-rose plot |
| GET | `/wind/current` | 🔵 | Live BMKG wind field (per-kelurahan) for a rose/arrow overlay |
| GET | `/sources/candidates` | 🟡 | Triangulated source *areas* (polygons) — currently inside `/sources` |
| GET | `/trajectories` | 🔵 | HYSPLIT backward trajectories `?episode=` — "home-grown vs imported" |

## 5. Layer C — source typing (what kind)

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/sources` | 🟡 | Attributed sources: `candidates` (areas) + `factors` (types w/ confidence + evidence) |
| GET | `/sources/factors/{id}` | 🔵 | One NMF factor in detail: chemical profile + diurnal signature |

## 6. Layer D — context & evidence

| Method | Path | Status | Purpose |
|---|---|---|---|
| (embedded) | `evidence[]` in `/sources` | 🟡 | Road/zone/fire corroboration strings per source |
| GET | `/context/fires` | 🔵 | FIRMS active fires `?from=&to=` (map layer + burning evidence) |
| GET | `/context/landuse` | ⚪ | Industrial/built/green masks (static overlay) |

## 7. Layer E — digital twin

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `/twin/whatif` | 🟢 | Scenario diff → before/after grids + deltas (Gaussian plume) |
| GET | `/twin/sources` | 🔵 | The attributed sources currently feeding the twin (labels, strengths, locations) |
| GET | `/twin/forecast` | 🔵 | N-hour dispersion forecast `?hours=` (plume rolled on BMKG forecast wind) |
| GET | `/twin/skill` | 🔵 | Backtest: our forecast vs persistence **and vs DLH's own posted forecast** |

## 8. Satellite / earth observation

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/satellite/{product}` | 🔵 | Grid `?date=` for `s5p_no2`/`s5p_so2`/`s5p_co`/`maiac_aod` (citywide chemistry) |
| GET | `/satellite/pm25` | 🔵 | AOD-derived PM2.5 surface (calibrated vs SPKU; carries its R²) |
| GET | `/regional/background` | 🔵 | CAMS regional PM2.5 (twin boundary term; "imported" narrative) |

## 9. Forecast & alerts

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/forecast` | 🔵 | Predicted concentration/ISPU `?pollutant=&hours=` (twin + ML) |
| GET | `/alerts` | 🔵 | Predicted threshold exceedances — "Kelurahan X akan >ISPU 150 dalam ~3 jam" |
| GET | `/episodes` | ⚪ | Written case studies (spike → direction → type → evidence) for the paper/demo |

---

## 10. Backend progress vs. final target (subsystem view)

| Subsystem | Final target | Where it is now | Remaining work |
|---|---|---|---|
| **DB / schema** | All tables incl. satellite, CAMS, factors | ✅ **All tables exist & applied** (satellite/CAMS/factors empty) | populate the empty ones |
| **Ingestion** | SPKU, BMKG, Open-Meteo, FIRMS, GEE-satellite, CAMS | SPKU 🟢, BMKG 🟢, Open-Meteo 🟢(running), FIRMS 🟡(code, needs key), GEE ⚪(stub), CAMS ⚪(stub) | API keys + implement GEE/CAMS |
| **Layer A (wind)** | polar/CPF, triangulation, HYSPLIT | polar+triangulation implemented 🟡 (pending 1st batch); HYSPLIT 🔵 | run batch; build HYSPLIT |
| **Layer B (spatial)** | IDW **+ kriging + uncertainty**, **Gi\*** hotspots, AOD densify | IDW+LOOCV 🟡, district hotspots 🟡; kriging/Gi\*/AOD 🔵 | upgrade interpolation + stats |
| **Layer C (typing)** | NMF factors + rule interp + satellite cross-check | implemented 🟡; needs multi-pollutant **accumulation** | accumulate hourly, then run |
| **Layer D (context)** | roads/zones/FIRMS/NDVI/WorldPop fusion + exposure | `upwind_bearing_ok` helper only 🔵 | build spatial joins + exposure |
| **Twin (E)** | what-if ✅ **+ forecast + skill/backtest** | what-if 🟢 working; forecast/skill 🔵 | build forecast roll + backtest |
| **Satellite** | TROPOMI/AOD/NDVI/WorldPop + CAMS | 🔵 stubs only | credentials + GEE sampling code |
| **API endpoints** | ~26 endpoints | **9 implemented** (3 🟢 live, 6 🟡 pending batch), ~17 🔵 planned | build out the planned set |
| **Validation surfacing** | LOOCV, forecast-skill, NMF-stability, AOD-cal | LOOCV 🟡 wired | add the others as their layers land |

### One-line status
**MVP core is ~35% of the final backend and is nearly wired end-to-end** — real DB, real ingestion
with 30-day bootstrap (21k+ readings), Layer B + district hotspots + the working plume twin, all
behind a live API. The remaining ~65% is *breadth* (satellite, HYSPLIT, forecast/alerts, exposure,
kriging/Gi\* upgrades) and *depth that only time buys* (Layer C needs weeks of accumulated hourly
history — which is exactly why the VPS scrapers must start now).

### Critical-path ordering to "final"
1. Keep scrapers running 24/7 on the VPS (unlocks Layer A quality + Layer C at all)
2. Register FIRMS + GEE + CAMS keys → turn on satellite & fire ingestion
3. Layer D fusion + `/exposure` (cheap, high-value "warga terpapar" number)
4. Twin `/forecast` + `/skill` (the "beats DLH's own forecast" claim)
5. Kriging/Gi\* upgrades once enough history makes them validate
6. HYSPLIT + `/alerts` + `/episodes` (polish for the paper/demo)
