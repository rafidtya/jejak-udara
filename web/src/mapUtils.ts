/** Map helpers shared by Peta & Twin views. */
import type { StyleSpecification } from "maplibre-gl";

/** Free OSM raster basemap — no API key. Attribution required and included. */
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
