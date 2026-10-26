import { fmtFrame, type Fps } from "../lib/time";
import type { Suspicious } from "../lib/types";

const KIND: Record<string, string> = {
  slayd_chegarasi: "Slayd chegarasi",
  qisqa_slayd: "Qisqa slayd",
  past_ishonchli_soz: "Past ishonchli soʻz",
};

export const kindLabel = (k: string) => KIND[k] ?? k.replace(/_/g, " ");

/** Eng past ishonchli birinchi (FR-14). */
export const sortSuspicious = (items: Suspicious[]) =>
  items.slice().sort((a, b) => a.score - b.score || a.frame - b.frame);

export function SuspiciousList({ items, fps, onJump }: { items: Suspicious[]; fps: Fps; onJump: (frame: number) => void }) {
  if (!items.length) return <p className="caption dim pad">Shubhali joy yoʻq</p>;
  return (
    <ul className="list">
      {sortSuspicious(items).map((s, i) => (
        <li key={i}>
          <button className="row-btn" onClick={() => onJump(s.frame)} title="Shu joyga oʻtish">
            <span className="body-strong">{kindLabel(s.kind)}</span>
            <span className="stat dim">{fmtFrame(s.frame, fps)}</span>
            <span className="caption dim ellipsis">{s.text}</span>
            <span className="caption stat dim">{s.score.toFixed(2)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
