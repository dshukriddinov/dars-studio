"""FCP7 XML (xmeml v5) — Premiere Pro va DaVinci Resolve uchun (FR-18, D-11).

V1 fon (still), V2 slaydlar (A: kanvasdagi joyiga warp qilingan PNG, B: to'liq ekran PNG), V3 o'qituvchi
(teacher.mov, ProRes 4444 alfa, kesilmagan asl vaqt chizig'ida, kanvasdagi joyida), A1 audio (tozalangan, kesilmagan).
Kesishlar V3/A1 klip in/out nuqtalari bilan: montajchi Premiere'da kesishni o'zgartira oladi. Effekt/transform yo'q.
"""

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote

from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import Project

LONG = 24 * 3600 * 30  # still rasmlar uchun "cheksiz" davomiylik (kadr)


def rate_el(parent: ET.Element, fps: Fraction) -> None:
    r = ET.SubElement(parent, "rate")
    ntsc = fps.denominator == 1001
    ET.SubElement(r, "timebase").text = str(round(fps)) if not ntsc else str(round(fps * Fraction(1001, 1000)))
    ET.SubElement(r, "ntsc").text = "TRUE" if ntsc else "FALSE"


def pathurl(p: Path) -> str:
    return "file://localhost/" + quote(str(Path(p).resolve()).replace("\\", "/"), safe="/:")


class Xml:
    def __init__(self, fps: Fraction, size: tuple[int, int]) -> None:
        self.fps, self.size = fps, size
        self.defined: set[str] = set()
        self.n = 0

    def file_el(self, parent: ET.Element, fid: str, path: Path, duration: int, kind: str) -> None:
        f = ET.SubElement(parent, "file", id=fid)
        if fid in self.defined:
            return
        self.defined.add(fid)
        ET.SubElement(f, "name").text = path.name
        ET.SubElement(f, "pathurl").text = pathurl(path)
        rate_el(f, self.fps)
        ET.SubElement(f, "duration").text = str(duration)
        media = ET.SubElement(f, "media")
        if kind in ("video", "still"):
            v = ET.SubElement(media, "video")
            sc = ET.SubElement(v, "samplecharacteristics")
            rate_el(sc, self.fps)
            ET.SubElement(sc, "width").text = str(self.size[0])
            ET.SubElement(sc, "height").text = str(self.size[1])
            ET.SubElement(sc, "pixelaspectratio").text = "square"
        if kind == "audio":
            a = ET.SubElement(media, "audio")
            sc = ET.SubElement(a, "samplecharacteristics")
            ET.SubElement(sc, "depth").text = "16"
            ET.SubElement(sc, "samplerate").text = "48000"
            ET.SubElement(a, "channelcount").text = "2"

    def clip(self, track: ET.Element, fid: str, path: Path, start: int, end: int, src_in: int, file_dur: int,
             kind: str) -> ET.Element:
        self.n += 1
        c = ET.SubElement(track, "clipitem", id=f"clip-{self.n}")
        ET.SubElement(c, "name").text = path.name
        ET.SubElement(c, "enabled").text = "TRUE"
        ET.SubElement(c, "duration").text = str(file_dur)
        rate_el(c, self.fps)
        ET.SubElement(c, "start").text = str(start)
        ET.SubElement(c, "end").text = str(end)
        ET.SubElement(c, "in").text = str(src_in)
        ET.SubElement(c, "out").text = str(src_in + end - start)
        if kind == "still":
            ET.SubElement(c, "stillframe").text = "TRUE"
        self.file_el(c, fid, path, file_dur, kind)
        if kind == "audio":
            st = ET.SubElement(c, "sourcetrack")
            ET.SubElement(st, "mediatype").text = "audio"
            ET.SubElement(st, "trackindex").text = "1"
        return c


def build(p: Project, tm: TimeMap, pkg: Path, name: str) -> ET.ElementTree:
    """pkg: background.png, slides_warped/NNN.png, slides_full/NNN.png, teacher.mov, audio.wav."""
    fps = p.fps_frac
    x = Xml(fps, (1920, 1080))
    root = ET.Element("xmeml", version="5")
    seq = ET.SubElement(root, "sequence", id="sequence-1")
    ET.SubElement(seq, "name").text = name
    ET.SubElement(seq, "duration").text = str(tm.out_total)
    rate_el(seq, fps)
    media = ET.SubElement(seq, "media")
    video = ET.SubElement(media, "video")
    fmt = ET.SubElement(ET.SubElement(video, "format"), "samplecharacteristics")
    rate_el(fmt, fps)
    ET.SubElement(fmt, "width").text, ET.SubElement(fmt, "height").text = "1920", "1080"
    ET.SubElement(fmt, "pixelaspectratio").text = "square"

    v1, v2, v3 = (ET.SubElement(video, "track") for _ in range(3))
    x.clip(v1, "bg", pkg / "background.png", 0, tm.out_total, 0, LONG, "still")
    for sp in p.slide_spans:
        for ls in p.layout_spans:
            a, b = max(sp.start, ls.start), min(sp.end, ls.end)
            if a >= b:
                continue
            sub = "slides_full" if ls.layout == "B" else "slides_warped"
            f = pkg / sub / f"{sp.slide:03d}.png"
            for s, e in tm.map_span(a, b):
                x.clip(v2, f"{sub}-{sp.slide}", f, s, e, 0, LONG, "still")
    total = p.total_frames
    for ls in p.layout_spans:
        if ls.layout == "B":
            continue  # B sahnada o'qituvchi yashirin (audio davom etadi)
        for ks, ke in tm.ranges:
            a, b = max(ks, ls.start), min(ke, ls.end)
            if a < b:
                o = tm.src_to_out(a)
                assert o is not None
                x.clip(v3, "teacher", pkg / "teacher.mov", o, o + (b - a), a, total, "video")
    audio = ET.SubElement(media, "audio")
    a1 = ET.SubElement(audio, "track")
    for ks, ke in tm.ranges:
        o = tm.src_to_out(ks)
        assert o is not None
        x.clip(a1, "audio", pkg / "audio.wav", o, o + (ke - ks), ks, total, "audio")
    ET.indent(root)
    return ET.ElementTree(root)


def write(tree: ET.ElementTree, path: Path) -> None:
    with open(path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)
