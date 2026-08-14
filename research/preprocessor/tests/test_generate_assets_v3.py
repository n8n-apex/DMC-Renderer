"""Image generation is a paid call. It must never happen by default."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from stages.generate_assets_v3 import AssetGenerationPolicy, GenerationOutcome


def test_the_default_policy_cannot_spend() -> None:
    """No policy, no key, no ceiling: nothing generates."""
    assert AssetGenerationPolicy().enabled is False
    assert AssetGenerationPolicy().max_generations == 0
    assert AssetGenerationPolicy().resolved_key() is None


def test_enabling_without_a_ceiling_still_cannot_spend() -> None:
    """`enabled` alone is not permission; an explicit ceiling is required."""
    policy = AssetGenerationPolicy(enabled=True, max_generations=0)

    assert policy.resolved_key() is None


def test_a_ceiling_without_enabling_still_cannot_spend() -> None:
    policy = AssetGenerationPolicy(enabled=False, max_generations=50)

    assert policy.resolved_key() is None


def test_both_together_resolve_the_key_from_the_named_env_var(monkeypatch) -> None:
    monkeypatch.setenv("TEST_FAL_KEY", "k-123")
    policy = AssetGenerationPolicy(
        enabled=True, max_generations=3, fal_key_env="TEST_FAL_KEY"
    )

    assert policy.resolved_key() == "k-123"


def test_a_missing_key_is_not_invented(monkeypatch) -> None:
    monkeypatch.delenv("ABSENT_KEY", raising=False)
    policy = AssetGenerationPolicy(
        enabled=True, max_generations=3, fal_key_env="ABSENT_KEY"
    )

    assert policy.resolved_key() is None


def test_the_outcome_says_plainly_when_nothing_was_allowed() -> None:
    outcome = GenerationOutcome(planned=11, skipped_no_permission=11)

    assert "generation is off" in outcome.summary()
    assert "11 image(s) would be generated" in outcome.summary()


def test_no_network_call_can_happen_without_a_resolved_key(monkeypatch) -> None:
    """The guard is the key being None, so prove None is what reaches fal."""
    seen = {}

    async def _fake_generate(pages, manifest, **kwargs):
        seen.update(kwargs)
        class _Plan:
            results = ()
        return _Plan()

    import stages.generate_assets as real
    monkeypatch.setattr(real, "generate_assets", _fake_generate)
    from stages import generate_assets_v3

    generate_assets_v3.plan_or_generate(
        [], {}, brand_primary="#000000", brand_accent="#ffffff",
        output_dir=Path("/tmp/does-not-matter"),
    )

    assert seen["fal_key"] is None
    assert seen["max_generations_per_report"] == 0
