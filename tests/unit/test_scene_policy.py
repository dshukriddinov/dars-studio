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
