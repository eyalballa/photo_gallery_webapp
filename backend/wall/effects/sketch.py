"""Pencil sketch: colour-dodge line drawing, darkened to read from afar, hatched shadows, on grainy off-white paper."""

from random import Random

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from wall.config import EffectsConfig
from wall.effects.base import EffectResult, Face, register

# variant -> (pencil colour at full darkness, paper colour, line strength exponent)
VARIANTS = {
    "graphite": ((22, 24, 30), (244, 241, 232), 3.0),
    "sepia": ((56, 32, 16), (243, 232, 210), 2.8),
    "charcoal": ((8, 7, 7), (238, 234, 226), 3.4),
}


K = 30.0


def _blur(a: np.ndarray, radius: float) -> np.ndarray:
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)


@register
class Sketch:
    id, label, weight, accessory = "sketch", "Pencil sketch", 10.0, False

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        variant = rng.choices(list(VARIANTS), weights=[5, 3, 2])[0]
        ink, paper, strength = VARIANTS[variant]
        nrng = np.random.default_rng(rng.randrange(2**32))
        w, h = img.size
        scale = max(w, h) / 1600

        grey = ImageOps.autocontrast(img.convert("L"), cutoff=1)
        g = np.asarray(grey.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(scale)), np.float32)
        # classic dodge: grey / (1 - blur(inverted grey)) keeps only the edges. The +K offset stops it amplifying
        # sensor noise in dark areas, where the ratio is otherwise between two tiny numbers.
        base = 255 - _blur(255 - g, 8 * scale)
        lines = np.clip((g + K) / (base + K), 0, 1)
        # drop the faint film-grain speckle, then darken and thicken the strokes so they read across a room
        stroke = np.clip((1 - lines - 0.015) * 3.0, 0, 1)
        lines = (1 - stroke) ** strength

        # light tonal shading so faces and hair keep their volume instead of going blank white
        tone = _blur(np.asarray(grey, np.float32), 4 * scale) / 255
        shade = 1 - 0.38 * np.clip(1 - tone, 0, 1) ** 1.2

        # faint cross-hatching in the darker regions
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        period = max(5.0, 7 * scale)
        jitter = nrng.normal(0, 0.6, (h, 1)).astype(np.float32)
        hatch1 = (np.abs(((xx + yy + jitter) % period) - period / 2) < 0.8).astype(np.float32)
        hatch2 = (np.abs(((xx - yy + jitter) % period) - period / 2) < 0.8).astype(np.float32)
        dark1 = np.clip((0.45 - tone) / 0.2, 0, 1)
        dark2 = np.clip((0.25 - tone) / 0.15, 0, 1)
        hatch = 1 - 0.5 * (hatch1 * dark1 + hatch2 * dark2)
        hatch = _blur(hatch * 255, 0.5 * scale) / 255

        darkness = np.clip(lines * shade * hatch, 0, 1)  # 1 = paper, 0 = full pencil

        # paper: fine grain plus horizontal fibres (noise stretched sideways), and a light vignette
        grain = nrng.normal(0, 1, (h, w)).astype(np.float32)
        fib = nrng.normal(0, 1, (max(h // 2, 1), max(w // 24, 1))).astype(np.float32)
        fib_im = Image.fromarray(np.clip(fib * 40 + 128, 0, 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        fibres = (np.asarray(fib_im, dtype=np.float32) - 128) / 40
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
        vignette = np.clip(1.04 - 0.14 * r**2, 0.82, 1)
        paper_lum = (1 + 0.025 * grain + 0.012 * fibres) * vignette

        ink_a = np.array(ink, dtype=np.float32)
        paper_a = np.array(paper, dtype=np.float32)
        # graphite catches the paper grain: strokes are a little patchy
        d = np.clip(darkness + 0.06 * grain * (1 - darkness), 0, 1)[..., None]
        out = (ink_a + (paper_a - ink_a) * d) * paper_lum[..., None]
        img.paste(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)))
        return EffectResult(variant=variant, aged_paper=True)
