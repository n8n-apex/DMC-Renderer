"""Brand-token FALLBACK constants for the dmc-renderer adapter logic.

D4: raw hex colors in LOGIC violate the brand-agnostic rule (the no-hex guard
scans only research/v7-renderer). These are the neutral fallbacks used when a
client envelope omits a brand token; per-client colors always arrive as
tokens in the envelope and win. They live here so the guard (once extended to
scan dmc-renderer) sees named constants, not literal hexes in logic.
"""

FALLBACK_BRAND_HEX_DARK = "#1a1a2e"
FALLBACK_BRAND_HEX_LIGHT = "#f5f5f7"
FALLBACK_BRAND_HEX_ACCENT = "#e94560"
FALLBACK_V3_ACCENT = "#c94e2c"
