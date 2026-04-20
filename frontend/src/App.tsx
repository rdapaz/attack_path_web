import { useState } from "react";
import BuildView from "./components/BuildView";
import ViewerView from "./components/ViewerView";
import SettingsView from "./components/SettingsView";

type View = "build" | "viewer" | "settings";

export default function App() {
  const [view, setView] = useState<View>("build");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>Attack Path</h1>
        <button className={`nav-btn ${view === "build" ? "active" : ""}`} onClick={() => setView("build")}>
          Build
        </button>
        <button className={`nav-btn ${view === "viewer" ? "active" : ""}`} onClick={() => setView("viewer")}>
          Viewer
        </button>
        <button className={`nav-btn ${view === "settings" ? "active" : ""}`} onClick={() => setView("settings")}>
          Settings
        </button>
      </aside>
      <main className="main">
        {view === "build" && <BuildView />}
        {view === "viewer" && <ViewerView />}
        {view === "settings" && <SettingsView />}
      </main>
    </div>
  );
}
