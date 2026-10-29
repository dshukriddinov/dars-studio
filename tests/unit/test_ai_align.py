"""FR-08: sintetik matnlarda (ma'lum chegaralar) Viterbi to'g'ri chegaralarni topadi; beep (TZ 9.6); jurnal."""

import random
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from darsstudio.project.model import Slide, Word
from darsstudio.sync import ai_align, beep, metrics, slide_log

TOPICS = [
    ("Iqlim oʻzgarishi", "global isish harorat issiqxona gazlari karbonat angidrid atmosfera"),
    ("Suv resurslari", "daryo suv tanqisligi sugʻorish Amudaryo Sirdaryo muzliklar"),
    ("Qishloq xoʻjaligi", "hosildorlik paxta bugʻdoy tuproq shoʻrlanishi fermerlar"),
    ("Energetika", "quyosh shamol elektr stansiyalari koʻmir gaz energiya samaradorligi"),
    ("Transport", "avtomobil yoqilgʻi elektromobil temir yoʻl jamoat transporti"),
    ("Bino va inshootlar", "issiqlik izolyatsiya isitish sovutish binolar qurilish"),
    ("Xulosa", "natijalar takliflar siyosat moslashuv yumshatish xulosa"),
]
FILLER = "endi biz bunga qarasak aslida shuni aytish kerakki misol uchun bu juda muhim".split()


def make_lesson(seed: int, seconds_per_slide: list[int]) -> tuple[list[Word], list[Slide], list[float]]:
    rng = random.Random(seed)
    slides = [Slide(index=i + 1, title=t, body=b, notes=f"{t}. {b}") for i, (t, b) in enumerate(TOPICS)]
    words, t_ms, bounds = [], 0, []
    for k, dur in enumerate(seconds_per_slide):
        if k:
            bounds.append(t_ms / 1000)
        vocab = TOPICS[k][1].split() + TOPICS[k][0].split()
        end = t_ms + dur * 1000
        while t_ms < end:
            w = rng.choice(vocab) if rng.random() < 0.45 else rng.choice(FILLER)
            if rng.random() < 0.05:  # ASR xatosi / boshqa mavzudan so'z
                w = rng.choice(rng.choice(TOPICS)[1].split())
            d = rng.randint(250, 550)
            last = t_ms + d >= end   # slayd almashishi gap oxirida (real ma'ruzadagidek)
            text = w + ("." if last or rng.random() < 0.12 else "")
            words.append(Word(text=text, start_ms=t_ms, end_ms=t_ms + d, conf=0.9))
            t_ms += d + (rng.randint(250, 700) if text.endswith(".") else rng.randint(30, 120))
    return words, slides, bounds


def test_ai_align_synthetic_boundaries() -> None:
    fps = Fraction(25)
    res_all = []
    for seed in range(5):
        durs = [40, 55, 35, 60, 45, 50, 30]
        words, slides, gt_s = make_lesson(seed, durs)
        total = int(words[-1].end_ms / 1000 * 25) + 25
        r = ai_align.align(words, slides, total, fps)
        assert r.spans[0].start == 0 and r.spans[-1].end == total
        assert all(a.end == b.start for a, b in zip(r.spans, r.spans[1:], strict=False))
        gt = [metrics.GtBoundary(t, k + 2) for k, t in enumerate(gt_s)]
        pred = metrics.frames_to_pred([(b.frame, b.slide, b in r.suspicious) for b in r.boundaries], fps)
        res_all.append(metrics.evaluate(gt, pred))
    within2 = np.mean([r.within_2s for r in res_all])
    assert within2 >= 0.9, [r.within_2s for r in res_all]
    assert np.median([r.median_err_s for r in res_all]) <= 1.0


def test_ai_align_detects_back_jump() -> None:
    # 1 -> 2 -> 1 (qisqa qaytish, 8 s) -> 2 -> 3
    rng = random.Random(1)
    slides = [Slide(index=i + 1, title=t, body=b) for i, (t, b) in enumerate(TOPICS[:3])]
    words, t = [], 0
    for k, dur in [(0, 40), (1, 40), (0, 8), (1, 30), (2, 40)]:
        end = t + dur * 1000
        while t < end:
            w = rng.choice(TOPICS[k][1].split())
            words.append(Word(text=w + ("." if rng.random() < 0.2 else ""), start_ms=t, end_ms=t + 350, conf=0.9))
            t += 420
    r = ai_align.align(words, slides, int(t / 40) + 10, Fraction(25), ai_align.Params(min_dwell_s=3))
    seq = [s.slide for s in r.spans]
    assert seq[:2] == [1, 2] and seq[-1] == 3
    if 1 in seq[2:]:  # qaytish topilgan bo'lsa, u shubhali deb belgilanadi
        assert any(b.reason == "qisqa orqaga qaytish" for b in r.suspicious)


def test_beep_found_within_10ms() -> None:
    sr = 16000
    rng = np.random.default_rng(3)
    x = (rng.standard_normal(sr * 20) * 0.05).astype(np.float32)
    x[sr * 2: sr * 4] += (np.sin(np.arange(sr * 2) * 0.07) * 0.3).astype(np.float32)  # "nutq"
    at = 7.4321
    tpl = beep.template(sr) * 0.4
    i = int(round(at * sr))
    x[i:i + len(tpl)] += tpl.astype(np.float32)
    r = beep.find_beep(x)
    assert r.reliable and abs(r.start_s - at) <= 0.010, r


def test_slide_log_to_spans(tmp_path: Path) -> None:
    beep_ns = 5_000_000_000
    rows = ["sync_beep_t_ns,5000000000", "t_ns,event,slide_index,build_index",
            f"{beep_ns + 3 * 10**9},SlideShowBegin,1,0", f"{beep_ns + 20 * 10**9},SlideShowNextSlide,2,0",
            f"{beep_ns + 21 * 10**9},SlideShowNextBuild,2,1", f"{beep_ns + 40 * 10**9},SlideShowNextSlide,3,0",
            f"{beep_ns + 40_500_000_000},SlideShowNextSlide,2,0", f"{beep_ns + 60 * 10**9},SlideShowEnd,0,0"]
    f = tmp_path / "log.csv"
    f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    b, ev = slide_log.read_log(f)
    spans, short = slide_log.to_spans(b, ev, beep_video_s=1.5, fps=Fraction(25), total=2000)
    assert [(s.start, s.end, s.slide) for s in spans] == [(0, 538, 1), (538, 1038, 2), (1038, 1050, 3),
                                                          (1050, 2000, 2)]
    assert short == [(1038, 1050)]   # 0.5 s — qisqa oraliq foydalanuvchiga ko'rsatiladi


def test_cue_phrase_snaps_boundary() -> None:
    """Leksik o'xshashlik chegarani oldingi gapga surgan bo'lsa, "xo'p, keyingi slaydimizda" signali uni tuzatadi."""
    fps = Fraction(25)
    words = [Word(text=t, start_ms=s, end_ms=s + 300, conf=0.9) for t, s in
             [("suv", 10000), ("resurslari.", 10400), ("xo'p,", 30000), ("keyingi", 30400), ("slaydimizda", 30800),
              ("energetika", 31300), ("navbatdagi", 50000), ("slaydda", 50400)]]
    bounds = [ai_align.Boundary(frame=int(15 * 25), prev_slide=1, slide=2, confidence=0.9),
              ai_align.Boundary(frame=int(52 * 25), prev_slide=2, slide=3, confidence=0.9),
              ai_align.Boundary(frame=int(80 * 25), prev_slide=3, slide=2, confidence=0.9)]   # orqaga — tegilmaydi
    ai_align.snap_to_cues(bounds, words, fps, window_s=25)
    assert [b.frame for b in bounds] == [30 * 25, 50 * 25, 80 * 25]
    assert bounds[0].reason == "og'zaki signal" and bounds[2].reason == ""
    # oyna tashqarisidagi signal ishlatilmaydi
    far = [ai_align.Boundary(frame=int(2 * 25), prev_slide=1, slide=2, confidence=0.9)]
    ai_align.snap_to_cues(far, words, fps, window_s=10)
    assert far[0].frame == 50


def test_bounds_order_restored(monkeypatch: Any) -> None:
    """Surishlardan keyin chegaralar tartibi buzilsa, oraliqlar baribir monoton va bo'sh emas."""
    orig = ai_align.snap_to_cues

    def swap(bounds: list[ai_align.Boundary], *a: Any) -> None:
        orig(bounds, *a)
        if len(bounds) >= 2:
            bounds[0].frame, bounds[1].frame = bounds[1].frame + 10, bounds[0].frame
    monkeypatch.setattr(ai_align, "snap_to_cues", swap)
    words, slides, _ = make_lesson(0, [40, 55, 35, 60, 45, 50, 30])
    total = int(words[-1].end_ms / 1000 * 25) + 25
    r = ai_align.align(words, slides, total, Fraction(25))
    assert all(s.end - s.start >= 10 for s in r.spans)
    assert [s.start for s in r.spans] == sorted(s.start for s in r.spans)


def test_topic_starts_uzbek_transition_phrases() -> None:
    """DSBA9600 (inson slaydni shu gaplar boshida almashtirgan) va DSBA9359 dagi yolg'on holat."""
    from darsstudio.project.model import Word
    from darsstudio.sync.ai_align import topic_starts
    text = ("o'sha ko'proq oladi. ikkinchi mavzuga o'tamiz. mahalliy byudjet. esa bu to'lanadi. grafikka qarang, "
            "o'z daromadlari. bu haqda beshinchi savolda gaplashamiz. endi aholi ishtiroki haqida gaplashadigan "
            "bo'lsak, ishtirok. uchinchi qismda gap pulni o'zi haqida. bu ikkinchi mavzuga bog'liq gap.")
    ws = [Word(text=t, start_ms=i * 400, end_ms=i * 400 + 300, conf=0.9) for i, t in enumerate(text.split())]
    hits = [next(w.text for w in ws if w.start_ms == ms) for ms in topic_starts(ws)]
    assert hits == ["ikkinchi", "grafikka", "endi", "uchinchi"]   # "bu haqda..." kelajak, gap o'rtasi — emas


def test_b_scene_starts_when_teacher_points_at_slide() -> None:
    """Montajchi (nargiza 2): B "mazkur slaydda keltirilgan rasm" degan joyda; ishora yo'q — a_seconds."""
    from darsstudio.project.model import Word
    from darsstudio.sync.run import b_start_ms
    text = "endi yumshatish haqida gaplashamiz. mazkur slaydda keltirilgan rasm yumshatish va moslashuvni ko'rsatadi."
    ws = [Word(text=t, start_ms=1000 + i * 500, end_ms=1000 + i * 500 + 400, conf=0.9)
          for i, t in enumerate(text.split())]
    slayd = next(w for w in ws if w.text == "slaydda")
    assert b_start_ms(ws, 0, 60000, 9000) == slayd.end_ms          # slayd boshidan 3.5 s: ishora -> B
    assert b_start_ms(ws[:5], 1000, 60000, 9000) == 9000            # ishora yo'q
    assert b_start_ms(ws, slayd.start_ms - 1000, 60000, 9000) != slayd.end_ms   # boshidan 3 s ichida — hali A
