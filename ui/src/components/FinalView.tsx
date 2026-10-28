// "Tayyor video" ekrani (Batafsil tahrir): butun dars bir marta fonda render qilinadi (render vazifasi, alohida
// jarayon), keyin asosiy pleyer bilan sinxron ko'rsatiladi. Asl kadr -> chiqish kadri render paytidagi saqlangan
// oraliqlar (keep) bo'yicha; kesilgan joyda "kesiladi" belgisi. Ovoz asosiy pleyerdan (bu video ovozsiz).
import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useStore } from "../store";
import { api, urls } from "../lib/api";
import { player } from "../lib/player";
import { seekTime, type Fps } from "../lib/time";
import { StatusBadge } from "./StatusBadge";

/** Asl kadr -> tayyor videodagi kadr; kesilgan bo'lsa null. keep — [start, end) saralangan. */
export function srcToOut(keep: [number, number][], f: number): number | null {
  let acc = 0;
  for (const [s, e] of keep) {
    if (f < s) return null;
    if (f < e) return acc + (f - s);
    acc += e - s;
  }
  return null;
}

type Info = { file: string | null; keep?: [number, number][]; stale?: boolean };

export function FinalView({ name, fps }: { name: string; fps: Fps }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [info, setInfo] = useState<Info | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [cut, setCut] = useState(false);
  const job = useStore((s) => (jobId !== null ? s.jobs[jobId] : undefined));
  const view = useStore((s) => s.view);
  const fail = useStore((s) => s.fail);

  const done = job?.status === "tayyor";
  useEffect(() => {
    api.finalPreview(name).then(setInfo).catch(() => setInfo({ file: null }));
  }, [name, view?.project, done]);

  // sinxron: pauzada aniq kadr, ijroda o'ynaydi va 0.15 s dan ortiq siljisa tuzatiladi
  useEffect(() => {
    const keep = info?.keep;
    if (!keep) return;
    const sync = (f: number) => {
      const v = ref.current;
      if (!v) return;
      const g = srcToOut(keep, f);
      setCut(g === null);
      if (g === null) { if (!v.paused) v.pause(); return; }
      const t = seekTime(g, fps);
      if (player.playing) {
        if (v.paused) void v.play().catch(() => undefined);
        if (Math.abs(v.currentTime - t) > 0.15) v.currentTime = t;
      } else {
        if (!v.paused) v.pause();
        if (Math.abs(v.currentTime - t) > 0.5 / (fps.num / fps.den)) v.currentTime = t;
      }
    };
    sync(player.frame);
    const src = player.video;
    const now = () => sync(player.frame);
    src?.addEventListener("play", now); src?.addEventListener("pause", now);
    const off = player.subscribe(sync);
    return () => { off(); src?.removeEventListener("play", now); src?.removeEventListener("pause", now); };
  }, [info, fps]);

  const start = async () => {
    try { setJobId((await api.finalPreviewStart(name)).id); } catch (e) { fail(e); }
  };
  const busy = jobId !== null && !done && job?.status !== "xato" && job?.status !== "toʻxtatildi";

  if (!info) return <div className="final-empty" />;
  if (!info.file) {
    return (
      <div className="final-empty">
        <p>Tayyor video hali yoʻq. Butun dars bir marta tayyorlanadi (16 daqiqalik dars ~7 daqiqa), keyin bu yerda
          asosiy pleyer bilan birga oʻynaydi.</p>
        {busy ? <StatusBadge status={job?.status ?? "navbatda"} progress={job?.progress} />
          : <button className="btn-primary sm" onClick={start}>Tayyorlash</button>}
      </div>
    );
  }
  return (
    <div className="final-wrap">
      <video ref={ref} src={`${urls.file(name, info.file)}`} preload="auto" muted onClick={() => player.toggle()} />
      {cut ? <div className="final-cut">Bu joy kesiladi</div> : null}
      {info.stale || busy ? (
        <div className="final-stale">
          {busy ? <StatusBadge status={job?.status ?? "navbatda"} progress={job?.progress} /> : (
            <>
              <span>Oʻzgarishlardan keyin eskirgan</span>
              <button className="btn-secondary sm" onClick={start}><RefreshCw size={14} /> Yangilash</button>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
