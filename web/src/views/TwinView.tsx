/**
 * Twin view — 3D what-if simulator. Pollution renders as EXTRUDED COLUMNS
 * (height + color = concentration above background) on a pitched camera, over
 * the real precomputed Gaussian-plume grids. Physics = the project's actual
 * engine (twin/plume.py); honesty labels throughout.
 */
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { ScenarioSet } from "../fixtures";
import {
  COLUMN_COLOR_EXPR, createMapWithFallback, gridToColumns, JAKARTA_CENTER,
} from "../mapUtils";

interface Props {
  scenarios: ScenarioSet | null;
}

const SOURCE_ICON: Record<string, string> = {
  lalu_lintas: "🚗", industri: "🏭", pembakaran: "🔥",
};

/** Add 3D buildings if the basemap style carries a building source-layer. */
function tryAddBuildings(map: maplibregl.Map) {
  try {
    const style = map.getStyle();
    if (style.layers?.some((l) => l.id.includes("building-3d"))) return;
    const bldg = style.layers?.find(
      (l) => "source-layer" in l && (l as { "source-layer"?: string })["source-layer"] === "building",
    ) as { source?: string } | undefined;
    if (!bldg?.source) return;
    map.addLayer({
      id: "jk-buildings-3d",
      type: "fill-extrusion",
      source: bldg.source,
      "source-layer": "building",
      minzoom: 13,
      paint: {
        "fill-extrusion-color": "#d8dce1",
        "fill-extrusion-height": ["coalesce", ["get", "render_height"], 12],
        "fill-extrusion-opacity": 0.55,
      },
    });
  } catch {
    /* buildings are polish, never fatal */
  }
}

export default function TwinView({ scenarios }: Props) {
  const mapDiv = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [selected, setSelected] = useState("baseline");

  useEffect(() => {
    if (!mapDiv.current || mapRef.current || !scenarios) return;
    const map = createMapWithFallback(
      mapDiv.current,
      { center: JAKARTA_CENTER, zoom: 10.6, pitch: 57, bearing: -12, maxPitch: 70 },
      (m) => {
        tryAddBuildings(m);
        const baseline = scenarios.scenarios.find((s) => s.id === "baseline")!;
        m.addSource("plume-columns", {
          type: "geojson",
          data: gridToColumns(
            baseline.values, scenarios.nrows, scenarios.ncols,
            scenarios.bbox, scenarios.background_ugm3,
          ) as unknown as GeoJSON.GeoJSON,
        });
        m.addLayer({
          id: "plume-columns",
          type: "fill-extrusion",
          source: "plume-columns",
          paint: {
            "fill-extrusion-color": COLUMN_COLOR_EXPR,
            "fill-extrusion-height": ["get", "h"],
            "fill-extrusion-opacity": 0.78,
          },
        });
      },
    );
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");
    // markers are DOM overlays -- independent of style load, add immediately
    for (const src of scenarios.sources) {
      const el = document.createElement("div");
      el.className = "source-marker";
      el.textContent = SOURCE_ICON[src.label] ?? "📍";
      el.title = `${src.label} (ilustratif)`;
      new maplibregl.Marker({ element: el }).setLngLat([src.lon, src.lat]).addTo(map);
    }
    mapRef.current = map;

    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarios]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !scenarios) return;
    const sc = scenarios.scenarios.find((s) => s.id === selected);
    const src = map.getSource("plume-columns") as maplibregl.GeoJSONSource | undefined;
    if (sc && src) {
      src.setData(gridToColumns(
        sc.values, scenarios.nrows, scenarios.ncols,
        scenarios.bbox, scenarios.background_ugm3,
      ) as unknown as GeoJSON.GeoJSON);
    }
  }, [selected, scenarios]);

  if (!scenarios) {
    return <p className="muted view-pad">Fixture skenario belum tersedia — jalankan scripts/build_scenarios.py</p>;
  }
  const current = scenarios.scenarios.find((s) => s.id === selected)!;

  return (
    <div className="view-map">
      <div ref={mapDiv} className="map-container" />
      <aside className="map-panel">
        <h2>Digital twin — simulasi skenario 3D</h2>
        <p className="muted small">
          Tinggi &amp; warna kolom = konsentrasi di atas latar ({scenarios.background_ugm3}{" "}
          µg/m³). {scenarios.met.label}. Geser dengan klik-kanan untuk memutar kamera.
        </p>
        <div className="scenario-list">
          {scenarios.scenarios.map((sc) => (
            <button
              key={sc.id}
              className={`scenario-btn ${sc.id === selected ? "active" : ""}`}
              onClick={() => setSelected(sc.id)}
            >
              {sc.title}
            </button>
          ))}
        </div>
        {current.id !== "baseline" && (
          <div className={`delta-badge ${current.delta_max_local_ugm3 < 0 ? "good" : "bad"}`}>
            Di titik paling terdampak: {current.delta_max_local_ugm3} µg/m³ vs baseline
            <div className="small" style={{ fontWeight: 400 }}>
              (rata-rata seluruh kota: {current.delta_mean_pct > 0 ? "+" : ""}
              {current.delta_mean_pct}% — dampak intervensi bersifat lokal di sekitar
              sumber, sesuai fisika dispersi)
            </div>
          </div>
        )}
        <div className="card">
          <div className="muted small">{scenarios.disclaimer}</div>
        </div>
      </aside>
    </div>
  );
}
