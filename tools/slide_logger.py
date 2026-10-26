"""Slayd jurnali yozuvchi (FR-07, Windows + PowerPoint). Suratga olish paytida noutbukda ishga tushiriladi:

    python tools/slide_logger.py dars05_slides.csv

Boshlanishda 1 kHz, 300 ms "sync beep" chaladi (kamera mikrofoni yozib oladi) va PowerPoint hodisalarini
(SlideShowBegin, SlideShowNextSlide, SlideShowNextBuild, SlideShowEnd) perf_counter_ns bilan CSV ga yozadi.
To'xtatish: Ctrl+C yoki slayd shou tugashi.
"""

import csv
import sys
import time
from pathlib import Path


def play_beep() -> int:
    """Beep chalinadigan payt (perf_counter_ns, ovoz boshlanishi). winsound — standart kutubxona."""
    import io
    import math
    import struct
    import wave
    import winsound

    sr, n = 48000, int(0.3 * 48000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]
        w.writeframes(b"".join(struct.pack("<h", int(20000 * hann[i] * math.sin(2 * math.pi * 1000 * i / sr)))
                               for i in range(n)))
    t = time.perf_counter_ns()
    winsound.PlaySound(buf.getvalue(), winsound.SND_MEMORY)
    return t


class Handler:
    writer: "csv.writer"  # type: ignore[valid-type]
    out: object

    def _row(self, event: str, wn: object) -> None:
        t = time.perf_counter_ns()
        try:
            view = wn.View  # type: ignore[attr-defined]
            slide, build = int(view.CurrentShowPosition), int(view.GetClickIndex())
        except Exception:
            slide, build = 0, 0
        self.writer.writerow([t, event, slide, build])
        self.out.flush()  # type: ignore[attr-defined]
        print(f"{event} {slide}.{build}", flush=True)

    def OnSlideShowBegin(self, wn: object) -> None:  # noqa: N802 (COM hodisa nomlari)
        self._row("SlideShowBegin", wn)

    def OnSlideShowNextSlide(self, wn: object) -> None:  # noqa: N802
        self._row("SlideShowNextSlide", wn)

    def OnSlideShowNextBuild(self, wn: object) -> None:  # noqa: N802
        self._row("SlideShowNextBuild", wn)

    def OnSlideShowEnd(self, pres: object) -> None:  # noqa: N802
        t = time.perf_counter_ns()
        self.writer.writerow([t, "SlideShowEnd", 0, 0])
        self.out.flush()  # type: ignore[attr-defined]
        print("SlideShowEnd", flush=True)


def main(path: str) -> int:
    import pythoncom
    import win32com.client

    out = open(Path(path), "w", encoding="utf-8", newline="")  # noqa: SIM115 (butun ish davomida ochiq)
    print("Kamera yozuvni boshlang, keyin Enter bosing (beep chalinadi)...", flush=True)
    input()
    beep = play_beep()
    w = csv.writer(out)
    w.writerow(["sync_beep_t_ns", beep])
    w.writerow(["t_ns", "event", "slide_index", "build_index"])
    out.flush()
    app = win32com.client.DispatchWithEvents("PowerPoint.Application", Handler)
    app.writer, app.out = w, out
    print("Jurnal yozilmoqda. Slayd shouni boshlang. To'xtatish: Ctrl+C", flush=True)
    try:
        while True:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
