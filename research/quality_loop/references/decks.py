"""Pure-data registry of Richard's reference decks.

Each entry names a reference source PDF (catalog data) and its per-client
axes from the design DNA section B. Axes are CATEGORICAL LABELS only —
brand-agnostic descriptors, never hex / RGB / font-family literals. This is
what keeps reference retrieval spread across multiple clients (never anchored
on one brand).
"""

REPO_ROOT = "/Users/utkarsh/Projects/richard"

# Axis keys present on EVERY deck:
#   headline_type, palette, accent_mechanic, texture, density, qr_enabled, tone
DECKS = [
    {
        "deck_id": "apex",
        # MACHINE-GENERATED (pipeline output, not Richard's hand). Kept in the
        # registry for axis bookkeeping, but build_st_type_index labels every
        # page OTHER so retrieval can never anchor a comparison on it (owner
        # rule: never anchor on apex).
        "machine_generated": True,
        "pdf_filename": "APEX - KI DMC Report v1 (1).pdf",
        "axes": {
            "headline_type": "serif",
            "palette": "mono_blue_cyan_navy",
            "accent_mechanic": "tonal",
            "texture": "frosted_glass_geometric",
            "density": "airy",
            "qr_enabled": False,
            "tone": "tech_premium",
        },
    },
    {
        "deck_id": "niklas",
        "pdf_filename": "Niklas Niemeyer DMC-Report Druckfertig (1).pdf",
        "axes": {
            "headline_type": "serif_sans_caps_accent",
            "palette": "royal_blue_charcoal",
            "accent_mechanic": "contrasting",
            "texture": "darkened_photo",
            "density": "punchy_5050",
            "qr_enabled": True,
            "tone": "masculine_bold",
        },
    },
    {
        "deck_id": "buchagentur",
        "pdf_filename": "Buchagentur DMC-Report (1).pdf",
        "axes": {
            "headline_type": "serif_didone",
            "palette": "teal_petrol",
            "accent_mechanic": "contrasting",
            "texture": "paper_grain",
            "density": "dense_editorial",
            "qr_enabled": True,
            "tone": "editorial_luxury",
        },
    },
    {
        "deck_id": "boss",
        "pdf_filename": "DMC-Report Alexander Boss doppelt (1).pdf",
        "axes": {
            "headline_type": "serif_slab",
            "palette": "navy_azure",
            "accent_mechanic": "contrasting",
            "texture": "flat_icons",
            "density": "navy_panels",
            "qr_enabled": False,
            "tone": "corporate_trust",
        },
    },
    {
        "deck_id": "werkzeugkoffer",
        "pdf_filename": "DMC-Report Mein_Werkzeugkoffer.pdf",
        "axes": {
            "headline_type": "all_sans",
            "palette": "midblue_navy",
            "accent_mechanic": "tonal",
            "texture": "darkened_photo",
            "density": "navy_panels",
            "qr_enabled": True,
            "tone": "corporate_masculine",
        },
    },
    {
        "deck_id": "aerztepartner",
        "pdf_filename": "aerztepartner_v0.2 (1).pdf",
        "axes": {
            "headline_type": "serif_didone",
            "palette": "navy_gold",
            "accent_mechanic": "contrasting",
            "texture": "parchment_marble_gold",
            "density": "airy_premium",
            "qr_enabled": False,
            "tone": "private_banking_luxury",
        },
    },
]
