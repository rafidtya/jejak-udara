/**
 * Kelayakan — feasibility receipts, wired to live /meta (real station count +
 * ingestion freshness). Verbatim checklist copy from the design system's kit.
 */
import { useEffect, useState } from "react";
import { api, type Meta } from "../api";
import { NavTabs, type View } from "../components/chrome";
import { Card } from "../components/primitives";

interface Props { view: View; onChange: (v: View) => void; }

const CHECKLIST = [
  { done: true, text: "Kontrak data SPKU (105+ stasiun) — diverifikasi live, scraper berjalan" },
  { done: true, text: "Kontrak API BMKG per-kelurahan (267 kode adm4) — diverifikasi live" },
  { done: true, text: "Mesin simulasi Gaussian plume — lolos uji fisika (20/20 tes)" },
  { done: true, text: "Interpolasi IDW + validasi LOOCV — metrik nyata tampil di Peta" },
  { done: false, text: "Atribusi jenis sumber (NMF + wind back-tracing) — dibangun menuju final" },
];

export default function KelayakanView({ view, onChange }: Props) {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => { api.meta().then(setMeta); }, []);

  const spku = meta?.ingestion.find((i) => i.source === "spku");
  const captured = spku?.last_success
    ? new Date(spku.last_success).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" })
    : "—";

  return (
    <div style={{ padding: "var(--space-7)", maxWidth: 760, margin: "0 auto", fontFamily: "var(--font-ui)", height: "100%", overflowY: "auto", boxSizing: "border-box" }}>
      <div style={{ marginBottom: 16 }}><NavTabs active={view} onChange={onChange} /></div>
      <h2 style={{ fontSize: "var(--text-xl)", marginBottom: 6 }}>Bukti kelayakan (feasibility)</h2>

      <Card style={{ margin: "16px 0" }}>
        <strong style={{ fontSize: "var(--text-sm)" }}>Data pada demo ini nyata</strong>
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--fg-secondary)", margin: "6px 0 0" }}>
          Snapshot {meta?.station_count ?? "—"} stasiun SPKU diambil langsung dari udara.jakarta.go.id.
          Pembaruan ingestion terakhir: {captured} WIB.
        </p>
      </Card>

      <Card>
        <strong style={{ fontSize: "var(--text-sm)" }}>Terverifikasi hingga hari ini</strong>
        <ul style={{ fontSize: "var(--text-2xs)", paddingLeft: 18, margin: "6px 0 0", lineHeight: "var(--leading-normal)" }}>
          {CHECKLIST.map((c) => <li key={c.text}>{c.done ? "✅" : "⏳"} {c.text}</li>)}
        </ul>
      </Card>

      <p style={{ color: "var(--fg-secondary)", fontSize: "var(--text-2xs)", marginTop: 12 }}>
        Diagram arsitektur &amp; alur data menyusul.
      </p>
    </div>
  );
}
