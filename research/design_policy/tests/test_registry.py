from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[3]
POLICY_ROOT = ROOT / "research" / "design_policy"
COMPOSITION_ROOT = ROOT / "research" / "composition_registry"
for path in (ROOT / "research", POLICY_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from composition_registry.registry import load_registry as load_composition_registry  # noqa: E402
from registry import (  # noqa: E402
    assert_composition_policy_bindings,
    load_design_policy_registry,
)
from schema import DesignPolicy, DesignPolicyRegistry  # noqa: E402


POLICY_PATH = POLICY_ROOT / "policies" / "dmc-print-v1.json"
SOURCE_PATH = POLICY_ROOT / "sources.json"
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"
COMPOSITION_PATH = COMPOSITION_ROOT / "families" / "dmc-v1.json"


def test_policy_rejects_missing_print_translation_or_owner() -> None:
    valid = json.loads(POLICY_PATH.read_text())["policies"][0]
    missing_translation = {**valid, "print_translation": ""}
    missing_owner = {**valid, "enforcement_owner": ""}

    with pytest.raises(ValidationError):
        DesignPolicy.model_validate(missing_translation)
    with pytest.raises(ValidationError):
        DesignPolicy.model_validate(missing_owner)


def test_policy_sources_and_atlas_evidence_resolve() -> None:
    registry = load_design_policy_registry(
        POLICY_PATH,
        sources_path=SOURCE_PATH,
        atlas_path=ATLAS_PATH,
    )

    assert len(registry.policies) >= 7
    assert registry.validated_policy_ids
    for policy in registry.policies:
        assert policy.source_references
        assert policy.atlas_face_ids
        assert policy.print_translation
        assert policy.enforcement_owner
        if policy.kind == "human_rubric" and policy.status == "experimental":
            assert policy.confidence in {"low", "medium"}


def test_all_composition_families_bind_only_validated_policies() -> None:
    policies = load_design_policy_registry(
        POLICY_PATH,
        sources_path=SOURCE_PATH,
        atlas_path=ATLAS_PATH,
    )
    compositions = load_composition_registry(
        COMPOSITION_PATH,
        atlas_path=ATLAS_PATH,
    )

    assert_composition_policy_bindings(compositions, policies)
    for family in compositions.families:
        assert family.design_policy_ids
        assert set(family.design_policy_ids) <= set(policies.validated_policy_ids)


def test_design_review_template_uses_registry_policy_ids() -> None:
    policies = DesignPolicyRegistry.model_validate(json.loads(POLICY_PATH.read_text()))
    template = json.loads(
        (ROOT / "research" / "quality_loop" / "design-review-template-v3.json").read_text()
    )

    assert template["policy_registry_version"] == policies.version
    assert set(template["policy_ids"]) <= {policy.policy_id for policy in policies.policies}
    assert all(row["observation"] and row["failure"] and row["remediation"] for row in template["rows"])
