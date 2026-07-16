/** Kelayakan (feasibility) view — the receipts. Day-3 polish; skeleton today. */
import type { Meta } from "../fixtures";

export default function KelayakanView({ meta }: { meta: Meta | null }) {
  return (
    <div className="view-pad">
      <h2>Bukti kelayakan (feasibility)</h2>
      {meta && (
        <div className="card">
          <strong>Data pada demo ini nyata</strong>
          <p className="small">
            Snapshot {meta.station_count} stasiun SPKU diambil langsung dari{" "}
            {meta.source} pada{" "}
            {new Date(meta.captured_at_utc).toLocaleString("id-ID", {
              timeZone: "Asia/Jakarta",
            })}{" "}
            WIB.
          </p>
        </div>
      )}
      <div className="card">
        <strong>Terverifikasi hingga hari ini</strong>
        <ul className="small">
          <li>✅ Kontrak data SPKU (105+ stasiun) — diverifikasi live, scraper berjalan</li>
          <li>✅ Kontrak API BMKG per-kelurahan (267 kode adm4) — diverifikasi live</li>
          <li>✅ Mesin simulasi Gaussian plume — lolos uji fisika (20/20 tes)</li>
          <li>✅ Interpolasi IDW + validasi LOOCV — metrik nyata tampil di Peta</li>
          <li>⏳ Atribusi sumber (NMF + wind back-tracing) — dibangun menuju final</li>
        </ul>
      </div>
      <p className="muted small">
        Diagram arsitektur & alur data menyusul di Hari 3.
      </p>
    </div>
  );
}
