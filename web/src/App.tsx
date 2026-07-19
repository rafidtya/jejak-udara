/**
 * JejakUdara — 4-view console (Peta / Twin / Sumber / Kelayakan), design system
 * implemented from the Claude Design project, wired to the live backend API.
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import { type View } from "./components/chrome";
import KelayakanView from "./views/KelayakanView";
import PetaView from "./views/PetaView";
import TwinView from "./views/TwinView";

export default function App() {
  const [view, setView] = useState<View>("Peta");
  const [stationCount, setStationCount] = useState(0);
  const [sourceCount, setSourceCount] = useState(0);

  useEffect(() => {
    api.meta().then((m) => setStationCount(m?.station_count ?? 0));
    api.sources().then((s) => setSourceCount(s?.candidates.length ?? 0));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, minHeight: 0 }}>
        {view === "Peta" && <PetaView view={view} onChange={setView} stationCount={stationCount} sourceCount={sourceCount} />}
        {view === "Twin" && <TwinView view={view} onChange={setView} stationCount={stationCount} sourceCount={sourceCount} />}
        {view === "Kelayakan" && <KelayakanView view={view} onChange={setView} />}
      </div>
      <footer style={{
        padding: "6px 18px", fontSize: "var(--text-xs)", color: "var(--fg-secondary)",
        background: "var(--gray-050)", borderTop: "1px solid var(--gray-100)", fontFamily: "var(--font-ui)",
      }}>
        Data: DLH DKI Jakarta (SPKU) · BMKG · Open-Meteo — seluruh permukaan berlabel{" "}
        <em>estimasi</em>, titik stasiun = terukur
      </footer>
    </div>
  );
}
