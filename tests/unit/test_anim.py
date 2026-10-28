"""Slayd animatsiyasi: javob o'qituvchi aytganda chiqadi (topshiriqni tushuntirayotganda ko'rinmaydi)."""
from fractions import Fraction

from darsstudio.project.model import AnimStep, LayoutSpan, Slide, SlideSpan, Word
from darsstudio.render import templates
from darsstudio.render.compositor import STEP_FRAMES, Timeline
from darsstudio.slides import anim

FPS = Fraction(25)


def _words(text: str, start_ms: int = 0, step: int = 400) -> list[Word]:
    return [Word(text=t, start_ms=start_ms + i * step, end_ms=start_ms + i * step + 300, conf=0.9)
            for i, t in enumerate(text.split())]


def _slide(**kw: object) -> Slide:
    return Slide(index=1, title="GRAMMAR — QUICK CHECK Simple or Continuous?", body="", **kw)  # type: ignore[arg-type]


SPAN = [SlideSpan(start=0, end=2000, slide=1, source="ai")]


def test_answer_appears_when_teacher_says_it_not_when_task_is_read() -> None:
    # topshiriq: "simple or continuous" (sarlavha) o'qiladi — javob emas; keyin "it's present simple"
    ws = _words("choose if it is simple or continuous let's do it the first one dior makes luxury fashion "
                "yes it's present simple next one dior is currently looking it's present continuous")
    sl = _slide(anim=["Present Simple", "Present Continuous"])
    st = anim.step_times([sl], SPAN, ws, FPS, 2000)
    said = {w.text: w.start_ms for w in ws}
    first_present = next(w.start_ms for w in ws if w.text == "present")
    assert [s.click for s in st] == [1, 2]
    assert st[0].frame == round(Fraction(first_present - anim.LEAD_MS, 1000) * FPS)
    assert st[1].frame > st[0].frame and st[1].frame >= round(Fraction(said["currently"], 1000) * FPS)


def test_short_answer_inside_static_text_is_skipped() -> None:
    # "true or false" sarlavhada: o'qituvchi uni o'qiganda FALSE chiqmasin
    sl = Slide(index=1, title="READING — TRUE OR FALSE", body="Dior started in 1946.", anim=["FALSE"])
    ws = _words("now true or false questions number one dior started in 1946 no it's false")
    st = anim.step_times([sl], SPAN, ws, FPS, 2000)
    last_false = [w.start_ms for w in ws if w.text == "false"][-1]
    assert st[0].frame == round(Fraction(last_false - anim.LEAD_MS, 1000) * FPS)


def test_unfound_answers_are_placed_late_never_early() -> None:
    sl = _slide(anim=["Asking opinions", "Agreeing"])
    ws = _words("today we will practise phrases for meetings", 0)
    st = anim.step_times([sl], SPAN, ws, FPS, 2000)
    end_ms = 2000 * 1000 // 25
    assert [s.frame for s in st] == [round(Fraction(end_ms - 2 * anim.LATE_STEP_MS, 1000) * FPS),
                                     round(Fraction(end_ms - anim.LATE_STEP_MS, 1000) * FPS)]


def test_display_spans_and_image_ids() -> None:
    spans = [SlideSpan(start=0, end=100, slide=1, source="ai"), SlideSpan(start=100, end=400, slide=2, source="ai")]
    steps = [AnimStep(slide=2, click=1, frame=200), AnimStep(slide=2, click=2, frame=300)]
    assert anim.display_spans(spans, steps, {2: 2}) == [(0, 1, 0), (100, 2, 0), (200, 2, 1), (300, 2, 2)]
    assert anim.display_spans(spans, [], {2: 2}) == [(0, 1, 0), (100, 2, 2)]      # vaqt yo'q — yakuniy holat
    assert anim.image_id(7, 0) == 7 and anim.image_id(7, 3) % 1000 == 7


def test_step_transition_is_short_fade_not_slide_wipe() -> None:
    tpl = templates.load("demo")
    spans = [SlideSpan(start=0, end=100, slide=1, source="ai"), SlideSpan(start=100, end=400, slide=2, source="ai")]
    display = anim.display_spans(spans, [AnimStep(slide=2, click=1, frame=250)], {2: 1})
    tl = Timeline.build(spans, [LayoutSpan(start=0, end=400, layout="A")], tpl, display)
    slide_mix = [f for f in range(0, 120) if tl.slide(f)[2] < 1]
    step_mix = [f for f in range(150, 300) if tl.slide(f)[2] < 1]
    assert slide_mix == list(range(100 - tpl.transitions.slide_frames, 100))
    assert step_mix == list(range(250 - STEP_FRAMES, 250))
    assert tl.slide(250)[0] == anim.image_id(2, 1) and tl.slide(249)[1] == anim.image_id(2, 0)


def test_all_answers_box_appears_when_teacher_starts_answers() -> None:
    # Unit 4: bitta bosishda "Answers: 1→e 2→h ..." — o'qituvchi "now answers" deganda
    sl = Slide(index=1, title="PRACTICAL TASK 1", body="Match the words.",
               anim=["Answers: 1→e  2→h  3→a  4→d  5→f  6→b  7→g  8→c"])
    ws = _words("match the words with definitions take your time okay now answers first one is e")
    st = anim.step_times([sl], SPAN, ws, FPS, 2000)
    at = next(w.start_ms for w in ws if w.text == "answers")
    assert st[0].frame == round(Fraction(at - anim.LEAD_MS, 1000) * FPS)
