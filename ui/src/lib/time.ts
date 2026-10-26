// Kadr <-> vaqt. fps kasr satr ("30000/1001"); float soniyalar yig'ilmaydi, har safar kadrdan hisoblanadi.
export interface Fps { num: number; den: number }

export function parseFps(s: string): Fps {
  const [n, d = "1"] = s.split("/");
  const num = Number(n), den = Number(d);
  if (!(num > 0 && den > 0)) throw new Error(`fps notoʻgʻri: ${s}`);
  return { num, den };
}

export const frameToSec = (f: number, fps: Fps) => (f * fps.den) / fps.num;
export const secToFrame = (s: number, fps: Fps) => Math.round((s * fps.num) / fps.den);
export const msToFrame = (ms: number, fps: Fps) => Math.round((ms * fps.num) / (fps.den * 1000));
/** Seek nuqtasi kadr ichida (chegarada emas), aks holda brauzer oldingi kadrga tushishi mumkin. */
export const seekTime = (f: number, fps: Fps) => ((f + 0.25) * fps.den) / fps.num;

/** 1234 kadr @25 -> "0:49.09" (daqiqa:soniya.kadr) */
export function fmtFrame(f: number, fps: Fps): string {
  const total = Math.max(0, f);
  const sec = Math.floor((total * fps.den) / fps.num);
  const rest = total - Math.ceil((sec * fps.num) / fps.den);
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}.${String(Math.max(0, rest)).padStart(2, "0")}`;
}
