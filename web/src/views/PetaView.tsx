/**
 * Peta — real MapLibre map (live /stations measured dots + /surface IDW estimate)
 * dressed in the JejakUdara design chrome (TopBar / NavTabs / MapControls / Card).
 * Honesty: dots = measured (crisp), surface = estimasi (translucent) + LOOCV shown.
 */
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { api, type SourcesResp, type StationsFC, type Surface, type ValidationRun } from "../api";
import { MapControls, NavTabs, TopBar, type View } from "../components/chrome";
import { Card, DisclaimerNote, ISPULegend } from "../components/primitives";
import { SourcesSidebar } from "../components/sources";
import {
  bboxCorners, createMapWithFallback, gridToDataURL, ispuColor, JAKARTA_CENTER,
} from "../mapUtils";

interface Props { view: View; onChange: (v: View) => void; stationCount: number; sourceCount: number; }

export default function PetaView({ view, onChange, stationCount, sourceCount }: Props) {
  const mapDiv = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [stations, setStations] = useState<StationsFC | null>(null);
  const [surface, setSurface] = useState<Surface | null>(null);
  const [loocv, setLoocv] = useState<ValidationRun | null>(null);
  const [showSurface, setShowSurface] = useState(true);
  const [sources, setSources] = useState<SourcesResp | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    api.stations().then(setStations);
    api.surface().then(setSurface);
    api.validation().then((v) => setLoocv(v?.find((x) => x.kind === "loocv") ?? null));
    api.sources().then(setSources);
  }, []);

  const locate = (lon: number, lat: number) =>
    mapRef.current?.flyTo({ center: [lon, lat], zoom: 12.5, speed: 0.8 });

  // init map once stations are ready (surface added separately — it may arrive later)
  useEffect(() => {
    if (!mapDiv.current || mapRef.current || !stations) return;
    const map = createMapWithFallback(mapDiv.current, { center: JAKARTA_CENTER, zoom: 10.4 }, (m) => {
      m.addSource("stations", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: stations.features.map((f) => ({
            ...f, properties: { ...f.properties, color: ispuColor(f.properties.ispu, f.properties.stale) },
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
      m.on("click", "stations", (e) => {
        const p = e.features?.[0]?.properties as StationsFC["features"][0]["properties"] | undefined;
        if (!p) return;
        new maplibregl.Popup({ maxWidth: "300px" }).setLngLat(e.lngLat).setHTML(
          `<div style="font-family:var(--font-ui);font-size:13px">
             <strong>${p.name}</strong><br/>
             <span style="color:#737373">${p.station_id} · ${p.kind === "reference" ? "referensi" : "low-cost"}</span><br/>
             ISPU: <strong>${p.ispu ?? "—"}</strong>${p.stale ? ' <span style="color:#7a5c00">⚠ stale</span>' : ""}
           </div>`,
        ).addTo(m);
      });
      m.on("mouseenter", "stations", () => { m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", "stations", () => { m.getCanvas().style.cursor = ""; });
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, [stations]);

  // add the estimated surface beneath the station dots, whenever it arrives
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !surface?.available) return;
    const add = () => {
      if (!m.getSource("stations") || m.getLayer("surface")) return;
      m.addSource("surface", {
        type: "image",
        url: gridToDataURL(surface.values, surface.nrows, surface.ncols, surface.metric),
        coordinates: bboxCorners(surface.bbox),
      });
      m.addLayer({ id: "surface", type: "raster", source: "surface",
        paint: { "raster-opacity": 0.5, "raster-resampling": "nearest" } }, "stations");
    };
    if (m.isStyleLoaded() && m.getSource("stations")) add(); else m.once("idle", add);
  }, [surface]);

  useEffect(() => {
    const m = mapRef.current;
    if (m?.getLayer("surface")) m.setLayoutProperty("surface", "visibility", showSurface ? "visible" : "none");
  }, [showSurface, surface]);

  const feats = stations?.features ?? [];
  const active = feats.filter((f) => !f.properties.stale).length;
  const stale = feats.length - active;
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
              onLayers={() => setShowSurface((s) => !s)}
            />
          </div>
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
                {feats.length} stasiun (snapshot nyata) · {active} aktif · {stale} stale (abu-abu)
              </p>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-sm)", cursor: "pointer", marginBottom: 8 }}>
                <input type="checkbox" checked={showSurface} onChange={(e) => setShowSurface(e.target.checked)} />
                Permukaan estimasi (IDW)
              </label>
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
