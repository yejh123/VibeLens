"""Friction analysis services — detection, persistence, and digest formatting."""

from vibelens.services.friction.analysis import analyze_friction
from vibelens.services.friction.digest import format_batch_digest, select_limits
from vibelens.services.friction.store import FrictionStore

__all__ = [
    "FrictionStore",
    "analyze_friction",
    "format_batch_digest",
    "select_limits",
]
