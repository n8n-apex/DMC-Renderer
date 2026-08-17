# Export profiles

Every delivery is produced from a stored, validated profile; the exporters never
guess or fall back.

## Digital

`dmc_digital_v1.json` is the stored digital export profile. It is loaded and
validated through `profiles/schema.py` (`load_digital_profile`), and every
digital delivery records the profile id and its content hash in the immutable
`report.digital-export-report.json` next to the delivery PDF. The profile pins
the minimum searchable-text preservation ratio, link/page-size/font/metadata
preservation, explicit metadata-normalization flags, and the PDF/A target.
`pdf_standard_target` is `preserve_source` in v1 because the digital deliverable
is the byte-preserved renderer PDF; a profile that declares `PDF/A-2b` makes the
exporter verify PDF/A markers on the output and fail otherwise.

## Print

Print export is disabled unless a strict profile is supplied and its ICC bytes
match the declared SHA-256.

`dmc_print_test` exists only for automated tests. It uses PDF/A-2b with an RGB
sRGB output intent, has no bleed, and is never valid for a production printer
handoff. It verifies the conversion and preflight machinery without pretending
to be a press profile.

`dmc_print_production_v1.json` is a BLOCKED template, not a usable profile. It
carries `"status": "awaiting_printer_approval"` and
`"production_allowed": false`, and every printer-supplied value (PDF standard,
ICC path and hash, color space, bleed, crop marks, minimum image DPI, TAC
limit, font policy, transparency and flattening policy, searchable-text
policy) is `null` with a `"required_from": "printer"` annotation. The loader
rejects it for any export (`print_profile_blocked_template`), and a doctored
copy with remaining nulls is rejected as `print_profile_incomplete`. Filling
the values does not unblock it: `production_allowed` may become `true` only
after the printer has approved the PDF standard, output intent, bleed, marks,
image DPI, ink coverage, font, and transparency policies.

The exporter must not guess a printer profile or fall back to the test profile.
Preflight measures real maximum CMYK total area coverage with Ghostscript
separations for CMYK profiles; when a profile requires bleed or crop marks,
export adds TrimBox/BleedBox geometry and corner marks and preflight compares
the input page size against the output TrimBox.
