"""Importing this package registers every effect. To add one, drop a module here that uses @register."""

from wall.effects import accessories, vintage  # noqa: F401
from wall.effects.base import EFFECTS, Effect, EffectResult, Face, choose_effect

__all__ = ["EFFECTS", "Effect", "EffectResult", "Face", "choose_effect"]
