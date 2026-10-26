// Timeline (FR-14): yo'laklar bitta absolyut qatlamda, faqat ko'rinadigan elementlar chiziladi (virtualizatsiya).
// Playhead React'dan tashqarida (player.subscribe) yangilanadi.
import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { player } from "../lib/player";
import { visibleSlice } from "../lib/spans";
import type { Span } from "../lib/types";

export interface Item extends Span { i: number; text?: string; cls?: string }
export interface Lane { id: string; label: string; items: Item[]; maxLen: number; boundaries?: boolean }

interface Props {
  total: number;
  lanes: Lane[];
  selected?: Record<string, number>;          // lane id -> tanlangan element indeksi (Item.i)
  selectedBoundary?: number;                   // slayd chegarasi indeksi
  onItemClick?: (lane: string, i: number, frame: number) => void;
  onBoundaryClick?: (b: number) => void;
  onSeek: (frame: number) => void;
  width?: number;                              // test uchun (jsdom'da o'lcham yo'q)
  pxPerFrame?: number;
}

const LANE_H = 28;
const OVERSCAN = 200; // px

export function laneMaxLen(items: Span[]) {
  let m = 0;
  for (const s of items) m = Math.max(m, s.end - s.start);
  return m;
}

export function Timeline({ total, lanes, selected = {}, selectedBoundary = -1, onItemClick, onBoundaryClick, onSeek,
  width: fixedWidth, pxPerFrame }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fixedWidth ?? 1000);
  const [scroll, setScroll] = useState(0);
  const fit = Math.max(width - 2, 1) / Math.max(total, 1);
  const [ppf, setPpf] = useState(pxPerFrame ?? 0);
  const zoom = ppf || fit;
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el || fixedWidth || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth || 1000));
    ro.observe(el);
    return () => ro.disconnect();
  }, [fixedWidth]);

  // Playhead: DOM'ni to'g'ridan-to'g'ri siljitish; ijroda ko'rinishdan chiqsa sahifa suriladi.
  useEffect(() => {
    const place = (f: number) => {
      const x = f * zoomRef.current;
      if (headRef.current) headRef.current.style.transform = `translateX(${x}px)`;
      const el = scrollRef.current;
      if (el && player.playing && (x < el.scrollLeft || x > el.scrollLeft + el.clientWidth - 20)) {
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
    const max = 12, min = fit;
    const z = Math.min(max, Math.max(min, next));
    const ax = anchorPx ?? (el ? el.clientWidth / 2 : 0);
    const frameAt = ((el?.scrollLeft ?? 0) + ax) / zoomRef.current;
    setPpf(z === min ? 0 : z);
    requestAnimationFrame(() => {
      if (el) { el.scrollLeft = frameAt * z - ax; setScroll(el.scrollLeft); }
    });
  }, [fit]);

  const onWheel = (e: React.WheelEvent) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    const rect = scrollRef.current!.getBoundingClientRect();
    setZoom(zoom * (e.deltaY < 0 ? 1.25 : 0.8), e.clientX - rect.left);
  };

  const frameFromEvent = (e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    return Math.floor((e.clientX - rect.left) / zoom);
  };

  const from = (scroll - OVERSCAN) / zoom, to = (scroll + width + OVERSCAN) / zoom;

  return (
    <div className="timeline">
      <div className="tl-labels">
        <div className="tl-ruler-label">
          <button className="btn-icon sm" onClick={() => setZoom(zoom * 0.5)} aria-label="Kichraytirish">−</button>
          <button className="btn-icon sm" onClick={() => setZoom(zoom * 2)} aria-label="Kattalashtirish">+</button>
        </div>
        {lanes.map((l) => <div key={l.id} className="tl-label label">{l.label}</div>)}
      </div>
      <div className="tl-scroll" ref={scrollRef} onScroll={onScroll} onWheel={onWheel}>
        <div className="tl-inner" style={{ width: Math.max(total * zoom, 1) }} onMouseDown={(e) => {
          if (e.button === 0 && (e.target as HTMLElement).dataset.bg !== undefined) onSeek(frameFromEvent(e));
        }}>
          <Ruler total={total} zoom={zoom} from={from} to={to} />
          {lanes.map((l) => (
            <LaneRow key={l.id} lane={l} zoom={zoom} from={from} to={to} selected={selected[l.id] ?? -1}
              selectedBoundary={l.boundaries ? selectedBoundary : -1}
              onItemClick={onItemClick} onBoundaryClick={onBoundaryClick} />
          ))}
          <div className="tl-playhead" ref={headRef} />
        </div>
      </div>
    </div>
  );
}

const STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200]; // soniya
function Ruler({ total, zoom, from, to }: { total: number; zoom: number; from: number; to: number }) {
  const fps = player.fps.num / player.fps.den;
  const step = STEPS.find((s) => s * fps * zoom >= 80) ?? 1200;
  const ticks = [];
  for (let s = Math.max(0, Math.floor(from / fps / step) * step); s * fps < Math.min(to, total); s += step) {
    ticks.push(
      <div key={s} className="tl-tick caption" style={{ left: s * fps * zoom }}>
        {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}
      </div>,
    );
  }
  return <div className="tl-ruler" data-bg="">{ticks}</div>;
}

interface LaneProps {
  lane: Lane; zoom: number; from: number; to: number; selected: number; selectedBoundary: number;
  onItemClick?: Props["onItemClick"]; onBoundaryClick?: Props["onBoundaryClick"];
}

const LaneRow = memo(function LaneRow({ lane, zoom, from, to, selected, selectedBoundary, onItemClick, onBoundaryClick }: LaneProps) {
  const [i0, i1] = visibleSlice(lane.items, from, to, lane.maxLen);
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
        }}>
        {w > 24 && it.text ? <span className="tl-text">{it.text}</span> : null}
        {lane.boundaries && it.i > 0 ? (
          <span className={`tl-bound${it.i - 1 === selectedBoundary ? " sel" : ""}`} title="Chegara"
            onMouseDown={(e) => { e.stopPropagation(); onBoundaryClick?.(it.i - 1); }} />
        ) : null}
      </div>,
    );
  }
  return <div className="tl-lane" data-bg="" style={{ height: LANE_H }}>{els}</div>;
});
