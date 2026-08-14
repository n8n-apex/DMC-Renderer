"""Fake async_playwright for capture tests — no real browser."""

from __future__ import annotations

from pathlib import Path


class _FakePage:
    def __init__(self, raw_dom_eval, raise_on_goto):
        self._raw = raw_dom_eval
        self._raise = raise_on_goto

    async def goto(self, url, wait_until=None, timeout=None):
        if self._raise:
            raise RuntimeError("nav failed")

    async def wait_for_load_state(self, state=None, timeout=None):
        return None

    async def evaluate(self, js):
        # Scroll calls pass JS that isn't our DOM blob; return None for those.
        if isinstance(js, str) and "cssVars" in js:
            return self._raw
        return None

    async def screenshot(self, path=None, full_page=False, **kw):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    async def query_selector_all(self, selector):
        return []

    async def set_viewport_size(self, *a, **k):
        return None


class _FakeBrowser:
    def __init__(self, page): self._page = page
    async def new_page(self, **kw): return self._page
    async def close(self): return None


class _FakeChromium:
    def __init__(self, page): self._page = page
    async def launch(self, **kw): return _FakeBrowser(self._page)


class _FakePW:
    def __init__(self, page): self.chromium = _FakeChromium(page)


class _FakeCtx:
    def __init__(self, page): self._page = page
    async def __aenter__(self): return _FakePW(self._page)
    async def __aexit__(self, *a): return False


def fake_async_playwright(raw_dom_eval=None, raise_on_goto=False):
    page = _FakePage(raw_dom_eval or {}, raise_on_goto)
    def factory():
        return _FakeCtx(page)
    return factory
