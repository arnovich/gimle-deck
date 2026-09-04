"""Tests for the reusable HTML deck compiler."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from gimle_deck.cli import main
from gimle_deck.compiler import DeckCompiler
from gimle_deck.errors import DeckToolError
from gimle_deck.project import APPENDIX_DIVIDER, load_project
from gimle_deck.web import google_analytics_fragment


CONFIG = """\
[deck]
title = "Example deck"
default_variant = "full"
slides_dir = "slides"
notes_dir = "notes"
assets_dir = "assets"
template = "template.html"
stylesheet = "deck.css"

[web]
google_analytics_id = "G-EXAMPLE123"

[variants]
full = "Complete deck"
public = "Public deck"

[[slides]]
slug = "title"

[[slides]]
slug = "detail"
variants = ["full"]

[[slides]]
slug = "supporting_detail"
variants = ["full"]
placement = "appendix"

[[slides]]
slug = "old_detail"
archived = true
"""

THEMED_CONFIG = (
    CONFIG.replace(
        'template = "template.html"\nstylesheet = "deck.css"\n',
        'default_theme = "default"\n',
    )
    + """\

[themes.default]
template = "template.html"
stylesheet = "deck.css"

[themes.minimal]
template = "minimal.html"
stylesheet = "minimal.css"
"""
)


class DeckProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)
        (self.root / "slides").mkdir()
        (self.root / "notes").mkdir()
        (self.root / "assets").mkdir()
        (self.root / "deck.toml").write_text(CONFIG, encoding="utf-8")
        (self.root / "template.html").write_text(
            "<html><head><title>{{title}}</title><style>{{css}}</style></head>"
            "<body>{{slides}}</body></html>",
            encoding="utf-8",
        )
        (self.root / "minimal.html").write_text(
            "<html><head><style>{{css}}</style></head>"
            '<body><article class="minimal">{{slides}}</article></body></html>',
            encoding="utf-8",
        )
        (self.root / "deck.css").write_text(
            '@font-face{src:url("font.ttf")}\n'
            '.slide{background-image:url("{{asset:bg.svg}}")}',
            encoding="utf-8",
        )
        (self.root / "font.ttf").write_bytes(b"example font")
        (self.root / "minimal.css").write_text(
            ".minimal{color:rebeccapurple}", encoding="utf-8"
        )
        (self.root / "assets" / "bg.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
            encoding="utf-8",
        )
        (self.root / "slides" / "title.html").write_text(
            '<section class="slide title">{{include:mark.svg}}Title</section>',
            encoding="utf-8",
        )
        (self.root / "assets" / "mark.svg").write_text(
            '<svg class="mark"></svg>', encoding="utf-8"
        )
        (self.root / "slides" / "detail.html").write_text(
            '<section class="slide"><section>Nested</section>Detail</section>',
            encoding="utf-8",
        )
        (self.root / "slides" / "old_detail.html").write_text(
            '<section class="slide">Old</section>', encoding="utf-8"
        )
        (self.root / "slides" / "supporting_detail.html").write_text(
            '<section class="slide">Supporting</section>', encoding="utf-8"
        )
        for slug in ("title", "detail", "supporting_detail", "old_detail"):
            (self.root / "notes" / f"{slug}.md").write_text(
                f"Notes for {slug}.\n", encoding="utf-8"
            )

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_loads_and_selects_a_project_manifest(self) -> None:
        project = load_project(self.root)

        self.assertEqual("Example deck", project.title)
        self.assertEqual("default", project.default_theme)
        self.assertEqual(("default",), project.theme_names())
        self.assertEqual((self.root / "template.html").resolve(), project.template_path)
        self.assertEqual((self.root / "deck.css").resolve(), project.stylesheet_path)
        self.assertEqual("G-EXAMPLE123", project.google_analytics_id)
        self.assertEqual(
            ["title", "detail", APPENDIX_DIVIDER, "supporting_detail"],
            project.select("full")[0],
        )
        self.assertEqual(["title"], project.select("public")[0])
        self.assertEqual(
            ["title", "detail", APPENDIX_DIVIDER, "supporting_detail"],
            project.select("all")[0],
        )
        self.assertEqual(("old_detail",), project.archived_slugs)

    def test_loads_named_themes_and_uses_the_declared_default(self) -> None:
        (self.root / "deck.toml").write_text(THEMED_CONFIG, encoding="utf-8")

        project = load_project(self.root)

        self.assertEqual("default", project.theme().name)
        self.assertEqual(("default", "minimal"), project.theme_names())
        self.assertEqual(
            (self.root / "minimal.html").resolve(),
            project.theme("minimal").template_path,
        )
        self.assertEqual(
            (self.root / "minimal.css").resolve(),
            project.theme("minimal").stylesheet_path,
        )

    def test_theme_named_default_is_implicit_when_no_default_is_configured(
        self,
    ) -> None:
        implicit_default = THEMED_CONFIG.replace('default_theme = "default"\n', "")
        (self.root / "deck.toml").write_text(implicit_default, encoding="utf-8")

        project = load_project(self.root)

        self.assertEqual("default", project.default_theme)
        self.assertEqual("default", project.theme().name)

    def test_compiler_builds_with_a_named_theme_without_changing_the_default(
        self,
    ) -> None:
        (self.root / "deck.toml").write_text(THEMED_CONFIG, encoding="utf-8")
        compiler = DeckCompiler(load_project(self.root))

        default_html, _ = compiler.build("public", quiet=True)
        minimal_html, _ = compiler.build("public", theme="minimal", quiet=True)

        self.assertIn("<title>Example deck</title>", default_html)
        self.assertNotIn('class="minimal"', default_html)
        self.assertIn('class="minimal"', minimal_html)
        self.assertIn("color:rebeccapurple", minimal_html)
        self.assertNotIn("data:font/ttf;base64,", minimal_html)

    def test_rejects_an_unknown_theme_with_the_available_names(self) -> None:
        (self.root / "deck.toml").write_text(THEMED_CONFIG, encoding="utf-8")
        project = load_project(self.root)

        with self.assertRaisesRegex(
            DeckToolError, "unknown theme 'missing'.*default, minimal"
        ):
            project.theme("missing")

    def test_rejects_a_default_theme_that_is_not_declared(self) -> None:
        invalid = THEMED_CONFIG.replace(
            'default_theme = "default"', 'default_theme = "missing"'
        )
        (self.root / "deck.toml").write_text(invalid, encoding="utf-8")

        with self.assertRaisesRegex(DeckToolError, "default theme 'missing'"):
            load_project(self.root)

    def test_google_analytics_is_optional(self) -> None:
        without_analytics = CONFIG.replace(
            '[web]\ngoogle_analytics_id = "G-EXAMPLE123"\n\n', ""
        )
        (self.root / "deck.toml").write_text(without_analytics, encoding="utf-8")
        output = self.root / "without-analytics.html"

        self.assertIsNone(load_project(self.root).google_analytics_id)
        self.assertEqual("", google_analytics_fragment(None))
        self.assertEqual(
            0,
            main(
                [
                    "--project",
                    str(self.root),
                    "build",
                    "--variant",
                    "public",
                    "--format",
                    "html",
                    "--analytics",
                    "--output",
                    str(output),
                ]
            ),
        )
        self.assertNotIn(
            "googletagmanager.com",
            output.read_text(encoding="utf-8"),
        )

    def test_rejects_an_unsafe_google_analytics_id(self) -> None:
        unsafe = CONFIG.replace("G-EXAMPLE123", "</script>")
        (self.root / "deck.toml").write_text(unsafe, encoding="utf-8")

        with self.assertRaisesRegex(DeckToolError, "google_analytics_id"):
            load_project(self.root)

    def test_builds_google_analytics_from_the_configured_id(self) -> None:
        analytics = google_analytics_fragment(
            load_project(self.root).google_analytics_id
        )

        self.assertIn("gtag/js?id=G-EXAMPLE123", analytics)
        self.assertIn("gtag('config', 'G-EXAMPLE123');", analytics)

    def test_builds_self_contained_numbered_html(self) -> None:
        compiler = DeckCompiler(load_project(self.root))

        html, kept = compiler.build("full", quiet=True)

        self.assertEqual(
            ["title", "detail", APPENDIX_DIVIDER, "supporting_detail"], kept
        )
        self.assertIn("<title>Example deck</title>", html)
        self.assertIn('<svg class="mark"></svg>', html)
        self.assertIn("data:image/svg+xml;base64,", html)
        self.assertIn("data:font/ttf;base64,", html)
        self.assertNotIn('class="num"', html.split("Title", 1)[0])
        self.assertIn('<div class="num">02</div>', html)
        self.assertIn("<h2>Appendix</h2>", html)
        self.assertIn('<div class="num">04</div>', html)
        self.assertNotIn("{{", html)

    def test_rejects_an_asset_path_outside_the_project(self) -> None:
        compiler = DeckCompiler(load_project(self.root))

        with self.assertRaisesRegex(DeckToolError, "must stay inside"):
            compiler.resolve_assets("{{include:../secret.txt}}", "title")

    def test_rejects_a_slide_without_the_slide_class(self) -> None:
        (self.root / "slides" / "title.html").write_text(
            '<section class="title">Title</section>', encoding="utf-8"
        )
        compiler = DeckCompiler(load_project(self.root))

        with self.assertRaisesRegex(DeckToolError, "outer section.*slide.*class"):
            compiler.build("public", quiet=True)

    def test_cli_lists_checks_and_builds_the_project(self) -> None:
        output = self.root / "out.html"
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            self.assertEqual(0, main(["--project", str(self.root), "list"]))
            self.assertEqual(0, main(["--project", str(self.root), "check"]))
            self.assertEqual(
                0,
                main(
                    [
                        "--project",
                        str(self.root),
                        "build",
                        "--variant",
                        "public",
                        "--format",
                        "html",
                        "--analytics",
                        "--output",
                        str(output),
                    ]
                ),
            )

        self.assertIn("full", stdout.getvalue())
        self.assertIn("public", stdout.getvalue())
        self.assertTrue(output.exists())
        output_html = output.read_text(encoding="utf-8")
        self.assertEqual(1, output_html.count("<section"))
        self.assertIn("gtag/js?id=G-EXAMPLE123", output_html)

    def test_cli_builds_a_named_theme(self) -> None:
        (self.root / "deck.toml").write_text(THEMED_CONFIG, encoding="utf-8")
        output = self.root / "deck_public_minimal.html"

        self.assertEqual(
            0,
            main(
                [
                    "--project",
                    str(self.root),
                    "build",
                    "--variant",
                    "public",
                    "--theme",
                    "minimal",
                ]
            ),
        )

        self.assertIn('class="minimal"', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
