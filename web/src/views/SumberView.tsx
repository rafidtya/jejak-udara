/** Sumber view — source attribution cards (Day-2 build; layout skeleton today). */
export default function SumberView() {
  return (
    <div className="view-pad">
      <h2>Atribusi sumber polusi</h2>
      <p className="muted">
        Menyusul di Hari 2: kartu sumber (arah + jenis + tingkat keyakinan + bukti),
        polar plot per stasiun (ECharts), dan overlay arah angin BMKG.
      </p>
      <div className="card">
        <strong>Yang akan tampil di sini</strong>
        <ul>
          <li>Arah datang polusi per stasiun (bivariate polar / CPF)</li>
          <li>Jenis sumber terduga (lalu lintas / industri / pembakaran) + confidence</li>
          <li>Bukti pendukung: jalan besar terdekat, zona industri, titik api satelit upwind</li>
        </ul>
      </div>
    </div>
  );
}
