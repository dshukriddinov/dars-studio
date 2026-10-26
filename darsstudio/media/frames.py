"""Kadrlarni rawvideo pipe orqali o'qish/yozish. Format: manba 4:2:0 baytlari o'zgarishsiz (konvertatsiyasiz).

Kadr = flat uint8 massiv w*h*3/2 (Y, keyin U, keyin V). `planes()` ko'rinishlarni beradi.
Rang: o'qishda pix_fmt manbanikidek (yuv420p yoki yuvj420p) so'raladi, shuning uchun ffmpeg diapazon
konvertatsiyasi qo'shmaydi. Yozishda kirish va chiqish teglari aniq beriladi (CLAUDE.md, 3-qoida).
"""

import threading
from collections.abc import Iterator, Sequence
from fractions import Fraction
from pathlib import Path
from types import TracebackType

import numpy as np
import numpy.typing as npt

from darsstudio.media import ffmpeg
from darsstudio.media.normalize import color_flags
from darsstudio.media.probe import ProbeResult

Frame = npt.NDArray[np.uint8]


def frame_bytes(w: int, h: int) -> int:
    return w * h * 3 // 2


def planes(frame: Frame, w: int, h: int) -> tuple[Frame, Frame, Frame]:
    n, q = w * h, (w // 2) * (h // 2)
    return (frame[:n].reshape(h, w), frame[n:n + q].reshape(h // 2, w // 2),
            frame[n + q:n + 2 * q].reshape(h // 2, w // 2))


def _drain(stream: object, sink: list[bytes]) -> None:
    # stderr to'lib qolib pipe bloklanmasin
    for line in stream:  # type: ignore[attr-defined]
        sink.append(line)


class FrameReader:
    """[start, start+count) kadrlar, asl kadr indekslarida. CFR manba kutiladi (VFR -> avval normalize)."""

    def __init__(self, p: ProbeResult, start: int = 0, count: int | None = None) -> None:
        if p.video.vfr:
            raise ValueError("VFR manba: avval media.normalize bilan CFR nusxa yarating")
        v = p.video
        self.w, self.h, self.nbytes = v.width, v.height, frame_bytes(v.width, v.height)
        args = ["-v", "error", "-nostdin"]
        if start:
            # -ss fayl boshiga (format start_time) nisbatan: video start_time + (start - 0.5) kadr -> aynan
            # `start` kadrdan (Eye Contact'da sinalgan)
            t = v.start_time - p.format_start_time + (start - Fraction(1, 2)) / v.fps
            args += ["-ss", f"{float(t):.6f}"]
        args += ["-i", p.path, "-map", "0:v:0"]
        if count is not None:
            args += ["-frames:v", str(count)]
        args += ["-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", v.pix_fmt, "-"]
        self.proc = ffmpeg.popen(args, stdout=True, bufsize=self.nbytes * 4)
        self._err: list[bytes] = []
        threading.Thread(target=_drain, args=(self.proc.stderr, self._err), daemon=True).start()

    def read(self) -> Frame | None:
        assert self.proc.stdout is not None
        buf = self.proc.stdout.read(self.nbytes)
        if len(buf) < self.nbytes:
            self.close()
            return None
        return np.frombuffer(buf, np.uint8).copy()

    def __iter__(self) -> Iterator[Frame]:
        while (f := self.read()) is not None:
            yield f

    def close(self) -> None:
        if self.proc.stdout:
            self.proc.stdout.close()
        self.proc.wait()

    def __enter__(self) -> "FrameReader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class FrameWriter:
    """yuv420p kadrlarni kodlaydi. encoder_args: masalan ["-c:v", "ffv1"] yoki NVENC sozlamalari.
    Rang teglari `color_of` dan (manba probe) olinadi va kirishga ham, chiqishga ham yoziladi."""

    def __init__(self, path: Path, w: int, h: int, fps: Fraction, color_of: ProbeResult | None,
                 encoder_args: Sequence[str], pix_fmt: str = "yuv420p", extra_out: Sequence[str] = (),
                 tags: Sequence[str] | None = None) -> None:
        tags = list(tags) if tags is not None else (color_flags(color_of) if color_of else [])
        self.nbytes = frame_bytes(w, h)
        args = ["-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", f"{w}x{h}",
                "-r", str(fps), *tags, "-i", "-", *encoder_args, *tags, *extra_out, str(path)]
        self.proc = ffmpeg.popen(args, stdin=True, bufsize=self.nbytes * 4)
        self._err: list[bytes] = []
        threading.Thread(target=_drain, args=(self.proc.stderr, self._err), daemon=True).start()

    def write(self, frame: Frame) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(np.ascontiguousarray(frame).data)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        if self.proc.wait() != 0:
            err = b"".join(self._err).decode("utf-8", "replace").strip()[-800:]
            raise ffmpeg.FfmpegError(f"kodlash xato bilan tugadi (kod {self.proc.returncode}): {err}")

    def __enter__(self) -> "FrameWriter":
        return self

    def __exit__(self, et: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None) -> None:
        if et is None:
            self.close()
        else:  # xato: jarayonni yopamiz, asl xato yo'qolmasin
            try:
                self.close()
            except ffmpeg.FfmpegError:
                pass
