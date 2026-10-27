import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("cheksiz siklsiz render bo'ladi", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 200 })));
    vi.stubGlobal("WebSocket", class { onopen = null; onclose = null; onmessage = null; close() {} } as unknown as typeof WebSocket);
    const r = render(<App />);
    await new Promise((res) => setTimeout(res, 300));
    expect(r.container.textContent).toContain("Dars Studio");
  });
});
