# JejakUdara

Data-orchestration, pollution **source-attribution**, and **digital-twin** platform for DLH Jakarta.

- What & why: `../Brief Proposal - JejakUdara (with Digital Twin).docx`
- Roadmap & phases: `../plan.md`
- How to work in this repo (humans & AI agents): `../agents.md`
- Incident log / lessons: `../workflow.md`

## Quickstart

```bash
cp .env.example .env          # fill keys (FIRMS, GEE, CAMS) and DB creds
docker compose -f infra/docker-compose.yml up -d db
make migrate                  # apply db/schema.sql
make test                     # numeric sanity tests (plume, polar, kriging LOOCV)
make api                      # FastAPI on :8000 (OpenAPI at /docs)
make run-ingest               # start pollers (BMKG live; SPKU gated on P0.1)
```

## Layout

```
ingest/      scrapers & pollers (BMKG ✅ implemented, SPKU ⚠ gated on P0.1, FIRMS, satellite/GEE, CAMS)
analytics/   layers A–D (wind back-tracing, hotspots, NMF source typing, context fusion)
twin/        layer E: Gaussian plume, forecast, what-if scenarios (implemented core)
api/         FastAPI read layer + POST /twin/whatif
web/         React + TS dashboard (scaffold)
db/          schema.sql + SCHEMA.md (data contracts)
infra/       docker-compose
tests/       known-answer numeric tests
```

## Status

Pre-P0. The single blocking gate is **P0.1**: verify what `udara.jakarta.go.id` actually exposes
(per-pollutant concentration vs ISPU index; hourly vs daily) via browser DevTools → Network.
Everything in `ingest/spku.py` marked `TODO(P0.1)` depends on that answer.
