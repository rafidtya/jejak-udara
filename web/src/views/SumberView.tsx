/**
 * Sumber — source attribution from live /sources. Shows Layer-C source-type
 * factors (with ConfidenceBadge + evidence) when present; otherwise the real
 * Layer-A directional candidates, honestly labeled while typing accumulates.
 * Cards (incl. the map thumbnail) are shared with the Peta ☰ sidebar.
 */
import { useEffect, useState } from "react";
import { api, type SourcesResp } from "../api";
import { NavTabs, type View } from "../components/chrome";
import { CandidateCard, FactorCard } from "../components/sources";

interface Props { view: View; onChange: (v: View) => void; }

export default function SumberView({ view, onChange }: Props) {
  const [data, setData] = useState<SourcesResp | null>(null);
  useEffect(() => { api.sources().then(setData); }, []);

  const factors = data?.factors ?? [];
  const candidates = data?.candidates ?? [];

  return (
    <div style={{ padding: "var(--space-7)", maxWidth: 1040, margin: "0 auto", fontFamily: "var(--font-ui)", height: "100%", overflowY: "auto", boxSizing: "border-box" }}>
      <div style={{ marginBottom: 16 }}><NavTabs active={view} onChange={onChange} /></div>
      <h2 style={{ fontSize: "var(--text-xl)", marginBottom: 6 }}>Atribusi sumber polusi</h2>
      <p style={{ color: "var(--fg-secondary)", fontSize: "var(--text-sm)", marginBottom: 20 }}>
        Arah datang + jenis sumber terduga + tingkat keyakinan + bukti pendukung, untuk setiap titik sumber pada Peta.
      </p>

      {factors.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16, marginBottom: 24 }}>
          {factors.map((f, i) => <FactorCard key={i} factor={f} />)}
        </div>
      )}

      <h3 style={{ fontSize: "var(--text-base)", margin: "0 0 4px" }}>Arah datang sumber (Layer A · wind back-tracing)</h3>
      <p style={{ color: "var(--fg-secondary)", fontSize: "var(--text-xs)", marginBottom: 12 }}>
        {candidates.length} kandidat arah dari triangulasi polar/CPF antar-stasiun.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
        {candidates.slice(0, 24).map((c, i) => <CandidateCard key={i} cand={c} />)}
      </div>
      {!data && <p style={{ color: "var(--fg-secondary)" }}>Memuat atribusi…</p>}
    </div>
  );
}
