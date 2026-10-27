// Yangi loyiha: video + slaydlar (Windows oynasidan tanlash), o'qituvchi ma'lumoti (lower-third) jonli ko'rinish bilan.
import { useEffect, useState } from "react";
import { FolderOpen } from "lucide-react";
import { useStore } from "../store";
import { api } from "../lib/api";
import { LESSON_FIELDS, LowerThirdPreview, MetaFields, TEACHER_FIELDS } from "../components/TeacherForm";

const DEFAULT_TEMPLATE = "akademiya";

export function NewProject() {
  const [video, setVideo] = useState("");
  const [more, setMore] = useState("");   // davomi (ikkinchi fayl), ixtiyoriy
  const [slides, setSlides] = useState("");
  const [name, setName] = useState("");
  const [templates, setTemplates] = useState<string[]>([]);
  const [template, setTemplate] = useState(DEFAULT_TEMPLATE);
  const [meta, setMeta] = useState<Record<string, string>>({});
  const [prepare, setPrepare] = useState(true);
  const [busy, setBusy] = useState(false);
  const { open, fail } = useStore.getState();

  useEffect(() => {
    api.templates().then((t) => {
      setTemplates(t);
      if (t.length && !t.includes(template)) setTemplate(t.includes(DEFAULT_TEMPLATE) ? DEFAULT_TEMPLATE : t[0]);
    }).catch(fail);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pick = async (kind: "video" | "more" | "slides") => {
    try {
      const { path } = await api.pickFile(kind === "more" ? "video" : kind);
      if (path) ({ video: setVideo, more: setMore, slides: setSlides }[kind])(path);
    } catch (e) { fail(e); }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const strip = (s: string) => s.trim().replace(/^"|"$/g, "");
      const r = await api.createProject({
        video: strip(video), more_videos: more.trim() ? [strip(more)] : [], slides: strip(slides), template, name: name.trim() || null, prepare,
        meta: Object.fromEntries(Object.entries(meta).map(([k, v]) => [k, v.trim()]).filter(([, v]) => v)),
      });
      await open(r.name, "project");
    } catch (err) { fail(err); } finally { setBusy(false); }
  };

  return (
    <form className="page" onSubmit={submit}>
      <section className="panel form">
        <h2 className="heading">1. Fayllar</h2>
        <PathField label="Video (oʻqituvchi, yashil fon)" value={video} onChange={setVideo}
          onPick={() => void pick("video")} placeholder="D:\darslar\dars01.mp4" />
        <PathField label="Davomi — dars ikkinchi faylda davom etgan boʻlsa (ixtiyoriy)" value={more} onChange={setMore}
          onPick={() => void pick("more")} placeholder="D:\darslar\dars01_2.mp4" optional />
        <PathField label="Taqdimot (PPTX yoki PDF)" value={slides} onChange={setSlides}
          onPick={() => void pick("slides")} placeholder="D:\darslar\dars01.pptx" />
        <div className="grid2">
          <label className="field">
            <span className="label">Shablon (studiya)</span>
            <select value={template} onChange={(e) => setTemplate(e.target.value)}>
              {templates.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="label">Loyiha nomi (ixtiyoriy)</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Fayl nomidan olinadi" />
          </label>
        </div>
      </section>

      <section className="panel form">
        <h2 className="heading">2. Oʻqituvchi (dars boshidagi yozuv)</h2>
        <MetaFields fields={TEACHER_FIELDS} meta={meta} onChange={setMeta} />
        <LowerThirdPreview template={template} meta={meta} />
      </section>

      <section className="panel form">
        <h2 className="heading">3. Dars</h2>
        <MetaFields fields={LESSON_FIELDS} meta={meta} onChange={setMeta} />
        <label className="check body">
          <input type="checkbox" checked={prepare} onChange={(e) => setPrepare(e.target.checked)} />
          Darhol tayyorlash (shovqin tozalash, nutqni matnga aylantirish, slayd sinxroni, kesish takliflari, Eye Contact)
        </label>
        <div>
          <button className="btn-primary" disabled={busy || !video || !slides || !meta.oqituvchi?.trim()}>
            {busy ? "Import qilinmoqda…" : "Loyihani yaratish"}
          </button>
        </div>
      </section>
    </form>
  );
}

function PathField({ label, value, onChange, onPick, placeholder, optional }: {
  label: string; value: string; onChange: (v: string) => void; onPick: () => void; placeholder: string;
  optional?: boolean;
}) {
  return (
    <label className="field">
      <span className="label">{label}{optional ? "" : " *"}</span>
      <span className="pick">
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} required={!optional} />
        <button type="button" className="btn-secondary" onClick={onPick}><FolderOpen size={16} /> Tanlash</button>
      </span>
    </label>
  );
}
