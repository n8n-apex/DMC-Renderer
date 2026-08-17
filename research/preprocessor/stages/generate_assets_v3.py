"""Wire real image generation into v3, switched off by default.

`stages/generate_assets.py` carries a working fal.ai integration -- 915
lines, POSTing to https://fal.run/{model} at line 360 -- and v3 has never
called it. That is why every build runs on procedurally drawn placeholders
and why 11 of 45 gate failures are `synthetic_placeholder_asset`.

Its own module docstring is stale: it says the fal integration "goes here
later". Only `generate_texture` is still a stub; `fal_generate_image` is
real and will spend money.

Which is the whole reason this adapter defaults to OFF. Generation is a
paid call on the owner's account, so it happens only when a policy is
passed in with an explicit key and an explicit ceiling. Absent that, the
stage plans the work and reports what WOULD be generated, which is useful
on its own: it turns "the images are missing" into a costed list.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AssetGenerationPolicy:
    """Explicit permission to spend money, with a ceiling.

    There is deliberately no default that generates. A caller must name the
    key source and the maximum number of NEW paid generations; cache hits
    are free and are always served regardless of the ceiling.
    """

    enabled: bool = False
    fal_key_env: str = "FAL_KEY"
    max_generations: int = 0
    model: str = "fal-ai/nano-banana-pro"
    resolution: str = "2K"
    cache_dir: Path | None = None

    def resolved_key(self) -> str | None:
        """The key, or None when generation is off or the key is absent."""
        if not self.enabled or self.max_generations < 1:
            return None
        return os.environ.get(self.fal_key_env) or None


@dataclass(frozen=True)
class GenerationOutcome:
    """What generation did, or would have done."""

    planned: int = 0
    generated: int = 0
    from_cache: int = 0
    failed: int = 0
    skipped_no_permission: int = 0
    details: tuple[str, ...] = ()

    def summary(self) -> str:
        if self.skipped_no_permission:
            return (
                f"{self.skipped_no_permission} image(s) would be generated; "
                "generation is off (no policy, no key, or a zero ceiling)"
            )
        return (
            f"{self.generated} generated, {self.from_cache} served from cache, "
            f"{self.failed} failed"
        )


def plan_or_generate(
    pages: list[Any],
    image_manifest: dict | Any,
    *,
    brand_primary: str,
    brand_accent: str,
    output_dir: Path,
    client_slug: str = "",
    policy: AssetGenerationPolicy | None = None,
    design_brief: Any = None,
) -> GenerationOutcome:
    """Generate the report's images, or cost the work without spending.

    With no policy this makes NO network call and returns the count of
    images the report needs, which is what turns a placeholder failure into
    an actionable number.
    """
    from stages.generate_assets import generate_assets

    policy = policy or AssetGenerationPolicy()
    fal_key = policy.resolved_key()

    plan = asyncio.run(
        generate_assets(
            pages,
            image_manifest,
            brand_primary=brand_primary,
            brand_accent=brand_accent,
            design_brief=design_brief,
            client_slug=client_slug,
            output_dir=output_dir,
            # No key means the stage plans and reports rather than spends.
            fal_key=fal_key,
            fal_model=policy.model,
            fal_resolution=policy.resolution,
            cache_dir=policy.cache_dir,
            max_generations_per_report=policy.max_generations,
        )
    )
    return _summarise(plan, spending=fal_key is not None)


def _summarise(plan: Any, *, spending: bool) -> GenerationOutcome:
    results = tuple(getattr(plan, "results", ()) or ())
    counts = {"generated": 0, "cached": 0, "failed": 0, "other": 0}
    details: list[str] = []
    for item in results:
        status = str(getattr(item, "status", ""))
        if status == "generated":
            counts["generated"] += 1
        elif "cache" in status:
            counts["cached"] += 1
        elif status == "failed":
            counts["failed"] += 1
            details.append(f"{getattr(item, 'slot_id', '?')}: {status}")
        else:
            counts["other"] += 1
    return GenerationOutcome(
        planned=len(results),
        generated=counts["generated"],
        from_cache=counts["cached"],
        failed=counts["failed"],
        skipped_no_permission=0 if spending else counts["other"] + counts["generated"],
        details=tuple(details[:10]),
    )
