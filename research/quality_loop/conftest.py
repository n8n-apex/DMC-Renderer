"""Pytest configuration for the quality_loop package.

Registers the ``slow`` marker so the deck-level real-render proof
(``tests/test_deck_proof.py::test_real_deck_converges_all_pages``) can be gated
out of the fast iteration run via ``-m "not slow"`` while staying runnable.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: marks tests that drive the real whole-deck render (deselect with "
        "-m 'not slow')",
    )
