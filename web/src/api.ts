/** Live backend client. Dev: vite proxies /api -> http://localhost:8000 (vite.config.ts). */
const BASE = "/api";

async function get<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${BASE}${path}`);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export interface Meta {
  station_count: number;
  ingestion: { source: string; last_success: string | null; rows_24h: number }[];
}

export interface StationFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    station_id: string; name: string; kind: string; kecamatan: string | null;
    ispu: number | null; ts: string | null; stale: boolean;
  };
}
export interface StationsFC { type: "FeatureCollection"; features: StationFeature[] }

export interface Surface {
  available: boolean; reason?: string;
  bbox: [number, number, number, number]; nrows: number; ncols: number; cell_m: number;
  metric: string; n_stations: number; values: number[]; disclaimer: string;
}

export interface Hotspot { district: string; pollutant: string; gi_z: number; ts: string; flagged: boolean }

export interface SourcesResp {
  candidates: { geometry: GeoJSON.Polygon; method: string; notes: string; ts: string }[];
  factors: { label: string; confidence: number; profile: unknown; diurnal: unknown; evidence: string[]; run_ts: string }[];
  disclaimer: string;
}

export interface ValidationRun { kind: string; pollutant: string; metrics: Record<string, number | string>; run_ts: string }

export interface WhatIf {
  available: boolean; delta_mean_pct: number; delta_max_local_ugm3: number;
  sources: { lon: number; lat: number; label: string }[];
  bbox: [number, number, number, number]; nrows: number; ncols: number;
  before: number[]; after: number[]; disclaimer: string;
}

export const api = {
  meta: () => get<Meta>("/meta"),
  stations: () => get<StationsFC>("/stations"),
  surface: () => get<Surface>("/surface?pollutant=pm25&kind=measured"),
  hotspots: () => get<Hotspot[]>("/hotspots"),
  sources: () => get<SourcesResp>("/sources"),
  validation: () => get<ValidationRun[]>("/validation"),
  whatif: async (body: { disable?: string[]; scale?: Record<string, number>; rain_mm?: number }): Promise<WhatIf | null> => {
    try {
      const r = await fetch(`${BASE}/twin/whatif`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!r.ok) return null;
      return (await r.json()) as WhatIf;
    } catch {
      return null;
    }
  },
};
