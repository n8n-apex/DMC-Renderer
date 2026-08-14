"""Reuse is technique for some classes and a defect for others."""

from __future__ import annotations

from contracts_v3.asset_ledger import SemanticAssetClass
from quality_loop.gates.assets_v3 import _REPEATABLE_CLASSES


def test_every_exempt_class_is_a_real_semantic_class() -> None:
    """An exemption for a class that does not exist can never fire.

    The first version of this set contained "ground" and "motif", neither of
    which is a SemanticAssetClass, so half the exemption was dead.
    """
    known = {member.value for member in SemanticAssetClass}

    assert _REPEATABLE_CLASSES <= known, _REPEATABLE_CLASSES - known


def test_the_classes_richard_actually_repeats_are_exempt() -> None:
    """Measured: a paper texture on 9 faces, a client logo on 8."""
    assert SemanticAssetClass.TEXTURE.value in _REPEATABLE_CLASSES
    assert SemanticAssetClass.LOGO.value in _REPEATABLE_CLASSES


def test_a_portrait_or_a_proof_may_never_repeat() -> None:
    """The same face on three case studies is a lie, not a technique."""
    assert SemanticAssetClass.IDENTITY.value not in _REPEATABLE_CLASSES
    assert SemanticAssetClass.PROOF.value not in _REPEATABLE_CLASSES
    assert SemanticAssetClass.CONTEXT.value not in _REPEATABLE_CLASSES
