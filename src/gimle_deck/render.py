"""Render assembled deck HTML to PDF and verify the resulting artifact."""

from pathlib import Path
import re
import shutil
import subprocess
from typing import List, Optional

from .errors import DeckToolError
from .project import DeckProject


def find_chrome() -> Optional[str]:
    """Find a supported Chrome or Chromium executable."""
    candidates = (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
        if Path(candidate).is_file():
            return candidate
    return None


def _run(command: List[str], label: str) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as error:
        raise DeckToolError(f"{label} timed out after 60 seconds") from error
    except OSError as error:
        raise DeckToolError(f"could not start {label}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise DeckToolError(f"{label} failed: {detail}")
    return result


def verify_pdf(project: DeckProject, output: Path, expected_pages: int) -> None:
    """Verify page count, geometry, and optional font allowlist."""
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        info = _run([pdfinfo, str(output)], "pdfinfo").stdout
        pages = re.search(r"^Pages:\s+(\d+)", info, flags=re.MULTILINE)
        size = re.search(
            r"^Page size:\s+([0-9.]+) x ([0-9.]+) pts", info, flags=re.MULTILINE
        )
        if not pages or int(pages.group(1)) != expected_pages:
            actual = pages.group(1) if pages else "unknown"
            raise DeckToolError(f"PDF has {actual} pages; expected {expected_pages}")
        if not size:
            raise DeckToolError("pdfinfo did not report page geometry")
        width, height = float(size.group(1)), float(size.group(2))
        if (
            abs(width - project.page_width_points) > 0.1
            or abs(height - project.page_height_points) > 0.1
        ):
            raise DeckToolError(
                f"PDF page size is {width:g} x {height:g} pts; expected "
                f"{project.page_width_points:g} x {project.page_height_points:g} pts"
            )

    pdffonts = shutil.which("pdffonts")
    if pdffonts and project.allowed_font_prefixes:
        lines = _run([pdffonts, str(output)], "pdffonts").stdout.splitlines()[2:]
        names = {re.sub(r"^[A-Z]{6}\+", "", line.split()[0]) for line in lines if line}
        stray = sorted(
            name
            for name in names
            if not any(
                name.startswith(prefix) for prefix in project.allowed_font_prefixes
            )
        )
        if stray:
            raise DeckToolError("PDF contains unapproved fonts: " + ", ".join(stray))


def render_pdf(
    project: DeckProject, source: Path, output: Path, expected_pages: int
) -> None:
    """Render one assembled HTML source through headless Chrome."""
    chrome = find_chrome()
    if not chrome:
        raise DeckToolError("no Chrome or Chromium executable found")
    output.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--virtual-time-budget=10000",
            f"--print-to-pdf={output.resolve()}",
            source.resolve().as_uri(),
        ],
        "Chrome PDF render",
    )
    if not output.is_file():
        raise DeckToolError(f"Chrome did not create {output}")
    verify_pdf(project, output, expected_pages)
