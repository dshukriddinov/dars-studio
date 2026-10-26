"""B3 DoD: keyer (garbage alfa = 0), warp (ramkadan chiqmaydi), o'tishlar, renderer (A/V sinxron, chunk resume).
GPU bo'lsa CUDA'da, bo'lmasa CPU'da (sekinroq)."""

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
import torch

from darsstudio.media import ffmpeg, frames, probe
from darsstudio.project import importer
from darsstudio.project.commands import CommandStack
from darsstudio.project.model import KeySettings, LayoutSpan, SlideSpan
from darsstudio.render import keyer, renderer, templates
from darsstudio.render.compositor import Timeline
from darsstudio.slides import warp

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def first_frame_planes(path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, probe.ProbeResult]:
    p = probe.probe(path)
    with frames.FrameReader(p, start=40, count=1) as r:
        f = r.read()
    assert f is not None
    y, u, v = frames.planes(f, p.video.width, p.video.height)
    return y, u, v, p


def test_keyer_suggest_and_garbage(test_media: dict[str, Any]) -> None:
    exp = test_media["green_key.mp4"]
    y, u, v, p = first_frame_planes(exp["path"])
    ks = keyer.suggest(y, u, v, p.full_range)
    wx0 = exp["wall_box"][0]
    # garbage oq devorni qoplaydi
    g = keyer.raster_polys(ks.garbage_polys, 1920, 1080)
    assert g[:, wx0 + 2:].all() and not g[:, : wx0 - 20].any()
    t = lambda a: torch.from_numpy(np.ascontiguousarray(a)).unsqueeze(0).to(DEV)  # noqa: E731
    a = keyer.Keyer(ks, 1920, 1080, p.full_range, DEV)(t(y), t(u), t(v)).alpha[0, 0].cpu().numpy()
    assert a[g].max() == 0.0                          # garbage hududida alfa aynan 0
    assert a[50:300, 100:600].max() < 0.01            # yashil fon
    pw, ph = exp["person_size"]
    yc = exp["person_y"] + ph // 2
    row = a[yc]
    assert row.max() > 0.99 and (row > 0.99).sum() > pw * 0.8   # "odam" kesimi to'liq


def test_keyer_spill_reduces_green() -> None:
    # yashil fonga 50% aralashgan kulrang chegara piksel: spill G ni max(R, B) gacha tushiradi
    s = KeySettings(key_cbcr=(-0.17, -0.27), tolerance=0.05, softness=0.3, spill=1.0)
    rgb = np.array([[[0.45, 0.7, 0.4]]], np.float32)
    ycc = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)  # BT.601, faqat test kirishi uchun
    y8 = np.full((2, 2), int(ycc[0, 0, 0] * 219 + 16), np.uint8)
    u8 = np.full((1, 1), int((ycc[0, 0, 2] - 0.5) * 224 + 128), np.uint8)
    v8 = np.full((1, 1), int((ycc[0, 0, 1] - 0.5) * 224 + 128), np.uint8)
    t = lambda a: torch.from_numpy(a).unsqueeze(0)  # noqa: E731
    k = keyer.Keyer(s, 2, 2, False, torch.device("cpu"), guided_chroma=False)
    r = k(t(y8), t(u8), t(v8))
    a = float(r.alpha[0, 0, 0, 0])
    rr, gg, bb = (float(c) / max(a, 1e-6) for c in r.rgb[0, :, 0, 0])
    assert 0 < a < 1 and gg <= max(rr, bb) + 1e-4


def test_warp_stays_inside_quad() -> None:
    tpl = templates.load("demo")
    slide = np.full((2160, 3840, 3), 255, np.uint8)
    out = warp.warp_slide(slide, tpl.screen_quad, tpl.canvas)
    inside1 = warp.quad_mask(tpl.screen_quad, tpl.canvas, dilate_px=1)
    assert out[..., 3][~inside1].max() == 0           # 1 px dan ortiq chiqmaydi
    core = cv2.erode(warp.quad_mask(tpl.screen_quad, tpl.canvas).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    assert out[..., 3][core].min() == 255 and out[..., :3][core].min() >= 254
    # 4:3 slayd: pillarbox (chap/o'ng chekka qora), markaz oq
    s43 = np.full((1536, 2048, 3), 255, np.uint8)
    o43 = warp.warp_slide(s43, ((0, 0), (1920, 0), (1920, 1080), (0, 1080)), (1920, 1080))
    assert o43[540, 100, :3].max() < 5 and o43[540, 960, :3].min() > 250


def test_timeline_transition_lengths() -> None:
    tpl = templates.load("demo")
    ss = [SlideSpan(start=0, end=100, slide=1, source="manual"),
          SlideSpan(start=100, end=300, slide=2, source="manual")]
    ls = [LayoutSpan(start=0, end=150, layout="A"), LayoutSpan(start=150, end=250, layout="B"),
          LayoutSpan(start=250, end=300, layout="A")]
    tl = Timeline.build(ss, ls, tpl)
    n_s, n_l = tpl.transitions.slide_frames, tpl.transitions.layout_frames
    # o'tish chegaradan OLDIN n kadr va chegarada tugaydi (yangi slayd gap boshida to'liq ko'rinadi)
    mixing = [f for f in range(300) if tl.slide(f)[2] < 1]
    assert mixing == list(range(100 - n_s, 100))
    assert tl.slide(100) == (2, 2, 1.0) and tl.slide(99)[:2] == (2, 1)
    for start in (150, 250):  # A->B va B->A
        mix = [f for f in range(start - 30, start + 30) if tl.layout(f)[2] < 1]
        assert mix == list(range(start - n_l, start))
        ws = [tl.layout(f)[2] for f in mix]
        assert ws == sorted(ws) and 0 < ws[0] < ws[-1] < 1
    assert tl.layout(150 - n_l - 1) == ("A", "A", 1.0) and tl.layout(150) == ("B", "B", 1.0)
    assert tl.layout(249)[:2] == ("A", "B") and tl.layout(250) == ("A", "A", 1.0)


def make_slides(n: int, d: Path) -> list[Path]:
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(1, n + 1):
        img = np.full((2160, 3840, 3), (40 * i % 255, 200, 255 - 20 * i % 255), np.uint8)
        cv2.putText(img, str(i), (1500, 1400), cv2.FONT_HERSHEY_SIMPLEX, 30, (0, 0, 0), 60)
        p = d / f"{i:03d}.png"
        cv2.imwrite(str(p), img)
        out.append(p)
    return out


def setup_project(video: str, pptx: str, tmp: Path) -> tuple[CommandStack, probe.ProbeResult, list[Path], list[Path]]:
    store = importer.import_project(Path(video), Path(pptx), "demo", tmp / "w", make_proxy=False)
    st = CommandStack(store)
    tpl = templates.load("demo")
    pngs = make_slides(len(st.project.slides), tmp / "slides")
    warped = warp.warp_all(pngs, tpl, tmp / "warped")
    return st, probe.probe(video), pngs, warped


def test_render_av_sync_with_offset(tmp_path: Path, test_media: dict[str, Any]) -> None:
    """Manbada video audiodan 52 ms keyin; 100-kadr oq chaqnash, beep aynan shu kadr ko'rsatilgan paytda.
    Chiqishda chaqnash kadri va beep vaqti 1 kadr (40 ms) ichida mos bo'lishi kerak (AC-07)."""
    src = tmp_path / "flash.mov"
    beep_t = 0.052 + 100 / 25   # audio vaqt o'qida
    ffmpeg.run(["-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=1920x1080:r=25:d=6,drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='eq(n,100)',"
                "settb=1/25000,setpts=PTS+1300",
                "-f", "lavfi", "-i",
                f"aevalsrc=0.5*sin(2*PI*1000*t)*between(t\\,{beep_t}\\,{beep_t + 0.2}):s=48000:d=7",
                "-map", "0:v", "-map", "1:a", "-fps_mode", "passthrough", "-copyts", "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "18", "-bf", "0", "-pix_fmt", "yuv420p",
                "-enc_time_base:v", "1/25000", "-video_track_timescale", "25000", "-movie_timescale", "25000",
                "-c:a", "pcm_s16le", str(src)])
    p0 = probe.probe(src)
    assert p0.av_offset == Fraction(52, 1000)
    st, pr, pngs, warped = setup_project(str(src), test_media["lesson.pptx"]["path"], tmp_path)
    n = st.project.total_frames
    st.do("key", {"key": KeySettings(key_cbcr=(-0.17, -0.27), tolerance=0.1).model_dump(mode="json"),
                  "placement": {"scale": 0.5, "x": 1100, "y": 500, "color": {}},
                  "slide_spans": [{"start": 0, "end": n, "slide": 1, "source": "manual", "confidence": 1.0,
                                   "approved": True}],
                  "layout_spans": [{"start": 0, "end": n, "layout": "A", "suggested": False}]})
    p = st.project
    out = tmp_path / "out.mp4"
    renderer.render(p, pr, templates.load("demo"), warped, pngs, p.slide_spans, p.layout_spans, out,
                    tmp_path / "render", renderer.RenderOptions(chunk_sec=2))
    q = probe.probe(out)
    assert q.video.nb_frames == n
    with frames.FrameReader(q) as r:
        luma = [float(frames.planes(f, 1920, 1080)[0][700:900, 1300:1600].mean()) for f in r]
    flash = int(np.argmax(luma))
    assert flash == 100
    proc = ffmpeg.popen(["-v", "error", "-i", str(out), "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-f", "f32le",
                         "-"], stdout=True)
    assert proc.stdout is not None
    audio = np.frombuffer(proc.stdout.read(), np.float32)
    proc.wait()
    assert q.audio is not None
    onset = int(np.argmax(np.abs(audio) > 0.1)) / 48000 + float(q.audio.start_time - q.video.start_time)
    assert abs(onset - flash / 25) <= 1 / 25, (onset, flash / 25)


def test_render_scenes_and_resume(tmp_path: Path, test_media: dict[str, Any]) -> None:
    """A->B->A: B kadri to'liq ekran slayd, A kadrida slayd ekranda va o'qituvchi joyida; qayta render
    checkpoint'dan (segmentlar qayta yozilmaydi)."""
    st, pr, pngs, warped = setup_project(test_media["av_offset.mov"]["path"], test_media["lesson.pptx"]["path"],
                                         tmp_path)
    tpl = templates.load("demo")
    n = st.project.total_frames  # 300
    st.do("vaqtlar", {
        "key": KeySettings(key_cbcr=(-0.17, -0.27), tolerance=0.1).model_dump(mode="json"),
        "placement": {"scale": 0.4, "x": 1150, "y": 600, "color": {}},
        "slide_spans": [{"start": 0, "end": 100, "slide": 1, "source": "manual", "confidence": 1.0, "approved": True},
                        {"start": 100, "end": n, "slide": 2, "source": "manual", "confidence": 1.0, "approved": True}],
        "layout_spans": [{"start": 0, "end": 150, "layout": "A", "suggested": False},
                         {"start": 150, "end": 250, "layout": "B", "suggested": False},
                         {"start": 250, "end": n, "layout": "A", "suggested": False}]})
    p = st.project
    out = tmp_path / "o.mp4"
    opts = renderer.RenderOptions(chunk_sec=4, profile="arxiv")
    rep = renderer.render(p, pr, tpl, warped, pngs, p.slide_spans, p.layout_spans, out, tmp_path / "r", opts)
    assert rep.frames == n == probe.probe(out).video.nb_frames
    with frames.FrameReader(probe.probe(out)) as r:
        fr = {i: f for i, f in enumerate(r) if i in (50, 200, 290)}
    full2 = cv2.cvtColor(warp.fit_contain(warp.read_rgb(pngs[1]), 1920, 1080), cv2.COLOR_RGB2YUV_I420).ravel()
    y200 = frames.planes(fr[200], 1920, 1080)[0].astype(int)
    exp_y = full2[: 1920 * 1080].reshape(1080, 1920).astype(int)
    # B: to'liq ekran slayd (logo hududidan tashqari)
    assert np.abs(y200[100:900, 100:1500] - exp_y[100:900, 100:1500]).mean() < 6
    y50 = frames.planes(fr[50], 1920, 1080)[0]
    bg = cv2.cvtColor(warp.read_rgb(tpl.asset(tpl.background)), cv2.COLOR_RGB2YUV_I420)[:1080]
    assert abs(int(y50[60:120, 1300:1500].mean()) - int(bg[60:120, 1300:1500].mean())) < 6   # A: fon ko'rinadi
    seg_mtimes = {s: s.stat().st_mtime_ns for s in (tmp_path / "r").rglob("seg_*.mp4")}
    assert len(seg_mtimes) == 3
    renderer.render(p, pr, tpl, warped, pngs, p.slide_spans, p.layout_spans, out, tmp_path / "r", opts)
    assert {s: s.stat().st_mtime_ns for s in seg_mtimes} == seg_mtimes
    rj = json.loads(out.with_suffix(".render.json").read_text(encoding="utf-8"))
    assert rj["frames"] == n


@pytest.mark.parametrize("csv_text, expect", [
    ("start,slide,layout\n0,1,A\n0:04,2,B\n8,3\n", [(0, 100, 1), (100, 200, 2), (200, 300, 3)]),
    ("start,slide\n2,1\n4,2\n", [(0, 100, 1), (100, 300, 2)]),
])
def test_read_slides_csv(tmp_path: Path, csv_text: str, expect: list[tuple[int, int, int]]) -> None:
    from darsstudio.render import prepare
    f = tmp_path / "t.csv"
    f.write_text(csv_text, encoding="utf-8")
    ss, ls = prepare.read_slides_csv(f, Fraction(25), 300, 12)
    assert [(s.start, s.end, s.slide) for s in ss] == expect
    assert ls[0].start == 0 and ls[-1].end == 300
