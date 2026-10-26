"""B9 DoD: FCP7 XML tuzilmasi (klip in/out = TimeMap), QA tekshiruvlari negativ holatlarda xato beradi, jadvallar,
fayl nomi/versiya, o'qituvchi qatlami ProRes 4444 alfa bilan."""

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from darsstudio.export import fcp7xml, qa, tables
from darsstudio.media import ffmpeg, probe
from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import CutProposal, KeySettings, LayoutSpan, Project, Slide, SlideSpan

FPS = Fraction(25)


def make_project(total: int = 500) -> Project:
    return Project(id="x", name="dars", fps="25/1", total_frames=total, template_id="demo",
                   meta={"fan": "Iqlim siyosati", "mavzu": "Moslashuv va yumshatish", "dars": "5"},
                   slides=[Slide(index=i, title=f"S{i}") for i in (1, 2, 3)],
                   slide_spans=[SlideSpan(start=0, end=200, slide=1, source="ai"),
                                SlideSpan(start=200, end=350, slide=2, source="ai"),
                                SlideSpan(start=350, end=total, slide=3, source="ai")],
                   layout_spans=[LayoutSpan(start=0, end=250, layout="A"), LayoutSpan(start=250, end=400, layout="B"),
                                 LayoutSpan(start=400, end=total, layout="A")],
                   cuts=[CutProposal(start=100, end=130, reason="pause", status="tasdiqlangan"),
                         CutProposal(start=300, end=310, reason="pause", status="tasdiqlangan"),
                         CutProposal(start=420, end=430, reason="pause", status="taklif")])


def tm_of(p: Project) -> TimeMap:
    return TimeMap.from_cuts(p.total_frames, [(c.start, c.end) for c in p.cuts if c.status == "tasdiqlangan"], FPS)


def clips(track: ET.Element) -> list[dict[str, Any]]:
    return [{k: int(c.findtext(k)) for k in ("start", "end", "in", "out")} | {"name": c.findtext("name")}
            for c in track.findall("clipitem")]


def test_fcp7_xml_structure(tmp_path: Path) -> None:
    p = make_project()
    tm = tm_of(p)
    tree = fcp7xml.build(p, tm, tmp_path, "dars_v1")
    fcp7xml.write(tree, tmp_path / "sequence.xml")
    root = ET.parse(tmp_path / "sequence.xml").getroot()
    assert root.tag == "xmeml" and root.get("version") == "5"
    seq = root.find("sequence")
    assert seq is not None and int(seq.findtext("duration")) == tm.out_total == 460
    v1, v2, v3 = seq.findall("media/video/track")
    (a1,) = seq.findall("media/audio/track")
    assert clips(v1) == [{"start": 0, "end": 460, "in": 0, "out": 460, "name": "background.png"}]
    # A1: har saqlangan oraliq — in/out asl kadrlar, start/end chiqishda, uzluksiz
    ac = clips(a1)
    assert [(c["in"], c["out"]) for c in ac] == tm.ranges
    assert [(c["start"], c["end"]) for c in ac] == [(0, 100), (100, 270), (270, 460)]
    # V3: faqat A sahnalarda, in/out = TimeMap
    vc = clips(v3)
    assert [(c["in"], c["out"]) for c in vc] == [(0, 100), (130, 250), (400, 500)]
    for c in vc:
        assert tm.src_to_out(c["in"]) == c["start"] and c["out"] - c["in"] == c["end"] - c["start"]
    # V2: slaydlar butun chiqishni bo'shliqsiz qoplaydi; B oraliqda to'liq ekran PNG
    sc = sorted(clips(v2), key=lambda c: c["start"])
    assert sc[0]["start"] == 0 and sc[-1]["end"] == 460
    assert all(a["end"] == b["start"] for a, b in zip(sc, sc[1:], strict=False))
    names = [(c["start"], c["name"]) for c in sc]
    assert (220, "002.png") in names or any(n == "002.png" for _, n in names)
    pathurls = [e.text for e in root.iter("pathurl")]
    assert all(u.startswith("file://localhost/") for u in pathurls)
    assert any("slides_full" in u for u in pathurls) and any("slides_warped" in u for u in pathurls)
    # effekt/transform yo'q (D-11)
    assert root.find(".//effect") is None and root.find(".//filter") is None


def test_ntsc_rate() -> None:
    e = ET.Element("x")
    fcp7xml.rate_el(e, Fraction(30000, 1001))
    assert e.findtext("rate/timebase") == "30" and e.findtext("rate/ntsc") == "TRUE"


def test_tables_and_naming(tmp_path: Path) -> None:
    p = make_project()
    tm = tm_of(p)
    rows = tables.slide_rows(p, tm)
    assert [r["out_frames"] for r in rows] == [[0, 170], [170, 310], [310, 460]]
    assert rows[1]["layout"] == "A/B" and rows[1]["src_start"] == 8.0
    c, j = tables.write_tables(p, tm, tmp_path / "dars_v1")
    head = c.read_text(encoding="utf-8-sig").splitlines()[0]
    assert head == "slide_no,title,src_start,src_end,out_start,out_end,layout,source,confidence" and j.is_file()
    assert tables.export_name(p, 3) == "Iqlim_siyosati_5_Moslashuv_va_yumshatish_v3"
    (tmp_path / "exports" / "v1").mkdir(parents=True)
    (tmp_path / "exports" / "v7").mkdir()
    assert tables.next_version(tmp_path / "exports") == 8


def _mp4(path: Path, *vf_af: str, dur: float = 4.0, audio_delay_ms: int = 0, volume: str = "-24dB") -> Path:
    a = f"sine=f=440:r=48000:d={dur},volume={volume}"
    if audio_delay_ms:
        a += f",adelay={audio_delay_ms}:all=1"
    ffmpeg.run(["-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=640x360:r=25:d={dur}", "-f", "lavfi", "-i", a,
                *vf_af, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest" if not audio_delay_ms else "-y", str(path)])
    return path


def status(checks: list[qa.QaCheck], cid: str) -> str:
    return next(c.status for c in checks if c.id == cid)


def test_qa_file_checks_negative(tmp_path: Path) -> None:
    good = _mp4(tmp_path / "g.mp4")
    assert all(c.status == "ok" for c in qa.check_file(good, 100, FPS))
    assert status(qa.check_file(good, 105, FPS), "kadr_soni") == "xato"         # kadr soni noto'g'ri
    assert status(qa.check_file(good, 105, FPS), "davomiylik") == "xato"
    off = tmp_path / "o.mp4"
    ffmpeg.run(["-v", "error", "-y", "-i", str(good), "-itsoffset", "0.2", "-i", str(good), "-map", "0:v", "-map",
                "1:a", "-c", "copy", str(off)])
    assert status(qa.check_file(off, 100, FPS), "av_siljish") == "xato"          # 200 ms siljish
    assert status(qa.check_file(tmp_path / "yoq.mp4", 100, FPS), "fayl") == "xato"


def test_qa_loudness_negative(tmp_path: Path) -> None:
    loud = _mp4(tmp_path / "l.mp4", volume="0dB")
    assert qa.check_loudness(loud).status == "xato"


def test_qa_black_and_frozen(tmp_path: Path) -> None:
    black = _mp4(tmp_path / "b.mp4", "-vf", "drawbox=c=black:t=fill:enable='between(t,1,2.5)'")
    ch = qa.check_black_frozen(black)
    assert status(ch, "qora_kadrlar") == "ogohlantirish"
    frozen = tmp_path / "f.mp4"
    ffmpeg.run(["-v", "error", "-y", "-f", "lavfi", "-i",
                "testsrc2=s=640x360:r=25:d=8,trim=end_frame=1,loop=loop=199:size=1", "-t", "8",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(frozen)])
    assert status(qa.check_black_frozen(frozen), "muzlagan_kadrlar") == "ogohlantirish"
    assert status(qa.check_black_frozen(frozen, [(0.0, 8.0)]), "muzlagan_kadrlar") == "ok"   # B sahna ichida
    assert all(c.status == "ok" for c in qa.check_black_frozen(_mp4(tmp_path / "ok.mp4")))


def test_qa_scene_slides_srt_negative(tmp_path: Path) -> None:
    p = make_project()
    tm = tm_of(p)
    assert qa.check_scenes(p.layout_spans, tm).status == "ok"
    gap = [LayoutSpan.model_construct(start=0, end=240, layout="A"), LayoutSpan.model_construct(start=250, end=500,
                                                                                                layout="B")]
    assert qa.check_scenes(gap, tm).status == "xato"
    over = [*p.layout_spans, LayoutSpan.model_construct(start=0, end=50, layout="B")]
    assert qa.check_scenes(over, tm).status == "xato"
    pngs = [tmp_path / f"{i:03d}.png" for i in (1, 2, 3)]
    for f in pngs[:2]:
        f.write_bytes(b"x")
    assert qa.check_slide_files(p, pngs).status == "xato"
    pngs[2].write_bytes(b"x")
    assert qa.check_slide_files(p, pngs).status == "ok"
    good = "1\n00:00:00,000 --> 00:00:02,000\nA\n\n2\n00:00:02,000 --> 00:00:04,000\nB\n\n"
    bad = "1\n00:00:03,000 --> 00:00:04,000\nA\n\n2\n00:00:02,000 --> 00:00:02,500\nB\n\n"
    assert qa.check_srt(good, 10).status == "ok" and qa.check_srt(bad, 10).status == "xato"
    assert qa.check_srt(good, 3).status == "xato"   # titr videodan uzun
    assert qa.check_suspicious(0, 0).status == "ok" and qa.check_suspicious(2, 1).status == "ogohlantirish"


@pytest.mark.parametrize("n", [25])
def test_teacher_layer_prores4444(tmp_path: Path, test_media: dict[str, Any], n: int) -> None:
    from darsstudio.project import importer
    from darsstudio.project.commands import CommandStack
    from darsstudio.render import renderer, templates
    store = importer.import_project(Path(test_media["green_key.mp4"]["path"]).with_name("av_offset.mov"),
                                    Path(test_media["lesson.pptx"]["path"]), "demo", tmp_path, make_proxy=False)
    st = CommandStack(store)
    st.do("k", {"key": KeySettings(key_cbcr=(-0.17, -0.27), tolerance=0.1).model_dump(mode="json"),
                "placement": {"scale": 0.5, "x": 1000, "y": 400, "color": {}}})
    p = st.project.model_copy(update={"total_frames": n})
    out = renderer.render_teacher_layer(p, probe.probe(test_media["av_offset.mov"]["path"]), templates.load("demo"),
                                        tmp_path / "teacher.mov")
    q = probe.probe(out)
    assert q.video.codec == "prores" and q.video.pix_fmt.startswith("yuva444") and q.video.nb_frames == n
    assert (q.video.width, q.video.height) == (1920, 1080)
