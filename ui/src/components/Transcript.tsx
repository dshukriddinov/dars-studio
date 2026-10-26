// Transkript: ro'yxat bir marta chiziladi, joriy so'z DOM klassi bilan belgilanadi (har kadrda React yangilanmaydi).
import { memo, useEffect, useRef } from "react";
import { player } from "../lib/player";
import { frameToSec, msToFrame } from "../lib/time";
import type { Word } from "../lib/types";

export function wordIndexAt(words: Word[], ms: number): number {
  let lo = 0, hi = words.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (words[mid].start_ms <= ms) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return ans >= 0 && ms < words[ans].end_ms ? ans : -1;
}

export const Transcript = memo(function Transcript({ words }: { words: Word[] }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let cur: HTMLElement | null = null;
    const mark = (f: number) => {
      const i = wordIndexAt(words, frameToSec(f, player.fps) * 1000);
      const el = i >= 0 ? (box.current?.children[i] as HTMLElement | undefined) ?? null : null;
      if (el === cur) return;
      cur?.classList.remove("cur");
      el?.classList.add("cur");
      cur = el;
      if (el && player.playing) el.scrollIntoView({ block: "nearest" });
    };
    mark(player.frame);
    return player.subscribe(mark);
  }, [words]);

  if (!words.length) return <p className="caption dim pad">Transkript yoʻq (ASR hali bajarilmagan)</p>;
  return (
    <div className="transcript body" ref={box} onClick={(e) => {
      const i = Number((e.target as HTMLElement).dataset.i);
      if (!Number.isNaN(i) && words[i]) player.seek(msToFrame(words[i].start_ms, player.fps));
    }}>
      {words.map((w, i) => (
        <span key={i} data-i={i} className={w.conf < 0.4 ? "low" : undefined}>{w.text} </span>
      ))}
    </div>
  );
});
