"""Strict loading and registry validation for frozen v3 render contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parent
PREPROCESSOR_ROOT = RESEARCH_ROOT / "preprocessor"
for dependency_root in (RESEARCH_ROOT, PREPROCESSOR_ROOT):
    if str(dependency_root) not in sys.path:
        sys.path.insert(0, str(dependency_root))

from composition_registry.schema import CompositionRegistry  # noqa: E402
from contracts_v3.render_contract import FrozenRenderContractV3  # noqa: E402


class ContractLoadFailure(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.owner_stage = "contract_loader"
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _parse_contract(
    source: FrozenRenderContractV3 | Path | dict,
) -> FrozenRenderContractV3:
    if isinstance(source, FrozenRenderContractV3):
        return source
    if isinstance(source, Path):
        source = json.loads(source.read_text(encoding="utf-8"))
    return FrozenRenderContractV3.model_validate(source)


def load_render_contract(
    source: FrozenRenderContractV3 | Path | dict,
    registry: CompositionRegistry,
) -> FrozenRenderContractV3:
    contract = _parse_contract(source)
    family_by_key = {
        (family.family_id, family.version): family for family in registry.families
    }
    for fragment in contract.fragments:
        key = (
            fragment.composition.family_id,
            fragment.composition.family_version,
        )
        family = family_by_key.get(key)
        if family is None:
            raise ContractLoadFailure(
                "unknown_family",
                f"{key[0]}@{key[1]} is not in registry {registry.version}",
            )
        variants = {variant.variant_id for variant in family.variants}
        if fragment.composition.variant_id not in variants:
            raise ContractLoadFailure(
                "unsupported_variant",
                f"{fragment.composition.variant_id} is not valid for {key[0]}@{key[1]}",
            )
        if fragment.fallback_family_id is not None:
            # The contract names only the fallback FAMILY, not its version;
            # families version independently (theory_interpretation is 1.5.0
            # while the editorial_lead primary is 1.4.0). Look it up by id
            # across every registered version instead of the primary's.
            fallback = next(
                (
                    item
                    for (family_id, _version), item in family_by_key.items()
                    if family_id == fragment.fallback_family_id
                ),
                None,
            )
            if fallback is None:
                raise ContractLoadFailure(
                    "unknown_fallback_family",
                    fragment.fallback_family_id,
                )
    return contract
