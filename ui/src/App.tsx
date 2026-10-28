import { useEffect, useState } from "react";
import { ArrowLeft, X } from "lucide-react";
import { connectJobs, useStore } from "./store";
import { api } from "./lib/api";
import type { DoctorCheck } from "./lib/types";
import { Sidebar } from "./components/Sidebar";
import { NewProject } from "./screens/NewProject";
import { ProjectShell } from "./screens/ProjectShell";
import { Review } from "./screens/Review";
import { KeyCalib } from "./screens/KeyCalib";
import { TemplateCalib } from "./screens/TemplateCalib";
import { Settings } from "./screens/Settings";

export function App() {
  const tab = useStore((s) => s.tab);
  const error = useStore((s) => s.error);
  const notice = useStore((s) => s.notice);
  const { clearError, setTab, setStep } = useStore.getState();
  useEffect(() => connectJobs(), []);
  // to'g'ridan havola: ?dars=NOM&qadam=3, ?dars=NOM&batafsil (yoki ?yangi)
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const d = q.get("dars");
    if (q.has("yangi")) setTab("new");
    else if (d) {
      const s = Number(q.get("qadam"));
      void useStore.getState().open(d, q.has("batafsil") ? "review" : "project");
      if (s >= 1 && s <= 4) useStore.setState({ step: s as 1 | 2 | 3 | 4, stepFor: d });
    }
  }, [setTab, setStep]);
  // eski ichki havolalar (setTab("export") va h.k.) yangi tuzilishga
  useEffect(() => {
    if (tab === "export") setStep(4);
    else if (tab === "home") setTab("project");
  }, [tab, setStep, setTab]);

  const main = tab === "new" ? <NewProject />
    : tab === "settings" || tab === "key" || tab === "template" ? <SettingsPage initial={tab} />
      : tab === "review" ? <DetailedEdit /> : <ProjectShell />;

  return (
    <div className="shell">
      <Sidebar />
      <main className="main">
        {error ? (
          <div className="toast err" role="alert">
            <span>{error}</span>
            <button className="btn-ghost sm" onClick={clearError} aria-label="Yopish"><X size={16} /></button>
          </div>
        ) : notice ? <div className="toast ok" role="status">{notice}</div> : null}
        {main}
      </main>
    </div>
  );
}

function DetailedEdit() {
  const setStep = useStore.getState().setStep;
  return (
    <div className="detailed">
      <div className="detailed-bar">
        <button className="btn-ghost" onClick={() => setStep(3)}><ArrowLeft size={16} /> Koʻrib chiqishga qaytish</button>
        <span className="dim">Batafsil tahrir: slayd chegaralari, sahnalar, kesishlarni kadrgacha surish</span>
      </div>
      <Review />
    </div>
  );
}

const SETTINGS: [string, string][] = [["general", "Umumiy"], ["key", "Yashil fon"], ["template", "Studiya shabloni"],
  ["system", "Tizim holati"]];

function SettingsPage({ initial }: { initial: string }) {
  const [sub, setSub] = useState(initial === "key" || initial === "template" ? initial : "general");
  return (
    <div className="settings-page">
      <h1 className="display">Sozlamalar</h1>
      <div className="chips" role="tablist">
        {SETTINGS.map(([k, l]) => (
          <button key={k} role="tab" aria-selected={sub === k} className={`chip${sub === k ? " on" : ""}`}
            onClick={() => setSub(k)}>{l}</button>
        ))}
      </div>
      {sub === "general" ? <Settings /> : sub === "key" ? <KeyCalib /> : sub === "template" ? <TemplateCalib />
        : <SystemCheck />}
    </div>
  );
}

function SystemCheck() {
  const [checks, setChecks] = useState<DoctorCheck[] | null>(null);
  useEffect(() => { api.doctor().then(setChecks).catch(() => setChecks([])); }, []);
  if (!checks) return <p className="dim">Tekshirilmoqda…</p>;
  return (
    <ul className="checks">
      {checks.map((c) => (
        <li key={c.name} className={`chk ${c.status === "ok" ? "ok" : c.status === "xato" ? "err" : "warn"}`}>
          <span className="strong">{c.name}</span><span>{c.detail}</span>
          {c.fix && c.status !== "ok" ? <span className="caption dim">{c.fix}</span> : null}
        </li>
      ))}
    </ul>
  );
}
