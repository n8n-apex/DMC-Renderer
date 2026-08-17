"""Founder-asset scraper stage.

Sources real founder imagery from public channels (YouTube + Instagram),
selects/gates the best candidates, and feeds founder slots.

This package defines the SHARED CONTRACT used by every later piece:

- `models`  — Candidate / ScrapeResult dataclasses + ChannelStatus.
- `clients` — the `ChannelClient` protocol + `FakeChannelClient` test double
              so downstream code is built + tested without network.

Pure + brand-agnostic: shapes only, no client value.
"""
