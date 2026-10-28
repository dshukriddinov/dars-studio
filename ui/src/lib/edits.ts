// Tekshirish amallari -> server buyrug'i {label, values}. Sof funksiyalar; null = o'zgarish yo'q.
import { indexAt, mergeAt, moveBoundary, setRange, splitAt } from "./spans";
import type { LayoutSpan, Project, SlideSpan } from "./types";

export interface Cmd { label: string; values: Record<string, unknown> }

const manual: Partial<SlideSpan> = { source: "manual" };
const changed = <T>(a: T[], b: T[]) => a !== b;

/** b-chegarani `to` kadrga surish (server qoplash invariantini tekshiradi; bu yerda ham saqlanadi). */
export function moveBoundaryCmd(p: Project, b: number, to: number): Cmd | null {
  const spans = moveBoundary(p.slide_spans, b, to, manual);
  return changed(spans, p.slide_spans) ? { label: "Chegarani surish", values: { slide_spans: spans } } : null;
}

/** Javob (animatsiya qadami) vaqtini surish: shu slaydning qo'shni qadamlari orasida, qo'lda belgilangan. */
export function moveAnimStepCmd(p: Project, i: number, to: number): Cmd | null {
  const steps = p.anim_steps ?? [];
  const s = steps[i];
  if (!s) return null;
  const same = steps.filter((x) => x.slide === s.slide);
  const lo = Math.max(0, ...same.filter((x) => x.click < s.click).map((x) => x.frame + 1));
  const hi = Math.min(p.total_frames - 1, ...same.filter((x) => x.click > s.click).map((x) => x.frame - 1));
  const frame = Math.max(lo, Math.min(hi, Math.round(to)));
  if (frame === s.frame) return null;
  return { label: "Javob vaqti", values: { anim_steps: steps.map((x, k) => (k === i ? { ...x, frame, source: "manual" } : x)) } };
}

export function splitSlideCmd(p: Project, frame: number): Cmd | null {
  const spans = splitAt(p.slide_spans, frame, manual);
  return changed(spans, p.slide_spans) ? { label: "Chegara qoʻshish", values: { slide_spans: spans } } : null;
}

export function mergeSlideCmd(p: Project, b: number): Cmd | null {
  const spans = mergeAt(p.slide_spans, b);
  return changed(spans, p.slide_spans) ? { label: "Chegarani oʻchirish", values: { slide_spans: spans } } : null;
}

export function setSlideCmd(p: Project, i: number, slide: number): Cmd | null {
  const s = p.slide_spans[i];
  if (!s || s.slide === slide) return null;
  return { label: `Slayd ${slide}`, values: { slide_spans: setRange(p.slide_spans, s.start, s.end, "slide", slide, manual) } };
}

/** Playhead ostidagi slayd oralig'i uchun sahna turi (layout_spans kerak bo'lsa bo'linadi). */
export function setSceneCmd(p: Project, frame: number, layout: LayoutSpan["layout"]): Cmd | null {
  const si = indexAt(p.slide_spans, frame);
  const [start, end] = si >= 0 ? [p.slide_spans[si].start, p.slide_spans[si].end] : [0, p.total_frames];
  const base: LayoutSpan[] = p.layout_spans.length
    ? p.layout_spans : [{ start: 0, end: p.total_frames, layout: "A", suggested: true }];
  const spans = setRange(base, start, end, "layout", layout, { suggested: false });
  if (JSON.stringify(spans) === JSON.stringify(p.layout_spans)) return null;
  return { label: `Sahna ${layout}`, values: { layout_spans: spans } };
}

export function cutStatusCmd(p: Project, i: number, status: "tasdiqlangan" | "rad_etilgan"): Cmd | null {
  const c = p.cuts[i];
  if (!c || c.status === status) return null;
  return { label: status === "tasdiqlangan" ? "Kesishni tasdiqlash" : "Kesishni rad etish", values: { [`cuts.${i}.status`]: status } };
}

export function approveAllCutsCmd(p: Project): Cmd | null {
  if (!p.cuts.some((c) => c.status === "taklif")) return null;
  return {
    label: "Hammasini tasdiqlash",
    values: { cuts: p.cuts.map((c) => (c.status === "taklif" ? { ...c, status: "tasdiqlangan" } : c)) },
  };
}

export function addEyeOffCmd(p: Project, a: number, b: number): Cmd | null {
  const start = Math.max(0, Math.min(a, b)), end = Math.min(p.total_frames, Math.max(a, b));
  if (end <= start) return null;
  const eye_off = [...p.eye_off, { start, end }].sort((x, y) => x.start - y.start);
  return { label: "Eye Contact oʻchiq oraliq", values: { eye_off } };
}

export function removeEyeOffCmd(p: Project, i: number): Cmd | null {
  if (!p.eye_off[i]) return null;
  return { label: "Eye Contact oraligʻini oʻchirish", values: { eye_off: p.eye_off.filter((_, j) => j !== i) } };
}
