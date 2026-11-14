"""Per-photo pipeline: load → EXIF-rotate → resize → detect faces → pick effect → apply → save."""

import logging
from pathlib import Path

from PIL import Image, ImageOps

from wall.config import EffectsConfig
from wall.effects import EFFECTS, choose_effect
from wall.faces import FaceDetector
from wall.store import ProcessedFields

log = logging.getLogger(__name__)
MAX_PX = 1600


def process_one(
    photo_id: str, original: Path, out: Path, detector: FaceDetector, cfg: EffectsConfig, salt: int = 0
) -> ProcessedFields:
    with Image.open(original) as im:
        img = ImageOps.exif_transpose(im).convert("RGB")
    img.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)

    faces = [f for f in detector.detect(img) if f.box.w >= cfg.min_face_px]
    effect_id, rng = choose_effect(photo_id, salt, faces, cfg.weights, cfg.max_yaw)
    variant, aged, error = None, False, None
    if effect_id:
        if EFFECTS[effect_id].accessory:
            faces = [f for f in faces if abs(f.yaw) <= cfg.max_yaw]
        canvas = img.copy()
        try:
            result = EFFECTS[effect_id].apply(canvas, faces, rng, cfg)
            img, variant, aged = canvas, result.variant, result.aged_paper
        except Exception as e:  # an effect bug must not cost us the photo
            log.exception("effect %s failed on %s", effect_id, photo_id)
            effect_id, error = None, f"effect failed: {e}"

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return ProcessedFields(
        status="ready", width=img.width, height=img.height, faces=len(faces),
        effect=effect_id, variant=variant, aged_paper=aged, error=error,
    )
