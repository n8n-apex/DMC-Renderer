"""Stage 3.5 — copy-fit pre-check (heuristic overflow early-warning).

The pre-processor cannot know TRUE overflow — only the renderer's actual
WeasyPrint layout knows whether text spills past its box/page. This is a
cheap HEURISTIC that runs BEFORE the renderer: total page copy length vs a
per-ST-type capacity estimate. It is ADVISORY ONLY (warns, never blocks),
mirroring Stage 3's philosophy, so obviously-too-long copy is flagged for
Richard's QA before a render is even attempted.

The budgets below are conservative DATA (brand-agnostic), to be CALIBRATED
against real renders once the renderer produces real layouts. They are
deliberately generous — this catches gross over-length, not tight cases
(the renderer's real overflow validator is the ground-truth backstop).
"""

from __future__ import annotations

from typing import Any

from models import CopyWarning, ReportPage
from stages.validate_copy import _collect_all_strings


# Approximate total characters a page of each ST type can hold before
# overflow becomes likely. Conservative; CALIBRATE from real renders.
# Unknown ST types are skipped (no budget → no warning).
ST_COPY_BUDGET_CHARS: dict[str, int] = {
    "ST-01": 500,     # cover — headline + subtitle + bullets (short by design)
    "ST-02": 1600,    # outlook
    "ST-03": 400,     # hard CTA back cover (sparse)
    "ST-05": 1600,    # about
    "ST-06": 1400,    # mechanism
    "ST-07A": 1800,   # case study (LRP body sections)
    "ST-07B": 1800,   # theory / Gegenseite
    "ST-08": 2000,    # FAQ (densest text page)
    "ST-09": 1400,    # status quo
    "ST-14": 1500,    # false beliefs
    "ST-22": 1400,    # collaboration
    "ST-31": 350,     # Atemseite (breathing — light)
    "ST-32": 350,     # breathing
    "ST-FAZIT": 1600,  # summary
}


def _unpack_page(page: ReportPage | dict) -> tuple[int, str, Any]:
    if isinstance(page, ReportPage):
        return page.slot, page.type, page.data
    return int(page["slot"]), str(page["type"]), page.get("data", {})


def validate_copyfit(pages: list[ReportPage] | list[dict]) -> list[CopyWarning]:
    """Heuristic copy-fit pre-check. Returns advisory CopyWarnings (rule
    ``copy_overflow_risk``) for pages whose total copy length exceeds the
    ST-type capacity estimate. Never raises; unknown ST types are skipped.
    """
    warnings: list[CopyWarning] = []
    for page in pages:
        slot, st_type, data = _unpack_page(page)
        budget = ST_COPY_BUDGET_CHARS.get(st_type)
        if budget is None or not isinstance(data, dict):
            continue
        total = sum(len(s) for s in _collect_all_strings(data))
        if total > budget:
            warnings.append(CopyWarning(
                page_slot=slot,
                page_type=st_type,
                field_name="<page>",
                rule="copy_overflow_risk",
                detail=(
                    f"page copy ~{total} chars exceeds the ~{budget}-char "
                    f"capacity estimate for {st_type} — may overflow; shorten "
                    f"the copy or expect the renderer's overflow validator to "
                    f"flag it"
                ),
            ))
    return warnings
