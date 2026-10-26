import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Timeline, laneMaxLen, type Item } from "./Timeline";
import { StatusBadge } from "./StatusBadge";
import { SuspiciousList, sortSuspicious } from "./SuspiciousList";
import { parseFps } from "../lib/time";

afterEach(cleanup);

describe("Timeline virtualization", () => {
  const items: Item[] = Array.from({ length: 2000 }, (_, i) => ({ start: i * 10, end: i * 10 + 10, i, text: `s${i}` }));
  const lanes = [{ id: "slide", label: "Slayd", items, maxLen: laneMaxLen(items), boundaries: true }];

  it("renders only items in the visible range for 2000 items", async () => {
    const { container } = render(<Timeline total={20000} lanes={lanes} onSeek={() => undefined} width={1000} pxPerFrame={1} />);
    const rendered = () => container.querySelectorAll("[data-item]");
    // 1000 px + 2×200 px overscan, 10 px/element -> ~120 ta, 2000 emas
    expect(rendered().length).toBeGreaterThan(50);
    expect(rendered().length).toBeLessThan(200);
    expect(screen.getByTitle("s0")).toBeTruthy();
    expect(screen.queryByTitle("s1500")).toBeNull();

    const scroller = container.querySelector(".tl-scroll") as HTMLDivElement;
    scroller.scrollLeft = 15000;
    await act(async () => {
      fireEvent.scroll(scroller);
      await new Promise((r) => requestAnimationFrame(() => r(null)));
    });
    expect(screen.getByTitle("s1500")).toBeTruthy();
    expect(screen.queryByTitle("s0")).toBeNull();
    expect(rendered().length).toBeLessThan(200);
  });

  it("calls onItemClick / onBoundaryClick", () => {
    const onItem = vi.fn(), onBound = vi.fn();
    const { container } = render(<Timeline total={20000} lanes={lanes} onSeek={() => undefined} width={1000} pxPerFrame={1}
      onItemClick={onItem} onBoundaryClick={onBound} />);
    fireEvent.mouseDown(screen.getByTitle("s3"), { button: 0 });
    expect(onItem.mock.calls[0][0]).toBe("slide");
    expect(onItem.mock.calls[0][1]).toBe(3);
    fireEvent.mouseDown(container.querySelectorAll(".tl-bound")[0]);
    expect(onBound).toHaveBeenCalledWith(0);
  });
});

describe("StatusBadge", () => {
  it.each([
    ["navbatda", "Navbatda", "var(--muted)"],
    ["toʻxtatildi", "Toʻxtatildi", "var(--muted)"],
    ["ishlanmoqda", "Ishlanmoqda", "var(--accent)"],
    ["tayyor", "Tayyor", "var(--success)"],
    ["xato", "Xato", "var(--danger)"],
  ] as const)("%s -> word %s, colour %s", (status, word, color) => {
    const { container } = render(<StatusBadge status={status} />);
    const pill = container.querySelector(".pill") as HTMLElement;
    expect(pill.textContent).toBe(word);
    expect(pill.style.color).toBe(color);
  });

  it("shows percentage while processing", () => {
    const { container } = render(<StatusBadge status="ishlanmoqda" progress={0.42} />);
    expect(container.textContent).toBe("Ishlanmoqda 42%");
  });
});

describe("SuspiciousList", () => {
  const items = [
    { kind: "qisqa_slayd", frame: 500, score: 0.5, text: "1 s dan qisqa" },
    { kind: "past_ishonchli_soz", frame: 100, score: 0.12, text: "soʻz" },
    { kind: "slayd_chegarasi", frame: 900, score: 0.3, text: "2 -> 3" },
  ];

  it("sorts by score ascending", () => {
    expect(sortSuspicious(items).map((s) => s.frame)).toEqual([100, 900, 500]);
    expect(items[0].frame).toBe(500); // asl ro'yxat o'zgarmaydi
  });

  it("renders sorted and jumps to frame on click", () => {
    const onJump = vi.fn();
    render(<SuspiciousList items={items} fps={parseFps("25/1")} onJump={onJump} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons[0].textContent).toContain("Past ishonchli soʻz");
    expect(buttons[1].textContent).toContain("Slayd chegarasi");
    fireEvent.click(buttons[1]);
    expect(onJump).toHaveBeenCalledWith(900);
  });
});
