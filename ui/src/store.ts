import { create } from "zustand";
import { api } from "./lib/api";
import type { Job, ProjectView, Suspicious, Word } from "./lib/types";

export type Tab = "home" | "new" | "review" | "key" | "template" | "export" | "settings";

interface State {
  tab: Tab;
  name: string | null;
  view: ProjectView | null;
  words: Word[];
  suspicious: Suspicious[];
  jobs: Record<number, Job>;
  error: string | null;
  notice: string | null;
  busy: boolean;
  setTab: (t: Tab) => void;
  open: (name: string, tab?: Tab) => Promise<void>;
  command: (label: string, values: Record<string, unknown>) => Promise<boolean>;
  undo: () => Promise<void>;
  redo: () => Promise<void>;
  setView: (v: ProjectView) => void;
  upsertJob: (j: Job) => void;
  setJobs: (js: Job[]) => void;
  fail: (e: unknown) => void;
  clearError: () => void;
}

let noticeTimer: ReturnType<typeof setTimeout> | undefined;

export const useStore = create<State>((set, get) => {
  const run = async (fn: () => Promise<ProjectView>, notice = "Saqlandi") => {
    set({ busy: true });
    try {
      const view = await fn();
      set({ view, busy: false, error: null, notice });
      clearTimeout(noticeTimer);
      noticeTimer = setTimeout(() => set({ notice: null }), 2000);
      return true;
    } catch (e) {
      set({ busy: false });
      get().fail(e);
      return false;
    }
  };
  return {
    tab: "home", name: null, view: null, words: [], suspicious: [], jobs: {}, error: null, notice: null, busy: false,
    setTab: (tab) => set({ tab }),
    open: async (name, tab) => {
      set({ name, view: null, words: [], suspicious: [], ...(tab ? { tab } : {}) });
      try {
        const [view, words, suspicious] = await Promise.all([api.project(name), api.words(name), api.suspicious(name)]);
        if (get().name === name) set({ view, words, suspicious, error: null });
      } catch (e) { get().fail(e); }
    },
    command: (label, values) => {
      const n = get().name;
      return n ? run(() => api.command(n, label, values)) : Promise.resolve(false);
    },
    undo: async () => { const n = get().name; if (n && get().view?.can_undo) await run(() => api.undo(n), "Qaytarildi"); },
    redo: async () => { const n = get().name; if (n && get().view?.can_redo) await run(() => api.redo(n), "Takrorlandi"); },
    setView: (view) => set({ view }),
    upsertJob: (j) => set((s) => ({ jobs: { ...s.jobs, [j.id]: j } })),
    setJobs: (js) => set({ jobs: Object.fromEntries(js.map((j) => [j.id, j])) }),
    fail: (e) => set({ error: e instanceof Error ? e.message : String(e) }),
    clearError: () => set({ error: null }),
  };
});

/** Navbat yangilanishlari (WS /ws). Uzilsa 2 s dan keyin qayta ulanadi. */
export function connectJobs(): () => void {
  let ws: WebSocket | null = null;
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const connect = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "job") useStore.getState().upsertJob(m.job);
      } catch { /* e'tiborsiz */ }
    };
    ws.onopen = () => { api.jobs().then(useStore.getState().setJobs).catch(() => undefined); };
    ws.onclose = () => { if (!stopped) timer = setTimeout(connect, 2000); };
  };
  connect();
  return () => { stopped = true; clearTimeout(timer); ws?.close(); };
}
