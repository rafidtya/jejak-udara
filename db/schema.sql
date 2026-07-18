-- JejakUdara initial schema (bootstrap; alembic adoption once schema stabilizes)
-- Convention: ALL timestamps UTC (timestamptz). Geometry EPSG:4326; metric math in 32748 at query time.

CREATE EXTENSION IF NOT EXISTS postgis;
-- TimescaleDB is OPTIONAL (scale optimization, unneeded at MVP volume). Guarded
-- so the same schema applies on plain PostGIS now and a Timescale DB later.
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS timescaledb;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'timescaledb unavailable -> hypertables become plain tables (fine at MVP scale)';
END $$;

-- Helper: turn a table into a hypertable IFF timescaledb is present; else no-op.
CREATE OR REPLACE FUNCTION _maybe_hypertable(tbl regclass, col text) RETURNS void AS $$
BEGIN
  PERFORM create_hypertable(tbl, col, if_not_exists => TRUE);
EXCEPTION WHEN undefined_function OR others THEN
  NULL;  -- plain table
END $$ LANGUAGE plpgsql;

-- ============ reference ============
CREATE TABLE IF NOT EXISTS stations (
    station_id   text PRIMARY KEY,              -- SPKU datasourceKode, e.g. CAC3, DKI1, LCS-04
    name         text NOT NULL,
    kind         text NOT NULL CHECK (kind IN ('reference','low_cost')),  -- from SPKU `type`
    geom         geometry(Point, 4326) NOT NULL,
    adm4_code    text,                          -- nearest BMKG kelurahan (P0.6 join)
    meta         jsonb DEFAULT '{}'::jsonb       -- {uuid, kecamatan, kota} -- uuid = /spku/<uuid> detail path
);

CREATE TABLE IF NOT EXISTS kelurahan (
    adm4_code    text PRIMARY KEY,              -- e.g. 31.71.03.1001
    name         text NOT NULL,
    geom_centroid geometry(Point, 4326)         -- from BMKG response lon/lat
);

-- ============ raw / dead-letter ============
CREATE TABLE IF NOT EXISTS raw_payloads (
    id           bigserial PRIMARY KEY,
    source       text NOT NULL,                 -- 'spku' | 'bmkg' | 'firms' | 'cams'
    fetched_at   timestamptz NOT NULL DEFAULT now(),
    url          text NOT NULL,
    http_status  int,
    payload      jsonb,                         -- raw body; parser fixes are retroactive
    parsed_ok    boolean DEFAULT false,
    parse_error  text
);
SELECT _maybe_hypertable('raw_payloads', 'fetched_at');

-- ============ time series ============
CREATE TABLE IF NOT EXISTS readings (
    station_id   text NOT NULL REFERENCES stations(station_id),
    ts           timestamptz NOT NULL,
    pollutant    text NOT NULL,                 -- pm25|pm10|no2|so2|co|o3|hc
    value        double precision NOT NULL,
    unit         text NOT NULL,                 -- 'ug/m3' | 'index'
    is_index     boolean NOT NULL DEFAULT false,-- true=ISPU index, false=raw concentration
    qa_flag      text DEFAULT 'ok',             -- ok|stale|spike|stuck|gapfill
    -- P0.1 VERIFIED (db/SCHEMA.md): SPKU gives BOTH an ISPU index and a raw
    -- concentration for the same station/pollutant/timestamp. is_index MUST
    -- stay in the PK -- without it the second insert silently overwrites/
    -- conflicts with the first (caught during spku.py implementation, never shipped).
    PRIMARY KEY (station_id, ts, pollutant, is_index)
);
SELECT _maybe_hypertable('readings', 'ts');

CREATE TABLE IF NOT EXISTS weather_forecasts (
    adm4_code    text NOT NULL,
    run_ts       timestamptz NOT NULL,          -- OUR poll timestamp (one label per poll; we keep every poll).
                                                -- INTENTIONAL: not BMKG's analysis_date (that lives in raw_payloads).
                                                -- Do not "fix" this to analysis_date without updating bmkg.py + SCHEMA.md.
    valid_ts     timestamptz NOT NULL,          -- forecast valid time (3h steps)
    wd_deg       double precision,              -- wind FROM, deg clockwise from N
    ws           double precision,              -- m/s
    hu           double precision,              -- humidity %
    t            double precision,              -- temp C
    tcc          double precision,              -- total cloud cover %
    tp           double precision,              -- precip mm / 3h
    PRIMARY KEY (adm4_code, run_ts, valid_ts)
);
SELECT _maybe_hypertable('weather_forecasts', 'valid_ts');

-- Historical hourly wind (Open-Meteo) -- BMKG has no history API, so this is
-- how Layer A pairs past concentration with past wind. Keyed by station for a
-- trivial join (wind ~constant across a kelurahan; station-level is fine).
CREATE TABLE IF NOT EXISTS weather_history (
    station_id   text NOT NULL REFERENCES stations(station_id),
    ts           timestamptz NOT NULL,
    wd_deg       double precision,             -- wind FROM, deg cw from N (meteorological)
    ws           double precision,             -- m/s
    source       text NOT NULL DEFAULT 'open-meteo',
    PRIMARY KEY (station_id, ts)
);
SELECT _maybe_hypertable('weather_history', 'ts');

CREATE TABLE IF NOT EXISTS fire_events (
    id           bigserial PRIMARY KEY,
    ts           timestamptz NOT NULL,
    geom         geometry(Point, 4326) NOT NULL,
    confidence   text,
    frp          double precision               -- fire radiative power
);

CREATE TABLE IF NOT EXISTS satellite_grids (
    product      text NOT NULL,                 -- s5p_no2|s5p_so2|s5p_co|s5p_aer_ai|maiac_aod|derived_pm25
    date         date NOT NULL,
    cell         geometry(Polygon, 4326) NOT NULL,
    value        double precision,
    qa           text DEFAULT 'ok',             -- cloud gaps stay NULL + qa='cloud'; never fabricate
    PRIMARY KEY (product, date, cell)
);

CREATE TABLE IF NOT EXISTS regional_background (   -- CAMS
    ts           timestamptz NOT NULL,
    pollutant    text NOT NULL,
    value        double precision NOT NULL,     -- ug/m3, Jakarta-region mean
    kind         text NOT NULL CHECK (kind IN ('analysis','forecast')),
    PRIMARY KEY (ts, pollutant, kind)
);

-- ============ analytics results ============
CREATE TABLE IF NOT EXISTS polar_stats (
    station_id   text NOT NULL,
    pollutant    text NOT NULL,
    window_start timestamptz NOT NULL,
    window_end   timestamptz NOT NULL,
    wd_bin       int NOT NULL,                  -- degrees, bin start (0,10,...350)
    ws_bin       int NOT NULL,                  -- m/s integer bin
    mean_conc    double precision,
    n            int,
    cpf          double precision,              -- P(conc>threshold | this bin)
    PRIMARY KEY (station_id, pollutant, window_start, wd_bin, ws_bin)
);

CREATE TABLE IF NOT EXISTS hotspots (
    id           bigserial PRIMARY KEY,
    ts_window    tstzrange NOT NULL,
    district     text NOT NULL,
    pollutant    text NOT NULL,
    gi_z         double precision,
    p_value      double precision,
    population_affected int                     -- WorldPop join (P2.13b)
);

CREATE TABLE IF NOT EXISTS source_factors (
    factor_id    bigserial PRIMARY KEY,
    run_ts       timestamptz NOT NULL,
    label        text NOT NULL,                 -- traffic|industry|burning|dust|unknown
    confidence   double precision NOT NULL,     -- 0..1 — NEVER present label without this
    profile      jsonb NOT NULL,                -- pollutant -> loading
    diurnal      jsonb NOT NULL,                -- hour -> mean contribution
    evidence     jsonb NOT NULL DEFAULT '[]'::jsonb  -- ["major arterial 300m NE", "TROPOMI NO2 corridor", ...]
);

CREATE TABLE IF NOT EXISTS source_candidates (  -- triangulation output
    id           bigserial PRIMARY KEY,
    episode_ts   tstzrange NOT NULL,
    geom         geometry(Polygon, 4326) NOT NULL,   -- uncertainty polygon, not a pin
    method       text NOT NULL DEFAULT 'ray_intersection',
    n_stations   int,
    notes        text
);

CREATE TABLE IF NOT EXISTS forecast_surfaces (
    run_ts       timestamptz NOT NULL,
    valid_ts     timestamptz NOT NULL,
    pollutant    text NOT NULL,
    grid         jsonb NOT NULL,                -- encoded grid (demo scale); GeoTIFF store later
    kind         text NOT NULL CHECK (kind IN ('measured','plume','ml','whatif')),
    scenario     jsonb,                         -- what-if diff, null for plain forecast
    PRIMARY KEY (run_ts, valid_ts, pollutant, kind)
);

CREATE TABLE IF NOT EXISTS validation_runs (
    id           bigserial PRIMARY KEY,
    run_ts       timestamptz NOT NULL DEFAULT now(),
    kind         text NOT NULL,                 -- loocv|forecast_skill|nmf_stability|aod_calibration
    pollutant    text,
    metrics      jsonb NOT NULL                 -- {rmse, mae, r2, bias, baseline_mae, ...}
);

-- ============ ops ============
CREATE TABLE IF NOT EXISTS ingest_heartbeat (
    source       text PRIMARY KEY,
    last_success timestamptz,
    last_error   timestamptz,
    error_msg    text,
    rows_24h     int DEFAULT 0
);
