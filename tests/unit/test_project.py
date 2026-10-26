"""B2: loyiha modeli invariantlari, atomik saqlash, buyruqlar (undo/redo) va tarixni qayta ochish."""

import json
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from darsstudio.project import commands
from darsstudio.project.model import LayoutSpan, Project, Slide, SlideSpan
from darsstudio.project.store import ProjectStore

TOTAL = 1000


def make_project() -> Project:
    return Project(id="p1", name="test", fps="30000/1001", total_frames=TOTAL, template_id="demo",
                   slides=[Slide(index=i, title=f"S{i}") for i in range(1, 6)],
                   slide_spans=[SlideSpan(start=0, end=400, slide=1, source="ai"),
                                SlideSpan(start=400, end=TOTAL, slide=2, source="ai")],
                   layout_spans=[LayoutSpan(start=0, end=TOTAL, layout="A")])


def test_invariants() -> None:
    p = make_project()
    assert p.fps == "30000/1001"
    data = p.model_dump(mode="json")
    data["slide_spans"][1]["start"] = 410        # bo'shliq
    with pytest.raises(ValidationError, match="bo'shliq"):
        Project.model_validate(data)
    data["slide_spans"][1]["start"] = 390        # ustma-ust
    with pytest.raises(ValidationError, match="ustma-ust"):
        Project.model_validate(data)
    data = p.model_dump(mode="json")
    data["layout_spans"][0]["end"] = TOTAL - 1   # oxirigacha emas
    with pytest.raises(ValidationError):
        Project.model_validate(data)
    data = p.model_dump(mode="json")
    data["slide_spans"][0]["slide"] = 9          # bunday slayd yo'q
    with pytest.raises(ValidationError, match="9-slayd"):
        Project.model_validate(data)
    with pytest.raises(ValidationError):
        SlideSpan(start=5, end=5, slide=1, source="ai")
    with pytest.raises(ValidationError):
        Project.model_validate({**p.model_dump(mode="json"), "nomalum": 1})


def test_store_roundtrip(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "p")
    store.create_dirs()
    p = make_project()
    store.save(p)
    assert store.load() == p
    assert not list(store.root.glob("*.tmp"))
    data = json.loads(store.project_file.read_text(encoding="utf-8"))
    data["schema_version"] = 99
    store.project_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="yangiroq"):
        store.load()


def random_command(p: Project, rng: random.Random) -> dict[str, object]:
    kind = rng.choice(["boundary", "slide", "layout", "key", "meta"])
    if kind == "boundary":
        spans = p.model_dump(mode="json")["slide_spans"]
        i = rng.randrange(len(spans) - 1)
        lo, hi = spans[i]["start"] + 1, spans[i + 1]["end"] - 1
        b = rng.randint(lo, hi)
        spans[i]["end"] = spans[i + 1]["start"] = b
        return {"slide_spans": spans}
    if kind == "slide":
        return {f"slide_spans.{rng.randrange(len(p.slide_spans))}.slide": rng.randint(1, 5)}
    if kind == "layout":
        return {"layout_spans.0.layout": rng.choice("AB")}
    if kind == "key":
        return {"key.tolerance": round(rng.random(), 3), "key.spill": round(rng.random(), 3)}
    return {"meta": {"fan": rng.choice(["Fizika", "Kimyo", "Tarix"])}}


def test_100_commands_undo_redo_and_reopen(tmp_path: Path) -> None:
    rng = random.Random(7)
    store = ProjectStore(tmp_path / "p")
    store.create_dirs()
    p0 = make_project()
    store.save(p0)
    st = commands.CommandStack(store)
    states = [st.project]
    for i in range(100):
        st.do(f"amal {i}", random_command(st.project, rng))
        states.append(st.project)
    final = st.project

    # dastur yopilib qayta ochildi: holat va tarix diskdan
    st = commands.CommandStack(store)
    assert st.project == final and len(st.undo_stack) == 100
    for i in range(100, 0, -1):
        assert st.project == states[i]
        st.undo()
    assert st.project == p0 and st.undo() is None
    st = commands.CommandStack(store)          # undo'lar ham saqlangan
    assert st.project == p0 and len(st.redo_stack) == 100
    for i in range(1, 101):
        st.redo()
        assert st.project == states[i]
    assert st.redo() is None

    # yangi amal redo tarixini tozalaydi
    st.undo()
    st.do("yangi", {"key.tolerance": 0.5})
    assert st.redo_stack == []


def test_invalid_command_keeps_state(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "p")
    store.create_dirs()
    store.save(make_project())
    st = commands.CommandStack(store)
    before = st.project
    with pytest.raises(ValidationError):
        st.do("buzuvchi", {"slide_spans.1.start": 500})   # bo'shliq hosil qiladi
    assert st.project == before and st.undo_stack == [] and store.load() == before


def test_concurrent_stacks_no_lost_update(tmp_path: Path) -> None:
    """Barqarorlik sinovida topilgan: parallel vazifa eski nusxani saqlab, boshqa vazifa natijasini o'chirgan."""
    import threading
    store = ProjectStore(tmp_path / "p")
    store.create_dirs()
    store.save(make_project())
    a, b = commands.CommandStack(store), commands.CommandStack(store)   # ikkalasi bir paytda yuklangan
    a.do("sinxron", {"key.tolerance": 0.3})
    b.do("eye contact", {"eye_contact": {"lid_open": 0.5, "status": "tayyor"}})   # b eski nusxada edi
    p = store.load()
    assert p.key.tolerance == 0.3 and p.eye_contact["status"] == "tayyor"

    fields = ["key.softness", "key.spill", "key.choke_px", "key.feather_px"]
    stacks = [commands.CommandStack(store) for _ in fields]

    def work(i: int) -> None:
        for k in range(10):
            stacks[i].do(f"{i}-{k}", {fields[i]: float(k)})

    ths = [threading.Thread(target=work, args=(i,)) for i in range(len(fields))]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    final = store.load().key
    assert (final.softness, final.spill, final.choke_px, final.feather_px) == (9.0,) * 4   # hech biri yo'qolmagan
    assert len(commands.CommandStack(store).undo_stack) == 42
    assert not (store.root / "project.lock").exists()
