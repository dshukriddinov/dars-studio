import { useEffect, useState } from "react";
import { useStore } from "../store";
import { api } from "../lib/api";

const META: [string, string][] = [["fan", "Fan"], ["mavzu", "Mavzu"], ["oqituvchi", "Oʻqituvchi"], ["dars", "Dars raqami"]];

export function NewProject() {
  const [video, setVideo] = useState("");
  const [slides, setSlides] = useState("");
  const [name, setName] = useState("");
  const [templates, setTemplates] = useState<string[]>([]);
  const [template, setTemplate] = useState("demo");
  const [meta, setMeta] = useState<Record<string, string>>({});
  const [prepare, setPrepare] = useState(true);
  const [busy, setBusy] = useState(false);
  const { open, fail } = useStore.getState();

  useEffect(() => { api.templates().then((t) => { setTemplates(t); if (t.length && !t.includes(template)) setTemplate(t[0]); }).catch(fail); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const strip = (s: string) => s.trim().replace(/^"|"$/g, "");
      const r = await api.createProject({
        video: strip(video), slides: strip(slides), template, name: name.trim() || null, prepare,
        meta: Object.fromEntries(Object.entries(meta).filter(([, v]) => v.trim())),
      });
      await open(r.name, prepare ? "home" : "review");
    } catch (err) { fail(err); } finally { setBusy(false); }
  };

  return (
    <form className="page panel form" onSubmit={submit}>
      <h2 className="heading">Yangi loyiha</h2>
      <Field label="Video fayl yoʻli" value={video} onChange={setVideo} placeholder="D:\darslar\dars01.mp4" required />
      <Field label="Slaydlar (PPTX yoki PDF) yoʻli" value={slides} onChange={setSlides} placeholder="D:\darslar\dars01.pptx" required />
      <Field label="Loyiha nomi (ixtiyoriy)" value={name} onChange={setName} />
      <label className="field">
        <span className="label">Shablon</span>
        <select value={template} onChange={(e) => setTemplate(e.target.value)}>
          {templates.map((t) => <option key={t}>{t}</option>)}
        </select>
      </label>
      <div className="grid2">
        {META.map(([k, l]) => (
          <Field key={k} label={l} value={meta[k] ?? ""} onChange={(v) => setMeta({ ...meta, [k]: v })} />
        ))}
      </div>
      <label className="check body">
        <input type="checkbox" checked={prepare} onChange={(e) => setPrepare(e.target.checked)} />
        Tekshiruvgacha tayyorlash
      </label>
      <div><button className="btn-primary" disabled={busy || !video || !slides}>{busy ? "Ishlanmoqda…" : "Boshlash"}</button></div>
    </form>
  );
}

function Field({ label, value, onChange, ...rest }: { label: string; value: string; onChange: (v: string) => void } &
  Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value">) {
  return (
    <label className="field">
      <span className="label">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} {...rest} />
    </label>
  );
}
