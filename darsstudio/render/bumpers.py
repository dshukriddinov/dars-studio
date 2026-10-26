"""Intro/outro (shablondan) dars boshi va oxiriga, hard cut. Klip bir marta loyiha formatiga kodlanadi (kanvas, fps,
asosiy render bilan bir xil kodek sozlamalari, BT.709 limited) va keshlanadi: video (audiosiz mp4) + audio (WAV 48k,
-16 LUFS, video davomiyligiga aniq tekislangan).
Yig'ish: video — concat demuxer, qayta kodlashsiz (asosiy video ikkinchi marta kodlanmaydi); audio — PCM bo'laklar
namuna aniqligida ulanib bir marta AAC'ga. (AAC'ni concat demuxer bilan -c copy qilish har chokda priming tufayli
~21 ms A/V siljish beradi.)"""

import hashlib
from fractions import Fraction
from pathlib import Path

from darsstudio.audio import loudness
from darsstudio.media import ffmpeg, probe
from darsstudio.render.renderer import BT709_TAGS, encoder_args
from darsstudio.render.templates import Template

SR = 48000


def encode(src: Path, out: Path, fps: Fraction, canvas: tuple[int, int], profile: str) -> int:
    """out (.mp4, audiosiz) + out.with_suffix(".wav"). -> kadrlar soni."""
    pr = probe.probe(src)
    n = int(pr.duration * fps)
    wav = out.with_suffix(".wav")
    if out.is_file() and wav.is_file():
        return n
    dur = f"{float(Fraction(n) / fps):.6f}"
    v = pr.video
    rng = "full" if v.color_range == "pc" else "tv"
    mat = "bt601" if v.color_space in ("smpte170m", "bt470bg") else "bt709"
    cw, ch = canvas
    vf = (f"scale={cw}:{ch}:force_original_aspect_ratio=decrease:flags=lanczos:in_range={rng}:in_color_matrix={mat}"
          f":out_range=tv:out_color_matrix=bt709,pad={cw}:{ch}:-1:-1:black,fps={fps},format=yuv420p")
    tmp = out.with_name(out.stem + ".tmp.mp4")
    ffmpeg.run(["-v", "error", "-nostdin", "-y", "-i", str(src), "-an", "-vf", vf, *encoder_args(profile), *BT709_TAGS,
                "-t", dur, "-movflags", "+faststart", str(tmp)])
    af = (loudness.loudnorm_filter(loudness.measure(src)) + "," if pr.audio else "") + \
        f"aresample={SR},aformat=sample_fmts=s16:channel_layouts=stereo,apad=whole_len={n * SR // fps}"
    src_a = ["-i", str(src)] if pr.audio else ["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo"]
    ffmpeg.run(["-v", "error", "-nostdin", "-y", *src_a, "-af", af, "-t", dur, "-c:a", "pcm_s16le", str(wav)])
    tmp.replace(out)
    return n


def wrap(main: Path, tpl: Template, fps: Fraction, profile: str, cache: Path,
         audio_wav: Path | None = None) -> tuple[int, int]:
    """main.mp4 ni joyida intro + main + outro ga almashtiradi. audio_wav — asosiy qism audiosi (chiqish vaqt o'qida,
    PCM); berilmasa main'dan dekodlanadi. -> (intro, outro) kadrlari."""
    if not (tpl.intro or tpl.outro):
        return 0, 0
    bump: dict[str, tuple[Path, int]] = {}
    for name in {x for x in (tpl.intro, tpl.outro) if x}:
        src = tpl.asset(name)
        key = hashlib.sha256(src.read_bytes() + f"{fps}|{tpl.canvas}|{profile}".encode()).hexdigest()[:16]
        enc = cache / f"bumper_{key}.mp4"
        bump[name] = (enc, encode(src, enc, fps, tpl.canvas, profile))
    q = probe.probe(main)
    n_main = round(q.duration * fps)
    body = main.with_name(main.stem + ".body.mp4")
    ffmpeg.run(["-v", "error", "-nostdin", "-y", "-i", str(main), "-an", "-c", "copy", str(body)])
    parts: list[tuple[Path, Path, int]] = []          # (video, audio manbasi, kadrlar)
    if tpl.intro:
        v, n = bump[tpl.intro]
        parts.append((v, v.with_suffix(".wav"), n))
    parts.append((body, audio_wav or main, n_main))
    if tpl.outro:
        v, n = bump[tpl.outro]
        parts.append((v, v.with_suffix(".wav"), n))
    lst = cache / "bumpers_concat.txt"
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p, _, _ in parts), encoding="utf-8")
    ins, chains = [], []
    for i, (_, a, n) in enumerate(parts, 1):
        ins += ["-i", str(a)]
        ns = n * SR // fps
        chains.append(f"[{i}:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"apad=whole_len={ns},atrim=end_sample={ns}[a{i}]")
    fc = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(1, len(parts) + 1)) + \
        f"concat=n={len(parts)}:v=0:a=1[a]"
    tmp = main.with_name(main.stem + ".tmp.mp4")
    ffmpeg.run(["-v", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), *ins,
                "-filter_complex", fc, "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-ar", str(SR), *BT709_TAGS, "-movflags", "+faststart", str(tmp)])
    tmp.replace(main)
    body.unlink()
    return (bump[tpl.intro][1] if tpl.intro else 0), (bump[tpl.outro][1] if tpl.outro else 0)
