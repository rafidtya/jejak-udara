/**
 * Twin — real 3D plume columns from the live Gaussian-plume engine (/twin/whatif),
 * design chrome + ScenarioButton + DeltaBadge. Height/color = concentration above
 * background. All labeled simulasi.
 */
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { api, type WhatIf } from "../api";
import { MapControls, NavTabs, TopBar, type View } from "../components/chrome";
import { Card, DeltaBadge, DisclaimerNote, ScenarioButton } from "../components/primitives";
import { COLUMN_COLOR_EXPR, createMapWithFallback, gridToColumns, JAKARTA_CENTER } from "../mapUtils";

interface Props { view: View; onChange: (v: View) => void; stationCount: number; sourceCount: number; }

const SCENARIOS: { id: string; title: string; body: Record<string, unknown> }[] = [
  { id: "baseline", title: "Baseline (kondisi saat ini)", body: {} },
  { id: "lalin", title: "Kurangi lalu lintas 50%", body: { scale: { lalu_lintas: 0.5 } } },
  { id: "industri", title: "Tutup sumber industri", body: { disable: ["industri"] } },
  { id: "hujan", title: "Hujan 5 mm (washout)", body: { rain_mm: 5 } },
];
const BG = 18;
const SRC_ICON: Record<string, string> = { lalu_lintas: "🚗", industri: "🏭", pembakaran: "🔥" };

export default function TwinView({ view, onChange, stationCount, sourceCount }: Props) {
  const mapDiv = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [sel, setSel] = useState("baseline");
  const [result, setResult] = useState<WhatIf | null>(null);

  // fetch the selected scenario from the live engine
  useEffect(() => {
    const sc = SCENARIOS.find((s) => s.id === sel)!;
    api.whatif(sc.body).then(setResult);
  }, [sel]);

  // init map once
  useEffect(() => {
    if (!mapDiv.current || mapRef.current) return;
    const map = createMapWithFallback(
      mapDiv.current,
      { center: JAKARTA_CENTER, zoom: 10.6, pitch: 55, bearing: -12, maxPitch: 70 },
      (m) => {
        m.addSource("plume", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        m.addLayer({
          id: "plume", type: "fill-extrusion", source: "plume",
          paint: {
            "fill-extrusion-color": COLUMN_COLOR_EXPR,
            "fill-extrusion-height": ["get", "h"], "fill-extrusion-opacity": 0.78,
          },
        });
      },
    );
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // push new plume + source markers whenever the result changes
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !result?.available) return;
    const apply = () => {
      const src = m.getSource("plume") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      src.setData(gridToColumns(result.after, result.nrows, result.ncols, result.bbox, BG) as unknown as GeoJSON.GeoJSON);
      markersRef.current.forEach((mk) => mk.remove());
      markersRef.current = result.sources.map((s) => {
        const el = document.createElement("div");
        el.className = "source-marker"; el.textContent = SRC_ICON[s.label] ?? "📍";
        el.style.fontSize = "22px"; el.title = `${s.label} (ilustratif)`;
        return new maplibregl.Marker({ element: el }).setLngLat([s.lon, s.lat]).addTo(m);
      });
    };
    if (m.isStyleLoaded() && m.getSource("plume")) apply(); else m.once("idle", apply);
  }, [result]);

  const cur = SCENARIOS.find((s) => s.id === sel)!;

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={mapDiv} style={{ position: "absolute", inset: 0 }} />
      <div style={{ position: "absolute", inset: "var(--topbar-inset)", display: "flex", flexDirection: "column", pointerEvents: "none" }}>
        <div style={{ pointerEvents: "auto" }}><TopBar stationCount={stationCount} sourceCount={sourceCount} /></div>
        <div style={{ margin: "10px 0 0", pointerEvents: "auto" }}><NavTabs active={view} onChange={onChange} /></div>
        <div style={{ flex: 1, position: "relative" }}>
          <div style={{ position: "absolute", right: 0, top: 8, pointerEvents: "auto" }}>
            <MapControls onZoomIn={() => mapRef.current?.zoomIn()} onZoomOut={() => mapRef.current?.zoomOut()} />
          </div>
          <div style={{ position: "absolute", left: 0, bottom: 0, width: 340, pointerEvents: "auto" }}>
            <Card>
              <h2 style={{ fontSize: "var(--text-base)", marginBottom: 6 }}>Digital twin — simulasi skenario 3D</h2>
              <p style={{ color: "var(--fg-secondary)", fontSize: "var(--text-2xs)", marginBottom: 10 }}>
                Tinggi &amp; warna kolom = konsentrasi di atas latar ({BG} µg/m³). Contoh angin baratan 3 m/s (bukan data live).
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 8 }}>
                {SCENARIOS.map((sc) => (
                  <ScenarioButton key={sc.id} title={sc.title} active={sc.id === sel} onClick={() => setSel(sc.id)} />
                ))}
              </div>
              {cur.id !== "baseline" && result?.available && (
                <DeltaBadge deltaMaxLocal={result.delta_max_local_ugm3} deltaMeanPct={result.delta_mean_pct} />
              )}
              <div style={{ background: "#fff", borderRadius: 8, padding: 8, marginTop: 8 }}>
                <DisclaimerNote>
                  {result?.disclaimer ?? "Simulasi plume Gaussian (mesin asli), bukan pengukuran. Lokasi sumber ilustratif; fisika & delta nyata."}
                </DisclaimerNote>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
