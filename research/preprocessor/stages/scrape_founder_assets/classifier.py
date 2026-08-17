"""VIS asset classifier — the asset "interceptor" Analysis layer.

Where ``quality_gate`` answers a BINARY accept/reject, this classifier answers
the richer question the design (§4.2) asks of every surviving asset: WHAT does
it depict (its ``role``), does it carry overlaid graphic text, and how visually
appealing is it (0-3)? The router (``router.py``) then places each asset into
the report element where it adds the most appeal.

Design (mirrors ``quality_gate.RealVisionGate`` exactly):
  * ``AssetClassifierClient`` — the Protocol: ``classify(path)`` returns a dict
    ``{role, has_overlaid_text, visual_appeal, notes}``.
  * ``FakeAssetClassifier`` — scripted, network-free double for tests.
  * ``RealAssetClassifier`` — the OpenRouter VIS call (sync httpx, lazy import;
    key/model from typed Settings falling back to ``OPENROUTER_API_KEY`` /
    ``OPENROUTER_VISION_MODEL``); fenced-```json tolerant parse.
  * ``classify_asset`` — thin wrapper that fails CLOSED on any error
    (``AssetJudgement(role="other", visual_appeal=0, notes="classifier error: ...")``)
    so a broken/unreadable asset never crashes the run and never gets a
    confident role.

The prompt is brand-agnostic on purpose: it judges what the image DEPICTS +
its quality, and explicitly IGNORES brand identity — no client literal leaks.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Protocol, Union, runtime_checkable

from .models import ASSET_ROLES, AssetJudgement

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 60.0

# Brand-agnostic classification prompt: depiction + quality ONLY, ignore brand.
# Names every role so the model chooses from the closed vocabulary; asks for the
# overlaid-text flag (separates clean photos from designed cards) and a 0-3
# visual-appeal rank used to order assets within a role.
_CLASSIFY_PROMPT = (
    "You are cataloguing one image for a professional business report. "
    "Judge ONLY what the image DEPICTS and its visual quality; IGNORE brand "
    "identity, logos, colours, and any company name. "
    "Choose the single best role describing the SUBJECT from this list:\n"
    "- founder_portrait: a clean, posed photo of one person (head/shoulders).\n"
    "- founder_working: a person at a laptop/phone/desk, working or hands-on.\n"
    "- founder_speaking: a person on stage / presenting / at an event.\n"
    "- group_team: two or more people together (a team or group shot).\n"
    "- lifestyle: an atmospheric / candid / environmental shot.\n"
    "- content_card: a DESIGNED graphic (testimonial card, quote, slide, "
    "video thumbnail) with overlaid title text, captions, or app icons.\n"
    "- logo: a logo or wordmark.\n"
    "- other: anything that fits none of the above.\n"
    "Also report has_overlaid_text: true if title text, captions, pull-quotes, "
    "logos, watermarks, or app icons are COMPOSITED onto the image (incidental "
    "background signage inside a real photo does NOT count). "
    "And visual_appeal: an integer 0-3 (0 worst, 3 best) for how sharp, "
    "specific, and report-worthy the image is. "
    "Reply with ONLY a JSON object of the form "
    '{"role": <one of the roles above>, "has_overlaid_text": <bool>, '
    '"visual_appeal": <integer 0-3>, "notes": <short string>}.'
)

Judgement = Dict[str, object]


@runtime_checkable
class AssetClassifierClient(Protocol):
    """Classifies a single image into a role + appeal judgement dict."""

    def classify(self, image_path: str) -> Judgement:
        """Return ``{role, has_overlaid_text, visual_appeal, notes}``."""
        ...


class FakeAssetClassifier:
    """Scripted, network-free AssetClassifierClient for tests.

    ``scripted`` is either:
      * a single judgement dict — returned for every call, or
      * a dict keyed by ``image_path`` — the matching judgement is returned, or
      * a list of judgements — consumed in sequence (one per call).

    Every classified path is appended to ``self.calls``.
    """

    def __init__(
        self, scripted: Union[Judgement, Dict[str, Judgement], List[Judgement]]
    ):
        self.scripted = scripted
        self.calls: List[str] = []
        self._seq_index = 0

    def classify(self, image_path: str) -> Judgement:
        self.calls.append(image_path)

        if isinstance(self.scripted, list):
            judgement = self.scripted[self._seq_index]
            self._seq_index += 1
            return judgement

        if isinstance(self.scripted, dict):
            # A by-path mapping has string keys to judgement dicts; a single
            # judgement has the "role" key directly.
            if "role" in self.scripted:
                return self.scripted  # single judgement for every call
            return self.scripted[image_path]  # keyed by path

        raise TypeError(f"unsupported scripted type: {type(self.scripted)!r}")


class RealAssetClassifier:
    """OpenRouter-backed classifier (mirrors quality_gate.RealVisionGate, sync).

    Reads its key/model from the constructor, falling back to settings/env
    (``OPENROUTER_API_KEY`` + ``OPENROUTER_VISION_MODEL``). httpx is
    lazy-imported so importing this module stays dependency-light and the test
    suite never needs the network. With no API key, ``classify`` raises a clear
    RuntimeError instead of hitting the network (fail-closed via
    ``classify_asset``).
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

    def classify(self, image_path: str) -> Judgement:
        if not self.api_key:
            raise RuntimeError(
                "asset classifier has no OpenRouter API key "
                "(set OPENROUTER_API_KEY or pass api_key=...)"
            )

        import httpx  # lazy: keep import-time + tests network-free

        from stages.onboard._imaging import encode_image_data_url

        data_url = encode_image_data_url(image_path)
        if not data_url:
            raise RuntimeError(f"could not read image for classifier: {image_path}")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _CLASSIFY_PROMPT},
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

        return _parse_judgement(content)


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


def _parse_judgement(content: str) -> Judgement:
    """Parse the judgement JSON from a reply, tolerating a ```json fence."""
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
        "role": str(parsed.get("role", "other")),
        "has_overlaid_text": bool(parsed.get("has_overlaid_text", False)),
        "visual_appeal": int(parsed.get("visual_appeal", 0)),
        "notes": str(parsed.get("notes", "")),
    }


def _coerce_role(value: object) -> str:
    """Map a raw role string to the closed vocabulary, defaulting to ``other``."""
    role = str(value)
    return role if role in ASSET_ROLES else "other"


def classify_asset(image_path: str, client: AssetClassifierClient) -> AssetJudgement:
    """Classify a single image into an ``AssetJudgement``.

    Fails CLOSED: any exception from the client (no key, network error,
    unparseable reply, unreadable file) yields a neutral
    ``AssetJudgement(role="other", visual_appeal=0, notes="classifier error: ...")``
    rather than raising or asserting a confident role.
    """
    try:
        raw = client.classify(image_path)
        return AssetJudgement(
            role=_coerce_role(raw.get("role", "other")),
            has_overlaid_text=bool(raw.get("has_overlaid_text", False)),
            visual_appeal=int(raw.get("visual_appeal", 0)),
            notes=str(raw.get("notes", "")),
        )
    except Exception as exc:  # fail closed — neutral verdict, never crash
        return AssetJudgement(
            role="other", visual_appeal=0, notes=f"classifier error: {exc}"
        )
