"""Swappable vision CLIENT for the quality loop (Task B).

Two interchangeable implementations share one ``VisionClientProtocol``:

  * ``FakeVisionClient`` -- deterministic, offline, records its calls. Used in
    ALL tests and in any dry-run wiring. No network.
  * ``VisionClient`` -- the real OpenRouter client (sync ``httpx``), mirroring
    the proven pattern in
    ``research/preprocessor/stages/onboard/vision_reading.py`` but synchronous.
    It builds the brand-agnostic prompt via ``vis_prompt``, downscale-encodes
    the images, posts to OpenRouter with a small retry, parses the JSON reply,
    and caches results on disk.

The API key + model are read from the canonical preprocessor secrets file
(``research/preprocessor/.env``), exposed as the env vars ``OPENROUTER_API_KEY``
and ``OPENROUTER_VISION_MODEL``. The key is NEVER printed or logged.

NOTE: ``httpx`` is imported lazily inside the network path so that merely
importing this module (e.g. in the offline test suite) never requires httpx.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Optional, Protocol

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 60.0
_MAX_ATTEMPTS = 3
# US-2026-08-19: 1568px max edge consumed the LOCAL model's vision-token
# budget (a 9B Q4 Qwen image tiles to thousands of tokens; the JSON reply then
# truncated). 1024px is still ample for layout review and leaves the model
# room to close the rating object.
_MAX_EDGE = 1024
_JPEG_QUALITY = 85

# Bumping this invalidates every cached score (prompt semantics changed).
PROMPT_VERSION = "vis-1.0"

# Cheap default per the spec (Gemini Flash) when no model is configured.
_FALLBACK_MODEL = "google/gemini-2.0-flash-001"

# Canonical secrets file (the preprocessor's .env).
_ENV_PATH = Path(__file__).resolve().parents[1] / "preprocessor" / ".env"

# On-disk cache lives beside the reference library.
_CACHE_DIR = Path(__file__).resolve().parent / "references" / ".vis_cache"


def _loads_lenient(raw: str) -> dict:
    """Parse a model's JSON reply, tolerating a markdown code fence.

    Even under ``response_format={"type":"json_object"}`` some OpenRouter
    providers (notably the Anthropic family) satisfy the contract by wrapping
    the object in a ```json ... ``` fence. A bare ``json.loads`` then fails.
    We strip an optional fence (and any leading/trailing prose) by extracting
    the outermost ``{...}`` span before parsing, so the client works across
    every provider rather than only the fence-free ones.
    """
    text = raw.strip()
    if text.startswith("```"):
        # drop the opening fence line (``` or ```json) and the closing fence
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last resort: extract the outermost object span
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        # US-2026-08-19: a small local model (LM Studio Q4) occasionally emits
        # UNBALANCED JSON (one missing closing brace for the nested rating
        # object). Repair by appending the missing closing braces — a trailing
        # `}` with an unmatched open depth is a machine-truncation quirk, and
        # the repaired object is still structurally valid for the coerced
        # rating shape.
        opens = text.count("{")
        closes = text.count("}")
        if closes < opens and text.rstrip().endswith("}"):
            repaired = text + "}" * (opens - closes)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        raise


# --------------------------------------------------------------------------- #
# tiny .env reader (KEY=VALUE; no external dependency required)
# --------------------------------------------------------------------------- #
def _read_env_file(name: str, path: Optional[Path] = None) -> Optional[str]:
    """Return the value for ``name`` from the .env file, or None.

    Never raises; never logs. A real env var (already in ``os.environ``) wins
    over the file so deployments can override the canonical secrets. ``path``
    resolves to the module-level ``_ENV_PATH`` at call time (so it stays
    monkeypatchable in tests).
    """
    if name in os.environ and os.environ[name]:
        return os.environ[name]
    path = path if path is not None else _ENV_PATH
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == name:
                val = val.strip().strip('"').strip("'")
                return val or None
    except OSError:
        return None
    return None


# --------------------------------------------------------------------------- #
# protocol
# --------------------------------------------------------------------------- #
class VisionClientProtocol(Protocol):
    """The single contract both clients satisfy."""

    def score_page(
        self,
        page_png: str,
        reference_pngs: list[str],
        row_ids: list[str],
        row_metadata: dict[str, dict] | None = None,
    ) -> dict[str, dict]:
        """Return ``{row_id: {"score": int, "rationale": str}}``."""
        ...

    def classify(self, page_png: str, candidate_types: list[str]) -> str:
        """Return the single best-matching st_type label for ``page_png``."""
        ...


# --------------------------------------------------------------------------- #
# cache key (exposed for testing)
# --------------------------------------------------------------------------- #
def _prompt_signature(row_ids: list[str], n_reference_images: int,
                      row_metadata: dict[str, dict] | None = None) -> str:
    """Hash of the ACTUAL built prompt for these inputs, so a change to the
    vis_prompt text (or the Director's per-row metadata) busts the cache.
    Lazy import keeps the offline import clean.
    """
    import vis_prompt
    system_prompt, user_prompt = vis_prompt.build_prompt(
        sorted(row_ids), n_reference_images, row_metadata=row_metadata
    )
    return hashlib.sha256(
        (system_prompt + "\x00" + user_prompt).encode("utf-8")
    ).hexdigest()[:16]


def cache_key(
    page_png: str,
    reference_pngs: list[str],
    row_ids: list[str],
    *,
    model: str = "",
    prompt_sig: str = "",
) -> str:
    """sha256 over the page bytes + each reference's bytes + sorted row ids +
    the MODEL + a prompt signature + PROMPT_VERSION. Sensitive to every input
    that changes the score, so swapping to a stronger grader (or editing the
    prompt) busts the cache instead of silently serving old scores.
    """
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode("utf-8"))
    h.update(b"\x00model\x00")
    h.update((model or "").encode("utf-8"))
    h.update(b"\x00psig\x00")
    h.update((prompt_sig or "").encode("utf-8"))
    h.update(b"\x00page\x00")
    h.update(Path(page_png).read_bytes())
    for ref in reference_pngs:
        h.update(b"\x00ref\x00")
        h.update(Path(ref).read_bytes())
    h.update(b"\x00rows\x00")
    h.update("\x1f".join(sorted(row_ids)).encode("utf-8"))
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# image encoding (downscale -> JPEG -> base64 data URL)
# --------------------------------------------------------------------------- #
def _encode_image(path: str, *, max_edge: int = _MAX_EDGE) -> str:
    """Downscale (max edge ~1568px) and base64-encode an image as a data URL.

    Falls back to the raw PNG bytes if PIL cannot process the file.
    """
    from PIL import Image  # local import: PIL is only needed on the real path

    p = Path(path)
    try:
        img = Image.open(p).convert("RGB")
        if max(img.size) > max_edge:
            img.thumbnail((max_edge, max_edge))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"


# --------------------------------------------------------------------------- #
# fake client (offline; used in all tests)
# --------------------------------------------------------------------------- #
class FakeVisionClient:
    """Returns scripted results filtered to the requested rows; records calls.

    Never touches the network or the filesystem cache.
    """

    def __init__(self, scripted: dict[str, dict]) -> None:
        self._scripted = scripted
        # each entry is (page_png, reference_pngs, row_ids) for assertions
        self.calls: list[tuple[str, list[str], list[str]]] = []
        # classification scripting: either a constant label via
        # ``classify_return``, or a per-png mapping via ``classify_map``.
        self.classify_return: str = "OTHER"
        self.classify_map: dict[str, str] = {}
        self.classify_calls: list[tuple[str, list[str]]] = []
        # layout-extraction scripting (Phase 4): extract_json returns a COPY of
        # ``extract_return``; calls are recorded for assertions. No network.
        self.extract_return: dict = {}
        self.extract_calls: list[tuple[str, str, str]] = []

    def score_page(
        self,
        page_png: str,
        reference_pngs: list[str],
        row_ids: list[str],
        row_metadata: dict[str, dict] | None = None,
    ) -> dict[str, dict]:
        self.calls.append((page_png, list(reference_pngs), list(row_ids)))
        return {
            rid: self._scripted[rid]
            for rid in row_ids
            if rid in self._scripted
        }

    def classify(self, page_png: str, candidate_types: list[str]) -> str:
        """Scripted classification; records the call. No network/filesystem."""
        self.classify_calls.append((page_png, list(candidate_types)))
        return self.classify_map.get(page_png, self.classify_return)

    def extract_json(self, page_png: str, system_prompt: str, user_prompt: str) -> dict:
        """Scripted layout-template extraction; records the call. No network."""
        self.extract_calls.append((page_png, system_prompt, user_prompt))
        return dict(self.extract_return)


# --------------------------------------------------------------------------- #
# real client (OpenRouter, sync httpx, on-disk cache, retry)
# --------------------------------------------------------------------------- #
class VisionClient:
    """Real OpenRouter vision client (synchronous).

    Construction never hits the network and never requires a key; the key is
    only required when ``score_page`` actually needs to call the API. Missing
    key raises a CLEAR ``ValueError`` rather than issuing a malformed request.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        *,
        api_base: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: float = _TIMEOUT,
        referer: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        # Defaults pulled from the canonical secrets file / env. We do NOT
        # store the key anywhere it could be logged; it stays a private attr.
        self._api_key = api_key or _read_env_file("OPENROUTER_API_KEY")
        self.model = model or _read_env_file("OPENROUTER_VISION_MODEL") or _FALLBACK_MODEL
        # Provider-agnostic endpoint: the FULL OpenAI-compatible chat/completions
        # URL. Defaults to OpenRouter; VISION_API_BASE (env/.env) or an explicit
        # api_base points the same client at a local Ollama / self-hosted vLLM
        # endpoint, so switching providers is a config flip, never a code change.
        self._api_base = api_base or _read_env_file("VISION_API_BASE") or _OPENROUTER_URL
        self._cache_dir = Path(cache_dir) if cache_dir else _CACHE_DIR
        self._timeout = timeout
        self._referer = referer
        self._title = title

    # -- cache helpers ----------------------------------------------------- #
    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def _cache_read(self, key: str) -> Optional[dict[str, dict]]:
        path = self._cache_path(key)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _cache_write(self, key: str, value: dict[str, dict]) -> None:
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(key).write_text(
                json.dumps(value), encoding="utf-8"
            )
        except OSError:
            # caching is best-effort; never fail a score over a cache write
            pass

    # -- main entrypoint --------------------------------------------------- #
    def score_page(
        self,
        page_png: str,
        reference_pngs: list[str],
        row_ids: list[str],
        row_metadata: dict[str, dict] | None = None,
    ) -> dict[str, dict]:
        key = cache_key(
            page_png, reference_pngs, row_ids,
            model=self.model,
            prompt_sig=_prompt_signature(
                row_ids, len(reference_pngs), row_metadata=row_metadata
            ),
        )
        cached = self._cache_read(key)
        if cached is not None:
            return cached

        if not self._api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is missing: cannot call the vision model. "
                "Set it in research/preprocessor/.env or pass api_key=..."
            )

        result = self._call_openrouter(
            page_png, reference_pngs, row_ids, row_metadata=row_metadata
        )
        self._cache_write(key, result)
        return result

    # -- one-shot page-type classification --------------------------------- #
    def classify(self, page_png: str, candidate_types: list[str]) -> str:
        """Ask the model which candidate st_type best matches ``page_png``.

        Minimal one-shot call (no references): a tight system instruction +
        the page image; expects ``{"st_type": "..."}``. The reply is clamped
        to one of ``candidate_types`` (falling back to the last candidate,
        conventionally ``"OTHER"``). Never logs the key.
        """
        if not self._api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is missing: cannot call the vision model. "
                "Set it in research/preprocessor/.env or pass api_key=..."
            )

        import httpx  # local import: only needed for the real network call

        options = ", ".join(candidate_types)
        system_prompt = (
            "You classify a single slide/page by its COMPOSITION/page-type. "
            "Ignore brand colours and content. Reply with exactly one of the "
            f"allowed labels: {options}."
        )
        user_prompt = (
            "Which page type best matches this page? Reply with exactly one "
            f"of: {options}. Respond as JSON: {{\"st_type\": \"...\"}}."
        )
        content: list[dict] = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": _encode_image(page_png)}},
        ]
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._referer:
            headers["HTTP-Referer"] = self._referer
        if self._title:
            headers["X-Title"] = self._title

        last_exc: Optional[Exception] = None
        with httpx.Client(timeout=self._timeout) as client:
            for _ in range(_MAX_ATTEMPTS):
                try:
                    resp = client.post(
                        self._api_base, json=payload, headers=headers
                    )
                    if resp.status_code != 200:
                        last_exc = RuntimeError(
                            f"OpenRouter returned HTTP {resp.status_code}"
                        )
                        continue
                    data = resp.json()
                    raw = data["choices"][0]["message"]["content"]
                    parsed = _loads_lenient(raw)
                    label = str(parsed.get("st_type", "")).strip()
                    if label in candidate_types:
                        return label
                    return candidate_types[-1]
                except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                    last_exc = exc
                    continue

        raise RuntimeError(
            f"OpenRouter classify call failed after {_MAX_ATTEMPTS} attempts"
        ) from last_exc

    # -- generic single-image JSON extraction (Phase 4 layout templates) --- #
    def extract_json(self, page_png: str, system_prompt: str, user_prompt: str) -> dict:
        """Post system+user prompts + ONE image; return the parsed JSON object.

        Used by the reference LayoutTemplate extraction. Honors the configured
        endpoint/model/key (never logged); parses leniently (fenced replies OK).
        """
        if not self._api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is missing: cannot call the vision model. "
                "Set it in research/preprocessor/.env or pass api_key=..."
            )
        import httpx  # local import: only needed for the real network call

        content: list[dict] = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": _encode_image(page_png)}},
        ]
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._referer:
            headers["HTTP-Referer"] = self._referer
        if self._title:
            headers["X-Title"] = self._title

        last_exc: Optional[Exception] = None
        with httpx.Client(timeout=self._timeout) as client:
            for attempt in range(_MAX_ATTEMPTS):
                # LM Studio rejects `response_format: json_object`; retry
                # without it (lenient parsing handles the plain reply).
                _payload = dict(payload)
                if attempt >= 1:
                    _payload.pop("response_format", None)
                try:
                    resp = client.post(self._api_base, json=_payload, headers=headers)
                    if resp.status_code != 200:
                        last_exc = RuntimeError(
                            f"vision endpoint HTTP {resp.status_code}"
                        )
                        continue
                    data = resp.json()
                    raw = data["choices"][0]["message"]["content"]
                    return _loads_lenient(raw)
                except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                    last_exc = exc
                    continue
        raise RuntimeError(
            f"vision extract_json failed after {_MAX_ATTEMPTS} attempts"
        ) from last_exc

    # -- the network path (httpx imported lazily) -------------------------- #
    def _call_openrouter(
        self,
        page_png: str,
        reference_pngs: list[str],
        row_ids: list[str],
        row_metadata: dict[str, dict] | None = None,
    ) -> dict[str, dict]:
        import httpx  # local import: only needed for the real network call

        from vis_prompt import build_prompt

        system_prompt, user_prompt = build_prompt(
            row_ids, len(reference_pngs), row_metadata=row_metadata
        )

        content: list[dict] = [{"type": "text", "text": user_prompt}]
        for img in [page_png, *reference_pngs]:
            content.append(
                {"type": "image_url",
                 "image_url": {"url": _encode_image(img)}}
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "max_tokens": 1500,   # local models (LM Studio) truncate at their
                                  # default cap — a cut JSON then fails the
                                  # lenient parser. A generous budget lets the
                                  # rating object close.
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._referer:
            headers["HTTP-Referer"] = self._referer
        if self._title:
            headers["X-Title"] = self._title

        last_exc: Optional[Exception] = None
        with httpx.Client(timeout=self._timeout) as client:
            for attempt in range(_MAX_ATTEMPTS):
                # LM Studio (the local vision endpoint via VISION_API_BASE)
                # rejects `response_format: {"type":"json_object"}` (it wants
                # json_schema or text). Retry without it — the lenient JSON
                # parser already handles non-fenced replies.
                _payload = dict(payload)
                if attempt >= 1:
                    _payload.pop("response_format", None)
                try:
                    resp = client.post(
                        self._api_base, json=_payload, headers=headers
                    )
                    if resp.status_code != 200:
                        last_exc = RuntimeError(
                            f"OpenRouter returned HTTP {resp.status_code}"
                        )
                        continue
                    data = resp.json()
                    if "choices" not in data:
                        last_exc = RuntimeError(f"no choices in response: {str(data)[:200]}")
                        continue
                    raw = data["choices"][0]["message"]["content"]
                    parsed = _loads_lenient(raw)
                    return self._coerce(parsed, row_ids)
                except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                    last_exc = exc
                    continue

        raise RuntimeError(
            f"OpenRouter vision call failed after {_MAX_ATTEMPTS} attempts: {last_exc}"
        ) from last_exc

    @staticmethod
    def _coerce(parsed: dict, row_ids: list[str]) -> dict[str, dict]:
        """Keep only requested rows, coerce score->int, rationale->str."""
        out: dict[str, dict] = {}
        for rid in row_ids:
            entry = parsed.get(rid)
            if not isinstance(entry, dict):
                continue
            try:
                score = int(entry.get("score"))
            except (TypeError, ValueError):
                continue
            rationale = entry.get("rationale")
            out[rid] = {
                "score": score,
                "rationale": str(rationale) if rationale is not None else "",
            }
        return out
