"""IDML export — an InDesign-EDITABLE package for the deck.

Why this exists: the Chromium+Ghostscript PDF is print-ready but FLAT (no text
layer, CID-subset fonts, flattened transparency). Richard cannot edit it in
InDesign as a layout — every element is a locked graphic. This exporter writes
the deck as IDML (Adobe's native interchange markup): a ZIP of XML that
InDesign opens as a REAL document with:

  * editable TEXT (stories + paragraph styles — headline/body/stats/quotes)
  * linked IMAGES (the real client photos, copied beside the IDML)
  * movable/resizable FRAMES (per-page spread geometry)
  * the deck's copy VERBATIM from the package (no fabrication)

Scope (honest first version): page skeletons with real copy as editable
stories + real images as linked graphics + a basic style set. It is NOT a
pixel-perfect replica of the CSS layout — the point is that Richard takes over
the manual composition.

Brand-agnostic: all copy comes from the package; no client literal in logic.
"""

from __future__ import annotations

import json
import shutil
import xml.sax.saxutils as sax
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Geometry (IDML uses POINTS; 1mm = 72/25.4 pt)
# --------------------------------------------------------------------------- #
PT_PER_MM = 72.0 / 25.4

A4_W_MM, A4_H_MM = 210.0, 297.0
A3_W_MM, A3_H_MM = 420.0, 297.0
MARGIN_TOP_MM, MARGIN_BOTTOM_MM = 16.0, 20.0
MARGIN_SIDE_MM = 18.0


def _pt(mm: float) -> float:
    return round(mm * PT_PER_MM, 3)


# --------------------------------------------------------------------------- #
# IDML helpers
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    """XML-escape text for IDML story content (CDATA-safe)."""
    return sax.escape(str(text or ""))


@dataclass
class Story:
    """One editable text story (a paragraph block)."""

    self_id: str
    text: str
    style: str = "ParagraphStyle/paragraph_style_body"


@dataclass
class ImageRef:
    """One linked image placed in a frame."""

    self_id: str
    src: Path            # the asset file (copied to the links dir)
    link_name: str       # file name inside the links dir
    frame: tuple[float, float, float, float]  # top,left,bottom,right (pt)


@dataclass
class Page:
    """One physical page of the deck."""

    page_id: str
    spread_id: str
    width_pt: float
    height_pt: float
    stories: list[Story] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Page-data → stories/images (deterministic mapping from the package)
# --------------------------------------------------------------------------- #
_TEXT_FIELDS = (
    "title", "subtitle", "intro", "body", "lead", "ergebnis", "these",
    "key_insight", "ergebnis_text", "ausgangsproblem", "loesung", "ziel",
    "kurzportraet", "phrase", "audience", "cta_text", "ergebnis_headline",
    "kosten_des_nichtstuns", "pullquote_text",
)

_IMAGE_TYPES = ("photo", "portrait", "scene", "background", "proof")


def _collect_stories(data: dict, page_id: str) -> list[Story]:
    """Extract the page's text blocks as editable stories (verbatim copy)."""
    stories: list[Story] = []
    n = 0

    def _add(text: str, style: str) -> None:
        nonlocal n
        text = str(text or "").strip()
        if not text:
            return
        n += 1
        stories.append(Story(
            self_id=f"story_{page_id}_{n}",
            text=text,
            style=f"ParagraphStyle/paragraph_style_{style}",
        ))

    for field in _TEXT_FIELDS:
        val = data.get(field)
        if isinstance(val, str):
            _add(val, "body" if field != "title" else "headline")
        elif isinstance(val, dict) and "text" in val:
            _add(val.get("text", ""), "quote")

    # steps (mechanism/process pages): each step title+body as its own story
    for i, step in enumerate(data.get("steps") or []):
        if isinstance(step, dict):
            title = str(step.get("title") or "")
            body = str(step.get("body") or "")
            if title:
                _add(f"{title}", "h3")
            if body:
                _add(body, "body")

    # metrics/stats: value + label as one compact story
    for i, m in enumerate(data.get("ergebnis_metrics") or data.get("stats") or []):
        if isinstance(m, dict):
            value = str(m.get("value") or "")
            label = str(m.get("label") or "")
            if value:
                _add(f"{value}  {label}".strip(), "stat")

    # pullquote dict
    pq = data.get("pullquote")
    if isinstance(pq, dict):
        _add(str(pq.get("text") or ""), "quote")

    # testimonial captions
    for i, t in enumerate(data.get("testimonials") or []):
        if isinstance(t, dict):
            _add(str(t.get("label") or t.get("handle") or ""), "caption")

    return stories


def _collect_images(page: dict, assets_dir: Path, page_id: str) -> list[ImageRef]:
    """Resolve the page's image assets into placed, linked graphics."""
    images: list[ImageRef] = []
    n = 0
    for asset in page.get("assets") or []:
        path = asset.get("path")
        if not path or asset.get("image_type") not in _IMAGE_TYPES:
            continue
        src = assets_dir / str(path).removeprefix("assets/")
        if not src.exists():
            continue
        n += 1
        name = f"{page_id}_{n}{src.suffix}"
        # frame: a placeholder rectangle (top,left,bottom,right) — Richard
        # repositions/resizes freely; the content fills the frame on placement.
        images.append(ImageRef(
            self_id=f"img_{page_id}_{n}",
            src=src,
            link_name=name,
            frame=(_pt(20), _pt(MARGIN_SIDE_MM), _pt(90), _pt(150)),
        ))
    return images


# --------------------------------------------------------------------------- #
# IDML XML builders
# --------------------------------------------------------------------------- #
def _spread_xml(page: Page) -> str:
    """The spread XML: one A4/A3 page + its frames (text + images)."""
    frames = []
    story_refs = []
    for i, story in enumerate(page.stories):
        top = _pt(30 + 14 * i)
        left = _pt(MARGIN_SIDE_MM)
        bottom = _pt(30 + 14 * i + 12)
        right = page.width_pt - _pt(MARGIN_SIDE_MM)
        fid = f"tf_{story.self_id}"
        frames.append(
            f'<TextFrame Self="{fid}" Story="{story.self_id}" '
            f'PreviousTextFrame="n" NextTextFrame="n" '
            f'ContentType="TextType" '
            f'GeometricBounds="{top} {left} {bottom} {right}" '
            f'ItemTransform="1 0 0 1 0 0" '
            f'AppliedParagraphStyle="{story.style}"/>'
        )
        story_refs.append(f'<TextFrame Self="{fid}" ParentStory="{story.self_id}"/>')
    for img in page.images:
        top, left, bottom, right = img.frame
        gid = f"gf_{img.self_id}"
        frames.append(
            f'<Rectangle Self="{gid}" GeometricBounds="{top} {left} {bottom} {right}" '
            f'ItemTransform="1 0 0 1 0 0">'
            f'<FilledRectangleStroke />'
            f'</Rectangle>'
        )
        frames.append(
            f'<Image Self="{img.self_id}" '
            f'GeometricBounds="0 0 {bottom - top} {right - left}" '
            f'ItemTransform="1 0 0 1 0 0" '
            f'Graphic="graphic_{img.self_id}" '
            f'Visible="true"/>'
        )

    body = "".join(
        f'<Page Self="{page.page_id}" Name="{page.page_id}" '
        f'AppliedMaster="idMasterPageA" '
        f'GeometricBounds="0 0 {page.height_pt} {page.width_pt}" '
        f'ItemTransform="1 0 0 1 0 0"/>'
    ) + "".join(frames)

    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Spread Self="{page.spread_id}" PageCount="1" '
        f'AllowPageShuffle="true" ItemTransform="1 0 0 1 0 0">{body}</Spread>'
    )


def _story_xml(story: Story) -> str:
    """One story XML: the editable text with its paragraph style."""
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Story Self="{story.self_id}" AppliedTOC="idTOC" '
        f'AppliedNamedGrid="n" TrackChanges="false" StoryTitle="$ID/" '
        f'StoryDirection="LeftToRightDirection">'
        f'<StoryPreference OpticalMarginAlignment="false" '
        f'OpticalMarginSize="0" FrameType="TextFrameType" '
        f'StoryOrientation="Horizontal"/>'
        f'<ParagraphStyleRange AppliedParagraphStyle="{story.style}">'
        f'<CharacterStyleRange AppliedCharacterStyle="'
        f'CharacterStyle/$ID/[No character style]">'
        f'<Content>{_esc(story.text)}</Content>'
        f'</CharacterStyleRange></ParagraphStyleRange>'
        f'</Story>'
    )


def _graphic_xml(images: list[ImageRef]) -> str:
    """The graphic table: each image as a placed graphic referencing the link."""
    entries = []
    for img in images:
        entries.append(
            f'<Image Self="graphic_{img.self_id}" Type="GraphicType" '
            f'Visible="true" ItemTransform="1 0 0 1 0 0" '
            f'Dimensions="{img.frame[2] - img.frame[0]} '
            f'{img.frame[3] - img.frame[1]}" '
            f'GeometricBounds="0 0 {img.frame[2] - img.frame[0]} '
            f'{img.frame[3] - img.frame[1]}" '
            f'Href="Links/{img.link_name}" />'
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<GraphicTable xmlns:aid="http://ns.adobe.com/AdobeInDesign/4.0/">'
        + "".join(entries)
        + "</GraphicTable>"
    )


# --------------------------------------------------------------------------- #
# The exporter
# --------------------------------------------------------------------------- #
def export_idml(
    package_path: Path,
    out_path: Path,
    *,
    assets_dir: Path | None = None,
) -> Path:
    """Write `<out_path>/<report>.idml` + the `Links/` folder from a package.

    `out_path` may be a file (.idml) or a directory; the Links folder is
    written beside it.
    """
    package_path = Path(package_path)
    pkg = json.loads(package_path.read_text(encoding="utf-8"))
    if assets_dir is None:
        assets_dir = package_path.parent / "assets"
    assets_dir = Path(assets_dir)

    out_path = Path(out_path)
    if out_path.suffix.lower() == ".idml":
        idml_path = out_path
        links_dir = out_path.parent / "Links"
    else:
        idml_path = out_path / f"{pkg.get('record_id', 'report')}.idml"
        links_dir = out_path / "Links"
    idml_path.parent.mkdir(parents=True, exist_ok=True)
    links_dir.mkdir(parents=True, exist_ok=True)

    pages: list[Page] = []
    all_images: list[ImageRef] = []
    for idx, page in enumerate(pkg.get("pages", []), start=1):
        page_id = f"page_{idx}"
        spread_id = f"spread_{idx}"
        fmt = page.get("page_format")
        w_mm, h_mm = (A3_W_MM, A3_H_MM) if fmt == "a3" else (A4_W_MM, A4_H_MM)
        stories = _collect_stories(page.get("data") or {}, page_id)
        images = _collect_images(page, assets_dir, page_id)
        all_images.extend(images)
        pages.append(Page(
            page_id=page_id,
            spread_id=spread_id,
            width_pt=_pt(w_mm),
            height_pt=_pt(h_mm),
            stories=stories,
            images=images,
        ))

    # ---- copy image files to the Links folder (real, linked graphics) ----
    for img in all_images:
        shutil.copy2(img.src, links_dir / img.link_name)

    # ---- assemble the IDML ZIP ----
    all_stories = [s for p in pages for s in p.stories]

    with zipfile.ZipFile(idml_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/container.xml", _container_xml())
        z.writestr("designmap.xml", _designmap_xml(pages, all_stories))
        for s in all_stories:
            z.writestr(f"Stories/Story_{s.self_id}.xml", _story_xml(s))
        for p in pages:
            z.writestr(f"Spreads/Spread_{p.spread_id}.xml", _spread_xml(p))
        z.writestr("Resources/Graphic.xml", _graphic_xml(all_images))
        z.writestr("Resources/Styles.xml", _styles_xml())
        z.writestr("Resources/Color.xml", _color_xml())
        z.writestr("Resources/Fonts.xml", _fonts_xml())
        z.writestr("Resources/Layers.xml", _layers_xml())
        z.writestr("Resources/Preferences.xml", _prefs_xml())
        z.writestr("Resources/Tags.xml", _tags_xml())
        z.writestr("Resources/TOC.xml", _toc_xml())
        z.writestr("Resources/ViewingDistance.xml", _viewing_xml())
        z.writestr("Resources/ViewingBounds.xml", _viewing_bounds_xml())
        z.writestr(
            "MasterSpreads/MasterSpread_um.xml",
            _master_spread_xml(pages[0] if pages else None),
        )

    return idml_path


def _container_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0">\n'
        '  <rootfiles>\n'
        '    <rootfile full-path="designmap.xml" media-type="application/vnd.adobe.indesign-idml-package"/>\n'
        "  </rootfiles>\n"
        "</container>"
    )


def _designmap_xml(pages: list[Page], stories: list[Story]) -> str:
    page_list = ""
    for p in pages:
        page_list += (
            f'<Page Self="{p.page_id}" Name="{p.page_id}" '
            f'AppliedMaster="idMasterPageA" '
            f'GeometricBounds="0 0 {p.height_pt} {p.width_pt}" '
            f'ItemTransform="1 0 0 1 0 0"/>'
        )
    spread_list = ""
    for p in pages:
        spread_list += f'<Spread Self="{p.spread_id}" PageCount="1">{page_list}</Spread>'
    # NOTE: the spread bodies live in Spreads/Spread_*.xml; designmap lists them.
    spread_entries = "".join(
        f'<Spread Self="{p.spread_id}" PageCount="1" '
        f'AllowPageShuffle="true" ItemTransform="1 0 0 1 0 0"/>'
        for p in pages
    )
    story_entries = "".join(
        f'<Story Self="{s.self_id}" AppliedTOC="idTOC" />' for s in stories
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Document DOMVersion="8.0" Self="idDocument" '
        'xmlns:aid="http://ns.adobe.com/AdobeInDesign/4.0/">'
        '<DocumentPreference PageHeight="841.889763779528" '
        'PageWidth="595.275590551181" PageOrientation="0" '
        'PagesPerDocument="1" FacingPages="false" '
        'DocumentBleedTopOffset="0" DocumentBleedBottomOffset="0" '
        'DocumentBleedInsideOffset="0" DocumentBleedOutsideOffset="0" '
        'ColumnGutter="0" AllowPageShuffle="true"/>'
        '<DocumentBleedSetup Self="idDocBleedSetup" BleedTop="0" '
        'BleedBottom="0" BleedInside="0" BleedOutside="0"/>'
        '<ViewingBounds Self="idViewingBounds" Top="0" Left="0" '
        'Bottom="841.889763779528" Right="595.275590181102"/>'
        '<StoryList>' + story_entries + "</StoryList>"
        "<SpreadList>" + spread_entries + "</SpreadList>"
        "<MasterSpreadList>"
        '<MasterSpread Self="idMasterSpreadA" PageCount="1" '
        'Name="A-Master" ShowMasterItems="true" '
        'AllowPageShuffle="true"/>'
        "</MasterSpreadList>"
        '<Resource>'
        '<FontTable Self="idFontTable"><Font Self="font_0" '
        'FontStyle="Regular" FontName="SourceSans3-Regular" '
        'Name="Source Sans 3"/></FontTable>'
        '<ColorTable Self="idColorTable"/>'
        '<GraphicTable Self="idGraphicTable"/>'
        '<StyleTable Self="idStyleTable"/>'
        "<CharacterStyleList/>"
        "<ParagraphStyleList/>"
        "</Resource>"
        "</Document>"
    )


def _styles_xml() -> str:
    styles = {
        "headline": ('FontStyle="Bold" PointSize="32" Leading="36" '
                     'AppliedFont="font_0"'),
        "h3": ('FontStyle="Bold" PointSize="14" Leading="18" '
               'AppliedFont="font_0"'),
        "body": ('PointSize="10.5" Leading="15" AppliedFont="font_0"'),
        "stat": ('FontStyle="Bold" PointSize="40" Leading="44" '
                 'AppliedFont="font_0"'),
        "quote": ('FontStyle="Italic" PointSize="18" Leading="24" '
                  'AppliedFont="font_0"'),
        "caption": ('PointSize="8.5" Leading="11" AppliedFont="font_0"'),
    }
    entries = []
    for name, attrs in styles.items():
        # `attrs` already carries AppliedFont for headline/h3; keep ONE.
        if "AppliedFont" not in attrs:
            attrs = attrs + ' AppliedFont="font_0"'
        entries.append(
            f'<ParagraphStyle Self="paragraph_style_{name}" '
            f'Name="{name}" {attrs} '
            f'BasedOn="idParagraphStyleBase" '
            f'NextStyle="idParagraphStyleBase" '
            f'Justification="LeftAlign" SpaceAfter="6"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Styles><ParagraphStyleTable>'
        + "".join(entries)
        + "</ParagraphStyleTable>"
        "<CharacterStyleTable/></Styles>"
    )


def _color_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<ColorTable>"
        '<Color Self="color_black" Name="Black" Model="Process" '
        'ColorValue="0 0 0 100" ColorSpace="CMYK"/>'
        '<Color Self="color_paper" Name="Paper" Model="Process" '
        'ColorValue="0 0 0 0" ColorSpace="CMYK"/>'
        "</ColorTable>"
    )


def _fonts_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<FontTable>"
        '<Font Self="font_0" FontStyle="Regular" FontName="SourceSans3-Regular" '
        'Name="Source Sans 3"/>'
        '<Font Self="font_1" FontStyle="Bold" FontName="SourceSans3-Bold" '
        'Name="Source Sans 3"/>'
        "</FontTable>"
    )


def _layers_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Layers>'
        '<Layer Self="layer_1" Name="Layer 1" Visible="true" '
        'Locked="false" Printable="true" Color="176 138 60" '
        'Opacity="100"/>'
        "</Layers>"
    )


def _prefs_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Preferences Self="idPreferences"/>'
    )


def _tags_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<Tags/>"
    )


def _toc_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<TOC/>"
    )


def _viewing_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<ViewingDistance/>"
    )


def _viewing_bounds_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<ViewingBounds/>"
    )


def _master_spread_xml(first: Page | None) -> str:
    if first is None:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            "<MasterSpread Self=\"idMasterSpreadA\" PageCount=\"1\"/>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<MasterSpread Self="idMasterSpreadA" PageCount="1" '
        f'Name="A-Master" ShowMasterItems="true" AllowPageShuffle="true">'
        f'<Page Self="idMasterPageA" Name="A-Master" '
        f'AppliedMaster="n" GeometricBounds="0 0 {first.height_pt} '
        f'{first.width_pt}" ItemTransform="1 0 0 1 0 0"/>'
        "</MasterSpread>"
    )


def package_delivery(
    idml_path: Path,
    zip_path: Path,
    *,
    extra_files: list[Path] | None = None,
) -> Path:
    """Assemble the MAIL-READY delivery unit: a ZIP with the IDML, its Links
    folder, and optional extra files (PDF/PNGs).

    Why a ZIP: the IDML's images are LINKED (href="Links/<file>"), so the
    Links folder must travel with the file or InDesign shows missing images.
    A single ZIP is the attachment n8n can mail or upload to Drive.
    """
    idml_path = Path(idml_path)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    links_dir = idml_path.parent / "Links"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(idml_path, idml_path.name)
        if links_dir.exists():
            for f in sorted(links_dir.iterdir()):
                if f.is_file():
                    z.write(f, f"Links/{f.name}")
        for extra in extra_files or []:
            extra = Path(extra)
            if extra.exists():
                z.write(extra, extra.name)
    return zip_path
