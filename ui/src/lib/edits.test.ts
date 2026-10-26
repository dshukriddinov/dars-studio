import { describe, expect, it } from "vitest";
import * as E from "./edits";
import { isCovering } from "./spans";
import type { Project, SlideSpan } from "./types";

const span = (start: number, end: number, slide: number): SlideSpan =>
  ({ start, end, slide, source: "ai", confidence: 0.9, approved: false });

const project = (): Project => ({
  id: "x", name: "t", meta: {}, fps: "25/1", total_frames: 300, template_id: "demo",
  slides: [1, 2, 3].map((index) => ({ index, title: "" })),
  slide_spans: [span(0, 100, 1), span(100, 200, 2), span(200, 300, 3)],
  layout_spans: [{ start: 0, end: 300, layout: "A", suggested: true }],
  cuts: [{ start: 10, end: 20, reason: "pause", status: "taklif" }, { start: 50, end: 60, reason: "pause", status: "taklif" }],
  eye_off: [], key: { key_cbcr: [0, 0], tolerance: 0, softness: 0, spill: 0, choke_px: 0, feather_px: 0 }, eye_contact: {},
});

describe("command payload builders", () => {
  it("moveBoundaryCmd sends full covering slide_spans with spans[b].end == spans[b+1].start", () => {
    const p = project();
    const c = E.moveBoundaryCmd(p, 0, 112)!;
    expect(c.label).toBe("Chegarani surish");
    const s = c.values.slide_spans as SlideSpan[];
    expect(s[0].end).toBe(112);
    expect(s[1].start).toBe(112);
    expect(s[0].source).toBe("manual");
    expect(s[2]).toEqual(p.slide_spans[2]);
    expect(isCovering(s, p.total_frames)).toBe(true);
    expect(E.moveBoundaryCmd(p, 0, 100)).toBeNull();
    // chegaradan oshib ketmaydi
    expect(isCovering(E.moveBoundaryCmd(p, 1, 10_000)!.values.slide_spans as SlideSpan[], 300)).toBe(true);
  });

  it("split / merge / set slide stay covering", () => {
    const p = project();
    const sp = E.splitSlideCmd(p, 150)!.values.slide_spans as SlideSpan[];
    expect(sp).toHaveLength(4);
    expect(isCovering(sp, 300)).toBe(true);
    const mg = E.mergeSlideCmd(p, 1)!.values.slide_spans as SlideSpan[];
    expect(mg.map((s) => [s.start, s.end, s.slide])).toEqual([[0, 100, 1], [100, 300, 2]]);
    const st = E.setSlideCmd(p, 1, 3)!.values.slide_spans as SlideSpan[];
    expect(st.map((s) => [s.start, s.end, s.slide])).toEqual([[0, 100, 1], [100, 300, 3]]);
    expect(E.setSlideCmd(p, 1, 2)).toBeNull();
  });

  it("setSceneCmd splits layout spans around the slide under playhead", () => {
    const c = E.setSceneCmd(project(), 150, "B")!;
    expect((c.values.layout_spans as { start: number; end: number; layout: string }[])
      .map((s) => [s.start, s.end, s.layout])).toEqual([[0, 100, "A"], [100, 200, "B"], [200, 300, "A"]]);
    expect(E.setSceneCmd(project(), 150, "A")).toBeNull();
  });

  it("cut commands", () => {
    const p = project();
    expect(E.cutStatusCmd(p, 1, "tasdiqlangan")).toEqual({ label: "Kesishni tasdiqlash", values: { "cuts.1.status": "tasdiqlangan" } });
    const all = E.approveAllCutsCmd(p)!.values.cuts as { status: string }[];
    expect(all.every((c) => c.status === "tasdiqlangan")).toBe(true);
  });

  it("eye_off add sorts and clamps", () => {
    const c = E.addEyeOffCmd(project(), 80, 40)!;
    expect(c.values.eye_off).toEqual([{ start: 40, end: 80 }]);
    expect(E.addEyeOffCmd(project(), 5, 5)).toBeNull();
  });
});
