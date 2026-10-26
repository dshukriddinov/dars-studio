import { useEffect, useState } from "react";
import { useStore } from "../store";

export function Settings() {
  const view = useStore((s) => s.view);
  const command = useStore.getState().command;
  const lid = Number(view?.project.eye_contact.lid_open ?? 0.5);
  const [v, setV] = useState(lid);
  const [health, setHealth] = useState<{ workdir?: string }>({});
  useEffect(() => setV(lid), [lid]);
  useEffect(() => { fetch("/api/health").then((r) => r.json()).then(setHealth).catch(() => undefined); }, []);
  const commit = () => { if (v !== lid) void command("Eye Contact: lid_open", { "eye_contact.lid_open": v }); };

  return (
    <div className="page panel form">
      <h2 className="heading">Sozlamalar</h2>
      {view ? (
        <label className="field">
          <span className="head"><span className="label">Eye Contact: qovoq ochiqligi (lid_open)</span>
            <span className="stat accent">{v.toFixed(2)}</span></span>
          <input type="range" min={0} max={1} step={0.05} value={v} onChange={(e) => setV(Number(e.target.value))}
            onPointerUp={commit} onKeyUp={commit} />
          <span className="caption dim">Oʻzgarish Eye Contact keshini bekor qiladi, qayta ishlash kerak boʻladi.</span>
        </label>
      ) : <p className="body dim">Loyiha tanlanmagan.</p>}
      <label className="field">
        <span className="label">Mavzu</span>
        <select defaultValue={document.documentElement.dataset.theme ?? "dark"} style={{ width: 160 }} onChange={(e) => {
          document.documentElement.dataset.theme = e.target.value;
          try { localStorage.setItem("theme", e.target.value); } catch { /* saqlanmasa ham ishlaydi */ }
        }}>
          <option value="dark">Qorongʻi</option>
          <option value="light">Yorugʻ</option>
        </select>
      </label>
      <div className="field">
        <span className="label">Ishchi papka</span>
        <span className="code">{health.workdir ?? "—"}</span>
        <span className="caption dim">DARS_WORKDIR muhit oʻzgaruvchisi bilan oʻzgartiriladi.</span>
      </div>
    </div>
  );
}
