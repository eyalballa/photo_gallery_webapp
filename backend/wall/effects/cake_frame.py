"""Birthday-cake frame: dripping frosting on top, a sponge cake with lit candles and "Happy Birthday" at the bottom."""

import io
import re
from functools import lru_cache
from random import Random

import resvg_py
from PIL import Image, ImageDraw, ImageFont, ImageOps

from wall.config import EffectsConfig
from wall.effects.base import ASSETS, EffectResult, Face, register, svg_size

DIR = ASSETS / "cake_frame"
TOKEN = re.compile(r"\b(FROST_LO|FROST_HI|FROST|SPONGE_LO|SPONGE|CREAM|CANDLE|STRIPE)\b")

# frosting, its highlight and shadow, the sponge, its crumb/shadow, the filling, and the outline colour of the text
VARIANTS: dict[str, dict[str, str]] = {
    "strawberry": {"FROST": "#ff8fb8", "FROST_HI": "#ffd3e4", "FROST_LO": "#d6457d", "SPONGE": "#f7d39a",
                   "SPONGE_LO": "#d9a55f", "CREAM": "#ff6b9a", "INK": "#a3174f"},
    "chocolate": {"FROST": "#7a4528", "FROST_HI": "#a8714b", "FROST_LO": "#45230f", "SPONGE": "#9c6440",
                  "SPONGE_LO": "#6b3d22", "CREAM": "#f6e7cc", "INK": "#3b1a08"},
    "vanilla": {"FROST": "#fff3d6", "FROST_HI": "#ffffff", "FROST_LO": "#d8b27a", "SPONGE": "#f3c27a",
                "SPONGE_LO": "#c98f45", "CREAM": "#ff8fb0", "INK": "#b5541c"},
    "blueberry": {"FROST": "#a5c8ff", "FROST_HI": "#e3eeff", "FROST_LO": "#4f7fd6", "SPONGE": "#f7d39a",
                  "SPONGE_LO": "#d9a55f", "CREAM": "#7b5cd6", "INK": "#23408f"},
}
CANDLES = [("#ff6b6b", "#ffffff"), ("#4dabf7", "#ffffff"), ("#63e6be", "#ffffff"), ("#ffd23f", "#ff6b6b"),
           ("#9775fa", "#ffd23f"), ("#ffffff", "#ff6b9a")]
LETTERS = ["#ffffff", "#ffe066", "#ffffff", "#c3fae8"]

TOP = 0.12  # frosting tile height per `ref` (the image height for landscape); the solid band is ~45% of it
BAND = 0.15  # cake band height
CANDLE = 0.1  # candle height (they stand on the band, so the bottom frame is ~23% at the candles)


@lru_cache(maxsize=64)
def _render(name: str, width: int, colours: tuple[tuple[str, str], ...] = ()) -> Image.Image:
    """An asset rendered at `width` px, with its colour tokens replaced by `colours` ((token, colour) pairs)."""
    svg = TOKEN.sub(lambda m: dict(colours).get(m.group(1), m.group(1)), (DIR / name).read_text())
    png = resvg_py.svg_to_bytes(svg_string=svg, width=max(width, 1))
    return Image.open(io.BytesIO(png)).convert("RGBA")


def _strip(name: str, width: int, height: float, colours: tuple) -> tuple[Image.Image, int]:
    """The tile and how many of them span `width`: a whole number of tiles, each about `height` tall."""
    aw, ah = svg_size(DIR / name)
    n = max(1, round(width / (height * aw / ah)))
    return _render(name, -(-width // n) + 1, colours), n


def _tile(img: Image.Image, tile: Image.Image, n: int, y: int, rng: Random) -> None:
    """Repeats a tile across the full width, some of them mirrored so the pattern doesn't look stamped
    (tile edges are symmetric, so mirrored tiles still join up)."""
    flipped = ImageOps.mirror(tile)
    for i in range(n):
        t = flipped if rng.random() < 0.5 else tile
        img.paste(t, (round(i * img.width / n), y), t)


def _layout(faces: list[Face], w: int, h: int, top: float, band: float) -> tuple[float, float]:
    """Scale and vertical offset for the photo so no face's eyes-to-mouth sit under the frame (1, 0 if it already fits).
    A shrunken photo leaves gaps that must stay hidden under the solid frosting and the cake band."""
    lo = min(f.box.y + 0.2 * f.box.h for f in faces)
    hi = max(f.box.y + 0.85 * f.box.h for f in faces)
    min_y, max_y = top * 0.5, h - band
    if lo >= min_y and hi <= max_y:
        return 1.0, 0.0
    for s in (0.96, 0.92, 0.88, 0.84, 0.8, 0.76):
        a = max(h - band * 0.9 - s * h, min_y - s * lo)  # gap below hidden; faces below the frosting
        b = min(top * 0.45, max_y - s * hi)  # gap above hidden; faces above the cake
        if a <= b:
            return s, min(max(h * (1 - s) / 2, a), b)
    return 1.0, 0.0


def _font(text: str, size: int, max_w: float, stroke: int) -> ImageFont.FreeTypeFont:
    while size > 10:
        font = ImageFont.load_default(size=size)
        if font.getlength(text) + 2 * stroke <= max_w:
            return font
        size = int(size * 0.92)
    return ImageFont.load_default(size=size)


@register
class CakeFrame:
    id, label, weight, accessory = "cake_frame", "Cake frame", 10.0, False

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        w, h = img.size
        variant = rng.choice(sorted(VARIANTS))
        pal = VARIANTS[variant]
        colours = tuple(pal.items())
        # sized by the height for landscape; portraits use a smaller unit so the frame doesn't swallow the width
        ref = min(h, 0.82 * (w * h) ** 0.5)
        drip, n_drip = _strip("drip.svg", w, TOP * ref, colours)
        cake, n_cake = _strip("cake.svg", w, BAND * ref, colours)
        top, band, candle_h = drip.height, cake.height, CANDLE * ref
        band_y = h - band

        s, oy = _layout(faces, w, h, top, band)
        if s < 1:  # shrink the photo onto a frosting-coloured board; the side gaps become piped borders
            photo = img.resize((round(w * s), round(h * s)), Image.LANCZOS)
            img.paste(Image.new("RGB", (w, h), pal["FROST"]))
            img.paste(photo, ((w - photo.width) // 2, round(oy)))

        # piped beads down both sides (on the photo edge, or along the border when the photo was shrunk)
        bead_d = max(8, round(0.035 * ref))
        side = (w - round(w * s)) // 2 if s < 1 else 0
        bead = _render("bead.svg", bead_d, colours)
        y0, y1 = top * 0.4, band_y - bead_d * 0.3
        n = max(1, int((y1 - y0) / (bead_d * 0.82)))
        for i in range(n + 1):
            y = round(y0 + i * (y1 - y0 - bead_d) / n)
            img.paste(bead, (max(side - bead_d // 2, -bead_d // 3), y), bead)
            img.paste(bead, (min(w - side - bead_d // 2, w - bead_d + bead_d // 3), y), bead)

        _tile(img, drip, n_drip, 0, rng)

        # candles standing on the cake, skipping any that would stand in front of a face
        boxes = [(side + f.box.x * s, oy + f.box.y * s, side + (f.box.x + f.box.w) * s, oy + (f.box.y + f.box.h) * s)
                 for f in faces]
        cw = candle_h * 40 / 140
        count = max(3, min(9, round(w / (candle_h * 1.5))))
        for i in range(count):
            cx = w * (i + 0.5) / count + rng.uniform(-0.15, 0.15) * w / count
            cy = band_y + band * 0.12 - candle_h * rng.uniform(0.95, 1.05)
            if any(x0 - cw < cx < x1 + cw and cy < y1 for x0, y0_, x1, y1 in boxes):
                continue
            body, stripe = rng.choice(CANDLES)
            c = _render("candle.svg", round(cw), (("CANDLE", body), ("STRIPE", stripe)))
            img.paste(c, (round(cx - c.width / 2), round(cy)), c)

        _tile(img, cake, n_cake, band_y, rng)

        # the greeting, centred on the sponge, in alternating bright letters with a thick outline
        text = f"Happy Birthday, {cfg.honoree.strip()}!" if cfg.honoree and cfg.honoree.strip() else "Happy Birthday!"
        stroke = max(2, round(band * 0.045))
        font = _font(text, round(band * 0.42), w * 0.9, stroke)
        draw = ImageDraw.Draw(img)
        cy = band_y + band * 0.56
        x = (w - font.getlength(text)) / 2
        shadow = max(2, round(band * 0.025))
        draw.text((x + shadow, cy + shadow), text, font=font, anchor="lm", fill=pal["INK"], stroke_width=stroke,
                  stroke_fill=pal["INK"])
        k = 0
        for ch in text:
            fill = LETTERS[k % len(LETTERS)] if ch.strip() else None
            if fill:
                draw.text((x, cy), ch, font=font, anchor="lm", fill=fill, stroke_width=stroke, stroke_fill=pal["INK"])
                k += 1
            x += font.getlength(ch)
        return EffectResult(variant=variant, aged_paper=False)
