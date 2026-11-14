"""Cartoon big eyes: a smooth bulge warp on each eye plus an anime catch-light sparkle."""

import math
from random import Random

import numpy as np
from PIL import Image

from wall.config import EffectsConfig
from wall.effects.base import EffectResult, Face, Point, register

# variant -> range of the centre shrink s (centre magnification is 1 / (1 - s))
STRENGTH = {"cute": (0.48, 0.52), "huge": (0.56, 0.60)}
RADIUS = 0.5  # bulge radius along the eye line, in inter-ocular units (<= 0.5 so the two eyes never overlap)
SQUASH = 1.25  # taller across the eye line than along it: cartoon eyes are tall, and there's room above and below
PLATEAU = 0.2  # inside this fraction of the radius the magnification is uniform (the eye itself)
DARK = 170  # luminance above which a catch-light is fully suppressed (iris is darker than skin)
LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)
# catch-lights: (offset along the eye line, offset down the face, radius) in iris radii, and opacity
SPARKLES = [(-0.25, -0.25, 0.22, 0.95), (0.27, 0.22, 0.1, 0.85)]
IRIS = 0.093  # natural iris radius in inter-ocular units (~5.8 mm / 63 mm)


def _bulge(a: np.ndarray, c: Point, roll: float, r: float, s: float) -> None:
    """Magnifies a[...] around c in place: inverse-maps each output pixel inside an ellipse (radius r
    along the roll direction, r * SQUASH across) to a source pixel nearer the centre, bilinear sampled.
    The shrink factor is 1 - s on the plateau and rises with a smoothstep to 1 (with zero slope, so no seam)
    at the edge; since it only grows outwards, the mapping stays monotonic (no fold-overs)."""
    h, w, _ = a.shape
    reach = r * max(1.0, SQUASH)
    x0, x1 = max(int(c.x - reach) - 1, 0), min(int(c.x + reach) + 2, w)
    y0, y1 = max(int(c.y - reach) - 1, 0), min(int(c.y + reach) + 2, h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx, dy = xx - c.x, yy - c.y
    co, si = math.cos(roll), math.sin(roll)
    u, v = dx * co + dy * si, -dx * si + dy * co  # eye-line frame
    d = np.sqrt((u / r) ** 2 + (v / (r * SQUASH)) ** 2)
    t = np.clip((d - PLATEAU) / (1 - PLATEAU), 0, 1)
    k = 1 - s * (1 - t * t * (3 - 2 * t))
    sx = np.clip(c.x + dx * k, 0, w - 1)
    sy = np.clip(c.y + dy * k, 0, h - 1)
    # bilinear sample from the whole image (sources stay inside the ellipse, hence inside the window)
    ix, iy = np.minimum(sx.astype(np.int32), w - 2), np.minimum(sy.astype(np.int32), h - 2)
    fx, fy = (sx - ix)[..., None], (sy - iy)[..., None]
    p00, p01 = a[iy, ix], a[iy, ix + 1]
    p10, p11 = a[iy + 1, ix], a[iy + 1, ix + 1]
    out = (p00 * (1 - fx) + p01 * fx) * (1 - fy) + (p10 * (1 - fx) + p11 * fx) * fy
    a[y0:y1, x0:x1] = out


def _dot(a: np.ndarray, x: float, y: float, r: float, strength: float) -> None:
    """Soft white disc blended into a in place (anti-aliased edge one pixel wide, plus a faint glow).
    Fades out over bright pixels so that on a squinting eye it doesn't land on the eyelid as a white blob."""
    h, w, _ = a.shape
    under = a[int(np.clip(y, 0, h - 1)), int(np.clip(x, 0, w - 1))]
    strength *= float(np.clip((DARK - under @ LUMA) / 60, 0, 1))
    if strength <= 0:
        return
    g = r * 2 + 2
    x0, x1 = max(int(x - g), 0), min(int(x + g) + 2, w)
    y0, y1 = max(int(y - g), 0), min(int(y + g) + 2, h)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = np.hypot(xx - x, yy - y)
    core = np.clip(r - d + 0.5, 0, 1)
    glow = 0.2 * np.exp(-((d / (r * 1.6)) ** 2))
    alpha = (np.maximum(core, glow) * strength)[..., None]
    a[y0:y1, x0:x1] = a[y0:y1, x0:x1] * (1 - alpha) + 255 * alpha


@register
class BigEyes:
    id, label, weight, accessory = "big_eyes", "Big eyes", 10.0, True

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        variant = rng.choice(sorted(STRENGTH))
        lo, hi = STRENGTH[variant]
        a = np.asarray(img.convert("RGB"), dtype=np.float32).copy()
        for face in faces:
            s = rng.uniform(lo, hi)
            r = RADIUS * face.size
            iris = IRIS * face.size / (1 - s)  # iris radius after magnification
            co, si = math.cos(face.roll), math.sin(face.roll)
            lm = face.landmarks
            # roll is only known modulo pi (eyes are sorted by x): flip for upside-down faces so the
            # catch-light stays at the top-left of the iris as seen from the face
            mid_x, mid_y = (lm.left_eye.x + lm.right_eye.x) / 2, (lm.left_eye.y + lm.right_eye.y) / 2
            if (lm.forehead.x - mid_x) * si - (lm.forehead.y - mid_y) * co < 0:
                co, si = -co, -si
            for eye in (lm.left_eye, lm.right_eye):
                _bulge(a, eye, face.roll, r, s)
                if iris >= 4:  # a sparkle on tiny faces is just noise
                    for du, dv, size, strength in SPARKLES:
                        x = eye.x + (du * co - dv * si) * iris
                        y = eye.y + (du * si + dv * co) * iris
                        _dot(a, x, y, size * iris, strength)
        img.paste(Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)))
        return EffectResult(variant=variant, aged_paper=False)
