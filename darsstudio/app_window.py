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
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    if not wait_ready(url):
        raise SystemExit("Server ishga tushmadi: jurnalni tekshiring.")

    try:
        import webview  # pywebview (BSD)
    except ImportError:
        log.info("pywebview topilmadi, brauzer ochiladi: %s", url)
        webbrowser.open(url)
        try:
            th.join()  # brauzer rejimi: server jarayon tugaguncha ishlaydi
        except KeyboardInterrupt:
            pass
    else:
        webview.create_window("Dars Studio", url, width=1600, height=960, min_size=(1100, 700))
        webview.start()
    server.should_exit = True
    th.join(30)


if __name__ == "__main__":
    main()
