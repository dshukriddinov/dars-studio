"""templates/demo: sintetik studiya shabloni (haqiqiy studiya foni berilmaguncha, O-08). Qayta yaratish:
    python tools/make_demo_template.py
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "templates" / "demo"
W, H = 1920, 1080
QUAD = [[150, 170], [1030, 200], [1022, 690], [142, 722]]   # chap tomonda, biroz perspektivada
ANCHOR = [1060, 40, 1880, 1080]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):  # vertikal gradient: to'q ko'k -> to'q kulrang
        t = y / H
        c = (int(18 + 20 * t), int(32 + 18 * t), int(58 - 10 * t))
        for x in range(W):
            px[x, y] = c
    d = ImageDraw.Draw(bg)
    d.rectangle([0, 860, W, H], fill=(40, 44, 52))                      # pol
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).polygon([tuple(p) for p in QUAD], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    bg.paste(Image.new("RGB", (W, H), (70, 110, 170)), (0, 0), glow.point(lambda v: v // 3))
    bezel = [(-14, -14), (14, -14), (14, 14), (-14, 14)]
    frame = [(x + dx, y + dy) for (x, y), (dx, dy) in zip(QUAD, bezel, strict=True)]
    d.polygon(frame, fill=(12, 12, 14))                                 # ekran ramkasi (bezel)
    d.polygon([tuple(p) for p in QUAD], fill=(25, 25, 28))              # bo'sh ekran (slayd ustiga tushadi)
    bg.save(OUT / "background.png")

    logo = Image.new("RGBA", (360, 96), (0, 0, 0, 0))
    ld = ImageDraw.Draw(logo)
    ld.rounded_rectangle([0, 0, 359, 95], 18, fill=(255, 255, 255, 210))
    try:
        font = ImageFont.truetype("arial.ttf", 52)
    except OSError:
        font = ImageFont.load_default()
    ld.text((24, 18), "Dars Studio", fill=(20, 40, 90, 255), font=font)
    logo.save(OUT / "logo.png")

    tpl = {"id": "demo", "canvas": [W, H], "background": "background.png", "screen_quad": QUAD,
           "screen_aspect": "16:9", "teacher_anchor": ANCHOR, "safe_margin_px": 24,
           "logo": {"file": "logo.png", "pos": [1660, 32], "height": 48},
           "lower_third": {"style": "default", "duration_s": 6},
           "transitions": {"slide_frames": 8, "layout_frames": 12},
           "fullscreen": {"fit": "contain", "pillarbox_color": "#000000"}, "key_defaults": {}}
    (OUT / "template.json").write_text(json.dumps(tpl, indent=1), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
