"""Face/effect data structures, the effect registry, effect choice and the landmark-to-anchor geometry."""

import hashlib
import io
import math
from functools import lru_cache
from pathlib import Path
from random import Random
from typing import Protocol

import resvg_py
from PIL import Image
from pydantic import BaseModel

from wall.config import EffectsConfig

ASSETS = Path(__file__).resolve().parents[2] / "assets"


class Point(BaseModel):
    x: float
    y: float


class Rect(BaseModel):
    x: float
    y: float
    w: float
    h: float


class Landmarks(BaseModel):
    left_eye: Point  # leftmost in the image
    right_eye: Point
    nose_tip: Point
    mouth_center: Point
    forehead: Point
    chin: Point


class Face(BaseModel):
    box: Rect  # pixels
    landmarks: Landmarks
    roll: float  # radians, from the eye line; positive = tilted clockwise in the image
    yaw: float  # rough proxy: nose offset from the eye midpoint, in inter-ocular units (0 = frontal)
    size: float  # inter-ocular distance, the unit all effects scale by


class EffectResult(BaseModel):
    variant: str | None
    aged_paper: bool = False  # the frontend uses a yellowed polaroid


class Effect(Protocol):
    id: str
    label: str
    weight: float  # default weight, can be overridden by config
    accessory: bool  # True if it draws on faces (skipped for strongly turned faces)

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        """Draws on `img` in place (same size). `faces` holds only the faces this effect may use."""
        ...


EFFECTS: dict[str, Effect] = {}


def register(cls):
    """Class decorator used in effects/*.py."""
    effect = cls()
    EFFECTS[effect.id] = effect
    return cls


def stable_seed(media_id: str, salt: int) -> int:
    """Python's hash() is salted per process; this one is the same on every run and machine."""
    return int.from_bytes(hashlib.sha256(media_id.encode()).digest()[:8], "big") ^ salt


def choose_effect(
    media_id: str, salt: int, faces: list[Face], weights: dict[str, float], max_yaw: float
) -> tuple[str | None, Random]:
    """Picks one effect per photo, deterministic per (media id, salt). No faces → no effect."""
    rng = Random(stable_seed(media_id, salt))
    if not faces:
        return None, rng
    frontal = any(abs(f.yaw) <= max_yaw for f in faces)
    pool = {
        eid: weights.get(eid, e.weight)
        for eid, e in sorted(EFFECTS.items())
        if weights.get(eid, e.weight) > 0 and (frontal or not e.accessory)
    }
    if not pool:
        return None, rng
    return rng.choices(list(pool), weights=list(pool.values()))[0], rng


# --- geometry ---------------------------------------------------------------------------------------


class Placement(BaseModel):
    """Where an asset goes: `anchor` (fractions of the asset's w/h) lands on `target`."""

    target: Point
    width: float
    angle: float  # radians, same convention as Face.roll
    anchor: Point


def up_vector(face: Face) -> Point:
    """Unit vector pointing from the chin towards the top of the head, perpendicular to the eye line."""
    return Point(x=math.sin(face.roll), y=-math.cos(face.roll))


def lerp(a: Point, b: Point, t: float) -> Point:
    return Point(x=a.x + (b.x - a.x) * t, y=a.y + (b.y - a.y) * t)


def paste_position(p: Placement, asset_w: float, asset_h: float) -> tuple[Point, float, float]:
    """Top-left corner for pasting the asset after it is scaled to p.width and rotated by p.angle
    (PIL rotate with expand=True), so that its anchor lands on p.target. Returns (corner, rot_w, rot_h)."""
    scale = p.width / asset_w
    w, h = asset_w * scale, asset_h * scale
    c, s = math.cos(p.angle), math.sin(p.angle)
    rot_w, rot_h = abs(w * c) + abs(h * s), abs(w * s) + abs(h * c)
    # anchor offset from the asset's centre, rotated clockwise by angle (image y points down)
    ox, oy = (p.anchor.x - 0.5) * w, (p.anchor.y - 0.5) * h
    rx, ry = ox * c - oy * s, ox * s + oy * c
    return Point(x=p.target.x - rx - rot_w / 2, y=p.target.y - ry - rot_h / 2), rot_w, rot_h


@lru_cache(maxsize=64)
def render_svg(path: Path, width: int) -> Image.Image:
    png = resvg_py.svg_to_bytes(svg_path=str(path), width=max(width, 1))
    return Image.open(io.BytesIO(png)).convert("RGBA")


def svg_size(path: Path) -> tuple[float, float]:
    """Width and height from the SVG's viewBox."""
    import re

    m = re.search(r'viewBox="\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)"', path.read_text())
    if not m:
        raise ValueError(f"{path} has no viewBox")
    return float(m.group(1)), float(m.group(2))


def paste_asset(img: Image.Image, path: Path, p: Placement) -> None:
    aw, ah = svg_size(path)
    asset = render_svg(path, round(p.width))
    rotated = asset.rotate(-math.degrees(p.angle), resample=Image.BICUBIC, expand=True)
    corner, rot_w, rot_h = paste_position(p, aw, ah)
    # PIL's expanded canvas can differ from the exact size by a pixel; re-centre on the real one
    x = corner.x + (rot_w - rotated.width) / 2
    y = corner.y + (rot_h - rotated.height) / 2
    img.paste(rotated, (round(x), round(y)), rotated)


def variants(effect_id: str) -> list[Path]:
    return sorted((ASSETS / effect_id).glob("*.svg"))
