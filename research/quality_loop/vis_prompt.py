"""Brand-agnostic vision PROMPT builder for the quality loop (Task B).

Pure, no network. This module owns the *compositional grammar* questions the
vision model is asked when comparing OUR rendered page against expert REFERENCE
pages of the same page type.

The cardinal rule (design DNA §C universal grammar): references ground
**composition**, NOT brand values. So every question here is about structure,
hierarchy, and design DEVICES -- never about which brand, colour palette, copy,
or logo is used. The guardrail is enforced again in the system prompt so the
model cannot reward/penalise on brand identity.

There are deliberately NO client names, NO hex colours, and NO font-family
literals anywhere in this module.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# Per-rubric-row composition questions (design DNA §C). Each is phrased so a
# higher score (0-3) means "more present / better composed" for POSITIVE rows,
# and explicitly notes when a higher score is WORSE for the negative (N*) rows.
# --------------------------------------------------------------------------- #
QUESTIONS: dict[str, str] = {
    "P01": (
        "Is a founder/person used as the dominant human anchor of the page "
        "(a large, prominent portrait), as opposed to being absent or tiny?"
    ),
    "P05": (
        "Does each case study show a clearly framed, named client portrait at "
        "meaningful size (roughly a quarter to a third of the column), not an "
        "empty gap?"
    ),
    "P07": (
        "Is there a social-proof apparatus present (a press/logo wall, rating "
        "cards, a review grid, or testimonials)?"
    ),
    "P10": (
        "Are oversized decorative typographic elements present (giant ghost "
        "numerals, large quote glyphs)?"
    ),
    "P11": (
        "Are there real data-visualisations bound to numbers (before/after, "
        "charts, cost-math), as opposed to empty chart frames?"
    ),
    "P12": (
        "Does the page read as a dense, magazine-quality editorial layout that "
        "fills the sheet, versus sparse and under-filled?"
    ),
    "P13": (
        "Is there an intentional background texture/atmosphere appropriate to "
        "the page, versus flat blankness?"
    ),
    "P14": (
        "If a full-bleed photo is used, is it treated (scrim/darkening) so that "
        "any overlaid text stays readable?"
    ),
    "P16": (
        "Is a device/product mockup shown (phone/laptop/book) to add real "
        "product credibility where appropriate?"
    ),
    "N07": (
        "Does the imagery look generic/stock rather than specific to a real "
        "business? (A HIGHER score means MORE generic, which is WORSE.)"
    ),
    "N08": (
        "Is there sparse, purposeless dead whitespace (large empty regions with "
        "no content)? (A HIGHER score means MORE dead space, which is WORSE.)"
    ),
    "N10": (
        "Is there text sitting on a busy photo with no scrim, or awkward inset "
        "gaps? (A HIGHER score means WORSE.)"
    ),
}


# The verbatim brand-agnostic guardrail. Lives in the system prompt so the
# model is bound by it before it ever sees the images. Phrased to satisfy both
# British and American spelling of "colour"/"penalise".
_GUARDRAIL = (
    "Judge COMPOSITION, STRUCTURE, and DESIGN DEVICES ONLY. "
    "IGNORE brand colours/colors, language, copy, logos, and brand identity -- "
    "do NOT reward or penalise (penalize) based on which brand or colour "
    "palette is used. The references differ in brand; only their compositional "
    "grammar is the target. References ground composition, NOT brand values."
)

_SYSTEM_PROMPT = (
    "You are an expert print/editorial designer acting as a strict, consistent "
    "scoring judge. You compare one generated page against expert reference "
    "pages of the SAME page type and rate specific compositional criteria.\n\n"
    + _GUARDRAIL
    + "\n\nScore every requested criterion on an integer 0-3 scale "
    "(0 = absent/poor, 3 = strongly present/excellent) and give a one-sentence "
    "rationale grounded in what you actually see. Output STRICT JSON only."
)


def build_prompt(row_ids: list[str], n_reference_images: int,
                 row_metadata: dict[str, dict] | None = None) -> tuple[str, str]:
    """Build the (system_prompt, user_prompt) pair for a scoring call.

    Args:
        row_ids: rubric row ids to score; only ids known in ``QUESTIONS`` are
            included (unknown ids are skipped silently so callers can pass a
            superset).
        n_reference_images: how many expert reference pages follow OUR page.
        row_metadata: optional {row_id: {visual_job, argument, density}} — the
            DIRECTOR's semantic context for each page. When present, the
            reviewer judges the page against its actual editorial job instead
            of a generic question bank.

    The user prompt explains the image ordering (ours first, then the
    references as examples of the compositional grammar), lists the selected
    tagged questions, and pins the exact JSON output shape.
    """
    selected = [r for r in row_ids if r in QUESTIONS]

    lines: list[str] = []
    lines.append(
        f"The FIRST image is OUR generated page. The remaining "
        f"{n_reference_images} image(s) are REFERENCE pages of the SAME page "
        "type by an expert designer -- they are EXAMPLES OF THE COMPOSITIONAL "
        "GRAMMAR to compare against (their brand/colour differs on purpose; "
        "only their composition is the target)."
    )
    lines.append("")
    if row_metadata:
        meta_lines = []
        for rid in selected:
            meta = (row_metadata or {}).get(rid) or {}
            if meta:
                job = meta.get("visual_job") or ""
                arg = meta.get("argument") or ""
                dens = meta.get("density") or ""
                bits = []
                if job:
                    bits.append(f"visual job: {job}")
                if dens:
                    bits.append(f"density: {dens}")
                if arg:
                    bits.append(f"page argument: {arg[:140]}")
                if bits:
                    meta_lines.append(f"  [{rid}] " + "; ".join(bits))
        if meta_lines:
            lines.append("THE DIRECTOR'S INTENT for each page (what this page "
                         "must communicate — judge against THIS, not a generic "
                         "template):")
            lines.extend(meta_lines)
            lines.append("")
    lines.append(
        "For OUR page (the first image), answer each of the following "
        "questions. Each is tagged with a rubric row id. Give an integer score "
        "from 0 to 3 and a one-sentence rationale per row:"
    )
    lines.append("")
    for rid in selected:
        lines.append(f"  [{rid}] {QUESTIONS[rid]}")
    lines.append("")
    lines.append(
        "Return STRICT JSON with EXACTLY this shape (one entry per row id "
        "above, scores are integers 0-3):"
    )
    lines.append(
        '  {"<row_id>": {"score": <0-3 int>, "rationale": "<str>"}, ...}'
    )
    lines.append("")
    lines.append("Remember: " + _GUARDRAIL)

    return _SYSTEM_PROMPT, "\n".join(lines)
