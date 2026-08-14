"""Tests for the typed Settings object."""
from __future__ import annotations

from settings import Settings


def _fresh(**env) -> Settings:
    # _env_file=None → ignore any on-disk .env so tests are deterministic.
    return Settings(_env_file=None, **env)


def test_defaults_match_prior_literals(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    s = _fresh()
    assert s.openrouter_vision_model == "anthropic/claude-sonnet-4.6"
    assert s.openrouter_brief_model == "anthropic/claude-opus-4.6"
    assert s.openrouter_prompt_model == "anthropic/claude-sonnet-4.6"
    assert s.fal_image_model == "fal-ai/nano-banana-pro"
    assert s.fal_image_resolution == "2K"
    assert s.max_generations_per_report == 12
    assert s.openrouter_key_str() is None
    assert s.fal_key_str() is None


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("FAL_IMAGE_MODEL", "fal-ai/flux-2")
    monkeypatch.setenv("MAX_GENERATIONS_PER_REPORT", "5")
    s = Settings(_env_file=None)
    assert s.fal_image_model == "fal-ai/flux-2"
    assert s.max_generations_per_report == 5


def test_secret_is_masked_but_readable() -> None:
    s = _fresh(openrouter_api_key="super-secret-token", fal_key="fal-token")
    assert "super-secret-token" not in repr(s)
    assert "super-secret-token" not in str(s)
    assert s.openrouter_key_str() == "super-secret-token"
    assert s.fal_key_str() == "fal-token"
