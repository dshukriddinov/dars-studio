"""a_then_b: slayd almashganda N s A, keyin B; qisqa slayd va birinchi/oxirgi slayd A."""

from unittest import mock

from darsstudio.project.model import Project, SlideSpan
from darsstudio.render.templates import ScenePolicy
from darsstudio.sync import run


def test_a_then_b() -> None:
    spans = [SlideSpan(start=s, end=e, slide=i, source="ai")
             for i, (s, e) in enumerate([(0, 1000), (1000, 2000), (2000, 2400), (2400, 3000)], 1)]
    p = Project(id="x", name="d", fps="25/1", total_frames=3000, template_id="t", slide_spans=spans)
    stack = mock.Mock(project=p)
    tpl = mock.Mock(scene_policy=ScenePolicy(mode="a_then_b", a_seconds=10, min_b_seconds=10))
    with mock.patch("darsstudio.render.templates.load", return_value=tpl):
        out = run.suggest_layouts(stack)
    # 1 — birinchi (A); 2 — 250 kadr A, 750 B; 3 — 400 kadr < 250+250 -> A; 4 — oxirgi (A)
    assert [(s.start, s.end, s.layout) for s in out] == [(0, 1250, "A"), (1250, 2000, "B"), (2000, 3000, "A")]


def test_fit_body() -> None:
    from darsstudio.render.placement import Body, fit_body
    pl = fit_body(Body(head_y=66, hands_y=848, center_x=1063), head_y=250, hands_y=1025, center_x=1473)
    s = pl.scale
    assert abs(66 * s + pl.y - 250) <= 1 and abs(848 * s + pl.y - 1025) <= 1 and abs(1063 * s + pl.x - 1473) <= 1
    assert fit_body(Body(0, 100, 0), 0, 1000, 0).scale == 1.5          # kattalashtirish chegarasi


def test_thanks_slide_and_unshown() -> None:
    from fractions import Fraction

    from darsstudio.project.model import Slide, Word
    slides = [Slide(index=1, title="Mavzu"), Slide(index=2, title="Saylov"), Slide(index=3, title="Jinoyat"),
              Slide(index=4, title="EʼTIBORINGIZ UCHUN RAHMAT")]
    spans = [SlideSpan(start=0, end=1000, slide=1, source="ai"), SlideSpan(start=1000, end=3000, slide=2, source="ai")]
    ws = [Word(text=t, start_ms=s, end_ms=s + 300, conf=0.9) for t, s in
          [("iborat", 100000), ("edi.", 100400), ("eʼtiboringiz", 101000), ("uchun", 101500), ("rahmat.", 102000)]]
    out = run.thanks_slide(spans, slides, ws, Fraction(25), 3000)
    assert [(s.start, s.end, s.slide) for s in out] == [(0, 1000, 1), (1000, 2518, 2), (2518, 3000, 4)]
    assert run.unshown_slides(out, 4) == [3]
    assert run.thanks_slide(spans, slides[:3], ws, Fraction(25), 3000) == spans       # rahmat slaydi yo'q
