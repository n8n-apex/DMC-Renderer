"""Guard: every generation cache key must be sensitive to the inputs that can
change its output (model / prompt / brand). This is the lock against the
"I changed it and nothing changed" decay. If a future edit drops one of these
inputs from a key, this test fails.
"""
from __future__ import annotations

from stages.assets_cache import fal_cache_key, cache_salt
from stages.restructure_page import restructure_cache_key


def test_fal_key_includes_salt() -> None:
    base = fal_cache_key(model="m", prompt="p", negative_prompt=None,
                         aspect="1:1", resolution="2K", salt="")
    salted = fal_cache_key(model="m", prompt="p", negative_prompt=None,
                           aspect="1:1", resolution="2K", salt="x")
    assert base != salted, "fal key must include the brand/client salt"


def test_salt_includes_brand_and_client() -> None:
    a = cache_salt(client_slug="c1", brand_primary="#1", brand_accent="#2",
                   design_brief=None, builder_version="v")
    b = cache_salt(client_slug="c2", brand_primary="#1", brand_accent="#2",
                   design_brief=None, builder_version="v")
    assert a != b, "salt must distinguish clients"


def test_restructure_key_includes_budget() -> None:
    pd = {"body": "x"}
    assert (restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=900)
            != restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=600))
