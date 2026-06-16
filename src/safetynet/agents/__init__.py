"""Generative agent stubs.

These are dependency-free placeholders behind a common :class:`Agent` interface. Swap each for
a real LLM / diffusion / video model without touching the gates, breaker, or pipeline.
"""

from .base import Agent
from .image_agent import ImageAgent
from .script_agent import ScriptAgent
from .video_agent import VideoAgent

__all__ = ["Agent", "ScriptAgent", "ImageAgent", "VideoAgent"]
