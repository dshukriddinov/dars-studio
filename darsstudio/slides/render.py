"""Slaydlarni 4K PNG ga render qilish (FR-03, TZ 4.2).

PPTX: PowerPoint COM (Slide.Export) -> bo'lmasa LibreOffice headless -> PDF -> pypdfium2. PDF: pypdfium2.
PNG lar slaydning o'z nisbatida, balandligi 2160 (16:9 da 3840x2160); 16:9 ga pillarbox — warp/kompozitda.
PyMuPDF ishlatilmaydi (AGPL, TZ 10.2). PowerPoint bir vaqtda bitta jarayonda (rejalashtiruvchida `pptx` = 1).
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from darsstudio.media.probe import MediaError, file_id

HEIGHT = 2160


def powerpoint_available() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"PowerPoint.Application"))
        return True
    except OSError:
        return False


def soffice_path() -> str | None:
    for p in (shutil.which("soffice"), r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if p and Path(p).is_file():
            return p
    return None


def render_pptx_com(src: Path, out_dir: Path) -> list[Path]:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx("PowerPoint.Application")
    pres = None
    try:
        # WithWindow=False: foydalanuvchi oynasi ochilmaydi; ReadOnly: manba o'zgarmaydi
        pres = app.Presentations.Open(str(src.resolve()), True, False, False)
        w = round(HEIGHT * pres.PageSetup.SlideWidth / pres.PageSetup.SlideHeight)
        out = []
        for i in range(1, pres.Slides.Count + 1):
            p = out_dir / f"{i:03d}.png"
            pres.Slides(i).Export(str(p.resolve()), "PNG", w, HEIGHT)
            out.append(p)
        return out
    finally:
        if pres is not None:
            pres.Close()
        if app.Presentations.Count == 0:  # foydalanuvchi PowerPoint'da boshqa fayl ochgan bo'lsa yopmaymiz
            app.Quit()
        pythoncom.CoUninitialize()


def render_pdf(src: Path, out_dir: Path) -> list[Path]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(src))
    out = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            _, h = page.get_size()
            img = page.render(scale=HEIGHT / h).to_pil().convert("RGB")
            p = out_dir / f"{i + 1:03d}.png"
            img.save(p)
            out.append(p)
    finally:
        doc.close()
    return out


def pptx_to_pdf_libreoffice(src: Path, tmp: Path) -> Path:
    exe = soffice_path()
    if exe is None:
        raise MediaError("PPTX ni ochish uchun PowerPoint yoki LibreOffice kerak. Ulardan birini o'rnating "
                         "yoki slaydlarni PDF qilib bering.")
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(src)], check=True,
                   capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return tmp / (src.stem + ".pdf")


def render_slides(src: Path, out_dir: Path) -> tuple[list[Path], str]:
    """(PNG ro'yxati, ishlatilgan usul). Manba hash'i mos bo'lsa keshdan qaytaradi."""
    src = Path(src)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = out_dir / "stamp.json"
    sid = file_id(src)
    if stamp.is_file():
        st = json.loads(stamp.read_text(encoding="utf-8"))
        files = [out_dir / f for f in st.get("files", [])]
        if st.get("source_id") == sid and files and all(f.is_file() for f in files):
            return files, st["method"]
    for old in out_dir.glob("*.png"):
        old.unlink()
    ext = src.suffix.lower()
    if ext == ".pdf":
        files, method = render_pdf(src, out_dir), "pdf"
    elif ext == ".pptx" and powerpoint_available():
        files, method = render_pptx_com(src, out_dir), "powerpoint"
    elif ext == ".pptx":
        with tempfile.TemporaryDirectory() as t:
            files, method = render_pdf(pptx_to_pdf_libreoffice(src, Path(t)), out_dir), "libreoffice"
    else:
        raise MediaError(f"{src.name}: slaydlar PPTX yoki PDF bo'lishi kerak.")
    stamp.write_text(json.dumps({"source_id": sid, "method": method, "files": [f.name for f in files]}),
                     encoding="utf-8")
    return files, method
