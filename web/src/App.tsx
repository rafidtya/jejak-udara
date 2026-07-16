/**
 * JejakUdara — Track-A demo shell. Fixture-fed (frozen REAL data, no backend);
 * in August the fixtures swap for live API calls, views stay.
 */
import { useEffect, useState } from "react";
import "./app.css";
import type { Heatmap, Meta, ScenarioSet, Station } from "./fixtures";
import { loadJson } from "./fixtures";
import KelayakanView from "./views/KelayakanView";
import PetaView from "./views/PetaView";
import SumberView from "./views/SumberView";
import TwinView from "./views/TwinView";

const VIEWS = ["Peta", "Twin", "Sumber", "Kelayakan"] as const;
type View = (typeof VIEWS)[number];

export default function App() {
  const [view, setView] = useState<View>("Peta");
  const [stations, setStations] = useState<Station[] | null>(null);
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioSet | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    loadJson<Station[]>("/fixtures/stations.json").then(setStations);
    loadJson<Heatmap>("/fixtures/heatmap.json").then(setHeatmap);
    loadJson<ScenarioSet>("/fixtures/scenarios.json").then(setScenarios);
    loadJson<Meta>("/fixtures/meta.json").then(setMeta);
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <h1>JejakUdara</h1>
        <span className="tagline">
          Dari mana polusi Jakarta berasal — dan apa yang terjadi jika kita bertindak
        </span>
        {meta && (
          <span className="freshness">
            Snapshot data nyata:{" "}
            {new Date(meta.captured_at_utc).toLocaleDateString("id-ID")} ·{" "}
            {meta.station_count} stasiun SPKU
          </span>
        )}
      </header>
      <nav className="nav">
        {VIEWS.map((v) => (
          <button
            key={v}
            className={`nav-btn ${view === v ? "active" : ""}`}
            onClick={() => setView(v)}
          >
            {v}
          </button>
        ))}
      </nav>
      <main className="main">
        {view === "Peta" &&
          (stations ? (
            <PetaView stations={stations} heatmap={heatmap} />
          ) : (
            <p className="muted view-pad">Memuat snapshot stasiun…</p>
          ))}
        {view === "Twin" && <TwinView scenarios={scenarios} />}
        {view === "Sumber" && <SumberView />}
        {view === "Kelayakan" && <KelayakanView meta={meta} />}
      </main>
      <footer className="footer">
        Data: DLH DKI Jakarta (SPKU) · BMKG · demo prototipe — seluruh permukaan
        berlabel <em>estimasi</em>, titik stasiun = terukur
      </footer>
    </div>
  );
}
