from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "dmc-renderer" / "fixtures" / "calibration"
for path in (ROOT / "research", ROOT / "research" / "calibration", ROOT / "dmc-renderer"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from render_fixtures import run_calibration_fixtures  # noqa: E402
from calibration_fixtures_v3 import envelope_for_profile  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_pins_eight_diverse_redacted_fixture_profiles() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())

    assert len(manifest["fixtures"]) == 8
    profiles = []
    for entry in manifest["fixtures"]:
        path = FIXTURE_ROOT / entry["path"]
        fixture = json.loads(path.read_text())
        profiles.append(fixture)
        assert entry["sha256"] == sha256(path)
        assert entry["expected_product_profile"] == "dmc_house_20_face"
        assert entry["consent_status"] in {"synthetic", "internal_redacted_evaluation"}
        assert entry["redaction_status"] in {"not_applicable", "redacted"}
        assert entry["expected_gate_state"] in {
            "rejected",
            "draft",
            "review_candidate",
            "ship_ready",
        }
        if fixture["origin"] == "real-derived":
            assert entry["redaction_status"] == "redacted"

    assert len({profile["industry"] for profile in profiles}) >= 6
    assert len({profile["tone"] for profile in profiles}) >= 5
    assert len({profile["asset_availability"] for profile in profiles}) >= 5
    assert len({profile["evidence_density"] for profile in profiles}) >= 4
    assert len({profile["visual_brand"] for profile in profiles}) == 8


def test_expected_blockers_are_explicit_and_only_complete_profiles_are_reviewable() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())

    for entry in manifest["fixtures"]:
        if entry["expected_gate_state"] == "rejected":
            assert entry["expected_blockers"]
        else:
            assert entry["expected_blockers"] == []


def test_fixture_files_contain_no_absolute_paths_or_obvious_secrets() -> None:
    for path in FIXTURE_ROOT.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "/Users/" not in text
        assert "OPENROUTER_API_KEY" not in text
        assert "FAL_KEY" not in text


def test_calibration_runner_executes_every_recipe_and_preserves_expected_blockers(
    tmp_path: Path,
) -> None:
    class Failure:
        def __init__(self, code: str):
            self.code = code

    class Blocked(RuntimeError):
        def __init__(self, codes: list[str]):
            self.failures = tuple(Failure(code) for code in codes)
            super().__init__(", ".join(codes))

    def fake_builder(envelope, output_dir, cleanup=False, release_context=None):
        fixture_id = envelope["payload"]["meta"]["client_slug"]
        if "christoph" in fixture_id:
            raise Blocked(["ungrounded_numeric_candidate", "face_count_mismatch", "case_count_mismatch", "missing_required"])
        if "sparse" in fixture_id:
            raise Blocked(["missing_required", "required_proof_missing"])
        # The six synthetic "valid" envelopes are rejected on the density
        # blockers (no real photos; the documented G24 gap) since the
        # 2026-08-08 pixel-policy recalibration to Richard's corpus.
        return {
            "release_state": "rejected",
            "gate_report_sha256": "a" * 64,
            "failures": [
                {"code": "visual_density_below_reference"},
                {"code": "dead_space_region"},
                {"code": "ink_occupancy_out_of_bounds"},
                {"code": "whitespace_fraction_out_of_bounds"},
                {"code": "asset_reused_across_faces"},
            ],
        }

    report = run_calibration_fixtures(
        FIXTURE_ROOT / "manifest.json",
        output_root=tmp_path / "run",
        builder=fake_builder,
    )

    assert len(report["fixtures"]) == 8
    assert all(item["matched_expectation"] for item in report["fixtures"])


def test_every_fixture_recipe_preserves_internal_face_allocation_contract(
    tmp_path: Path,
) -> None:
    """Every VALID fixture must allocate exactly as many faces as its format
    list claims. The christoph-known-failures recipe is the deliberate
    exception: its manifest declares expected_gate_state=rejected with the
    face_count_mismatch blocker, so its 17 faces against a 20-face format
    allocation IS the failure the recipe exists to produce."""
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    EXPECTED_MISALLOCATED = {
        entry["fixture_id"]
        for entry in manifest["fixtures"]
        if "face_count_mismatch" in entry.get("expected_blockers", [])
    }

    for entry in manifest["fixtures"]:
        if entry["fixture_id"] in EXPECTED_MISALLOCATED:
            continue
        profile = json.loads((FIXTURE_ROOT / entry["path"]).read_text())
        envelope = envelope_for_profile(profile, tmp_path / entry["fixture_id"])
        face_count = len(envelope["editorial_brief_v3"]["faces"])
        allocated_face_count = sum(
            2 if page_format == "a3" else 1
            for page_format in envelope["editorial_brief_v3"]["formats"]
        )
        assert allocated_face_count == face_count, entry["fixture_id"]


def test_materially_different_clients_produce_distinct_plans_and_pdfs(
    tmp_path: Path,
) -> None:
    """Blocker 3 regression: client character must reach rendered decisions."""
    import hashlib
    import json as json_module

    from build_v3 import ReleaseContextV3, build_and_render_v3
    from calibration_fixtures_v3 import envelope_for_profile

    calibration = ReleaseContextV3(allow_synthetic_assets=True)
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures" / "calibration"
    plan_hashes = {}
    pdf_hashes = {}
    for name in (
        "apex.json",
        "service-business.json",
        "product-business.json",
        "craft-trade.json",
        "medical-practice.json",
    ):
        profile = json_module.loads((fixture_dir / name).read_text(encoding="utf-8"))
        envelope = envelope_for_profile(profile, tmp_path / name / "assets")
        result = build_and_render_v3(
            envelope,
            output_dir=tmp_path / name / "build",
            cleanup=False,
            release_context=calibration,
        )
        # Since the 2026-08-08 pixel-policy recalibration to Richard's corpus,
        # these synthetic envelopes cannot reach review_candidate: they carry
        # no real photographs, so they land below the reference ink floor and
        # above the reference whitespace ceiling (documented as the "no
        # pictures" gap, G24). The gate is CORRECT — the fixtures are the
        # lighter side — so they are expected to be REJECTED for the density
        # blockers. The distinctness of plans and PDFs below is the point of
        # this test and holds regardless of release state.
        codes = {failure["code"] for failure in result.get("failures", ())}
        assert result["release_state"] == "rejected", (name, result["release_state"])
        assert {
            "visual_density_below_reference",
            "dead_space_region",
            "ink_occupancy_out_of_bounds",
        } <= codes, (name, sorted(codes))
        plan = json_module.loads(Path(result["composition_plan_path"]).read_text())
        selections = tuple(
            (item["selected"]["family_id"], item["selected"]["variant_id"])
            for item in plan["decisions"]
        )
        plan_hashes[name] = hashlib.sha256(
            json_module.dumps(selections).encode("utf-8")
        ).hexdigest()
        pdf_hashes[name] = result["hashes"]["raw_pdf_sha256"]

    # Materially different characters (expressive/dense vs restrained/light
    # vs technical) must select differently; near-cousin profiles (service vs
    # craft, apex vs medical) may share per-face selections while their
    # evidence density still renders visibly different pages. Both halves are
    # asserted: at least three distinct selection plans, and five distinct
    # rendered PDFs.
    assert len(set(plan_hashes.values())) >= 3, plan_hashes
    assert plan_hashes["apex.json"] != plan_hashes["service-business.json"]
    assert plan_hashes["apex.json"] != plan_hashes["product-business.json"]
    assert plan_hashes["service-business.json"] != plan_hashes["product-business.json"]
    assert len(set(pdf_hashes.values())) == 5, pdf_hashes


def test_apex_dense_fixture_builds_at_reference_density(tmp_path: Path) -> None:
    """The apex-dense envelope must close the measured density gap.

    Pinned against the Apex reference bands
    (research/calibration/reference-bands/apex-v1.json): mean words per face
    inside the corpus word-density range and pixel features inside the
    corpus bands. After the 2026-08-06 color-field work (dark family fields,
    reversed type, blue gradient photo assets) the candidate measures mean
    ink 0.227 / whitespace 0.751, with the heavy reference families
    (editorial 0.304, false_belief 0.308, summary 0.369, collaboration
    0.339) inside their own family ink bands. Floors are pinned slightly
    below those achieved levels so the gain cannot silently regress while
    staying stable across raster rounding.
    """
    import statistics

    import fitz

    from build_v3 import PIXEL_POLICY_PATH, ReleaseContextV3, build_and_render_v3
    from quality_loop.gates.pixels_v3 import (
        PixelSample,
        load_pixel_policy,
        measure_face_pixels,
    )

    profile = json.loads((FIXTURE_ROOT / "apex-dense.json").read_text())
    envelope = envelope_for_profile(profile, tmp_path / "assets")
    result = build_and_render_v3(
        envelope,
        output_dir=tmp_path / "build",
        cleanup=False,
        release_context=ReleaseContextV3(allow_synthetic_assets=True),
    )
    # The COPY-density contract below is the point of this test and holds.
    # The pixel gates (dead-space / ink / whitespace, recalibrated to
    # Richard's corpus on 2026-08-08) still REJECT the synthetic envelope
    # because it carries no real photographs — the documented "no pictures"
    # gap (G24) that real client assets close, not code. So the honest
    # release state is rejected on the density blockers, never ship_ready.
    codes = {failure["code"] for failure in result.get("failures", ())}
    assert result["release_state"] == "rejected", result["release_state"]
    assert {"visual_density_below_reference", "dead_space_region"} <= codes, sorted(codes)

    contract = json.loads(Path(result["contract_path"]).read_text())
    face_words: dict[str, int] = {}
    with fitz.open(Path(result["pdf_path"])) as document:
        for fragment, page in zip(contract["fragments"], document, strict=True):
            words = page.get_text("words")
            if fragment["format"] == "a3" and len(fragment["face_ids"]) == 2:
                midpoint = page.rect.width / 2
                left = sum(1 for word in words if (word[0] + word[2]) / 2 < midpoint)
                face_words[fragment["face_ids"][0]] = left
                face_words[fragment["face_ids"][1]] = len(words) - left
            else:
                face_words[fragment["face_ids"][0]] = len(words)
    assert len(face_words) == 20
    mean_words = statistics.mean(face_words.values())
    assert mean_words >= 240, face_words
    # The belief page reached its corpus word band (417-495) on 2026-08-06;
    # the floor locks that gain with a small pad.
    belief_face = sorted(face_words)[4]
    assert face_words[belief_face] >= 400, face_words
    # Role-band conformance (2026-08-07): every face's word count sits
    # inside its role's band measured from the complete reference atlas.
    # This is the definitive density criterion; the cover is a declaration
    # (127-170), the argument pages are dense (354+), and every face is
    # judged against Richard's own pages in the same role.
    ROLE_BY_INDEX = {
        1: "cover", 2: "outlook", 3: "about", 4: "status_quo",
        5: "false_beliefs", 6: "case_study", 7: "theory", 8: "theory",
        9: "theory", 10: "case_study", 11: "theory", 12: "case_study",
        13: "theory", 14: "mechanism", 15: "trust_proof", 16: "summary",
        17: "objections", 18: "collaboration", 19: "status_quo", 20: "cta",
    }
    role_bands = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "research/calibration/reference-bands/corpus-v2.json"
        ).read_text()
    )["role_word_bands"]["bands"]
    # The collaboration face (face.18) is the known below-band outlier: its A3
    # pathway process renders through the SVG component bridge (device-svg),
    # whose text PyMuPDF's get_text("words") does not count, so the face's
    # countable copy sits at ~208 against the corpus band min 239. The 2026-08-07
    # density drive explicitly listed "mechanism/collab/theory faces vs their
    # own word bands" as REMAINING work; this assertion pins every OTHER face
    # in-band and records the collaboration shortfall instead of hiding it.
    COLLABORATION_OUTLIER = "face.18"
    ordered_faces = sorted(face_words)
    for index, face_id in enumerate(ordered_faces, start=1):
        if face_id == COLLABORATION_OUTLIER:
            assert face_words[face_id] < role_bands["collaboration"]["min"], (
                "the collaboration outlier is pinned BELOW the band; if it now "
                "meets the band, remove the exemption"
            )
            continue
        band = role_bands[ROLE_BY_INDEX[index]]
        assert band["min"] <= face_words[face_id] <= band["max"], (
            face_id,
            ROLE_BY_INDEX[index],
            face_words[face_id],
            band,
        )
    # Band-steered editorial modes (2026-08-07): the dense outlook and
    # status-quo faces select the text-led variant and carry corpus-band
    # copy; the light cover and about faces stay photo-led.
    plan = json.loads(Path(result["composition_plan_path"]).read_text())
    editorial_variants = {
        item["face_id"]: item["selected"]["variant_id"]
        for item in plan["decisions"]
        if item["selected"]["family_id"] == "editorial_lead"
    }
    assert editorial_variants["face.01"] == "photo_bleed"
    assert editorial_variants["face.03"] == "photo_bleed"
    assert editorial_variants["face.02"] == "proof_rail"
    assert editorial_variants["face.04"] == "proof_rail"
    ordered = sorted(face_words)
    assert face_words[ordered[1]] >= 345, face_words
    assert face_words[ordered[3]] >= 345, face_words

    family_by_face = {
        fragment_face: fragment["composition"]["family_id"]
        for fragment in contract["fragments"]
        for fragment_face in fragment["face_ids"]
    }
    policy = load_pixel_policy(PIXEL_POLICY_PATH)
    raster_dir = tmp_path / "build" / "face-rasters"
    features = [
        measure_face_pixels(
            PixelSample(
                face_id=face_id,
                family_id=family_by_face[face_id],
                image_path=str(raster_dir / f"{face_id}.png"),
                accent_rgb=(64, 128, 160),
            ),
            policy.families[family_by_face[face_id]],
            policy.measurement,
        )
        for face_id in sorted(face_words)
    ]
    mean_ink = statistics.mean(item.ink_occupancy for item in features)
    mean_whitespace = statistics.mean(item.whitespace_fraction for item in features)
    mean_bands = statistics.mean(item.type_rhythm_bands for item in features)
    assert mean_ink >= 0.19, mean_ink
    assert mean_whitespace <= 0.80, mean_whitespace
    assert mean_whitespace >= 0.45, mean_whitespace
    assert mean_bands >= 12, mean_bands

    # The heavy reference families must keep their color fields: per-family
    # mean ink floors sit a small pad below the measured 2026-08-06 levels
    # (editorial 0.304, false_belief 0.308, summary 0.369, collaboration
    # 0.339), each of which lies inside its apex-v1 family ink band.
    #
    # Floors were re-pinned 2026-08-13 after the Aug-11 family-CSS typography
    # rework (stat numerals 40pt/34pt -> 26pt) measurably lowered ink while
    # staying inside the corpus bands: editorial 0.304->0.233, collaboration
    # 0.339->0.235. The corpus band (min 0.1029) is the authority; these pins
    # only guard against silent regression below the CURRENT rendered level.
    ink_by_family: dict[str, list[float]] = {}
    for item in features:
        ink_by_family.setdefault(item.family_id, []).append(item.ink_occupancy)
    family_ink_floors = {
        "editorial_lead": 0.21,
        "false_belief_stack": 0.26,
        "summary_synthesis": 0.31,
        "collaboration_pathway": 0.21,
    }
    for family_id, floor in family_ink_floors.items():
        family_values = ink_by_family.get(family_id)
        if not family_values:
            # The fixture maps no face to this family in this composition;
            # its floor is inert until a face renders through it.
            continue
        family_mean = statistics.mean(family_values)
        assert family_mean >= floor, (family_id, family_mean)
