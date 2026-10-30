// Timeline (FR-14), montaj dasturlari uslubida:
//  - Alt (yoki Ctrl) + g'ildirak — kursor ostidagi joy atrofida yaqinlashtirish/uzoqlashtirish; g'ildirak — gorizontal
//    surish; o'rta tugma bilan sudrash — surish; = / - — masshtab, \ — butun dars, Home/End — boshi/oxiri;
//  - o'lchov chizig'i (soniyalar, yaqinlashganda kadrlar), sichqoncha ostidagi vaqt; o'lchovda sudrab ko'rish (scrub);
//  - slayd chegarasini sudrab surish (playhead'ga yopishadi), slayd ichida kichik rasm, audio to'lqin;
//  - umumiy ko'rinish (minimap): butun dars, ko'rinib turgan oyna sudraladi.
// Faqat ko'rinadigan elementlar chiziladi (virtualizatsiya); playhead React'dan tashqarida yangilanadi.
import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Maximize2, Minus, Plus, Crosshair, Scissors } from "lucide-react";
import { player } from "../lib/player";
import { visibleSlice } from "../lib/spans";
import type { Span } from "../lib/types";

export interface Item extends Span { i: number; text?: string; cls?: string; thumb?: string }
export interface Lane {
  id: string; label: string; items: Item[]; maxLen: number; boundaries?: boolean; tall?: boolean;
  drag?: boolean | "both";   // element boshini (both: boshi va oxirini) sudrab surish (onItemDrag)
}
export type Edge = "start" | "end";

interface Props {
  total: number;
  lanes: Lane[];
  selected?: Record<string, number>;          // lane id -> tanlangan element indeksi (Item.i)
  selectedBoundary?: number;                   // slayd chegarasi indeksi
  onItemClick?: (lane: string, i: number, frame: number) => void;
  onBoundaryClick?: (b: number) => void;
  onBoundaryDrag?: (b: number, frame: number) => void;
  onItemDrag?: (lane: string, i: number, frame: number, edge: Edge) => void;
  onItemDouble?: (lane: string, i: number) => void;   // ikki marta bosish (masalan sahna A <-> B)
  onRangeCut?: (start: number, end: number) => void;  // kesish asbobi (C): timeline'da sudrab belgilangan oraliq
  onSeek: (frame: number) => void;
  waveform?: Uint8Array | null;                // har kadrga cho'qqi (0..255)
  overview?: Span[];                           // minimap'da belgilanadigan oraliqlar (masalan kesishlar)
  width?: number;                              // test uchun (jsdom'da o'lcham yo'q)
  pxPerFrame?: number;
}

const LANE_H = 26, TALL_H = 40, WAVE_H = 40, RULER_H = 26;
const OVERSCAN = 200;       // px
const MAX_PPF = 24;         // 1 kadr = 24 px
const SNAP_PX = 8;

export function laneMaxLen(items: Span[]) {
  let m = 0;
  for (const s of items) m = Math.max(m, s.end - s.start);
  return m;
}

const fpsNum = () => player.fps.num / player.fps.den;
export function fmtTc(f: number, withFrames = false): string {
  const fps = fpsNum();
  const s = Math.floor(f / fps);
  const base = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  return withFrames ? `${base}.${String(Math.round(f - s * fps)).padStart(2, "0")}` : base;
}

export function Timeline({ total, lanes, selected = {}, selectedBoundary = -1, onItemClick, onBoundaryClick,
  onBoundaryDrag, onItemDrag, onItemDouble, onRangeCut, onSeek, waveform, overview = [], width: fixedWidth,
  pxPerFrame }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fixedWidth ?? 1000);
  const [scroll, setScroll] = useState(0);
  const fit = Math.max(width - 2, 1) / Math.max(total, 1);
  const [ppf, setPpf] = useState(pxPerFrame ?? 0);
  const zoom = ppf || fit;
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const [follow, setFollow] = useState(true);
  const followRef = useRef(follow);
  followRef.current = follow;
  const [hover, setHover] = useState<number | null>(null);
  const [drag, setDrag] = useState<{ b: number; frame: number } | null>(null);
  const [razor, setRazor] = useState(false);
  const [range, setRange] = useState<[number, number] | null>(null);
  const pendingAnchor = useRef<{ frame: number; px: number } | null>(null);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el || fixedWidth || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth || 1000));
    ro.observe(el);
    return () => ro.disconnect();
  }, [fixedWidth]);

  // masshtab o'zgargach: langar kadr ekranda o'z joyida qolsin
  useLayoutEffect(() => {
    const el = scrollRef.current, a = pendingAnchor.current;
    if (!el || !a) return;
    pendingAnchor.current = null;
    el.scrollLeft = Math.max(0, a.frame * zoom - a.px);
    setScroll(el.scrollLeft);
  }, [zoom]);

  // Playhead: DOM to'g'ridan; ijroda ko'rinishdan chiqsa (kuzatish yoqilgan bo'lsa) sahifa suriladi
  useEffect(() => {
    const place = (f: number) => {
      const x = f * zoomRef.current;
      if (headRef.current) headRef.current.style.transform = `translateX(${x}px)`;
      const el = scrollRef.current;
      if (el && followRef.current && player.playing && (x < el.scrollLeft || x > el.scrollLeft + el.clientWidth - 40)) {
        el.scrollLeft = x - el.clientWidth * 0.1;
      }
    };
    place(player.frame);
    return player.subscribe(place);
  }, [zoom]);

  const raf = useRef(0);
  const onScroll = () => {
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => setScroll(scrollRef.current?.scrollLeft ?? 0));
  };

  const setZoom = useCallback((next: number, anchorPx?: number) => {
    const el = scrollRef.current;
    const z = Math.min(MAX_PPF, Math.max(fit, next));
    const px = anchorPx ?? (el ? Math.min(el.clientWidth, Math.max(0, player.frame * zoomRef.current - el.scrollLeft)) : 0);
    pendingAnchor.current = { frame: ((el?.scrollLeft ?? 0) + px) / zoomRef.current, px };
    setPpf(z <= fit * 1.0001 ? 0 : z);
  }, [fit]);

  // g'ildirak: passive emas (preventDefault ishlashi uchun)
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const rect = el.getBoundingClientRect();
        const k = Math.exp(-e.deltaY * 0.0025);           // oldinga — yaqinlashadi, orqaga — uzoqlashadi
        setZoom(zoomRef.current * k, e.clientX - rect.left);
      } else if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        el.scrollLeft += e.deltaY;                         // oddiy g'ildirak — gorizontal surish
      }
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [setZoom]);

  // klaviatura: = / - masshtab, \ butun dars, Home / End
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t?.closest?.("input, select, textarea") || e.ctrlKey || e.metaKey) return;
      if (e.key === "=" || e.key === "+") { e.preventDefault(); setZoom(zoomRef.current * 1.6); }
      else if (e.key === "-") { e.preventDefault(); setZoom(zoomRef.current / 1.6); }
      else if (e.key === "\\") { e.preventDefault(); setZoom(0); }
      else if (e.key === "Home") { e.preventDefault(); onSeek(0); if (scrollRef.current) scrollRef.current.scrollLeft = 0; }
      else if (e.key === "End") { e.preventDefault(); onSeek(total - 1); }
      else if (onRangeCut && (e.key === "c" || e.key === "C") && !e.altKey) { e.preventDefault(); setRazor((r) => !r); }
      else if (e.key === "Escape") setRazor(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setZoom, onSeek, total, onRangeCut]);

  const frameAt = (clientX: number) => {
    const el = scrollRef.current;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    return Math.max(0, Math.min(total - 1, Math.floor((clientX - r.left + el.scrollLeft) / zoomRef.current)));
  };

  // sudrash: o'lchovda scrub, o'rta tugma bilan surish, slayd chegarasi
  type Kind = "scrub" | "pan" | { b: number; lane?: string; edge?: Edge } | { range: number };
  const startDrag = (e: React.MouseEvent, kind: Kind) => {
    e.preventDefault();
    const el = scrollRef.current;
    const x0 = e.clientX, s0 = el?.scrollLeft ?? 0;
    let last = -1;
    const move = (ev: MouseEvent) => {
      if (kind === "pan") { if (el) el.scrollLeft = s0 - (ev.clientX - x0); return; }
      let f = frameAt(ev.clientX);
      if (kind === "scrub") { if (f !== last) { last = f; onSeek(f); } return; }
      if (Math.abs((f - player.frame) * zoomRef.current) <= SNAP_PX) f = player.frame;   // playhead'ga yopishadi
      if ("range" in kind) { setRange([Math.min(kind.range, f), Math.max(kind.range, f)]); return; }
      setDrag({ b: kind.b, frame: f });
    };
    const up = (ev: MouseEvent) => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      if (typeof kind === "object") {
        let f = frameAt(ev.clientX);
        if (Math.abs((f - player.frame) * zoomRef.current) <= SNAP_PX) f = player.frame;
        setDrag(null);
        setRange(null);
        if ("range" in kind) {
          const [a, b] = [Math.min(kind.range, f), Math.max(kind.range, f)];
          if (b - a >= 2) onRangeCut?.(a, b + 1);
        } else if (Math.abs(ev.clientX - x0) > 2) {
          if (kind.lane) onItemDrag?.(kind.lane, kind.b, f, kind.edge ?? "start"); else onBoundaryDrag?.(kind.b, f);
        }
      }
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    if (kind === "scrub") onSeek(frameAt(e.clientX));
  };

  const from = (scroll - OVERSCAN) / zoom, to = (scroll + width + OVERSCAN) / zoom;
  const zoomPct = Math.round(Math.log(zoom / fit) / Math.log(MAX_PPF / fit) * 100) || 0;

  return (
    <div className="ntl">
      <div className="ntl-bar">
        <button className="btn-icon sm" onClick={() => setZoom(zoom / 1.6)} aria-label="Uzoqlashtirish (−)" title="Uzoqlashtirish (−)">
          <Minus size={14} /></button>
        <input type="range" min={0} max={100} value={zoomPct} aria-label="Masshtab" className="ntl-zoom"
          onChange={(e) => setZoom(fit * Math.pow(MAX_PPF / fit, Number(e.target.value) / 100))} />
        <button className="btn-icon sm" onClick={() => setZoom(zoom * 1.6)} aria-label="Yaqinlashtirish (=)" title="Yaqinlashtirish (=)">
          <Plus size={14} /></button>
        <button className="btn-ghost sm" onClick={() => setZoom(0)} title="Butun dars (\)"><Maximize2 size={14} /> Butun dars</button>
        <button className={`btn-ghost sm${follow ? " on" : ""}`} onClick={() => setFollow(!follow)}
          title="Ijroda timeline playhead ortidan yursin"><Crosshair size={14} /> Kuzatish</button>
        {onRangeCut ? (
          <button className={`btn-ghost sm${razor ? " on" : ""}`} onClick={() => setRazor(!razor)}
            title="Kesish asbobi (C): timeline ustida sudrab kesiladigan joyni belgilang; Esc — chiqish">
            <Scissors size={14} /> Kesish (C)</button>
        ) : null}
        <span className="spacer" />
        <span className="caption dim">{razor ? "Kesish: sudrab belgilang (Esc — chiqish)"
          : hover !== null ? `Kursor: ${fmtTc(hover, zoom > 4)}` : "Alt + gʻildirak — masshtab, gʻildirak — surish"}</span>
      </div>
      <Overview total={total} marks={overview} scroll={scroll} width={width} zoom={zoom}
        onMove={(frameLeft) => { if (scrollRef.current) scrollRef.current.scrollLeft = frameLeft * zoom; }} />
      <div className="ntl-body">
        <div className="ntl-heads">
          <div className="ntl-head ruler-head" style={{ height: RULER_H }} />
          {lanes.map((l) => <div key={l.id} className="ntl-head" style={{ height: l.tall ? TALL_H : LANE_H }}>{l.label}</div>)}
          {waveform ? <div className="ntl-head" style={{ height: WAVE_H }}>Ovoz</div> : null}
        </div>
        <div className="tl-scroll ntl-scroll" ref={scrollRef} onScroll={onScroll}
          onMouseMove={(e) => setHover(frameAt(e.clientX))} onMouseLeave={() => setHover(null)}
          onMouseDown={(e) => { if (e.button === 1) startDrag(e, "pan"); }}>
          <div className={`tl-inner${razor ? " razor" : ""}`} style={{ width: Math.max(total * zoom, 1) }}
            onMouseDownCapture={(e) => {
              if (!razor || e.button !== 0 || (e.target as HTMLElement).closest(".ntl-ruler")) return;
              e.stopPropagation();
              startDrag(e, { range: frameAt(e.clientX) });
            }}
            onMouseDown={(e) => {
              if (e.button === 0 && (e.target as HTMLElement).dataset.bg !== undefined) onSeek(frameAt(e.clientX));
            }}>
            <Ruler total={total} zoom={zoom} from={from} to={to} onScrub={(e) => startDrag(e, "scrub")} />
            {lanes.map((l) => (
              <LaneRow key={l.id} lane={l} zoom={zoom} from={from} to={to} selected={selected[l.id] ?? -1}
                selectedBoundary={l.boundaries ? selectedBoundary : -1}
                onItemClick={onItemClick} onBoundaryClick={onBoundaryClick} onItemDouble={onItemDouble}
                onBoundaryDown={l.drag && onItemDrag ? (e, i, edge) => startDrag(e, { b: i, lane: l.id, edge })
                  : l.boundaries && onBoundaryDrag ? (e, b) => { onBoundaryClick?.(b); startDrag(e, { b }); } : undefined} />
            ))}
            {waveform ? <Wave peaks={waveform} zoom={zoom} scroll={scroll} width={width} /> : null}
            {hover !== null ? <div className="ntl-hover" style={{ transform: `translateX(${hover * zoom}px)` }} /> : null}
            {drag ? <div className="ntl-ghost" style={{ transform: `translateX(${drag.frame * zoom}px)` }}>
              <span>{fmtTc(drag.frame, true)}</span></div> : null}
            {range ? <div className="ntl-range" style={{ left: range[0] * zoom, width: Math.max(1, (range[1] - range[0]) * zoom) }}>
              <span>{fmtTc(range[0], true)} – {fmtTc(range[1], true)}</span></div> : null}
            <div className="tl-playhead ntl-playhead" ref={headRef}><span className="ntl-knob" /></div>
          </div>
        </div>
      </div>
    </div>
  );
}

const STEP_S = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200];
function Ruler({ total, zoom, from, to, onScrub }: {
  total: number; zoom: number; from: number; to: number; onScrub: (e: React.MouseEvent) => void;
}) {
  const fps = fpsNum();
  // yaqinlashganda kadr qadamlari (1, 2, 5, 10 kadr), aks holda soniyalar
  const frameSteps = [1, 2, 5, 10].filter((s) => s < fps);
  const stepF = frameSteps.find((s) => s * zoom >= 70) ?? (STEP_S.find((s) => s * fps * zoom >= 80) ?? 1200) * fps;
  const minor = stepF / 5;
  const ticks = [];
  const lo = Math.max(0, Math.floor(from / stepF) * stepF), hi = Math.min(to, total);
  for (let f = lo; f < hi; f += minor) {
    const major = Math.abs(f / stepF - Math.round(f / stepF)) < 1e-6;
    ticks.push(
      <div key={f} className={`ntl-tick${major ? " major" : ""}`} style={{ left: f * zoom }}>
        {major ? <span>{fmtTc(Math.round(f), stepF < fps)}</span> : null}
      </div>,
    );
  }
  return <div className="tl-ruler ntl-ruler" style={{ height: RULER_H }} onMouseDown={(e) => { if (e.button === 0) onScrub(e); }}>
    {ticks}</div>;
}

interface LaneProps {
  lane: Lane; zoom: number; from: number; to: number; selected: number; selectedBoundary: number;
  onItemClick?: Props["onItemClick"]; onBoundaryClick?: Props["onBoundaryClick"]; onItemDouble?: Props["onItemDouble"];
  onBoundaryDown?: (e: React.MouseEvent, b: number, edge: Edge) => void;
}

const LaneRow = memo(function LaneRow({ lane, zoom, from, to, selected, selectedBoundary, onItemClick, onBoundaryClick,
  onItemDouble, onBoundaryDown }: LaneProps) {
  const [i0, i1] = visibleSlice(lane.items, from, to, lane.maxLen);
  const laneLast = lane.items.length - 1;
  const h = lane.tall ? TALL_H : LANE_H;
  const els = [];
  for (let k = i0; k < i1; k++) {
    const it = lane.items[k];
    const w = Math.max(1, (it.end - it.start) * zoom);
    els.push(
      <div key={it.i} className={`tl-item ${it.cls ?? ""}${it.i === selected ? " sel" : ""}`} data-item={lane.id}
        style={{ left: it.start * zoom, width: w }} title={it.text}
        onMouseDown={(e) => {
          if (e.button !== 0) return;
          e.stopPropagation();
          const rect = (e.currentTarget.parentElement as HTMLElement).getBoundingClientRect();
          onItemClick?.(lane.id, it.i, Math.floor((e.clientX - rect.left) / zoom));
        }}
        onDoubleClick={onItemDouble ? () => onItemDouble(lane.id, it.i) : undefined}>
        {w > 24 ? (
          <span className="tl-stick">
            {it.thumb && w > 90 ? <img className="tl-thumb" src={it.thumb} alt="" loading="lazy" draggable={false} /> : null}
            {it.text ? <span className="tl-text">{it.text}</span> : null}
          </span>
        ) : null}
        {lane.boundaries && it.i > 0 ? (
          <span className={`tl-bound${it.i - 1 === selectedBoundary ? " sel" : ""}`} title="Chegara: sudrab suring"
            onMouseDown={(e) => {
              e.stopPropagation();
              if (onBoundaryDown) onBoundaryDown(e, it.i - 1, "start"); else onBoundaryClick?.(it.i - 1);
            }} />
        ) : null}
        {lane.boundaries && it.i < laneLast ? (
          <span className={`tl-bound end${it.i === selectedBoundary ? " sel" : ""}`} title="Chegara: sudrab suring"
            onMouseDown={(e) => {
              e.stopPropagation();
              if (onBoundaryDown) onBoundaryDown(e, it.i, "start"); else onBoundaryClick?.(it.i);
            }} />
        ) : null}
        {!lane.boundaries && lane.drag ? (
          <span className="tl-bound" title="Boshini sudrab suring"
            onMouseDown={(e) => { e.stopPropagation(); onBoundaryDown?.(e, it.i, "start"); }} />
        ) : null}
        {lane.drag === "both" ? (
          <span className="tl-bound end" title="Oxirini sudrab suring"
            onMouseDown={(e) => { e.stopPropagation(); onBoundaryDown?.(e, it.i, "end"); }} />
        ) : null}
      </div>,
    );
  }
  return <div className="tl-lane" data-bg="" style={{ height: h }}>{els}</div>;
});

/** Audio to'lqin: faqat ko'rinadigan qism canvas'ga chiziladi. */
function Wave({ peaks, zoom, scroll, width }: { peaks: Uint8Array; zoom: number; scroll: number; width: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.max(1, Math.round(width * dpr));
    c.height = Math.round(WAVE_H * dpr);
    const g = c.getContext("2d");
    if (!g) return;
    g.scale(dpr, dpr);
    g.clearRect(0, 0, width, WAVE_H);
    g.fillStyle = getComputedStyle(c).color || "#5b6782";
    const mid = WAVE_H / 2;
    for (let x = 0; x < width; x++) {
      const f0 = Math.floor((scroll + x) / zoom), f1 = Math.max(f0 + 1, Math.floor((scroll + x + 1) / zoom));
      let m = 0;
      for (let f = f0; f < f1 && f < peaks.length; f++) if (peaks[f] > m) m = peaks[f];
      const hgt = Math.max(1, (m / 255) * (mid - 2));
      g.fillRect(x, mid - hgt, 1, hgt * 2);
    }
  }, [peaks, zoom, scroll, width]);
  return (
    <div className="tl-lane ntl-wave" data-bg="" style={{ height: WAVE_H }}>
      <canvas ref={ref} style={{ position: "absolute", left: scroll, width, height: WAVE_H }} data-bg="" />
    </div>
  );
}

/** Umumiy ko'rinish: butun dars, belgilar va ko'rinib turgan oyna (sudraladi). */
function Overview({ total, marks, scroll, width, zoom, onMove }: {
  total: number; marks: Span[]; scroll: number; width: number; zoom: number; onMove: (frameLeft: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const pct = (f: number) => `${(f / Math.max(1, total)) * 100}%`;
  const viewF = width / zoom, leftF = scroll / zoom;
  const toFrame = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect();
    return ((clientX - r.left) / r.width) * total;
  };
  const down = (e: React.MouseEvent) => {
    e.preventDefault();
    const go = (x: number) => onMove(Math.max(0, toFrame(x) - viewF / 2));
    go(e.clientX);
    const move = (ev: MouseEvent) => go(ev.clientX);
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };
  return (
    <div className="ntl-over" ref={ref} onMouseDown={down} title="Butun dars: bosib yoki sudrab oʻting">
      {marks.map((m, i) => <span key={i} className="ntl-over-mark" style={{ left: pct(m.start), width: `max(1px, ${pct(m.end - m.start)})` }} />)}
      <span className="ntl-over-view" style={{ left: pct(leftF), width: `max(6px, ${pct(viewF)})` }} />
    </div>
  );
}
