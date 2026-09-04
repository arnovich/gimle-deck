"""Compile manifest-driven HTML slide decks to self-contained HTML or PDF."""

from .compiler import DeckCompiler
from .errors import DeckToolError
from .project import DeckProject, SlideSpec, ThemeSpec, load_project
from .web import google_analytics_fragment, inject_google_analytics

__all__ = [
    "DeckCompiler",
    "DeckProject",
    "DeckToolError",
    "SlideSpec",
    "ThemeSpec",
    "google_analytics_fragment",
    "inject_google_analytics",
    "load_project",
]
