// Tekshirish amallari -> server buyrug'i {label, values}. Sof funksiyalar; null = o'zgarish yo'q.
import { indexAt, mergeAt, moveBoundary, setRange, splitAt } from "./spans";
import { frameToSec, msToFrame, type Fps } from "./time";
import type { LayoutSpan, Project, SlideSpan, Word } from "./types";

export interface Cmd { label: string; values: Record<string, unknown> }

const manual: Partial<SlideSpan> = { source: "manual" };
const changed = <T>(a: T[], b: T[]) => a !== b;

/** b-chegarani `to` kadrga surish (server qoplash invariantini tekshiradi; bu yerda ham saqlanadi). */
export function moveBoundaryCmd(p: Project, b: number, to: number): Cmd | null {
  const spans = moveBoundary(p.slide_spans, b, to, manual);
  if (!changed(spans, p.slide_spans)) return null;
  const layout = followSlide(p.layout_spans, p.slide_spans[b].end, spans[b].end, spans[b + 1].end);
  return { label: "Chegarani surish", values: layout ? { slide_spans: spans, layout_spans: layout } : { slide_spans: spans } };
}

/** Slayd chegarasi old -> neu surilganda shu chegaraga bog'langan tavsiya sahnalari (A boshi va undan keyingi
 * A->B) ham birga suriladi — aks holda sahna slayddan oldin/keyin almashadi (DSBA9600: 7 s). Qo'lda o'zgartirilgan
 * sahnaga tegilmaydi. */
function followSlide(ls: LayoutSpan[], old: number, neu: number, slideEnd: number): LayoutSpan[] | null {
  const k = ls.findIndex((s, i) => i > 0 && s.start === old && s.suggested && ls[i - 1].suggested);
  if (k < 0) return null;
  const d = neu - old;
  let out = ls;
  const next = ls[k + 1];
  // A->B chegarasi (agar shu slayd ichida bo'lsa) — avval, siljish yo'nalishiga qarab tartib buzilmasin
  const moveNext = () => { if (next && next.suggested && next.start < slideEnd - d) out = moveBoundary(out, k, Math.min(next.start + d, slideEnd - 1)); };
  if (d > 0) moveNext();
  out = moveBoundary(out, k - 1, neu);
  if (d < 0) moveNext();
  return out === ls ? null : out;
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

/** setRange bir xil sahnali qo'shnilarni birlashtiradi va chapdagining "suggested" belgisi qoladi — inson tanlovi
 * yo'qolib, "Slaydlarga moslash" uni qaytarardi. [start, end) ni qamragan oraliq qo'lda deb belgilanadi. */
function markManual(spans: LayoutSpan[], start: number, end: number): LayoutSpan[] {
  return spans.map((s) => (s.start < end && start < s.end ? { ...s, suggested: false } : s));
}

/** Playhead ostidagi slayd oralig'i uchun sahna turi (layout_spans kerak bo'lsa bo'linadi). */
export function setSceneCmd(p: Project, frame: number, layout: LayoutSpan["layout"]): Cmd | null {
  const si = indexAt(p.slide_spans, frame);
  const [start, end] = si >= 0 ? [p.slide_spans[si].start, p.slide_spans[si].end] : [0, p.total_frames];
  const base: LayoutSpan[] = p.layout_spans.length
    ? p.layout_spans : [{ start: 0, end: p.total_frames, layout: "A", suggested: true }];
  const raw = setRange(base, start, end, "layout", layout, { suggested: false });
  const same = (xs: LayoutSpan[]) => JSON.stringify(xs.map((s) => [s.start, s.end, s.layout]));
  if (p.layout_spans.length && same(raw) === same(p.layout_spans)) return null;   // sahna o'zgarmadi
  const spans = markManual(raw, start, end);
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

/** Videoda slaydlarning 60% idan kami topilgan bo'lsa — taqdimot fayli videodagisidan farq qiladi
 * (DSBA8915: 36 tadan 15 tasi; boshqa darslarda 79–100%). null — hammasi joyida yoki hali sinxron qilinmagan. */
export function slideMismatch(p: Project): string | null {
  const n = p.slides.length;
  if (!p.slide_spans.length || n < 8) return null;
  const shown = new Set(p.slide_spans.map((s) => s.slide)).size;
  return shown / n < 0.6
    ? `Videoda ${n} ta slayddan faqat ${shown} tasi topildi: taqdimot fayli videodagi taqdimotdan farq qilayotganga ` +
      "oʻxshaydi — 1-qadamda toʻgʻri faylni tanlang (“Taqdimotni almashtirish”)."
    : null;
}

/** Kadr so'z ichida bo'lsa — eng yaqin so'zlar orasidagi bo'shliq o'rtasiga (kesish so'zni qirqmasin). */
export function snapOutOfWord(frame: number, words: Word[], fps: Fps): number {
  const ms = frameToSec(frame, fps) * 1000;
  const k = words.findIndex((w) => w.start_ms < ms && ms < w.end_ms);
  if (k < 0) return frame;
  const w = words[k];
  const before = k > 0 ? (words[k - 1].end_ms + w.start_ms) / 2 : w.start_ms;
  const after = k + 1 < words.length ? (w.end_ms + words[k + 1].start_ms) / 2 : w.end_ms;
  return msToFrame(ms - before <= after - ms ? before : after, fps);
}

/** Qo'lda kesish (timeline'dagi kesish asbobi yoki matndan); aynan shunday kesish bo'lsa — qo'shilmaydi. */
export function addCutCmd(p: Project, start: number, end: number, label = "Timeline'dan kesish"): Cmd | null {
  const s = Math.max(0, Math.min(start, end)), e = Math.min(p.total_frames, Math.max(start, end));
  if (e - s < 1 || p.cuts.some((c) => c.start === s && c.end === e && c.status === "tasdiqlangan")) return null;
  return { label, values: { cuts: [...p.cuts, { start: s, end: e, reason: "manual", status: "tasdiqlangan" }] } };
}

/** Kesishni cheti bo'yicha kengaytirish/toraytirish: inson qarori — qo'lda, tasdiqlangan. */
export function resizeCutCmd(p: Project, i: number, edge: "start" | "end", to: number): Cmd | null {
  const c = p.cuts[i];
  if (!c) return null;
  const f = Math.max(0, Math.min(p.total_frames, Math.round(to)));
  const [start, end] = edge === "start" ? [Math.min(f, c.end - 1), c.end] : [c.start, Math.max(f, c.start + 1)];
  if (start === c.start && end === c.end) return null;
  return { label: "Kesish chegarasi", values: { [`cuts.${i}`]: { ...c, start, end, reason: "manual", status: "tasdiqlangan" } } };
}

/** Sahna chegarasini surish (i — o'ng tomondagi oraliq; boshi = chapdagining oxiri). */
export function moveSceneBoundaryCmd(p: Project, i: number, to: number): Cmd | null {
  if (i <= 0 || i >= p.layout_spans.length) return null;
  const spans = moveBoundary(p.layout_spans, i - 1, to, { suggested: false });
  return changed(spans, p.layout_spans) ? { label: "Sahna chegarasi", values: { layout_spans: spans } } : null;
}

/** Sahna A <-> B (ikki marta bosish). */
export function toggleSceneCmd(p: Project, i: number): Cmd | null {
  const s = p.layout_spans[i];
  if (!s) return null;
  const layout = s.layout === "A" ? "B" : "A";
  const spans = markManual(setRange(p.layout_spans, s.start, s.end, "layout", layout, { suggested: false }), s.start, s.end);
  return { label: `Sahna ${layout}`, values: { layout_spans: spans } };
}
