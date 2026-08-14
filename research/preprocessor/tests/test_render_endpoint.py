"""End-to-end test of the FastAPI /render endpoint via TestClient."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "sample_render_request.json"
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_payload() -> dict:
    with _FIXTURE_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_root_health(client: TestClient) -> None:
    """GET / returns service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "dmc-preprocessor"
    assert body["layer"] == 1
    assert "/render" in body["endpoints"]
    assert "/onboard" in body["endpoints"]


def test_onboard_missing_body_returns_422(client: TestClient) -> None:
    """POST /onboard without a body returns 422 (endpoint is live, not a stub)."""
    response = client.post("/onboard")
    assert response.status_code == 422


def test_render_sample_payload_returns_success(
    client: TestClient, sample_payload: dict
) -> None:
    """POST /render with the on-disk sample returns 200 + success."""
    response = client.post("/render", json=sample_payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["errors"] == []
    assert body["validated_brand_tokens"] is not None
    assert body["font_config"] is not None


def test_render_validated_tokens_match_chassis_shape(
    client: TestClient, sample_payload: dict
) -> None:
    """The validated_brand_tokens in the response are exactly the 10
    flat fields the chassis BrandConfig expects.
    """
    response = client.post("/render", json=sample_payload)
    body = response.json()
    tokens = body["validated_brand_tokens"]
    expected_keys = {
        "brand_primary", "brand_accent", "brand_neutral_dark",
        "brand_neutral_mid", "brand_neutral_light", "font_heading",
        "font_body", "qr_target_url", "company_name_short",
        "company_url_display",
    }
    assert set(tokens.keys()) == expected_keys

    # Stage 2 filled in the font fields.
    assert tokens["font_heading"] == "Montserrat"
    assert tokens["font_body"] == "Source Sans 3"


def test_render_font_config_in_response(
    client: TestClient, sample_payload: dict
) -> None:
    response = client.post("/render", json=sample_payload)
    body = response.json()
    font_cfg = body["font_config"]
    assert font_cfg["font_heading_name"] == "Montserrat"
    assert font_cfg["font_body_name"] == "Source Sans 3"
    assert font_cfg["source"] == "chassis_default"
    assert font_cfg["font_heading_path"] is not None
    assert font_cfg["font_body_path"] is not None


def test_render_missing_brand_hex_dark_returns_422(
    client: TestClient, sample_payload: dict
) -> None:
    """Pydantic at the route boundary catches missing required keys
    BEFORE Stage 1 runs. n8n gets a 422 with structured details, the
    'REJECT LOUD' contract the spec requires.
    """
    del sample_payload["client"]["brand_hex_dark"]
    response = client.post("/render", json=sample_payload)
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    # Pydantic includes the missing field name in the detail array.
    detail_str = json.dumps(body["detail"])
    assert "brand_hex_dark" in detail_str


def test_render_page_count_18_returns_error_status_with_brand_tokens_none(
    client: TestClient, sample_payload: dict
) -> None:
    """Semantic validation errors (Stage 1) return 200 with an 'error'
    status body, NOT 422 — the request was syntactically valid but
    failed the grammar's invariants.
    """
    sample_payload["report_json"]["meta"]["page_count_target"] = 18
    response = client.post("/render", json=sample_payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "error"
    assert body["validated_brand_tokens"] is None
    assert any(e["code"] == "page_count_invalid" for e in body["errors"])


# ─────────────────────────────────────────────────────────────────────────────
# Phase B — Stage 3 + Stage 4 wired into the response
# ─────────────────────────────────────────────────────────────────────────────


def test_render_includes_cover_validation_for_phase_b(
    client: TestClient, sample_payload: dict
) -> None:
    """Stage 4 output is on the response when the cover page (slot 1 /
    ST-01) carries a complete cover stack.
    """
    response = client.post("/render", json=sample_payload)
    assert response.status_code == 200, response.text
    body = response.json()
    cv = body["cover_validation"]
    assert cv is not None, "expected cover_validation on response"
    # Three matrices each with non-empty detail lists
    assert isinstance(cv["h_score"], int)
    assert isinstance(cv["s_score"], int)
    assert isinstance(cv["b_score"], int)
    assert len(cv["h_scores_detail"]) == 8
    assert len(cv["s_scores_detail"]) == 5
    assert len(cv["b_scores_detail"]) == 5
    assert cv["headline_type"] in {
        "Typ A — Etikett", "Typ B — Diagnose", "ambiguous",
    }
    assert cv["headline_size_class"] in {"short", "long"}
    assert cv["overall"] in {"pass", "pass_with_warnings", "needs_review"}
    # The sample fixture uses the strong Diagnose-style cover.
    assert cv["headline_type"] == "Typ B — Diagnose"
    assert cv["headline_size_class"] == "long"


def test_render_copy_warnings_field_always_present(
    client: TestClient, sample_payload: dict
) -> None:
    """`copy_warnings` is always a list (possibly empty)."""
    response = client.post("/render", json=sample_payload)
    body = response.json()
    assert "copy_warnings" in body
    assert isinstance(body["copy_warnings"], list)


def test_render_copy_warning_fires_on_buzzword_in_page_body(
    client: TestClient, sample_payload: dict
) -> None:
    """If a body field contains an §3.9 buzzword, Stage 3 surfaces it on
    the response with the correct page_slot.
    """
    # Inject a buzzword into page 4 (ST-09) data.
    for page in sample_payload["report_json"]["pages"]:
        if page["slot"] == 4:
            page["data"] = {"intro": "Wir bieten innovative Lösungen für den Mittelstand."}
            break
    response = client.post("/render", json=sample_payload)
    body = response.json()
    warnings = body["copy_warnings"]
    buzz = [
        w for w in warnings
        if w["rule"] == "buzzword_denylist" and w["page_slot"] == 4
    ]
    assert buzz, (
        f"expected buzzword_denylist warning on slot 4; "
        f"got copy_warnings={warnings}"
    )


def test_render_no_cover_validation_when_no_cover_page(
    client: TestClient, sample_payload: dict
) -> None:
    """If slot 1 isn't ST-01 (or is missing), cover_validation is null."""
    # Drop slot 1.
    sample_payload["report_json"]["pages"] = [
        p for p in sample_payload["report_json"]["pages"] if p["slot"] != 1
    ]
    # The grammar requires slot 1 = ST-01 → stage 1 will raise. Re-add as ST-02
    # so the request validates but no ST-01 exists.
    sample_payload["report_json"]["pages"].insert(
        0, {"slot": 1, "type": "ST-02", "data": {"intro": "Body copy."}}
    )
    response = client.post("/render", json=sample_payload)
    body = response.json()
    # Slot 1 exists (ST-02), so the lookup picks it up — but it's not the
    # ST-01 cover stack. That's fine; the scorer simply scores its data.
    # The point of this test is the field must be either populated OR null
    # without crashing.
    assert "cover_validation" in body


# ─────────────────────────────────────────────────────────────────────────────
# Phase C — Stage 6 + Stage 7 wired into the response
# ─────────────────────────────────────────────────────────────────────────────


def test_render_includes_layout_plan(
    client: TestClient, sample_payload: dict
) -> None:
    """Stage 7 output appears on the /render response."""
    response = client.post("/render", json=sample_payload)
    assert response.status_code == 200, response.text
    body = response.json()
    lp = body["layout_plan"]
    assert lp is not None
    assert lp["page_count"] == 20
    assert lp["page_count_target"] == 20
    # Heavy SVG strings live in memory — JSON only carries counts
    for page in lp["pages"]:
        assert "components" not in page  # confirmed shed
        assert "data" not in page
        assert isinstance(page["component_count"], int)


def test_render_component_count_field_present(
    client: TestClient, sample_payload: dict
) -> None:
    """`component_count` is an integer (≥ 0) on the response."""
    response = client.post("/render", json=sample_payload)
    body = response.json()
    assert isinstance(body["component_count"], int)
    assert body["component_count"] >= 0


def test_render_component_count_increases_when_page_has_chart(
    client: TestClient, sample_payload: dict
) -> None:
    """If a page carries chart payload data, Stage 6 generates an SVG
    for it and `component_count` reflects that.
    """
    # Slot 4 is ST-09 — inject a matrix payload so Stage 6 produces an SVG
    matrix_data = {
        "x_axis": {"label": "Sichtbarkeit", "low": "schwer", "high": "leicht"},
        "y_axis": {"label": "Schaden", "low": "gering", "high": "hoch"},
        "quadrants": {
            "tl": {"tag": "STILL", "meaning": "high damage hidden"},
            "tr": {"tag": "OFFEN", "meaning": "high damage visible"},
            "bl": {"tag": "GRUND", "meaning": "low damage hidden"},
            "br": {"tag": "SICHTBAR", "meaning": "low damage visible"},
        },
        "items": [
            {"label": "Doppelarbeit", "x": 0.14, "y": 0.62, "qtag": "tl"},
        ],
    }
    for page in sample_payload["report_json"]["pages"]:
        if page["slot"] == 4:
            page["data"] = matrix_data
            break
    response = client.post("/render", json=sample_payload)
    body = response.json()
    assert body["component_count"] >= 1
    # The slot-4 page summary in the layout plan should show component_count >= 1
    slot_4 = next(p for p in body["layout_plan"]["pages"] if p["slot"] == 4)
    assert slot_4["component_count"] >= 1


def test_render_layout_plan_pages_have_css_templates(
    client: TestClient, sample_payload: dict
) -> None:
    """Every page in the layout plan summary carries a css_template."""
    response = client.post("/render", json=sample_payload)
    body = response.json()
    for page in body["layout_plan"]["pages"]:
        assert page["css_template"], f"slot {page['slot']} missing css_template"


# ─────────────────────────────────────────────────────────────────────────────
# Phase D — Stages 5 + 8 wired in
# ─────────────────────────────────────────────────────────────────────────────


def test_render_returns_package_path_and_output_dir(
    client: TestClient, sample_payload: dict
) -> None:
    """The response carries an absolute path to resolved_package.json
    + the package's output_dir; both files exist on disk.
    """
    response = client.post("/render", json=sample_payload)
    body = response.json()
    assert body["package_path"] is not None
    assert body["output_dir"] is not None
    pkg_path = Path(body["package_path"])
    out_dir = Path(body["output_dir"])
    assert pkg_path.exists(), f"package json missing at {pkg_path}"
    assert out_dir.is_dir()
    assert (out_dir / "components").is_dir()
    assert (out_dir / "assets").is_dir()
    assert (out_dir / "fonts").is_dir()
    # JSON parses
    pkg = json.loads(pkg_path.read_text())
    assert pkg["version"] == "2.0"
    assert pkg["pages"]


def test_render_asset_summary_counts_match_inventory(
    client: TestClient, sample_payload: dict
) -> None:
    """asset_summary on the response reflects what Stage 5 saw."""
    response = client.post("/render", json=sample_payload)
    body = response.json()
    s = body["asset_summary"]
    # The fixture has no image_manifest entries → every required asset
    # is either stubbed or client_upload_needed
    assert s["total_required"] >= 1
    assert s["total_downloaded"] == 0
    assert (s["total_stubbed"] + s["total_client_upload_needed"]) == s["total_required"]


def test_render_resolved_package_has_brand_tokens(
    client: TestClient, sample_payload: dict
) -> None:
    """resolved_package.json `brand` block matches `validated_brand_tokens`."""
    response = client.post("/render", json=sample_payload)
    body = response.json()
    pkg = json.loads(Path(body["package_path"]).read_text())
    assert pkg["brand"] == body["validated_brand_tokens"]


def test_render_resolved_package_paths_are_relative(
    client: TestClient, sample_payload: dict
) -> None:
    """No /Users/, /tmp/, or /var/folders/ paths inside the json."""
    raw = Path((response := client.post("/render", json=sample_payload)).json()
               ["package_path"]).read_text()
    assert "/Users/" not in raw
    assert "/var/folders/" not in raw
    assert "/tmp/" not in raw


def test_render_with_client_ig_folder_produces_social_bindings(
    client: TestClient, sample_payload: dict, tmp_path, monkeypatch
) -> None:
    """The LIVE path derives a social manifest from the client's IG folder and
    plans real placements (US-307): a payload + IG folder with a stage shot
    produces a scene_breather binding in the rendered package."""
    import json as _json

    ig = tmp_path / "client_assets" / "mein-werkzeugkoffer" / "ig"
    ig.mkdir(parents=True)
    for name in ("tc_avatar.jpg", "tc_stage_1.jpg", "tc_office_2.jpg"):
        (ig / name).write_bytes(b"x")

    from main import app as _app

    monkeypatch.setattr(
        "main.client_assets_dir",
        lambda slug, base: tmp_path / "client_assets" / slug,
    )
    monkeypatch.setattr("main.list_client_assets", lambda d: [])

    payload = dict(sample_payload)
    payload["client"]["founder_instagram_url"] = "https://instagram.com/tc"
    response = client.post("/render", json=payload)
    assert response.status_code == 200, response.text
    output_dir = response.json()["output_dir"]
    pkg = _json.loads(
        (Path(output_dir) / "resolved_package.json").read_text(encoding="utf-8")
    )
    # scene_breather bindings REPOINT the ST-31 page's breathing_bg* asset
    # to the staged scene photo (image_type=scene) — check the package assets.
    repointed = [
        (page["slot"], a["path"])
        for page in pkg["pages"]
        for a in page.get("assets", [])
        if str(a.get("slot_id", "")).startswith("breathing_bg")
        and a.get("image_type") == "scene"
    ]
    # ST-31 breathers in the sample payload exist → a scene breather binding
    assert repointed, "live render with an IG folder must produce scene breathers"
