// Loyiha sahifasi: tayyorlash bosqichlari, o'qituvchi ma'lumoti (tahrir + ko'rinish), slaydlar (ko'rsatilmaganlari
// belgilanadi), kesish takliflari turlari bo'yicha (tasdiqlash / rad etish).
import { useEffect, useMemo, useState } from "react";
import { useStore } from "../store";
import { api, urls } from "../lib/api";
import { frameToSec, parseFps, type Fps } from "../lib/time";
import type { CutProposal, Job, Project as P } from "../lib/types";
import { ProgressBar, StatusBadge } from "../components/StatusBadge";
import { LowerThirdPreview, MetaFields, TEACHER_FIELDS, LESSON_FIELDS } from "../components/TeacherForm";

const STEPS: [string, string][] = [
  ["slides", "Slaydlar"], ["audio", "Ovoz (shovqin, yoʻtal)"], ["asr", "Nutq → matn"], ["eyecontact", "Eye Contact"],
  ["sync", "Slayd sinxroni"], ["cuts", "Kesish takliflari"], ["export", "Eksport"],
];
export const CUT_KINDS: Record<CutProposal["reason"], string> = {
  pause: "Uzun pauzalar", manual: "Qoʻlda", bosh: "Dars boshi (salomgacha)", oxir: "Dars oxiri (xayrlashuvdan keyin)",
  "yo'tal": "Yoʻtal, tomoq qirish", aksa: "Aksa", "to'ldiruvchi": "“mmm/eee” oʻylab turish", takror: "Takror va qayta aytish",
  qism: "Video qismlari ulanishi",
};
const projName = (path: string) => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

export function Project() {
  const name = useStore((s) => s.name);
  const view = useStore((s) => s.view);
  const jobs = useStore((s) => s.jobs);
  const { open } = useStore.getState();
  const mine = useMemo(() => Object.values(jobs).filter((j) => name && projName(j.project) === name), [jobs, name]);
  const doneKey = mine.filter((j) => j.status === "tayyor").map((j) => j.id).join(",");

  // bosqich tugaganda (sinxron, kesish…) loyiha holatini qayta o'qish
  useEffect(() => { if (name && doneKey) void open(name); }, [doneKey]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!name) return <div className="pad body dim">Loyiha tanlanmagan. Bosh sahifadan oching yoki yangisini yarating.</div>;
  if (!view) return <div className="pad body dim">Yuklanmoqda…</div>;
  return <Body name={name} p={view.project} jobs={mine} />;
}

function Body({ name, p, jobs }: { name: string; p: P; jobs: Job[] }) {
  const { setTab, fail } = useStore.getState();
  const fps = parseFps(p.fps);
  const latest = (type: string) => jobs.filter((j) => j.type === type).sort((a, b) => b.id - a.id)[0];
  const preparing = jobs.some((j) => j.status === "navbatda" || j.status === "ishlanmoqda");
  const minutes = (frameToSec(p.total_frames, fps) / 60).toFixed(1);

  return (
    <div className="page">
      <section className="panel">
        <div className="toolbar">
          <h2 className="heading" style={{ margin: 0 }}>{name}</h2>
          <span className="caption dim">{p.meta.oqituvchi ?? ""} · {p.slides.length} slayd · {minutes} daq · shablon {p.template_id}</span>
          <span className="spacer" />
          <button className="btn-secondary" onClick={() => setTab("review")}>Tekshirish</button>
          <button className="btn-primary" onClick={() => setTab("export")}>Eksport</button>
        </div>
        <div className="steps">
          {STEPS.map(([t, label]) => {
            const j = latest(t);
            return (
              <div key={t} className="qrow" style={{ minWidth: 150, flex: 1 }}>
                <div className="body-strong">{label}</div>
                {j ? <StatusBadge status={j.status} progress={j.progress} /> : <span className="caption dim">—</span>}
                {j && j.status === "ishlanmoqda" ? <ProgressBar status={j.status} progress={j.progress} /> : null}
                {j?.error ? <div className="caption danger">{j.error}</div> : null}
              </div>
            );
          })}
        </div>
        <PartsRow name={name} p={p} fps={fps} busy={preparing} />
        {!preparing && !latest("cuts") ? (
          <div style={{ marginTop: 12 }}>
            <button className="btn-secondary" onClick={() => api.prepare(name).catch(fail)}>Tayyorlashni boshlash</button>
          </div>
        ) : null}
      </section>

      <TeacherPanel p={p} />
      <CutsPanel p={p} fps={fps} />
      <SlidesPanel name={name} p={p} />
    </div>
  );
}

function PartsRow({ name, p, fps, busy }: { name: string; p: P; fps: Fps; busy: boolean }) {
  const { setView, fail } = useStore.getState();
  const [adding, setAdding] = useState(false);
  const parts = p.parts?.length ? p.parts : null;
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
    <div className="toolbar" style={{ marginTop: 12, marginBottom: 0 }}>
      <span className="caption dim">
        {parts ? `Video ${parts.length} qismdan: ` + parts.map((x, i) =>
          `${i + 1}) ${projName(x.path)} — ${(frameToSec(x.frames, fps) / 60).toFixed(1)} daq`).join(", ")
          : "Video bitta fayldan."}
      </span>
      <button className="btn-secondary sm" disabled={busy || adding} onClick={() => void add()}
        title="Dars keyingi faylda davom etgan bo‘lsa: qismlar ulanadi, tahlil qayta bajariladi">
        {adding ? "Ulanmoqda…" : "Davomini qoʻshish"}
      </button>
    </div>
  );
}

function TeacherPanel({ p }: { p: P }) {
  const command = useStore.getState().command;
  const [meta, setMeta] = useState<Record<string, string>>(p.meta);
  useEffect(() => setMeta(p.meta), [p.meta]);
  const keys = [...TEACHER_FIELDS, ...LESSON_FIELDS].map((f) => f.key);
  const dirty = keys.some((k) => (meta[k] ?? "") !== (p.meta[k] ?? ""));
  return (
    <section className="panel form">
      <h2 className="heading">Oʻqituvchi va dars</h2>
      <MetaFields fields={TEACHER_FIELDS} meta={meta} onChange={setMeta} />
      <LowerThirdPreview template={p.template_id} meta={meta} />
      <MetaFields fields={LESSON_FIELDS} meta={meta} onChange={setMeta} />
      <div className="toolbar" style={{ margin: 0 }}>
        <button className="btn-primary" disabled={!dirty}
          onClick={() => void command("Oʻqituvchi maʼlumoti", {
            meta: { ...p.meta, ...Object.fromEntries(keys.map((k) => [k, (meta[k] ?? "").trim()])) },
          })}>Saqlash</button>
        {dirty ? <button className="btn-ghost" onClick={() => setMeta(p.meta)}>Bekor qilish</button> : null}
        <span className="caption dim">Oʻzgarish keyingi eksportda qoʻllanadi</span>
      </div>
    </section>
  );
}

function CutsPanel({ p, fps }: { p: P; fps: Fps }) {
  const command = useStore.getState().command;
  const groups = useMemo(() => {
    const g = new Map<CutProposal["reason"], CutProposal[]>();
    for (const c of p.cuts) g.set(c.reason, [...(g.get(c.reason) ?? []), c]);
    return [...g.entries()];
  }, [p.cuts]);
  const total = frameToSec(p.cuts.filter((c) => c.status === "tasdiqlangan").reduce((s, c) => s + c.end - c.start, 0), fps);
  const setStatus = (reason: CutProposal["reason"], status: CutProposal["status"]) =>
    void command(`${CUT_KINDS[reason]}: ${status === "tasdiqlangan" ? "tasdiqlash" : "rad etish"}`, {
      cuts: p.cuts.map((c) => (c.reason === reason ? { ...c, status } : c)),
    });
  return (
    <section className="panel">
      <div className="toolbar">
        <h2 className="heading" style={{ margin: 0 }}>Kesishlar</h2>
        <span className="caption dim">tasdiqlangan: {total.toFixed(1)} s qisqaradi</span>
      </div>
      {!groups.length ? <p className="caption dim">Takliflar hali yoʻq (tayyorlash tugagach paydo boʻladi).</p> : (
        <div className="cut-groups">
          {groups.map(([reason, cs]) => {
            const ok = cs.filter((c) => c.status === "tasdiqlangan").length;
            const sec = frameToSec(cs.reduce((s, c) => s + c.end - c.start, 0), fps);
            return (
              <div key={reason} className="cut-group">
                <span className="body-strong">{CUT_KINDS[reason]}</span>
                <span className="caption dim">{cs.length} ta · {sec.toFixed(1)} s · tasdiqlangan {ok}</span>
                <button className="btn-secondary sm" disabled={ok === cs.length}
                  onClick={() => setStatus(reason, "tasdiqlangan")}>Hammasini kesish</button>
                <button className="btn-ghost sm" disabled={cs.every((c) => c.status === "rad_etilgan")}
                  onClick={() => setStatus(reason, "rad_etilgan")}>Qoldirish</button>
              </div>
            );
          })}
        </div>
      )}
      <p className="caption dim hint">Har bir joyni alohida koʻrish va oʻzgartirish — “Tekshirish” boʻlimida.</p>
    </section>
  );
}

function SlidesPanel({ name, p }: { name: string; p: P }) {
  const shown = new Set(p.slide_spans.map((s) => s.slide));
  const unshown = p.slide_spans.length ? p.slides.filter((s) => !shown.has(s.index)) : [];
  return (
    <section className="panel">
      <div className="toolbar">
        <h2 className="heading" style={{ margin: 0 }}>Slaydlar</h2>
        {unshown.length ? (
          <span className="caption danger">Videoda koʻrsatilmagan: {unshown.map((s) => s.index).join(", ")} — oʻqituvchi
            gapirmagan boʻlishi mumkin; kerak boʻlsa “Tekshirish”da qoʻshing.</span>
        ) : null}
      </div>
      <div className="slides-grid">
        {p.slides.map((s) => (
          <figure key={s.index} className={p.slide_spans.length && !shown.has(s.index) ? "unshown" : ""}>
            <img src={urls.slide(name, s.index)} alt={`${s.index}-slayd`} loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.visibility = "hidden"; }} />
            <figcaption className="caption ellipsis" title={s.title}>
              {s.index}. {s.title.replace(/\v/g, " ")}{p.slide_spans.length && !shown.has(s.index) ? " · videoda yoʻq" : ""}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
