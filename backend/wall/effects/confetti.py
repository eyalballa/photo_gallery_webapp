"""Party confetti frozen mid-fall: tumbling strips, dots, stars and curly streamers, thinner over faces."""

import math
from random import Random

from PIL import Image, ImageDraw, ImageFilter

from wall.config import EffectsConfig
from wall.effects.base import EffectResult, Face, register

SS = 2  # supersampling factor for antialiasing

PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "rainbow": [
        (255, 46, 99), (255, 214, 10), (0, 200, 255), (60, 220, 90), (255, 128, 0),
        (156, 80, 255), (255, 70, 200), (30, 120, 255),
    ],
    "gold": [(214, 166, 46), (232, 190, 70), (190, 140, 30), (226, 120, 60), (176, 180, 192)],
    "pastel": [
        (255, 179, 198), (255, 236, 150), (170, 225, 255), (180, 240, 190), (215, 190, 255),
        (255, 205, 160),
    ],
}


def _shade(c: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    """k < 1 darkens, k > 1 lightens towards white."""
    if k <= 1:
        return tuple(round(v * k) for v in c)
    t = min(k - 1, 1)
    return tuple(round(v + (255 - v) * t) for v in c)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _inner(pts, f: float, nudge: float):
    """The polygon shrunk by f about its centroid and nudged up-left, towards the light."""
    gx, gy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return [(gx + (px - gx) * f - nudge, gy + (py - gy) * f - nudge) for px, py in pts]


def _shape(kind: str, cx: float, cy: float, size: float, squash: float, angle: float, rng: Random):
    """Polygon for a piece: built in its own frame (squash = tumbling foreshortening), then rotated."""
    if kind == "rect":
        ln, wd = size * rng.uniform(0.9, 1.7), size * rng.uniform(0.45, 0.7) * squash
        pts = [(-ln / 2, -wd / 2), (ln / 2, -wd / 2), (ln / 2, wd / 2), (-ln / 2, wd / 2)]
    elif kind == "strip":
        ln, wd = size * rng.uniform(2.0, 3.2), size * rng.uniform(0.22, 0.32) * squash
        pts = [(-ln / 2, -wd / 2), (ln / 2, -wd / 2), (ln / 2, wd / 2), (-ln / 2, wd / 2)]
    elif kind == "dot":
        r = size * rng.uniform(0.35, 0.55)
        pts = [(r * math.cos(t), r * squash * math.sin(t)) for t in (i * math.tau / 18 for i in range(18))]
    else:  # star
        r = size * rng.uniform(0.6, 0.85)
        pts = [
            ((r if i % 2 == 0 else r * 0.45) * math.cos(t), (r if i % 2 == 0 else r * 0.45) * squash * math.sin(t))
            for i, t in ((i, i * math.pi / 5 - math.pi / 2) for i in range(10))
        ]
    c, s = math.cos(angle), math.sin(angle)
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def _streamer(cx: float, cy: float, size: float, angle: float, rng: Random):
    """A curly ribbon: a decaying sine along a slightly curved path."""
    ln = size * rng.uniform(5, 9)
    amp, waves = size * rng.uniform(0.5, 0.9), rng.uniform(1.5, 3)
    bend = rng.uniform(-0.6, 0.6)
    c, s = math.cos(angle), math.sin(angle)
    pts = []
    for i in range(40):
        t = i / 39
        x = (t - 0.5) * ln
        y = amp * math.sin(t * waves * math.tau) + bend * ln * (t - 0.5) ** 2
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


@register
class Confetti:
    id, label, weight, accessory = "confetti", "Confetti", 10.0, False

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        variant = rng.choice(list(PALETTES))
        palette = PALETTES[variant]
        metallic = variant == "gold"
        w, h = img.size
        W, H = w * SS, h * SS
        unit = max(w, h) / 72  # piece size at 1x
        count = int(min(max(w * h / 4200, 140), 480))

        boxes = []
        for f in faces:  # face boxes grown a bit, at 1x
            b = f.box
            gx, gy = b.w * 0.15, b.h * 0.2
            boxes.append((b.x - gx, b.y - gy * 1.5, b.x + b.w + gx, b.y + b.h + gy))

        def density(x: float, y: float) -> float:
            d = 0.35 + 1.0 * (1 - y / h) ** 2  # denser at the top
            edge = min(x, w - x) / w  # 0 at the edges, 0.5 in the middle
            d += 0.8 * max(0.0, 1 - edge / 0.18)
            for x0, y0, x1, y1 in boxes:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return d * 0.06
            return d

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shadow = Image.new("L", (W, H), 0)
        ghosts = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # motion trails, kept apart so they never punch holes
        draw, gdraw = ImageDraw.Draw(layer), ImageDraw.Draw(ghosts)
        sdraw = ImageDraw.Draw(shadow)
        off = unit * 0.35 * SS  # shadow offset (light from the top left)

        placed, tries = 0, 0
        while placed < count and tries < count * 12:
            tries += 1
            x, y = rng.uniform(-unit, w + unit), rng.uniform(-unit, h + unit)
            if rng.random() * 2.2 > density(x, y):
                continue
            placed += 1
            cx, cy = x * SS, y * SS
            depth = rng.uniform(0.7, 1.3)  # nearer pieces are bigger
            size = unit * SS * depth
            angle = rng.uniform(0, math.tau)
            tumble = abs(math.cos(rng.uniform(0, math.pi)))
            squash = max(tumble, 0.12)
            roll = rng.random()
            if roll < 0.25:
                squash = max(squash, 0.35)  # strips are thin already
            base = rng.choice(palette)
            if metallic:  # specular: bright when facing the light, dark edge-on
                k = 0.55 + 0.85 * tumble**2 + rng.uniform(-0.1, 0.1)
            else:
                k = 0.7 + 0.35 * tumble + rng.uniform(-0.05, 0.05)
                if rng.random() < 0.25:
                    k *= 0.8  # the back side
            color = _shade(base, k)
            if roll < 0.05:
                pts = _streamer(cx, cy, size * 0.8, angle, rng)
                lw = max(round(size * 0.26), 2)
                sdraw.line([(px + off, py + off) for px, py in pts], fill=110, width=lw, joint="curve")
                draw.line(pts, fill=color, width=lw, joint="curve")
                hl = _shade(color, 1.35)
                draw.line(pts[::2][:12], fill=_mix(color, hl, 0.6), width=max(lw // 3, 1))
                continue
            kind = "strip" if roll < 0.25 else "rect" if roll < 0.62 else "dot" if roll < 0.92 else "star"
            pts = _shape(kind, cx, cy, size, squash, angle, rng)

            if rng.random() < 0.2:  # motion blur: faint ghosts above (it is falling)
                trail = size * rng.uniform(0.4, 0.8)
                for i in range(1, 7):
                    dy, a = -trail * i / 6, round(60 * (1 - i / 7))
                    gdraw.polygon([(px, py + dy) for px, py in pts], fill=(*color, a))
            sdraw.polygon([(px + off * depth, py + off * depth) for px, py in pts], fill=120)
            draw.polygon(pts, fill=color)
            if metallic:  # foil: dark rim, lighter body, bright glint towards the light
                draw.polygon(_inner(pts, 0.75, size * 0.03), fill=_shade(color, 1.18))
                if tumble > 0.35:
                    draw.polygon(_inner(pts, 0.4, size * 0.07), fill=_shade(color, 1.6))
            elif tumble > 0.7 and rng.random() < 0.5:  # a soft sheen on pieces facing the light
                draw.polygon(_inner(pts, 0.5, size * 0.06), fill=_shade(color, 1.18))

        ghosts.alpha_composite(layer)
        layer = ghosts.resize((w, h), Image.LANCZOS)
        shadow = shadow.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(unit * 0.25))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        img.paste(dark, (0, 0), shadow.point(lambda v: v * 0.45))
        img.paste(layer, (0, 0), layer)
        return EffectResult(variant=variant, aged_paper=False)
