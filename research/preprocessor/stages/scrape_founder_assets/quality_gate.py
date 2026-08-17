"""Quality gate — the acceptance bar for scraped + restored founder assets.

A scraped/restored image is only allowed into a slot if a VISION model judges
it a REAL, SPECIFIC, SHARP photograph of the person/business — NOT generic
stock, NOT blurry, NOT AI-generated/"waxy". This mirrors the closed-loop's
N07 (generic imagery) VIS check; the acceptance bar is the author's explicit
choice.

Design:
  * ``VisionGateClient`` — the Protocol the gate implements: ``assess(path)``
    returns ``{"accept": bool, "reason": str, "score": int}`` (score 0-3;
    accept iff specific + sharp + real).
  * ``FakeVisionGate`` — scripted, network-free double for tests.
  * ``RealVisionGate`` — mirrors the OpenRouter vision call PATTERN from
    ``stages/onboard/vision_reading.py`` (sync httpx here), behind the same
    Protocol so it stays injectable.
  * ``passes_quality`` — thin wrapper that fails CLOSED on any gate error
    (a failed/unreadable asset is NEVER accepted, and never crashes the run).

The prompt is brand-agnostic on purpose: it judges IMAGE QUALITY + SPECIFICITY
only and explicitly ignores brand identity, so no client literal leaks in.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Protocol, Tuple, Union, runtime_checkable

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 60.0

# Brand-agnostic gate prompt: quality + specificity ONLY, ignore brand identity.
#
# The composite-text rejection clause is the load-bearing addition (June 2026):
# a sharp video thumbnail or testimonial CARD with the founder's real face would
# otherwise pass a plain "real + sharp + specific" check, because it IS a sharp
# real photo — just one with title text / logos / app icons composited on top.
# Those designed graphics read as cheap/templated in a report, so the gate must
# reject them while still ACCEPTING real photographs that merely contain
# incidental background signage (office logos, event banners, projected slides).
# This discrimination was verified live on real scraped imagery.
_GATE_PROMPT = (
    "You are selecting a photo for a professional business report. ACCEPT only a "
    "REAL, SHARP PHOTOGRAPH that clearly shows a person and/or their workplace. "
    "REJECT if it is a DESIGNED GRAPHIC rather than a photograph — that is, if it "
    "has OVERLAID title text, captions, pull-quotes, testimonial text, logos, "
    "watermarks, or app icons COMPOSITED onto it, or it looks like a video "
    "thumbnail, promotional card, or presentation slide. Incidental background "
    "signage inside a real photo (office logos on a wall, event banners, projected "
    "slides) is OK and should NOT cause rejection. Also reject blurry, generic "
    "stock, or AI-generated/waxy images. Judge IMAGE QUALITY + SPECIFICITY only; "
    "ignore brand identity. "
    "Reply with ONLY a JSON object of the form "
    '{"accept": <bool>, "reason": <short string>, "score": <integer 0-3>}. '
    "score is 0-3 (0 worst, 3 best); set accept to true ONLY when the image is a "
    "real, sharp, specific photograph FREE of composited/overlaid graphic text."
)

Verdict = Dict[str, object]


@runtime_checkable
class VisionGateClient(Protocol):
    """Assesses a single image for acceptance into a slot."""

    def assess(self, image_path: str) -> Verdict:
        """Return ``{"accept": bool, "reason": str, "score": int}``."""
        ...


class FakeVisionGate:
    """Scripted, network-free VisionGateClient for tests.

    ``scripted`` is either:
      * a single verdict dict — returned for every call, or
      * a dict keyed by ``image_path`` — the matching verdict is returned, or
      * a list of verdicts — consumed in sequence (one per call).

    Every assessed path is appended to ``self.calls``.
    """

    def __init__(self, scripted: Union[Verdict, Dict[str, Verdict], List[Verdict]]):
        self.scripted = scripted
        self.calls: List[str] = []
        self._seq_index = 0

    def assess(self, image_path: str) -> Verdict:
        self.calls.append(image_path)

        if isinstance(self.scripted, list):
            verdict = self.scripted[self._seq_index]
            self._seq_index += 1
            return verdict

        if isinstance(self.scripted, dict):
            # A by-path mapping has string keys to verdict dicts; a single
            # verdict has the "accept"/"reason"/"score" keys directly.
            if "accept" in self.scripted:
                return self.scripted  # single verdict for every call
            return self.scripted[image_path]  # keyed by path

        raise TypeError(f"unsupported scripted type: {type(self.scripted)!r}")


class RealVisionGate:
    """OpenRouter-backed gate (mirrors the vision_reading.py PATTERN, sync).

    Reads its key/model from the constructor, falling back to settings/env
    (``OPENROUTER_API_KEY`` + ``OPENROUTER_VISION_MODEL``). httpx is
    lazy-imported so importing this module stays dependency-light and the test
    suite never needs the network. With no API key, ``assess`` raises a clear
    RuntimeError instead of hitting the network (fail-closed via
    ``passes_quality``).
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = _TIMEOUT,
    ):
        self.api_key = api_key if api_key is not None else _default_api_key()
        self.model = model if model is not None else _default_model()
        self.timeout = timeout

    def assess(self, image_path: str) -> Verdict:
        if not self.api_key:
            raise RuntimeError(
                "quality gate has no OpenRouter API key "
                "(set OPENROUTER_API_KEY or pass api_key=...)"
            )

        import httpx  # lazy: keep import-time + tests network-free

        from stages.onboard._imaging import encode_image_data_url

        data_url = encode_image_data_url(image_path)
        if not data_url:
            raise RuntimeError(f"could not read image for quality gate: {image_path}")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _GATE_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(_OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        return _parse_verdict(content)


def _default_api_key() -> Optional[str]:
    """Read the OpenRouter key from typed Settings, falling back to raw env."""
    try:
        from settings import Settings

        return Settings().openrouter_key_str()
    except Exception:
        return os.getenv("OPENROUTER_API_KEY")


def _default_model() -> str:
    """Read the vision model slug from typed Settings, falling back to env."""
    try:
        from settings import Settings

        return Settings().openrouter_vision_model
    except Exception:
        return os.getenv("OPENROUTER_VISION_MODEL", "anthropic/claude-sonnet-4.6")


def _parse_verdict(content: str) -> Verdict:
    """Parse ``{"accept","reason","score"}`` from a reply, tolerating a fence."""
    text = content.strip()
    if text.startswith("```"):
        # Strip a ```json ... ``` (or plain ```) fence before json.loads.
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    parsed = json.loads(text)
    return {
        "accept": bool(parsed.get("accept", False)),
        "reason": str(parsed.get("reason", "")),
        "score": int(parsed.get("score", 0)),
    }


def passes_quality(image_path: str, gate: VisionGateClient) -> Tuple[bool, str]:
    """Gate a single image. Returns ``(accept, reason)``.

    Fails CLOSED: any exception from the gate (no key, network error,
    unparseable reply, unreadable file) yields ``(False, "quality gate error: ...")``
    rather than raising or accepting a bad asset.
    """
    try:
        verdict = gate.assess(image_path)
        return bool(verdict["accept"]), str(verdict["reason"])
    except Exception as exc:  # fail closed — never accept on error, never crash
        return False, f"quality gate error: {exc}"
