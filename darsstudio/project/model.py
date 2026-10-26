"""Loyiha holati (TZ 8.2, D-10). Vaqt oraliqlari asl kadr indekslarida, [start, end). fps — Fraction satr."""

from fractions import Fraction
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = 1


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=False)


class Span(_M):
    start: int = Field(ge=0)
    end: int

    @model_validator(mode="after")
    def _order(self) -> "Span":
        if self.end <= self.start:
            raise ValueError(f"oraliq bo'sh yoki teskari: [{self.start}, {self.end})")
        return self


class MediaAsset(_M):
    id: str                          # probe.file_id (FR-01)
    path: str
    kind: Literal["video", "pptx", "pdf", "image", "audio", "slide_log"]
    probe: dict[str, Any] = {}       # ProbeResult.to_dict()
    cfr_path: str | None = None      # VFR yoki audio != 48 kHz bo'lsa normallashtirilgan nusxa


class Slide(_M):
    index: int = Field(ge=1)
    title: str = ""
    body: str = ""
    notes: str = ""
    ocr: str | None = None
    png_4k: str = ""
    warped_png: str | None = None
    warnings: list[str] = []


class Word(_M):
    text: str
    start_ms: int
    end_ms: int
    conf: float


class SlideSpan(Span):
    slide: int = Field(ge=1)
    source: Literal["log", "ai", "manual"]
    confidence: float = 1.0
    approved: bool = False


class LayoutSpan(Span):
    layout: Literal["A", "B", "C"]
    suggested: bool = False


class CutProposal(Span):
    reason: Literal["pause", "manual", "bosh", "oxir"]
    status: Literal["taklif", "tasdiqlangan", "rad_etilgan"] = "taklif"


class EyeOffSpan(Span):
    pass


class KeySettings(_M):
    key_cbcr: tuple[float, float] = (0.0, 0.0)
    tolerance: float = 0.08
    softness: float = 0.08
    spill: float = 0.5
    choke_px: float = 0.0
    feather_px: float = 1.0
    garbage_polys: list[list[tuple[int, int]]] = []
    keep_polys: list[list[tuple[int, int]]] = []
    edge_refine: bool = False
    light_wrap: float = 0.0


class TeacherPlacement(_M):
    scale: float = 1.0
    x: int = 0
    y: int = 0
    color: dict[str, float] = {}     # exposure, temp, tint, saturation


def _check_cover(spans: list[Any], total: int, name: str) -> None:
    """Bo'sh bo'lmasa [0, total) ni bo'shliqsiz va ustma-ust tushmasdan qoplashi kerak (TZ 8.2)."""
    if not spans:
        return
    pos = 0
    for s in sorted(spans, key=lambda x: x.start):
        if s.start != pos:
            kind = "bo'shliq" if s.start > pos else "ustma-ust"
            raise ValueError(f"{name}: {pos} kadrda {kind}")
        pos = s.end
    if pos != total:
        raise ValueError(f"{name}: oxiri {pos}, kutilgan {total}")


class Project(_M):
    schema_version: int = SCHEMA_VERSION
    id: str
    name: str
    meta: dict[str, str] = {}        # fan, mavzu, o'qituvchi, dars raqami, til
    assets: list[MediaAsset] = []
    fps: str                         # Fraction, masalan "30000/1001"
    total_frames: int = Field(ge=0)
    template_id: str
    slides: list[Slide] = []
    words: str = "cache/asr/words.parquet"
    slide_spans: list[SlideSpan] = []
    layout_spans: list[LayoutSpan] = []
    cuts: list[CutProposal] = []
    eye_off: list[EyeOffSpan] = []
    key: KeySettings = KeySettings()
    placement: TeacherPlacement = TeacherPlacement()
    eye_contact: dict[str, Any] = {"lid_open": 0.5}
    exports: list[dict[str, Any]] = []

    @field_validator("fps")
    @classmethod
    def _fps(cls, v: str) -> str:
        f = Fraction(v)
        if f <= 0:
            raise ValueError("fps musbat bo'lishi kerak")
        return f"{f.numerator}/{f.denominator}"

    @property
    def fps_frac(self) -> Fraction:
        return Fraction(self.fps)

    @model_validator(mode="after")
    def _invariants(self) -> "Project":
        _check_cover(self.slide_spans, self.total_frames, "slide_spans")
        _check_cover(self.layout_spans, self.total_frames, "layout_spans")
        for group, name in ((self.cuts, "cuts"), (self.eye_off, "eye_off")):
            for s in group:
                if s.end > self.total_frames:
                    raise ValueError(f"{name}: [{s.start}, {s.end}) {self.total_frames} kadrdan oshadi")
        n = len(self.slides)
        for sp in self.slide_spans:
            if n and sp.slide > n:
                raise ValueError(f"slide_spans: {sp.slide}-slayd yo'q (jami {n})")
        return self

    def asset(self, kind: str) -> MediaAsset | None:
        return next((a for a in self.assets if a.kind == kind), None)
