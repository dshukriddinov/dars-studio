"""Kim gapiryapti (diarization): o'qituvchi — asosiy ovoz; operator/boshqa odam gapirgan joylar aniqlanadi.

Model: wespeaker voxceleb resnet34-LM (ONNX, CPU, CC-BY-4.0 — attribution: WeSpeaker, arXiv:2210.17016).
Nutq (VAD) ichida 2 s oynalar embedding'lanadi; o'qituvchi markazi ikki bosqichda topiladi (avval hamma oynalar
o'rtachasi, keyin chetga chiqqanlarsiz qayta). Markazdan uzoq oynalar — "boshqa ovoz", qo'shnilari birlashtiriladi.
Natija kesish TAKLIFI bo'ladi, avtomatik kesilmaydi.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from darsstudio import paths

F32 = npt.NDArray[np.float32]

SR = 16000
WIN_S = 2.0            # embedding oynasi
HOP_S = 1.0
SIM_OTHER = 0.42       # o'qituvchi markaziga kosinus o'xshashlik shundan past — boshqa ovoz (o'lchov bilan tanlangan)
SIM_CORE = 0.60        # markazni qayta hisoblashda ishonchli "o'qituvchi" oynalar
MIN_OTHER_S = 0.8      # shundan qisqa "boshqa ovoz" oroli — shovqin, tashlanadi
MODEL = "wespeaker-voxceleb-resnet34-LM/voxceleb_resnet34_LM.onnx"


def _mel_banks(n_fft: int = 512, n_mels: int = 80, low: float = 20.0, high: float = 8000.0) -> F32:
    """Kaldi uslubidagi mel filtrlar (torchaudio.compliance.kaldi.fbank bilan mos)."""
    def mel(f: float) -> float:
        return 1127.0 * math.log(1.0 + f / 700.0)
    lo, hi = mel(low), mel(high)
    centers = np.linspace(lo, hi, n_mels + 2)
    fft_hz = np.arange(n_fft // 2 + 1) * SR / n_fft
    fft_mel = 1127.0 * np.log(1.0 + fft_hz / 700.0)
    banks = np.zeros((n_mels, n_fft // 2 + 1), np.float32)
    for m in range(n_mels):
        left, center, right = centers[m], centers[m + 1], centers[m + 2]
        up = (fft_mel - left) / (center - left)
        down = (right - fft_mel) / (right - center)
        banks[m] = np.clip(np.minimum(up, down), 0.0, 1.0)
    banks[:, 0] = 0.0   # kaldi DC bin'ni ishlatmaydi
    return banks


_BANKS: F32 | None = None


def fbank(wav: F32) -> F32:
    """Kaldi uslubidagi log-mel fbank [T, 80]: 25 ms oyna / 10 ms qadam, povey oyna, pre-emphasis 0.97, dither 0."""
    global _BANKS
    if _BANKS is None:
        _BANKS = _mel_banks()
    frame, hop, n_fft = 400, 160, 512
    n = 1 + max(0, (len(wav) - frame)) // hop
    if len(wav) < frame:
        return np.zeros((0, 80), np.float32)
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    frames = wav[idx].astype(np.float64)
    frames = frames - frames.mean(axis=1, keepdims=True)                      # remove_dc_offset
    frames = np.concatenate([frames[:, :1] * (1 - 0.97), frames[:, 1:] - 0.97 * frames[:, :-1]], axis=1)
    win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(frame) / (frame - 1))) ** 0.85   # povey
    spec = np.abs(np.fft.rfft(frames * win, n=n_fft)) ** 2
    feats = np.log(np.maximum(spec @ _BANKS.T, 1e-10))
    return feats.astype(np.float32)


@dataclass
class OtherSpan:
    start_ms: int
    end_ms: int
    sim: float      # o'qituvchi markaziga eng yaqin oynaning o'xshashligi (past = ishonchli boshqa ovoz)


def embed_windows(wav: F32, speech: list[tuple[int, int]], model_path: Path | None = None,
                  win_s: float = WIN_S, hop_s: float = HOP_S) -> tuple[F32, list[tuple[int, int]]]:
    """Nutq oraliqlaridagi oynalar uchun L2-normlangan embedding'lar [N, 256] va oyna vaqtlari (ms)."""
    import onnxruntime as ort  # type: ignore[import-untyped]
    sess = ort.InferenceSession(str(model_path or paths.models_dir() / MODEL), providers=["CPUExecutionProvider"])
    spans: list[tuple[int, int]] = []
    for s, e in speech:
        t = s
        while t < e:
            w_end = min(t + int(win_s * 1000), e)
            if w_end - t >= 600:    # juda qisqa oyna embedding uchun ishonchsiz
                spans.append((t, w_end))
            t += int(hop_s * 1000)
    feats = []
    for s, e in spans:
        f = fbank(wav[s * SR // 1000: e * SR // 1000])
        feats.append(f - f.mean(axis=0, keepdims=True))    # CMN (wespeaker inference'dagi kabi)
    embs = np.zeros((len(spans), 256), np.float32)
    by_len: dict[int, list[int]] = {}
    for i, f in enumerate(feats):
        by_len.setdefault(f.shape[0], []).append(i)
    for idx in by_len.values():                            # bir xil uzunlikdagi oynalar bitta batch'da (CPU 4-5x tez)
        for k in range(0, len(idx), 64):
            part = idx[k:k + 64]
            out = sess.run(["embs"], {"feats": np.stack([feats[i] for i in part])})[0]
            embs[part] = out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
    return embs, spans


def other_spans(embs: F32, spans: list[tuple[int, int]]) -> list[OtherSpan]:
    """O'qituvchi markazidan uzoq oynalar -> birlashtirilgan "boshqa ovoz" oraliqlari."""
    if len(embs) < 5:
        return []
    center = embs.mean(axis=0)
    center /= max(float(np.linalg.norm(center)), 1e-9)
    sim = embs @ center
    core = embs[sim >= max(SIM_CORE, float(np.quantile(sim, 0.3)))]   # chetga chiqqanlarsiz qayta markaz
    if len(core):
        center = core.mean(axis=0)
        center /= max(float(np.linalg.norm(center)), 1e-9)
        sim = embs @ center
    out: list[OtherSpan] = []
    for i, (s, e) in enumerate(spans):
        if sim[i] >= SIM_OTHER:
            continue
        if out and s <= out[-1].end_ms + 400:
            out[-1] = OtherSpan(out[-1].start_ms, max(out[-1].end_ms, e), max(out[-1].sim, float(sim[i])))
        else:
            out.append(OtherSpan(s, e, float(sim[i])))
    return [o for o in out if o.end_ms - o.start_ms >= MIN_OTHER_S * 1000]


def run(wav16k: F32, speech: list[tuple[int, int]], out_json: Path) -> list[OtherSpan]:
    embs, spans = embed_windows(wav16k, speech)
    others = other_spans(embs, spans)
    out_json.write_text(json.dumps({"windows": len(spans),
                                    "other": [[o.start_ms, o.end_ms, round(o.sim, 3)] for o in others]},
                        ensure_ascii=False), encoding="utf-8")
    return others
