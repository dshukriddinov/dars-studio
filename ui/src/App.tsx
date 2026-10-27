import { useEffect } from "react";
import { connectJobs, useStore, type Tab } from "./store";
import { Home } from "./screens/Home";
import { NewProject } from "./screens/NewProject";
import { Project } from "./screens/Project";
import { Review } from "./screens/Review";
import { KeyCalib } from "./screens/KeyCalib";
import { TemplateCalib } from "./screens/TemplateCalib";
import { Export } from "./screens/Export";
import { Settings } from "./screens/Settings";

const TABS: [Tab, string, () => JSX.Element][] = [
  ["home", "Bosh sahifa", Home],
  ["new", "Yangi loyiha", NewProject],
  ["project", "Loyiha", Project],
  ["review", "Tekshirish", Review],
  ["key", "Key kalibrlash", KeyCalib],
  ["template", "Shablon kalibrlash", TemplateCalib],
  ["export", "Eksport", Export],
  ["settings", "Sozlamalar", Settings],
];

export function App() {
  const tab = useStore((s) => s.tab);
  const name = useStore((s) => s.name);
  const error = useStore((s) => s.error);
  const notice = useStore((s) => s.notice);
  const busy = useStore((s) => s.busy);
  const { setTab, clearError } = useStore.getState();
  useEffect(() => connectJobs(), []);
  const Screen = TABS.find(([t]) => t === tab)![2];

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand body-strong">Dars Studio</span>
        <nav>
          {TABS.map(([t, label]) => (
            <button key={t} className={`tab${t === tab ? " on" : ""}`} onClick={() => setTab(t)}>{label}</button>
          ))}
        </nav>
        <span className="spacer" />
        {busy ? <span className="caption accent">Saqlanmoqda…</span> : notice ? <span className="caption success">{notice}</span> : null}
        {name ? <span className="caption dim">Loyiha: <b>{name}</b></span> : null}
      </header>
      {error ? (
        <div className="banner banner-error toast" role="alert">
          <span className="body">{error}</span>
          <button className="btn-ghost" onClick={clearError}>Yopish</button>
        </div>
      ) : null}
      <main><Screen /></main>
    </div>
  );
}
