"""Glasses, circus glasses, mustache and party hat: SVG assets anchored to face landmarks."""

from random import Random

from PIL import Image

from wall.config import EffectsConfig
from wall.effects.base import (
    EffectResult,
    Face,
    Placement,
    Point,
    lerp,
    paste_asset,
    register,
    up_vector,
    variants,
)


class _Accessory:
    id = ""
    label = ""
    weight = 25.0
    accessory = True

    def placement(self, face: Face) -> Placement:
        raise NotImplementedError

    def apply(self, img: Image.Image, faces: list[Face], rng: Random, cfg: EffectsConfig) -> EffectResult:
        path = rng.choice(variants(self.id))
        for face in faces:
            paste_asset(img, path, self.placement(face))
        return EffectResult(variant=path.stem)


@register
class Glasses(_Accessory):
    id, label = "glasses", "Glasses"

    def placement(self, face: Face) -> Placement:
        lm = face.landmarks
        # assets put the bridge at the centre, lens centres at 0.29/0.71 of the width
        return Placement(target=lerp(lm.left_eye, lm.right_eye, 0.5), width=2.4 * face.size, angle=face.roll,
                         anchor=Point(x=0.5, y=0.5))


@register
class CircusGlasses(_Accessory):
    id, label = "circus_glasses", "Circus glasses"

    def placement(self, face: Face) -> Placement:
        lm = face.landmarks
        # oversized novelty glasses: assets are 400x260 with the eyes at (150, 100) and (250, 100), i.e. one
        # inter-ocular distance = 100 units, so the width is 4x; the lenses sit further out than the eyes
        return Placement(target=lerp(lm.left_eye, lm.right_eye, 0.5), width=4.0 * face.size, angle=face.roll,
                         anchor=Point(x=0.5, y=100 / 260))


@register
class Mustache(_Accessory):
    id, label = "mustache", "Mustache"

    def placement(self, face: Face) -> Placement:
        lm = face.landmarks
        return Placement(target=lerp(lm.nose_tip, lm.mouth_center, 0.3), width=1.5 * face.size, angle=face.roll,
                         anchor=Point(x=0.5, y=0.3))


@register
class PartyHat(_Accessory):
    id, label = "party_hat", "Party hat"

    def placement(self, face: Face) -> Placement:
        up = up_vector(face)
        f = face.landmarks.forehead
        base = Point(x=f.x + up.x * 0.45 * face.size, y=f.y + up.y * 0.45 * face.size)
        # the brim centre (bottom middle of the asset) sits on the crown, about half an eye distance above landmark 10
        return Placement(target=base, width=2.2 * face.size, angle=face.roll, anchor=Point(x=0.5, y=0.94))
