import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { TextEdit } from "./TextEdit";
import { parseFps } from "../lib/time";
import type { CutProposal, Word } from "../lib/types";

afterEach(cleanup);
const fps = parseFps("25/1");
const words: Word[] = ["bir", "ikki", "uch", "toʻrt", "besh"].map((t, i) => ({ text: t, start_ms: i * 1000,
  end_ms: i * 1000 + 600, conf: 0.9 }));

describe("TextEdit", () => {
  it("Shift bilan belgilangan so'zlarni so'zlar orasidagi bo'shliq o'rtasidan kesadi", () => {
    const onCut = vi.fn();
    render(<TextEdit words={words} cuts={[]} fps={fps} total={200} onCut={onCut} onRestore={() => undefined} />);
    fireEvent.mouseDown(screen.getByText(/^ikki/));
    fireEvent.mouseUp(window);
    fireEvent.mouseDown(screen.getByText(/^uch/), { shiftKey: true });
    expect(screen.getByText("2 ta soʻz")).toBeTruthy();
    fireEvent.click(screen.getByText("Kesish"));
    // ikki: 1000–1600, uch: 2000–2600 -> (600+1000)/2=800 ms .. (2600+3000)/2=2800 ms -> 20..70 kadr
    expect(onCut).toHaveBeenCalledWith(20, 70);
  });

  it("kesilgan so'z bosilsa Tiklash", () => {
    const onRestore = vi.fn();
    const cuts: CutProposal[] = [{ start: 20, end: 70, reason: "manual", status: "tasdiqlangan" }];
    render(<TextEdit words={words} cuts={cuts} fps={fps} total={200} onCut={() => undefined} onRestore={onRestore} />);
    fireEvent.mouseDown(screen.getByText(/^uch/));
    fireEvent.click(screen.getByText("Tiklash"));
    expect(onRestore).toHaveBeenCalledWith([0]);
  });
});
