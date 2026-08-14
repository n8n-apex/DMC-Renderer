"""Tests for Stage Onboard-0 — capture (Playwright session)."""

from __future__ import annotations

import pytest

from stages.onboard import capture as cap
from models_onboard import OnboardRequest


def test_dom_eval_js_is_nonempty_and_has_key_tokens() -> None:
    js = cap.DOM_EVAL_JS
    assert isinstance(js, str) and len(js) > 50
    assert "getComputedStyle" in js
    assert "fontFamily" in js
    assert "cssVars" in js


def test_looks_blank_true_for_empty_signal() -> None:
    assert cap._looks_blank({"sampledColors": [], "bodyText": ""}) is True


def test_looks_blank_false_with_content() -> None:
    assert cap._looks_blank(
        {"sampledColors": ["rgb(1,2,3)"], "bodyText": "Hello world"}
    ) is False


def test_consent_selectors_nonempty() -> None:
    assert len(cap.CONSENT_TEXTS) > 0
    assert any("akzeptier" in t.lower() for t in cap.CONSENT_TEXTS)


@pytest.mark.anyio
async def test_capture_maps_fake_session(tmp_path, monkeypatch) -> None:
    from tests._onboard_fakes import fake_async_playwright
    monkeypatch.setattr(cap, "async_playwright", fake_async_playwright(
        raw_dom_eval={"cssVars": {}, "fontHead": "Montserrat, sans-serif",
                      "fontBody": "Arial", "sampledColors": ["rgb(1,2,3)"],
                      "bodyText": "Hi", "logoUrl": None},
    ))
    result = await cap.capture(
        OnboardRequest(record_id="r", website_url="https://x.de"),
        output_dir=tmp_path,
    )
    assert result.status == "ok"
    assert result.hero_png is not None
    assert result.raw_dom_eval["fontHead"].startswith("Montserrat")


@pytest.mark.anyio
async def test_capture_navigation_error_returns_status(tmp_path, monkeypatch) -> None:
    from tests._onboard_fakes import fake_async_playwright
    monkeypatch.setattr(cap, "async_playwright", fake_async_playwright(raise_on_goto=True))
    result = await cap.capture(
        OnboardRequest(record_id="r", website_url="https://x.de"),
        output_dir=tmp_path,
    )
    assert result.status in ("nav_error", "timeout")
    assert result.hero_png is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
