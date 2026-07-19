/**
 * Peta — real MapLibre map dressed in the JejakUdara design chrome.
 * Layers (bottom→top): estimated IDW surface (heatmap) · CPF source-likelihood
 * heatmap (real Layer-A wedges, shown with the ☰ Sumber sidebar) · measured
 * station dots. The ▤ control opens a panel: heatmap opacity + basemap (Peta /
 * Satelit). Honesty: dots = measured (crisp); surfaces/wedges = estimasi.
 */
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type SourcesResp, type StationsFC, type Surface, type ValidationRun } from "../api";
import { MapControls, NavTabs, TopBar, type View } from "../components/chrome";
import { Card, DisclaimerNote, ISPULegend } from "../components/primitives";
import { SourcesSidebar } from "../components/sources";
import {
  type Basemap, basemapStyle, bboxCorners, candidatesToHeatFC, CPF_HEAT_COLOR,
  createMapWithFallback, gridToDataURL, isBroken, ispuColor, JAKARTA_CENTER,
} from "../mapUtils";

interface Props { view: View; onChange: (v: View) => void; stationCount: number; sourceCount: number; }

export default function PetaView({ view, onChange, stationCount, sourceCount }: Props) {
  const mapDiv = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const wiredRef = useRef(false);

  const [stations, setStations] = useState<StationsFC | null>(null);
  const [surface, setSurface] = useState<Surface | null>(null);
  const [loocv, setLoocv] = useState<ValidationRun | null>(null);
  const [sources, setSources] = useState<SourcesResp | null>(null);
  const [showSurface, setShowSurface] = useState(true);
  const [surfaceOpacity, setSurfaceOpacity] = useState(0.55);
  const [basemap, setBasemap] = useState<Basemap>("peta");
  const [layersOpen, setLayersOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // refs so map callbacks (fired outside React render) read the latest values
  const stationsRef = useRef(stations);
  const surfaceRef = useRef(surface);
  const sourcesRef = useRef(sources);
  const showSurfaceRef = useRef(showSurface);
  const opacityRef = useRef(surfaceOpacity);
  const sidebarRef = useRef(sidebarOpen);

  useEffect(() => {
    api.stations().then(setStations);
    api.surface().then(setSurface);
    api.validation().then((v) => setLoocv(v?.find((x) => x.kind === "loocv") ?? null));
    api.sources().then(setSources);
  }, []);

  const locate = (lon: number, lat: number) =>
    mapRef.current?.flyTo({ center: [lon, lat], zoom: 12.5, speed: 0.8 });

  /** (Re)build every custom overlay — safe to call after a setStyle() wipe. */
  const addOverlays = useCallback((m: mapboxgl.Map) => {
    // --- estimated surface (bottom) ---
    if (m.getLayer("surface")) m.removeLayer("surface");
    if (m.getSource("surface")) m.removeSource("surface");
    const sf = surfaceRef.current;
    if (sf?.available) {
      m.addSource("surface", {
        type: "image",
        url: gridToDataURL(sf.values, sf.nrows, sf.ncols, sf.metric, 0.5, sf.confidence),
        coordinates: bboxCorners(sf.bbox),
      });
      m.addLayer({
        id: "surface", type: "raster", source: "surface",
        layout: { visibility: showSurfaceRef.current ? "visible" : "none" },
        paint: { "raster-opacity": opacityRef.current, "raster-resampling": "nearest" },
      });
    }

    // --- CPF source-likelihood heatmap (middle) ---
    for (const id of ["src-heat-line", "src-heat"]) if (m.getLayer(id)) m.removeLayer(id);
    if (m.getSource("src-heat")) m.removeSource("src-heat");
    const fc = candidatesToHeatFC(sourcesRef.current?.candidates);
    if (fc.features.length) {
      const vis = sidebarRef.current ? "visible" : "none";
      m.addSource("src-heat", { type: "geojson", data: fc });
      m.addLayer({
        id: "src-heat", type: "fill", source: "src-heat",
        layout: { visibility: vis },
        paint: { "fill-color": CPF_HEAT_COLOR, "fill-opacity": 0.32 },
      });
      m.addLayer({
        id: "src-heat-line", type: "line", source: "src-heat",
        layout: { visibility: vis },
        paint: { "line-color": CPF_HEAT_COLOR, "line-width": 1, "line-opacity": 0.55 },
      });
    }

    // --- measured station dots (top) ---
    if (m.getLayer("stations")) m.removeLayer("stations");
    if (m.getSource("stations")) m.removeSource("stations");
    const st = stationsRef.current;
    if (st) {
      m.addSource("stations", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: st.features.map((f) => ({
            ...f,
            properties: {
              ...f.properties,
              color: ispuColor(f.properties.ispu, f.properties.stale),
              broken: isBroken(f.properties.ispu, f.properties.stale),
            },
          })),
        } as GeoJSON.FeatureCollection,
      });
      m.addLayer({
        id: "stations", type: "circle", source: "stations",
        paint: {
          "circle-radius": 6, "circle-color": ["get", "color"],
          "circle-stroke-width": 1.5, "circle-stroke-color": "#fff",
        },
      });
    }
  }, []);

  /** Station popups/cursor — delegated listeners, registered exactly once. */
  const wireInteractions = useCallback((m: mapboxgl.Map) => {
    if (wiredRef.current) return;
    wiredRef.current = true;
    m.on("click", "stations", (e) => {
      const p = e.features?.[0]?.properties as
        (StationsFC["features"][0]["properties"] & { broken?: boolean }) | undefined;
      if (!p) return;
      const ispuLine = p.broken
        ? '<span style="color:#696969">⚠ Tidak berfungsi (indeks 0 / tidak ada data)</span>'
        : `ISPU: <strong>${p.ispu ?? "—"}</strong>`;
      new mapboxgl.Popup({ maxWidth: "300px" }).setLngLat(e.lngLat).setHTML(
        `<div style="font-family:var(--font-ui);font-size:13px">
           <strong>${p.name}</strong><br/>
           <span style="color:#737373">${p.station_id} · ${p.kind === "reference" ? "referensi" : "low-cost"}</span><br/>
           ${ispuLine}
         </div>`,
      ).addTo(m);
    });
    m.on("mouseenter", "stations", () => { m.getCanvas().style.cursor = "pointer"; });
    m.on("mouseleave", "stations", () => { m.getCanvas().style.cursor = ""; });
  }, []);

  // init map once stations are ready
  useEffect(() => {
    if (!mapDiv.current || mapRef.current || !stations) return;
    const map = createMapWithFallback(mapDiv.current, { center: JAKARTA_CENTER, zoom: 10.4 }, (m) => {
      addOverlays(m);
      wireInteractions(m);
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; wiredRef.current = false; };
  }, [stations, addOverlays, wireInteractions]);

  // keep refs current, and re-add overlays when late-arriving data lands
  useEffect(() => { stationsRef.current = stations; }, [stations]);
  useEffect(() => {
    surfaceRef.current = surface;
    const m = mapRef.current;
    if (m && m.isStyleLoaded()) addOverlays(m);
  }, [surface, addOverlays]);
  useEffect(() => {
    sourcesRef.current = sources;
    const m = mapRef.current;
    if (m && m.isStyleLoaded()) addOverlays(m);
  }, [sources, addOverlays]);

  // basemap swap: setStyle wipes overlays, so re-add them once the new style is in
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    m.setStyle(basemapStyle(basemap), { diff: false } as Parameters<typeof m.setStyle>[1]);
    const readd = () => { if (m.isStyleLoaded()) addOverlays(m); else m.once("idle", () => addOverlays(m)); };
    m.once("styledata", readd);
  }, [basemap, addOverlays]);

  // live-toggle existing layers
  useEffect(() => {
    showSurfaceRef.current = showSurface;
    const m = mapRef.current;
    if (m?.getLayer("surface")) m.setLayoutProperty("surface", "visibility", showSurface ? "visible" : "none");
  }, [showSurface]);
  useEffect(() => {
    opacityRef.current = surfaceOpacity;
    const m = mapRef.current;
    if (m?.getLayer("surface")) m.setPaintProperty("surface", "raster-opacity", surfaceOpacity);
  }, [surfaceOpacity]);
  useEffect(() => {
    sidebarRef.current = sidebarOpen;
    const m = mapRef.current;
    for (const id of ["src-heat", "src-heat-line"]) {
      if (m?.getLayer(id)) m.setLayoutProperty(id, "visibility", sidebarOpen ? "visible" : "none");
    }
  }, [sidebarOpen]);

  const feats = stations?.features ?? [];
  const active = feats.filter((f) => !isBroken(f.properties.ispu, f.properties.stale)).length;
  const broken = feats.length - active;
  const rmse = loocv?.metrics.rmse; const r2 = loocv?.metrics.r2; const n = loocv?.metrics.n;

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={mapDiv} style={{ position: "absolute", inset: 0 }} />
      <div style={{ position: "absolute", inset: "var(--topbar-inset)", display: "flex", flexDirection: "column", pointerEvents: "none" }}>
        <div style={{ pointerEvents: "auto" }}><TopBar stationCount={stationCount} sourceCount={sourceCount} /></div>
        <div style={{ margin: "10px 0 0", pointerEvents: "auto" }}><NavTabs active={view} onChange={onChange} /></div>
        <div style={{ flex: 1, position: "relative" }}>
          <div style={{ position: "absolute", right: 0, top: 8, pointerEvents: "auto" }}>
            <MapControls
              onList={() => setSidebarOpen((o) => !o)}
              onZoomIn={() => mapRef.current?.zoomIn()} onZoomOut={() => mapRef.current?.zoomOut()}
              onLayers={() => setLayersOpen((o) => !o)}
            />
          </div>

          {layersOpen && (
            <div style={{ position: "absolute", right: 60, top: 8, width: 236, pointerEvents: "auto" }}>
              <Card>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <strong style={{ fontSize: "var(--text-sm)" }}>Tampilan & layer</strong>
                  <button onClick={() => setLayersOpen(false)} aria-label="Tutup" style={{
                    width: 24, height: 24, borderRadius: "var(--radius-sm)", border: "none",
                    background: "var(--gray-100)", color: "var(--fg-secondary)", cursor: "pointer", fontSize: 13,
                  }}>✕</button>
                </div>

                <div style={{ fontSize: "var(--text-2xs)", color: "var(--fg-secondary)", marginBottom: 4 }}>Peta dasar</div>
                <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
                  {(["peta", "satelit"] as Basemap[]).map((b) => (
                    <button key={b} onClick={() => setBasemap(b)} style={{
                      flex: 1, fontFamily: "var(--font-ui)", fontSize: "var(--text-xs)", padding: "6px 0",
                      border: "none", borderRadius: "var(--radius-sm)", cursor: "pointer", textTransform: "capitalize",
                      background: basemap === b ? "var(--blue-500)" : "var(--gray-100)",
                      color: basemap === b ? "#fff" : "var(--fg-secondary)",
                      fontWeight: basemap === b ? "var(--weight-semibold)" : "var(--weight-regular)",
                    }}>{b === "peta" ? "Peta" : "Satelit"}</button>
                  ))}
                </div>

                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-sm)", cursor: "pointer", marginBottom: 8 }}>
                  <input type="checkbox" checked={showSurface} onChange={(e) => setShowSurface(e.target.checked)} />
                  Permukaan estimasi (IDW)
                </label>

                <div style={{ fontSize: "var(--text-2xs)", color: "var(--fg-secondary)", marginBottom: 2 }}>
                  Opasitas heatmap · {Math.round(surfaceOpacity * 100)}%
                </div>
                <input type="range" min={0} max={100} value={Math.round(surfaceOpacity * 100)}
                  onChange={(e) => setSurfaceOpacity(Number(e.target.value) / 100)}
                  disabled={!showSurface}
                  style={{ width: "100%", accentColor: "var(--blue-500)", marginBottom: 10 }} />

                <DisclaimerNote>
                  Heatmap sumber (arah datang, berbobot CPF) muncul saat panel Sumber (☰) dibuka.
                </DisclaimerNote>
              </Card>
            </div>
          )}

          {sidebarOpen && (
            <div style={{ position: "absolute", left: 0, top: 8, bottom: 8, pointerEvents: "auto" }}>
              <SourcesSidebar data={sources} onClose={() => setSidebarOpen(false)} onLocate={locate} />
            </div>
          )}

          {!sidebarOpen && (
          <div style={{ position: "absolute", left: 0, bottom: 0, width: 320, pointerEvents: "auto" }}>
            <Card>
              <h2 style={{ fontSize: "var(--text-base)", marginBottom: 6 }}>Peta kualitas udara</h2>
              <p style={{ color: "var(--fg-secondary)", fontSize: "var(--text-2xs)", marginBottom: 8 }}>
                {feats.length} stasiun (snapshot nyata) · {active} aktif · {broken} tidak berfungsi (abu-abu)
              </p>
              {showSurface && (
                <div style={{ background: "#fff", borderRadius: 8, padding: 8, marginBottom: 8 }}>
                  <DisclaimerNote>
                    {surface?.disclaimer ?? "Permukaan interpolasi antar-stasiun (estimasi), bukan pengukuran langsung. Klaim hotspot bersifat tingkat kecamatan, bukan presisi jalan."}
                  </DisclaimerNote>
                  {rmse != null && (
                    <div style={{ fontSize: "var(--text-xs)", marginTop: 6 }}>
                      Validasi LOOCV (nyata, tidak disembunyikan): RMSE ±{rmse} · R²={r2} (n={n})
                    </div>
                  )}
                </div>
              )}
              <ISPULegend />
            </Card>
          </div>
          )}
        </div>
      </div>
    </div>
  );
}
