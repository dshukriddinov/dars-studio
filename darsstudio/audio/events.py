"""Nutqdagi kamchiliklar: yo'tal, aksa, tomoq qirish va h.k. (AudioSet sinflari) — PANNs Cnn14 16 kHz
(Kong va b., 2020; kod MIT, og'irliklar CC-BY-4.0, `models/panns/`). Arxitektura shu yerda (PANNs repo'si bilan
bir xil kalitlar), tashqi paket yo'q. Checkpoint numpy obyektlari bilan saqlangan — faqat ular ruxsat etilgan
`weights_only=True` rejimida yuklanadi (ixtiyoriy kod bajarilmaydi).

Aniqlash: WINDOW_S oynalar HOP_S qadam bilan, har sinf ehtimoli; kadrga (HOP_S) taqsimlanadi (oynalar maksimumi).
GPU ishi — worker jarayonida (`jobs/tasks.py`), CLI'da ham ishlaydi.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import torch
import torch.nn.functional as F
from torch import nn

from darsstudio import paths

SR = 16000
WINDOW_S, HOP_S = 1.0, 0.1
CKPT = "panns/Cnn14_16k_mAP=0.438.pth"
LABELS = "panns/class_labels_indices.csv"
# kamchilik sinflari (AudioSet nomi -> bizning sabab)
# "Sniff"/"Gasp" — sinov videosida asosan gaplar orasidagi oddiy nafas (kesilmaydi)
EVENT_CLASSES = {"Cough": "yo'tal", "Throat clearing": "yo'tal", "Sneeze": "aksa", "Hiccup": "aksa",
                 "Burping, eructation": "aksa", "Humming": "to'ldiruvchi"}


class ConvBlock(nn.Module):
    def __init__(self, cin: int, cout: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(cin, cout, 3, padding=1, bias=False)
        self.conv2 = nn.Conv2d(cout, cout, 3, padding=1, bias=False)
        self.bn1, self.bn2 = nn.BatchNorm2d(cout), nn.BatchNorm2d(cout)

    def forward(self, x: torch.Tensor, pool: tuple[int, int]) -> torch.Tensor:
        x = F.relu(self.bn2(self.conv2(F.relu(self.bn1(self.conv1(x))))))
        return F.avg_pool2d(x, pool)


class Cnn14(nn.Module):
    """PANNs Cnn14 (16 kHz: n_fft 512, hop 160, 64 mel, 50–8000 Hz). STFT va mel matritsasi checkpoint'dan."""

    def __init__(self, classes: int = 527) -> None:
        super().__init__()
        self.stft_real = nn.Parameter(torch.zeros(257, 1, 512), requires_grad=False)
        self.stft_imag = nn.Parameter(torch.zeros(257, 1, 512), requires_grad=False)
        self.melW = nn.Parameter(torch.zeros(257, 64), requires_grad=False)
        self.bn0 = nn.BatchNorm2d(64)
        chans = [1, 64, 128, 256, 512, 1024, 2048]
        self.blocks = nn.ModuleList(ConvBlock(a, b) for a, b in zip(chans, chans[1:], strict=False))
        self.fc1 = nn.Linear(2048, 2048)
        self.fc_audioset = nn.Linear(2048, classes)

    def load_panns(self, sd: dict[str, torch.Tensor]) -> None:
        m = {"stft_real": "spectrogram_extractor.stft.conv_real.weight",
             "stft_imag": "spectrogram_extractor.stft.conv_imag.weight", "melW": "logmel_extractor.melW"}
        own = {}
        for k in self.state_dict():
            src = m.get(k, k)
            if k.startswith("blocks."):
                i, rest = k[len("blocks."):].split(".", 1)
                src = f"conv_block{int(i) + 1}.{rest}"
            own[k] = sd[src]
        self.load_state_dict(own)

    def forward(self, wav: torch.Tensor) -> torch.Tensor:
        """wav [B, N] 16 kHz -> [B, 527] ehtimollar."""
        x = F.pad(wav.unsqueeze(1), (256, 256), mode="reflect")
        re, im = F.conv1d(x, self.stft_real, stride=160), F.conv1d(x, self.stft_imag, stride=160)
        mel = torch.matmul((re ** 2 + im ** 2).transpose(1, 2), self.melW)          # [B, T, 64]
        x = (10 * torch.log10(mel.clamp(min=1e-10))).unsqueeze(1)                    # [B, 1, T, 64]
        x = self.bn0(x.transpose(1, 3)).transpose(1, 3)
        for i, b in enumerate(self.blocks):
            x = b(x, (2, 2) if i < 5 else (1, 1))
        x = x.mean(3)
        x = F.max_pool1d(x, 3, 1, 1) + F.avg_pool1d(x, 3, 1, 1)
        x = x.max(2)[0] + x.mean(2)
        return torch.sigmoid(self.fc_audioset(F.relu(self.fc1(x))))


def load_model(device: torch.device) -> tuple[Cnn14, list[str]]:
    from numpy._core.multiarray import _reconstruct  # checkpoint numpy 1.x nomi bilan saqlangan
    np_globals: list[Any] = [(_reconstruct, "numpy.core.multiarray._reconstruct"), np.ndarray,
                             (np.dtype, "numpy.dtype"), np.dtypes.Float64DType, np.dtypes.Int64DType,
                             np.dtypes.Float32DType]
    with torch.serialization.safe_globals(np_globals):
        ck = torch.load(paths.models_dir() / CKPT, map_location="cpu", weights_only=True)
    m = Cnn14()
    m.load_panns(ck["model"])
    with open(paths.models_dir() / LABELS, encoding="utf-8") as f:
        labels = [r["display_name"] for r in csv.DictReader(f)]
    return m.to(device).eval(), labels


def frame_probs(wav: npt.NDArray[np.float32], device: torch.device, batch: int = 128) -> tuple[np.ndarray, list[str]]:
    """wav 16 kHz mono -> [n_hop, 527]: har HOP_S kadr uchun uni qoplagan oynalar ehtimollarining maksimumi."""
    model, labels = load_model(device)
    win, hop = int(WINDOW_S * SR), int(HOP_S * SR)
    n = max(1, (len(wav) - win) // hop + 1)
    pad = np.zeros(max(0, (n - 1) * hop + win - len(wav)), np.float32)
    w = torch.from_numpy(np.concatenate([wav, pad]))
    out = []
    with torch.inference_mode():
        for s in range(0, n, batch):
            idx = torch.arange(s, min(n, s + batch)) * hop
            seg = torch.stack([w[i:i + win] for i in idx.tolist()]).to(device)
            out.append(model(seg).float().cpu().numpy())
    win_p = np.concatenate(out)                                   # [n, 527], oyna i: [i*hop, i*hop+win)
    k = int(round(WINDOW_S / HOP_S))
    frames = np.zeros((n + k - 1, win_p.shape[1]), np.float32)
    for j in range(k):                                            # kadr t — oynalar t-k+1..t
        np.maximum(frames[j:j + n], win_p, out=frames[j:j + n])
    return frames, labels


@dataclass
class Event:
    start_ms: int
    end_ms: int
    kind: str          # yo'tal | aksa | to'ldiruvchi
    label: str         # AudioSet nomi
    prob: float


def detect(frames: np.ndarray, labels: list[str], threshold: float = 0.3, min_ms: int = 150) -> list[Event]:
    """Kadr ehtimollaridan hodisalar: sinf ehtimoli >= threshold bo'lgan ketma-ket kadrlar."""
    out: list[Event] = []
    hop_ms = int(HOP_S * 1000)
    for name, kind in EVENT_CLASSES.items():
        c = labels.index(name)
        on = frames[:, c] >= threshold
        i = 0
        while i < len(on):
            if not on[i]:
                i += 1
                continue
            j = i
            while j < len(on) and on[j]:
                j += 1
            if (j - i) * hop_ms >= min_ms:
                out.append(Event(i * hop_ms, j * hop_ms, kind, name, round(float(frames[i:j, c].max()), 3)))
            i = j
    return sorted(out, key=lambda e: e.start_ms)


def available() -> bool:
    return (paths.models_dir() / CKPT).is_file() and (paths.models_dir() / LABELS).is_file()


def run(wav16k: Path, out: Path) -> list[Event]:
    """16 kHz WAV -> hodisalar (out JSON). GPU bo'lsa GPU (~4 s / 20 min), aks holda CPU."""
    import json

    from darsstudio.audio.extract import read_pcm
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frames, labels = frame_probs(read_pcm(wav16k), dev)
    ev = detect(frames, labels)
    out.write_text(json.dumps([e.__dict__ for e in ev], ensure_ascii=False, indent=1), encoding="utf-8")
    return ev
