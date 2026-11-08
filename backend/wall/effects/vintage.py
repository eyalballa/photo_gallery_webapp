"""Old-photo look: sepia, fade, grain, vignette and a few scratches. Pairs with a yellowed polaroid."""

from random import Random

import numpy as np
from PIL import Image, ImageDraw

from wall.effects.base import EffectResult, Face, register

SEPIA = np.array([[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]])
PAPER = np.array([240, 228, 200], dtype=np.float32)


@register
class Vintage:
    id, label, weight, accessory = "vintage", "Vintage", 25.0, False

    def apply(self, img: Image.Image, faces: list[Face], rng: Random) -> EffectResult:
        a = np.asarray(img.convert("RGB"), dtype=np.float32)
        h, w, _ = a.shape
        a = np.clip(a @ SEPIA.T, 0, 255)
        a = a * 0.82 + PAPER * 0.18  # fade towards old paper
        noise = np.random.default_rng(rng.randrange(2**32)).normal(0, 9, (h, w, 1))
        a = a + noise
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
        a = a * np.clip(1.15 - 0.45 * r**2, 0.45, 1)[..., None]
        out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

        draw = ImageDraw.Draw(out)
        for _ in range(rng.randint(2, 5)):
            x = rng.uniform(0, w)
            draw.line([(x, rng.uniform(0, h * 0.3)), (x + rng.uniform(-w * 0.02, w * 0.02), rng.uniform(h * 0.6, h))],
                      fill=(235, 225, 205), width=1)
        img.paste(out)
        return EffectResult(variant=None, aged_paper=True)
