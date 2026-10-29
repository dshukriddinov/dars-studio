// Backend modeli (darsstudio/project/model.py) ning UI'ga kerakli qismi. Oraliqlar asl kadrlarda, [start, end).
export interface Span { start: number; end: number }
export interface SlideSpan extends Span { slide: number; source: "log" | "ai" | "manual"; confidence: number; approved: boolean }
export interface LayoutSpan extends Span { layout: "A" | "B" | "C"; suggested: boolean }
export interface CutProposal extends Span { reason: "pause" | "manual" | "bosh" | "oxir" | "yo'tal" | "aksa" | "to'ldiruvchi" | "takror" | "qism"; status: "taklif" | "tasdiqlangan" | "rad_etilgan" }
export type EyeOffSpan = Span;
/** Slayd animatsiyasining click-bosishi shu asl kadrda (javob o'qituvchi aytganda chiqadi). */
export interface AnimStep { slide: number; click: number; frame: number; source: "ai" | "manual" }

export interface KeySettings {
  key_cbcr: [number, number]; tolerance: number; softness: number; spill: number;
  choke_px: number; feather_px: number; [k: string]: unknown;
}

export interface Project {
  id: string; name: string; meta: Record<string, string>; fps: string; total_frames: number; template_id: string;
  slides: { index: number; title: string; body?: string; anim?: string[] }[];
  anim_steps?: AnimStep[];
  assets: { path: string; kind: string }[];
  slide_spans: SlideSpan[]; layout_spans: LayoutSpan[]; cuts: CutProposal[]; eye_off: EyeOffSpan[];
  parts?: { path: string; start: number; frames: number }[];
  exports?: { version: number; path: string; qa: string }[];
  key: KeySettings; eye_contact: { lid_open?: number; [k: string]: unknown };
}

export interface ProjectView {
  project: Project; can_undo: boolean; can_redo: boolean; undo_label: string | null; redo_label: string | null;
}

export interface Word { text: string; start_ms: number; end_ms: number; conf: number }
export interface Suspicious { kind: string; frame: number; score: number; text: string }

export type JobStatus = "navbatda" | "ishlanmoqda" | "tayyor" | "xato" | "toʻxtatildi";
export interface Job {
  id: number; type: string; project: string; status: JobStatus; progress: number; message: string;
  error: string | null; args: Record<string, unknown>; created: number;
}

export interface ProjectSummary {
  name: string; fps: string; total_frames: number; slides: number; meta: Record<string, string>;
  jobs: Record<JobStatus, number>;
}

export interface DoctorCheck { name: string; status: "ok" | "ogohlantirish" | "xato"; detail: string; fix: string }
