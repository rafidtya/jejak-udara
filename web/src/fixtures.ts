/** Fixture types + loader for the Track-A demo (frozen real data, no backend). */

export interface DailyPoint {
  date: string;
  ispu: number | null;
  conc: number | null;
}

export interface Station {
  station_id: string;
  name: string;
  kind: "reference" | "low_cost";
  lon: number;
  lat: number;
  kecamatan: string | null;
  kota: string | null;
  ispu: number | null;
  category: string | null;
  parameter: string | null;
  concentration: number | null;
  last_update_utc: string | null;
  stale: boolean;
  daily30: DailyPoint[];
}

export interface Heatmap {
  bbox: [number, number, number, number]; // w, s, e, n
  nrows: number;
  ncols: number;
  cell_m: number;
  metric: string;
  n_stations_used: number;
  n_stations_stale_excluded: number;
  n_outliers_removed: number;
  loocv: { rmse: number; mae: number; bias: number; r2: number; n: number };
  values: number[];
  disclaimer: string;
}

export interface ScenarioResult {
  id: string;
  title: string;
  delta_mean_pct: number;
  delta_max_local_ugm3: number;
  values: number[];
}

export interface ScenarioSet {
  bbox: [number, number, number, number];
  nrows: number;
  ncols: number;
  cell_m: number;
  met: { wd_deg: number; ws: number; label: string };
  background_ugm3: number;
  sources: { label: string; q: number; lon: number; lat: number }[];
  scenarios: ScenarioResult[];
  disclaimer: string;
}

export interface Meta {
  captured_at_utc: string;
  station_count: number;
  failures: number;
  source: string;
}

export async function loadJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(path);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}
