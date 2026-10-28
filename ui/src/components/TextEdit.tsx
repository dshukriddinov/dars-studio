// Matn orqali kesish: o'qituvchi so'zlari; bosish yoki sudrab belgilash -> "Kesish" (qo'lda kesish, darhol
// tasdiqlangan). Kesilgan so'zlar ustidan chizilgan; bosilsa "Tiklash". Bosilgan so'zga video o'tadi.
import { useEffect, useMemo, useRef, useState } from "react";
import { Scissors, Undo2 } from "lucide-react";
import { player, useFrameValue } from "../lib/player";
import { frameToSec, msToFrame, type Fps } from "../lib/time";
import type { CutProposal, Word } from "../lib/types";

const PARA_GAP_MS = 1500;   // shundan uzun pauza — yangi xatboshi

export function TextEdit({ words, cuts, fps, total, onCut, onRestore }: {
  words: Word[]; cuts: CutProposal[]; fps: Fps; total: number;
  onCut: (start: number, end: number) => void; onRestore: (cutIndex: number[]) => void;
}) {
  const ws = useMemo(() => [...words].sort((a, b) => a.start_ms - b.start_ms), [words]);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [head, setHead] = useState<number | null>(null);
  const dragging = useRef(false);
  const anchorRef = useRef<number | null>(null);   // tez ketma-ket bosishlarda ham joriy qiymat
  const pick = (a: number | null, h: number | null) => { anchorRef.current = a; setAnchor(a); setHead(h); };

  // har so'z qaysi tasdiqlangan kesish ichida (yo'q — -1)
  const cutOf = useMemo(() => {
    const ms = (f: number) => frameToSec(f, fps) * 1000;
    const on = cuts.map((c, i) => ({ c, i })).filter((x) => x.c.status === "tasdiqlangan");
    return ws.map((w) => on.find((x) => w.start_ms >= ms(x.c.start) && w.start_ms < ms(x.c.end))?.i ?? -1);
  }, [ws, cuts, fps]);

  const playing = useFrameValue((f) => {
    const t = frameToSec(f, fps) * 1000;
    let lo = 0, hi = ws.length - 1, k = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (ws[m].start_ms <= t) { k = m; lo = m + 1; } else hi = m - 1; }
    return k >= 0 && t < ws[k].end_ms + 300 ? k : -1;
  }, [ws, fps]);

  const sel = anchor !== null && head !== null ? [Math.min(anchor, head), Math.max(anchor, head)] as const : null;
  const selCuts = sel ? [...new Set(cutOf.slice(sel[0], sel[1] + 1).filter((x) => x >= 0))] : [];
  const allCut = sel ? cutOf.slice(sel[0], sel[1] + 1).every((x) => x >= 0) : false;

  const cutSelection = () => {
    if (!sel) return;
    const [a, b] = sel;
    // chegaralar so'zlar orasidagi bo'shliq o'rtasida (so'z boshi/oxiri qirqilmasin)
    const s = a > 0 ? (ws[a - 1].end_ms + ws[a].start_ms) / 2 : Math.max(0, ws[a].start_ms - 150);
    const e = b + 1 < ws.length ? (ws[b].end_ms + ws[b + 1].start_ms) / 2 : ws[b].end_ms + 150;
    onCut(Math.max(0, msToFrame(s, fps)), Math.min(total, msToFrame(e, fps)));
    pick(null, null);
  };

  useEffect(() => {
    const up = () => { dragging.current = false; };
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, select, textarea")) return;
      if ((e.key === "Delete" || e.key === "Backspace") && sel && !allCut) { e.preventDefault(); cutSelection(); }
      if (e.key === "Escape") { pick(null, null); }
    };
    window.addEventListener("mouseup", up); window.addEventListener("keydown", key);
    return () => { window.removeEventListener("mouseup", up); window.removeEventListener("keydown", key); };
  });

  if (!ws.length) return <p className="dim pad">Matn hali tayyor emas (2-qadam: nutq matni).</p>;

  const paras: number[][] = [];
  ws.forEach((w, i) => {
    if (!i || w.start_ms - ws[i - 1].end_ms >= PARA_GAP_MS) paras.push([]);
    paras[paras.length - 1].push(i);
  });

  return (
    <div className="textedit">
      <div className="te-bar">
        {sel ? (
          <>
            <span className="strong">{sel[1] - sel[0] + 1} ta soʻz</span>
            <span className="caption dim">{fmt(ws[sel[0]].start_ms)}–{fmt(ws[sel[1]].end_ms)}</span>
            <span className="spacer" />
            {allCut ? (
              <button className="btn-secondary sm" onClick={() => { onRestore(selCuts); pick(null, null); }}>
                <Undo2 size={14} /> Tiklash</button>
            ) : (
              <button className="btn-primary sm" onClick={cutSelection}><Scissors size={14} /> Kesish</button>
            )}
            <button className="btn-ghost sm" onClick={() => { pick(null, null); }}>Bekor</button>
          </>
        ) : <span className="caption dim">Soʻzni bosing yoki sichqoncha bilan sudrab belgilang. Delete — kesish,
          Shift + bosish — tanlovni kengaytirish.</span>}
      </div>
      <div className="te-text" onMouseLeave={() => { dragging.current = false; }}>
        {paras.map((p) => (
          <p key={p[0]}>
            <span className="te-time" onClick={() => player.seek(msToFrame(ws[p[0]].start_ms, fps))}>{fmt(ws[p[0]].start_ms)}</span>
            {p.map((i) => {
              const inSel = sel && i >= sel[0] && i <= sel[1];
              const cls = `w${cutOf[i] >= 0 ? " w-cut" : ""}${inSel ? " sel" : ""}${i === playing ? " now" : ""}`;
              return (
                <span key={i} className={cls}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    if (e.shiftKey && anchorRef.current !== null) { setHead(i); return; }
                    dragging.current = true; pick(i, i);
                    player.seek(msToFrame(ws[i].start_ms, fps));
                  }}
                  onMouseEnter={() => { if (dragging.current) setHead(i); }}>{ws[i].text} </span>
              );
            })}
          </p>
        ))}
      </div>
    </div>
  );
}

const fmt = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor((ms / 1000) % 60)).padStart(2, "0")}`;
