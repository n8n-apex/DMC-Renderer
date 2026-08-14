"""Tests for the content-addressed fal cache."""
from __future__ import annotations

from stages.assets_cache import cache_lookup, cache_store, cache_salt, fal_cache_key


def _k(**over) -> str:
    base = dict(model="m", prompt="p", negative_prompt="n", aspect="1:1", resolution="2K")
    base.update(over)
    return fal_cache_key(**base)


def test_key_is_deterministic_and_sha256() -> None:
    assert _k() == _k()
    assert len(_k()) == 64


def test_key_sensitive_to_every_input() -> None:
    base = _k()
    assert base != _k(model="m2")
    assert base != _k(prompt="p2")
    assert base != _k(negative_prompt="n2")
    assert base != _k(aspect="3:4")
    assert base != _k(resolution="4K")


def test_key_handles_none_negative() -> None:
    assert isinstance(fal_cache_key(model="m", prompt="p", negative_prompt=None,
                                    aspect="1:1", resolution="2K"), str)


def test_lookup_miss_then_store_then_hit(tmp_path) -> None:
    cache = tmp_path / "cache"
    src = tmp_path / "src.png"
    src.write_bytes(b"PNGDATA")
    key = "abc123"
    assert cache_lookup(cache, key) is None
    stored = cache_store(cache, key, src)
    assert stored is not None and stored.exists()
    hit = cache_lookup(cache, key)
    assert hit is not None and hit.read_bytes() == b"PNGDATA"


def test_cache_dir_none_is_off(tmp_path) -> None:
    src = tmp_path / "s.png"
    src.write_bytes(b"x")
    assert cache_lookup(None, "k") is None
    assert cache_store(None, "k", src) is None


def test_cache_salt_is_deterministic_and_sensitive() -> None:
    base = dict(client_slug="acme", brand_primary="#111111",
                brand_accent="#222222", design_brief={"mood": "calm"},
                builder_version="v1")
    s = cache_salt(**base)
    assert s == cache_salt(**base)              # deterministic
    assert len(s) == 64                         # sha256 hex
    assert s != cache_salt(**{**base, "client_slug": "other"})
    assert s != cache_salt(**{**base, "brand_primary": "#999999"})
    assert s != cache_salt(**{**base, "brand_accent": "#999999"})
    assert s != cache_salt(**{**base, "design_brief": {"mood": "bold"}})
    assert s != cache_salt(**{**base, "builder_version": "v2"})


def test_fal_key_sensitive_to_salt() -> None:
    base = _k()
    assert base != _k(salt="abc")               # salt changes the key
    assert _k(salt="abc") == _k(salt="abc")      # but stays deterministic
