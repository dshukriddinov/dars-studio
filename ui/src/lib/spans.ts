// Qoplovchi oraliqlar (slide_spans, layout_spans) ustida sof amallar. Natija [0,total) ni bo'shliqsiz qoplaydi.
import type { Span } from "./types";

/** frame ni o'z ichiga olgan oraliq indeksi (start bo'yicha tartiblangan ro'yxat), yo'q bo'lsa -1. */
export function indexAt<T extends Span>(spans: T[], frame: number): number {
  let lo = 0, hi = spans.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (frame < spans[mid].start) hi = mid - 1;
    else if (frame >= spans[mid].end) lo = mid + 1;
    else return mid;
  }
  return -1;
}

/** b-chegara = spans[b].end = spans[b+1].start. Ikkala oraliq kamida 1 kadr qoladi. */
export function moveBoundary<T extends Span>(spans: T[], b: number, frame: number, patch: Partial<T> = {}): T[] {
  if (b < 0 || b >= spans.length - 1) return spans;
  const f = Math.min(Math.max(Math.round(frame), spans[b].start + 1), spans[b + 1].end - 1);
  if (f === spans[b].end) return spans;
  const out = spans.slice();
  out[b] = { ...out[b], ...patch, end: f };
  out[b + 1] = { ...out[b + 1], ...patch, start: f };
  return out;
}

/** frame da bo'lish; frame allaqachon chegara yoki tashqarida bo'lsa o'zgarmaydi. */
export function splitAt<T extends Span>(spans: T[], frame: number, patch: Partial<T> = {}): T[] {
  const i = indexAt(spans, frame);
  if (i < 0 || spans[i].start === frame) return spans;
  const out = spans.slice();
  out.splice(i, 1, { ...spans[i], end: frame }, { ...spans[i], ...patch, start: frame });
  return out;
}

/** b-chegarani o'chirish: spans[b+1] spans[b] ga qo'shiladi (chap oraliq qiymatlari saqlanadi). */
export function mergeAt<T extends Span>(spans: T[], b: number): T[] {
  if (b < 0 || b >= spans.length - 1) return spans;
  const out = spans.slice();
  out.splice(b, 2, { ...spans[b], end: spans[b + 1].end });
  return out;
}

/** [start,end) da key=value (kerak bo'lsa bo'lib), so'ng bir xil qiymatli qo'shnilarni birlashtirish. */
export function setRange<T extends Span, K extends keyof T>(spans: T[], start: number, end: number, key: K, value: T[K],
  patch: Partial<T> = {}): T[] {
  const out = splitAt(splitAt(spans, start), end)
    .map((s) => (s.start >= start && s.end <= end ? { ...s, ...patch, [key]: value } : s));
  const merged: T[] = [];
  for (const s of out) {
    const last = merged[merged.length - 1];
    if (last && last[key] === s[key] && last.end === s.start) merged[merged.length - 1] = { ...last, end: s.end };
    else merged.push(s);
  }
  return merged;
}

/** Qoplash invarianti (serverdagi _check_cover bilan bir xil). */
export function isCovering(spans: Span[], total: number): boolean {
  let pos = 0;
  for (const s of spans) {
    if (s.start !== pos || s.end <= s.start) return false;
    pos = s.end;
  }
  return pos === total;
}

/** Ko'rinadigan [from,to) bilan kesishgan elementlar [i0, i1). items start bo'yicha tartiblangan, maxLen — eng uzun element. */
export function visibleSlice(items: Span[], from: number, to: number, maxLen: number): [number, number] {
  let lo = 0, hi = items.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (items[mid].start < from - maxLen) lo = mid + 1; else hi = mid;
  }
  let i0 = lo;
  while (i0 < items.length && items[i0].end <= from) i0++;
  let i1 = i0;
  while (i1 < items.length && items[i1].start < to) i1++;
  return [i0, i1];
}
