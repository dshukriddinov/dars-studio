"""Studiya fonidan shablon yaratish: fonni kanvasga joylash, ekran (oq slayd hududi) burchaklarini avtomatik topish.

    python tools/make_template.py ID FON.png [--scale 0.9145 --offset -4 0] [--intro intro.mp4] [--outro outro.mp4]
                                  [--fit 250 1473 161 368 | --teacher 0.929 692 79] [--copyright "matn"]

Masshtab/siljish berilmasa fon kanvasni to'liq qoplaydi (cover). Ekran burchaklari: eng katta oq to'rtburchak
(fonda eski slayd chizilgan bo'lishi kerak). Natija: templates/ID/ (background.png 1920x1080 + template.json).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

from darsstudio import paths

W, H = 1920, 1080


def place_background(src: Path, scale: float | None, offset: tuple[float, float]) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(src), np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    s = scale or max(W / w, H / h)
    m = np.float32([[s, 0, offset[0]], [0, s, offset[1]]])
    out = cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_REPLICATE)
    return out


def find_screen_quad(bgr: np.ndarray) -> list[list[float]]:
    """Eng katta oq (past to'yinganlik, yorqin) hudud -> 4 burchak TL, TR, BR, BL."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    white = ((hsv[..., 1] < 60) & (hsv[..., 2] > 170)).astype(np.uint8) * 255
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    cs, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cs, key=cv2.contourArea)
    peri = cv2.arcLength(c, True)
    ap = None
    for eps in (0.01, 0.02, 0.03, 0.05):
        ap = cv2.approxPolyDP(c, eps * peri, True)
        if len(ap) == 4:
            break
    if ap is None or len(ap) != 4:
        raise SystemExit("Ekran to'rtburchagi topilmadi: burchaklarni calibrate-screen bilan bering.")
    pts = ap.reshape(-1, 2).astype(float)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    q = [pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]]
    return [[round(float(x), 1), round(float(y), 1)] for x, y in q]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("background")
    ap.add_argument("--scale", type=float)
    ap.add_argument("--offset", type=float, nargs=2, default=(0.0, 0.0))
    ap.add_argument("--intro")
    ap.add_argument("--outro")
    ap.add_argument("--teacher", type=float, nargs=3, metavar=("SCALE", "X", "Y"), help="qat'iy joy")
    ap.add_argument("--fit", type=float, nargs=4, metavar=("HEAD_Y", "CENTER_X", "HEAD_PX", "SHOULDER_PX"),
                    help="gavda: bosh tepasi, markaz, bosh balandligi, yelka kengligi (kanvas px)")
    ap.add_argument("--copyright")
    a = ap.parse_args()
    out = paths.ROOT / "templates" / a.id
    out.mkdir(parents=True, exist_ok=True)
    bg = place_background(Path(a.background), a.scale, tuple(a.offset))
    cv2.imencode(".png", bg)[1].tofile(str(out / "background.png"))
    quad = find_screen_quad(bg)
    tpl: dict[str, object] = {
        "id": a.id, "canvas": [W, H], "background": "background.png", "screen_quad": quad, "screen_aspect": "16:9",
        "teacher_anchor": [1240, 245, 1840, 1080], "safe_margin_px": 24, "logo": None,
        "lower_third": {"style": "akademiya", "duration_s": 8.6},
        "transitions": {"slide_frames": 25, "layout_frames": 30, "slide": "clock_wipe", "layout": "zoom_blur"},
        "fullscreen": {"fit": "contain", "pillarbox_color": "#000000"}, "key_defaults": {},
        "scene_policy": {"mode": "a_then_b", "a_seconds": 10.0, "min_b_seconds": 10.0},
    }
    if a.fit:
        tpl["teacher_fit"] = {"head_y": int(a.fit[0]), "center_x": int(a.fit[1]), "head_px": a.fit[2],
                              "shoulder_px": a.fit[3]}
    if a.teacher:
        tpl["teacher_placement"] = {"scale": a.teacher[0], "x": int(a.teacher[1]), "y": int(a.teacher[2])}
    for key, f in (("intro", a.intro), ("outro", a.outro)):
        if f:
            shutil.copy2(f, out / Path(f).name)
            tpl[key] = Path(f).name
    if a.copyright:
        tpl["copyright"] = {"text": a.copyright, "on": "tail", "seconds": 5.0, "slide_s": 3.0, "slide_px": 640}
    (out / "template.json").write_text(json.dumps(tpl, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out}\n  ekran: {quad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
