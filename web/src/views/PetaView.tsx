/**
 * Peta view — real station snapshot on a MapLibre map + IDW surface overlay.
 * Honesty rules: station dots = measured; surface = labeled interpolation with
 * its real LOOCV metrics shown, stale stations grayed out.
 */
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { Heatmap, Station } from "../fixtures";
import {
  bboxCorners, gridToDataURL, ispuColor, ISPU_LEGEND, JAKARTA_CENTER, OSM_STYLE,
} from "../mapUtils";

interface Props {
  stations: Station[];
  heatmap: Heatmap | null;
}

function popupHtml(s: Station): string {
  const upd = s.last_update_utc
    ? new Date(s.last_update_utc).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" })
    : "—";
  const staleWarn = s.stale
    ? `<div class="pill pill-warn">⚠ data stale — pembaruan terakhir sudah lama</div>` : "";
  return `
    <strong>${s.name}</strong><br/>
    <span class="muted">${s.station_id} · ${s.kind === "reference" ? "Stasiun referensi" : "Sensor low-cost"}</span><br/>
    ISPU: <strong>${s.ispu ?? "—"}</strong> (${s.category ?? "—"})<br/>
    ${s.parameter ?? ""} ${s.concentration != null ? `${s.concentration} µg/m³` : ""}<br/>
    <span class="muted">Pembaruan: ${upd} WIB</span>
    ${staleWarn}`;
}

export default function PetaView({ stations, heatmap }: Props) {
  const mapDiv = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [showSurface, setShowSurface] = useState(true);

  useEffect(() => {
    if (!mapDiv.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapDiv.current,
      style: OSM_STYLE,
      center: JAKARTA_CENTER,
      zoom: 10.3,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", () => {
      if (heatmap) {
        map.addSource("surface", {
          type: "image",
          url: gridToDataURL(heatmap.values, heatmap.nrows, heatmap.ncols, heatmap.metric),
          coordinates: bboxCorners(heatmap.bbox),
        });
        map.addLayer({
          id: "surface",
          type: "raster",
          source: "surface",
          paint: { "raster-opacity": 0.55, "raster-resampling": "nearest" },
        });
      }

      map.addSource("stations", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: stations.map((s) => ({
            type: "Feature" as const,
            geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
            properties: { id: s.station_id, color: ispuColor(s.ispu, s.stale) },
          })),
        },
      });
      map.addLayer({
        id: "stations",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": 6,
          "circle-color": ["get", "color"],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("click", "stations", (e) => {
        const id = e.features?.[0]?.properties?.id as string | undefined;
        const s = stations.find((st) => st.station_id === id);
        if (!s) return;
        new maplibregl.Popup({ maxWidth: "320px" })
          .setLngLat([s.lon, s.lat])
          .setHTML(popupHtml(s))
          .addTo(map);
      });
      map.on("mouseenter", "stations", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "stations", () => { map.getCanvas().style.cursor = ""; });
    });

    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stations, heatmap]);

  useEffect(() => {
    const map = mapRef.current;
    if (map?.getLayer("surface")) {
      map.setLayoutProperty("surface", "visibility", showSurface ? "visible" : "none");
    }
  }, [showSurface]);

  const live = stations.filter((s) => !s.stale).length;

  return (
    <div className="view-map">
      <div ref={mapDiv} className="map-container" />
      <aside className="map-panel">
        <h2>Peta kualitas udara</h2>
        <p className="muted">
          {stations.length} stasiun (snapshot nyata) · {live} aktif ·{" "}
          {stations.length - live} stale (abu-abu)
        </p>
        <label className="toggle">
          <input
            type="checkbox"
            checked={showSurface}
            onChange={(e) => setShowSurface(e.target.checked)}
          />{" "}
          Permukaan estimasi (IDW)
        </label>
        {heatmap && showSurface && (
          <div className="card">
            <div className="muted small">{heatmap.disclaimer}</div>
            <div className="small">
              Validasi LOOCV nyata: R²={heatmap.loocv.r2}, RMSE={heatmap.loocv.rmse}{" "}
              ({heatmap.metric}, {heatmap.n_stations_used} stasiun)
            </div>
          </div>
        )}
        <div className="legend">
          {ISPU_LEGEND.map((l) => (
            <div key={l.label} className="legend-row">
              <span className="dot" style={{ background: l.color }} /> {l.label}
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
