/**
 * Chrome components — TopBar, NavTabs, MapControls. Ported faithfully from the
 * Claude Design project (components/layout, components/navigation). Wordmark is
 * rendered as text (Medium 500, -0.08em tracking, brand blue) per the wordmark
 * spec, avoiding a binary asset; search icon is inline SVG.
 */

const VIEWS = ["Peta", "Twin", "Sumber", "Kelayakan"] as const;
export type View = (typeof VIEWS)[number];

function SearchGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.4" strokeLinecap="round">
      <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span style={{
      fontFamily: "var(--font-ui)", fontWeight: "var(--weight-medium)",
      letterSpacing: "var(--tracking-tight)", fontSize: "var(--text-2xs)",
      color: "var(--blue-500)", whiteSpace: "nowrap",
    }}>JejakUdara</span>
  );
}

function CountChip({ dotColor, value, label }: { dotColor: string; value: number | string; label: string }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6, background: "#fff",
      borderRadius: "var(--radius-pill)", padding: "4px 12px 4px 4px", boxShadow: "var(--shadow-sm)",
    }}>
      <span style={{ width: 22, height: 22, borderRadius: "var(--radius-circle)", background: dotColor }} />
      <span style={{ fontWeight: "var(--weight-extrabold)", fontSize: "var(--text-base)" }}>{value}</span>
      <span style={{ fontWeight: "var(--weight-medium)", fontSize: "var(--text-xs)", color: "var(--fg-secondary)" }}>{label}</span>
    </div>
  );
}

export function TopBar({ stationCount, sourceCount }: { stationCount: number | string; sourceCount: number | string }) {
  return (
    <div style={{
      width: "100%", height: 45, borderRadius: "var(--radius-md)",
      background: "var(--surface-card-translucent)", boxShadow: "var(--shadow-sm)",
      display: "flex", padding: "0 var(--space-4)", justifyContent: "space-between",
      alignItems: "center", boxSizing: "border-box", fontFamily: "var(--font-ui)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ color: "var(--blue-500)", display: "inline-flex" }}><SearchGlyph /></span>
        <span style={{ fontWeight: "var(--weight-semibold)", fontSize: "var(--text-sm)", color: "var(--fg-secondary)" }}>
          Cari lokasi, koordinat, atau nama stasiun
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <CountChip dotColor="var(--blue-500)" value={stationCount} label="Stasiun SPKU" />
        <CountChip dotColor="var(--ispu-tidak-sehat)" value={sourceCount} label="Sumber polusi" />
        <Wordmark />
      </div>
    </div>
  );
}

export function NavTabs({ active, onChange }: { active: View; onChange: (v: View) => void }) {
  return (
    <nav style={{ display: "flex", gap: 6 }}>
      {VIEWS.map((v) => (
        <button key={v} onClick={() => onChange(v)} style={{
          fontFamily: "var(--font-ui)", fontSize: "var(--text-sm)", padding: "6px 16px",
          border: "none", borderRadius: "var(--radius-sm)", cursor: "pointer",
          boxShadow: "var(--shadow-sm)",
          background: active === v ? "var(--blue-500)" : "var(--surface-card-translucent)",
          color: active === v ? "#fff" : "var(--fg-primary)",
          fontWeight: active === v ? "var(--weight-semibold)" : "var(--weight-regular)",
        }}>{v}</button>
      ))}
    </nav>
  );
}

const MAP_ICONS: Record<string, string> = { list: "☰", plus: "+", minus: "–", layers: "▤" };
function ControlButton({ icon, onClick }: { icon: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} style={{
      width: 46, height: 43, borderRadius: "var(--radius-md)", background: "#fff",
      boxShadow: "var(--shadow-md)", border: "none", display: "flex", alignItems: "center",
      justifyContent: "center", color: "var(--blue-500)", fontSize: "var(--text-lg)", cursor: "pointer",
    }}>{MAP_ICONS[icon] ?? icon}</button>
  );
}
export function MapControls({ onList, onZoomIn, onZoomOut, onLayers }:
  { onList?: () => void; onZoomIn?: () => void; onZoomOut?: () => void; onLayers?: () => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <ControlButton icon="list" onClick={onList} />
      <ControlButton icon="plus" onClick={onZoomIn} />
      <ControlButton icon="minus" onClick={onZoomOut} />
      <ControlButton icon="layers" onClick={onLayers} />
    </div>
  );
}
