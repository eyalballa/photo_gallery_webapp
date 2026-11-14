"""1960s screen-print pop art: a 2x2 grid of the photo, each tile flattened to three tones in clashing colours."""

from random import Random

import numpy as np
from PIL import Image, ImageFilter

from wall.config import EffectsConfig
from wall.effects.base import EffectResult, Face, register

# each tile is (ink, mid tone, highlight/background); four tiles per variant
PALETTES: dict[str, list[tuple[tuple[int, int, int], ...]]] = {
    "warhol": [
        ((30, 20, 60), (255, 64, 160), (255, 230, 40)),  # navy / hot pink / yellow
        ((10, 40, 90), (255, 140, 0), (0, 220, 235)),  # blue / orange / cyan
        ((70, 0, 110), (150, 230, 30), (255, 120, 200)),  # purple / lime / pink
        ((20, 20, 20), (230, 30, 40), (60, 140, 255)),  # black / red / blue
    ],
    "candy": [
        ((120, 0, 90), (255, 110, 180), (180, 255, 240)),
        ((0, 70, 80), (255, 200, 0), (255, 90, 120)),
        ((40, 0, 120), (0, 210, 160), (255, 245, 120)),
        ((150, 20, 0), (255, 160, 60), (140, 120, 255)),
    ],
    "electric": [
        ((0, 0, 0), (0, 255, 120), (255, 0, 200)),
        ((0, 0, 0), (255, 240, 0), (0, 120, 255)),
        ((0, 0, 0), (255, 60, 30), (0, 240, 255)),
        ((0, 0, 0), (200, 80, 255), (255, 200, 0)),
    ],
}
GUTTER = (250, 248, 240)


def _crop_box(w: int, h: int, aspect: float, faces: list[Face]) -> tuple[int, int, int, int]:
    """Largest box of `aspect` (w/h) that fits, zoomed a little towards the faces and centred on them."""
    x0 = min(f.box.x for f in faces)
    y0 = min(f.box.y for f in faces)
    x1 = max(f.box.x + f.box.w for f in faces)
    y1 = max(f.box.y + f.box.h for f in faces)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cw, ch = (w, w / aspect) if w / h < aspect else (h * aspect, h)
    # zoom in so the faces fill more of the tile, but keep them (with margin) inside
    need = max((x1 - x0) * 2.0 / cw, (y1 - y0) * 2.4 / ch, 0.42)
    s = min(1.0, need)
    cw, ch = cw * s, ch * s
    left = min(max(cx - cw / 2, 0), w - cw)
    top = min(max(cy - ch * 0.45, 0), h - ch)
    return round(left), round(top), round(left + cw), round(top + ch)


@register
class PopArt:
    id, label, weight, accessory = "pop_art", "Pop art", 10.0, False

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        w, h = img.size
        g = max(4, round(min(w, h) * 0.012))
        tw, th = (w - 3 * g) // 2, (h - 3 * g) // 2
        big = max(f.size for f in faces)
        faces = [f for f in faces if f.size >= 0.55 * big]  # frame the main subjects, not tiny background faces
        box = _crop_box(w, h, tw / th, faces)
        tile = img.convert("RGB").crop(box).resize((tw, th), Image.LANCZOS)
        # smooth out texture so the posterized shapes read as flat screen-print areas
        lum = np.asarray(tile.convert("L").filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.2)),
                         dtype=np.float32)
        # thresholds from the face region so features survive; the background just goes along
        sx, sy = tw / (box[2] - box[0]), th / (box[3] - box[1])
        mask = np.zeros(lum.shape, bool)
        for f in faces:
            fx0, fy0 = max(0, int((f.box.x - box[0]) * sx)), max(0, int((f.box.y - box[1]) * sy))
            fx1, fy1 = int((f.box.x + f.box.w - box[0]) * sx), int((f.box.y + f.box.h - box[1]) * sy)
            mask[fy0:max(fy0, fy1), fx0:max(fx0, fx1)] = True
        ref = lum[mask] if mask.sum() > 200 else lum
        lo, hi = np.percentile(ref, [25, 62])
        levels = (lum > lo).astype(np.uint8) + (lum > hi)

        variant = rng.choice(list(PALETTES))
        palettes = PALETTES[variant][:]
        rng.shuffle(palettes)
        out = Image.new("RGB", (w, h), GUTTER)
        for i, pal in enumerate(palettes):
            lut = np.array(pal, dtype=np.uint8)
            t = Image.fromarray(lut[levels])
            out.paste(t, (g + (i % 2) * (tw + g), g + (i // 2) * (th + g)))
        img.paste(out)
        return EffectResult(variant=variant, aged_paper=False)
