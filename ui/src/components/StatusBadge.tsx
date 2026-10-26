import type { JobStatus } from "../lib/types";

// Rang faqat kuchaytiradi; har doim o'zbekcha so'z bilan (design-system README, "Status colour").
export const STATUS: Record<JobStatus, { word: string; color: string; bg: string }> = {
  navbatda: { word: "Navbatda", color: "var(--muted)", bg: "var(--muted-subtle)" },
  ishlanmoqda: { word: "Ishlanmoqda", color: "var(--accent)", bg: "var(--accent-subtle)" },
  tayyor: { word: "Tayyor", color: "var(--success)", bg: "var(--success-subtle)" },
  xato: { word: "Xato", color: "var(--danger)", bg: "var(--danger-subtle)" },
  "toʻxtatildi": { word: "Toʻxtatildi", color: "var(--muted)", bg: "var(--muted-subtle)" },
};

export function StatusBadge({ status, progress }: { status: JobStatus; progress?: number }) {
  const s = STATUS[status] ?? STATUS.navbatda;
  const pct = status === "ishlanmoqda" && progress !== undefined ? ` ${Math.round(progress * 100)}%` : "";
  return (
    <span className="pill label" style={{ color: s.color, background: s.bg }} data-status={status}>
      <span className="dot" />{s.word}{pct}
    </span>
  );
}

export function ProgressBar({ status, progress }: { status: JobStatus; progress: number }) {
  const color = status === "xato" ? "var(--danger)" : status === "ishlanmoqda" ? "var(--accent)"
    : status === "tayyor" ? "var(--success)" : "var(--muted)";
  return (
    <div className="track" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className="fill" style={{ width: `${Math.min(100, progress * 100)}%`, background: color }} />
    </div>
  );
}
