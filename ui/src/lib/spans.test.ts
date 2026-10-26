import { describe, expect, it } from "vitest";
import { indexAt, isCovering, mergeAt, moveBoundary, setRange, splitAt, visibleSlice } from "./spans";
import { fmtFrame, frameToSec, msToFrame, parseFps, secToFrame } from "./time";
import { groupWords } from "./subtitles";

const S = (...b: number[]) => b.slice(0, -1).map((s, i) => ({ start: s, end: b[i + 1], v: i }));

describe("spans", () => {
  it("indexAt binary search, half-open", () => {
    const s = S(0, 10, 20, 30);
    expect(indexAt(s, 0)).toBe(0);
    expect(indexAt(s, 9)).toBe(0);
    expect(indexAt(s, 10)).toBe(1);
    expect(indexAt(s, 29)).toBe(2);
    expect(indexAt(s, 30)).toBe(-1);
  });

  it("moveBoundary keeps cover and clamps to ≥1 frame", () => {
    const s = S(0, 10, 20, 30);
    const m = moveBoundary(s, 0, 15);
    expect(m.map((x) => [x.start, x.end])).toEqual([[0, 15], [15, 20], [20, 30]]);
    expect(isCovering(m, 30)).toBe(true);
    expect(moveBoundary(s, 0, 99)[0].end).toBe(19);
    expect(moveBoundary(s, 1, -5)[1].end).toBe(11);
    expect(moveBoundary(s, 2, 25)).toBe(s); // oxirgi oraliqdan keyin chegara yo'q
    expect(moveBoundary(s, 0, 10)).toBe(s); // o'zgarmadi
    expect(s[0].end).toBe(10); // asl ro'yxat o'zgarmaydi
  });

  it("splitAt / mergeAt", () => {
    const s = S(0, 10, 30);
    const sp = splitAt(s, 20, { v: 9 });
    expect(sp.map((x) => [x.start, x.end, x.v])).toEqual([[0, 10, 0], [10, 20, 1], [20, 30, 9]]);
    expect(isCovering(sp, 30)).toBe(true);
    expect(splitAt(s, 10)).toBe(s);
    const mg = mergeAt(sp, 1);
    expect(mg.map((x) => [x.start, x.end, x.v])).toEqual([[0, 10, 0], [10, 30, 1]]);
    expect(isCovering(mg, 30)).toBe(true);
  });

  it("setRange splits then merges equal neighbours", () => {
    const s = [{ start: 0, end: 100, layout: "A" }];
    const a = setRange(s, 20, 50, "layout", "B");
    expect(a.map((x) => [x.start, x.end, x.layout])).toEqual([[0, 20, "A"], [20, 50, "B"], [50, 100, "A"]]);
    const b = setRange(a, 20, 50, "layout", "A");
    expect(b.map((x) => [x.start, x.end, x.layout])).toEqual([[0, 100, "A"]]);
    expect(isCovering(b, 100)).toBe(true);
  });

  it("isCovering detects gap / overlap / short", () => {
    expect(isCovering(S(0, 5, 10), 10)).toBe(true);
    expect(isCovering([{ start: 0, end: 5 }, { start: 6, end: 10 }], 10)).toBe(false);
    expect(isCovering([{ start: 0, end: 6 }, { start: 5, end: 10 }], 10)).toBe(false);
    expect(isCovering(S(0, 5, 9), 10)).toBe(false);
  });

  it("visibleSlice returns only intersecting items", () => {
    const items = Array.from({ length: 2000 }, (_, i) => ({ start: i * 10, end: i * 10 + 10 }));
    expect(visibleSlice(items, 0, 100, 10)).toEqual([0, 10]);
    expect(visibleSlice(items, 105, 125, 10)).toEqual([10, 13]);
    expect(visibleSlice(items, 30000, 40000, 10)).toEqual([2000, 2000]);
  });
});

describe("time (fraction fps)", () => {
  it("parses and converts", () => {
    const ntsc = parseFps("30000/1001");
    expect(secToFrame(frameToSec(1798, ntsc), ntsc)).toBe(1798);
    expect(msToFrame(1000, parseFps("25/1"))).toBe(25);
    expect(fmtFrame(25 * 61 + 3, parseFps("25/1"))).toBe("1:01.03");
    expect(() => parseFps("0/1")).toThrow();
  });
});

describe("subtitles", () => {
  it("groups words by pause and length", () => {
    const w = (text: string, s: number, e: number) => ({ text, start_ms: s, end_ms: e, conf: 1 });
    const cues = groupWords([w("a", 0, 400), w("b", 400, 800), w("c", 3000, 3400)], parseFps("25/1"));
    expect(cues.map((c) => [c.text, c.start, c.end])).toEqual([["a b", 0, 20], ["c", 75, 85]]);
  });
});
