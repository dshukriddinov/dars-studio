import { useEffect, useState } from "react";
import { AlertTriangle, Info } from "lucide-react";
import { useStore } from "../store";
import { api } from "../lib/api";
import type { DoctorCheck, Job, JobStatus, ProjectSummary } from "../lib/types";
import { ProgressBar, StatusBadge } from "../components/StatusBadge";

const ORDER: JobStatus[] = ["ishlanmoqda", "navbatda", "toʻxtatildi", "xato", "tayyor"];
const projName = (path: string) => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

export function Home() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [doctor, setDoctor] = useState<DoctorCheck[]>([]);
  const jobs = useStore((s) => s.jobs);
  const { open, fail } = useStore.getState();

  useEffect(() => {
    api.projects().then(setProjects).catch(fail);
    api.doctor().then(setDoctor).catch(() => undefined);
  }, [fail]);

  const queue = Object.values(jobs).sort((a, b) =>
    ORDER.indexOf(a.status) - ORDER.indexOf(b.status) || b.created - a.created).slice(0, 50);

  return (
    <div className="page">
      <DoctorBanner checks={doctor} />
      <section className="panel">
        <h2 className="heading">Loyihalar</h2>
        {projects === null ? <p className="caption dim">Yuklanmoqda…</p> : !projects.length
          ? <p className="body dim">Loyiha yoʻq. “Yangi loyiha” boʻlimidan qoʻshing.</p> : (
            <ul className="list">
              {projects.map((p) => (
                <li key={p.name}>
                  <button className="row-btn" onClick={() => void open(p.name, "review")}>
                    <span className="body-strong">{p.name}</span>
                    <span className="caption dim">
                      {[p.meta.fan, p.meta.mavzu].filter(Boolean).join(" · ")} {p.slides} slayd · {p.total_frames} kadr
                    </span>
                    <span className="badges">
                      {ORDER.filter((s) => p.jobs[s]).map((s) => (
                        <span key={s} className="caption"><StatusBadge status={s} /> {p.jobs[s]}</span>
                      ))}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
      </section>
      <section className="panel">
        <h2 className="heading">Navbat</h2>
        {queue.length ? <div className="queue">{queue.map((j) => <QueueRow key={j.id} job={j} />)}</div>
          : <p className="caption dim">Navbat boʻsh</p>}
      </section>
    </div>
  );
}

export function QueueRow({ job }: { job: Job }) {
  const { upsertJob, fail } = useStore.getState();
  const act = (fn: (id: number) => Promise<Job>) => fn(job.id).then(upsertJob).catch(fail);
  return (
    <div className="qrow">
      <div className="qtop">
        <div>
          <div className="body-strong">{job.type} <span className="caption dim">#{job.id}</span></div>
          <div className="caption dim">{projName(job.project)}{job.message ? ` · ${job.message}` : ""}</div>
        </div>
        <StatusBadge status={job.status} progress={job.progress} />
        {job.status === "navbatda" || job.status === "ishlanmoqda"
          ? <button className="btn-secondary sm" onClick={() => act(api.stopJob)}>Toʻxtatish</button> : null}
        {job.status === "toʻxtatildi" || job.status === "xato"
          ? <button className="btn-secondary sm" onClick={() => act(api.resumeJob)}>Davom ettirish</button> : null}
      </div>
      {job.status !== "tayyor" ? <ProgressBar status={job.status} progress={job.progress} /> : null}
      {job.error ? <div className="caption danger">{job.error}</div> : null}
    </div>
  );
}

export function DoctorBanner({ checks }: { checks: DoctorCheck[] }) {
  const bad = checks.filter((c) => c.status !== "ok");
  if (!bad.length) return null;
  return (
    <div className="banners">
      {bad.map((c) => (
        <div key={c.name} className={`banner ${c.status === "xato" ? "banner-error" : "banner-notice"}`}>
          {c.status === "xato" ? <AlertTriangle size={20} /> : <Info size={20} />}
          <div>
            <div className="body-strong title">{c.name}: {c.detail}</div>
            {c.fix ? <div className="body">{c.fix}</div> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
