/** Map helpers shared by Peta & Twin views (Mapbox GL JS). */
import mapboxgl from "mapbox-gl";
import type { StyleSpecification } from "mapbox-gl";

/**
 * Mapbox public token (pk.…). Provide via web/.env.local:  VITE_MAPBOX_TOKEN=pk.xxx
 * Mapbox GL JS is proprietary + billed per map-load (free tier 50k/mo). When the
 * token is ABSENT the app degrades gracefully to tokenless raster basemaps, so
 * teammates/judges who clone without a token still get a working map.
 */
export const MAPBOX_TOKEN: string = import.meta.env.VITE_MAPBOX_TOKEN ?? "";
export const hasMapboxToken = MAPBOX_TOKEN.length > 0;
mapboxgl.accessToken = MAPBOX_TOKEN;

/** Mapbox vector styles (used only when a token is present). */
export const MAPBOX_PETA = "mapbox://styles/mapbox/light-v11";
export const MAPBOX_SATELLITE = "mapbox://styles/mapbox/satellite-streets-v12";

/** Tokenless fallback basemap: raw OSM raster (also the offline safety net). */
export const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

/**
 * Satellite basemap — Esri "World Imagery" raster (tokenless, like our other
 * tiles; note the {z}/{y}/{x} order). Swap for a Mapbox Satellite style URL +
 * token here if the team adds a Mapbox account; nothing else changes.
 */
export const SATELLITE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    esri: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
    },
  },
  layers: [{ id: "esri", type: "raster", source: "esri" }],
};

/** The two selectable basemaps for the ▤ layers panel. Token-aware: Mapbox
 *  vector styles when a token is set, else tokenless raster equivalents. */
export type Basemap = "peta" | "satelit";
export function basemapStyle(b: Basemap): string | StyleSpecification {
  if (!hasMapboxToken) return b === "satelit" ? SATELLITE_STYLE : OSM_STYLE;
  return b === "satelit" ? MAPBOX_SATELLITE : MAPBOX_PETA;
}

export const JAKARTA_CENTER: [number, number] = [106.8272, -6.2088];

/** True when a station can't be trusted: stale, missing, or a broken 0 reading
 *  (ISPU 0 is impossible in Jakarta → dead sensor, not "Baik"). */
export function isBroken(v: number | null | undefined, stale: boolean): boolean {
  return stale || v === null || v === undefined || v <= 0;
}

/** Official-ish ISPU category colors (Baik→Berbahaya). */
export function ispuColor(v: number | null, stale: boolean): string {
  if (isBroken(v, stale) || v === null) return "#9aa0a6";
  if (v <= 50) return "#00a65a";
  if (v <= 100) return "#0073b7";
  if (v <= 200) return "#ff851b";
  if (v <= 300) return "#dd4b39";
  return "#111111";
}

export const ISPU_LEGEND: { label: string; color: string }[] = [
  { label: "Baik (0–50)", color: "#00a65a" },
  { label: "Sedang (51–100)", color: "#0073b7" },
  { label: "Tidak Sehat (101–200)", color: "#ff851b" },
  { label: "Sangat Tidak Sehat (201–300)", color: "#dd4b39" },
  { label: "Berbahaya (>300)", color: "#111111" },
  { label: "Tidak berfungsi / tidak ada data", color: "#9aa0a6" },
];

/** Thresholds for the surface color ramp, by fixture metric. */
function rampThresholds(metric: string): number[] {
  return metric.startsWith("PM2.5") ? [15, 35, 55, 150] : [50, 100, 200, 300];
}

const RAMP_COLORS: [number, number, number][] = [
  [0, 166, 90],    // low
  [255, 221, 87],  // moderate
  [255, 133, 27],  // high
  [221, 75, 57],   // very high
  [64, 20, 80],    // extreme
];

/**
 * Render a row-major grid (row 0 = SOUTH, from grid_over_bbox) to a PNG data URL.
 * Canvas row 0 is the TOP (north), so rows are flipped here.
 *
 * `confidence` (optional, same row-major indexing as `values`) is a per-cell
 * 0..1 opacity multiplier: without it the whole grid paints at a flat `alpha`,
 * which — since IDW has no "stop extrapolating past my data" behavior — makes
 * areas with zero real station coverage (neighboring cities, the bay) look
 * exactly as confident as areas dense with stations. With it, cells far from
 * any real station fade out instead of reading as a solid rectangle.
 */
export function gridToDataURL(
  values: number[], nrows: number, ncols: number, metric: string, alpha = 0.5,
  confidence?: number[],
): string {
  const th = rampThresholds(metric);
  const canvas = document.createElement("canvas");
  canvas.width = ncols;
  canvas.height = nrows;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(ncols, nrows);
  for (let r = 0; r < nrows; r++) {
    const canvasRow = nrows - 1 - r; // flip: south-first grid → north-first canvas
    for (let c = 0; c < ncols; c++) {
      const idx = r * ncols + c;
      const v = values[idx];
      let band = 0;
      while (band < th.length && v > th[band]) band++;
      const [red, green, blue] = RAMP_COLORS[band];
      const conf = confidence ? confidence[idx] : 1;
      const i = (canvasRow * ncols + c) * 4;
      img.data[i] = red;
      img.data[i + 1] = green;
      img.data[i + 2] = blue;
      img.data[i + 3] = Math.round(255 * alpha * conf);
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL("image/png");
}

/** Image-source corner coordinates from a (w,s,e,n) bbox: TL, TR, BR, BL. */
export function bboxCorners(
  bbox: [number, number, number, number],
): [[number, number], [number, number], [number, number], [number, number]] {
  const [w, s, e, n] = bbox;
  return [[w, n], [e, n], [e, s], [w, s]];
}

/** Minimal structural GeoJSON types (avoids depending on @types/geojson resolution). */
export interface ColumnFeature {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: number[][][] };
  properties: { v: number; h: number };
}
export interface ColumnCollection {
  type: "FeatureCollection";
  features: ColumnFeature[];
}

/**
 * 3D pollution columns: grid cells above background become extruded square
 * columns — height & color encode concentration. Row 0 = SOUTH (grid_over_bbox
 * convention); GeoJSON is computed in lat directly, so no flipping here.
 */
export function gridToColumns(
  values: number[],
  nrows: number,
  ncols: number,
  bbox: [number, number, number, number],
  background: number,
  metersPerUnit = 45,
): ColumnCollection {
  const [w, s, e, n] = bbox;
  const dLon = (e - w) / ncols;
  const dLat = (n - s) / nrows;
  const features: ColumnFeature[] = [];
  for (let r = 0; r < nrows; r++) {
    for (let c = 0; c < ncols; c++) {
      const v = values[r * ncols + c];
      if (v <= background + 0.5) continue; // background cells stay flat
      const x0 = w + c * dLon;
      const y0 = s + r * dLat;
      features.push({
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [[
            [x0, y0], [x0 + dLon, y0], [x0 + dLon, y0 + dLat],
            [x0, y0 + dLat], [x0, y0],
          ]],
        },
        properties: { v, h: (v - background) * metersPerUnit },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

/** MapLibre color expression for column concentration (µg/m³). */
export const COLUMN_COLOR_EXPR = [
  "interpolate", ["linear"], ["get", "v"],
  18, "#00a65a", 30, "#ffdd57", 45, "#ff851b", 60, "#dd4b39", 80, "#401450",
] as unknown as string;

/**
 * Source-likelihood heatmap from the REAL Layer-A directional candidates:
 * each candidate is a CPF-weighted wedge (arah datang). Rendered as translucent
 * heat-ramp fills so where multiple stations' wedges overlap, the area reads
 * hotter — i.e. a higher-confidence source region. Honest: this is attribution
 * (arah), not a measured emission map.
 */
export function candidatesToHeatFC(
  candidates: { geometry: GeoJSON.Polygon; notes: string }[] | undefined,
): GeoJSON.FeatureCollection {
  const features = (candidates ?? []).map((c) => ({
    type: "Feature" as const,
    geometry: c.geometry,
    properties: { cpf: parseFloat(/CPF=([\d.]+)/.exec(c.notes)?.[1] ?? "0") },
  }));
  return { type: "FeatureCollection", features };
}

/** MapLibre color expression for CPF (0–0.5 observed range) → heat ramp. */
export const CPF_HEAT_COLOR = [
  "interpolate", ["linear"], ["get", "cpf"],
  0, "#00a65a", 0.15, "#ffdd57", 0.3, "#ff851b", 0.4, "#dd4b39", 0.5, "#401450",
] as unknown as string;

/**
 * Create the Mapbox map (mercator, not globe — this is a city dashboard), with
 * an automatic RASTER FALLBACK when a token IS present: if the Mapbox style
 * hasn't loaded within `timeoutMs` (bad/blocked token, venue wifi), swap to the
 * self-contained OSM raster so the demo never shows a black map. Without a
 * token the initial style is already tokenless, so no fallback is needed.
 * `onReady` fires exactly once, after whichever style ends up active.
 */
export function createMapWithFallback(
  container: HTMLElement,
  options: Partial<ConstructorParameters<typeof mapboxgl.Map>[0]>,
  onReady: (map: mapboxgl.Map) => void,
  timeoutMs = 10000,
): mapboxgl.Map {
  const map = new mapboxgl.Map({
    container,
    style: basemapStyle("peta"),
    projection: "mercator",
    attributionControl: { compact: true },
    ...options,
  } as ConstructorParameters<typeof mapboxgl.Map>[0]);
  let ready = false;
  const finish = () => {
    if (!ready) {
      ready = true;
      onReady(map);
    }
  };
  map.once("load", finish);
  if (hasMapboxToken) {
    window.setTimeout(() => {
      if (!ready) {
        // diff:false = clean full reload; diffing against a half-loaded style
        // can wedge the map (never fires load, fetches no tiles).
        map.setStyle(OSM_STYLE, { diff: false } as Parameters<typeof map.setStyle>[1]);
        map.once("styledata", () => window.setTimeout(finish, 250));
      }
    }, timeoutMs);
  }
  return map;
}
