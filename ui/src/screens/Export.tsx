import { useEffect, useState } from "react";
import { useStore } from "../store";
import { api, urls } from "../lib/api";
import { QueueRow } from "./Home";

export function Export() {
  const name = useStore((s) => s.name);
  const jobs = useStore((s) => s.jobs);
  const fail = useStore.getState().fail;
  const [profile, setProfile] = useState("web");
  const [subtitles, setSubtitles] = useState(false);
  const [premiere, setPremiere] = useState(false);
  const [files, setFiles] = useState<{ file: string; size_mb: number; qa: unknown }[]>([]);
  const [jobId, setJobId] = useState<number | null>(null);
  const job = jobId !== null ? jobs[jobId] : undefined;

  useEffect(() => { if (name) api.exports(name).then(setFiles).catch(fail); }, [name, job?.status, fail]);
  if (!name) return <div className="pad body dim">Loyiha tanlanmagan.</div>;

  return (
    <div className="page">
      <section className="panel">
        <h2 className="heading">Eksport</h2>
        <div className="toolbar">
          <label className="label">Profil</label>
          <select value={profile} onChange={(e) => setProfile(e.target.value)}>
            <option value="web">web (H.264 8 Mbit/s)</option>
            <option value="arxiv">arxiv (H.264 cq 19)</option>
          </select>
          <label className="check body">
            <input type="checkbox" checked={subtitles} onChange={(e) => setSubtitles(e.target.checked)} /> Subtitr (SRT)
          </label>
          <label className="check body">
            <input type="checkbox" checked={premiere} onChange={(e) => setPremiere(e.target.checked)} />
            Premiere/DaVinci paketi
          </label>
          <button className="btn-primary" onClick={async () => {
            try { setJobId((await api.addJob(name, "export", { profile, subtitles, premiere })).id); } catch (e) { fail(e); }
          }}>Boshlash</button>
        </div>
        <p className="caption dim">Natija: exports/vN/ — MP4 (intro va outro bilan), slaydlar jadvali, QA hisobot.
          Faqat tasdiqlangan kesishlar qoʻllanadi.</p>
        {job ? <QueueRow job={job} /> : null}
      </section>
      <section className="panel">
        <h2 className="heading">Fayllar</h2>
        {files.length ? (
          <ul className="list">
            {files.map((f) => (
              <li key={f.file} className="qrow">
                <a href={urls.file(name, f.file)} target="_blank" rel="noreferrer" className="body-strong">{f.file}</a>
                <span className="caption dim"> · {f.size_mb} MB</span>
                {f.qa ? <details><summary className="caption">QA hisobot</summary><pre className="code">{JSON.stringify(f.qa, null, 2)}</pre></details> : null}
              </li>
            ))}
          </ul>
        ) : <p className="caption dim">Eksport yoʻq</p>}
      </section>
    </div>
  );
}
