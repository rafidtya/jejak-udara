/** Map helpers shared by Peta & Twin views. */
import maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";

/**
 * Basemap: OpenFreeMap "Liberty" — free vector style, NO token/signup
 * (vs Mapbox: similar polish but token + proprietary license). Swap to a
 * Mapbox style URL + token here if the team ever wants it; nothing else changes.
 */
export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

/** Fallback: raw OSM raster (kept for emergencies — e.g. OpenFreeMap outage). */
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

export const JAKARTA_CENTER: [number, number] = [106.8272, -6.2088];

/** Official-ish ISPU category colors (Baik→Berbahaya). */
export function ispuColor(v: number | null, stale: boolean): string {
  if (stale || v === null) return "#9aa0a6";
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
  { label: "Stale / tidak ada data", color: "#9aa0a6" },
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
 */
export function gridToDataURL(
  values: number[], nrows: number, ncols: number, metric: string, alpha = 0.5,
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
      const v = values[r * ncols + c];
      let band = 0;
      while (band < th.length && v > th[band]) band++;
      const [red, green, blue] = RAMP_COLORS[band];
      const i = (canvasRow * ncols + c) * 4;
      img.data[i] = red;
      img.data[i + 1] = green;
      img.data[i + 2] = blue;
      img.data[i + 3] = Math.round(255 * alpha);
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
 * Create a map on the vector basemap, with automatic RASTER FALLBACK:
 * if the vector style hasn't finished loading within `timeoutMs` (CDN outage,
 * blocked network, presentation-venue wifi), swap to the self-contained OSM
 * raster style so the demo never shows a black map. `onReady` fires exactly
 * once, after whichever style ends up active — add sources/layers there.
 */
export function createMapWithFallback(
  container: HTMLElement,
  options: Partial<ConstructorParameters<typeof maplibregl.Map>[0]>,
  onReady: (map: maplibregl.Map) => void,
  timeoutMs = 10000,
): maplibregl.Map {
  const map = new maplibregl.Map({
    container,
    style: BASEMAP_STYLE,
    attributionControl: { compact: true },
    ...options,
  } as ConstructorParameters<typeof maplibregl.Map>[0]);
  let ready = false;
  const finish = () => {
    if (!ready) {
      ready = true;
      onReady(map);
    }
  };
  map.once("load", finish);
  window.setTimeout(() => {
    if (!ready) {
      map.setStyle(OSM_STYLE);
      map.once("styledata", () => window.setTimeout(finish, 250));
    }
  }, timeoutMs);
  return map;
}
