// O'qituvchi ma'lumoti (dars boshidagi lower-third) + jonli ko'rinish. Yangi loyiha va Loyiha sahifasida.
import { useEffect, useState } from "react";
import { api } from "../lib/api";

export const TEACHER_FIELDS: { key: string; label: string; hint: string; required?: boolean }[] = [
  { key: "oqituvchi", label: "Ism familiya (sharifi bilan)", hint: "Asadov Shavkat Gʻaybullayevich", required: true },
  { key: "ish_joyi", label: "Ish joyi", hint: "Gumanitar va ijtimoiy fanlar maktabi" },
  { key: "lavozim", label: "Lavozimi", hint: "professori" },
  { key: "ilmiy_unvon", label: "Ilmiy darajasi / unvoni (ixtiyoriy)", hint: "Yuridik fanlari doktori" },
];
export const LESSON_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: "fan", label: "Fan", hint: "Mahalliy boshqaruv" },
  { key: "mavzu", label: "Mavzu", hint: "Vakillik organlarini shakllantirish" },
  { key: "dars", label: "Dars raqami", hint: "5" },
];

/** Dars tili (meta.til): nutqni tanish modeli shunga qarab tanlanadi. */
export const LANGS: [string, string][] = [["uz", "Oʻzbek tili"], ["en", "Ingliz tili"]];
export const langLabel = (m: Record<string, string>) => (LANGS.find(([k]) => k === m.til) ?? LANGS[0])[1];

export function LangField({ meta, onChange }: { meta: Record<string, string>; onChange: (m: Record<string, string>) => void }) {
  return (
    <label className="field">
      <span className="label">Dars tili (oʻqituvchi nutqi)</span>
      <select value={meta.til ?? "uz"} onChange={(e) => onChange({ ...meta, til: e.target.value })}>
        {LANGS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      <span className="caption dim">Ingliz tili: orada oʻzbekcha soʻzlar boʻlsa ham shu tanlansin</span>
    </label>
  );
}

/** Avvalgi darslardagi o'qituvchilar: ism -> o'qituvchi maydonlari (+ fan). Bir ism bir necha darsda bo'lsa —
 * ro'yxatdagi oxirgisi (bo'sh qiymatlar oldingisini o'chirmaydi). */
export function teachersFrom(projects: { meta: Record<string, string> }[]): Map<string, Record<string, string>> {
  const out = new Map<string, Record<string, string>>();
  for (const { meta } of projects) {
    const name = meta.oqituvchi?.trim();
    if (!name) continue;
    const prev = out.get(name) ?? {};
    const keep = Object.fromEntries([...TEACHER_FIELDS.map((f) => f.key), "fan"]
      .map((k) => [k, meta[k]?.trim() || prev[k] || ""]).filter(([, v]) => v));
    out.set(name, keep);
  }
  return out;
}

export function useTeachers(): Map<string, Record<string, string>> {
  const [t, setT] = useState<Map<string, Record<string, string>>>(new Map());
  useEffect(() => { api.projects().then((ps) => setT(teachersFrom(ps))).catch(() => undefined); }, []);
  return t;
}

/** Ism ro'yxatdagi o'qituvchiga to'liq mos kelsa — qolgan o'qituvchi maydonlari undan, fan esa bo'sh bo'lsa. */
export function fillTeacher(meta: Record<string, string>, teachers: Map<string, Record<string, string>>) {
  const t = teachers.get(meta.oqituvchi?.trim() ?? "");
  if (!t) return meta;
  const { fan, ...rest } = t;
  return { ...meta, ...rest, ...(fan && !meta.fan?.trim() ? { fan } : {}) };
}

/** Kiritishda oddiy apostrofni oʻ/gʻ uchun U+02BB ga almashtiradi (CLAUDE.md 10-qoida). */
export const fixOkina = (s: string) => s.replace(/([OoGg])['’‘`]/g, "$1ʻ");

export function MetaFields({ fields, meta, onChange, teachers }: {
  fields: { key: string; label: string; hint: string; required?: boolean }[];
  meta: Record<string, string>; onChange: (m: Record<string, string>) => void;
  teachers?: Map<string, Record<string, string>>;   // ism maydonida taklif va avtomatik to'ldirish
}) {
  return (
    <div className="grid2">
      {fields.map((f) => (
        <label key={f.key} className="field">
          <span className="label">{f.label}{f.required ? " *" : ""}</span>
          <input value={meta[f.key] ?? ""} placeholder={f.hint} required={f.required}
            list={teachers && f.key === "oqituvchi" ? "known-teachers" : undefined} autoComplete="off"
            onChange={(e) => {
              const next = { ...meta, [f.key]: fixOkina(e.target.value) };
              onChange(teachers && f.key === "oqituvchi" ? fillTeacher(next, teachers) : next);
            }} />
        </label>
      ))}
      {teachers?.size ? (
        <datalist id="known-teachers">
          {[...teachers].map(([n, t]) => <option key={n} value={n}>{[t.lavozim, t.ish_joyi].filter(Boolean).join(", ")}</option>)}
        </datalist>
      ) : null}
    </div>
  );
}

/** Lower-third ko'rinishi: kiritish to'xtagandan 400 ms keyin yangilanadi. */
export function LowerThirdPreview({ template, meta }: { template: string; meta: Record<string, string> }) {
  // maket (2026-10-29): chapda aksent chiziq, o'ng yuqorida shablon belgisi
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const key = JSON.stringify([template, TEACHER_FIELDS.map((f) => meta[f.key] ?? "")]);
  useEffect(() => {
    let alive = true;
    let made: string | null = null;
    const t = setTimeout(() => {
      // bo'sh maydonlar o'rniga namuna — qayerda nima chiqishi ko'rinsin
      const shown = Object.fromEntries(TEACHER_FIELDS.map((f) => [f.key, meta[f.key]?.trim() || f.hint]));
      api.lowerThirdPreview(template, { ...meta, ...shown })
        .then((u) => { made = u; if (alive) { setUrl(u); setErr(null); } else URL.revokeObjectURL(u); })
        .catch((e) => alive && setErr(String(e instanceof Error ? e.message : e)));
    }, 400);
    return () => { alive = false; clearTimeout(t); if (made) setTimeout(() => URL.revokeObjectURL(made!), 1000); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return (
    <figure className="lt-preview">
      <div className="lt-frame">
        <span className="lt-bar" aria-hidden />
        {url ? <img src={url} alt="Lower-third koʻrinishi" /> : <div className="noslide" />}
        <span className="lt-tpl">{template.toUpperCase()}</span>
      </div>
      <figcaption className="caption dim">{err ?? "Dars boshida koʻrinadigan yozuv — shablondan, jonli koʻrinish"}</figcaption>
    </figure>
  );
}
