"""Stage Onboard-0 — capture screenshots + DOM signals via Playwright.

Owns the single browser session. Best-effort cookie dismissal, lazy-load
scroll, hero + full-page screenshots, and one page.evaluate() that returns
the raw DOM blob (parsed later by dom_extract). NEVER raises — failures map
to a status code and empty outputs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright  # re-exported for monkeypatch

from models_onboard import CaptureResult, OnboardRequest

_VIEWPORT = {"width": 1440, "height": 900}
_NAV_TIMEOUT_MS = 30000

CONSENT_TEXTS = (
    "akzeptieren", "alle akzeptieren", "zustimmen", "einverstanden",
    "accept", "accept all", "agree", "i agree", "allow all", "got it",
)

DOM_EVAL_JS = r"""
() => {
  const out = { cssVars: {}, fontHead: null, fontBody: null,
                sampledColors: [], bodyText: "", logoUrl: null };
  try {
    const rootStyle = getComputedStyle(document.documentElement);
    for (let i = 0; i < rootStyle.length; i++) {
      const prop = rootStyle[i];
      if (prop.startsWith("--")) {
        const val = rootStyle.getPropertyValue(prop).trim();
        if (val) out.cssVars[prop] = val;
      }
    }
    const h = document.querySelector("h1, h2");
    const b = document.querySelector("p, body");
    if (h) out.fontHead = getComputedStyle(h).fontFamily;
    if (b) out.fontBody = getComputedStyle(b).fontFamily;

    const sel = "header, nav, h1, h2, button, a.btn, .hero, [class*=hero]";
    const seen = [];
    document.querySelectorAll(sel).forEach((el) => {
      const cs = getComputedStyle(el);
      [cs.color, cs.backgroundColor, cs.borderColor].forEach((c) => {
        if (c && c !== "rgba(0, 0, 0, 0)" && !seen.includes(c)) seen.push(c);
      });
    });
    out.sampledColors = seen.slice(0, 30);
    out.bodyText = (document.body ? document.body.innerText : "").slice(0, 500);

    const logo = document.querySelector(
      "header img, img[alt*=logo i], img[class*=logo i], a[href='/'] img");
    if (logo && logo.src) out.logoUrl = logo.src;
  } catch (e) {}
  return out;
}
"""


def _looks_blank(raw: dict) -> bool:
    """True if the page produced no usable content (likely an unrendered SPA)."""
    if not raw:
        return True
    colors = raw.get("sampledColors") or []
    text = (raw.get("bodyText") or "").strip()
    return len(colors) == 0 and len(text) == 0


async def _dismiss_consent(page) -> None:
    """Best-effort cookie/consent dismissal. Never raises."""
    try:
        buttons = await page.query_selector_all("button, a, [role=button]")
        for btn in buttons:
            try:
                label = (await btn.inner_text()).strip().lower()
            except Exception:
                continue
            if any(t in label for t in CONSENT_TEXTS):
                try:
                    await btn.click(timeout=2000)
                    return
                except Exception:
                    continue
    except Exception:
        return


async def _scroll_to_trigger_lazy(page) -> None:
    try:
        await page.evaluate(
            "async () => { for (let y=0; y<document.body.scrollHeight; y+=600)"
            " { window.scrollTo(0, y); await new Promise(r=>setTimeout(r,80)); }"
            " window.scrollTo(0,0); }"
        )
    except Exception:
        return


async def capture(
    request: OnboardRequest, *, output_dir: Path, timeout_ms: int = _NAV_TIMEOUT_MS
) -> CaptureResult:
    output_dir = Path(output_dir)
    hero_path = output_dir / "hero.png"
    fullpage_path = output_dir / "fullpage.png"
    notes: list[str] = []

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport=_VIEWPORT)
                try:
                    # `domcontentloaded` is reliable; `networkidle` hangs on
                    # marketing sites whose chat widgets / analytics never let
                    # the network idle (observed: some sites time out at 30s on
                    # networkidle). Then best-effort wait for full load + a
                    # short settle, both bounded so we never hang.
                    await page.goto(request.website_url,
                                    wait_until="domcontentloaded", timeout=timeout_ms)
                    try:
                        await page.wait_for_load_state("load", timeout=8000)
                    except Exception:
                        pass
                    await asyncio.sleep(1.0)  # let fonts/hero paint settle
                except Exception as exc:  # navigation/timeout
                    notes.append(f"navigation failed: {exc!s}")
                    status = "timeout" if "timeout" in str(exc).lower() else "nav_error"
                    return CaptureResult(hero_png=None, fullpage_png=None,
                                         raw_dom_eval={}, status=status, notes=notes)

                await _dismiss_consent(page)
                await _scroll_to_trigger_lazy(page)

                await page.screenshot(path=str(hero_path), full_page=False)
                await page.screenshot(path=str(fullpage_path), full_page=True)
                raw = await page.evaluate(DOM_EVAL_JS)

                status = "spa_blank" if _looks_blank(raw) else "ok"
                return CaptureResult(
                    hero_png=str(hero_path), fullpage_png=str(fullpage_path),
                    raw_dom_eval=raw or {}, status=status, notes=notes,
                )
            finally:
                await browser.close()
    except Exception as exc:  # playwright launch / unexpected
        notes.append(f"capture failed: {exc!s}")
        return CaptureResult(hero_png=None, fullpage_png=None, raw_dom_eval={},
                             status="nav_error", notes=notes)
