"""Golden-set review tool (M2): renders every image in a folder with each effect, plus contact sheets.

    uv run python -m wall.golden golden/input golden/output

Writes <out>/<effect>/<name>.jpg and <out>/sheet_<effect>.jpg. Reviewed by eye, not pixel-compared.
"""

import math
from pathlib import Path
from random import Random

import typer
from PIL import Image, ImageDraw, ImageOps

from wall.config import EffectsConfig
from wall.effects import EFFECTS
from wall.faces import MediaPipeDetector

app = typer.Typer()


def sheet(images: list[tuple[str, Image.Image]], tile: int = 360, cols: int = 5) -> Image.Image:
    rows = math.ceil(len(images) / cols)
    out = Image.new("RGB", (cols * tile, rows * tile), "white")
    draw = ImageDraw.Draw(out)
    for i, (label, im) in enumerate(images):
        im = im.copy()
        im.thumbnail((tile - 6, tile - 22))
        x, y = (i % cols) * tile, (i // cols) * tile
        out.paste(im, (x + 3, y + 18))
        draw.text((x + 4, y + 3), label, fill="black")
    return out


@app.command()
def main(src: Path, dst: Path, show_landmarks: bool = False) -> None:
    cfg = EffectsConfig()
    det = MediaPipeDetector()
    per_effect: dict[str, list[tuple[str, Image.Image]]] = {eid: [] for eid in EFFECTS}
    stats = []
    for path in sorted(src.glob("*.jpg")):
        with Image.open(path) as im:
            base = ImageOps.exif_transpose(im).convert("RGB")
        base.thumbnail((1600, 1600))
        all_faces = det.detect(base)
        faces = [f for f in all_faces if f.box.w >= cfg.min_face_px]
        frontal = [f for f in faces if abs(f.yaw) <= cfg.max_yaw]
        stats.append((path.stem, len(all_faces), len(faces), len(frontal)))
        for eid, effect in EFFECTS.items():
            img = base.copy()
            use = frontal if effect.accessory else faces
            if use:
                effect.apply(img, use, Random(path.stem), cfg)
            if show_landmarks:
                d = ImageDraw.Draw(img)
                for f in faces:
                    for p in f.landmarks.model_dump().values():
                        d.ellipse([p["x"] - 4, p["y"] - 4, p["x"] + 4, p["y"] + 4], fill="lime")
            (dst / eid).mkdir(parents=True, exist_ok=True)
            img.save(dst / eid / f"{path.stem}.jpg", quality=85)
            per_effect[eid].append((f"{path.stem[:22]} f={len(faces)}/{len(all_faces)}", img))
    for eid, imgs in per_effect.items():
        sheet(imgs).save(dst / f"sheet_{eid}.jpg", quality=80)
    total = sum(s[1] for s in stats)
    typer.echo(f"{len(stats)} images, {total} faces detected, {sum(s[2] for s in stats)} ≥ min size, "
               f"{sum(s[3] for s in stats)} frontal; {sum(1 for s in stats if s[1] == 0)} images with no faces")
    for s in stats:
        typer.echo(f"  {s[0]:<28} detected={s[1]} sized={s[2]} frontal={s[3]}")


if __name__ == "__main__":
    app()
