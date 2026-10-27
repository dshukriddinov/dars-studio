"""Dars Studio oynasi (D-09): API'ni fon oqimida (127.0.0.1, bo'sh port) ishga tushiradi va pywebview oynasini ochadi.
pywebview o'rnatilmagan bo'lsa — standart brauzer.

    python -m darsstudio.app_window
"""

import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

log = logging.getLogger(__name__)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_ready(url: str, timeout: float = 30.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.2)
    return False


def main() -> None:
    import uvicorn

    from darsstudio.api.app import create_app

    if sys.stderr is None:  # pythonw.exe: konsol yo'q, uvicorn logi stderr'ga yozadi
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    # FR-22: ishga tushgandan keyin tarmoq talab qilinmaydi
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    # bitta nusxa: ikkinchi ishga tushirish yangi server (va vazifa rejalashtiruvchi) ochmaydi — ikkitasi bitta
    # navbatdan bir ishni ikki marta bajarardi (2026-10-28: proxy fayli band, PermissionError)
    running = running_instance()
    if running:
        open_window(running)
        return
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    if not wait_ready(url):
        raise SystemExit("Server ishga tushmadi: jurnalni tekshiring.")
    lock = instance_file()
    lock.write_text(url, encoding="utf-8")
    try:
        if not open_window(url):
            try:
                th.join()  # brauzer rejimi: server jarayon tugaguncha ishlaydi
            except KeyboardInterrupt:
                pass
    finally:
        lock.unlink(missing_ok=True)
        server.should_exit = True
        th.join(30)


def instance_file() -> Path:
    from darsstudio import paths
    paths.workdir().mkdir(parents=True, exist_ok=True)
    return paths.workdir() / "app_instance.txt"


def running_instance() -> str | None:
    """Ishlab turgan nusxa URL'i (fayl bor va server javob beradi), aks holda None."""
    f = instance_file()
    if not f.is_file():
        return None
    url = f.read_text(encoding="utf-8").strip()
    return url if url and wait_ready(url, timeout=2) else None


def open_window(url: str) -> bool:
    """pywebview oynasi (yopilguncha kutadi) -> True; pywebview yo'q bo'lsa brauzer -> False."""
    try:
        import webview  # pywebview (BSD)
    except ImportError:
        log.info("pywebview topilmadi, brauzer ochiladi: %s", url)
        webbrowser.open(url)
        return False
    webview.create_window("Dars Studio", url, width=1600, height=960, min_size=(1100, 700))
    webview.start()
    return True


if __name__ == "__main__":
    main()
