"""Studiya shabloni (TZ 8.3, FR-12): templates/<id>/template.json + assetlar."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from darsstudio import paths
from darsstudio.media.probe import MediaError

Point = tuple[float, float]


class Logo(BaseModel):
    file: str
    pos: tuple[int, int] = (40, 32)
    height: int = 64


class LowerThird(BaseModel):
    style: str = "default"
    duration_s: float = 6.0


TransitionKind = Literal["crossfade", "cut", "clock_wipe", "zoom_blur"]


class Transitions(BaseModel):
    slide_frames: int = Field(default=8, ge=0)
    layout_frames: int = Field(default=12, ge=0)
    slide: TransitionKind = "crossfade"     # A sahna ichida slayd -> slayd
    layout: TransitionKind = "crossfade"    # A <-> B (B -> A da yangi slayd bilan birga)


class ScenePolicy(BaseModel):
    """Sahna tavsiyasi. words: TZ FR-12 (>= N so'z -> B). a_then_b: slayd almashganda a_seconds A (o'qituvchi
    yangi slayd bilan), keyin B; slayd qolgan qismi min_b_seconds dan qisqa bo'lsa A qoladi (montajchi uslubi)."""
    mode: Literal["words", "a_then_b"] = "words"
    a_seconds: float = 10.0
    min_b_seconds: float = 10.0


class FixedPlacement(BaseModel):
    """Studiyada kamera qotirilgan bo'lsa: o'qituvchi joyi shablondan (namunadan o'lchangan)."""
    scale: float
    x: int
    y: int


class TeacherFit(BaseModel):
    """O'qituvchi gavdasini kanvasga sig'dirish (kanvas px): bosh tepasi head_y da, yonga tushgan kaftlar hands_y da,
    gavda markazi center_x da. Oyoqlar kadrdan pastda qoladi (montajchi namunasi, 2026-10-27)."""
    head_y: int
    hands_y: int
    center_x: int


class Copyright(BaseModel):
    """tail: dars oxirgi `seconds` soniyasida; o'ngdan chapga `slide_px` sirg'alib kiradi (`slide_s`, chiziqli), polosa
    o'ng chetidan tashqari ko'rinmaydi, keyin joyida turadi (montajchi namunasi: ~130 px/s, 640 px, 2026-10-27)."""
    text: str
    on: Literal["tail", "last_slide", "always"] = "tail"
    seconds: float = 5.0
    slide_s: float = 3.0
    slide_px: int = 640


class Fullscreen(BaseModel):
    fit: str = "contain"
    pillarbox_color: str = "#000000"


class Template(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    canvas: tuple[int, int] = (1920, 1080)
    background: str
    screen_quad: tuple[Point, Point, Point, Point]   # TL, TR, BR, BL kanvas koordinatasida
    screen_aspect: str = "16:9"
    teacher_anchor: tuple[int, int, int, int]        # x0, y0, x1, y1
    safe_margin_px: int = 24
    logo: Logo | None = None
    lower_third: LowerThird = LowerThird()
    transitions: Transitions = Transitions()
    fullscreen: Fullscreen = Fullscreen()
    key_defaults: dict[str, Any] = {}
    scene_policy: ScenePolicy = ScenePolicy()
    teacher_placement: FixedPlacement | None = None
    teacher_fit: TeacherFit | None = None
    intro: str | None = None                         # intro video (shablon papkasida)
    outro: str | None = None
    copyright: Copyright | None = None
    dir: str = ""                                    # yuklanganda to'ldiriladi (JSON'da yo'q)

    @field_validator("teacher_anchor")
    @classmethod
    def _anchor(cls, v: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        if not (v[0] < v[2] and v[1] < v[3]):
            raise ValueError("teacher_anchor: x0 < x1 va y0 < y1 bo'lishi kerak")
        return v

    def asset(self, name: str) -> Path:
        return Path(self.dir) / name

    def content_hash(self) -> str:
        """Warp keshi kaliti: shablon JSON + fon/logo fayllari."""
        h = hashlib.sha256(self.model_dump_json(exclude={"dir"}).encode())
        extra = [x for x in (self.intro, self.outro) if x]
        assets = (self.background, *([self.logo.file] if self.logo else []), *extra)
        for f in assets:
            h.update(self.asset(f).read_bytes())
        return h.hexdigest()[:16]


def templates_dir() -> Path:
    return paths.ROOT / "templates"


def load(template_id: str, root: Path | None = None) -> Template:
    d = (root or templates_dir()) / template_id
    f = d / "template.json"
    if not f.is_file():
        raise MediaError(f"'{template_id}' shabloni topilmadi ({f}). templates/ papkasini tekshiring.")
    t = Template.model_validate({**json.loads(f.read_text(encoding="utf-8")), "dir": str(d)})
    for name in (t.background, *([t.logo.file] if t.logo else []), *(x for x in (t.intro, t.outro) if x)):
        if not t.asset(name).is_file():
            raise MediaError(f"'{template_id}' shablonida {name} fayli yo'q.")
    return t


def save(t: Template) -> None:
    from darsstudio.project.store import atomic_write_json
    atomic_write_json(Path(t.dir) / "template.json", t.model_dump(mode="json", exclude={"dir"}))
