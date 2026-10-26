import { useEffect, useState } from "react";
import { useStore } from "../store";
import { api, urls } from "../lib/api";
import { player } from "../lib/player";

const SLIDERS: [string, string, number, number, number][] = [
  ["tolerance", "Tolerantlik", 0, 0.5, 0.005],
  ["softness", "Yumshoqlik", 0, 0.5, 0.005],
  ["spill", "Spill", 0, 1, 0.01],
  ["choke_px", "Choke, px", -5, 10, 0.5],
  ["feather_px", "Feather, px", 0, 10, 0.5],
];
const MODES: [string, string][] = [["orig", "Asl"], ["keyed", "Natija"], ["matte", "Matte"]];

export function KeyCalib() {
  const name = useStore((s) => s.name);
  const view = useStore((s) => s.view);
  const { command, setView, fail } = useStore.getState();
  const [frame, setFrame] = useState(player.frame);
  const [mode, setMode] = useState("keyed");
  const [vals, setVals] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const key = view?.project.key;

  useEffect(() => { if (key) setVals(Object.fromEntries(SLIDERS.map(([k]) => [k, Number(key[k])]))); }, [key]);
  if (!name || !view || !key) return <div className="pad body dim">Loyiha tanlanmagan.</div>;
  const total = view.project.total_frames;
  // Rasm URL'i kalit sozlamalariga bog'liq, aks holda brauzer eski JPEG'ni ko'rsatadi
  const ver = SLIDERS.map(([k]) => key[k]).join("_");

  const commit = (k: string) => { if (vals[k] !== key[k]) void command(`Key: ${k}`, { [`key.${k}`]: vals[k] }); };

  return (
    <div className="page calib">
      <section className="panel">
        <div className="toolbar">
          {MODES.map(([m, l]) => (
            <button key={m} className={`btn-secondary sm${mode === m ? " on" : ""}`} onClick={() => setMode(m)}>{l}</button>
          ))}
          <span className="spacer" />
          <label className="label">Kadr</label>
          <input type="number" min={0} max={total - 1} value={frame} style={{ width: 96 }}
            onChange={(e) => setFrame(Math.max(0, Math.min(total - 1, Number(e.target.value) || 0)))} />
        </div>
        <input type="range" className="wide" min={0} max={total - 1} value={frame} onChange={(e) => setFrame(Number(e.target.value))} />
        <img className="calib-img" src={`${urls.frame(name, frame, mode)}&v=${ver}`} alt="Kadr" />
      </section>
      <section className="panel sliders">
        {SLIDERS.map(([k, l, min, max, step]) => (
          <label key={k} className="field">
            <span className="head"><span className="label">{l}</span><span className="stat accent">{vals[k]?.toFixed(3)}</span></span>
            <input type="range" min={min} max={max} step={step} value={vals[k] ?? 0}
              onChange={(e) => setVals({ ...vals, [k]: Number(e.target.value) })}
              onPointerUp={() => commit(k)} onKeyUp={() => commit(k)} />
          </label>
        ))}
        <button className="btn-secondary" disabled={busy} onClick={async () => {
          setBusy(true);
          try { setView(await api.keySuggest(name, frame)); } catch (e) { fail(e); } finally { setBusy(false); }
        }}>{busy ? "Ishlanmoqda…" : "Avtomatik taklif"}</button>
      </section>
    </div>
  );
}
