#!/usr/bin/env python3
"""試読版の表紙（1600x2560）を手続き的に描く：星空・赤い矮星・氷原・着陸船の影・縦書きの題名。"""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1600, 2560
HORIZON = int(H * 0.66)
rnd = random.Random(20261010)
img = Image.new("RGB", (W, H))
px = img.load()
# 空：上は濃紺、地平線近くは赤みを帯びた暗い紫
for y in range(HORIZON):
    t = y / HORIZON
    r = int(6 + 60 * t ** 3)
    g = int(8 + 18 * t ** 2)
    b = int(28 + 40 * t)
    for x in range(W):
        px[x, y] = (r, g, b)
# 氷原：青白いグラデーション（手前ほど明るい）
for y in range(HORIZON, H):
    t = (y - HORIZON) / (H - HORIZON)
    base = (70 + int(120 * t), 95 + int(120 * t), 130 + int(105 * t))
    for x in range(W):
        px[x, y] = base
d = ImageDraw.Draw(img)
# 星
for _ in range(2600):
    x, y = rnd.randrange(W), rnd.randrange(int(HORIZON * 0.97))
    s = rnd.random()
    v = int(140 + 115 * rnd.random())
    if s > 0.995:
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(v, v, 255))
    elif s > 0.96:
        d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(v, v, v))
    else:
        d.point((x, y), fill=(v // 2, v // 2, v // 2 + 20))
# 天の川のような淡い帯
band = Image.new("L", (W, H), 0)
bd = ImageDraw.Draw(band)
for _ in range(9000):
    t = rnd.random()
    x = int(-200 + t * (W + 400))
    y = int(HORIZON * 0.15 + t * HORIZON * 0.55 + rnd.gauss(0, 120))
    r = rnd.randint(2, 7)
    bd.ellipse([x - r, y - r, x + r, y + r], fill=rnd.randint(8, 22))
band = band.filter(ImageFilter.GaussianBlur(18))
img = Image.composite(Image.new("RGB", (W, H), (150, 160, 210)), img, band)
d = ImageDraw.Draw(img)
# 赤い矮星（地平線の近く、低く）
glow = Image.new("RGB", (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
cx, cy = int(W * 0.28), HORIZON - 70
for r in range(260, 0, -4):
    a = int(90 * (1 - r / 260) ** 2)
    gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(a * 2, a // 2, a // 4))
glow = glow.filter(ImageFilter.GaussianBlur(10))
img = Image.blend(img, Image.eval(Image.merge("RGB", [glow.getchannel(i) for i in range(3)]), lambda v: v), 0.0)
img = Image.composite(img, img, Image.new("L", (W, H), 255))
img = Image.fromarray if False else img
base = img.copy()
img = Image.eval(base, lambda v: v)
img.paste(Image.composite(Image.new("RGB", (W, H), (255, 120, 70)), img, glow.convert("L")), (0, 0))
d = ImageDraw.Draw(img)
d.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=(255, 150, 110))
# 地平線の上だけ星の光（地平線から下は氷）
for y in range(HORIZON, H):
    t = (y - HORIZON) / (H - HORIZON)
    for x in range(0, W):
        r, g, b = img.getpixel((x, y))
        # 赤い光の反射を地平線近くに
        refl = max(0.0, 1 - abs(x - cx) / 500) * max(0.0, 1 - t * 3)
        img.putpixel((x, y), (min(255, int(70 + 120 * t + 120 * refl)), min(255, int(95 + 120 * t + 40 * refl)), min(255, int(130 + 105 * t + 10 * refl))))
d = ImageDraw.Draw(img)
# 氷の割れ目（地平線へ向かう細い線）
for _ in range(14):
    x0 = rnd.randrange(-400, W + 400)
    pts = [(x0, H)]
    x, y = x0, H
    while y > HORIZON + 10:
        y -= rnd.randint(40, 120)
        x += int((W * 0.5 - x) * 0.12 + rnd.gauss(0, 30))
        pts.append((x, max(y, HORIZON + 5)))
    d.line(pts, fill=(40, 60, 85), width=rnd.choice([2, 3, 4]))
# 一本だけ赤みを帯びた亀裂（物語の亀裂）
pts = [(int(W * 0.62), H)]
x, y = pts[0]
while y > HORIZON + 20:
    y -= 70
    x += int(rnd.gauss(-12, 18))
    pts.append((x, y))
d.line(pts, fill=(150, 70, 60), width=5)
# 着陸船の影（小さく）
lx, ly = int(W * 0.68), HORIZON + 95
d.polygon([(lx - 38, ly), (lx + 38, ly), (lx + 22, ly - 70), (lx - 22, ly - 70)], fill=(18, 22, 32))
d.polygon([(lx - 12, ly - 70), (lx + 12, ly - 70), (lx, ly - 112)], fill=(18, 22, 32))
for dx in (-40, 40):
    d.line([(lx + dx * 0.55, ly - 10), (lx + dx, ly + 18)], fill=(18, 22, 32), width=6)
d.ellipse([lx - 3, ly - 52, lx + 3, ly - 46], fill=(255, 210, 120))
# 題名（縦書き）
font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 168, index=0)
small = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 64, index=0)
title = "星を汚す者"
x_title, y0 = W - 300, 230
for i, ch in enumerate(title):
    d.text((x_title + 3, y0 + i * 200 + 3), ch, font=font, fill=(0, 0, 0))
    d.text((x_title, y0 + i * 200), ch, font=font, fill=(236, 240, 252))
sub = "試読版　三つの原稿"
for i, ch in enumerate(sub):
    if ch == "　":
        continue
    d.text((x_title - 140, y0 + 40 + i * 80), ch, font=small, fill=(200, 210, 235))
out = Path(__file__).resolve().parent.parent / "images" / "cover_trial.jpg"
img.save(out, quality=88)
print(out)
