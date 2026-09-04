"""Command-line interface for the deck compiler."""

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from .compiler import DeckCompiler
from .errors import DeckToolError
from .project import ALL_VARIANT, load_project
from .render import render_pdf
from .web import inject_google_analytics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gimle-deck")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="deck project directory or deck.toml path",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="validate the project and its sources")
    commands.add_parser("list", help="list variants and their slide counts")

    build = commands.add_parser("build", help="build HTML or PDF")
    build.add_argument(
        "--variant", help="variant name; defaults to deck.default_variant"
    )
    build.add_argument("--theme", help="theme name; defaults to deck.default_theme")
    build.add_argument("--format", choices=("html", "pdf"), default="html")
    build.add_argument("--output", type=Path)
    build.add_argument("--tags", action="store_true", help="add internal review labels")
    build.add_argument(
        "--analytics",
        action="store_true",
        help="include configured Google Analytics in HTML output",
    )
    return parser


def _default_output(project, variant: str, theme: str, output_format: str) -> Path:
    variant_suffix = "" if variant == project.default_variant else f"_{variant}"
    theme_suffix = "" if theme == project.default_theme else f"_{theme}"
    return project.root / (
        f"{project.output_basename}{variant_suffix}{theme_suffix}.{output_format}"
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Run the deck CLI and return a process status."""
    args = _parser().parse_args(argv)
    try:
        project = load_project(args.project)
        compiler = DeckCompiler(project)
        if args.command == "check":
            project.validate()
            print(
                f"{project.config_path} — {len(project.active_slides)} active slides, "
                f"{len(project.archived_slugs)} archived"
            )
            return 0
        if args.command == "list":
            for name in (*sorted(project.variants), ALL_VARIANT):
                kept, _ = project.select(name)
                description = project.variants.get(name, "All active slides")
                print(f"{name}: {len(kept)} slides — {description}")
            return 0

        variant = args.variant or project.default_variant
        theme = args.theme or project.default_theme
        output = args.output or _default_output(project, variant, theme, args.format)
        html, kept = compiler.build(variant, theme=theme, tags=args.tags)
        if args.format == "html":
            if args.analytics:
                html = inject_google_analytics(html, project.google_analytics_id)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(html, encoding="utf-8")
        elif args.analytics:
            raise DeckToolError("--analytics is only valid for HTML output")
        else:
            source = project.root / "build" / f"{output.stem}.html"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(html, encoding="utf-8")
            render_pdf(project, source, output, len(kept))
        print(
            f"{output} — {len(kept)} slides "
            f"[{variant}, theme: {theme}, {args.format}]"
        )
        return 0
    except DeckToolError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
