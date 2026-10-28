import { describe, expect, it } from "vitest";
import { srcToOut } from "./FinalView";

describe("srcToOut", () => {
  const keep: [number, number][] = [[0, 10], [20, 30], [40, 50]];
  it("saqlangan joylar ketma-ket, kesilgan joy null", () => {
    expect(srcToOut(keep, 0)).toBe(0);
    expect(srcToOut(keep, 9)).toBe(9);
    expect(srcToOut(keep, 10)).toBeNull();
    expect(srcToOut(keep, 20)).toBe(10);
    expect(srcToOut(keep, 45)).toBe(25);
    expect(srcToOut(keep, 50)).toBeNull();
  });
});
