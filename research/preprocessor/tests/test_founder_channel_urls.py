"""Optional founder channel URL fields on ClientInput.

The founder-asset scraper needs the founder's YouTube + Instagram URLs
(ingested from Airtable via the existing payload). These are OPTIONAL
fields — existing payloads without them must still validate (backward
compatible), and payloads with them must round-trip the values.
"""

from __future__ import annotations

from models import ClientInput


def _base_client() -> dict:
    return {
        "name": "Jane Founder",
        "company": "Acme Co",
        "website_url": "https://acme.example",
        "brand_hex_dark": "#1A2540",
        "brand_hex_light": "#F5F0E8",
        "brand_hex_accent": "#E97E47",
    }


def test_founder_urls_default_none_when_absent() -> None:
    """A payload WITHOUT the new fields still validates; all default None."""
    client = ClientInput(**_base_client())
    assert client.founder_youtube_url is None
    assert client.founder_instagram_url is None
    assert client.founder_linkedin_url is None


def test_founder_urls_round_trip_when_present() -> None:
    """A payload WITH the new fields round-trips the values."""
    payload = _base_client()
    payload["founder_youtube_url"] = "https://youtube.com/@janefounder"
    payload["founder_instagram_url"] = "https://instagram.com/janefounder"
    payload["founder_linkedin_url"] = "https://linkedin.com/in/janefounder"

    client = ClientInput(**payload)

    assert client.founder_youtube_url == "https://youtube.com/@janefounder"
    assert client.founder_instagram_url == "https://instagram.com/janefounder"
    assert client.founder_linkedin_url == "https://linkedin.com/in/janefounder"


def test_founder_urls_are_optional_str_type() -> None:
    """Fields accept plain strings (no hard URL-format validation)."""
    client = ClientInput(
        **_base_client(),
        founder_youtube_url="not-a-url-but-still-accepted",
    )
    assert client.founder_youtube_url == "not-a-url-but-still-accepted"
