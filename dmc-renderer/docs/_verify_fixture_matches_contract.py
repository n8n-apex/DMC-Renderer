"""Verify that fixtures/apex_consulting_payload.json conforms to API_CONTRACT.md.

This is a one-off audit script for Phase 2 surfacing. In Phase 3 it will
become a proper test at `tests/test_contract_matches_fixture.py` using
pytest + pydantic.

Run: python docs/_verify_fixture_matches_contract.py
Exit 0 if fixture matches contract; non-zero with details otherwise.
"""

import json
import re
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent.parent / "fixtures/apex_consulting_payload.json"

REQUIRED_META = {"client_slug", "report_id", "lang", "page_format",
                 "export_mode", "page_count_target"}

# Per-ST required fields per API_CONTRACT.md
ST_SCHEMAS = {
    "ST-01": {"required": {"title", "subtitle", "intro_body", "teaser_bullets"}},
    "ST-02": {"required": {"headline", "asymmetrie_opener", "body"}},
    "ST-03": {"required": {"headline", "body", "cta_text", "cta_url"}},
    "ST-05": {"required": {"headline", "intro", "body", "credibility_points"}},
    "ST-06": {"required": {"headline", "mechanism_name", "mechanism_description",
                            "steps", "closing_redirect"}},
    "ST-07A": {"required": {"fallstudie_number", "ergebnis_headline",
                             "kurzportraet", "ausgangsproblem", "wendepunkt",
                             "loesung", "ergebnis_text", "ergebnis_metrics",
                             "kunde", "pullquote"}},
    "ST-07B": {"required": {"headline", "subheadline", "body", "key_insight"}},
    "ST-09":  {"required": {"headline", "asymmetrie_opener", "body",
                             "symptoms", "closing"}},
    "ST-14":  {"required": {"headline", "intro", "beliefs"}},
    "ST-22":  {"required": {"headline", "intro", "steps"}},
    "ST-FAZIT": {"required": {"headline", "body", "bold_thesis",
                               "cost_of_inaction", "closing_question"}},
}

REQUIRED_BRAND_TOKENS = {
    "brand_primary", "brand_accent", "brand_neutral_dark",
    "brand_neutral_mid", "brand_neutral_light",
    "font_heading", "font_body",
    "qr_target_url", "company_name_short", "company_url_display",
}

PAGE_NUMBERS_RE = re.compile(r"^\d+(-\d+)?$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
REPORT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def check(cond: bool, msg: str, errors: list):
    if not cond:
        errors.append(msg)


def main():
    if not FIXTURE.exists():
        print(f"ERR: fixture missing at {FIXTURE}")
        sys.exit(2)
    data = json.loads(FIXTURE.read_text())

    errors = []
    notes = []

    # Top-level shape
    check("payload" in data, "top-level missing key: payload", errors)
    check("images" in data, "top-level missing key: images", errors)
    check("brand_tokens" in data, "top-level missing key: brand_tokens", errors)

    # payload.meta
    meta = data.get("payload", {}).get("meta", {})
    for k in REQUIRED_META:
        check(k in meta, f"payload.meta missing required key: {k}", errors)
    if "report_id" in meta:
        check(bool(REPORT_ID_RE.match(meta["report_id"])),
              f"payload.meta.report_id ill-formed: {meta['report_id']!r}", errors)
    if "page_format" in meta:
        check(meta["page_format"] == "A4",
              f"payload.meta.page_format must be A4 in v1, got {meta['page_format']!r}",
              errors)
    if "lang" in meta:
        check(meta["lang"] in {"de", "en"},
              f"payload.meta.lang must be de or en, got {meta['lang']!r}", errors)
    if "page_count_target" in meta:
        check(isinstance(meta["page_count_target"], int),
              "payload.meta.page_count_target must be int", errors)

    # payload.pages[]
    pages = data.get("payload", {}).get("pages", [])
    check(len(pages) > 0, "payload.pages[] is empty", errors)
    last_hi = 0
    for i, pg in enumerate(pages):
        prefix = f"payload.pages[{i}]"
        for k in {"slot", "type", "chapter_type_original", "page_numbers", "data"}:
            check(k in pg, f"{prefix} missing key: {k}", errors)
        if pg.get("slot") != i + 1:
            errors.append(f"{prefix}.slot = {pg.get('slot')}, expected {i + 1}")
        pn = pg.get("page_numbers", "")
        check(bool(PAGE_NUMBERS_RE.match(pn)),
              f"{prefix}.page_numbers ill-formed: {pn!r}", errors)
        # Monotonic check
        if PAGE_NUMBERS_RE.match(pn):
            lo, hi = (int(x) for x in (pn.split("-") if "-" in pn else (pn, pn)))
            if lo <= last_hi:
                notes.append(f"  monotonic warning: slot {pg.get('slot')} {pn!r} <= prev_hi {last_hi}")
            last_hi = hi
        # Per-ST data schema
        st = pg.get("type")
        if st not in ST_SCHEMAS:
            errors.append(f"{prefix}.type = {st!r} not in documented ST list")
            continue
        required = ST_SCHEMAS[st]["required"]
        present = set(pg.get("data", {}).keys())
        for k in required:
            check(k in present,
                  f"{prefix}.data ({st}) missing required field: {k}",
                  errors)

    # brand_tokens
    bt = data.get("brand_tokens", {})
    for k in REQUIRED_BRAND_TOKENS:
        check(k in bt, f"brand_tokens missing required key: {k}", errors)
    for k in ("brand_primary", "brand_accent", "brand_neutral_dark",
              "brand_neutral_mid", "brand_neutral_light"):
        if k in bt:
            check(bool(HEX_RE.match(bt[k])),
                  f"brand_tokens.{k} not a valid hex color: {bt[k]!r}", errors)

    # images — keys are not strictly required (depends on which STs are present)
    images = data.get("images", {})
    SLOT_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
    for k in images:
        check(bool(SLOT_RE.match(k)),
              f"images key {k!r} doesn't match slot-name pattern", errors)

    # Summary
    print(f"\n=== Fixture: {FIXTURE.name} ===")
    print(f"  pages: {len(pages)}")
    print(f"  ST types present: {sorted({pg['type'] for pg in pages})}")
    print(f"  brand_tokens keys: {len(bt)}")
    print(f"  images keys: {len(images)}")
    if notes:
        print("\nWarnings (non-blocking):")
        for n in notes:
            print(n)
    if errors:
        print(f"\nFAIL — {len(errors)} contract violation(s):\n")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\nPASS — fixture conforms to API_CONTRACT.md.")
    sys.exit(0)


if __name__ == "__main__":
    main()
