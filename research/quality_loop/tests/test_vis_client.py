"""Tests for the vision layer (Task B): the brand-agnostic prompt builder
(``vis_prompt``) and the swappable vision client (``vis_client``).

ALL tests here are offline: they use ``FakeVisionClient`` or exercise pure
functions. No real OpenRouter / network call is ever made. The real client is
only constructed (never invoked against the network) to prove it fails loudly
on a missing key instead of issuing a malformed request.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from vis_client import _loads_lenient


def test_vis_cache_key_tracks_model_and_prompt(tmp_path) -> None:
    from vis_client import cache_key
    page = tmp_path / "p.png"; page.write_bytes(b"PNG")
    ref = tmp_path / "r.png"; ref.write_bytes(b"REF")
    rows = ["P05", "N08"]
    base = cache_key(str(page), [str(ref)], rows, model="m1", prompt_sig="s1")
    assert base == cache_key(str(page), [str(ref)], rows, model="m1", prompt_sig="s1")
    assert base != cache_key(str(page), [str(ref)], rows, model="m2", prompt_sig="s1")
    assert base != cache_key(str(page), [str(ref)], rows, model="m1", prompt_sig="s2")


def test_loads_lenient_parses_plain_and_fenced_json():
    """Some OpenRouter providers (Anthropic family) wrap JSON in a ```json```
    fence even under json_object mode; the parser must tolerate that."""
    plain = '{"P05": {"score": 3, "rationale": "ok"}}'
    fenced = "```json\n" + plain + "\n```"
    fenced_bare = "```\n" + plain + "\n```"
    prose = 'Here is the result:\n```json\n' + plain + "\n```\nDone."
    expected = {"P05": {"score": 3, "rationale": "ok"}}
    assert _loads_lenient(plain) == expected
    assert _loads_lenient(fenced) == expected
    assert _loads_lenient(fenced_bare) == expected
    assert _loads_lenient(prose) == expected


def test_call_openrouter_parses_fenced_reply(tmp_path, monkeypatch):
    """End-to-end parse-path guard: an Anthropic-style FENCED json_object reply,
    fed through the real ``score_page`` -> ``_call_openrouter`` path with httpx
    mocked, must parse (this is the bug that broke the configured default model).
    No network: ``httpx.Client`` is monkeypatched."""
    import httpx

    from vis_client import VisionClient

    page = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(page)
    ref = tmp_path / "ref.png"
    Image.new("RGB", (8, 8), "black").save(ref)

    fenced = "```json\n" + '{"P05": {"score": 3, "rationale": "framed"}}' + "\n```"

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": fenced}}]}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):  # noqa: A002
            return _FakeResp()

    monkeypatch.setattr(httpx, "Client", _FakeClient)

    client = VisionClient(
        api_key="test-key",
        model="anthropic/claude-sonnet-4.6",
        cache_dir=tmp_path / "cache",
    )
    out = client.score_page(str(page), [str(ref)], ["P05"])
    assert out == {"P05": {"score": 3, "rationale": "framed"}}


# --------------------------------------------------------------------------- #
# configurable vision endpoint (provider-agnostic: OpenRouter / local / self-host)
# --------------------------------------------------------------------------- #
def test_api_base_defaults_to_openrouter() -> None:
    """With nothing configured, the client targets the OpenRouter endpoint."""
    from vis_client import VisionClient, _OPENROUTER_URL

    assert VisionClient(api_key="k", model="m")._api_base == _OPENROUTER_URL


def test_api_base_explicit_arg_and_env_override(monkeypatch) -> None:
    """An explicit api_base wins; otherwise VISION_API_BASE from the env wins
    over the default, so pointing at a local Ollama / self-hosted vLLM endpoint
    is a config flip, never a code change."""
    from vis_client import VisionClient

    explicit = "http://localhost:11434/v1/chat/completions"
    assert VisionClient(api_key="k", api_base=explicit)._api_base == explicit

    monkeypatch.setenv(
        "VISION_API_BASE", "http://gpu.internal:8000/v1/chat/completions"
    )
    assert (
        VisionClient(api_key="k")._api_base
        == "http://gpu.internal:8000/v1/chat/completions"
    )


def test_score_page_posts_to_configured_base(tmp_path, monkeypatch) -> None:
    """The configured endpoint is the URL actually posted to (proves the wiring
    uses self._api_base, not the hardcoded constant). No network."""
    import httpx

    from vis_client import VisionClient

    page = tmp_path / "p.png"
    Image.new("RGB", (8, 8), "white").save(page)
    ref = tmp_path / "r.png"
    Image.new("RGB", (8, 8), "black").save(ref)
    posted: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {"message": {"content": '{"P05": {"score": 2, "rationale": "ok"}}'}}
                ]
            }

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):  # noqa: A002
            posted["url"] = url
            return _Resp()

    monkeypatch.setattr(httpx, "Client", _Client)

    base = "http://localhost:11434/v1/chat/completions"
    client = VisionClient(
        api_key="k", model="m", api_base=base, cache_dir=tmp_path / "cache"
    )
    client.score_page(str(page), [str(ref)], ["P05"])
    assert posted["url"] == base


from vis_prompt import QUESTIONS, build_prompt
from vis_client import FakeVisionClient, VisionClient, cache_key


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_png(path: Path, color: tuple[int, int, int]) -> str:
    """Write a tiny valid PNG of a solid color and return its str path."""
    Image.new("RGB", (4, 4), color).save(path, format="PNG")
    return str(path)


# --------------------------------------------------------------------------- #
# 1. prompt is brand-agnostic
# --------------------------------------------------------------------------- #
def test_prompt_is_brand_agnostic() -> None:
    system, user = build_prompt(["P05", "N08"], 3)
    combined = f"{system}\n{user}"
    low = combined.lower()

    # the guardrail intent
    assert "composition" in low
    assert "ignore brand col" in low  # "ignore brand colours/colors..."
    assert ("do not reward or penalise" in low) or ("do not reward or penalize" in low)

    # the selected questions are present (verbatim from QUESTIONS)
    assert QUESTIONS["P05"] in combined
    assert QUESTIONS["N08"] in combined

    # mentions the reference count and which image is ours
    assert "3" in combined
    assert "first image" in low and "our" in low

    # brand-agnostic: no client names, no hex colors
    for banned in ("apex", "niklas", "boss"):
        assert banned not in low, f"client name {banned!r} leaked into prompt"
    assert "#" not in combined, "a hex/# leaked into the prompt"


# --------------------------------------------------------------------------- #
# 2. fake client returns exactly the requested rows
# --------------------------------------------------------------------------- #
def test_fake_client_returns_requested_rows() -> None:
    fake = FakeVisionClient({
        "P05": {"score": 3, "rationale": "x"},
        "N08": {"score": 2, "rationale": "y"},
        "P01": {"score": 0, "rationale": "z"},
    })
    out = fake.score_page("a.png", ["b.png"], ["P05", "N08"])

    assert set(out.keys()) == {"P05", "N08"}
    assert all(isinstance(out[r]["score"], int) for r in out)
    assert out["P05"]["score"] == 3
    assert out["N08"]["score"] == 2

    # call recording (for later wiring assertions)
    assert fake.calls == [("a.png", ["b.png"], ["P05", "N08"])]


# --------------------------------------------------------------------------- #
# 3. cache key is deterministic + sensitive to every input
# --------------------------------------------------------------------------- #
def test_cache_key_deterministic_and_sensitive(tmp_path: Path) -> None:
    p1 = _make_png(tmp_path / "page1.png", (10, 20, 30))
    p2 = _make_png(tmp_path / "page2.png", (200, 100, 50))  # different bytes
    r = _make_png(tmp_path / "refA.png", (0, 0, 0))
    r2 = _make_png(tmp_path / "refB.png", (255, 255, 255))

    rows = ["P05", "N08"]

    # stable
    assert cache_key(p1, [r], rows) == cache_key(p1, [r], rows)
    # order of row_ids must not matter (sorted internally)
    assert cache_key(p1, [r], rows) == cache_key(p1, [r], ["N08", "P05"])
    # sensitive to the page bytes
    assert cache_key(p1, [r], rows) != cache_key(p2, [r], rows)
    # sensitive to the reference bytes
    assert cache_key(p1, [r], rows) != cache_key(p1, [r2], rows)
    # sensitive to the row set
    assert cache_key(p1, [r], rows) != cache_key(p1, [r], ["P05"])


# --------------------------------------------------------------------------- #
# 4. real client constructs without a key, fails loudly on use (no network)
# --------------------------------------------------------------------------- #
def test_real_client_constructs_without_key_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Isolate from the dev machine's real secrets so "no key" truly means none:
    # blank the env var and point the .env reader at a non-existent file.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("vis_client._ENV_PATH", tmp_path / "nope.env")

    # Construction must never touch the network or require a key.
    client = VisionClient(api_key=None, model="google/gemini-2.0-flash-001")
    assert client.model == "google/gemini-2.0-flash-001"

    page = _make_png(tmp_path / "p.png", (1, 2, 3))
    ref = _make_png(tmp_path / "r.png", (4, 5, 6))

    # Calling without a key must raise a CLEAR error mentioning the missing key
    # rather than building a malformed request / hitting the network.
    with pytest.raises(ValueError) as exc:
        client.score_page(page, [ref], ["P05"])
    assert "key" in str(exc.value).lower()
