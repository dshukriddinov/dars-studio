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

/** Kiritishda oddiy apostrofni oʻ/gʻ uchun U+02BB ga almashtiradi (CLAUDE.md 10-qoida). */
export const fixOkina = (s: string) => s.replace(/([OoGg])['’‘`]/g, "$1ʻ");

export function MetaFields({ fields, meta, onChange }: {
  fields: { key: string; label: string; hint: string; required?: boolean }[];
  meta: Record<string, string>; onChange: (m: Record<string, string>) => void;
}) {
  return (
    <div className="grid2">
      {fields.map((f) => (
        <label key={f.key} className="field">
          <span className="label">{f.label}{f.required ? " *" : ""}</span>
          <input value={meta[f.key] ?? ""} placeholder={f.hint} required={f.required}
            onChange={(e) => onChange({ ...meta, [f.key]: fixOkina(e.target.value) })} />
        </label>
      ))}
    </div>
  );
}

/** Lower-third ko'rinishi: kiritish to'xtagandan 400 ms keyin yangilanadi. */
export function LowerThirdPreview({ template, meta }: { template: string; meta: Record<string, string> }) {
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
      {url ? <img src={url} alt="Lower-third koʻrinishi" /> : <div className="noslide" />}
      <figcaption className="caption dim">{err ?? "Dars boshida ~8 s koʻrinadi"}</figcaption>
    </figure>
  );
}
