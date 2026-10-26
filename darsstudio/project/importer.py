"""Loyiha yaratish va import (FR-01). Manba fayllar ko'chirilmaydi (havola + hash), so'ralsa nusxalanadi."""

import logging
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

from darsstudio.media import normalize, probe, proxy
from darsstudio.media.probe import MediaError
from darsstudio.project.model import MediaAsset, Project, Slide
from darsstudio.project.store import ProjectStore

log = logging.getLogger(__name__)

VIDEO_EXT = (".mov", ".mp4", ".mkv")
SLIDE_EXT = (".pptx", ".pdf")


def read_slide_titles(path: Path) -> list[Slide]:
    """Slaydlar soni va sarlavhalar. To'liq ekstraksiya (matn, eslatmalar, render) — slides/ modulida."""
    if path.suffix.lower() == ".pptx":
        from pptx import Presentation
        try:
            prs = Presentation(str(path))
        except Exception as e:
            raise MediaError(f"{path.name} ni ochib bo'lmadi: PPTX buzilgan yoki parol bilan himoyalangan.") from e
        out = []
        for i, s in enumerate(prs.slides, 1):
            t = s.shapes.title
            out.append(Slide(index=i, title=(t.text if t is not None and t.has_text_frame else "").strip()))
        return out
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium  # type: ignore[import-untyped]
        doc = pdfium.PdfDocument(str(path))
        return [Slide(index=i + 1) for i in range(len(doc))]
    raise MediaError(f"{path.name}: slaydlar PPTX yoki PDF bo'lishi kerak.")


def import_project(video: Path, slides: Path, template_id: str, workdir: Path, *, name: str | None = None,
                   meta: dict[str, str] | None = None, slide_log: Path | None = None, copy: bool = False,
                   make_proxy: bool = True, on_step: Callable[[str], None] = lambda s: None) -> ProjectStore:
    video, slides = Path(video).resolve(), Path(slides).resolve()
    name = name or video.stem
    store = ProjectStore(Path(workdir) / name)
    if store.exists():
        raise MediaError(f"'{name}' loyihasi allaqachon bor: {store.root}. Boshqa nom bering yoki eskisini o'chiring.")

    on_step("probe")
    p = probe.probe(video)
    probe.validate(p)
    slide_list = read_slide_titles(slides)
    if not slide_list:
        raise MediaError(f"{slides.name} da slayd yo'q.")

    store.create_dirs()
    try:
        if copy:
            src_dir = store.root / "source"
            src_dir.mkdir(exist_ok=True)
            for f in (video, slides, *([slide_log] if slide_log else [])):
                shutil.copy2(f, src_dir / f.name)
            video, slides = src_dir / video.name, src_dir / slides.name
            slide_log = src_dir / slide_log.name if slide_log else None

        work = p
        cfr_path = None
        if normalize.needs_normalize(p):
            on_step("normalize")
            work = normalize.normalize(p, store.cache("media") / "cfr.mkv")
            cfr_path = work.path
            log.info("normallashtirildi: %s -> %s (vfr=%s)", video, cfr_path, p.video.vfr)

        assets = [
            MediaAsset(id=probe.file_id(video), path=str(video), kind="video", probe=p.to_dict(), cfr_path=cfr_path),
            MediaAsset(id=probe.file_id(slides), path=str(slides), kind=slides.suffix.lower().lstrip(".")),
        ]
        if slide_log:
            assets.append(MediaAsset(id=probe.file_id(slide_log), path=str(Path(slide_log).resolve()),
                                     kind="slide_log"))

        project = Project(id=uuid.uuid4().hex[:12], name=name, meta=meta or {}, assets=assets,
                          fps=str(work.video.fps), total_frames=probe.frame_count(work), template_id=template_id,
                          slides=slide_list)
        store.save(project)
        if make_proxy:
            on_step("proxy")
            proxy.make_proxy(work, store.cache("media") / "proxy_540p.mp4")
    except BaseException:
        shutil.rmtree(store.root, ignore_errors=True)  # yarim loyiha qolmasin: qayta import mumkin bo'lsin
        raise
    return store


def find_pairs(folder: Path) -> list[tuple[Path, Path]]:
    """Papkadagi juftliklar: dars05.mov + dars05.pptx (bir xil nom, katta-kichik harf farqsiz)."""
    files = [f for f in Path(folder).iterdir() if f.is_file()]
    slides = {f.stem.lower(): f for f in files if f.suffix.lower() in SLIDE_EXT}
    return sorted((v, slides[v.stem.lower()]) for v in files
                  if v.suffix.lower() in VIDEO_EXT and v.stem.lower() in slides)
