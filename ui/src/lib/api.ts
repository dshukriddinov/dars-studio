// Backend (darsstudio/api/app.py) ga yupqa qatlam. Xato bo'lsa server "detail" matni bilan Error.
import type { DoctorCheck, Job, ProjectSummary, ProjectView, Suspicious, Word } from "./types";

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `Server xatosi ${r.status}`;
    try {
      const d = (await r.json()).detail;
      if (d) msg = typeof d === "string" ? d : JSON.stringify(d);
    } catch { /* matn JSON emas */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

const p = (name: string) => `/api/projects/${encodeURIComponent(name)}`;

export const api = {
  doctor: () => req<DoctorCheck[]>("GET", "/api/doctor"),
  projects: () => req<ProjectSummary[]>("GET", "/api/projects"),
  createProject: (body: unknown) => req<{ name: string; jobs: number[] }>("POST", "/api/projects", body),
  project: (name: string) => req<ProjectView>("GET", p(name)),
  command: (name: string, label: string, values: Record<string, unknown>) =>
    req<ProjectView>("POST", `${p(name)}/commands`, { label, values }),
  undo: (name: string) => req<ProjectView>("POST", `${p(name)}/undo`),
  redo: (name: string) => req<ProjectView>("POST", `${p(name)}/redo`),
  words: (name: string) => req<Word[]>("GET", `${p(name)}/words`),
  suspicious: (name: string) => req<Suspicious[]>("GET", `${p(name)}/suspicious`),
  prepare: (name: string) => req<{ jobs: number[] }>("POST", `${p(name)}/prepare`),
  addJob: (name: string, type: string, args: Record<string, unknown>) =>
    req<{ id: number }>("POST", `${p(name)}/jobs`, { type, args }),
  jobs: (project?: string) => req<Job[]>("GET", project ? `/api/jobs?project=${encodeURIComponent(project)}` : "/api/jobs"),
  stopJob: (id: number) => req<Job>("POST", `/api/jobs/${id}/stop`),
  resumeJob: (id: number) => req<Job>("POST", `/api/jobs/${id}/resume`),
  keySuggest: (name: string, frame: number) => req<ProjectView>("POST", `${p(name)}/key/suggest?frame=${frame}`),
  preview: (name: string, startS: number, durS: number) =>
    req<{ id: number; file: string }>("POST", `${p(name)}/preview?start_s=${startS}&duration_s=${durS}`),
  exports: (name: string) =>
    req<{ file: string; size_mb: number; qa: unknown; version: number; mtime: number }[]>("GET", `${p(name)}/exports`),
  templates: () => req<string[]>("GET", "/api/templates"),
  template: (id: string) => req<{ screen_quad: number[][]; teacher_anchor: number[]; [k: string]: unknown }>("GET", `/api/templates/${encodeURIComponent(id)}`),
  saveTemplate: (id: string, body: { screen_quad?: number[][]; teacher_anchor?: number[] }) =>
    req<unknown>("PUT", `/api/templates/${encodeURIComponent(id)}`, body),
  addPart: (name: string, video: string) => req<ProjectView & { jobs: number[] }>("POST", `${p(name)}/parts`, { video }),
  reveal: (name: string, file: string) => req<{ ok: boolean }>("POST", `${p(name)}/reveal`, { file }),
  pickFile: (kind: "video" | "slides") => req<{ path: string }>("POST", `/api/pick-file?kind=${kind}`),
  /** Lower-third ko'rinishi (PNG) -> object URL; chaqiruvchi eskisini URL.revokeObjectURL qiladi. */
  lowerThirdPreview: async (template: string, meta: Record<string, string>): Promise<string> => {
    const r = await fetch("/api/lower-third-preview", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template, meta }),
    });
    if (!r.ok) throw new Error(`Koʻrinish yaratilmadi (${r.status})`);
    return URL.createObjectURL(await r.blob());
  },
};

export const urls = {
  proxy: (name: string) => `${p(name)}/proxy`,
  waveform: (name: string) => `${p(name)}/waveform`,
  slide: (name: string, i: number) => `${p(name)}/slides/${i}`,
  frame: (name: string, f: number, mode: string, width = 960) => `${p(name)}/frame/${f}?mode=${mode}&width=${width}`,
  file: (name: string, file: string) => `${p(name)}/files/${file.split("/").map(encodeURIComponent).join("/")}`,
  templateBg: (id: string) => `/api/templates/${encodeURIComponent(id)}/background`,
};
