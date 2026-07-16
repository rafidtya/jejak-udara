/**
 * Twin view — what-if scenario simulator on precomputed REAL plume-engine output.
 * The physics is the project's actual Gaussian plume model (twin/plume.py);
 * grids were precomputed at fixture-build time. Honesty labels throughout.
 */
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { ScenarioSet } from "../fixtures";
import { bboxCorners, gridToDataURL, JAKARTA_CENTER, OSM_STYLE } from "../mapUtils";

interface Props {
  scenarios: ScenarioSet | null;
}

const SOURCE_ICON: Record<string, string> = {
  lalu_lintas: "🚗", industri: "🏭", pembakaran: "🔥",
};

export default function TwinView({ scenarios }: Props) {
  const mapDiv = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [selected, setSelected] = useState("baseline");

  useEffect(() => {
    if (!mapDiv.current || mapRef.current || !scenarios) return;
    const map = new maplibregl.Map({
      container: mapDiv.current,
      style: OSM_STYLE,
      center: JAKARTA_CENTER,
      zoom: 10.3,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", () => {
      const baseline = scenarios.scenarios.find((s) => s.id === "baseline")!;
      map.addSource("plume", {
        type: "image",
        url: gridToDataURL(baseline.values, scenarios.nrows, scenarios.ncols, "PM2.5"),
        coordinates: bboxCorners(scenarios.bbox),
      });
      map.addLayer({
        id: "plume",
        type: "raster",
        source: "plume",
        paint: { "raster-opacity": 0.55, "raster-resampling": "nearest" },
      });
      for (const src of scenarios.sources) {
        const el = document.createElement("div");
        el.className = "source-marker";
        el.textContent = SOURCE_ICON[src.label] ?? "📍";
        el.title = `${src.label} (ilustratif)`;
        new maplibregl.Marker({ element: el }).setLngLat([src.lon, src.lat]).addTo(map);
      }
    });

    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarios]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !scenarios) return;
    const sc = scenarios.scenarios.find((s) => s.id === selected);
    const src = map.getSource("plume") as maplibregl.ImageSource | undefined;
    if (sc && src) {
      src.updateImage({
        url: gridToDataURL(sc.values, scenarios.nrows, scenarios.ncols, "PM2.5"),
        coordinates: bboxCorners(scenarios.bbox),
      });
    }
  }, [selected, scenarios]);

  if (!scenarios) {
    return <p className="muted">Fixture skenario belum tersedia — jalankan scripts/build_scenarios.py</p>;
  }
  const current = scenarios.scenarios.find((s) => s.id === selected)!;

  return (
    <div className="view-map">
      <div ref={mapDiv} className="map-container" />
      <aside className="map-panel">
        <h2>Digital twin — simulasi skenario</h2>
        <p className="muted small">{scenarios.met.label}</p>
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
          <div className={`delta-badge ${current.delta_mean_pct < 0 ? "good" : "bad"}`}>
            Δ rata-rata konsentrasi: {current.delta_mean_pct > 0 ? "+" : ""}
            {current.delta_mean_pct}% vs baseline
          </div>
        )}
        <div className="card">
          <div className="muted small">{scenarios.disclaimer}</div>
        </div>
      </aside>
    </div>
  );
}
