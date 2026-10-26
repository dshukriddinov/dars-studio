import { describe, expect, it } from "vitest";
import { keyToAction } from "./keys";

describe("keyToAction (FR-14)", () => {
  it("maps review shortcuts", () => {
    expect(keyToAction({ key: "j" })).toBe("reverse");
    expect(keyToAction({ key: "K" })).toBe("pause");
    expect(keyToAction({ key: "l" })).toBe("play");
    expect(keyToAction({ key: " " })).toBe("toggle");
    expect(keyToAction({ key: "ArrowLeft" })).toBe("prevFrame");
    expect(keyToAction({ key: "ArrowRight" })).toBe("nextFrame");
    expect(keyToAction({ key: "ArrowLeft", shiftKey: true })).toBe("back1s");
    expect(keyToAction({ key: "ArrowRight", shiftKey: true })).toBe("fwd1s");
    expect(keyToAction({ key: "[" })).toBe("boundaryLeft");
    expect(keyToAction({ key: "]" })).toBe("boundaryRight");
    expect(keyToAction({ key: "1" })).toBe("sceneA");
    expect(keyToAction({ key: "2" })).toBe("sceneB");
    expect(keyToAction({ key: "Enter" })).toBe("approveCut");
    expect(keyToAction({ key: "z", ctrlKey: true })).toBe("undo");
    expect(keyToAction({ key: "Z", ctrlKey: true, shiftKey: true })).toBe("redo");
    expect(keyToAction({ key: "y", ctrlKey: true })).toBe("redo");
    expect(keyToAction({ key: "x" })).toBeNull();
    expect(keyToAction({ key: "c", ctrlKey: true })).toBeNull();
  });

  it("ignores keys while typing in inputs", () => {
    const input = document.createElement("input");
    const select = document.createElement("select");
    const textarea = document.createElement("textarea");
    for (const t of [input, select, textarea]) {
      expect(keyToAction({ key: "j", target: t })).toBeNull();
      expect(keyToAction({ key: "z", ctrlKey: true, target: t })).toBeNull();
    }
    expect(keyToAction({ key: "j", target: document.createElement("div") })).toBe("reverse");
  });
});
