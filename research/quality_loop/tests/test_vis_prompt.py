

def test_build_prompt_carries_director_metadata() -> None:
    """The reviewer prompt includes the DIRECTOR's intent (visual job,
    argument, density) per row — so the judge scores against the page's
    actual editorial job, not a generic template."""
    from vis_prompt import build_prompt

    _, user = build_prompt(
        ["P11"],
        2,
        row_metadata={
            "P11": {
                "visual_job": "transformation",
                "argument": "Martina Ammon — Von operativem Chaos zu skalierbarer KI-Infrastruktur",
                "density": "dense",
            }
        },
    )
    assert "DIRECTOR'S INTENT" in user
    assert "visual job: transformation" in user
    assert "density: dense" in user
    assert "Martina Ammon" in user


def test_build_prompt_without_metadata_unchanged() -> None:
    from vis_prompt import build_prompt

    _, user = build_prompt(["P11"], 2)
    assert "DIRECTOR'S INTENT" not in user
    assert "visual job" not in user
