"""IDML export contract tests — the InDesign-editability guarantee.

The PDF is flat (no text layer); the IDML must open in InDesign as a REAL
document: editable stories, linked images, per-page spreads, styles.
"""

from __future__ import annotations

import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # postprocessor root (export_idml lives there)

from export_idml import export_idml  # noqa: E402

FIXTURE = HERE.parent.parent / "v7-renderer" / "fixtures" / "apex" / "resolved_package.json"


def _export(tmp_path: Path) -> Path:
    return export_idml(FIXTURE, tmp_path / "deck.idml")


def _read(z: zipfile.ZipFile, name: str) -> str:
    return z.read(name).decode("utf-8")


# --------------------------------------------------------------------------- #
# 1. container + designmap (InDesign's entry points)
# --------------------------------------------------------------------------- #
def test_container_points_to_designmap(tmp_path: Path) -> None:
    out = _export(tmp_path)
    with zipfile.ZipFile(out) as z:
        container = _read(z, "META-INF/container.xml")
        assert 'full-path="designmap.xml"' in container
        assert "designmap.xml" in z.namelist()


def test_designmap_has_story_and_spread_lists(tmp_path: Path) -> None:
    out = _export(tmp_path)
    with zipfile.ZipFile(out) as z:
        dm = _read(z, "designmap.xml")
        assert "<StoryList>" in dm and "</StoryList>" in dm
        assert "<SpreadList>" in dm and "</SpreadList>" in dm
        assert "<MasterSpreadList>" in dm


# --------------------------------------------------------------------------- #
# 2. editable TEXT: every page's copy is a story with real content
# --------------------------------------------------------------------------- #
def test_stories_carry_verbatim_copy(tmp_path: Path) -> None:
    pkg = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = _export(tmp_path)
    with zipfile.ZipFile(out) as z:
        story_text = ""
        for n in z.namelist():
            if n.startswith("Stories/Story_"):
                story_text += _read(z, n)
        # a headline from the cover must be present verbatim
        cover = pkg["pages"][0].get("data", {})
        title = cover.get("title") or ""
        assert title and title in story_text, f"cover title not editable: {title!r}"


def test_story_count_matches_pages(tmp_path: Path) -> None:
    pkg = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = _export(tmp_path)
    with zipfile.ZipFile(out) as z:
        stories = [n for n in z.namelist() if n.startswith("Stories/Story_")]
        spreads = [n for n in z.namelist() if n.startswith("Spreads/Spread_")]
        assert len(spreads) == len(pkg["pages"])
        assert len(stories) >= len(pkg["pages"]), "every page must carry text"


# --------------------------------------------------------------------------- #
# 3. linked IMAGES: the real photos are placed + copied beside the IDML
# --------------------------------------------------------------------------- #
def test_images_are_linked_and_copied(tmp_path: Path) -> None:
    out = _export(tmp_path)
    links_dir = tmp_path / "Links"
    with zipfile.ZipFile(out) as z:
        graphic = _read(z, "Resources/Graphic.xml")
        assert "Href=" in graphic
    # the Links folder exists with real image files
    assert links_dir.exists()
    assert any(links_dir.iterdir()), "no linked images copied"


# --------------------------------------------------------------------------- #
# 4. per-page spreads exist for every physical page
# --------------------------------------------------------------------------- #
def test_spread_per_physical_page(tmp_path: Path) -> None:
    pkg = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = _export(tmp_path)
    with zipfile.ZipFile(out) as z:
        spreads = [n for n in z.namelist() if n.startswith("Spreads/Spread_")]
        assert len(spreads) == len(pkg["pages"]), (
            f"expected {len(pkg['pages'])} spreads; got {len(spreads)}"
        )


# --------------------------------------------------------------------------- #
# 5. every XML is well-formed (InDesign rejects malformed packages)
# --------------------------------------------------------------------------- #
def test_all_xml_well_formed(tmp_path: Path) -> None:
    out = _export(tmp_path)
    with zipfile.ZipFile(out) as z:
        for n in z.namelist():
            if n.endswith(".xml"):
                ET.fromstring(z.read(n))  # raises on malformed


# --------------------------------------------------------------------------- #
# 6. styles exist (headline/body/stat/quote) so Richard can restyle
# --------------------------------------------------------------------------- #
def test_styles_exported(tmp_path: Path) -> None:
    out = _export(tmp_path)
    with zipfile.ZipFile(out) as z:
        styles = _read(z, "Resources/Styles.xml")
        for name in ("headline", "body", "stat", "quote", "caption"):
            assert f"paragraph_style_{name}" in styles, f"missing style {name}"
