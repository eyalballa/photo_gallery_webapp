"""Old-West wanted poster: parchment, stretched wood-type lettering, the sepia faces and a silly birthday reward."""

from random import Random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from wall.config import EffectsConfig
from wall.effects.base import EffectResult, Face, register

SEPIA = np.array([[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]])
PAPER = np.array([226, 200, 150], dtype=np.float32)
INK = (58, 34, 18)
RED = (128, 30, 20)
BEHIND = (52, 36, 24)  # the wooden wall seen through torn corners

CRIMES = [
    "FOR EATING ALL THE CAKE",
    "FOR STEALING THE FROSTING",
    "FOR POPPING ALL THE BALLOONS",
    "FOR OPENING EVERYONE'S PRESENTS",
    "FOR BLOWING OUT THE CANDLES TWICE",
    "FOR HOGGING THE PINATA",
    "FOR DANCING WITHOUT A LICENSE",
    "FOR BEING TOO MUCH FUN",
]
SUBTITLES = ["HUNGRY OR FULL", "SILLY OR SERIOUS", "SLEEPY OR AWAKE", "WITH CAKE OR WITHOUT"]
REWARDS = {
    "million": "$1,000,000",
    "cupcakes": "100 CUPCAKES",
    "pony": "ONE PONY",
    "candy": "A BAG OF CANDY",
    "balloons": "99 BALLOONS",
    "hugs": "1,000 HUGS",
}


def _text(text: str, box_w: float, box_h: float, color, stretch: float = 1.0, bold: float = 0.06) -> Image.Image:
    """`text` rendered big, cropped to its ink, then scaled to fit (box_w, box_h) with a vertical stretch."""
    size = 120
    font = ImageFont.load_default(size=size)
    stroke = max(1, round(size * bold))
    l, t, r, b = font.getbbox(text, stroke_width=stroke)
    layer = Image.new("L", (r - l + 4, b - t + 4), 0)
    ImageDraw.Draw(layer).text((2 - l, 2 - t), text, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
    layer = layer.crop(layer.getbbox())
    nw, nh = layer.size
    scale = min(box_w / nw, box_h / (nh * stretch))
    mask = layer.resize((max(1, round(nw * scale)), max(1, round(nh * scale * stretch))), Image.LANCZOS)
    out = Image.new("RGBA", mask.size, color)
    out.putalpha(mask)
    return out


def _paste_centered(canvas: Image.Image, piece: Image.Image, cx: float, top: float) -> float:
    canvas.paste(piece, (round(cx - piece.width / 2), round(top)), piece)
    return top + piece.height


def _crop_box(img: Image.Image, faces: list[Face], aspect: float) -> tuple[int, int, int, int]:
    """A crop of aspect w/h around all faces with headroom, as tight as the faces allow."""
    W, H = img.size
    x0 = min(f.box.x - f.box.w * 0.45 for f in faces)
    x1 = max(f.box.x + f.box.w * 1.45 for f in faces)
    y0 = min(f.box.y - f.box.h * 0.45 for f in faces)
    y1 = max(f.box.y + f.box.h * 1.35 for f in faces)
    w, h = x1 - x0, y1 - y0
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    if w > W:
        w, h = W, W / aspect
    if h > H:
        h, w = H, H * aspect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left = min(max(cx - w / 2, 0), W - w)
    top = min(max(cy - h / 2, 0), H - h)
    return round(left), round(top), round(left + w), round(top + h)


def _parchment(w: int, h: int, nrng: np.random.Generator) -> Image.Image:
    a = np.broadcast_to(PAPER, (h, w, 3)).copy()
    # blotchy low-frequency stains plus fine grain
    blot = nrng.normal(0, 1, (max(2, h // 60), max(2, w // 60))).astype(np.float32)
    blot_img = Image.fromarray(((blot - blot.min()) / (np.ptp(blot) + 1e-6) * 255).astype(np.uint8))
    blot = np.asarray(blot_img.resize((w, h), Image.BICUBIC), dtype=np.float32) / 255 - 0.5
    a *= (1 + 0.16 * blot)[..., None]
    a += nrng.normal(0, 7, (h, w, 1))
    # burnt edges
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)) / (0.09 * min(w, h))
    edge = edge + 0.35 * blot  # ragged burn line
    burn = np.clip(edge, 0, 1) ** 0.6
    a = a * (0.35 + 0.65 * burn)[..., None]
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    a *= np.clip(1.08 - 0.22 * r**2, 0.6, 1)[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _sepia(photo: Image.Image, nrng: np.random.Generator) -> Image.Image:
    a = np.asarray(photo, dtype=np.float32)
    gray = a.mean(axis=2, keepdims=True)
    a = gray + (a - gray) * 0.6
    a = np.clip(a @ SEPIA.T, 0, 255)
    a = (a - 128) * 1.12 + 128  # a bit punchier, like a cheap print
    a = a * 0.85 + PAPER * 0.15
    a += nrng.normal(0, 6, (a.shape[0], a.shape[1], 1))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


@register
class Wanted:
    id, label, weight, accessory = "wanted", "Wanted poster", 10.0, False

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        W, H = img.size
        nrng = np.random.default_rng(rng.randrange(2**32))
        crime = rng.choice(CRIMES)
        subtitle = rng.choice(SUBTITLES)
        reward_key = rng.choice(sorted(REWARDS))
        out = _parchment(W, H, nrng)
        draw = ImageDraw.Draw(out)

        m = 0.075 * min(W, H)
        frame = round(m * 0.45)
        lw = max(1, round(min(W, H) * 0.003))
        draw.rectangle([frame, frame, W - frame, H - frame], outline=INK, width=lw)
        draw.rectangle([frame + 3 * lw, frame + 3 * lw, W - frame - 3 * lw, H - frame - 3 * lw], outline=INK, width=lw)

        inner_w, avail = W - 2 * m, H - 2 * m
        landscape = W > H * 1.2
        gap = avail * 0.02
        y = m
        title = _text("WANTED", inner_w * (0.8 if landscape else 0.94), avail * (0.2 if landscape else 0.14), INK,
                      stretch=1.7, bold=0.07)
        y = _paste_centered(out, title, W / 2, y) + gap
        sub = _text(subtitle, inner_w * 0.6, avail * (0.055 if landscape else 0.04), RED, stretch=1.2, bold=0.04)
        y = _paste_centered(out, sub, W / 2, y) + gap * 1.5

        b = max(2, round(min(W, H) * 0.006))
        if landscape:  # photo on the left, the charges on the right
            ph = H - m - y - 2 * b
            pw = min(inner_w * 0.56, ph * 1.3)
            px = round(m + 2 * b)
            col_x, col_w = px + pw + 2 * b + inner_w * 0.03, W - m - (px + pw + 2 * b + inner_w * 0.03)
            self._photo(out, draw, img, faces, nrng, px, round(y), pw, ph, b)
            lines = _split(crime) + ["REWARD", REWARDS[reward_key]]
            self._column(out, lines, col_x + col_w / 2, col_w, y, H - m - y)
        else:
            ph = avail * 0.53
            pw = min(inner_w * 0.86, ph * 1.05)
            self._photo(out, draw, img, faces, nrng, round(W / 2 - pw / 2), round(y), pw, ph, b)
            y += ph + 2 * b + gap * 1.5
            lines = ([crime] if len(crime) <= 26 else _split(crime)) + ["REWARD", REWARDS[reward_key]]
            self._column(out, lines, W / 2, inner_w, y, H - m - y)

        # nail holes and a torn corner or two
        for nx, ny in [(frame, frame), (W - frame, frame)]:
            r = max(3, min(W, H) * 0.009)
            draw.ellipse([nx - r * 1.8, ny - r * 1.8, nx + r * 1.8, ny + r * 1.8], fill=(150, 115, 75))
            draw.ellipse([nx - r, ny - r, nx + r, ny + r], fill=BEHIND)
        corners = [(0, H, 1, -1), (W, H, -1, -1)]
        for ox, oy, sx, sy in rng.sample(corners, rng.randint(1, 2)):
            s = min(W, H) * rng.uniform(0.05, 0.08)
            pts = [(ox, oy), (ox + sx * s * rng.uniform(0.9, 1.3), oy)]
            for t in (0.75, 0.5, 0.25):
                pts.append((ox + sx * s * t + sx * rng.uniform(-0.08, 0.08) * s,
                            oy + sy * s * (1 - t) + sy * rng.uniform(-0.08, 0.08) * s))
            pts.append((ox, oy + sy * s * rng.uniform(0.9, 1.3)))
            draw.polygon(pts, fill=BEHIND)

        img.paste(out.filter(ImageFilter.SMOOTH))
        return EffectResult(variant=reward_key, aged_paper=True)

    @staticmethod
    def _photo(out, draw, img, faces, nrng, px: int, py: int, pw: float, ph: float, b: int) -> None:
        crop = img.crop(_crop_box(img, faces, pw / ph)).resize((round(pw), round(ph)), Image.LANCZOS)
        photo = _sepia(crop, nrng)
        draw.rectangle([px - 2 * b, py - 2 * b, px + photo.width + 2 * b - 1, py + photo.height + 2 * b - 1], fill=INK)
        draw.rectangle([px - b, py - b, px + photo.width + b - 1, py + photo.height + b - 1], fill=(205, 180, 135))
        out.paste(photo, (px, py))

    @staticmethod
    def _column(out, lines: list[str], cx: float, width: float, top: float, height: float) -> None:
        """Crime line(s), REWARD and the amount, stacked and spread over the given height."""
        *crime, reward, amount = lines
        n = len(crime)
        share = 0.22 if n == 1 else 0.15
        rows = [(t, width * 0.92, height * share, INK, 1.25, 0.04) for t in crime]
        rows += [(reward, width * 0.5, height * 0.25, RED, 1.5, 0.06), (amount, width * 0.85, height * 0.3, INK, 1.4, 0.06)]
        pieces = [_text(*r) for r in rows]
        lh = min(p.height for p in pieces[:n])  # crime lines share one letter size
        pieces[:n] = [p.resize((round(p.width * lh / p.height), lh), Image.LANCZOS) for p in pieces[:n]]
        step = max(0.0, (height - sum(p.height for p in pieces)) / (len(pieces) + 0.5))
        y = top + step * 0.25
        for i, p in enumerate(pieces):
            y = _paste_centered(out, p, cx, y) + (step * 0.3 if i < n - 1 else step)


def _split(text: str) -> list[str]:
    """Two lines, broken at the space closest to the middle."""
    words = text.split()
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]
