/**
 * Shared source-attribution UI — used by BOTH the Sumber tab and the Peta
 * sidebar (opened by the ☰ control), so the two never drift.
 *
 * MapThumb: a tokenless static-map preview built from OSM raster <img> tiles
 * (no WebGL context per card, no API key — same basemap philosophy as
 * mapUtils.OSM_STYLE). Lazy-loaded to stay gentle on the tile server; swap the
 * tile URL for a keyed provider (Mapbox/MapTiler static) in production.
 */
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { type SourcesResp } from "../api";
import { Card, ConfidenceBadge, DisclaimerNote, Pill } from "./primitives";

type Candidate = SourcesResp["candidates"][number];
type Factor = SourcesResp["factors"][number];

/** Numeric centroid of a polygon's outer ring → [lon, lat]. */
export function polyCentroid(poly: GeoJSON.Polygon): [number, number] | null {
  const ring = poly.coordinates[0] ?? [];
  if (!ring.length) return null;
  const n = ring.length;
  const [lon, lat] = ring.reduce(([a, b], [x, y]) => [a + x, b + y], [0, 0]);
  return [lon / n, lat / n];
}

const TILE = 256;
function lonLatToPx(lon: number, lat: number, z: number) {
  const scale = TILE * 2 ** z;
  const x = ((lon + 180) / 360) * scale;
  const s = Math.min(0.9999, Math.max(-0.9999, Math.sin((lat * Math.PI) / 180)));
  const y = (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * scale;
  return { x, y };
}

/**
 * Static neighbourhood preview centred on [lon,lat]. Responsive width (measured
 * via ResizeObserver) so it fits any card; OSM tiles are absolutely positioned
 * inside an overflow-hidden box, offset so the point lands dead-centre.
 */
export function MapThumb({ lon, lat, height = 104, zoom = 12 }:
  { lon: number; lat: number; height?: number; zoom?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);

  // Measure synchronously on layout (ResizeObserver is unreliable in some
  // embedded webviews); re-measure on window resize for responsiveness.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setW(el.clientWidth);
    measure();
    let ro: ResizeObserver | undefined;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(measure);
      ro.observe(el);
    }
    window.addEventListener("resize", measure);
    return () => { ro?.disconnect(); window.removeEventListener("resize", measure); };
  }, []);

  const tiles: { key: string; url: string; sx: number; sy: number }[] = [];
  if (w > 0) {
    const { x, y } = lonLatToPx(lon, lat, zoom);
    const left = x - w / 2;
    const top = y - height / 2;
    const world = 2 ** zoom;
    for (let tx = Math.floor(left / TILE); tx <= Math.floor((left + w) / TILE); tx++) {
      for (let ty = Math.max(0, Math.floor(top / TILE)); ty <= Math.min(world - 1, Math.floor((top + height) / TILE)); ty++) {
        const wx = ((tx % world) + world) % world;
        tiles.push({
          key: `${tx}_${ty}`,
          url: `https://tile.openstreetmap.org/${zoom}/${wx}/${ty}.png`,
          sx: tx * TILE - left,
          sy: ty * TILE - top,
        });
      }
    }
  }

  return (
    <div ref={ref} style={{
      position: "relative", width: "100%", height, overflow: "hidden",
      borderRadius: "var(--radius-sm)", background: "var(--gray-100)",
    }}>
      {tiles.map((t) => (
        <img key={t.key} src={t.url} alt="" width={TILE} height={TILE}
          style={{ position: "absolute", left: t.sx, top: t.sy, maxWidth: "none" }} />
      ))}
      {w > 0 && (
        <div style={{ position: "absolute", left: w / 2, top: height / 2, transform: "translate(-50%,-100%)", pointerEvents: "none" }}>
          <svg width="20" height="26" viewBox="0 0 20 26" aria-hidden>
            <path d="M10 0C4.5 0 0 4.5 0 10c0 7 10 16 10 16s10-9 10-16C20 4.5 15.5 0 10 0z"
              fill="var(--ispu-tidak-sehat)" stroke="#fff" strokeWidth="1.6" />
            <circle cx="10" cy="10" r="3.4" fill="#fff" />
          </svg>
        </div>
      )}
    </div>
  );
}

/** Optional wrapper turning a card into a "click to locate on map" affordance. */
function Locatable({ onClick, children }: { onClick?: () => void; children: ReactNode }) {
  if (!onClick) return <>{children}</>;
  return (
    <div onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}
      style={{ cursor: "pointer" }}>{children}</div>
  );
}

/* ---------- Layer C: source-type factor ---------- */
export function FactorCard({ factor }: { factor: Factor }) {
  return (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontSize: "var(--text-base)", textTransform: "capitalize" }}>{factor.label}</strong>
        <Pill tone={factor.confidence > 0.6 ? "good" : "warn"}>Jenis sumber</Pill>
      </div>
      <div style={{ margin: "10px 0" }}><ConfidenceBadge level={factor.confidence} /></div>
      <ul style={{ fontSize: "var(--text-xs)", paddingLeft: 18, margin: 0, color: "var(--fg-secondary)" }}>
        {factor.evidence.map((e, j) => <li key={j}>{e}</li>)}
      </ul>
    </Card>
  );
}

/* ---------- Layer A: directional candidate (with map thumbnail) ---------- */
export function CandidateCard({ cand, onLocate }:
  { cand: Candidate; onLocate?: (lon: number, lat: number) => void }) {
  const cpf = parseFloat(/CPF=([\d.]+)/.exec(cand.notes)?.[1] ?? "0");
  const deg = /arah (\d+)/.exec(cand.notes)?.[1];
  const sid = /^(\S+?):/.exec(cand.notes)?.[1] ?? "stasiun";
  const c = polyCentroid(cand.geometry);

  return (
    <Locatable onClick={c && onLocate ? () => onLocate(c[0], c[1]) : undefined}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <strong style={{ fontSize: "var(--text-sm)" }}>{sid}{deg ? ` · arah ${deg}°` : ""}</strong>
          <Pill tone={cpf > 0.6 ? "good" : "warn"}>Layer A</Pill>
        </div>
        {c && <MapThumb lon={c[0]} lat={c[1]} />}
        <div style={{ margin: "10px 0" }}><ConfidenceBadge level={cpf} label={`CPF ${cpf.toFixed(2)}`} /></div>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--fg-secondary)", marginBottom: 8 }}>
          pusat area ~{c ? `${c[1].toFixed(4)}, ${c[0].toFixed(4)}` : "—"}
        </div>
        <DisclaimerNote>
          Arah datang polusi (bukan lokasi presisi). Jenis sumber (Layer C · NMF) sedang diakumulasi dari riwayat jam-an.
        </DisclaimerNote>
      </Card>
    </Locatable>
  );
}

/* ---------- Peta sidebar (opened by the ☰ control) ---------- */
export function SourcesSidebar({ data, onClose, onLocate }:
  { data: SourcesResp | null; onClose: () => void; onLocate?: (lon: number, lat: number) => void }) {
  const factors = data?.factors ?? [];
  const candidates = data?.candidates ?? [];

  return (
    <aside style={{
      width: 360, maxWidth: "82vw", height: "100%", display: "flex", flexDirection: "column",
      fontFamily: "var(--font-ui)", background: "var(--surface-card-translucent)",
      backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
      borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-md)", overflow: "hidden",
    }}>
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border-hairline)", flexShrink: 0,
      }}>
        <div>
          <strong style={{ fontSize: "var(--text-base)" }}>Sumber polusi</strong>
          <div style={{ fontSize: "var(--text-2xs)", color: "var(--fg-secondary)" }}>
            {candidates.length} kandidat arah · triangulasi polar/CPF
          </div>
        </div>
        <button onClick={onClose} aria-label="Tutup" style={{
          width: 30, height: 30, borderRadius: "var(--radius-sm)", border: "none",
          background: "var(--gray-100)", color: "var(--fg-secondary)", cursor: "pointer",
          fontSize: "var(--text-base)", lineHeight: 1,
        }}>✕</button>
      </header>

      <div style={{ flex: 1, overflowY: "auto", padding: "var(--space-4)", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        {factors.map((f, i) => <FactorCard key={`f${i}`} factor={f} />)}
        {candidates.slice(0, 24).map((c, i) => <CandidateCard key={`c${i}`} cand={c} onLocate={onLocate} />)}
        {!data && <p style={{ color: "var(--fg-secondary)", fontSize: "var(--text-sm)" }}>Memuat atribusi…</p>}
        {data && !candidates.length && !factors.length && (
          <p style={{ color: "var(--fg-secondary)", fontSize: "var(--text-sm)" }}>Belum ada kandidat sumber.</p>
        )}
      </div>

      <footer style={{
        padding: "var(--space-2) var(--space-4)", fontSize: "var(--text-2xs)", color: "var(--fg-secondary)",
        borderTop: "1px solid var(--border-hairline)", flexShrink: 0,
      }}>
        Ketuk kartu untuk memusatkan peta · thumbnail © OpenStreetMap
      </footer>
    </aside>
  );
}
