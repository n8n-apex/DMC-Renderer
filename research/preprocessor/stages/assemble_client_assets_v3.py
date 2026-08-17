"""Assemble a build's asset list from a client's real files.

The pieces existed separately and nothing joined them: `ingest_client_assets_v3`
reads a folder into records, `build_asset_ledger_v3` consumes an envelope's
`assets`, and `generate_assets_v3` can make what is missing. This is the
join, so a build can run on real photographs instead of placeholders.

Order matters and is deliberate:

  1. the client's OWN files first, because a real photograph of the founder
     beats any generated one
  2. then generated images, only for what is still missing and only with
     explicit permission
  3. anything still short is REPORTED, never substituted

Rights are carried through untouched. A file the owner has not authorized
arrives with `rights_status: unknown` and the asset gate stops it, which is
the behaviour that kept 27 of 28 real images out of the last build.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from stages.ingest_client_assets_v3 import (
    ingest_case_client_assets,
    ingest_client_assets,
    portrait_capable,
    print_usable,
)


# An identity slot in a rail is roughly this wide. A portrait smaller than
# this prints as a thumbnail wherever a face is expected.
IDENTITY_MIN_PRINT_MM = 55.0


@dataclass(frozen=True)
class AssetAssembly:
    """What the build will have to work with, and what it still lacks."""

    assets: tuple[dict[str, Any], ...] = ()
    authorized: int = 0
    blocked_on_rights: int = 0
    shortfall: int = 0
    warnings: tuple[str, ...] = field(default=())

    def summary(self) -> str:
        parts = [
            f"{len(self.assets)} assets assembled",
            f"{self.authorized} authorized",
            f"{self.blocked_on_rights} blocked on rights",
        ]
        if self.shortfall:
            parts.append(f"{self.shortfall} still missing")
        return ", ".join(parts)


def assemble(
    *,
    client_slug: str,
    own_assets_dir: Path | None = None,
    case_assets_dir: Path | None = None,
    required_count: int = 0,
    authorized: tuple[str, ...] = (),
    authorized_by: str | None = None,
    authorized_on: date | None = None,
) -> AssetAssembly:
    """Every usable real image this client has, with rights carried through."""
    records: list[dict[str, Any]] = []
    warnings: list[str] = []

    if own_assets_dir and own_assets_dir.is_dir():
        records.extend(
            ingest_client_assets(
                own_assets_dir,
                client_slug=client_slug,
                authorized=authorized,
                authorized_by=authorized_by,
                authorized_on=authorized_on,
            )
        )
    if case_assets_dir and case_assets_dir.is_dir():
        records.extend(
            ingest_case_client_assets(
                case_assets_dir,
                client_slug=f"{client_slug}.case",
                authorized=authorized,
                authorized_by=authorized_by,
                authorized_on=authorized_on,
            )
        )

    usable = [record for record in records if print_usable(record)]
    dropped = len(records) - len(usable)
    if dropped:
        warnings.append(f"{dropped} file(s) too small to print were dropped")

    # A landscape file in a portrait slot crops badly. Saying so here is
    # cheaper than the owner discovering it in a rendered PDF.
    identities = [r for r in usable if r["semantic_class"] == "identity"]
    landscape = [r for r in identities if not portrait_capable(r)]
    for record in landscape:
        warnings.append(
            f"{Path(record['local_path']).name} is landscape "
            f"({record['pixel_width']}x{record['pixel_height']}) and will crop "
            "in a portrait identity slot"
        )
    # Portrait ASPECT is not enough. An avatar is square and passes the
    # general print floor at 27mm, but an identity rail wants roughly 60mm,
    # so it would print as a thumbnail where a portrait belongs.
    usable_portraits = [
        record
        for record in identities
        if portrait_capable(record)
        and min(record["print_width_mm"], record["print_height_mm"])
        >= IDENTITY_MIN_PRINT_MM
    ]
    if identities and not usable_portraits:
        warnings.append(
            "no portrait founder shot exists at usable print size: "
            + ", ".join(
                f"{Path(r['local_path']).name} "
                f"{r['print_width_mm']:.0f}x{r['print_height_mm']:.0f}mm"
                for r in identities
            )
        )

    if not any(record["semantic_class"] == "logo" for record in usable):
        warnings.append(
            "no logo-class asset exists, so a logo wall cannot be built "
            "(it needs three)"
        )

    authorized_count = sum(
        1 for record in usable if record["rights_status"] == "client_authorized"
    )
    return AssetAssembly(
        assets=tuple(usable),
        authorized=authorized_count,
        blocked_on_rights=len(usable) - authorized_count,
        shortfall=max(0, required_count - authorized_count),
        warnings=tuple(warnings),
    )
