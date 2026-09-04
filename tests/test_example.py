"""Integration tests for the example project shipped with the package."""

import unittest
from pathlib import Path

from gimle_deck.compiler import DeckCompiler
from gimle_deck.project import APPENDIX_DIVIDER, load_project


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "basic"


class ExampleProjectTest(unittest.TestCase):
    def test_default_theme_builds_the_complete_example(self) -> None:
        project = load_project(EXAMPLE)

        html, kept = DeckCompiler(project).build("full", quiet=True)

        self.assertEqual("default", project.default_theme)
        self.assertEqual(
            [
                "title",
                "one_source_many_decks",
                "slide_contract",
                "variants_shape_the_story",
                "assets_stay_with_the_deck",
                "themes_change_the_frame",
                "build_artifacts",
                "closing",
                APPENDIX_DIVIDER,
                "manifest_reference",
                "asset_reference",
            ],
            kept,
        )
        self.assertEqual(("legacy_overview",), project.archived_slugs)
        self.assertIn("One source of truth", html)
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg"', html)
        self.assertIn("data:image/png;base64,", html)
        self.assertIn("<pre><code>", html)
        self.assertIn("<table>", html)
        self.assertNotIn("{{", html)

    def test_minimal_theme_builds_the_public_example(self) -> None:
        project = load_project(EXAMPLE)

        html, kept = DeckCompiler(project).build("public", theme="minimal", quiet=True)

        self.assertEqual(
            [
                "title",
                "one_source_many_decks",
                "variants_shape_the_story",
                "assets_stay_with_the_deck",
                "build_artifacts",
                "closing",
            ],
            kept,
        )
        self.assertIn('class="minimal-deck"', html)
        self.assertNotIn("A slide has one outer section", html)
        self.assertNotIn("Appendix", html)

    def test_readme_separates_required_and_recommended_slide_structure(
        self,
    ) -> None:
        readme = (EXAMPLE.parents[1] / "README.md").read_text(encoding="utf-8")
        authoring = (EXAMPLE.parents[1] / "docs" / "slide-authoring.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Required HTML contract", readme)
        self.assertIn("Recommended slide anatomy", readme)
        self.assertIn('<section class="slide', readme)
        self.assertIn("Compiler-owned markup", authoring)
        self.assertIn("Project-owned markup", authoring)
        self.assertIn("Do not author `.num`", authoring)

    def test_repository_declares_the_mit_license(self) -> None:
        root = EXAMPLE.parents[1]
        license_text = (root / "LICENSE").read_text(encoding="utf-8")
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")

        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Copyright (c) 2026 Gimle Labs", license_text)
        self.assertIn('requires = ["setuptools>=77"]', pyproject)
        self.assertIn('license = "MIT"', pyproject)
        self.assertIn('license-files = ["LICENSE"]', pyproject)
        self.assertIn("[MIT License](LICENSE)", readme)


if __name__ == "__main__":
    unittest.main()
