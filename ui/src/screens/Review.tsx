// Tekshirish (FR-14, FR-15): Tez ko'rinish (proxy + slayd), transkript, timeline, Shubhali joylar, amallar.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, Pause, Play, Redo2, Scissors, SkipBack, SkipForward, Undo2, X } from "lucide-react";
import { useStore } from "../store";
import { api, urls } from "../lib/api";
import { player, useFrameValue } from "../lib/player";
import { fmtFrame, frameToSec, parseFps, secToFrame } from "../lib/time";
import { indexAt } from "../lib/spans";
import { groupWords } from "../lib/subtitles";
import { keyToAction, type KeyAction } from "../lib/keys";
import * as E from "../lib/edits";
import { Timeline, laneMaxLen, type Item, type Lane } from "../components/Timeline";
import { SuspiciousList } from "../components/SuspiciousList";
import { Transcript } from "../components/Transcript";
import { StatusBadge } from "../components/StatusBadge";
import type { Project } from "../lib/types";

export function Review() {
  const name = useStore((s) => s.name);
  const view = useStore((s) => s.view);
  const words = useStore((s) => s.words);
  const suspicious = useStore((s) => s.suspicious);
  const { command, undo, redo } = useStore.getState();
  if (!name) return <Empty text="Loyiha tanlanmagan. Bosh sahifadan loyihani oching." />;
  if (!view) return <Empty text="Yuklanmoqda…" />;
  return <ReviewBody name={name} p={view.project} words={words} suspicious={suspicious}
    command={command} undo={undo} redo={redo} />;
}

const Empty = ({ text }: { text: string }) => <div className="pad body dim">{text}</div>;

interface BodyProps {
  name: string; p: Project; words: ReturnType<typeof useStore.getState>["words"];
  suspicious: ReturnType<typeof useStore.getState>["suspicious"];
  command: (l: string, v: Record<string, unknown>) => Promise<boolean>; undo: () => Promise<void>; redo: () => Promise<void>;
}

function ReviewBody({ name, p, words, suspicious, command, undo, redo }: BodyProps) {
  const view = useStore((s) => s.view)!;
  const fps = useMemo(() => parseFps(p.fps), [p.fps]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [selBoundary, setSelBoundary] = useState(-1);
  const [selCut, setSelCut] = useState(-1);
  const [selEye, setSelEye] = useState(-1);
  const [markIn, setMarkIn] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    player.attach(v, fps, p.total_frames);
    const on = () => setPlaying(!v.paused);
    v.addEventListener("play", on); v.addEventListener("pause", on);
    return () => { v.removeEventListener("play", on); v.removeEventListener("pause", on); player.detach(); };
  }, [name, fps, p.total_frames]);

  const run = useCallback((c: E.Cmd | null) => { if (c) void command(c.label, c.values); }, [command]);

  // Playhead ostidagi slayd oralig'i (kam o'zgaradi, shuning uchun qayta chizish arzon)
  const spanIdx = useFrameValue((f) => indexAt(p.slide_spans, f), [p.slide_spans]);
  const slideNo = spanIdx >= 0 ? p.slide_spans[spanIdx].slide : null;
  const boundary = selBoundary >= 0 && selBoundary < p.slide_spans.length - 1 ? selBoundary : -1;

  const lanes = useMemo<Lane[]>(() => {
    const items = <T extends { start: number; end: number }>(arr: T[], f: (x: T, i: number) => Partial<Item>) =>
      arr.map((x, i) => ({ start: x.start, end: x.end, i, ...f(x, i) }))
        .sort((a, b) => a.start - b.start);
    const slide = items(p.slide_spans, (s) => ({
      text: String(s.slide), cls: `src-${s.source}${s.confidence < 0.6 ? " low" : ""}`,
    }));
    const scene = items(p.layout_spans, (s) => ({ text: s.layout, cls: `scene-${s.layout}` }));
    const cuts = items(p.cuts, (c) => ({ cls: `cut-${c.status}`, text: c.reason === "pause" ? "pauza" : "qoʻlda" }));
    const eye = items(p.eye_off, () => ({ cls: "eye" }));
    const subs = groupWords(words, fps).map((c, i) => ({ ...c, i, cls: "sub" }));
    return [
      { id: "slide", label: "Slayd", items: slide, maxLen: laneMaxLen(slide), boundaries: true },
      { id: "scene", label: "Sahna (A/B)", items: scene, maxLen: laneMaxLen(scene) },
      { id: "cut", label: "Kesishlar", items: cuts, maxLen: laneMaxLen(cuts) },
      { id: "eye", label: "Eye Contact oʻchiq", items: eye, maxLen: laneMaxLen(eye) },
      { id: "sub", label: "Subtitr", items: subs, maxLen: laneMaxLen(subs) },
    ];
  }, [p, words, fps]);

  const onItemClick = useCallback((lane: string, i: number, frame: number) => {
    player.seek(frame);
    if (lane === "slide") setSelBoundary(i > 0 ? i - 1 : 0);
    if (lane === "cut") setSelCut(i);
    if (lane === "eye") setSelEye(i);
  }, []);

  const half = secToFrame(0.5, fps);
  const nudge = (df: number) => boundary >= 0 && run(E.moveBoundaryCmd(p, boundary, p.slide_spans[boundary].end + df));

  const cutAtHead = () => p.cuts.findIndex((c) => c.start <= player.frame && player.frame < c.end);
  const approveCut = (status: "tasdiqlangan" | "rad_etilgan") => {
    const i = selCut >= 0 ? selCut : cutAtHead();
    if (i >= 0) run(E.cutStatusCmd(p, i, status));
  };

  const act = useRef<(a: KeyAction) => void>(() => undefined);
  act.current = (a: KeyAction) => {
    switch (a) {
      case "reverse": player.seekSec(-1); break;
      case "pause": player.pause(); break;
      case "toggle": player.toggle(); break;
      case "play": player.play(); break;
      case "prevFrame": player.step(-1); break;
      case "nextFrame": player.step(1); break;
      case "back1s": player.seekSec(-1); break;
      case "fwd1s": player.seekSec(1); break;
      case "boundaryLeft": nudge(-1); break;
      case "boundaryRight": nudge(1); break;
      case "sceneA": run(E.setSceneCmd(p, player.frame, "A")); break;
      case "sceneB": run(E.setSceneCmd(p, player.frame, "B")); break;
      case "approveCut": approveCut("tasdiqlangan"); break;
      case "undo": void undo(); break;
      case "redo": void redo(); break;
    }
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Tugma fokusda bo'lsa Enter/Space tugmaning o'zini bosadi
      if ((e.key === "Enter" || e.key === " ") && (e.target as HTMLElement)?.tagName === "BUTTON") return;
      const a = keyToAction(e);
      if (!a) return;
      e.preventDefault();
      act.current(a);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const selSpan = boundary >= 0 ? p.slide_spans[boundary] : null;
  const curSpan = spanIdx >= 0 ? p.slide_spans[spanIdx] : null;
  const curLayout = useFrameValue((f) => p.layout_spans[indexAt(p.layout_spans, f)]?.layout ?? "—", [p.layout_spans]);
  const cut = selCut >= 0 ? p.cuts[selCut] : undefined;
  const pending = p.cuts.filter((c) => c.status === "taklif").length;

  return (
    <div className="review">
      <div className="review-top">
        <section className="panel media">
          <div className="media-pair">
            <figure>
              <video ref={videoRef} src={urls.proxy(name)} preload="auto" onClick={() => player.toggle()} />
              <figcaption className="caption dim">Proxy</figcaption>
            </figure>
            <figure>
              {slideNo ? <img src={urls.slide(name, slideNo)} alt={`${slideNo}-slayd`} /> : <div className="noslide" />}
              <figcaption className="caption dim">{slideNo ? `${slideNo}-slayd` : "Slayd yoʻq"}</figcaption>
            </figure>
          </div>
          <div className="transport">
            <button className="btn-icon" onClick={() => player.step(-1)} aria-label="Oldingi kadr"><SkipBack size={16} /></button>
            <button className="btn-icon" onClick={() => player.toggle()} aria-label={playing ? "Pauza" : "Ijro"}>
              {playing ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <button className="btn-icon" onClick={() => player.step(1)} aria-label="Keyingi kadr"><SkipForward size={16} /></button>
            <FrameCounter fps={fps} total={p.total_frames} />
            <span className="caption dim">Sahna {curLayout}</span>
            <span className="spacer" />
            <RealPreview name={name} fps={fps} />
          </div>
        </section>
        <section className="panel side">
          <h2 className="heading">Shubhali joylar <span className="caption dim">{suspicious.length}</span></h2>
          <div className="scroll"><SuspiciousList items={suspicious} fps={fps} onJump={(f) => player.seek(f)} /></div>
          <h2 className="heading">Transkript</h2>
          <div className="scroll"><Transcript words={words} /></div>
        </section>
      </div>

      <section className="panel actions">
        <div className="group">
          <button className="btn-secondary" disabled={!view.can_undo} onClick={() => void undo()}
            title={view.undo_label ? `Bekor qilish: ${view.undo_label} (Ctrl+Z)` : "Bekor qilish (Ctrl+Z)"}>
            <Undo2 size={16} /> {view.undo_label ?? "Bekor qilish"}
          </button>
          <button className="btn-secondary" disabled={!view.can_redo} onClick={() => void redo()}
            title={view.redo_label ? `Qaytarish: ${view.redo_label} (Ctrl+Y)` : "Qaytarish (Ctrl+Y)"}>
            <Redo2 size={16} /> {view.redo_label ?? "Qaytarish"}
          </button>
        </div>

        <div className="group">
          <span className="label dim">Chegara</span>
          {selSpan ? (
            <span className="stat">{selSpan.slide}→{p.slide_spans[boundary + 1].slide} · {fmtFrame(selSpan.end, fps)}</span>
          ) : <span className="caption dim">tanlanmagan</span>}
          <button className="btn-secondary sm" disabled={!selSpan} onClick={() => nudge(-half)}>−0.5 s</button>
          <button className="btn-secondary sm" disabled={!selSpan} onClick={() => nudge(-1)} title="[">−1 kadr</button>
          <button className="btn-secondary sm" disabled={!selSpan} onClick={() => nudge(1)} title="]">+1 kadr</button>
          <button className="btn-secondary sm" disabled={!selSpan} onClick={() => nudge(half)}>+0.5 s</button>
          <button className="btn-secondary sm" disabled={!selSpan}
            onClick={() => selSpan && run(E.moveBoundaryCmd(p, boundary, player.frame))}>Playhead'ga</button>
          <button className="btn-secondary sm" onClick={() => run(E.splitSlideCmd(p, player.frame))}>Chegara qoʻshish</button>
          <button className="btn-secondary sm" disabled={!selSpan}
            onClick={() => { run(E.mergeSlideCmd(p, boundary)); setSelBoundary(-1); }}>Chegarani oʻchirish</button>
        </div>

        <div className="group">
          <label className="label dim" htmlFor="slide-no">Slayd raqami</label>
          <select id="slide-no" value={curSpan?.slide ?? ""} disabled={!curSpan}
            onChange={(e) => run(E.setSlideCmd(p, spanIdx, Number(e.target.value)))}>
            {(p.slides.length ? p.slides.map((s) => s.index) : [curSpan?.slide ?? 1]).map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          <span className="label dim">Sahna</span>
          <button className={`btn-secondary sm${curLayout === "A" ? " on" : ""}`}
            onClick={() => run(E.setSceneCmd(p, player.frame, "A"))} title="1">A</button>
          <button className={`btn-secondary sm${curLayout === "B" ? " on" : ""}`}
            onClick={() => run(E.setSceneCmd(p, player.frame, "B"))} title="2">B</button>
        </div>

        <div className="group">
          <span className="label dim"><Scissors size={14} /> Kesish</span>
          {cut ? <span className="stat">{fmtFrame(cut.start, fps)} · {cut.status}</span>
            : <span className="caption dim">{p.cuts.length ? "tanlanmagan" : "kesish yoʻq"}</span>}
          <button className="btn-secondary sm" disabled={!p.cuts.length} onClick={() => approveCut("tasdiqlangan")} title="Enter">
            <Check size={14} /> Tasdiqlash</button>
          <button className="btn-secondary sm" disabled={!p.cuts.length} onClick={() => approveCut("rad_etilgan")}>
            <X size={14} /> Rad etish</button>
          <button className="btn-secondary sm" disabled={!pending} onClick={() => run(E.approveAllCutsCmd(p))}>
            Hammasini tasdiqlash ({pending})</button>
        </div>

        <div className="group">
          <span className="label dim">Eye Contact oʻchiq</span>
          <button className="btn-secondary sm" onClick={() => setMarkIn(player.frame)}>
            Boshi{markIn !== null ? ` ${fmtFrame(markIn, fps)}` : ""}</button>
          <button className="btn-secondary sm" disabled={markIn === null}
            onClick={() => { run(E.addEyeOffCmd(p, markIn!, player.frame)); setMarkIn(null); }}>Oxiri va qoʻshish</button>
          <button className="btn-secondary sm" disabled={selEye < 0 || !p.eye_off[selEye]}
            onClick={() => { run(E.removeEyeOffCmd(p, selEye)); setSelEye(-1); }}>Oʻchirish</button>
        </div>
      </section>

      <section className="panel tl-panel">
        <Timeline total={p.total_frames} lanes={lanes} selected={{ cut: selCut, eye: selEye, slide: spanIdx }}
          selectedBoundary={boundary} onItemClick={onItemClick} onBoundaryClick={setSelBoundary}
          onSeek={(f) => player.seek(f)} />
        <p className="caption dim hint">
          J −1 s · K pauza · L ijro · ←/→ kadr · Shift+←/→ 1 s · [ ] chegara · 1/2 sahna · Enter tasdiqlash · Ctrl+Z/Y · Ctrl+gʻildirak masshtab
        </p>
      </section>
    </div>
  );
}

function FrameCounter({ fps, total }: { fps: ReturnType<typeof parseFps>; total: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const put = (f: number) => { if (ref.current) ref.current.textContent = `${fmtFrame(f, fps)} · ${f} / ${total} kadr`; };
    put(player.frame);
    return player.subscribe(put);
  }, [fps, total]);
  return <span className="stat" ref={ref} />;
}

/** "Haqiqiy ko'rinish" (FR-15): playhead atrofida ±5 s render navbatga, tayyor bo'lsa ijro. */
function RealPreview({ name, fps }: { name: string; fps: ReturnType<typeof parseFps> }) {
  const [req, setReq] = useState<{ id: number; file: string } | null>(null);
  const [open, setOpen] = useState(false);
  const job = useStore((s) => (req ? s.jobs[req.id] : undefined));
  const fail = useStore((s) => s.fail);

  useEffect(() => { if (job?.status === "tayyor") setOpen(true); }, [job?.status]);

  const start = async () => {
    const t = Math.max(0, frameToSec(player.frame, fps) - 5);
    try {
      player.pause();
      setOpen(false);
      setReq(await api.preview(name, Math.round(t * 1000) / 1000, 10));
    } catch (e) { fail(e); }
  };

  return (
    <>
      {req && job && job.status !== "tayyor" ? <StatusBadge status={job.status} progress={job.progress} /> : null}
      {req && !job ? <StatusBadge status="navbatda" /> : null}
      <button className="btn-primary" onClick={start}>Haqiqiy koʻrinish</button>
      {open && req ? (
        <div className="overlay" onClick={() => setOpen(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-head">
              <span className="heading">Haqiqiy koʻrinish</span>
              <button className="btn-ghost" onClick={() => setOpen(false)}>Yopish</button>
            </div>
            <video src={`${urls.file(name, req.file)}?v=${req.id}`} controls autoPlay />
          </div>
        </div>
      ) : null}
    </>
  );
}
