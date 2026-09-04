"""Load and validate a manifest-driven deck project."""

from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import sys
from typing import Any, FrozenSet, List, Mapping, Optional, Tuple

tomllib = importlib.import_module("tomllib" if sys.version_info >= (3, 11) else "tomli")

from .errors import DeckToolError

ALL_VARIANT = "all"
MAIN = "main"
APPENDIX = "appendix"
APPENDIX_DIVIDER = "__generated_appendix_divider__"
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
GOOGLE_ANALYTICS_ID = re.compile(r"^G-[A-Z0-9]+$")


def normalize_google_analytics_id(value: Any) -> Optional[str]:
    """Validate an optional GA4 measurement ID from project configuration."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise DeckToolError("web.google_analytics_id must be a string")
    measurement_id = value.strip()
    if not measurement_id:
        return None
    if not GOOGLE_ANALYTICS_ID.fullmatch(measurement_id):
        raise DeckToolError(
            "web.google_analytics_id must be a GA4 measurement ID such as " "G-ABC123"
        )
    return measurement_id


@dataclass(frozen=True)
class SlideSpec:
    """One authored slide and its selection rules."""

    slug: str
    variants: Optional[FrozenSet[str]] = None
    placement: str = MAIN
    archived: bool = False


@dataclass(frozen=True)
class ThemeSpec:
    """One named presentation theme owned by a deck project."""

    name: str
    template_path: Path
    stylesheet_path: Path


@dataclass(frozen=True)
class DeckProject:
    """Resolved project configuration and its slide manifest."""

    root: Path
    config_path: Path
    title: str
    default_variant: str
    variants: Mapping[str, str]
    slides: Tuple[SlideSpec, ...]
    slide_dir: Path
    notes_dir: Path
    asset_dir: Path
    themes: Mapping[str, ThemeSpec]
    default_theme: str
    require_notes: bool = True
    appendix_title: str = "Appendix"
    output_basename: str = "deck"
    page_width_points: float = 960.0
    page_height_points: float = 540.0
    allowed_font_prefixes: Tuple[str, ...] = ()
    google_analytics_id: Optional[str] = None

    @property
    def archived_slugs(self) -> Tuple[str, ...]:
        """Archived source slugs in declaration order."""
        return tuple(slide.slug for slide in self.slides if slide.archived)

    @property
    def active_slides(self) -> Tuple[SlideSpec, ...]:
        """Active slides in reading order."""
        return tuple(slide for slide in self.slides if not slide.archived)

    @property
    def template_path(self) -> Path:
        """Default theme template path retained for compatibility."""
        return self.theme().template_path

    @property
    def stylesheet_path(self) -> Path:
        """Default theme stylesheet path retained for compatibility."""
        return self.theme().stylesheet_path

    def slide_path(self, slug: str) -> Path:
        """Return the source path for a slide slug."""
        return self.slide_dir / f"{slug}.html"

    def notes_path(self, slug: str) -> Path:
        """Return the editorial-notes path for a slide slug."""
        return self.notes_dir / f"{slug}.md"

    def variant_names(self) -> Tuple[str, ...]:
        """Legal named variants, including the comparison build."""
        return tuple(sorted(self.variants)) + (ALL_VARIANT,)

    def theme_names(self) -> Tuple[str, ...]:
        """Declared theme names in stable display order."""
        return tuple(sorted(self.themes))

    def theme(self, name: Optional[str] = None) -> ThemeSpec:
        """Resolve a named theme, falling back to the project's default."""
        selected = self.default_theme if name is None else name
        try:
            return self.themes[selected]
        except KeyError as error:
            names = ", ".join(self.theme_names())
            raise DeckToolError(
                f"unknown theme {selected!r}; declared themes are {names}"
            ) from error

    def validate(self) -> None:
        """Validate the manifest against its project files."""
        if self.default_variant not in self.variants:
            raise DeckToolError(
                f"default variant {self.default_variant!r} is not declared"
            )
        if self.default_theme not in self.themes:
            raise DeckToolError(f"default theme {self.default_theme!r} is not declared")

        seen = set()
        for slide in self.slides:
            if slide.slug == APPENDIX_DIVIDER:
                raise DeckToolError(
                    f"{APPENDIX_DIVIDER!r} is reserved for generated structure"
                )
            if slide.slug in seen:
                raise DeckToolError(f"slide {slide.slug!r} is declared twice")
            seen.add(slide.slug)
            if slide.placement not in {MAIN, APPENDIX}:
                raise DeckToolError(
                    f"unknown placement {slide.placement!r} on {slide.slug!r}"
                )
            if slide.archived and slide.variants is not None:
                raise DeckToolError(
                    f"archived slide {slide.slug!r} cannot declare variants"
                )
            if slide.archived and slide.placement != MAIN:
                raise DeckToolError(
                    f"archived slide {slide.slug!r} cannot use appendix placement"
                )
            if slide.variants is not None:
                if not slide.variants:
                    raise DeckToolError(
                        f"slide {slide.slug!r} has an empty variant list"
                    )
                unknown = sorted(slide.variants - set(self.variants))
                if unknown:
                    raise DeckToolError(
                        f"slide {slide.slug!r} uses unknown variants: "
                        f"{', '.join(unknown)}"
                    )
            if not self.slide_path(slide.slug).is_file():
                raise DeckToolError(
                    f"slide {slide.slug!r} has no source at "
                    f"{self.slide_path(slide.slug)}"
                )

        on_disk = {path.stem for path in self.slide_dir.glob("*.html")}
        orphans = sorted(on_disk - seen)
        if orphans:
            raise DeckToolError(
                "slide sources are not declared active or archived: "
                + ", ".join(orphans)
            )

        if self.require_notes:
            missing_notes = sorted(
                slide.slug
                for slide in self.slides
                if not self.notes_path(slide.slug).is_file()
            )
            if missing_notes:
                raise DeckToolError(
                    "slides have no matching notes file: " + ", ".join(missing_notes)
                )

        commented = sorted(
            slide.slug
            for slide in self.slides
            if "<!--" in self.slide_path(slide.slug).read_text(encoding="utf-8")
            or "-->" in self.slide_path(slide.slug).read_text(encoding="utf-8")
        )
        if commented:
            raise DeckToolError(
                "slide markup contains HTML comments: " + ", ".join(commented)
            )

        for theme in self.themes.values():
            if not theme.template_path.is_file():
                raise DeckToolError(
                    f"theme {theme.name!r} template does not exist: "
                    f"{theme.template_path}"
                )
            template = theme.template_path.read_text(encoding="utf-8")
            for token in ("{{css}}", "{{slides}}"):
                if token not in template:
                    raise DeckToolError(
                        f"theme {theme.name!r} template {theme.template_path} "
                        f"has no {token} placeholder"
                    )
            if not theme.stylesheet_path.is_file():
                raise DeckToolError(
                    f"theme {theme.name!r} stylesheet does not exist: "
                    f"{theme.stylesheet_path}"
                )

    def select(
        self, variant: str
    ) -> Tuple[List[str], List[Tuple[str, FrozenSet[str]]]]:
        """Select active slide slugs for a variant."""
        if variant != ALL_VARIANT and variant not in self.variants:
            names = ", ".join(self.variant_names())
            raise DeckToolError(
                f"unknown variant {variant!r}; declared variants are {names}"
            )
        self.validate()

        main: List[str] = []
        appendix: List[str] = []
        dropped: List[Tuple[str, FrozenSet[str]]] = []
        for slide in self.active_slides:
            if (
                variant == ALL_VARIANT
                or slide.variants is None
                or variant in slide.variants
            ):
                target = appendix if slide.placement == APPENDIX else main
                target.append(slide.slug)
            else:
                dropped.append((slide.slug, slide.variants))

        kept = main
        if appendix:
            kept += [APPENDIX_DIVIDER, *appendix]
        if not kept:
            raise DeckToolError(f"variant {variant!r} selects no slides")
        return kept, dropped


def _string(table: Mapping[str, Any], key: str, default: Optional[str] = None) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise DeckToolError(f"deck.{key} must be a non-empty string")
    return value


def _project_path(root: Path, value: str, label: str) -> Path:
    path = (root / value).resolve()
    if root != path and root not in path.parents:
        raise DeckToolError(f"{label} must stay inside the project root: {value}")
    return path


def _positive_number(table: Mapping[str, Any], key: str, default: float) -> float:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise DeckToolError(f"render.{key} must be a positive number")
    return float(value)


def _theme_string(table: Mapping[str, Any], key: str, name: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DeckToolError(f"themes.{name}.{key} must be a non-empty string")
    return value


def _load_themes(
    root: Path,
    deck: Mapping[str, Any],
    raw_themes: Any,
    default_theme: str,
) -> Mapping[str, ThemeSpec]:
    """Load named themes or adapt the original template/style pair."""
    has_legacy_theme = "template" in deck or "stylesheet" in deck
    if raw_themes is None:
        template = _string(deck, "template")
        stylesheet = _string(deck, "stylesheet")
        return {
            default_theme: ThemeSpec(
                name=default_theme,
                template_path=_project_path(root, template, "deck.template"),
                stylesheet_path=_project_path(root, stylesheet, "deck.stylesheet"),
            )
        }

    if not isinstance(raw_themes, dict) or not raw_themes:
        raise DeckToolError("themes must be a non-empty table")
    if has_legacy_theme:
        raise DeckToolError(
            "declare themes with [themes.<name>] or deck.template and "
            "deck.stylesheet, not both"
        )

    themes = {}
    for name, raw_theme in raw_themes.items():
        if not isinstance(name, str) or not SLUG.fullmatch(name):
            raise DeckToolError(
                f"invalid theme name {name!r}; use lowercase letters, numbers, "
                "underscores, or hyphens"
            )
        if not isinstance(raw_theme, dict):
            raise DeckToolError(f"themes.{name} must be a table")
        themes[name] = ThemeSpec(
            name=name,
            template_path=_project_path(
                root,
                _theme_string(raw_theme, "template", name),
                f"themes.{name}.template",
            ),
            stylesheet_path=_project_path(
                root,
                _theme_string(raw_theme, "stylesheet", name),
                f"themes.{name}.stylesheet",
            ),
        )
    return themes


def _load_slides(raw_slides: Any) -> Tuple[SlideSpec, ...]:
    if not isinstance(raw_slides, list) or not raw_slides:
        raise DeckToolError("deck.toml must declare at least one [[slides]] entry")

    slides = []
    for index, raw in enumerate(raw_slides, start=1):
        if not isinstance(raw, dict):
            raise DeckToolError(f"slides entry {index} must be a table")
        slug = raw.get("slug")
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            raise DeckToolError(
                f"slides entry {index} has invalid slug {slug!r}; use lowercase "
                "letters, numbers, underscores, or hyphens"
            )
        raw_variants = raw.get("variants")
        selected_variants: Optional[FrozenSet[str]] = None
        if raw_variants is not None:
            if not isinstance(raw_variants, list) or not all(
                isinstance(name, str) for name in raw_variants
            ):
                raise DeckToolError(f"slide {slug!r} variants must be a string list")
            selected_variants = frozenset(raw_variants)
        placement = raw.get("placement", MAIN)
        if not isinstance(placement, str):
            raise DeckToolError(f"slide {slug!r} placement must be a string")
        archived = raw.get("archived", False)
        if not isinstance(archived, bool):
            raise DeckToolError(f"slide {slug!r} archived must be true or false")
        slides.append(
            SlideSpec(
                slug=slug,
                variants=selected_variants,
                placement=placement,
                archived=archived,
            )
        )
    return tuple(slides)


def load_project(path: Path) -> DeckProject:
    """Load `deck.toml` from a project directory or explicit config path."""
    config_path = path.resolve()
    if config_path.is_dir():
        config_path /= "deck.toml"
    if not config_path.is_file():
        raise DeckToolError(f"deck configuration does not exist: {config_path}")

    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise DeckToolError(f"invalid TOML in {config_path}: {error}") from error

    deck = raw.get("deck")
    raw_variants = raw.get("variants")
    if not isinstance(deck, dict):
        raise DeckToolError("deck.toml must contain a [deck] table")
    if not isinstance(raw_variants, dict) or not raw_variants:
        raise DeckToolError("deck.toml must contain a non-empty [variants] table")
    if ALL_VARIANT in raw_variants:
        raise DeckToolError(f"variant {ALL_VARIANT!r} is reserved")
    if not all(
        isinstance(name, str) and isinstance(description, str)
        for name, description in raw_variants.items()
    ):
        raise DeckToolError("variant names and descriptions must be strings")

    root = config_path.parent.resolve()
    render = raw.get("render", {})
    if not isinstance(render, dict):
        raise DeckToolError("render must be a table")
    web = raw.get("web", {})
    if not isinstance(web, dict):
        raise DeckToolError("web must be a table")
    allowed_fonts = render.get("allowed_font_prefixes", [])
    if not isinstance(allowed_fonts, list) or not all(
        isinstance(prefix, str) for prefix in allowed_fonts
    ):
        raise DeckToolError("render.allowed_font_prefixes must be a string list")
    require_notes = deck.get("require_notes", True)
    if not isinstance(require_notes, bool):
        raise DeckToolError("deck.require_notes must be true or false")
    default_theme = _string(deck, "default_theme", "default")

    project = DeckProject(
        root=root,
        config_path=config_path,
        title=_string(deck, "title"),
        default_variant=_string(deck, "default_variant"),
        variants=dict(raw_variants),
        slides=_load_slides(raw.get("slides")),
        slide_dir=_project_path(
            root, _string(deck, "slides_dir", "slides"), "deck.slides_dir"
        ),
        notes_dir=_project_path(
            root, _string(deck, "notes_dir", "notes"), "deck.notes_dir"
        ),
        asset_dir=_project_path(
            root, _string(deck, "assets_dir", "assets"), "deck.assets_dir"
        ),
        themes=_load_themes(root, deck, raw.get("themes"), default_theme),
        default_theme=default_theme,
        require_notes=require_notes,
        appendix_title=_string(deck, "appendix_title", "Appendix"),
        output_basename=_string(deck, "output_basename", "deck"),
        page_width_points=_positive_number(render, "page_width_points", 960),
        page_height_points=_positive_number(render, "page_height_points", 540),
        allowed_font_prefixes=tuple(allowed_fonts),
        google_analytics_id=normalize_google_analytics_id(
            web.get("google_analytics_id")
        ),
    )
    project.validate()
    return project
