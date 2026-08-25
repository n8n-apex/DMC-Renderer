"""BANK PLANNER - the pre-processor's per-page plan over the Template Bank.

The planner produces ONE first-class object per page: a PagePlan carrying the
chosen TEMPLATE (treatment), its ROLE (from the v3 vocabulary), the page format,
the data the renderer will fill, and the DEVICES the template can host (from the
bank catalog, by role).

This is the "judgment" layer the user asked for: for each page the planner
  1. asks the bank catalog which templates serve the page's ROLE (browse by
     context), and
  2. applies the existing deterministic assignment (data contract + adjacency +
     dedup) - reusing treatment_stylist.assign unchanged as the executor
     decision,
  3. annotates each decision with its role + the candidate devices, emitting a
     plan the renderer consumes.

Brand-agnostic: the role mapping is structural (st_type -> v3 RoleName), no
client data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from treatment_stylist import PageAssignment, assign as _assign  # type: ignore
    _HAS_ASSIGN = True
except Exception:  # noqa: BLE001
    _HAS_ASSIGN = False

try:
    from bank_catalog import browse_by_role, catalog  # type: ignore
    _HAS_CATALOG = True
except Exception:  # noqa: BLE001
    _HAS_CATALOG = False


# st_type -> v3 RoleName (the bank's context vocabulary). Structural mapping,
# brand-agnostic. A type with no entry has no role (browsable catalog omits it).
_ROLE_BY_ST: dict[str, str] = {
    "ST-01": "cover",
    "ST-02": "outlook",
    "ST-05": "about",
    "ST-09": "status_quo",
    "ST-14": "false_beliefs",
    "ST-07A": "case_study",
    "ST-07B": "theory",
    "ST-07C": "case_study",
    "ST-06": "mechanism",
    "ST-22": "collaboration",
    "ST-FAZIT": "summary",
    "ST-03": "cta",
    "ST-31": "brand_breather",
    "ST-32": "brand_breather",
}


@dataclass
class PagePlan:
    """The per-page plan the renderer consumes. One per page, in order.

    Field names are drop-in compatible with the legacy PageAssignment the
    assembler consumes (index / treatment / page_format / reason), so the plan
    can replace it in the render path unchanged. The extra fields (role,
    devices, and the `template` alias) are the bank's contribution: the
    context (role) and the candidate devices the template can host.
    """

    index: int
    slot: Any
    st_type: str
    role: Optional[str]                 # v3 RoleName (structural)
    treatment: Optional[str]            # chosen treatment name (compat with PageAssignment)
    page_format: Optional[str]          # "a4"/"a3" or None
    reason: str                         # audit trail from assign()
    devices: list[str] = field(default_factory=list)  # candidate devices by role

    @property
    def template(self) -> Optional[str]:
        """The same as `treatment` (human-friendly alias for the bank's term)."""
        return self.treatment


def plan_pages(pages: list[dict], ctx: Any, *, max_a3: int = 4) -> list[PagePlan]:
    """Produce the deck plan: the existing assignment, annotated with role +
    candidate devices from the bank catalog.

    Deterministic (reuses assign). Never raises: a missing catalog/assign falls
    back to a plan with template=None + a clear reason (so the caller can still
    render the legacy path, but the plan is explicit about why).
    """
    if not _HAS_ASSIGN:
        return [
            PagePlan(index=i, slot=p.get("slot"), st_type=p.get("st_type", ""),
                     role=_ROLE_BY_ST.get(p.get("st_type", ""), None),
                     treatment=None, page_format=None,
                     reason="bank_plan: assign unavailable")
            for i, p in enumerate(pages)
        ]

    # the renderer's assembler registers the treatment catalog before assign
    # (candidate_fits needs the templates known). Mirror that here so the plan
    # reflects the same decisions as the render path.
    if _HAS_CATALOG:
        try:
            from treatment_catalog import register_all  # type: ignore
            register_all()
        except Exception:  # noqa: BLE001
            pass

    assigns: list[PageAssignment] = _assign(pages, ctx, max_a3=max_a3)
    plans: list[PagePlan] = []
    for i, a in enumerate(assigns):
        st = a.st_type or (pages[i].get("st_type", "") if i < len(pages) else "")
        role = _ROLE_BY_ST.get(st, None)
        devices: list[str] = []
        if _HAS_CATALOG and role:
            try:
                br = browse_by_role(role)
                # candidate devices for this role: every device the catalog
                # tags (the template decides at render which it actually hosts
                # via page.data.viz).
                devices = sorted({d["name"] for d in (br.get("devices") or [])})
            except Exception:  # noqa: BLE001
                devices = []
        plans.append(PagePlan(
            index=a.index,
            slot=a.slot,
            st_type=st,
            role=role,
            treatment=a.treatment,
            page_format=a.page_format,
            reason=a.reason,
            devices=devices,
        ))
    return plans


def browse(role: str) -> dict:
    """Human/machine browsable catalog query by role (the 'open by context').
    Returns the contexts + built templates + candidate devices for the role."""
    if not _HAS_CATALOG:
        return {"role": role, "error": "catalog unavailable"}
    return browse_by_role(role)


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, __file__.parent.as_posix())
    from package_loader import load_package  # type: ignore
    from patterns.base import RenderContext  # type: ignore
    from brand_tokens import parse_brand_tokens  # type: ignore
    from grammar_loader import load_grammar  # type: ignore

    pkg = load_package(sys.argv[1] if len(sys.argv) > 1 else "fixtures/apex")
    ctx = RenderContext(brand=pkg.brand, grammar=load_grammar(),
                        package_dir=pkg.package_dir,
                        report_assets=pkg.report_assets)
    plans = plan_pages(pkg.pages, ctx)
    print(json.dumps([p.__dict__ for p in plans], ensure_ascii=False, indent=2))