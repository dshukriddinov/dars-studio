// Shablon kalibrlash: ekran to'rtburchagi (TL, TR, BR, BL) va o'qituvchi anchor to'rtburchagi, kanvas koordinatalarida.
import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import { api, urls } from "../lib/api";

type Drag = { kind: "quad"; i: number } | { kind: "a0" } | { kind: "a1" } | null;

export function TemplateCalib() {
  const view = useStore((s) => s.view);
  const fail = useStore.getState().fail;
  const [ids, setIds] = useState<string[]>([]);
  const [id, setId] = useState<string>("");
  const [canvas, setCanvas] = useState<[number, number]>([1920, 1080]);
  const [quad, setQuad] = useState<number[][]>([]);
  const [anchor, setAnchor] = useState<number[]>([0, 0, 0, 0]);
  const [drag, setDrag] = useState<Drag>(null);
  const [saved, setSaved] = useState(false);
  const svg = useRef<SVGSVGElement>(null);

  useEffect(() => {
    api.templates().then((t) => { setIds(t); setId(view?.project.template_id && t.includes(view.project.template_id) ? view.project.template_id : t[0] ?? ""); })
      .catch(fail);
  }, [view?.project.template_id, fail]);

  useEffect(() => {
    if (!id) return;
    api.template(id).then((t) => {
      setQuad(t.screen_quad.map((p) => [...p]));
      setAnchor([...t.teacher_anchor]);
      if (Array.isArray(t.canvas)) setCanvas(t.canvas as [number, number]);
      setSaved(false);
    }).catch(fail);
  }, [id, fail]);

  const toCanvas = (e: React.PointerEvent) => {
    const r = svg.current!.getBoundingClientRect();
    return [Math.round(((e.clientX - r.left) / r.width) * canvas[0]), Math.round(((e.clientY - r.top) / r.height) * canvas[1])];
  };

  const onMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const [x, y] = toCanvas(e);
    setSaved(false);
    if (drag.kind === "quad") setQuad(quad.map((p, i) => (i === drag.i ? [x, y] : p)));
    else if (drag.kind === "a0") setAnchor([Math.min(x, anchor[2] - 8), Math.min(y, anchor[3] - 8), anchor[2], anchor[3]]);
    else setAnchor([anchor[0], anchor[1], Math.max(x, anchor[0] + 8), Math.max(y, anchor[1] + 8)]);
  };

  const save = async () => {
    try { await api.saveTemplate(id, { screen_quad: quad, teacher_anchor: anchor }); setSaved(true); } catch (e) { fail(e); }
  };

  const h = canvas[0] / 120; // tutqich o'lchami kanvas birligida
  return (
    <div className="page panel">
      <div className="toolbar">
        <label className="label">Shablon</label>
        <select value={id} onChange={(e) => setId(e.target.value)}>{ids.map((t) => <option key={t}>{t}</option>)}</select>
        <span className="spacer" />
        {saved ? <span className="caption success">Saqlandi</span> : null}
        <button className="btn-primary" disabled={!id || quad.length !== 4} onClick={save}>Saqlash</button>
      </div>
      {id ? (
        <div className="tpl-stage">
          <img src={urls.templateBg(id)} alt="Fon" draggable={false} />
          <svg ref={svg} viewBox={`0 0 ${canvas[0]} ${canvas[1]}`} onPointerMove={onMove} onPointerUp={() => setDrag(null)}
            onPointerLeave={() => setDrag(null)}>
            {quad.length === 4 ? <polygon points={quad.map((p) => p.join(",")).join(" ")} className="tpl-quad" /> : null}
            <rect x={anchor[0]} y={anchor[1]} width={anchor[2] - anchor[0]} height={anchor[3] - anchor[1]} className="tpl-anchor" />
            {quad.map((p, i) => (
              <circle key={i} cx={p[0]} cy={p[1]} r={h} className="tpl-handle" onPointerDown={() => setDrag({ kind: "quad", i })}>
                <title>{["Yuqori chap", "Yuqori oʻng", "Pastki oʻng", "Pastki chap"][i]}</title>
              </circle>
            ))}
            <rect x={anchor[0] - h} y={anchor[1] - h} width={2 * h} height={2 * h} className="tpl-handle a"
              onPointerDown={() => setDrag({ kind: "a0" })} />
            <rect x={anchor[2] - h} y={anchor[3] - h} width={2 * h} height={2 * h} className="tpl-handle a"
              onPointerDown={() => setDrag({ kind: "a1" })} />
          </svg>
        </div>
      ) : <p className="body dim">Shablon topilmadi.</p>}
      <p className="caption dim">Toʻrtburchak: ekran burchaklari (TL, TR, BR, BL). Kvadrat tutqichlar: oʻqituvchi joyi (anchor).</p>
    </div>
  );
}
