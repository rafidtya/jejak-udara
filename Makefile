# JejakUdara — command contract (see agents.md §3)
.PHONY: install migrate seed run-ingest run-batch run-twin-backtest api web status test demo-seed gen-api-types demo-fixtures demo

# ---- Track A: July-20 demo (fixture-fed, no DB) ----
demo-fixtures:   # refresh the frozen real-data snapshot (gentle scrape ~5 min)
	python -m scripts.build_fixtures
	python -m scripts.build_heatmap
	python -m scripts.build_scenarios

demo:            # build + serve the dockerized demo on :8080
	docker compose -f infra/docker-compose.demo.yml up --build

install:
	pip install -e ".[dev]"
	@echo "For full geo/satellite stacks: pip install -e '.[geo,satellite]'"

migrate:
	docker compose -f infra/docker-compose.yml exec -T db \
		psql -U jejakudara -d jejakudara < db/schema.sql

seed:
	python -m ingest.static_gis --load-centroids
	@echo "TODO(P1.4): OSM roads + landuse loaders"

run-ingest:
	python -m ingest.scheduler

run-batch:
	python -m analytics.jobs --once

run-twin-backtest:
	python -m twin.backtest

api:
	uvicorn api.main:app --reload --port 8000

web:
	cd web && npm install && npm run dev

status:
	python -m ingest.status

test:
	pytest -q

demo-seed:
	python -m api.demo_seed
	@echo "Offline demo dataset loaded — judging-day lifeline (agents.md §8)"

gen-api-types:
	cd web && npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
