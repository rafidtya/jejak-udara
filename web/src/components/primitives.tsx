/**
 * JejakUdara design-system primitives — ported from the Claude Design project
 * "JejakUdara Design System" (components/*). Inline styles use CSS variables
 * from tokens/*.css. All copy Bahasa Indonesia; honesty rules baked in.
 */
import type { CSSProperties, ReactNode } from "react";

/* ---------- surfaces/Card ---------- */
export function Card({ children, translucent = false, style }:
  { children: ReactNode; translucent?: boolean; style?: CSSProperties }) {
  return (
    <div style={{
      fontFamily: "var(--font-ui)",
      background: translucent ? "var(--surface-panel-translucent)" : "var(--surface-card-translucent)",
      borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-sm)",
      padding: "var(--space-3) var(--space-4)", ...style,
    }}>{children}</div>
  );
}

/* ---------- data/DisclaimerNote ---------- */
export function DisclaimerNote({ children }: { children: ReactNode }) {
  return (
    <div style={{
      fontFamily: "var(--font-ui)", fontSize: "var(--text-xs)",
      color: "var(--fg-secondary)", lineHeight: "var(--leading-normal)",
    }}>{children}</div>
  );
}

/* ---------- data/ConfidenceBadge — required on every attribution ---------- */
export function ConfidenceBadge({ level, label }: { level: number; label?: string }) {
  const pct = Math.round(level * 100);
  return (
    <div style={{ fontFamily: "var(--font-ui)", display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 72, height: 6, borderRadius: "var(--radius-pill)", background: "var(--gray-100)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: "var(--blue-500)", borderRadius: "var(--radius-pill)" }} />
      </div>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--fg-secondary)", fontWeight: "var(--weight-medium)" }}>
        {label ?? `Keyakinan ${pct}%`}
      </span>
    </div>
  );
}

/* ---------- feedback/Pill ---------- */
type PillTone = "warn" | "stale" | "good";
const PILL_TONES: Record<PillTone, { bg: string; fg: string }> = {
  warn: { bg: "var(--warn-bg)", fg: "var(--warn-fg)" },
  stale: { bg: "var(--gray-100)", fg: "var(--gray-600)" },
  good: { bg: "var(--positive-bg)", fg: "var(--positive-fg)" },
};
export function Pill({ tone = "warn", children }: { tone?: PillTone; children: ReactNode }) {
  const t = PILL_TONES[tone] ?? PILL_TONES.warn;
  return (
    <span style={{
      display: "inline-block", fontFamily: "var(--font-ui)", fontSize: "var(--text-xs)",
      fontWeight: "var(--weight-medium)", padding: "2px 8px", borderRadius: "var(--radius-pill)",
      background: t.bg, color: t.fg,
    }}>{children}</span>
  );
}

/* ---------- feedback/DeltaBadge (twin result) ---------- */
export function DeltaBadge({ deltaMaxLocal, deltaMeanPct }: { deltaMaxLocal: number; deltaMeanPct: number }) {
  return (
    <div style={{
      fontFamily: "var(--font-ui)", padding: "var(--space-3) var(--space-4)",
      borderRadius: "var(--radius-md)", fontSize: "var(--text-base)", fontWeight: "var(--weight-semibold)",
      background: "var(--surface-card-translucent)", boxShadow: "var(--shadow-sm)",
      color: "var(--fg-primary)", margin: "var(--space-2) 0",
    }}>
      Di titik paling terdampak: {deltaMaxLocal} µg/m³ vs baseline
      <div style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-regular)", color: "var(--fg-secondary)" }}>
        (rata-rata seluruh kota: {deltaMeanPct > 0 ? "+" : ""}{deltaMeanPct}% — dampak intervensi bersifat lokal di sekitar sumber, sesuai fisika dispersi)
      </div>
    </div>
  );
}

/* ---------- forms/ScenarioButton ---------- */
export function ScenarioButton({ title, active = false, onClick }:
  { title: string; active?: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      display: "block", width: "100%", textAlign: "left", fontFamily: "var(--font-ui)",
      fontSize: "var(--text-sm)", padding: "var(--space-3) var(--space-4)",
      borderRadius: "var(--radius-md)", border: "none", boxShadow: "var(--shadow-md)",
      background: active ? "var(--blue-500)" : "var(--gray-100)",
      color: active ? "#fff" : "var(--fg-secondary)",
      fontWeight: active ? "var(--weight-semibold)" : "var(--weight-regular)",
      cursor: "pointer", margin: "var(--space-1) 0",
    }}>{title}</button>
  );
}

/* ---------- data/ISPUDot + ISPULegend ---------- */
export function ISPUDot({ color, size = 12 }: { color: string; size?: number }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size, borderRadius: "var(--radius-circle)",
      background: color, border: "1.5px solid #fff", boxShadow: "0 0 0 1px #ccc", flexShrink: 0,
    }} />
  );
}
const ISPU_LEVELS = [
  { label: "Baik (0–50)", color: "var(--ispu-baik)" },
  { label: "Sedang (51–100)", color: "var(--ispu-sedang)" },
  { label: "Tidak Sehat (101–200)", color: "var(--ispu-tidak-sehat)" },
  { label: "Sangat Tidak Sehat (201–300)", color: "var(--ispu-sangat-tidak-sehat)" },
  { label: "Berbahaya (>300)", color: "var(--ispu-berbahaya)" },
  { label: "Tidak berfungsi / tidak ada data", color: "var(--ispu-stale)" },
];
export function ISPULegend() {
  return (
    <div style={{ fontFamily: "var(--font-ui)", display: "flex", flexDirection: "column", gap: 6 }}>
      {ISPU_LEVELS.map((l) => (
        <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-xs)" }}>
          <ISPUDot color={l.color} /> {l.label}
        </div>
      ))}
    </div>
  );
}
