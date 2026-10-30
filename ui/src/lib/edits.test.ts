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
  eye_off: [], key: { key_cbcr: [0, 0], tolerance: 0, softness: 0, spill: 0, choke_px: 0, feather_px: 0 }, eye_contact: {}, assets: [],
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

describe("moveAnimStepCmd", () => {
  it("javob vaqtini shu slaydning qo'shni qadamlari orasida suradi va qo'lda deb belgilaydi", () => {
    const p = { ...project(), anim_steps: [
      { slide: 2, click: 1, frame: 120, source: "ai" as const },
      { slide: 2, click: 2, frame: 150, source: "ai" as const },
      { slide: 3, click: 1, frame: 250, source: "ai" as const },
    ] };
    const c = E.moveAnimStepCmd(p, 0, 170)!;   // 2-qadamdan o'tib ketmaydi
    expect(c.values.anim_steps).toEqual([
      { slide: 2, click: 1, frame: 149, source: "manual" }, p.anim_steps[1], p.anim_steps[2]]);
    expect(E.moveAnimStepCmd(p, 1, 150)).toBeNull();
  });
});

describe("timeline tahriri", () => {
  const fps = { num: 25, den: 1 };
  const words = [{ text: "bir", start_ms: 0, end_ms: 400, conf: 1 }, { text: "ikki", start_ms: 600, end_ms: 1000, conf: 1 }];
  it("kesish cheti so'z ichiga tushsa — bo'shliq o'rtasiga", () => {
    expect(E.snapOutOfWord(18, words, fps)).toBe(13);     // 720 ms "ikki" ichida -> (400+600)/2 = 500 ms
    expect(E.snapOutOfWord(12, words, fps)).toBe(12);     // 480 ms bo'shliqda
  });
  it("kesishni cheti bo'yicha o'zgartirish qo'lda va tasdiqlangan bo'ladi; teskari bo'lmaydi", () => {
    const c = E.resizeCutCmd(project(), 0, "end", 5)!;
    expect(c.values["cuts.0"]).toEqual({ start: 10, end: 11, reason: "manual", status: "tasdiqlangan" });
  });
  it("bir xil qo'lda kesish ikki marta qo'shilmaydi", () => {
    const p = { ...project(), cuts: [{ start: 30, end: 40, reason: "manual" as const, status: "tasdiqlangan" as const }] };
    expect(E.addCutCmd(p, 30, 40)).toBeNull();
    expect(E.addCutCmd(p, 40, 30)).toBeNull();
    expect(E.addCutCmd(p, 41, 50)!.values.cuts).toHaveLength(2);
  });
  it("sahna: chegara surish va A<->B", () => {
    const p = { ...project(), layout_spans: [{ start: 0, end: 100, layout: "A" as const, suggested: true },
      { start: 100, end: 300, layout: "B" as const, suggested: true }] };
    expect(E.moveSceneBoundaryCmd(p, 1, 120)!.values.layout_spans).toEqual([
      { start: 0, end: 120, layout: "A", suggested: false }, { start: 120, end: 300, layout: "B", suggested: false }]);
    expect(E.moveSceneBoundaryCmd(p, 0, 50)).toBeNull();
    const t = E.toggleSceneCmd(p, 1)!.values.layout_spans as { layout: string }[];
    expect(t.every((s) => s.layout === "A")).toBe(true);
  });
});

describe("slayd chegarasi surilganda tavsiya sahnalari ergashadi", () => {
  const base = () => ({ ...project(), slide_spans: [span(0, 100, 1), span(100, 300, 2)],
    layout_spans: [{ start: 0, end: 100, layout: "B" as const, suggested: true },
      { start: 100, end: 125, layout: "A" as const, suggested: true },
      { start: 125, end: 300, layout: "B" as const, suggested: true }] });
  const bounds = (c: E.Cmd) => (c.values.layout_spans as { start: number }[]).map((s) => s.start);
  it("oldinga va orqaga", () => {
    expect(bounds(E.moveBoundaryCmd(base(), 0, 120)!)).toEqual([0, 120, 145]);
    expect(bounds(E.moveBoundaryCmd(base(), 0, 90)!)).toEqual([0, 90, 115]);
  });
  it("qo'lda o'zgartirilgan sahnaga tegilmaydi", () => {
    const p = base();
    p.layout_spans[1] = { ...p.layout_spans[1], suggested: false };
    expect(E.moveBoundaryCmd(p, 0, 120)!.values.layout_spans).toBeUndefined();
  });
});

describe("sahna tanlovi birlashganda ham qo'lda qoladi", () => {
  it("B -> A qo'shni A lar bilan birlashadi, natija suggested=false", () => {
    const p = { ...project(), layout_spans: [{ start: 0, end: 100, layout: "A" as const, suggested: true },
      { start: 100, end: 200, layout: "B" as const, suggested: true },
      { start: 200, end: 300, layout: "A" as const, suggested: true }] };
    expect(E.toggleSceneCmd(p, 1)!.values.layout_spans).toEqual([{ start: 0, end: 300, layout: "A", suggested: false }]);
  });
});

describe("slideMismatch", () => {
  it("slaydlarning 60% idan kami topilsa — ogohlantirish", () => {
    const many = { ...project(), slides: Array.from({ length: 10 }, (_, i) => ({ index: i + 1, title: "" })) };
    expect(E.slideMismatch(many)).toContain("10 ta slayddan faqat 3 tasi");
    const ok = { ...many, slide_spans: Array.from({ length: 10 }, (_, i) => span(i * 30, i * 30 + 30, i + 1)) };
    expect(E.slideMismatch(ok)).toBeNull();
    expect(E.slideMismatch(project())).toBeNull();   // kam slayd (< 8) — ogohlantirilmaydi
  });
});

describe("removeCutCmd (Delete tugmasi)", () => {
  it("qo'lda kesish ro'yxatdan o'chadi, avtomatik taklif rad etiladi", () => {
    const p = { ...project(), cuts: [{ start: 10, end: 20, reason: "manual" as const, status: "tasdiqlangan" as const },
      { start: 50, end: 60, reason: "pause" as const, status: "taklif" as const }] };
    expect(E.removeCutCmd(p, 0)!.values.cuts).toEqual([p.cuts[1]]);
    expect(E.removeCutCmd(p, 1)!.values).toEqual({ "cuts.1.status": "rad_etilgan" });
    expect(E.removeCutCmd({ ...p, cuts: [{ ...p.cuts[1], status: "rad_etilgan" as const }] }, 0)).toBeNull();
  });
});

describe("deleteSlideSpanCmd (Delete)", () => {
  it("oraliq o'chadi, vaqti qo'shniga qo'shiladi; yakka oraliq o'chmaydi", () => {
    const p = project();
    expect((E.deleteSlideSpanCmd(p, 1)!.values.slide_spans as { start: number; end: number; slide: number }[])
      .map((s) => [s.start, s.end, s.slide])).toEqual([[0, 200, 1], [200, 300, 3]]);
    expect((E.deleteSlideSpanCmd(p, 0)!.values.slide_spans as { start: number }[])[0].start).toBe(0);
    expect(E.deleteSlideSpanCmd({ ...p, slide_spans: [p.slide_spans[0]] }, 0)).toBeNull();
  });
});
