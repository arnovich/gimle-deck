"""Assemble a configured deck project into one self-contained HTML document."""

import base64
import mimetypes
from pathlib import Path
import re
import sys
from typing import FrozenSet, Iterable, List, Optional, Tuple

from .errors import DeckToolError
from .project import APPENDIX_DIVIDER, DeckProject, SlideSpec

PLACEHOLDER = re.compile(r"\{\{(include|asset):([^}]+)\}\}")
SOURCE_PAGE_MARKER = re.compile(r'class=["\'][^"\']*\bnum\b')
CLASS_ATTRIBUTE = re.compile(r'\bclass\s*=\s*(["\'])(.*?)\1', flags=re.S)
LOCAL_URL = re.compile(r"url\((['\"]?)([^)'\"]+)\1\)")


def top_level_sections(markup: str) -> List[Tuple[int, int]]:
    """Return byte spans of the outermost section elements."""
    spans: List[Tuple[int, int]] = []
    depth = 0
    start: Optional[int] = None
    for match in re.finditer(r"</?section\b", markup):
        if match.group(0).startswith("</"):
            depth -= 1
            if depth < 0:
                raise DeckToolError("unbalanced <section> tags")
            if depth == 0 and start is not None:
                spans.append((start, markup.index(">", match.start()) + 1))
                start = None
        else:
            if depth == 0:
                start = match.start()
            depth += 1
    if depth != 0:
        raise DeckToolError("unbalanced <section> tags")
    return spans


def number_slides(slides: Iterable[str]) -> List[str]:
    """Insert contiguous page markers, leaving the first slide unnumbered."""
    numbered = []
    for index, markup in enumerate(slides, start=1):
        if SOURCE_PAGE_MARKER.search(markup):
            raise DeckToolError(
                "page marker present before numbering; slide sources must not "
                "own page numbers"
            )
        if index == 1:
            numbered.append(markup)
            continue
        spans = top_level_sections(markup)
        if len(spans) != 1:
            raise DeckToolError("numbering expects exactly one outer slide section")
        close_start = markup.rfind("</section", spans[0][0], spans[0][1])
        if close_start < 0:
            raise DeckToolError("cannot find the outer slide closing tag")
        marker = f'<div class="num">{index:02d}</div>'
        numbered.append(
            markup[:close_start].rstrip() + f"\n  {marker}\n" + markup[close_start:]
        )
    return numbered


class DeckCompiler:
    """Compile one validated deck project."""

    def __init__(self, project: DeckProject):
        self.project = project

    def _asset_path(self, name: str, label: str) -> Path:
        path = (self.project.asset_dir / name).resolve()
        if (
            self.project.asset_dir != path
            and self.project.asset_dir not in path.parents
        ):
            raise DeckToolError(
                f"asset path for {label} must stay inside "
                f"{self.project.asset_dir}: {name}"
            )
        if not path.is_file():
            raise DeckToolError(f"{label} wants missing asset {name}")
        return path

    def resolve_assets(self, markup: str, label: str) -> str:
        """Resolve inline-text and data-URI asset placeholders."""

        def substitute(match: re.Match) -> str:
            kind, name = match.group(1), match.group(2).strip()
            path = self._asset_path(name, label)
            if kind == "include":
                return path.read_text(encoding="utf-8").strip()
            mime = mimetypes.guess_type(name)[0]
            if not mime:
                raise DeckToolError(
                    f"cannot determine media type of {name} for {label}"
                )
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}"

        return PLACEHOLDER.sub(substitute, markup)

    def embed_local_urls(self, html: str, base_dir: Optional[Path] = None) -> str:
        """Embed project-relative CSS URLs so an output is self-contained."""

        base_dir = base_dir or self.project.root

        def substitute(match: re.Match) -> str:
            quote, name = match.group(1), match.group(2).strip()
            if name.startswith(("data:", "http:", "https:", "#", "/")):
                return match.group(0)
            path = (base_dir / name).resolve()
            if not path.is_file() and base_dir != self.project.root:
                # Existing projects may have written CSS for the eventual deck
                # document rather than for the stylesheet's source directory.
                path = (self.project.root / name).resolve()
            if self.project.root != path and self.project.root not in path.parents:
                raise DeckToolError(
                    f"local URL must stay inside {self.project.root}: {name}"
                )
            if not path.is_file():
                raise DeckToolError(f"local URL points at a missing file: {name}")
            mime = mimetypes.guess_type(path.name)[0]
            if not mime:
                raise DeckToolError(f"cannot determine media type of local URL: {name}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"url({quote}data:{mime};base64,{encoded}{quote})"

        return LOCAL_URL.sub(substitute, html)

    def read_slide(self, slug: str) -> str:
        """Read and validate one authored slide."""
        path = self.project.slide_path(slug)
        markup = self.resolve_assets(path.read_text(encoding="utf-8"), slug)
        if SOURCE_PAGE_MARKER.search(markup):
            raise DeckToolError(
                f"{path} contains a .num page marker; the compiler owns numbering"
            )
        spans = top_level_sections(markup)
        if len(spans) != 1:
            raise DeckToolError(
                f"{path} holds {len(spans)} top-level section elements; expected 1"
            )
        start, end = spans[0]
        opening_tag = markup[start : markup.index(">", start, end) + 1]
        class_attribute = CLASS_ATTRIBUTE.search(opening_tag)
        classes = class_attribute.group(2).split() if class_attribute else []
        if "slide" not in classes:
            raise DeckToolError(f"{path} outer section must include the slide class")
        return markup.strip()

    def appendix_divider(self) -> str:
        """Generate the structural divider for selected appendix slides."""
        return (
            '<section class="slide appendix-divider">\n'
            f"  <h2>{self.project.appendix_title}</h2>\n"
            '  <div class="rule"></div>\n'
            "</section>"
        )

    @staticmethod
    def deck_tag(variants: Optional[FrozenSet[str]]) -> str:
        """Return an internal review badge for a slide's variant membership."""
        if variants is None:
            return '<div class="deck-tag every">EVERY DECK</div>'
        label = " · ".join(sorted(name.upper() for name in variants))
        if len(variants) == 1:
            label += " ONLY"
        return f'<div class="deck-tag">{label}</div>'

    def slide_reference(self, slug: str) -> str:
        """Return an internal reference to the authored slide source."""
        relative = self.project.slide_path(slug).relative_to(self.project.root)
        return f'<div class="slide-ref">{relative.as_posix()}</div>'

    def stamp(self, markup: str, variants: Optional[FrozenSet[str]], slug: str) -> str:
        """Add internal review furniture to one slide."""
        spans = top_level_sections(markup)
        open_end = markup.index(">", spans[0][0]) + 1
        furniture = f"{self.deck_tag(variants)}\n  {self.slide_reference(slug)}"
        return markup[:open_end] + "\n  " + furniture + markup[open_end:]

    def report(
        self,
        variant: str,
        kept: List[str],
        dropped: List[Tuple[str, FrozenSet[str]]],
    ) -> None:
        """Report variant selection to standard error."""
        print(f"deck {variant!r} — {len(kept)} slides", file=sys.stderr)
        for slug, variants in dropped:
            print(
                f"  dropped: {slug}  [{' '.join(sorted(variants))}]",
                file=sys.stderr,
            )

    def build(
        self,
        variant: str,
        *,
        theme: Optional[str] = None,
        drop: Iterable[str] = (),
        css: Optional[str] = None,
        tags: bool = False,
        quiet: bool = False,
        embed_local_urls: bool = True,
    ) -> Tuple[str, List[str]]:
        """Build selected slides into the project's HTML template."""
        selected_theme = self.project.theme(theme)
        kept, dropped = self.project.select(variant)
        if not quiet:
            self.report(variant, kept, dropped)

        dropped_slugs = set(drop)
        if APPENDIX_DIVIDER in dropped_slugs:
            raise DeckToolError(
                "the generated appendix divider cannot be dropped directly"
            )
        kept = [slug for slug in kept if slug not in dropped_slugs]
        if kept and kept[-1] == APPENDIX_DIVIDER:
            kept.pop()
        if not kept:
            raise DeckToolError(f"variant {variant!r} is empty after applying cuts")

        slides = [
            self.appendix_divider()
            if slug == APPENDIX_DIVIDER
            else self.read_slide(slug)
            for slug in kept
        ]
        if tags:
            membership = {
                slide.slug: slide.variants for slide in self.project.active_slides
            }
            slides = [
                markup
                if slug == APPENDIX_DIVIDER
                else self.stamp(markup, membership[slug], slug)
                for markup, slug in zip(slides, kept)
            ]
        slides = number_slides(slides)

        if css is None:
            css = selected_theme.stylesheet_path.read_text(encoding="utf-8")
        css = self.resolve_assets(css, selected_theme.stylesheet_path.name)
        if embed_local_urls:
            css = self.embed_local_urls(css, selected_theme.stylesheet_path.parent)
        template = selected_theme.template_path.read_text(encoding="utf-8")
        html = (
            template.replace("{{title}}", self.project.title)
            .replace("{{css}}", css)
            .replace("{{slides}}", "\n\n".join(slides))
        )
        unresolved = PLACEHOLDER.search(html)
        if unresolved:
            raise DeckToolError(
                f"unresolved placeholder {unresolved.group(0)} in assembled deck"
            )
        if embed_local_urls:
            html = self.embed_local_urls(html)
        return html, kept
