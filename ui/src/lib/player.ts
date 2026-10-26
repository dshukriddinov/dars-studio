// Joriy kadr soati React'dan tashqarida: playhead, kadr hisoblagich, joriy so'z obunachilar orqali yangilanadi,
// shuning uchun har kadrda butun ekran qayta chizilmaydi.
import { useEffect, useState } from "react";
import { frameToSec, seekTime, type Fps } from "./time";

type Listener = (frame: number) => void;

class Player {
  frame = 0;
  fps: Fps = { num: 25, den: 1 };
  total = 0;
  video: HTMLVideoElement | null = null;
  private listeners = new Set<Listener>();
  private detachFn: (() => void) | null = null;

  subscribe(l: Listener): () => void {
    this.listeners.add(l);
    return () => { this.listeners.delete(l); };
  }

  set(f: number) {
    const c = Math.max(0, Math.min(f, Math.max(0, this.total - 1)));
    if (c === this.frame) return;
    this.frame = c;
    this.listeners.forEach((l) => l(c));
  }

  private fromTime(t: number) {
    // Ko'rsatilayotgan asl kadr = round(mediaTime * fps)
    return Math.round((t * this.fps.num) / this.fps.den);
  }

  attach(video: HTMLVideoElement, fps: Fps, total: number) {
    this.detach();
    this.video = video;
    this.fps = fps;
    this.total = total;
    const v = this.video;
    let alive = true;
    let handle = 0;
    const rvfc = typeof (v as { requestVideoFrameCallback?: unknown }).requestVideoFrameCallback === "function";
    if (rvfc) {
      const tick: VideoFrameRequestCallback = (_, meta) => {
        if (!alive) return;
        this.set(this.fromTime(meta.mediaTime));
        handle = v.requestVideoFrameCallback(tick);
      };
      handle = v.requestVideoFrameCallback(tick);
    } else {
      // ponytail: rVFC yo'q bo'lsa rAF bilan currentTime o'qiladi (kadr aniqligi pastroq)
      const tick = () => {
        if (!alive) return;
        if (!v.paused) this.set(this.fromTime(v.currentTime));
        handle = requestAnimationFrame(tick);
      };
      handle = requestAnimationFrame(tick);
    }
    const onSeeked = () => { if (!rvfc) this.set(this.fromTime(v.currentTime)); };
    v.addEventListener("seeked", onSeeked);
    this.detachFn = () => {
      alive = false;
      if (rvfc) v.cancelVideoFrameCallback(handle); else cancelAnimationFrame(handle);
      v.removeEventListener("seeked", onSeeked);
    };
  }

  detach() {
    this.detachFn?.();
    this.detachFn = null;
    this.video = null;
  }

  seek(f: number) {
    const c = Math.max(0, Math.min(Math.round(f), Math.max(0, this.total - 1)));
    if (this.video) this.video.currentTime = seekTime(c, this.fps);
    this.set(c);
  }

  step(df: number) {
    this.pause();
    this.seek(this.frame + df);
  }

  seekSec(ds: number) {
    this.seek(this.frame + Math.round((ds * this.fps.num) / this.fps.den));
  }

  get playing() { return !!this.video && !this.video.paused; }

  play() {
    if (!this.video) return;
    // L ikkinchi marta: tezroq (1x -> 2x -> 4x)
    if (!this.video.paused) this.video.playbackRate = Math.min(4, this.video.playbackRate * 2);
    else { this.video.playbackRate = 1; void this.video.play().catch(() => undefined); }
  }

  pause() {
    if (!this.video) return;
    this.video.pause();
    this.video.playbackRate = 1;
  }

  toggle() { if (this.playing) this.pause(); else this.play(); }

  get seconds() { return frameToSec(this.frame, this.fps); }
}

export const player = new Player();

/** Joriy kadrdan hosil qilingan qiymat; komponent faqat qiymat o'zgarganda qayta chiziladi. */
export function useFrameValue<T>(fn: (frame: number) => T, deps: unknown[] = []): T {
  const [v, setV] = useState(() => fn(player.frame));
  useEffect(() => {
    setV(fn(player.frame));
    return player.subscribe((f) => setV(fn(f)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return v;
}
