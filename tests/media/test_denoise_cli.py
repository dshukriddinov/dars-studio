"""deep-filter CLI integratsiyasi: chiqish kechikishi o'lchanadi va olib tashlanadi, uzunlik manbaga teng (A/V).
CLI o'rniga soxta jarayon: manbani 480 namuna kechiktirib, 0.2 s uzunroq yozadi."""

import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from darsstudio.audio import denoise
from darsstudio.audio.extract import read_pcm
from darsstudio.media import ffmpeg

pytestmark = pytest.mark.media


def test_lag_samples() -> None:
    rng = np.random.default_rng(0)
    a = rng.standard_normal(48000 * 3).astype(np.float32)
    assert denoise.lag_samples(a, np.concatenate([np.zeros(777, np.float32), a])) == 777
    assert denoise.lag_samples(a, a[300:]) == -300
    assert denoise.lag_samples(a, a) == 0


def test_cli_output_aligned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "src_48k.wav"
    ffmpeg.run(["-v", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=d=4:c=pink:r=48000:a=0.3", "-c:a", "pcm_s16le",
                str(src)])

    real_run = subprocess.run

    def fake_run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        if not cmd[0].endswith("deep-filter.exe"):
            return real_run(cmd, **kw)
        out_dir = Path(cmd[cmd.index("-o") + 1])
        ffmpeg.run(["-v", "error", "-y", "-i", cmd[-1], "-af", "adelay=480S:all=1,apad=pad_dur=0.2",
                    "-c:a", "pcm_f32le", str(out_dir / Path(cmd[-1]).name)])
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(denoise.subprocess, "run", fake_run)
    monkeypatch.setattr(denoise, "deepfilter_cli", lambda: tmp_path / "deep-filter.exe")
    dst = tmp_path / "den.wav"
    assert denoise.denoise(src, dst) == "deepfilternet3-cli"
    a, b = read_pcm(src, 48000), read_pcm(dst, 48000)
    assert len(a) == len(b)
    assert denoise.lag_samples(a, b) == 0
