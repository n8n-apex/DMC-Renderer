"""Chassis-level anti-pattern toggles — per-element-class signature.

Per matrix ROW NO-ROUNDED-EXCEPT-CTA (2026-05-18 RICHARD-PRIMARY block)
+ grammar §6.1 ("ANTI-PATTERNS — UNIVERSAL [HARD]"):

  #1 No rounded corners on text containers / panels.
     EXCEPTION 1: CTA boxes may have 2–3mm border-radius optionally.
       Citation: DMC_InDesign_Spec_v1.md L548-552 (Textrahmen_CTA_Box:
       "Ecken: Optional leicht abgerundet (2–3mm)").
     EXCEPTION 2: Mechanism / process step cards (P-8, P-13) may have
       rounded corners when used as numbered-stage containers.
       Citation: grammar §6.1 #1 exception 2 — VARIATION (per-brand,
       not universal); evidence aerz_p07.

  #2 No drop shadows on type or panels (flat fills only). NO EXCEPTIONS.

History (Move 2c, 2026-05-23): this module previously took an opaque
`design_preferences` dict and an ANTIPATTERN_MODE flag (HARD vs
BRAND_PREF). All design_preferences plumbing deleted per A1 DELETE +
matrix ROW NO-ROUNDED-EXCEPT-CTA. The right gate is per-ELEMENT-CLASS
(the grammar's terms), not per-brand override.
"""

from __future__ import annotations


# Element classes (CSS-class-style names) that the renderer applies the
# CTA-box exception to. Per InDesign Spec L548-552 the exception is
# specific to CTA boxes; if a future pattern adds another class that
# represents a CTA box (e.g. a soft-CTA strip), add it here.
_CTA_BOX_CLASSES: frozenset[str] = frozenset({
    "cta-box",
})

# Element classes that the renderer applies the mechanism-step-card
# exception to. Per grammar §6.1 #1 exception 2 this is VARIATION
# (per-brand designer choice, not universal). Adding a class here is a
# per-brand pattern decision, not a chassis-wide rule change.
_MECHANISM_STEP_CLASSES: frozenset[str] = frozenset({
    "mechanism-step-card",
    "process-step-card",
})


def allow_rounded_corners(element_class: str) -> bool:
    """Return True iff this element class is allowed rounded corners.

    Hue-agnostic, brand-agnostic. The decision is purely on the role
    the element plays in the page composition. Per grammar §6.1 #1:
    default no rounded corners; CTA boxes are the universal exception;
    mechanism step cards are the VARIATION exception.

    Every other element class returns False. The function never reads
    a brand-config dict — the grammar's rules are the rules.
    """
    if element_class in _CTA_BOX_CLASSES:
        return True
    if element_class in _MECHANISM_STEP_CLASSES:
        return True
    return False


def allow_drop_shadows(element_class: str) -> bool:
    """Return False unconditionally — drop shadows have no Richard
    citation on any element class. Grammar §6.1 #2 (HARD, no exception).
    """
    # element_class is accepted for symmetry with allow_rounded_corners
    # but does not affect the answer. Keeping the parameter ensures any
    # future "soft" exception can land here in one place.
    _ = element_class
    return False
