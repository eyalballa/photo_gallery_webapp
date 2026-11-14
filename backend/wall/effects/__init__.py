"""Importing this package registers every effect. To add one, drop a module here that uses @register."""

from wall.effects import (  # noqa: F401
    accessories,
    big_eyes,
    cake_frame,
    confetti,
    pop_art,
    sketch,
    vintage,
    wanted,
)
from wall.effects.base import EFFECTS, Effect, EffectResult, Face, choose_effect

__all__ = ["EFFECTS", "Effect", "EffectResult", "Face", "choose_effect"]
