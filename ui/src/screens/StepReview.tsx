// 3. Ko'rib chiqish: video + kesish takliflari o'qituvchining so'zlari bilan (kesiladigan qism ustidan chizilgan).
// Qatorni bosish — video o'sha joydan; katakcha — kesish / qoldirish; "Natijani tinglash" — tasdiqlangan
// kesishlarni o'tkazib yuborib o'ynaydi. Klaviatura: Probel — o'ynatish, ↑/↓ — oldingi/keyingi, Enter — belgilash.
import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, SlidersHorizontal } from "lucide-react";
import { useStore } from "../store";
import { urls } from "../lib/api";
import { player, useFrameValue } from "../lib/player";
import { frameToSec, parseFps, secToFrame } from "../lib/time";
import type { CutProposal, Project as P, Word } from "../lib/types";
import { TextEdit } from "../components/TextEdit";

type Group = "all" | "takror" | "yotal" | "mmm" | "pause" | "auto";
const GROUPS: [Group, string, CutProposal["reason"][]][] = [
  ["all", "Hammasi", []],
  ["takror", "Takror va qayta aytish", ["takror"]],
  ["yotal", "Yoʻtal, aksa", ["yo'tal", "aksa"]],
  ["mmm", "“mmm”, “eee”", ["to'ldiruvchi"]],
  ["pause", "Uzun pauzalar", ["pause", "manual"]],
  ["auto", "Boshi, oxiri, ulanish", ["bosh", "oxir", "qism"]],
];
const KIND: Record<CutProposal["reason"], string> = {
  pause: "Pauza", manual: "Qoʻlda", bosh: "Dars boshi", oxir: "Dars oxiri", "yo'tal": "Yoʻtal", aksa: "Aksa",
  "to'ldiruvchi": "“mmm”", takror: "Takror", qism: "Qismlar ulanishi",
};
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export function StepReview({ name, p }: { name: string; p: P }) {
  const words = useStore((s) => s.words);
  const { command, setTab, setStep } = useStore.getState();
  const fps = useMemo(() => parseFps(p.fps), [p.fps]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [group, setGroup] = useState<Group>("all");
  const [sel, setSel] = useState(0);
  const [result, setResult] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [panel, setPanel] = useState<"list" | "text">("list");

  const items = useMemo(() => p.cuts.map((c, i) => ({ c, i })).sort((a, b) => a.c.start - b.c.start), [p.cuts]);
  const shown = useMemo(() => {
    const g = GROUPS.find(([k]) => k === group)!;
    return group === "all" ? items : items.filter((x) => g[2].includes(x.c.reason));
  }, [items, group]);
  const approved = useMemo(() => p.cuts.filter((c) => c.status === "tasdiqlangan").sort((a, b) => a.start - b.start),
    [p.cuts]);
  const savedSec = frameToSec(approved.reduce((s, c) => s + c.end - c.start, 0), fps);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    player.attach(v, fps, p.total_frames);
    const on = () => setPlaying(!v.paused);
    v.addEventListener("play", on); v.addEventListener("pause", on);
    return () => { v.removeEventListener("play", on); v.removeEventListener("pause", on); player.detach(); };
  }, [name, fps, p.total_frames]);

  // "Natijani tinglash": tasdiqlangan kesish ichiga kirsa — oxiriga sakraydi
  useEffect(() => player.subscribe((f) => {
    if (!result || !player.playing) return;
    const c = approved.find((x) => f >= x.start && f < x.end - 1);
    if (c) player.seek(c.end);
  }), [result, approved]);

  const setStatus = (idx: number[], status: CutProposal["status"]) => {
    const set = new Set(idx);
    void command(status === "tasdiqlangan" ? "Kesish" : "Qoldirish",
      { cuts: p.cuts.map((c, i) => (set.has(i) ? { ...c, status } : c)) });
  };
  const jump = (k: number) => {
    const x = shown[k];
    if (!x) return;
    setSel(k);
    player.seek(Math.max(0, x.c.start - secToFrame(2, fps)));
    player.play();
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, select, textarea")) return;
      if (e.key === " ") { e.preventDefault(); player.toggle(); }
      else if (panel !== "list") return;
      else if (e.key === "ArrowDown") { e.preventDefault(); jump(Math.min(shown.length - 1, sel + 1)); }
      else if (e.key === "ArrowUp") { e.preventDefault(); jump(Math.max(0, sel - 1)); }
      else if (e.key === "Enter" && shown[sel]) {
        e.preventDefault();
        const x = shown[sel];
        setStatus([x.i], x.c.status === "tasdiqlangan" ? "rad_etilgan" : "tasdiqlangan");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const unshown = p.slide_spans.length ? p.slides.filter((s) => !p.slide_spans.some((x) => x.slide === s.index)) : [];

  return (
    <div className="review2">
      <div className="rv-media">
        <div className="rv-video">
          <video ref={videoRef} src={urls.proxy(name)} preload="auto" onClick={() => player.toggle()} />
        </div>
        <div className="rv-controls">
          <button className="btn-icon" onClick={() => player.toggle()} aria-label={playing ? "Toʻxtatish" : "Oʻynatish"}>
            {playing ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <Clock fps={fps} />
          <label className="check"><input type="checkbox" checked={result} onChange={(e) => setResult(e.target.checked)} />
            Natijani tinglash (kesiladigan joylarsiz)</label>
          <span className="spacer" />
          <button className="btn-ghost" onClick={() => setTab("review")}><SlidersHorizontal size={16} /> Batafsil tahrir</button>
        </div>
        <CutMap p={p} items={shown.map((x) => x.c)} selected={shown[sel]?.c} />
        <p className="caption dim">Tasdiqlangan kesishlar: {approved.length} ta, video {mmss(savedSec)} ga qisqaradi.
          {unshown.length ? ` Koʻrsatilmagan slaydlar: ${unshown.map((s) => s.index).join(", ")}.` : ""}</p>
        <div className="rv-done">
        <div>
          <div className="strong">Koʻrib chiqib boʻldingizmi?</div>
          <div className="caption dim">{approved.length} ta joy kesiladi, {items.length - approved.length} ta joy qoladi.
            Belgilarni keyin ham oʻzgartirish mumkin.</div>
        </div>
        <button className="btn-primary big" onClick={() => setStep(4)}>Tasdiqlash va eksportga oʻtish</button>
      </div>
      </div>

      <aside className="rv-list">
        <div className="seg" role="tablist" aria-label="Koʻrinish">
          <button role="tab" aria-selected={panel === "list"} className={panel === "list" ? "on" : ""}
            onClick={() => setPanel("list")}>Takliflar</button>
          <button role="tab" aria-selected={panel === "text"} className={panel === "text" ? "on" : ""}
            onClick={() => setPanel("text")}>Matn: soʻzlarni kesish</button>
        </div>
        {panel === "text" ? (
          <TextEdit words={words} cuts={p.cuts} fps={fps} total={p.total_frames}
            onCut={(start, end) => void command("Matndan kesish", {
              cuts: [...p.cuts, { start, end, reason: "manual", status: "tasdiqlangan" }],
            })}
            onRestore={(idx) => setStatus(idx, "rad_etilgan")} />
        ) : <>
        <div className="chips" role="tablist">
          {GROUPS.map(([g, label, reasons]) => {
            const n = g === "all" ? items.length : items.filter((x) => reasons.includes(x.c.reason)).length;
            return n || g === "all" ? (
              <button key={g} role="tab" aria-selected={group === g} className={`chip${group === g ? " on" : ""}`}
                onClick={() => { setGroup(g); setSel(0); }}>{label} <span className="chip-n">{n}</span></button>
            ) : null;
          })}
        </div>
        <div className="row bulk">
          <button className="btn-secondary sm" disabled={!shown.length}
            onClick={() => setStatus(shown.map((x) => x.i), "tasdiqlangan")}>Hammasini kesish</button>
          <button className="btn-ghost sm" disabled={!shown.length}
            onClick={() => setStatus(shown.map((x) => x.i), "rad_etilgan")}>Hammasini qoldirish</button>
        </div>
        {!shown.length ? <p className="dim pad">Bu turda taklif yoʻq.</p> : (
          <ul className="cuts" aria-label="Kesish takliflari">
            {shown.map((x, k) => (
              <CutRow key={x.i} c={x.c} words={words} fps={fps} active={k === sel} onOpen={() => jump(k)}
                onToggle={(on) => setStatus([x.i], on ? "tasdiqlangan" : "rad_etilgan")} />
            ))}
          </ul>
        )}
        <p className="caption dim hint">Probel — oʻynatish, ↑ ↓ — oldingi/keyingi, Enter — kesish yoki qoldirish.</p>
        </>}
      </aside>

    </div>
  );
}

function Clock({ fps }: { fps: ReturnType<typeof parseFps> }) {
  const f = useFrameValue((x) => Math.floor(frameToSec(x, fps)), [fps]);
  return <span className="clock">{mmss(f)}</span>;
}

function CutRow({ c, words, fps, active, onOpen, onToggle }: {
  c: CutProposal; words: Word[]; fps: ReturnType<typeof parseFps>; active: boolean;
  onOpen: () => void; onToggle: (on: boolean) => void;
}) {
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => { if (active) ref.current?.scrollIntoView({ block: "nearest" }); }, [active]);
  const s = frameToSec(c.start, fps) * 1000, e = frameToSec(c.end, fps) * 1000;
  const cut = words.filter((w) => w.start_ms >= s && w.start_ms < e);
  const before = words.filter((w) => w.end_ms <= s).slice(-4);
  const after = words.filter((w) => w.start_ms >= e).slice(0, 4);
  const on = c.status === "tasdiqlangan";
  return (
    <li ref={ref} className={`cut${active ? " active" : ""}${on ? " on" : ""}`}>
      <input type="checkbox" checked={on} onChange={(ev) => onToggle(ev.target.checked)}
        aria-label={on ? "Kesiladi" : "Qoladi"} />
      <button className="cut-body" onClick={onOpen}>
        <span className="cut-head"><span className={`kind k-${c.reason.replace("'", "")}`}>{KIND[c.reason]}</span>
          <span className="caption dim">{mmss(s / 1000)}, {((e - s) / 1000).toFixed(1)} s</span></span>
        <span className="cut-text">
          {before.length ? <span className="ctx">…{before.map((w) => w.text).join(" ")} </span> : null}
          {cut.length ? <del>{cut.map((w) => w.text).join(" ")}</del> : <del className="gap">jimlik yoki tovush</del>}
          {after.length ? <span className="ctx"> {after.map((w) => w.text).join(" ")}…</span> : null}
        </span>
      </button>
    </li>
  );
}

/** Butun dars bo'ylab kesishlar xaritasi; bosilgan joyga o'tadi. */
function CutMap({ p, items, selected }: { p: P; items: CutProposal[]; selected?: CutProposal }) {
  const head = useFrameValue((f) => Math.round((f / Math.max(1, p.total_frames)) * 1000) / 10, [p.total_frames]);
  const pct = (f: number) => `${(f / Math.max(1, p.total_frames)) * 100}%`;
  return (
    <div className="cutmap" onClick={(e) => {
      const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
      player.seek(((e.clientX - r.left) / r.width) * p.total_frames);
    }}>
      {p.slide_spans.map((s) => <span key={`s${s.start}`} className="cm-slide" style={{ left: pct(s.start) }} />)}
      {items.map((c) => (
        <span key={`c${c.start}`} className={`cm-cut${c.status === "tasdiqlangan" ? " on" : ""}${c === selected ? " sel" : ""}`}
          style={{ left: pct(c.start), width: `max(2px, ${pct(c.end - c.start)})` }} />
      ))}
      <span className="cm-head" style={{ left: `${head}%` }} />
    </div>
  );
}
