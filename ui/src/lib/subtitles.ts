import type { Span, Word } from "./types";
import { msToFrame, type Fps } from "./time";

export interface Cue extends Span { text: string }

/** So'zlarni subtitr qatorlariga guruhlash (FR-17 ga yaqin: ≤42 belgi, ≤7 s, 0.7 s pauzada bo'lish). */
export function groupWords(words: Word[], fps: Fps): Cue[] {
  const cues: Cue[] = [];
  let cur: { text: string; s: number; e: number } | null = null;
  const flush = () => {
    if (!cur) return;
    const start = msToFrame(cur.s, fps);
    cues.push({ text: cur.text, start, end: Math.max(msToFrame(cur.e, fps), start + 1) });
    cur = null;
  };
  for (const w of words) {
    if (cur && (w.start_ms - cur.e > 700 || w.end_ms - cur.s > 7000 || cur.text.length + 1 + w.text.length > 42)) flush();
    cur = cur ? { text: `${cur.text} ${w.text}`, s: cur.s, e: w.end_ms } : { text: w.text, s: w.start_ms, e: w.end_ms };
  }
  flush();
  return cues;
}
