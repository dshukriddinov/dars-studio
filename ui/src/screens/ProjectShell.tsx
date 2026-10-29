// Dars sahifasi: sarlavha + 4 qadam (1 Fayllar va o'qituvchi, 2 Tayyorlash, 3 Ko'rib chiqish, 4 Eksport).
import { useEffect, useMemo, useState } from "react";
import { Check, FolderOpen, Play, RotateCw } from "lucide-react";
import { useStore, type Step } from "../store";
import { api, urls } from "../lib/api";
import * as E from "../lib/edits";
import { frameToSec, parseFps, type Fps } from "../lib/time";
import type { Job, Project as P } from "../lib/types";
import { LESSON_FIELDS, LowerThirdPreview, MetaFields, TEACHER_FIELDS, langLabel, useTeachers } from "../components/TeacherForm";
import { StepReview } from "./StepReview";

const projName = (path: string) => path.split(/[\\/]/).filter(Boolean).pop() ?? path;
const PREP: [string, string, string][] = [
  ["slides", "Slaydlar", "Taqdimot rasmga aylantiriladi"],
  ["audio", "Ovoz", "Shovqin tozalanadi, yoʻtal va aksa topiladi"],
  ["asr", "Nutq matni", "Oʻqituvchi soʻzlari vaqti bilan yoziladi"],
  ["eyecontact", "Koʻz kontakti", "Nigoh kameraga toʻgʻrilanadi"],
  ["sync", "Slaydlar vaqti", "Har slayd qachon koʻrinishi aniqlanadi"],
  ["cuts", "Kesish takliflari", "Pauza, takror, “mmm” va boshqalar topiladi"],
];
const STEP_LABELS: [Step, string][] = [[1, "Fayllar va oʻqituvchi"], [2, "Tayyorlash"], [3, "Koʻrib chiqish"], [4, "Eksport"]];

export function ProjectShell() {
  const name = useStore((s) => s.name);
  const view = useStore((s) => s.view);
  const jobs = useStore((s) => s.jobs);
  const step = useStore((s) => s.step);
  const stepFor = useStore((s) => s.stepFor);
  const { open, setStep } = useStore.getState();
  const mine = useMemo(() => Object.values(jobs).filter((j) => name && projName(j.project) === name), [jobs, name]);
  const doneKey = mine.filter((j) => j.status === "tayyor").map((j) => j.id).join(",");
  useEffect(() => { if (name && doneKey) void open(name); }, [doneKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // dars ochilganda mos qadam: tayyorlanmagan — 2, aks holda — 3
  const ready = !!view?.project.slide_spans.length;
  useEffect(() => { if (view && name && stepFor !== name) setStep(ready ? 3 : 2); }, [name, !!view]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!name) return <Empty text="Chapdan darsni tanlang yoki yangisini qoʻshing." />;
  if (!view) return <Empty text="Yuklanmoqda…" />;
  const p = view.project;
  const fps = parseFps(p.fps);
  const busy = mine.some((j) => j.status === "ishlanmoqda" || j.status === "navbatda");
  const exported = (p.exports?.length ?? 0) > 0;
  const done: Record<Step, boolean> = { 1: !!p.meta.oqituvchi, 2: ready && !busy, 3: exported, 4: exported };

  return (
    <div className="lesson-page">
      <header className="lesson-head">
        <div>
          <h1 className="display">{p.meta.mavzu || p.meta.fan || name}</h1>
          <p className="dim">{[p.meta.oqituvchi, p.meta.fan && p.meta.mavzu ? p.meta.fan : null,
            `${(frameToSec(p.total_frames, fps) / 60).toFixed(0)} daqiqa`, `${p.slides.length} slayd`]
            .filter(Boolean).join(", ")}</p>
        </div>
        <ol className="stepper" aria-label="Qadamlar">
          {STEP_LABELS.map(([s, label]) => (
            <li key={s}>
              <button className={`stp${step === s ? " on" : ""}${done[s] ? " done" : ""}`} onClick={() => setStep(s)}
                aria-current={step === s ? "step" : undefined}>
                <span className="stp-n">{done[s] && step !== s ? <Check size={14} /> : s}</span>{label}
              </button>
            </li>
          ))}
        </ol>
      </header>
      <div className="lesson-body">
        {step === 1 ? <StepFiles name={name} p={p} fps={fps} busy={busy} />
          : step === 2 ? <StepPrepare name={name} p={p} jobs={mine} />
            : step === 3 ? <StepReview name={name} p={p} />
              : <StepExport name={name} jobs={mine} />}
      </div>
    </div>
  );
}

const Empty = ({ text }: { text: string }) => <div className="empty"><p>{text}</p></div>;

/* 1. Fayllar va o'qituvchi */
function StepFiles({ name, p, fps, busy }: { name: string; p: P; fps: Fps; busy: boolean }) {
  const command = useStore.getState().command;
  const [meta, setMeta] = useState<Record<string, string>>(p.meta);
  useEffect(() => setMeta(p.meta), [p.meta]);
  const teachers = useTeachers();
  const keys = [...TEACHER_FIELDS, ...LESSON_FIELDS].map((f) => f.key);
  const dirty = keys.some((k) => (meta[k] ?? "") !== (p.meta[k] ?? ""));
  return (
    <div className="cols">
      <section className="block">
        <h2 className="h2">Dars boshidagi yozuv</h2>
        <MetaFields fields={TEACHER_FIELDS} meta={meta} onChange={setMeta} teachers={teachers} />
        <LowerThirdPreview template={p.template_id} meta={meta} />
        <MetaFields fields={LESSON_FIELDS} meta={meta} onChange={setMeta} />
        <div className="row">
          <button className="btn-primary" disabled={!dirty} onClick={() => void command("Oʻqituvchi maʼlumoti", {
            meta: { ...p.meta, ...Object.fromEntries(keys.map((k) => [k, (meta[k] ?? "").trim()])) },
          })}>Saqlash</button>
          {dirty ? <button className="btn-ghost" onClick={() => setMeta(p.meta)}>Bekor qilish</button> : null}
          <span className="caption dim">Keyingi eksportda qoʻllanadi</span>
        </div>
        <p className="caption dim">Dars tili: {langLabel(p.meta)} (yangi dars ochishda tanlanadi)</p>
      </section>
      <section className="block">
        <h2 className="h2">Video</h2>
        <Parts name={name} p={p} fps={fps} busy={busy} />
        <h2 className="h2" style={{ marginTop: 24 }}>Slaydlar</h2>
        <Slides name={name} p={p} />
      </section>
    </div>
  );
}

function Parts({ name, p, fps, busy }: { name: string; p: P; fps: Fps; busy: boolean }) {
  const { setView, fail } = useStore.getState();
  const [adding, setAdding] = useState(false);
  const parts = p.parts?.length ? p.parts : [{ path: p.name, start: 0, frames: p.total_frames }];
  const add = async () => {
    try {
      const { path } = await api.pickFile("video");
      if (!path) return;
      setAdding(true);
      const r = await api.addPart(name, path);
      setView({ project: r.project, can_undo: r.can_undo, can_redo: r.can_redo, undo_label: r.undo_label,
        redo_label: r.redo_label });
    } catch (e) { fail(e); } finally { setAdding(false); }
  };
  return (
    <div>
      <ul className="parts">
        {parts.map((x, i) => (
          <li key={i}><span className="part-n">{i + 1}</span><span className="ellipsis">{projName(x.path)}</span>
            <span className="dim">{(frameToSec(x.frames, fps) / 60).toFixed(1)} daq</span></li>
        ))}
      </ul>
      <button className="btn-secondary" disabled={busy || adding} onClick={() => void add()}>
        {adding ? "Ulanmoqda…" : "Davomini qoʻshish"}
      </button>
      <p className="caption dim">Dars keyingi faylda davom etgan boʻlsa. Qismlar ulanadi, takrorlangan joy kesiladi.</p>
    </div>
  );
}

function Slides({ name, p }: { name: string; p: P }) {
  const shown = new Set(p.slide_spans.map((s) => s.slide));
  const synced = p.slide_spans.length > 0;
  const missing = synced ? p.slides.filter((s) => !shown.has(s.index)) : [];
  const mismatch = E.slideMismatch(p);
  const { setView, fail } = useStore.getState();
  const replace = async () => {
    try {
      const { path } = await api.pickFile("slides");
      if (path) setView(await api.replaceSlides(name, path));
    } catch (e) { fail(e); }
  };
  return (
    <>
      <div className="row">
        <button className="btn-secondary sm" onClick={() => void replace()}
          title="Video boshqa taqdimot bilan yozilgan boʻlsa: slaydlar va ularning vaqti qayta tayyorlanadi, kesishlar saqlanadi">
          Taqdimotni almashtirish</button>
        <span className="caption dim ellipsis" title={p.assets.find((a) => a.kind === "pptx" || a.kind === "pdf")?.path}>
          {p.assets.find((a) => a.kind === "pptx" || a.kind === "pdf")?.path.split(/[\\/]/).pop()}</span>
      </div>
      {mismatch ? <p className="note warn strong">{mismatch}</p> : missing.length ? (
        <p className="note warn">Videoda koʻrsatilmagan: {missing.map((s) => s.index).join(", ")}-slayd.
          Oʻqituvchi ularni gapirmagan boʻlishi mumkin.</p>
      ) : null}
      <div className="slides-grid">
        {p.slides.map((s) => (
          <figure key={s.index} className={synced && !shown.has(s.index) ? "unshown" : ""}>
            <img src={urls.slide(name, s.index)} alt={`${s.index}-slayd`} loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.visibility = "hidden"; }} />
            <figcaption className="caption ellipsis" title={s.title}>{s.index}. {s.title.replace(/\v/g, " ")}</figcaption>
          </figure>
        ))}
      </div>
    </>
  );
}

/* 2. Tayyorlash */
function StepPrepare({ name, p, jobs }: { name: string; p: P; jobs: Job[] }) {
  const { setStep, fail, upsertJob } = useStore.getState();
  const latest = (t: string) => jobs.filter((j) => j.type === t).sort((a, b) => b.id - a.id)[0];
  const busy = jobs.some((j) => j.status === "ishlanmoqda" || j.status === "navbatda");
  const finished = PREP.every(([t]) => latest(t)?.status === "tayyor") || (!busy && p.slide_spans.length > 0);
  return (
    <section className="block narrow">
      <h2 className="h2">Avtomatik tayyorlash</h2>
      <p className="dim">20 daqiqalik dars uchun taxminan 10–15 daqiqa. Kompyuterni oʻchirmang, oynani yopsangiz ham ish
        davom etadi.</p>
      <ol className="prep">
        {PREP.map(([t, label, hint]) => {
          const j = latest(t);
          const st = j?.status ?? "kutilmoqda";
          return (
            <li key={t} className={`prep-row st-${st === "toʻxtatildi" ? "stop" : st}`}>
              <span className="prep-mark" aria-hidden />
              <div className="prep-text">
                <div className="strong">{label}</div>
                <div className="caption dim">{j?.status === "xato" ? friendlyError(j.error)
                  : st === "ishlanmoqda" && j ? `${Math.round(j.progress * 100)}%` : hint}</div>
                {st === "ishlanmoqda" && j ? <div className="bar"><div style={{ width: `${j.progress * 100}%` }} /></div> : null}
              </div>
              {j && (j.status === "xato" || j.status === "toʻxtatildi") ? (
                <button className="btn-secondary sm" onClick={() => api.resumeJob(j.id).then(upsertJob).catch(fail)}>
                  <RotateCw size={14} /> Qayta urinish</button>
              ) : null}
            </li>
          );
        })}
      </ol>
      <div className="row">
        {!busy && !finished ? (
          <button className="btn-primary" onClick={() => api.prepare(name).catch(fail)}><Play size={16} /> Tayyorlashni boshlash</button>
        ) : null}
        {finished ? <button className="btn-primary" onClick={() => setStep(3)}>Koʻrib chiqishga oʻtish</button> : null}
        {busy ? <span className="dim">Ishlanmoqda…</span> : null}
      </div>
    </section>
  );
}

/* 4. Eksport */
function StepExport({ name, jobs }: { name: string; jobs: Job[] }) {
  const fail = useStore.getState().fail;
  const [subtitles, setSubtitles] = useState(false);
  const [premiere, setPremiere] = useState(false);
  const [files, setFiles] = useState<{ file: string; size_mb: number; qa: unknown; version: number; mtime: number }[]>([]);
  const job = jobs.filter((j) => j.type === "export").sort((a, b) => b.id - a.id)[0];
  const running = job && (job.status === "ishlanmoqda" || job.status === "navbatda");
  useEffect(() => { api.exports(name).then(setFiles).catch(fail); }, [name, job?.status, fail]);
  const videos = files.filter((f) => f.file.endsWith(".mp4") && !f.file.includes("/premiere/"))
    .sort((a, b) => b.version - a.version);
  return (
    <div className="cols">
      <section className="block">
        <h2 className="h2">Tayyor video yaratish</h2>
        <p className="dim">Faqat “kesiladi” deb belgilangan joylar kesiladi. Intro, oʻqituvchi yozuvi va mualliflik matni
          shablondan qoʻshiladi.</p>
        <label className="check"><input type="checkbox" checked={subtitles} onChange={(e) => setSubtitles(e.target.checked)} />
          Subtitr fayli (SRT)</label>
        <label className="check"><input type="checkbox" checked={premiere} onChange={(e) => setPremiere(e.target.checked)} />
          Premiere / DaVinci uchun loyiha</label>
        <div className="row">
          <button className="btn-primary" disabled={!!running} onClick={async () => {
            try { await api.addJob(name, "export", { profile: "web", subtitles, premiere }); } catch (e) { fail(e); }
          }}>{running ? "Yaratilmoqda…" : "Videoni yaratish"}</button>
        </div>
        {running && job ? (
          <div><div className="bar"><div style={{ width: `${job.progress * 100}%` }} /></div>
            <p className="caption dim">{Math.round(job.progress * 100)}%</p></div>
        ) : null}
        {job?.status === "xato" ? <p className="note err">{friendlyError(job.error)}</p> : null}
      </section>
      <section className="block">
        <h2 className="h2">Tayyor videolar</h2>
        {!videos.length ? <p className="dim">Hali yoʻq. Chapdagi tugma bilan yarating.</p> : (
          <ul className="exports">
            {videos.map((f, i) => (
              <li key={f.file}>
                <div className="row"><span className="strong">{f.version}-versiya</span>
                  {i === 0 ? <span className="tag">eng soʻnggisi</span> : null}
                  <span className="caption dim">{new Date(f.mtime * 1000).toLocaleString("uz-UZ", { dateStyle: "short",
                    timeStyle: "short" })}, {Math.round(f.size_mb)} MB{qaVerdict(f.qa) ? `, tekshiruv: ${qaVerdict(f.qa)}` : ""}</span></div>
                <div className="caption dim ellipsis" title={f.file}>{f.file.split("/").pop()}</div>
                <div className="row">
                  <a className="btn-secondary sm" href={urls.file(name, f.file)} target="_blank" rel="noreferrer"><Play size={14} /> Koʻrish</a>
                  <button className="btn-secondary sm" onClick={() => api.reveal(name, f.file).catch(fail)}>
                    <FolderOpen size={14} /> Papkada koʻrsatish</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Vazifa xatosidan foydalanuvchiga tushunarli qator: "...Error: xabar" (traceback emas). */
export function friendlyError(err: string | null | undefined): string {
  if (!err) return "Nomaʼlum xato. Qayta urinib koʻring.";
  const lines = err.split(String.fromCharCode(10)).map((l) => l.trim()).filter(Boolean);
  const msg = [...lines].reverse().find((l) => /^[\w.]+(Error|Exception):/.test(l));
  return (msg ? msg.replace(/^[\w.]+(Error|Exception):\s*/, "") : lines[lines.length - 1]).slice(0, 400);
}

function qaVerdict(qa: unknown): string | null {
  const v = (qa as { verdict?: string } | null)?.verdict;
  return v === "ok" ? "yaxshi" : v === "ogohlantirish" ? "eslatmalar bor" : v === "xato" ? "xato bor" : null;
}
