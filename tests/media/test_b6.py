"""B6 DoD: pauza takliflari, kesishlar bilan render (kadr soni = TimeMap.out_total, A/V <= 1 kadr), loudness AC-08,
ko'z patchlari (format, rampa), SRT (monoton, satr cheklovlari), lower-third."""

import re
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from darsstudio.audio import extract, mix
from darsstudio.export import srt
from darsstudio.media import ffmpeg, frames, probe
from darsstudio.media.timemap import TimeMap
from darsstudio.project import cuts
from darsstudio.project.model import CutProposal, EyeOffSpan, KeySettings, Word
from darsstudio.render import eyepatch, overlays, renderer, templates

FPS = Fraction(25)


def W(t: str, s: int, e: int) -> Word:
    return Word(text=t, start_ms=s, end_ms=e, conf=0.9)


def test_propose_cuts_never_inside_words() -> None:
    words = [W("bir", 0, 400), W("ikki", 500, 900), W("uch.", 3000, 3400), W("tort", 3500, 3900),
             W("besh", 6000, 6500)]
    vad_sil = [(900, 2950), (3950, 5900), (6600, 8000)]
    props = cuts.propose(words, vad_sil, FPS, total=200)
    # (900..2950) -> 1075..2775 ms -> [27, 69); (3950..5900) -> [104, 143); oxiri -> [170, 200)
    assert [(c.start, c.end) for c in props] == [(27, 69), (104, 143), (170, 200)]
    for c in props:
        c.status = "tasdiqlangan"
    assert cuts.check_no_word_cut(props, words, FPS) == []
    bad = CutProposal(start=5, end=20, reason="manual", status="tasdiqlangan")       # "bir" yarmidan
    assert cuts.check_no_word_cut([bad], words, FPS) == [bad]
    whole = CutProposal(start=11, end=24, reason="manual", status="tasdiqlangan")    # "ikki" butunligicha (matndan)
    assert cuts.check_no_word_cut([whole], words, FPS) == []
    pause = CutProposal(start=11, end=24, reason="pause", status="tasdiqlangan")     # avtomatik — so'zga tegmasin
    assert cuts.check_no_word_cut([pause], words, FPS) == [pause]
    # oraliqsiz so'zlar (DSBA9600: "etaman." tugashi = "musiqa" boshi): chegara kadrga yaxlitlanib so'zga 1 kadrdan
    # kam kirsa — xato emas; ko'proq kirsa — xato
    glued = [W("etaman.", 0, 1000), W("musiqa", 1000, 2000)]
    near = CutProposal(start=26, end=60, reason="manual", status="tasdiqlangan")     # 1040 ms: 40 ms ichkarida
    far = CutProposal(start=28, end=60, reason="manual", status="tasdiqlangan")      # 1120 ms
    assert cuts.check_no_word_cut([near], glued, FPS) == []
    assert cuts.check_no_word_cut([far], glued, FPS) == [far]


def test_assemble_audio_length_and_crossfade() -> None:
    tm = TimeMap([(0, 50), (80, 130), (131, 200)], FPS)
    src = np.ones((200 * 1920 + 1000, 2), np.float32) * 0.5
    out = mix.assemble(src, tm)
    assert len(out) == sum(e - s for s, e in tm.audio_ranges()) == tm.out_total * 1920
    # doimiy signalda equal-power crossfade: birlashishda amplituda 0.5*(cos+sin) <= 0.5*sqrt(2), "chiq" yo'q
    assert out.max() <= 0.5 * np.sqrt(2) + 1e-6 and out.min() >= 0.5 - 1e-6


def test_final_audio_loudness_ac08(tmp_path: Path) -> None:
    src = tmp_path / "s.wav"
    ffmpeg.run(["-v", "error", "-f", "lavfi", "-i", "anoisesrc=a=0.05:r=48000:d=20:seed=2,lowpass=f=3000",
                "-f", "lavfi", "-i", "sine=f=300:r=48000:d=20", "-filter_complex",
                "[0][1]amix=inputs=2:normalize=0,volume=0.3", "-ac", "2", str(src)])
    tm = TimeMap([(0, 100), (150, 500)], FPS)
    m = mix.final_audio(src, tm, tmp_path / "o.wav")
    assert abs(m.integrated - (-16)) <= 1.0 and m.true_peak <= -1.5 + 0.2, m
    assert abs(len(extract.read_pcm(tmp_path / "o.wav", 48000, 2)) - tm.out_total * 1920) <= 1024


def test_eyepatch_apply_and_ramp() -> None:
    w, h = 64, 32
    frame = np.full(w * h * 3 // 2, 100, np.uint8)
    ym = np.zeros((8, 8), bool)
    ym[2:4, 2:4] = True
    uvm = np.zeros((4, 4), bool)
    uvm[1, 1] = True
    rec = {"box": (10, 6, 18, 14), "size": (w, h), "y_mask": ym, "uv_mask": uvm,
           "y_data": np.full(4, 200, np.uint8), "uv_data": np.array([50, 150], np.uint8)}
    f1 = frame.copy()
    eyepatch.apply(f1, rec, 1.0)
    Y = f1[: w * h].reshape(h, w)
    assert (Y[8:10, 12:14] == 200).all() and (Y != 100).sum() == 4
    U = f1[w * h: w * h + w * h // 4].reshape(h // 2, w // 2)
    V = f1[w * h + w * h // 4:].reshape(h // 2, w // 2)
    assert U[4, 6] == 50 and V[4, 6] == 150 and (U != 100).sum() == 1
    f2 = frame.copy()
    eyepatch.apply(f2, rec, 0.5)
    assert (f2[: w * h].reshape(h, w)[8:10, 12:14] == 150).all()
    off = [EyeOffSpan(start=100, end=200)]
    ws = [eyepatch.weight(f, off) for f in range(85, 215)]
    assert eyepatch.weight(150, off) == 0 and eyepatch.weight(50, off) == 1 and eyepatch.weight(250, off) == 1
    assert all(abs(a - b) <= 1 / 8 for a, b in zip(ws, ws[1:], strict=False))   # silliq (sakrashsiz)


def test_srt_cues(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    words, t = [], 0
    for i in range(300):
        d = int(rng.integers(200, 500))
        txt = ["oʻzbekiston", "taʼlim", "iqlim", "suv", "energiya", "2010-yil"][i % 6] + ("." if i % 9 == 8 else "")
        words.append(W(txt, t, t + d))
        t += d + int(rng.integers(50, 200))
    tm = TimeMap.from_cuts(int(t / 40) + 10, [(100, 150), (400, 420)], FPS)
    words = [w for w in words if all(tm.src_to_out(int(Fraction(x, 1000) * FPS)) is not None
                                     for x in (w.start_ms, w.end_ms - 1))]
    cues = srt.build_cues(words, tm)
    text = srt.to_srt(cues)
    assert all(c.start_ms < c.end_ms for c in cues)
    assert all(a.end_ms <= b.start_ms for a, b in zip(cues, cues[1:], strict=False))   # monoton, ustma-ust emas
    for c in cues:
        lines = c.text.split("\n")
        assert len(lines) <= 2 and all(len(x) <= 42 for x in lines)
        assert (c.end_ms - c.start_ms) <= 7000
    assert "oʻzbekiston" in text.lower() and re.search(r"\d\d:\d\d:\d\d,\d\d\d --> ", text)
    assert cues[-1].end_ms <= tm.out_total * 40


def test_lower_third_layer() -> None:
    lt = overlays.lower_third({"oqituvchi": "Nargiza Dalmuradova", "fan": "Iqlim siyosati", "mavzu": "Moslashuv"},
                              (1920, 1080))
    assert lt is not None and lt.shape == (1080, 1920, 4) and lt[..., 3].max() == 255 and lt[:500, :, 3].max() == 0
    assert overlays.lower_third({}, (1920, 1080)) is None
    assert overlays.lower_third_alpha(0, FPS, 6) == 0 and overlays.lower_third_alpha(50, FPS, 6) == 1
    assert overlays.lower_third_alpha(150, FPS, 6) == 0


def test_render_with_cuts_av_sync(tmp_path: Path, test_media: dict[str, Any]) -> None:
    """Kesish (30..60) oqibatida 100-kadrdagi chaqnash chiqishda 70-kadrda; beep ham 70/25 s da (+-1 kadr)."""
    from tests.media.test_render import setup_project
    src = tmp_path / "flash.mov"
    beep_t = 0.052 + 100 / 25
    ffmpeg.run(["-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=1920x1080:r=25:d=6,drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='eq(n,100)',"
                "settb=1/25000,setpts=PTS+1300", "-f", "lavfi", "-i",
                f"aevalsrc=0.5*sin(2*PI*1000*t)*between(t\\,{beep_t}\\,{beep_t + 0.2}):s=48000:d=7",
                "-map", "0:v", "-map", "1:a", "-fps_mode", "passthrough", "-copyts", "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "18", "-bf", "0", "-pix_fmt", "yuv420p", "-enc_time_base:v",
                "1/25000", "-video_track_timescale", "25000", "-movie_timescale", "25000", "-c:a", "pcm_s16le",
                str(src)])
    st, pr, pngs, warped = setup_project(str(src), test_media["lesson.pptx"]["path"], tmp_path)
    n = st.project.total_frames
    st.do("sozlamalar", {"key": KeySettings(key_cbcr=(-0.17, -0.27), tolerance=0.1).model_dump(mode="json"),
                         "placement": {"scale": 0.5, "x": 1100, "y": 500, "color": {}},
                         "slide_spans": [{"start": 0, "end": n, "slide": 1, "source": "manual", "confidence": 1.0,
                                          "approved": True}],
                         "layout_spans": [{"start": 0, "end": n, "layout": "A", "suggested": False}],
                         "cuts": [{"start": 30, "end": 60, "reason": "pause", "status": "tasdiqlangan"}]})
    p = st.project
    tm = cuts.timemap(p)
    assert tm.out_total == n - 30
    wav = extract.extract_wav(pr, tmp_path / "a48.wav")
    ff = mix.final_audio(wav, tm, tmp_path / "final.wav")
    assert ff.integrated > -30
    out = tmp_path / "out.mp4"
    lt = overlays.lower_third({"oqituvchi": "Test"}, (1920, 1080))
    renderer.render(p, pr, templates.load("demo"), warped, pngs, p.slide_spans, p.layout_spans, out,
                    tmp_path / "r", renderer.RenderOptions(chunk_sec=2),
                    renderer.RenderInputs(timemap=tm, audio_wav=tmp_path / "final.wav", lower_third=lt))
    q = probe.probe(out)
    assert q.video.nb_frames == tm.out_total
    with frames.FrameReader(q) as r:
        luma = [float(frames.planes(f, 1920, 1080)[0][700:900, 1300:1600].mean()) for f in r]
    assert int(np.argmax(luma)) == 70
    a = extract.read_pcm(out, 48000, 1)
    onset = int(np.argmax(np.abs(a) > 0.05)) / 48000
    assert abs(onset - 70 / 25) <= 1 / 25, onset
    assert q.audio is not None and abs(float(q.duration) - tm.out_total / 25) <= 1 / 25


@pytest.mark.parametrize("ms, out_ms", [(0, 0), (1000, 1000), (1300, 1000), (3000, 2000)])
def test_srt_time_mapping(ms: int, out_ms: int) -> None:
    tm = TimeMap.from_cuts(200, [(25, 50)], FPS)  # 1..2 s kesilgan
    got = srt._out_ms(ms, tm)
    if 1000 <= ms < 2000:
        assert got is None
    else:
        assert got == out_ms


def test_akademiya_overlays() -> None:
    meta = {"oqituvchi": "Dalmuradova Nargiza", "unvon": "Dotsent | (PhD)"}
    ovs = overlays.build(meta, "akademiya", 8.6, "Mazkur taqdimot akademiya mahsuloti", 900, 1000, FPS, (1920, 1080))
    bar, txt, cp = ovs
    assert (bar.start, bar.end, txt.end) == (0, 215, 215) and bar.fade_frames == 0
    assert bar.layer[900, 100, 3] > 200 and bar.layer[900, 1500, 3] == 0      # chapda ko'k, o'ngga shaffof
    assert txt.shift_at(0) == 0 and txt.shift_at(25) == -16                    # 16 px/s chapga
    assert (cp.start, cp.end) == (900, 1000) and cp.alpha_at(899) == 0 and cp.alpha_at(950) == 1
    assert overlays.build({}, "akademiya", 8.6, None, None, 1000, FPS, (1920, 1080)) == []


def test_glyph_safe_okina() -> None:
    f = overlays.slab(700, 44)                       # Roboto Slab: U+02BB yo'q, U+2018 bor
    assert overlays.glyph_safe("Gʻaybullayevich", f) == "G‘aybullayevich"
    assert overlays.glyph_safe("Gʻ", overlays.font(True, 30)) in ("Gʻ", "G‘")


def test_copyright_slides_in_from_right() -> None:
    """Oxirgi 5 s: 640 px o'ngdan 3 s da chiziqli kirib keladi, keyin joyida; polosa o'ng chetidan tashqari yo'q."""
    ovs = overlays.build({}, "akademiya", 8.6, "Mazkur taqdimot", 875, 1000, FPS, (1920, 1080), cp_slide=(3.0, 640))
    (cp,) = ovs
    assert (cp.start, cp.end, cp.slide_frames, cp.clip_x) == (875, 1000, 75, overlays.COPYRIGHT_BOX_X1)
    assert [cp.shift_at(875 + k) for k in (0, 25, 50, 75, 120)] == [640, 427, 213, 0, 0]
    assert cp.moves() and not overlays.Overlay(cp.layer, 0, 1).moves()
