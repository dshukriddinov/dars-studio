// Chap panel: darslar ro'yxati (holati bilan), yangi dars, navbat holati, sozlamalar.
import { useEffect, useMemo, useState } from "react";
import { Plus, Settings as Gear } from "lucide-react";
import { useStore } from "../store";
import { api } from "../lib/api";
import type { ProjectSummary } from "../lib/types";

const projName = (path: string) => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

export function Sidebar() {
  const tab = useStore((s) => s.tab);
  const name = useStore((s) => s.name);
  const jobs = useStore((s) => s.jobs);
  const { open, setTab, fail } = useStore.getState();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const finished = Object.values(jobs).filter((j) => j.status === "tayyor").length;

  useEffect(() => { api.projects().then(setProjects).catch(fail); }, [finished, name, fail]);

  const running = useMemo(() => Object.values(jobs).filter((j) => j.status === "ishlanmoqda"), [jobs]);
  const waiting = Object.values(jobs).filter((j) => j.status === "navbatda").length;
  const busyOf = (p: string) => Object.values(jobs).some((j) => projName(j.project) === p
    && (j.status === "ishlanmoqda" || j.status === "navbatda"));

  return (
    <aside className="sidebar">
      <div className="brand">Dars Studio</div>
      <button className="btn-primary new-lesson" onClick={() => setTab("new")}><Plus size={16} /> Yangi dars</button>
      <nav className="lessons" aria-label="Darslar">
        {projects === null ? <p className="caption dim pad">Yuklanmoqda…</p> : !projects.length
          ? <p className="caption dim pad">Hali dars yoʻq. Birinchisini “Yangi dars” bilan qoʻshing.</p>
          : projects.map((p) => (
            <button key={p.name} className={`lesson${name === p.name && tab !== "new" && tab !== "settings" ? " on" : ""}`}
              onClick={() => void open(p.name, "project")}>
              <span className="lesson-title ellipsis">{p.meta.mavzu || p.meta.fan || p.name}</span>
              <span className="lesson-sub ellipsis">{p.meta.oqituvchi || p.name}</span>
              {busyOf(p.name) ? <span className="lesson-dot" title="Ishlanmoqda" /> : null}
            </button>
          ))}
      </nav>
      <div className="sidebar-foot">
        <div className="caption dim queue-line">
          {running.length ? `Ishlanmoqda: ${running.map((j) => j.type).join(", ")}${waiting ? `, navbatda ${waiting}` : ""}`
            : waiting ? `Navbatda: ${waiting}` : "Navbat boʻsh"}
        </div>
        <button className={`btn-ghost${tab === "settings" ? " on" : ""}`} onClick={() => setTab("settings")}>
          <Gear size={16} /> Sozlamalar
        </button>
      </div>
    </aside>
  );
}
