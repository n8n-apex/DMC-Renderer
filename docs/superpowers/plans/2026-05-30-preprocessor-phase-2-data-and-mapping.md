# Pre-Processor Phase 2 — Data & Mapping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the typed DATA layer the richer PDF needs — the 6 validated design **axes** (`resolve_axes`), typed **per-page data + rhetorical-chart data + social-proof data** (`structure_content` + `models_pagedata`), and the declarative **slot registry + pure resolver** (`resolve_slots`) — all additive, with the golden contract test + 244 existing tests staying green.

**Architecture:** Phase 2 of 4 implementing `docs/superpowers/specs/2026-05-30-preprocessor-PRD.md`. Covers **PRD Units 2 + 3 + 4**. Built on the Phase-1 foundation (golden net + Settings/DI/logging/stamina/Stage-runner/errors). Every new capability is a NEW module with NEW tests; **nothing is wired into the emitted package yet** (that happens in Phase 4 / Unit 10 when the manifest goes v2.0 and the golden re-baselines). This keeps the package byte-stable and the golden green throughout Phase 2.

**Tech Stack:** Python 3.11, Pydantic v2, stdlib `colorsys` (axes hue math — no new dep), the existing strict-JSON OpenRouter spine (reused for the one interpretive chart-extraction lane). No new runtime deps in Unit 2.

**Plan status:** Unit 2 (axes) is fully detailed below. **Units 3 + 4 are appended once the renderer data-read-contract grounding lands** (the typed page-data field names must match exactly what the renderer already reads, per PRD §8.1).

---

## Conventions (same as Phase 1 — read once)

- **Working dir:** `/Users/utkarsh/Projects/richard/research/preprocessor/`; interpreter `.venv/bin/python`; tests run from that dir.
- **Full-suite command (the net):** `.venv/bin/python -m pytest tests/ -q` — baseline entering Phase 2: **244 passed**.
- **Guard:** `.venv/bin/python -m pytest tests/test_no_client_name_in_logic.py -q` — auto-covers new modules via `rglob`; new code must contain NO client-name literal.
- **Golden:** `.venv/bin/python -m pytest tests/test_resolved_package_contract.py -q` — must stay green for ALL of Phase 2 (package output unchanged until Phase 4).
- **NO GIT** in this repo. Per-task **Checkpoint** (replaces "commit") = new tests pass **AND** full suite green **AND** guard green **AND** golden green. That four-way gate is the ralph-loop convergence point: repeat red→green→refactor on a step until all four hold, then advance.
- **Async tests:** `@pytest.mark.anyio` + a module-local `anyio_backend` fixture returning `"asyncio"`. (Unit 2 is all sync.)
- **Brand-agnostic (cardinal):** axes/data/slots are DATA. Modules name only axis *kinds* + value *sets* + slot *kinds* + convention *keys* — never a client. Fixtures may use hexes/values but no client names.

---

## Why nothing is wired into the package in Phase 2 (reconciliation)

The PRD §6 says `resolve_axes` "replaces the inline literal at `main.py`" and §5 promotes the manifest to v2.0. Doing that **changes the emitted `brand_axes`** (4 keys → a 6-axis `ResolvedAxes`), which would break the golden snapshot. Per the additive discipline (and exactly like Phase 1 built the Stage runner without wiring it), Phase 2 builds the **capabilities + tests**; **Phase 4 (Unit 10)** wires them into the package and re-baselines the golden on purpose. So throughout Phase 2 the golden stays green.

---

## File Structure (Phase 2)

**Unit 2 — Axes (this section):**
- Modify `models.py` — add 3 axis fields to `BrandProfile` (`palette`, `qr_enabled`, `density`).
- Modify `models_onboard.py` — add the same 3 to `VisionAxes`.
- Create `stages/resolve_axes.py` — `ResolvedAxes` model + the pure `resolve_axes` resolver (precedence + `colorsys` hue-distance derivation + provenance).
- Create `tests/test_resolve_axes.py`.

**Unit 3 — Structured data (appended after renderer-contract grounding):**
- Create `models_pagedata.py`, `stages/structure_content.py`, `tests/test_structure_content.py` (+ a German-number parser, since only a *detector* exists today).

**Unit 4 — Slot registry + resolver (appended after grounding):**
- Create `stages/slot_registry.py` (`SlotSpec` + `PageTypeRecipe`), `stages/resolve_slots.py` (pure resolver + new statuses), `tests/test_slot_resolver.py`.

---

## Unit 2 — Axes (PRD Unit 2, §6)

Build the 6 validated design axes (DNA §B) as a typed, deterministic, pure resolver. **Not wired into `/render` or the package yet** (Phase 4). Grounding facts (verified against current code): `BrandProfile` (`models.py` L53–83, `ConfigDict(extra="allow")`) already has `accent_mechanic`/`ground_mode`/`texture`/`headline_type` (all `Optional[str]=None`); `VisionAxes` (`models_onboard.py` L97–101) has the same 4; **`palette`/`qr_enabled`/`density` are absent from both**. The resolved brand hexes come from `BrandTokensResolved.brand_primary`/`brand_accent` (the canonical precedence-resolved values from `stages/validate_input.py`).

### Task 2.1: Extend `BrandProfile` + `VisionAxes` with the 3 missing axes

**Files:**
- Modify: `models.py` (`BrandProfile`, after the `headline_type` field ~L83)
- Modify: `models_onboard.py` (`VisionAxes`, after its `headline_type` field ~L101)
- Create: `tests/test_resolve_axes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resolve_axes.py` with (this file grows in Task 2.2):

```python
"""Tests for the 6 design axes: model extensions + the pure resolver."""
from __future__ import annotations

from models import BrandProfile
from models_onboard import VisionAxes


def test_brand_profile_carries_new_axes() -> None:
    bp = BrandProfile(palette="dual_contrasting", qr_enabled=True, density="packed")
    assert bp.palette == "dual_contrasting"
    assert bp.qr_enabled is True
    assert bp.density == "packed"
    # additive + optional: a bare profile leaves them None
    assert BrandProfile().palette is None
    assert BrandProfile().qr_enabled is None
    assert BrandProfile().density is None


def test_vision_axes_carries_new_axes() -> None:
    va = VisionAxes(palette="mono_tonal", qr_enabled=False, density="airy")
    assert va.palette == "mono_tonal"
    assert va.qr_enabled is False
    assert va.density == "airy"
    assert VisionAxes().palette is None
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_resolve_axes.py -q`
Expected: FAIL (`BrandProfile`/`VisionAxes` have no `palette`).

- [ ] **Step 3: Add the fields to `BrandProfile`**

In `models.py`, in `BrandProfile`, immediately after the `headline_type: Optional[str] = None` line, add:

```python
    # §B axes added post-DNA (palette/accent derivation + QR + density).
    palette: Optional[str] = None        # mono_tonal | dual_contrasting
    qr_enabled: Optional[bool] = None     # whether the brand uses QR codes
    density: Optional[str] = None         # airy | balanced | packed
```

- [ ] **Step 4: Add the fields to `VisionAxes`**

In `models_onboard.py`, in `VisionAxes`, after its `headline_type: Optional[str] = None` line, add:

```python
    palette: Optional[str] = None
    qr_enabled: Optional[bool] = None
    density: Optional[str] = None
```

- [ ] **Step 5: Run the test — expect pass**

Run: `.venv/bin/python -m pytest tests/test_resolve_axes.py -q` → 2 passed.

- [ ] **Step 6: Checkpoint**

Run: `.venv/bin/python -m pytest tests/ -q` → expect **246 passed** (244 + 2).
Run guard + golden → both green (additive Optional fields change no output).

### Task 2.2: `ResolvedAxes` model + pure `resolve_axes` resolver

**Files:**
- Create: `stages/resolve_axes.py`
- Modify: `tests/test_resolve_axes.py` (append resolver tests)

- [ ] **Step 1: Append the failing resolver tests**

Append to `tests/test_resolve_axes.py`:

```python
from stages.resolve_axes import ResolvedAxes, resolve_axes

_HEADLINE = {"serif", "sans", "sans_allcaps"}
_PALETTE = {"mono_tonal", "dual_contrasting"}
_ACCENT = {"tonal_same_hue", "contrasting_hue"}
_TEXTURE = {"smooth", "marble_paper", "crumpled_paper", "paper_grain", "photo"}
_DENSITY = {"airy", "balanced", "packed"}


def test_defaults_when_no_profile_and_tonal_hexes() -> None:
    # two close blues → same hue family → tonal/mono; everything else default
    axes, prov = resolve_axes(brand_profile=None, brand_primary="#1B3A6B", brand_accent="#2E5BA6")
    assert axes.headline_type == "serif"          # DNA §B default 5:1
    assert axes.texture == "smooth"
    assert axes.density == "balanced"
    assert axes.qr_enabled is False
    assert axes.palette == "mono_tonal"
    assert axes.accent_mechanic == "tonal_same_hue"
    assert prov["headline_type"] == "default"
    assert prov["palette"] == "derived"
    assert prov["qr_enabled"] == "default"


def test_contrasting_hexes_derive_dual_contrasting() -> None:
    # navy primary + gold accent → distant hue → contrasting/dual
    axes, prov = resolve_axes(brand_profile=None, brand_primary="#0A1F44", brand_accent="#C8A030")
    assert axes.palette == "dual_contrasting"
    assert axes.accent_mechanic == "contrasting_hue"
    assert prov["palette"] == "derived"


def test_explicit_profile_overrides_derivation() -> None:
    bp = BrandProfile(palette="mono_tonal", accent_mechanic="tonal_same_hue",
                      headline_type="sans_allcaps", texture="marble_paper",
                      density="packed", qr_enabled=True)
    # contrasting hexes would derive dual, but explicit wins
    axes, prov = resolve_axes(brand_profile=bp, brand_primary="#0A1F44", brand_accent="#C8A030")
    assert axes.palette == "mono_tonal"
    assert axes.accent_mechanic == "tonal_same_hue"
    assert axes.headline_type == "sans_allcaps"
    assert axes.texture == "marble_paper"
    assert axes.density == "packed"
    assert axes.qr_enabled is True
    assert prov["palette"] == "brand_profile"
    assert prov["headline_type"] == "brand_profile"
    assert prov["qr_enabled"] == "brand_profile"


def test_near_neutral_accent_reads_tonal() -> None:
    # a low-saturation (grey) accent → tonal, regardless of hue angle
    axes, _ = resolve_axes(brand_profile=None, brand_primary="#0A1F44", brand_accent="#9A9AA0")
    assert axes.palette == "mono_tonal"
    assert axes.accent_mechanic == "tonal_same_hue"


def test_invalid_profile_value_falls_through_to_default() -> None:
    bp = BrandProfile(headline_type="bogus", density="weird")
    axes, prov = resolve_axes(brand_profile=bp, brand_primary="#1B3A6B", brand_accent="#2E5BA6")
    assert axes.headline_type == "serif"
    assert axes.density == "balanced"
    assert prov["headline_type"] == "default"


def test_every_axis_is_a_valid_literal_for_data_profiles() -> None:
    # 6-deck-like profiles AS DATA (no client names) — every axis must validate
    fixtures = [
        (None, "#1B3A6B", "#2E5BA6"),
        (BrandProfile(headline_type="sans", texture="photo", qr_enabled=True), "#101418", "#2E6BFF"),
        (BrandProfile(headline_type="serif", texture="marble_paper"), "#0A1F44", "#C8A030"),
        (BrandProfile(palette="dual_contrasting", density="airy"), "#0E5C63", "#E0556B"),
    ]
    for bp, p, a in fixtures:
        axes, prov = resolve_axes(brand_profile=bp, brand_primary=p, brand_accent=a)
        assert axes.headline_type in _HEADLINE
        assert axes.palette in _PALETTE
        assert axes.accent_mechanic in _ACCENT
        assert axes.texture in _TEXTURE
        assert axes.density in _DENSITY
        assert isinstance(axes.qr_enabled, bool)
        assert set(prov) == {"headline_type", "palette", "accent_mechanic",
                             "texture", "qr_enabled", "density"}
```

- [ ] **Step 2: Run it — expect failure (no module)**

Run: `.venv/bin/python -m pytest tests/test_resolve_axes.py -q`
Expected: FAIL (`No module named 'stages.resolve_axes'`).

- [ ] **Step 3: Implement `stages/resolve_axes.py`**

Create `stages/resolve_axes.py`:

```python
"""resolve_axes — derive the 6 per-client design axes (DNA §B) as validated
Literals, deterministically. Precedence per axis: explicit brand_profile →
derived-from-tokens (palette/accent_mechanic, by hue distance) → grammar
default. Pure (no I/O, stdlib colorsys only). Records per-axis provenance.

Brand-agnostic: axes are DATA — this module names only axis kinds + value
sets, never a client. Not wired into the package until Phase 4 (Unit 10).
"""
from __future__ import annotations

import colorsys
from typing import Literal, Optional

from pydantic import BaseModel

HeadlineType = Literal["serif", "sans", "sans_allcaps"]
Palette = Literal["mono_tonal", "dual_contrasting"]
AccentMechanic = Literal["tonal_same_hue", "contrasting_hue"]
Texture = Literal["smooth", "marble_paper", "crumpled_paper", "paper_grain", "photo"]
Density = Literal["airy", "balanced", "packed"]

_HEADLINE = {"serif", "sans", "sans_allcaps"}
_PALETTE = {"mono_tonal", "dual_contrasting"}
_ACCENT = {"tonal_same_hue", "contrasting_hue"}
_TEXTURE = {"smooth", "marble_paper", "crumpled_paper", "paper_grain", "photo"}
_DENSITY = {"airy", "balanced", "packed"}

# Hue-distance (degrees) below which primary+accent read as one hue family
# → tonal/mono; above → contrasting/dual.
_HUE_SAME_FAMILY_DEG = 35.0
# An accent below this saturation is effectively neutral → treat as tonal.
_MIN_ACCENT_SATURATION = 0.15


class ResolvedAxes(BaseModel):
    """The 6 validated design axes. Serialized into the package in Phase 4."""

    headline_type: HeadlineType
    palette: Palette
    accent_mechanic: AccentMechanic
    texture: Texture
    qr_enabled: bool
    density: Density


def _hex_to_hls(hex_str: str) -> Optional[tuple[float, float, float]]:
    """(#rgb|#rrggbb) → (hue_deg, lightness, saturation); None if unparseable."""
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        r, g, b = (int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None
    h, light, sat = colorsys.rgb_to_hls(r, g, b)
    return h * 360.0, light, sat


def _hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _derive_palette_accent(primary_hex: str, accent_hex: str) -> tuple[Palette, AccentMechanic]:
    p = _hex_to_hls(primary_hex)
    a = _hex_to_hls(accent_hex)
    if p is None or a is None:
        return "mono_tonal", "tonal_same_hue"
    if a[2] < _MIN_ACCENT_SATURATION:               # near-neutral accent
        return "mono_tonal", "tonal_same_hue"
    if _hue_distance(p[0], a[0]) <= _HUE_SAME_FAMILY_DEG:
        return "mono_tonal", "tonal_same_hue"
    return "dual_contrasting", "contrasting_hue"


def resolve_axes(
    *,
    brand_profile,                 # Optional[BrandProfile] (duck-typed)
    brand_primary: str,
    brand_accent: str,
) -> tuple[ResolvedAxes, dict[str, str]]:
    """Resolve the 6 axes + a {axis: source} provenance map. Sources:
    "brand_profile" | "derived" | "default"."""
    prov: dict[str, str] = {}

    def explicit(axis: str, allowed: set[str]) -> Optional[str]:
        val = getattr(brand_profile, axis, None) if brand_profile is not None else None
        if isinstance(val, str) and val in allowed:
            prov[axis] = "brand_profile"
            return val
        return None

    def with_default(axis: str, chosen: Optional[str], default: str) -> str:
        if chosen is not None:
            return chosen
        prov[axis] = "default"
        return default

    headline_type = with_default("headline_type", explicit("headline_type", _HEADLINE), "serif")
    texture = with_default("texture", explicit("texture", _TEXTURE), "smooth")
    density = with_default("density", explicit("density", _DENSITY), "balanced")

    palette = explicit("palette", _PALETTE)
    accent = explicit("accent_mechanic", _ACCENT)
    if palette is None or accent is None:
        d_palette, d_accent = _derive_palette_accent(brand_primary, brand_accent)
        if palette is None:
            palette, prov["palette"] = d_palette, "derived"
        if accent is None:
            accent, prov["accent_mechanic"] = d_accent, "derived"

    qr_val = getattr(brand_profile, "qr_enabled", None) if brand_profile is not None else None
    if isinstance(qr_val, bool):
        qr_enabled, prov["qr_enabled"] = qr_val, "brand_profile"
    else:
        qr_enabled, prov["qr_enabled"] = False, "default"

    return (
        ResolvedAxes(
            headline_type=headline_type,
            palette=palette,
            accent_mechanic=accent,
            texture=texture,
            qr_enabled=qr_enabled,
            density=density,
        ),
        prov,
    )
```

- [ ] **Step 4: Run the test — expect pass**

Run: `.venv/bin/python -m pytest tests/test_resolve_axes.py -q` → 8 passed (2 model + 6 resolver).

- [ ] **Step 5: Checkpoint**

Run: `.venv/bin/python -m pytest tests/ -q` → expect **252 passed** (246 + 6).
Run guard + golden → both green.

### Unit 2 self-review
- **Coverage (PRD §6):** 6 validated Literal axes ✓; precedence explicit→derived→default ✓; palette/accent derived from hue distance (`colorsys`, no dep) ✓; provenance map ✓; `BrandProfile` + `VisionAxes` extended with the 3 missing axes ✓. **Deferred to Phase 4 (stated):** wiring `resolve_axes` into `main.py`/the package + the `/onboard` VisionAxes→BrandProfile plumbing (those change the emitted package → done at v2.0 re-baseline).
- **Signature deviation from PRD:** PRD illustrated `resolve_axes(client, brand_profile, report_meta)`; the real derivation needs the resolved hexes, so the signature is `resolve_axes(*, brand_profile, brand_primary, brand_accent)` (pure + the exact inputs the logic uses). No axis needs `report_meta`/`client` today.
- **Brand-agnostic:** value sets + hexes only; fixtures carry no client names; guard auto-covers `stages/resolve_axes.py`.
- **Determinism:** pure function, stdlib math, no clock/network.

---

## Unit 3 — Structured page DATA + charts + social-proof (PRD Unit 3, §8)

Build the typed DATA layer as NEW modules. **Field names match EXACTLY what the renderer patterns read** (verified empirically): list items the renderer also accepts as `"label: value"`/bare strings keep a `str` alternative in the union, and every model is `extra="allow"` + every field optional — so the typed view **never rejects valid current data** and **never blocks** (parse failure → warning + `GenericPageData`). Like the rest of Phase 2, nothing is wired into `main.py`/the package yet (Phase 4); the golden stays green.

> **Discriminator note (reconciliation):** PRD §5/§8.1 describe `data` as a Pydantic discriminated union. The raw `data` dict does NOT carry the ST type (it's on `ReportPage.type`), so a field-discriminated union can't apply directly. We realize the intent as a **registry dispatch keyed on the page's `st_type`** (`ST_TYPE_TO_PAGEDATA`) with a `GenericPageData(extra="allow")` fallback — identical behavior, simpler, and it mirrors the renderer's own `get_renderer` dispatch.

> **Forward note:** Tasks 3.3 (chart-spec union), 3.4 (social-proof models), 3.5 (the `structure_content` stage: deterministic chart extraction using the Task 3.1 parser + degrade-to-warning), and **Unit 4** (slot registry + pure `resolve_slots`) are appended after Tasks 3.1–3.2 land. The strict-LLM interpretive chart lane (PRD §8.3 lane ②) is deferred to Phase 4 (it's interpretive + adds cost; the deterministic lane covers literal numbers, which is the common case).

### Task 3.1: German-number parser (`stages/numbers.py`)

Only a *detector* regex (`validate_cover.py` `_NUMERIC_RE`) exists today — it cannot turn `"1.000,50"` into `1000.5`. Build a real parser the chart-extraction lane needs. Pure, brand-agnostic.

**Files:**
- Create: `stages/numbers.py`
- Create: `tests/test_numbers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_numbers.py`:

```python
"""Tests for the German-number parser."""
from __future__ import annotations

from stages.numbers import parse_german_number


def test_thousands_and_decimal() -> None:
    assert parse_german_number("1.000,50") == 1000.5


def test_currency_thousands() -> None:
    assert parse_german_number("290.100 €") == 290100.0
    assert parse_german_number("172.549 €") == 172549.0


def test_percent() -> None:
    assert parse_german_number("14%") == 14.0
    assert parse_german_number("50 %") == 50.0


def test_plain_thousands() -> None:
    assert parse_german_number("50.000") == 50000.0
    assert parse_german_number("10.000.000") == 10000000.0


def test_single_dot_decimal_tail_not_three() -> None:
    # a lone dot with a non-3-digit tail reads as a decimal point
    assert parse_german_number("1.5") == 1.5


def test_comma_decimal() -> None:
    assert parse_german_number("1,5") == 1.5


def test_embedded_in_prose() -> None:
    assert parse_german_number("von 763.840 € pro Jahr") == 763840.0


def test_none_on_garbage() -> None:
    assert parse_german_number("keine Zahl") is None
    assert parse_german_number("") is None
    assert parse_german_number(None) is None  # type: ignore[arg-type]
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_numbers.py -q` → FAIL (`No module named 'stages.numbers'`).

- [ ] **Step 3: Implement `stages/numbers.py`**

```python
"""parse_german_number — turn a German-formatted numeric string into a float.

German convention: '.' = thousands separator, ',' = decimal separator.
Strips surrounding currency/percent/words and parses the first number-like
token. Pure + deterministic + brand-agnostic. Built for the chart lane
(only a detector regex existed before).
"""
from __future__ import annotations

import re
from typing import Optional

_TOKEN = re.compile(r"-?\d[\d.,]*")


def parse_german_number(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    m = _TOKEN.search(str(text))
    if not m:
        return None
    tok = m.group(0)
    if "," in tok:
        # comma = decimal; any dots are thousands separators
        tok = tok.replace(".", "").replace(",", ".")
    elif tok.count(".") == 1 and len(tok.split(".")[1]) != 3:
        # a single dot whose tail is not 3 digits → decimal point ("1.5")
        pass
    else:
        # dots are thousands separators ("50.000", "10.000.000")
        tok = tok.replace(".", "")
    try:
        return float(tok)
    except ValueError:
        return None
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_numbers.py -q` → 8 passed.

- [ ] **Step 5: Checkpoint**

Full suite → expect **260 passed** (252 + 8). Guard + golden green.

### Task 3.2: `models_pagedata.py` — typed per-ST schemas + registry

**Files:**
- Create: `models_pagedata.py`
- Create: `tests/test_models_pagedata.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models_pagedata.py`:

```python
"""Tests for the typed per-ST page-data schemas + parse_page_data dispatch."""
from __future__ import annotations

from models_pagedata import (
    CaseStudyData,
    GenericPageData,
    IntroData,
    StatItem,
    parse_page_data,
)


def test_case_study_full_structured() -> None:
    data = {
        "kurzportraet": "kp", "ausgangsproblem": "ap", "ziel": "z", "loesung": "l",
        "ergebnis_text": "et", "ergebnis_headline": "eh", "fallstudie_number": 3,
        "ergebnis_metrics": [{"label": "Umsatz", "value": "+172%"}, "6 Wochen: Zeit"],
        "kunde": {"name": "N", "funktion": "F", "company_url": "https://k.test"},
        "pullquote": {"text": "great", "attribution": "N, F"},
    }
    parsed, warn = parse_page_data("ST-07A", data)
    assert warn is None
    assert isinstance(parsed, CaseStudyData)
    assert parsed.kunde.name == "N"
    assert parsed.pullquote.text == "great"
    assert isinstance(parsed.ergebnis_metrics[0], StatItem)
    assert parsed.ergebnis_metrics[0].label == "Umsatz"
    assert parsed.ergebnis_metrics[1] == "6 Wochen: Zeit"  # str fallback preserved


def test_missing_fields_validate_as_none() -> None:
    parsed, warn = parse_page_data("ST-07A", {})
    assert warn is None
    assert isinstance(parsed, CaseStudyData)
    assert parsed.kunde is None
    assert parsed.pullquote is None
    assert parsed.ergebnis_metrics == []


def test_extra_keys_preserved() -> None:
    parsed, warn = parse_page_data("ST-02", {"title": "t", "mystery": "keep me"})
    assert warn is None
    assert isinstance(parsed, IntroData)
    assert parsed.model_dump().get("mystery") == "keep me"


def test_unknown_type_is_generic_no_warning() -> None:
    parsed, warn = parse_page_data("ST-99", {"anything": 1})
    assert warn is None
    assert isinstance(parsed, GenericPageData)
    assert parsed.model_dump().get("anything") == 1


def test_bad_data_on_known_type_degrades_with_warning() -> None:
    # zielgruppe must be a list[str]; an int is invalid → degrade + warn
    parsed, warn = parse_page_data("ST-02", {"zielgruppe": 123})
    assert warn is not None and "ST-02" in warn
    assert isinstance(parsed, GenericPageData)


def test_non_dict_data_degrades() -> None:
    parsed, warn = parse_page_data("ST-01", ["not", "a", "dict"])  # type: ignore[arg-type]
    assert warn is not None
    assert isinstance(parsed, GenericPageData)


def test_cover_proof_stats_mixed_forms() -> None:
    parsed, warn = parse_page_data("ST-01", {
        "title": "T", "kicker_pills": ["a", "b"],
        "proof_stats": ["172%: Wachstum", {"value": "50k", "label": "Leads"}],
        "author": {"name": "A", "role": "Founder"},
    })
    assert warn is None
    assert parsed.kicker_pills == ["a", "b"]
    assert parsed.proof_stats[0] == "172%: Wachstum"
    assert isinstance(parsed.proof_stats[1], StatItem)
    assert parsed.author.role == "Founder"


def test_collaboration_steps_have_n_and_dauer() -> None:
    parsed, warn = parse_page_data("ST-22", {
        "title": "Ablauf",
        "steps": [{"n": 1, "title": "Kickoff", "body": "b", "dauer": "1 Woche"}, "freitext"],
    })
    assert warn is None
    assert parsed.steps[0].n == 1
    assert parsed.steps[0].dauer == "1 Woche"
    assert parsed.steps[1] == "freitext"
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_models_pagedata.py -q` → FAIL (`No module named 'models_pagedata'`).

- [ ] **Step 3: Implement `models_pagedata.py`**

```python
"""Typed per-ST page-data schemas (DNA §D recipes).

Field names match EXACTLY what the renderer patterns read (verified against
research/v7-renderer/patterns/*.py). Every field is optional/defaulted so
missing content validates (degrade, never block). List items the renderer
also accepts as "label: value"/bare strings keep a `str` alternative so the
typed view never rejects valid current data. Each model is extra="allow"
(unexpected keys are preserved, not rejected). Unknown ST types →
GenericPageData. parse_page_data() never raises.

Brand-agnostic: field NAMES + shapes only; no client value here.
"""
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_Permissive = ConfigDict(extra="allow")


# ───────────────────────── shared leaves ─────────────────────────
class StatItem(BaseModel):
    model_config = _Permissive
    value: Optional[str] = None
    label: Optional[str] = None


class Author(BaseModel):
    model_config = _Permissive
    name: Optional[str] = None
    role: Optional[str] = None


class Kunde(BaseModel):
    model_config = _Permissive
    name: Optional[str] = None
    funktion: Optional[str] = None
    company_url: Optional[str] = None


class PullQuote(BaseModel):
    model_config = _Permissive
    text: Optional[str] = None
    attribution: Optional[str] = None


class Step(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None


class CollabStep(BaseModel):
    model_config = _Permissive
    n: Optional[Union[int, str]] = None
    title: Optional[str] = None
    body: Optional[str] = None
    dauer: Optional[str] = None


class FaqItem(BaseModel):
    model_config = _Permissive
    frage: Optional[str] = None
    antwort: Optional[str] = None


class Symptom(BaseModel):
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None


class Belief(BaseModel):
    model_config = _Permissive
    irrglaube: Optional[str] = None
    realitaet: Optional[str] = None
    quelle: Optional[str] = None


class Compare(BaseModel):
    model_config = _Permissive
    ohne: list[str] = Field(default_factory=list)
    mit: list[str] = Field(default_factory=list)


# ───────────────────────── per-ST page data ─────────────────────────
class CoverData(BaseModel):           # ST-01
    model_config = _Permissive
    title: Optional[str] = None
    subtitle: Optional[str] = None
    kicker_pills: list[str] = Field(default_factory=list)
    proof_stats: list[Union[StatItem, str]] = Field(default_factory=list)
    author: Optional[Author] = None


class IntroData(BaseModel):           # ST-02
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    zielgruppe: list[str] = Field(default_factory=list)


class CtaData(BaseModel):             # ST-03
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    cta_url: Optional[str] = None
    cta_text: Optional[str] = None


class AboutData(BaseModel):           # ST-05
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    stats: list[Union[StatItem, str]] = Field(default_factory=list)
    partners: list[str] = Field(default_factory=list)
    credibility_points: list[str] = Field(default_factory=list)


class MechanismData(BaseModel):       # ST-06
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    steps: list[Union[Step, str]] = Field(default_factory=list)
    ergebnis: Optional[str] = None
    bars: list[Union[StatItem, str]] = Field(default_factory=list)
    metrics: list[Union[StatItem, str]] = Field(default_factory=list)


class CaseStudyData(BaseModel):       # ST-07A
    model_config = _Permissive
    kurzportraet: Optional[str] = None
    ausgangsproblem: Optional[str] = None
    ziel: Optional[str] = None
    loesung: Optional[str] = None
    ergebnis_text: Optional[str] = None
    ergebnis_headline: Optional[str] = None
    fallstudie_number: Optional[Union[int, str]] = None
    ergebnis_metrics: list[Union[StatItem, str]] = Field(default_factory=list)
    kunde: Optional[Kunde] = None
    pullquote: Optional[PullQuote] = None


class ComparisonData(BaseModel):      # ST-07B
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    key_insight: Optional[str] = None
    compare: Optional[Compare] = None


class FaqData(BaseModel):             # ST-08
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    intro: Optional[str] = None
    faqs: list[Union[FaqItem, str]] = Field(default_factory=list)


class ProblemData(BaseModel):         # ST-09
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    symptoms: list[Union[Symptom, str]] = Field(default_factory=list)


class MythsData(BaseModel):           # ST-14
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    beliefs: list[Union[Belief, str]] = Field(default_factory=list)


class CollaborationData(BaseModel):   # ST-22
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    steps: list[Union[CollabStep, str]] = Field(default_factory=list)


class AtmosphericData(BaseModel):     # ST-31 / ST-32
    model_config = _Permissive
    phrase: Optional[str] = None


class FazitData(BaseModel):           # ST-FAZIT
    model_config = _Permissive
    title: Optional[str] = None
    body: Optional[str] = None
    these: Optional[str] = None
    kosten_des_nichtstuns: Optional[str] = None
    cta_url: Optional[str] = None


class GenericPageData(BaseModel):     # fallback (unknown ST / parse failure)
    model_config = _Permissive


ST_TYPE_TO_PAGEDATA: dict[str, type[BaseModel]] = {
    "ST-01": CoverData,
    "ST-02": IntroData,
    "ST-03": CtaData,
    "ST-05": AboutData,
    "ST-06": MechanismData,
    "ST-07A": CaseStudyData,
    "ST-07B": ComparisonData,
    "ST-08": FaqData,
    "ST-09": ProblemData,
    "ST-14": MythsData,
    "ST-22": CollaborationData,
    "ST-31": AtmosphericData,
    "ST-32": AtmosphericData,
    "ST-FAZIT": FazitData,
}


def parse_page_data(st_type: str, data) -> tuple[BaseModel, Optional[str]]:
    """Parse a page's raw `data` into its typed model (dispatched by st_type).
    Unknown type → GenericPageData (no warning; passthrough is expected).
    ValidationError on a known type → GenericPageData + a warning. Never raises.
    """
    if not isinstance(data, dict):
        return GenericPageData(), f"{st_type}: data was not a dict; kept as generic"
    model_cls = ST_TYPE_TO_PAGEDATA.get(st_type)
    if model_cls is None:
        return GenericPageData.model_validate(data), None
    try:
        return model_cls.model_validate(data), None
    except ValidationError as exc:
        return (
            GenericPageData.model_validate(data),
            f"{st_type}: page-data parse failed ({exc.error_count()} error(s)); kept as generic",
        )
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_models_pagedata.py -q` → 8 passed.

- [ ] **Step 5: Checkpoint**

Full suite → expect **268 passed** (260 + 8). Guard + golden green.

### Task 3.3: Rhetorical chart-DATA models (`models_charts.py`)

The 6 chart kinds from DNA §C5 / PRD §3.4, as a discriminated union keyed on `kind` (these DO carry the discriminator — we construct them). Persuasion data only; the renderer (deferred) draws them. `parse_chart` validates a dict into the right variant; never raises.

**Files:**
- Create: `models_charts.py`
- Create: `tests/test_models_charts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models_charts.py`:

```python
"""Tests for rhetorical chart-data models + parse_chart dispatch."""
from __future__ import annotations

from models_charts import (
    BeforeAfterBars,
    ComparisonColumns,
    parse_chart,
)


def test_before_after_constructs_with_kind() -> None:
    c = BeforeAfterBars(before_value=172549.0, after_value=290100.0, unit="€")
    assert c.kind == "before_after_bars"
    assert c.after_value == 290100.0


def test_parse_before_after_from_dict() -> None:
    c, warn = parse_chart({
        "kind": "before_after_bars", "unit": "€",
        "before_label": "vorher", "before_value": 172549,
        "after_label": "nachher", "after_value": 290100,
    })
    assert warn is None
    assert isinstance(c, BeforeAfterBars)
    assert c.before_value == 172549.0   # coerced to float
    assert c.after_label == "nachher"


def test_parse_comparison_columns() -> None:
    c, warn = parse_chart({"kind": "comparison_columns",
                           "ohne": ["langsam", "teuer"], "mit": ["schnell", "guenstig"]})
    assert warn is None
    assert isinstance(c, ComparisonColumns)
    assert c.ohne == ["langsam", "teuer"]
    assert c.mit == ["schnell", "guenstig"]


def test_parse_cost_math_strip() -> None:
    c, warn = parse_chart({"kind": "cost_math_strip",
                           "operands": [100, 48, 220, 43.40], "operators": ["×", "×", "×"],
                           "result": 763840.0, "unit": "€"})
    assert warn is None
    assert c.kind == "cost_math_strip"
    assert c.result == 763840.0


def test_unknown_kind_returns_warning() -> None:
    c, warn = parse_chart({"kind": "pie_3d"})
    assert c is None
    assert warn is not None and "pie_3d" in warn


def test_missing_kind_returns_warning() -> None:
    c, warn = parse_chart({"before_value": 1})
    assert c is None
    assert warn is not None
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_models_charts.py -q` → FAIL (`No module named 'models_charts'`).

- [ ] **Step 3: Implement `models_charts.py`**

```python
"""Rhetorical chart-DATA models (DNA §C5). Persuasion data only — NO axis
chrome; the renderer draws. Each variant carries a `kind` discriminator.
parse_chart() validates a dict into the right variant by `kind`; never
raises. Brand-agnostic: chart shapes only, no client value.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

_P = ConfigDict(extra="allow")


class BeforeAfterBars(BaseModel):
    model_config = _P
    kind: Literal["before_after_bars"] = "before_after_bars"
    title: Optional[str] = None
    unit: Optional[str] = None
    before_label: Optional[str] = None
    before_value: Optional[float] = None
    after_label: Optional[str] = None
    after_value: Optional[float] = None


class LineSeries(BaseModel):
    model_config = _P
    name: Optional[str] = None
    points: list[float] = Field(default_factory=list)


class LineCompare(BaseModel):
    model_config = _P
    kind: Literal["line_compare"] = "line_compare"
    title: Optional[str] = None
    x_labels: list[str] = Field(default_factory=list)
    series: list[LineSeries] = Field(default_factory=list)


class DonutSegment(BaseModel):
    model_config = _P
    label: Optional[str] = None
    value: Optional[float] = None


class Donut(BaseModel):
    model_config = _P
    kind: Literal["donut"] = "donut"
    title: Optional[str] = None
    segments: list[DonutSegment] = Field(default_factory=list)


class MoneyItem(BaseModel):
    model_config = _P
    label: Optional[str] = None
    value: Optional[float] = None


class MoneyInfographic(BaseModel):
    model_config = _P
    kind: Literal["money_infographic"] = "money_infographic"
    title: Optional[str] = None
    currency: Optional[str] = "€"
    items: list[MoneyItem] = Field(default_factory=list)


class CostMathStrip(BaseModel):
    model_config = _P
    kind: Literal["cost_math_strip"] = "cost_math_strip"
    title: Optional[str] = None
    operands: list[float] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    result: Optional[float] = None
    unit: Optional[str] = None


class ComparisonColumns(BaseModel):
    model_config = _P
    kind: Literal["comparison_columns"] = "comparison_columns"
    title: Optional[str] = None
    ohne: list[str] = Field(default_factory=list)
    mit: list[str] = Field(default_factory=list)


ChartSpec = Annotated[
    Union[
        BeforeAfterBars, LineCompare, Donut,
        MoneyInfographic, CostMathStrip, ComparisonColumns,
    ],
    Field(discriminator="kind"),
]
_CHART_ADAPTER = TypeAdapter(ChartSpec)


def parse_chart(data) -> tuple[Optional[BaseModel], Optional[str]]:
    """Validate a dict (carrying a `kind`) into its ChartSpec variant.
    Returns (chart, None) on success, (None, warning) otherwise. Never raises.
    """
    if not isinstance(data, dict):
        return None, "chart: not a dict"
    if "kind" not in data:
        return None, "chart: missing 'kind'"
    try:
        return _CHART_ADAPTER.validate_python(data), None
    except ValidationError as exc:
        return None, f"chart[{data.get('kind')!r}]: invalid ({exc.error_count()} error(s))"
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_models_charts.py -q` → 6 passed.

- [ ] **Step 5: Checkpoint**

Full suite → expect **274 passed** (268 + 6). Guard + golden green.

### Task 3.4: Social-proof DATA models (`models_social.py`)

DNA §C4 — the credibility apparatus (ratings, reviews, logo lists). **Validated from agency-supplied content; NEVER LLM-synthesized** (fabricating social proof is forbidden — PRD §8.3). `parse_social_proof` validates a provided dict; absent → `None`; never invents.

**Files:**
- Create: `models_social.py`
- Create: `tests/test_models_social.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models_social.py`:

```python
"""Tests for social-proof models — validated, never invented."""
from __future__ import annotations

from models_social import RatingCard, ReviewCard, SocialProofBlock, parse_social_proof


def test_full_block() -> None:
    block, warn = parse_social_proof({
        "ratings": [{"platform": "Trustpilot", "score": 4.8, "count": 212, "verified": True}],
        "reviews": [{"name": "M.", "role": "CEO", "stars": 5, "text": "top", "date": "2025-01"}],
        "press_logos": [{"name": "Forbes"}],
        "client_logos": [{"name": "ACME", "asset_key": "client-logo-1"}],
    })
    assert warn is None
    assert isinstance(block, SocialProofBlock)
    assert block.ratings[0].platform == "Trustpilot"
    assert block.ratings[0].verified is True
    assert block.reviews[0].stars == 5.0
    assert block.client_logos[0].asset_key == "client-logo-1"
    assert block.client_logos[0].grayscale is True   # default


def test_absent_is_none_no_warning() -> None:
    block, warn = parse_social_proof(None)
    assert block is None
    assert warn is None


def test_empty_dict_is_empty_block_never_fabricated() -> None:
    block, warn = parse_social_proof({})
    assert warn is None
    assert block.ratings == [] and block.reviews == []
    assert block.press_logos == [] and block.client_logos == []


def test_partial_only_ratings() -> None:
    block, warn = parse_social_proof({"ratings": [{"platform": "Google", "score": 4.9}]})
    assert warn is None
    assert block.ratings[0].score == 4.9
    assert block.reviews == []


def test_bad_shape_returns_warning() -> None:
    block, warn = parse_social_proof({"ratings": "not-a-list"})
    assert block is None
    assert warn is not None


def test_models_construct_directly() -> None:
    assert RatingCard(platform="Capterra", score=4.7).max_score == 5.0
    assert ReviewCard(name="A").stars is None
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_models_social.py -q` → FAIL (`No module named 'models_social'`).

- [ ] **Step 3: Implement `models_social.py`**

```python
"""Social-proof DATA models (DNA §C4) — ratings, reviews, logo lists.

VALIDATED from agency-supplied content; NEVER LLM-synthesized (fabricating
social proof is forbidden). parse_social_proof validates a provided dict;
absent → None; never invents. Brand-agnostic: shapes only, no client value.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_P = ConfigDict(extra="allow")


class RatingCard(BaseModel):
    model_config = _P
    platform: Optional[str] = None
    score: Optional[float] = None
    max_score: float = 5.0
    count: Optional[int] = None
    verified: bool = False


class ReviewCard(BaseModel):
    model_config = _P
    name: Optional[str] = None
    role: Optional[str] = None
    stars: Optional[float] = None
    text: Optional[str] = None
    date: Optional[str] = None


class LogoItem(BaseModel):
    model_config = _P
    name: Optional[str] = None
    asset_key: Optional[str] = None
    grayscale: bool = True


class SocialProofBlock(BaseModel):
    model_config = _P
    ratings: list[RatingCard] = Field(default_factory=list)
    reviews: list[ReviewCard] = Field(default_factory=list)
    press_logos: list[LogoItem] = Field(default_factory=list)
    client_logos: list[LogoItem] = Field(default_factory=list)


def parse_social_proof(data) -> tuple[Optional[SocialProofBlock], Optional[str]]:
    """Validate provided social-proof content. None → (None, None) (no proof
    is fine). Invalid shape → (None, warning). NEVER fabricates."""
    if data is None:
        return None, None
    if not isinstance(data, dict):
        return None, "social_proof: not a dict"
    try:
        return SocialProofBlock.model_validate(data), None
    except ValidationError as exc:
        return None, f"social_proof: invalid ({exc.error_count()} error(s))"
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_models_social.py -q` → 6 passed.

- [ ] **Step 5: Checkpoint**

Full suite → expect **280 passed** (274 + 6). Guard + golden green.

### Task 3.5: `structure_content` stage (the integrator)

Tie Unit 3 together: a pure stage that, per page, produces typed `PageData` (via `parse_page_data`), `ChartSpec` data (explicit `chart`/`charts` keys + a deterministic before/after transform from a 2-item numeric stat list using the Task 3.1 parser), and a validated `SocialProofBlock` (never invented). Degrades to warnings, never blocks. Heavy carriers are dataclasses (ADR split). Not wired into the package (Phase 4).

**Files:**
- Create: `stages/structure_content.py`
- Create: `tests/test_structure_content.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_structure_content.py`:

```python
"""Tests for the structure_content stage."""
from __future__ import annotations

from types import SimpleNamespace

from models_charts import BeforeAfterBars
from models_pagedata import CaseStudyData, GenericPageData
from models_social import SocialProofBlock
from stages.structure_content import structure_content


def _page(slot, type_, data):
    return SimpleNamespace(slot=slot, type=type_, data=data)


def test_typed_data_per_page() -> None:
    sc = structure_content([_page(7, "ST-07A", {"kunde": {"name": "N"}, "ziel": "z"})])
    p = sc.pages[0]
    assert isinstance(p.data, CaseStudyData)
    assert p.data.kunde.name == "N"
    assert p.warnings == []


def test_before_after_auto_from_two_numeric_metrics() -> None:
    sc = structure_content([_page(7, "ST-07A", {
        "ergebnis_metrics": [
            {"label": "vorher", "value": "172.549 €"},
            {"label": "nachher", "value": "290.100 €"},
        ],
    })])
    charts = sc.pages[0].charts
    assert len(charts) == 1
    assert isinstance(charts[0], BeforeAfterBars)
    assert charts[0].before_value == 172549.0
    assert charts[0].after_value == 290100.0
    assert charts[0].before_label == "vorher"


def test_no_auto_chart_when_not_two_numeric() -> None:
    sc = structure_content([_page(6, "ST-06", {"metrics": [{"value": "x"}, {"value": "y"}, {"value": "z"}]})])
    assert sc.pages[0].charts == []


def test_explicit_chart_is_parsed() -> None:
    sc = structure_content([_page(6, "ST-06", {"chart": {"kind": "comparison_columns", "ohne": ["a"], "mit": ["b"]}})])
    charts = sc.pages[0].charts
    assert len(charts) == 1
    assert charts[0].kind == "comparison_columns"


def test_social_proof_validated() -> None:
    sc = structure_content([_page(10, "ST-10", {"social_proof": {"ratings": [{"platform": "Google", "score": 4.9}]}})])
    sp = sc.pages[0].social_proof
    assert isinstance(sp, SocialProofBlock)
    assert sp.ratings[0].platform == "Google"


def test_bad_data_degrades_and_collects_warning() -> None:
    sc = structure_content([_page(2, "ST-02", {"zielgruppe": 123})])
    p = sc.pages[0]
    assert isinstance(p.data, GenericPageData)
    assert p.warnings and "ST-02" in p.warnings[0]
    assert sc.warnings  # aggregated up


def test_accepts_dict_pages() -> None:
    sc = structure_content([{"slot": 2, "type": "ST-02", "data": {"title": "t"}}])
    assert sc.pages[0].st_type == "ST-02"
    assert sc.pages[0].data.title == "t"


def test_no_social_proof_is_none() -> None:
    sc = structure_content([_page(2, "ST-02", {"title": "t"})])
    assert sc.pages[0].social_proof is None
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_structure_content.py -q` → FAIL (`No module named 'stages.structure_content'`).

- [ ] **Step 3: Implement `stages/structure_content.py`**

```python
"""structure_content — turn raw report pages into a typed, structured view:
per-page typed PageData (by st_type), rhetorical ChartSpec data (explicit
chart/charts keys + a deterministic before/after transform from a 2-item
numeric stat list), and a validated SocialProofBlock (never invented).
Pure (no I/O); degrades to warnings, never blocks. Heavy carriers are
dataclasses (ADR split). Not wired into the package until a later phase.
Brand-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel

from models_charts import BeforeAfterBars, parse_chart
from models_pagedata import parse_page_data
from models_social import SocialProofBlock, parse_social_proof
from stages.numbers import parse_german_number

_STAT_FIELDS = ("ergebnis_metrics", "metrics", "bars", "stats")


@dataclass
class StructuredPage:
    slot: Optional[int]
    st_type: str
    data: BaseModel
    charts: list = field(default_factory=list)
    social_proof: Optional[SocialProofBlock] = None
    warnings: list = field(default_factory=list)


@dataclass
class StructuredContent:
    pages: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _get(page, key, default=None):
    if isinstance(page, dict):
        return page.get(key, default)
    return getattr(page, key, default)


def _stat_value_label(item):
    if isinstance(item, str):
        return parse_german_number(item), item
    return parse_german_number(getattr(item, "value", None)), getattr(item, "label", None)


def _before_after_from_stats(data_model) -> Optional[BeforeAfterBars]:
    """A 2-item stat list whose both values parse to numbers → a before/after."""
    for fname in _STAT_FIELDS:
        items = getattr(data_model, fname, None)
        if isinstance(items, list) and len(items) == 2:
            v0, l0 = _stat_value_label(items[0])
            v1, l1 = _stat_value_label(items[1])
            if v0 is not None and v1 is not None:
                return BeforeAfterBars(
                    before_label=l0, before_value=v0,
                    after_label=l1, after_value=v1,
                )
    return None


def structure_content(pages) -> StructuredContent:
    out_pages: list = []
    all_warnings: list = []
    for page in pages:
        slot = _get(page, "slot")
        st_type = _get(page, "type") or _get(page, "st_type") or ""
        raw = _get(page, "data") or {}

        data_model, warn = parse_page_data(st_type, raw)
        warnings: list = []
        if warn:
            warnings.append(warn)

        charts: list = []
        if isinstance(raw, dict):
            explicit = []
            if isinstance(raw.get("chart"), dict):
                explicit.append(raw["chart"])
            if isinstance(raw.get("charts"), list):
                explicit.extend(c for c in raw["charts"] if isinstance(c, dict))
            for cd in explicit:
                chart, cw = parse_chart(cd)
                if chart is not None:
                    charts.append(chart)
                elif cw:
                    warnings.append(cw)
        if not charts:
            auto = _before_after_from_stats(data_model)
            if auto is not None:
                charts.append(auto)

        social_proof = None
        if isinstance(raw, dict) and "social_proof" in raw:
            social_proof, spw = parse_social_proof(raw.get("social_proof"))
            if spw:
                warnings.append(spw)

        out_pages.append(StructuredPage(
            slot=slot, st_type=st_type, data=data_model,
            charts=charts, social_proof=social_proof, warnings=warnings,
        ))
        all_warnings.extend(warnings)

    return StructuredContent(pages=out_pages, warnings=all_warnings)
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_structure_content.py -q` → 8 passed.

- [ ] **Step 5: Checkpoint (Unit 3 complete)**

Full suite → expect **288 passed** (280 + 8). Guard + golden green.

### Unit 3 self-review
- **Coverage (PRD §8):** typed per-ST schemas matching the renderer's exact keys + str-fallback unions (§8.1) ✓; additive degrade-to-warning, never blocks (§8.2) ✓; chart-DATA union + deterministic literal-number lane via a real German parser (§8.3 lane ①) ✓; social-proof validated, never invented (§8.3 lane ③) ✓. **Deferred to Phase 4 (stated):** the strict-LLM interpretive chart lane (§8.3 lane ②) + wiring `structure_content` into the package.
- **Brand-agnostic / determinism:** pure functions, no client value, no clock/network; guard auto-covers all new modules.

---

## Unit 4 — Slot registry + pure resolver (PRD Unit 4, §7)

The declarative slot taxonomy (DNA §7.1) + a pure deterministic resolver that maps each page's slots to Drive/file names by naming convention, emitting `resolved` / `missing_required` / `absent` (DNA §7.3 — **never a blank box**: a required miss is a *named* error so Richard knows which file to add). Built as NEW modules that **do not touch `generate_assets.py`** — so its 22 tests + the golden stay green (the merge into the asset pipeline + the count-invariant update happen in Phase 3/4). `source` is `drive` for `founder_hero`/`client_portrait`/`team`, structurally forbidding a fal "fake person". The guarded `rapidfuzz` last-resort fuzzy match (PRD §7.2) is **deferred to Unit 7 (Drive)** where real filenames arrive — Phase 2 ships the deterministic convention matching (exact / indexed / prefix-glob, sorted), which is the "accurate every time" core and adds no dependency.

### Task 4.1: Slot taxonomy + recipe registry (`stages/slot_registry.py`)

**Files:**
- Create: `stages/slot_registry.py`
- Create: `tests/test_slot_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_slot_registry.py`:

```python
"""Tests for the slot taxonomy + per-ST recipe registry."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from stages.slot_registry import SlotSpec, recipe_for


def test_case_study_has_required_indexed_client_portrait() -> None:
    specs = recipe_for("ST-07A")
    kinds = {s.slot_kind for s in specs}
    assert "client_portrait" in kinds
    cp = next(s for s in specs if s.slot_kind == "client_portrait")
    assert cp.cardinality == "indexed"
    assert cp.required is True          # the empty-box fix: every Fallstudie needs a portrait
    assert cp.source == "drive"         # never generated (no fake person)
    assert cp.drive_key == "case-study-{n}"


def test_about_has_team_and_logo_walls() -> None:
    specs = recipe_for("ST-05")
    by_kind = {s.slot_kind: s for s in specs}
    assert by_kind["team"].source == "drive"
    assert by_kind["press_logo"].cardinality == "many"
    assert by_kind["client_logo"].cardinality == "many"


def test_cover_has_founder_hero_drive_and_generated_scene() -> None:
    specs = recipe_for("ST-01")
    by_kind = {s.slot_kind: s for s in specs}
    assert by_kind["founder_hero"].source == "drive"
    assert by_kind["scene"].source == "generate"


def test_human_kinds_are_never_generated() -> None:
    # founder/client/team must be sourced from Drive, never fal (no fabricated person)
    for st in ("ST-01", "ST-05", "ST-07A", "ST-FAZIT"):
        for s in recipe_for(st):
            if s.slot_kind in ("founder_hero", "client_portrait", "team"):
                assert s.source == "drive"


def test_unknown_type_has_empty_recipe() -> None:
    assert recipe_for("ST-99") == []


def test_slotspec_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        SlotSpec(slot_kind="unicorn")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_slot_registry.py -q` → FAIL (`No module named 'stages.slot_registry'`).

- [ ] **Step 3: Implement `stages/slot_registry.py`**

```python
"""Declarative slot taxonomy + per-ST recipes (DNA §D / §7.1).

Names slot KINDS + drive_key CONVENTIONS only — never a client (brand-
agnostic). `source="drive"` on founder/client/team structurally forbids a
fal "fake person". The pure resolver (resolve_slots) consumes these + a
file listing. Not wired into generate_assets yet (Phase 3/4).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

SlotKind = Literal[
    "founder_hero", "client_portrait", "team", "press_logo", "client_logo",
    "scene", "device_mockup", "texture", "gradient", "logo",
]
Cardinality = Literal["one", "indexed", "many"]
SlotSource = Literal["drive", "manifest", "generate", "composite"]


class SlotSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_kind: SlotKind
    cardinality: Cardinality = "one"
    source: SlotSource = "drive"
    required: bool = False
    aspect_ratio: str = "1x1"
    drive_key: Optional[str] = None    # convention stem: "founder", "case-study-{n}", "press-logo-*"


PAGE_TYPE_RECIPES: dict[str, list[SlotSpec]] = {
    "ST-01": [  # cover — founder hero (Drive) over a generated scene
        SlotSpec(slot_kind="founder_hero", source="drive", required=False, aspect_ratio="3x4", drive_key="founder"),
        SlotSpec(slot_kind="scene", source="generate", aspect_ratio="3x4"),
    ],
    "ST-05": [  # about — team photo + press/client logo walls
        SlotSpec(slot_kind="team", source="drive", required=False, aspect_ratio="4x3", drive_key="team"),
        SlotSpec(slot_kind="press_logo", cardinality="many", source="drive", aspect_ratio="3x2", drive_key="press-logo-*"),
        SlotSpec(slot_kind="client_logo", cardinality="many", source="drive", aspect_ratio="3x2", drive_key="client-logo-*"),
    ],
    "ST-07A": [  # case study — a named client portrait per Fallstudie ordinal
        SlotSpec(slot_kind="client_portrait", cardinality="indexed", source="drive", required=True, aspect_ratio="1x1", drive_key="case-study-{n}"),
        SlotSpec(slot_kind="device_mockup", source="composite", required=False, aspect_ratio="9x16"),
    ],
    "ST-09": [SlotSpec(slot_kind="scene", source="generate", aspect_ratio="16x9")],
    "ST-FAZIT": [
        SlotSpec(slot_kind="scene", source="generate", aspect_ratio="3x4"),
        SlotSpec(slot_kind="founder_hero", source="drive", required=False, aspect_ratio="1x1", drive_key="founder"),
    ],
    "ST-31": [SlotSpec(slot_kind="texture", source="generate", aspect_ratio="3x4")],
    "ST-32": [SlotSpec(slot_kind="texture", source="generate", aspect_ratio="3x4")],
}


def recipe_for(st_type: str) -> list[SlotSpec]:
    """The list of SlotSpecs for a page's ST type (empty if it needs no imagery)."""
    return PAGE_TYPE_RECIPES.get(st_type, [])
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_slot_registry.py -q` → 6 passed.

- [ ] **Step 5: Checkpoint**

Full suite → expect **294 passed** (288 + 6). Guard + golden green.

### Task 4.2: Pure deterministic resolver (`stages/resolve_slots.py`)

**Files:**
- Create: `stages/resolve_slots.py`
- Create: `tests/test_resolve_slots.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resolve_slots.py`:

```python
"""Tests for the pure, deterministic slot resolver."""
from __future__ import annotations

from stages.resolve_slots import normalize_name, resolve_slots


def test_normalize_name_cases() -> None:
    assert normalize_name("Founder_Photo.JPG") == "founder-photo"
    assert normalize_name("case study 1.png") == "case-study-1"
    assert normalize_name("press logo acme.png") == "press-logo-acme"
    assert normalize_name("founder-image-12.jpg") == "founder"      # trailing n8n suffix
    assert normalize_name("image-7-team.png") == "team"             # leading n8n prefix


def _by_kind(slots):
    out = {}
    for s in slots:
        out.setdefault(s.slot_kind, []).append(s)
    return out


def test_case_study_portrait_resolves_by_index() -> None:
    slots = resolve_slots("ST-07A", ["case-study-1.jpg", "other.png"], case_index=1)
    cp = _by_kind(slots)["client_portrait"][0]
    assert cp.status == "resolved"
    assert cp.path == "case-study-1.jpg"


def test_missing_required_client_portrait_is_named_error() -> None:
    slots = resolve_slots("ST-07A", ["case-study-1.jpg"], case_index=2)
    cp = _by_kind(slots)["client_portrait"][0]
    assert cp.status == "missing_required"
    assert cp.expected == "case-study-2"     # tells Richard the exact file to add


def test_indexed_without_index_is_missing_required() -> None:
    slots = resolve_slots("ST-07A", ["case-study-1.jpg"], case_index=None)
    assert _by_kind(slots)["client_portrait"][0].status == "missing_required"


def test_composite_slot_is_absent_for_downstream() -> None:
    slots = resolve_slots("ST-07A", [], case_index=1)
    dm = _by_kind(slots)["device_mockup"][0]
    assert dm.status == "absent"
    assert dm.source == "composite"


def test_many_logos_resolve_sorted_and_optional_miss_absent() -> None:
    listing = ["press-logo-wsj.png", "press-logo-forbes.png", "team.jpg"]
    slots = resolve_slots("ST-05", listing)
    by = _by_kind(slots)
    assert by["team"][0].status == "resolved"
    press = [s for s in by["press_logo"] if s.status == "resolved"]
    assert [s.path for s in press] == ["press-logo-forbes.png", "press-logo-wsj.png"]  # sorted
    assert by["client_logo"][0].status == "absent"   # none present, optional


def test_determinism_shuffled_listing_same_result() -> None:
    a = resolve_slots("ST-05", ["press-logo-b.png", "press-logo-a.png", "team.jpg"])
    b = resolve_slots("ST-05", ["team.jpg", "press-logo-a.png", "press-logo-b.png"])
    assert [(s.slot_kind, s.status, s.path) for s in a] == [(s.slot_kind, s.status, s.path) for s in b]


def test_cover_founder_optional_absent_when_missing() -> None:
    slots = resolve_slots("ST-01", [])
    by = _by_kind(slots)
    assert by["founder_hero"][0].status == "absent"   # optional miss
    assert by["scene"][0].status == "absent"          # generated downstream
```

- [ ] **Step 2: Run it — expect failure**

Run: `.venv/bin/python -m pytest tests/test_resolve_slots.py -q` → FAIL (`No module named 'stages.resolve_slots'`).

- [ ] **Step 3: Implement `stages/resolve_slots.py`**

```python
"""Pure, deterministic slot resolver: match a page's SlotSpecs against a
file/Drive listing by naming convention. Emits ResolvedSlot with status
resolved | missing_required | absent (DNA §7.3 — a required miss is a NAMED
error, never a blank box). No I/O; listing normalized once + many-slots
sorted, so a shuffled listing yields identical output. The guarded
rapidfuzz last-resort is deferred to the Drive unit. Brand-agnostic.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from stages.slot_registry import SlotSpec, recipe_for

SlotStatus = Literal["resolved", "missing_required", "absent"]


class ResolvedSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_kind: str
    source: str
    status: SlotStatus
    path: Optional[str] = None        # matched listing entry (drive/manifest)
    drive_key: Optional[str] = None
    index: Optional[int] = None       # for indexed slots
    expected: Optional[str] = None    # the key we looked for (missing_required messaging)
    warnings: list[str] = Field(default_factory=list)


def normalize_name(name: str) -> str:
    """lowercase, drop extension, [_/space]→-, collapse, drop n8n image-<n> affix."""
    s = name.strip().lower()
    s = re.sub(r"\.[a-z0-9]+$", "", s)     # extension
    s = re.sub(r"[_\s]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    s = re.sub(r"-image-\d+$", "", s)      # trailing n8n suffix
    s = re.sub(r"^image-\d+-", "", s)      # leading n8n prefix
    return s


def _miss(spec: SlotSpec, *, expected: Optional[str] = None, index: Optional[int] = None) -> ResolvedSlot:
    return ResolvedSlot(
        slot_kind=spec.slot_kind, source=spec.source,
        status="missing_required" if spec.required else "absent",
        drive_key=spec.drive_key, expected=expected or spec.drive_key, index=index,
    )


def resolve_slots(st_type: str, drive_listing, *, case_index: Optional[int] = None) -> list[ResolvedSlot]:
    """Resolve every SlotSpec for st_type against drive_listing (filenames).
    `case_index` binds an `indexed` slot to its Fallstudie ordinal."""
    pairs = sorted((normalize_name(n), n) for n in drive_listing)  # deterministic order
    out: list[ResolvedSlot] = []

    for spec in recipe_for(st_type):
        # generate/composite are produced downstream, not matched against Drive.
        if spec.source in ("generate", "composite"):
            out.append(ResolvedSlot(
                slot_kind=spec.slot_kind, source=spec.source, status="absent",
                drive_key=spec.drive_key, expected=spec.drive_key,
            ))
            continue

        if spec.cardinality == "many":
            stem = normalize_name((spec.drive_key or spec.slot_kind).replace("*", ""))
            matches = [orig for nk, orig in pairs if stem and (nk == stem or nk.startswith(stem + "-"))]
            if matches:
                for i, orig in enumerate(matches):
                    out.append(ResolvedSlot(
                        slot_kind=spec.slot_kind, source=spec.source, status="resolved",
                        path=orig, index=i, drive_key=spec.drive_key,
                    ))
            else:
                out.append(_miss(spec))
            continue

        if spec.cardinality == "indexed":
            if case_index is None:
                out.append(_miss(spec, index=None))
                continue
            key = (spec.drive_key or spec.slot_kind).replace("{n}", str(case_index))
            idx = case_index
        else:
            key = spec.drive_key or spec.slot_kind
            idx = None

        target = normalize_name(key)
        hit = next((orig for nk, orig in pairs if nk == target), None)
        if hit is not None:
            out.append(ResolvedSlot(
                slot_kind=spec.slot_kind, source=spec.source, status="resolved",
                path=hit, drive_key=spec.drive_key, index=idx, expected=key,
            ))
        else:
            out.append(_miss(spec, expected=key, index=idx))

    return out
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_resolve_slots.py -q` → 8 passed.

- [ ] **Step 5: Checkpoint (Unit 4 + Phase 2 complete)**

Full suite → expect **302 passed** (294 + 8). Guard + golden green.

### Unit 4 self-review
- **Coverage (PRD §7):** typed slot taxonomy + recipe registry (§7.1) ✓; pure deterministic convention-first resolver with normalization + sorted determinism (§7.2) ✓; `resolved`/`missing_required`/`absent` statuses, required-miss = a NAMED error, no blank box (§7.3) ✓; `source="drive"` on human kinds forbids a fal fake person (§7.3) ✓. **Deferred (stated):** the guarded `rapidfuzz` fuzzy last-resort → Unit 7 (Drive); merging the resolver into `generate_assets` + the count invariant → Phase 3/4.
- **Brand-agnostic / determinism:** registry names kinds + conventions only; resolver is pure + sorted; guard auto-covers both modules.

---

## Phase 2 — overall self-review
- **Units 2–4 complete:** axes (Unit 2), typed page-data + charts + social-proof + the integrator (Unit 3), slot registry + resolver (Unit 4). All NEW modules, none wired into the emitted package → the golden contract stayed green throughout (Phase 4 wires them at v2.0).
- **Test count:** 244 → **302** (+58), all green; guard green; golden green at every checkpoint.
- **Brand-agnostic + deterministic:** every new module is pure data/logic with no client value and no clock/network; the guard's `rglob` auto-covers them all.
- **Deferred to later phases (explicit):** wiring axes/structure_content/slots into the package + `/onboard` VisionAxes plumbing (Phase 4 / v2.0); the strict-LLM interpretive chart lane (§8.3 ②); the `rapidfuzz` fuzzy fallback (Unit 7); merging the resolver into the asset pipeline + count invariant (Phase 3/4).
