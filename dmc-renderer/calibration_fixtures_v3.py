"""Frozen, generation-free envelopes for Phase 5 calibration runs."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image


DMC_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = DMC_ROOT.parent
RESEARCH_ROOT = PROJECT_ROOT / "research"
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))

from composition_registry.registry import load_registry  # noqa: E402


REGISTRY_PATH = RESEARCH_ROOT / "composition_registry" / "families" / "dmc-v1.json"
ATLAS_PATH = RESEARCH_ROOT / "reference-atlas" / "reference-atlas.json"

ROLES = (
    "cover", "outlook", "about", "status_quo", "false_beliefs",
    "case_study", "theory", "theory", "theory", "case_study",
    "theory", "case_study", "theory", "mechanism", "trust_proof",
    "summary", "objections", "collaboration", "status_quo", "cta",
)
FAMILY_BY_ROLE = {
    "cover": "editorial_lead", "outlook": "editorial_lead",
    "about": "editorial_lead", "status_quo": "editorial_lead",
    "false_beliefs": "false_belief_stack", "case_study": "case_narrative",
    "theory": "theory_interpretation", "mechanism": "mechanism_spread",
    "trust_proof": "evidence_wall", "summary": "summary_synthesis",
    "objections": "objection_response", "collaboration": "collaboration_pathway",
    "cta": "closing_cta",
}
MECHANISM_BY_ROLE = {
    "cover": "editorial", "outlook": "editorial", "about": "editorial",
    "status_quo": "editorial", "false_beliefs": "numbered_beliefs",
    "case_study": "case_narrative", "theory": "interpretation",
    "mechanism": "mechanism", "trust_proof": "evidence_wall",
    "summary": "synthesis", "objections": "objection_response",
    "collaboration": "collaboration_pathway", "cta": "closing_cta",
}
ST_BY_ROLE = {
    "cover": "ST-01", "outlook": "ST-02", "about": "ST-05",
    "status_quo": "ST-09", "false_beliefs": "ST-14",
    "case_study": "ST-07A", "theory": "ST-07B", "mechanism": "ST-06",
    "trust_proof": "ST-05", "summary": "ST-FAZIT", "objections": "ST-08",
    "collaboration": "ST-22", "cta": "ST-03",
}


def _asset(
    asset_dir: Path,
    face_id: str,
    semantic_class: str,
    *,
    bands: tuple[tuple[float, tuple[int, int, int]], ...] | None = None,
    gradient: tuple[tuple[float, tuple[int, int, int]], ...] | None = None,
    figure: tuple[tuple[float, float, float, float], ...] | None = None,
    name_suffix: str | None = None,
) -> dict:
    """Write a frozen synthetic asset.

    ``bands`` optionally paints horizontal color bands (fraction-of-height,
    RGB) top to bottom; the default stays the flat warm neutral used by the
    original calibration fixtures, byte-for-byte.

    ``gradient`` optionally paints a vertical multi-stop linear gradient as
    ``((fraction_of_height, rgb), ...)`` stops, deterministically per row,
    so image slots read as saturated photo fields instead of flat voids.

    ``figure`` optionally draws light mid-tone ellipses on top as
    ``((center_x, center_y, radius_x, radius_y), ...)`` in fractions of the
    canvas, giving the field a figure-like photographic subject. All bytes
    are a pure function of the arguments; nothing is random.
    """
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset_id = f"asset.{face_id}.{semantic_class}"
    if name_suffix:
        asset_id = f"{asset_id}.{name_suffix}"
    path = asset_dir / f"{asset_id}.png"
    image = Image.new("RGB", (1200, 1200), (210, 204, 190))
    if bands or gradient or figure:
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
    if gradient:
        stops = sorted(gradient, key=lambda stop: stop[0])
        for row in range(1200):
            position = row / 1199
            lower = stops[0]
            upper = stops[-1]
            for stop in stops:
                if stop[0] <= position:
                    lower = stop
            for stop in reversed(stops):
                if stop[0] >= position:
                    upper = stop
            span = upper[0] - lower[0]
            mix = 0.0 if span <= 0 else (position - lower[0]) / span
            rgb = tuple(
                int(round(lower[1][channel] + mix * (upper[1][channel] - lower[1][channel])))
                for channel in range(3)
            )
            draw.line((0, row, 1200, row), fill=rgb)
    if bands:
        cursor = 0
        for fraction, rgb in bands:
            height = int(round(fraction * 1200))
            draw.rectangle((0, cursor, 1200, min(1200, cursor + height)), fill=rgb)
            cursor += height
    if figure:
        for center_x, center_y, radius_x, radius_y in figure:
            draw.ellipse(
                (
                    int(round((center_x - radius_x) * 1200)),
                    int(round((center_y - radius_y) * 1200)),
                    int(round((center_x + radius_x) * 1200)),
                    int(round((center_y + radius_y) * 1200)),
                ),
                fill=(172, 206, 224),
            )
    image.save(path)
    return {
        "asset_id": asset_id,
        "semantic_class": semantic_class,
        "provenance_kind": "client_supplied",
        "source_locator": "frozen synthetic calibration bank",
        "rights_status": "cleared",
        "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        "local_path": str(path),
        "pixel_width": 1200,
        "pixel_height": 1200,
        "print_width_mm": 80,
        "print_height_mm": 80,
        "allowed_face_ids": [face_id],
        "substitution_policy": "exact_only",
    }


def valid_house_envelope(
    asset_dir: Path,
    *,
    fixture_id: str,
    proof_claim_count: int = 1,
) -> dict:
    registry = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)
    family_by_id = {family.family_id: family for family in registry.families}
    pages: list[dict] = []
    faces: list[dict] = []
    claims: list[dict] = []
    assets: list[dict] = []
    facts: list[dict] = []
    case_index = 0

    for index, role in enumerate(ROLES, start=1):
        face_id = f"face.{index:02d}"
        family = family_by_id[FAMILY_BY_ROLE[role]]
        claim_ids: list[str] = []
        proof_requirements: list[dict] = []
        asset_requirements: list[dict] = []
        selected_asset_ids: list[str] = []
        if role == "case_study":
            case_index += 1
            claim_id = f"claim.{face_id}.proof"
            claim_ids.append(claim_id)
            claims.append(
                {"claim_id": claim_id, "claim_type": "interpretation", "normalized_value": "Nachweisbare Wirkung"}
            )
            asset = _asset(asset_dir, face_id, "identity")
            assets.append(asset)
            selected_asset_ids.append(asset["asset_id"])
            asset_requirements.append(
                {"requirement_id": f"{face_id}.identity", "semantic_class": "identity", "required_for_ship": True}
            )
        elif role == "trust_proof":
            claim_id = f"claim.{face_id}.trust"
            claim_ids.append(claim_id)
            claims.append(
                {"claim_id": claim_id, "claim_type": "interpretation", "normalized_value": "Dokumentierte Vertrauensbasis"}
            )
            # Evidence density: denser clients carry more grounded trust
            # claims, which the composition planner scores against family
            # evidence bounds.
            for extra_index in range(2, proof_claim_count + 1):
                extra_id = f"claim.{face_id}.trust{extra_index}"
                claim_ids.append(extra_id)
                claims.append(
                    {
                        "claim_id": extra_id,
                        "claim_type": "interpretation",
                        "normalized_value": f"Dokumentierter Beleg {extra_index}",
                    }
                )
            proof_requirements.append(
                {"requirement_id": f"{face_id}.trust", "proof_type": "trust", "claim_ids": [claim_id], "required_for_ship": True}
            )
            asset = _asset(asset_dir, face_id, "proof")
            assets.append(asset)
            selected_asset_ids.append(asset["asset_id"])
            asset_requirements.append(
                {"requirement_id": f"{face_id}.proof", "semantic_class": "proof", "required_for_ship": True}
            )
        elif family.family_id == "editorial_lead":
            asset = _asset(asset_dir, face_id, "context")
            assets.append(asset)
            selected_asset_ids.append(asset["asset_id"])

        faces.append(
            {
                "face_id": face_id,
                "face_index": index,
                "role": role,
                "narrative_act": f"calibration act {index}",
                "argument": f"calibration argument {index}",
                "claim_ids": claim_ids,
                "proof_requirements": proof_requirements,
                "asset_requirements": asset_requirements,
                "dominant_mechanism": MECHANISM_BY_ROLE[role],
                "density_band": "moderate",
                "case_id": f"case.{case_index}" if role == "case_study" else None,
            }
        )
        pages.append(
            {
                "slot": index,
                "type": ST_BY_ROLE[role],
                "page_numbers": str(index),
                "data": {
                    "title": "Eine klare Leitidee",
                    "body": "Der Inhalt bleibt belastbar und in seiner Funktion eindeutig.",
                },
            }
        )
        content_by_ref: dict[str, str] = {}
        region_facts: dict[str, dict] = {}
        for region in family.regions:
            capacity = next(item for item in region.capacities if item.language == "de")
            count = 2 if {"process", "comparison"} & set(region.allowed_element_kinds) else 1
            refs = []
            for item_index in range(1, count + 1):
                ref = f"content.{face_id}.{region.region_id}.{item_index:02d}"
                refs.append(ref)
                content_by_ref[ref] = (
                    "Eine klare Leitidee"
                    if item_index == 1
                    else "Der zweite Baustein erklärt die überprüfbare Wirkung."
                )
            region_facts[region.region_id] = {
                "content_refs": refs,
                "font_size_pt": max(capacity.min_font_pt, min(capacity.max_font_pt, 12)),
                "image_aspect_ratio": 1.0 if "image" in region.allowed_element_kinds else None,
                "stat_count": len(claim_ids),
                "list_item_count": count,
            }
        facts.append(
            {
                "face_id": face_id,
                "language": "de",
                "content_by_ref": content_by_ref,
                "regions": region_facts,
                "asset_ids": selected_asset_ids,
            }
        )

    return {
        "payload": {
            "meta": {
                "client_slug": fixture_id,
                "report_id": fixture_id,
                "lang": "de",
                "page_format": "A4",
                "page_count_target": 20,
            },
            "pages": pages,
        },
        "images": {},
        "brand_tokens": {"founder_full_name": "Synthetic Founder"},
        "sources": [],
        "claims": claims,
        "source_appendix_v3": {
            "schema_version": "1.0",
            "entries": [],
        },
        "assets": assets,
        "editorial_brief_v3": {
            "product_profile_id": "dmc_house_20_face",
            "faces": faces,
            # Richard's own format model, measured from four of the six reference
            # reports: an A4 cover, NINE A3 double-page spreads carrying two
            # faces each, and an A4 back cover. 11 physical objects, 20 faces.
            "formats": ["a4"] + ["a3"] * 9 + ["a4"],
            "audience": "German B2B founder",
            "central_thesis": "A grounded calibration thesis",
            "promise": "A grounded calibration promise",
            "tone_profile": "Richard house",
        },
        "composition_facts_v3": facts,
    }


def _design_features_for_profile(profile: dict) -> dict:
    """Translate a calibration profile into typed planner design features.

    The mapping is deterministic from the profile's own declared character;
    it is what stops materially different clients collapsing into identical
    composition plans.
    """
    import re

    tone_tokens = tuple(
        word
        for word in re.split(r"[^a-zäöüß]+", profile["tone"].lower())
        if word and word != "german"
    ) + tuple(word for word in profile["visual_brand"].lower().split("-") if word)
    tone_lower = profile["tone"].lower()
    if "assertive" in tone_lower or "bold" in tone_lower:
        energy = "expressive"
    elif "measured" in tone_lower or "quiet" in tone_lower:
        energy = "restrained"
    else:
        energy = "balanced"
    availability = profile["asset_availability"]
    if "complete" in availability:
        imagery = "rich"
    elif "documentary" in availability:
        imagery = "sparse"
    else:
        imagery = "moderate"
    density = profile["evidence_density"]
    if density.startswith("dense"):
        charts = "high"
    elif density.startswith("moderate"):
        charts = "moderate"
    else:
        charts = "low"
    return {
        "tone_tokens": tone_tokens,
        "brand_energy": energy,
        "imagery_density": imagery,
        "chart_opportunity": charts,
    }


def envelope_for_profile(profile: dict, asset_dir: Path) -> dict:
    if profile["recipe"] == "apex-dense-report":
        return apex_dense_envelope(profile, asset_dir)
    density = profile["evidence_density"]
    if density.startswith("dense"):
        proof_claim_count = 3
    elif density.startswith("moderate"):
        proof_claim_count = 2
    else:
        proof_claim_count = 1
    envelope = valid_house_envelope(
        asset_dir,
        fixture_id=profile["fixture_id"],
        proof_claim_count=proof_claim_count,
    )
    envelope["brand_tokens"].update(
        {
            "calibration_visual_brand": profile["visual_brand"],
            "calibration_tone": profile["tone"],
        }
    )
    # The client profile id reaches the render bundle (G1): without it every
    # client renders on default axes and the per-client treatment rows in
    # richard-grammar-v2 never fire. Each calibration profile declares a real
    # brand-profile id in its fixture JSON.
    envelope["brand_profile_id"] = profile.get("profile_id")
    envelope["editorial_brief_v3"]["design_features"] = _design_features_for_profile(
        profile
    )
    # Evidence density is editorial structure, not decoration: it sets the
    # density band the planner fits copy against, face by face.
    density = profile["evidence_density"]
    if density.startswith("dense"):
        band = "dense"
    elif density.startswith("moderate"):
        band = "moderate"
    else:
        band = "light"
    for face in envelope["editorial_brief_v3"]["faces"]:
        face["density_band"] = band
    recipe = profile["recipe"]
    if recipe == "valid-house-report":
        return envelope
    if recipe == "christoph-known-failures":
        mutated = copy.deepcopy(envelope)
        mutated["editorial_brief_v3"]["faces"] = mutated["editorial_brief_v3"]["faces"][:17]
        # One retained A3 fragment accounts for two faces, so sixteen
        # fragments allocate the intended seventeen-face failure recipe.
        mutated["editorial_brief_v3"]["formats"] = mutated["editorial_brief_v3"]["formats"][:16]
        theory_faces = [face for face in mutated["editorial_brief_v3"]["faces"] if face["role"] == "theory"][:2]
        for case_number, face in enumerate(theory_faces, start=4):
            face["role"] = "case_study"
            face["case_id"] = f"case.{case_number}"
        mutated["payload"]["pages"][0]["data"]["body"] += " 83% schneller."
        mutated["assets"] = [asset for asset in mutated["assets"] if asset["semantic_class"] != "identity"]
        return mutated
    if recipe == "missing-proof-and-source":
        mutated = copy.deepcopy(envelope)
        mutated["assets"] = [
            asset for asset in mutated["assets"] if asset["semantic_class"] not in {"identity", "proof"}
        ]
        return mutated
    raise ValueError(f"unknown calibration recipe: {recipe}")


# ---------------------------------------------------------------------------
# apex-dense-report: a fully authored 20-face envelope at Apex reference
# density (240 to 340 words per face), German copy in Richard's house voice.
#
# Calibration notes (2026-08-06 density work):
# - No registry capacity was raised for this recipe. Every region's authored
#   copy fits the dmc-v1 1.2.0 envelopes (max_words and the physical height
#   budget at 1.2 leading); the density gap in the earlier candidate came
#   from stub copy volume, not from registry capacity.
# - Every figure printed on a face is carried by a claim on that face; every
#   span-grounded claim points at a verbatim excerpt of the single synthetic
#   operations source below. Delta claims are computed (operands declared).
# - The identity portraits on case faces carry the measured Apex brand blue
#   (#4080a0) so the case proof band holds the declared brand accent.
# ---------------------------------------------------------------------------

APEX_DENSE_ACCENT = "#4080a0"
_APEX_BLUE = (64, 128, 160)
_APEX_DARK = (15, 15, 31)

_APEX_SOURCE_ID = "source.apex-dense.betriebsauswertung"
_APEX_SOURCE_HEADER = (
    "Betriebsauswertung und Interviewprotokoll der Feldmann Automation GmbH. "
    "Erhoben aus den eigenen Kundenprojekten und den Ablaufmessungen vor und "
    "nach dem jeweiligen Umbau."
)

# claim_id -> (normalized_value, unit, source sentence containing the value
# verbatim). Computed claims carry (formula, operands) instead of a sentence.
_APEX_SPAN_CLAIMS: dict[str, tuple[str, str | None, str]] = {
    "claim.cover.hours": (
        "68 Stunden",
        None,
        "Über alle vermessenen Betriebe gingen im Durchschnitt 68 Stunden pro "
        "Woche in vorbereitende und verwaltende Arbeit ohne Kundenkontakt "
        "verloren.",
    ),
    "claim.cover.cost": (
        "310.000 €",
        "EUR",
        "Auf ein Jahr gerechnet entsprach diese gebundene Arbeitszeit im "
        "Durchschnitt 310.000 € an Personalkosten.",
    ),
    "claim.statusquo.minutes": (
        "41 Minuten",
        None,
        "Die Beantwortung einer einfachen Kundenanfrage dauerte in der "
        "Ablaufmessung im Durchschnitt 41 Minuten.",
    ),
    "claim.statusquo.systems": (
        "5 Systeme",
        None,
        "Die dafür notwendigen Informationen lagen in 5 Systeme umfassenden "
        "Insellösungen ohne direkte Verbindung.",
    ),
    "claim.case1.before": (
        "42 Stunden",
        None,
        "Bei Reber Anlagenbau ergab die Messung zum Projektstart 42 Stunden "
        "Angebotsvorbereitung pro Woche.",
    ),
    "claim.case1.after": (
        "6 Stunden",
        None,
        "Nach dem Umbau der Angebotsstrecke benötigte Reber Anlagenbau für "
        "denselben Umfang 6 Stunden pro Woche.",
    ),
    "claim.case1.orders": (
        "+31 %",
        "percent",
        "Der Auftragseingang von Reber Anlagenbau lag nach dem Umbau bei "
        "+31 % gegenüber dem Vorjahreszeitraum.",
    ),
    "claim.case2.y2023": (
        "310 Angebote",
        None,
        "Im Jahr 2023 erstellte Kolbe Technischer Handel 310 Angebote.",
    ),
    "claim.case2.y2024": (
        "540 Angebote",
        None,
        "Im Jahr 2024 erstellte Kolbe Technischer Handel 540 Angebote.",
    ),
    "claim.case2.y2025": (
        "780 Angebote",
        None,
        "Im Jahr 2025 erstellte Kolbe Technischer Handel 780 Angebote.",
    ),
    "claim.case2.revenue": (
        "2,1 Mio. €",
        "EUR",
        "Der zusätzliche Auftragswert aus schneller beantworteten Anfragen "
        "summierte sich bei Kolbe auf 2,1 Mio. €.",
    ),
    "claim.case3.before": (
        "14 Tage",
        None,
        "Bei Brandt Elektrotechnik vergingen zwischen Aufmaß und "
        "freigegebenem Nachtrag zum Projektstart 14 Tage.",
    ),
    "claim.case3.after": (
        "2 Tage",
        None,
        "Nach dem Umbau der Nachtragsstrecke lagen zwischen Aufmaß und "
        "Freigabe bei Brandt Elektrotechnik 2 Tage.",
    ),
    "claim.case3.projects": (
        "44 Projekte",
        None,
        "Brandt Elektrotechnik betreute nach dem Umbau 44 Projekte parallel "
        "mit unveränderter Projektleitung.",
    ),
    "claim.theory.deskshare": (
        "63 %",
        "percent",
        "63 % der bezahlten Arbeitszeit in den vermessenen "
        "Verwaltungsstrecken vergingen ohne jeden Kundenkontakt.",
    ),
    "claim.theory.search": (
        "4,2 Stunden",
        None,
        "Das Suchen und Übertragen von Informationen band im Durchschnitt "
        "4,2 Stunden pro Mitarbeiter und Woche.",
    ),
    "claim.theory.onboarding": (
        "12 Wochen",
        None,
        "Neue Mitarbeiter benötigten in Betrieben mit undokumentierten "
        "Abläufen im Durchschnitt 12 Wochen bis zur selbstständigen Arbeit.",
    ),
    "claim.theory.handovers": (
        "7 Übergaben",
        None,
        "Ein durchschnittlicher Auftrag durchlief von der Anfrage bis zur "
        "Rechnung 7 Übergaben.",
    ),
    "claim.theory.rework": (
        "30 %",
        "percent",
        "30 % der Aufträge durchliefen mindestens eine Korrekturschleife "
        "wegen fehlerhaft übertragener Daten.",
    ),
    "claim.theory.interfaces": (
        "9 Schnittstellen",
        None,
        "Die vermessenen Betriebe übertrugen Auftragsdaten über "
        "9 Schnittstellen zwischen getrennten Programmen.",
    ),
    "claim.theory.patterns.share": (
        "80 %",
        "percent",
        "80 % der eingehenden Anfragen folgten wiederkehrenden Mustern.",
    ),
    "claim.theory.patterns.count": (
        "20 Muster",
        None,
        "Über alle Projektbetriebe genügten 20 Muster, um diesen "
        "wiederkehrenden Kern abzubilden.",
    ),
    "claim.theory.payback": (
        "3 Monate",
        None,
        "Bei richtiger Streckenwahl trug der Umbau seine Kosten nach "
        "3 Monate langem Betrieb selbst.",
    ),
    "claim.theory.metrics": (
        "5 Kennzahlen",
        None,
        "Zur Steuerung jeder Strecke genügten 5 Kennzahlen von der "
        "Durchlaufzeit bis zur Fehlerquote.",
    ),
    "claim.method.live": (
        "14 Tagen",
        None,
        "Die erste umgebaute Strecke lief in den Projekten nach 14 Tagen im "
        "Tagesbetrieb.",
    ),
    "claim.method.measurable": (
        "90 Tagen",
        None,
        "Nach 90 Tagen war die erste Ausbaustufe an den Startkennzahlen "
        "messbar.",
    ),
    "claim.trust.clients": (
        "38 Betriebe",
        None,
        "Seit 2019 hat Feldmann Automation 38 Betriebe beim Umbau ihrer "
        "Strecken begleitet.",
    ),
    "claim.trust.years": (
        "12 Jahre",
        None,
        "Die Methodik stützt sich auf 12 Jahre eigene Betriebs- und "
        "Projekterfahrung.",
    ),
    "claim.trust.rating": (
        "4,9 von 5",
        None,
        "In den dokumentierten Projektbewertungen erreichte die "
        "Zusammenarbeit 4,9 von 5 Punkten.",
    ),
    "claim.trust.retention": (
        "92 %",
        "percent",
        "92 % der umgebauten Strecken liefen 12 Monate nach der Übergabe "
        "unverändert im Tagesbetrieb.",
    ),
    "claim.collab.call": (
        "45 Minuten",
        None,
        "Das Erstgespräch dauert 45 Minuten und dient der beidseitigen "
        "Prüfung.",
    ),
}

_APEX_QUOTE_CLAIMS: dict[str, str] = {
    "claim.review.mueller": (
        "Die Umstellung lief neben dem Tagesgeschäft, ohne dass eine "
        "Strecke stillstand."
    ),
    "claim.review.kolbe": (
        "Wir sehen jede Woche in den Auswertungen, dass die zweite "
        "Schicht kleiner wird."
    ),
}

_APEX_COMPUTED_CLAIMS: dict[str, tuple[str, str, tuple[str, str]]] = {
    "claim.case1.delta": (
        "36 Stunden weniger",
        "42 Stunden minus 6 Stunden = 36 Stunden pro Woche",
        ("claim.case1.before", "claim.case1.after"),
    ),
    "claim.case3.delta": (
        "12 Tage schneller",
        "14 Tage minus 2 Tage = 12 Tage",
        ("claim.case3.before", "claim.case3.after"),
    ),
}

# Entity and time scope for the case 2 series (renders as a time series).
_APEX_SERIES_SCOPES: dict[str, tuple[str, str]] = {
    "claim.case2.y2023": ("Angebote pro Jahr, Kolbe Technischer Handel", "2023"),
    "claim.case2.y2024": ("Angebote pro Jahr, Kolbe Technischer Handel", "2024"),
    "claim.case2.y2025": ("Angebote pro Jahr, Kolbe Technischer Handel", "2025"),
}

_APEX_CLAIMS_BY_FACE: dict[int, tuple[str, ...]] = {
    1: ("claim.cover.hours", "claim.cover.cost"),
    4: ("claim.statusquo.minutes", "claim.statusquo.systems"),
    6: (
        "claim.case1.before",
        "claim.case1.after",
        "claim.case1.delta",
        "claim.case1.orders",
    ),
    7: ("claim.theory.deskshare", "claim.theory.search"),
    8: ("claim.theory.onboarding", "claim.theory.handovers"),
    9: ("claim.theory.rework", "claim.theory.interfaces"),
    10: (
        "claim.case2.y2023",
        "claim.case2.y2024",
        "claim.case2.y2025",
        "claim.case2.revenue",
    ),
    11: ("claim.theory.patterns.share", "claim.theory.patterns.count"),
    12: (
        "claim.case3.before",
        "claim.case3.after",
        "claim.case3.delta",
        "claim.case3.projects",
    ),
    13: ("claim.theory.payback", "claim.theory.metrics"),
    14: ("claim.method.live", "claim.method.measurable"),
    15: (
        "claim.trust.clients",
        "claim.trust.years",
        "claim.trust.rating",
        "claim.trust.retention",
        "claim.review.mueller",
        "claim.review.kolbe",
    ),
    16: ("claim.cover.hours", "claim.cover.cost"),
    18: ("claim.collab.call", "claim.method.measurable"),
    19: ("claim.cover.hours",),
}

# Font sizes declared to the capacity estimator, per (family, region).
_APEX_FONT_PT: dict[tuple[str, str], float] = {
    ("editorial_lead", "headline"): 28,
    ("editorial_lead", "narrative"): 9.5,
    ("editorial_lead", "anchor"): 10,
    ("false_belief_stack", "opening"): 12,
    ("false_belief_stack", "beliefs"): 8.8,
    ("case_narrative", "case_story"): 9.2,
    ("case_narrative", "evidence_rail"): 9,
    ("theory_interpretation", "principle"): 9.2,
    ("theory_interpretation", "mechanism"): 9,
    ("mechanism_spread", "method_frame"): 10,
    ("mechanism_spread", "steps"): 8.8,
    ("summary_synthesis", "synthesis"): 9.2,
    ("summary_synthesis", "payoff"): 10,
    ("objection_response", "objection_frame"): 12,
    ("objection_response", "responses"): 8.8,
    ("collaboration_pathway", "commitment"): 9.5,
    ("collaboration_pathway", "pathway"): 8.8,
    ("evidence_wall", "trust_header"): 20,
    ("evidence_wall", "proof_wall"): 9,
    ("closing_cta", "closing_statement"): 14,
    ("closing_cta", "identity_close"): 10,
}

# face index -> semantic asset class (painted blue for case identity proof).
_APEX_ASSETS: dict[int, str] = {
    2: "context",
    3: "context",
    6: "identity",
    10: "identity",
    12: "identity",
    15: "proof",
    19: "context",
}


def _apex_dense_copy() -> dict[int, dict[str, tuple[str, ...]]]:
    """Region copy per face. Every string is printed German in house voice."""
    return {
        1: {
            "headline": (
                "Die zweite Schicht kostet dich 68 Stunden pro Woche.",
            ),
            # Cover = declaration, not essay: Richard's covers measure
            # 127-170 words (atlas role band). The measurement provenance
            # moved to the status-quo close (face 19).
            "narrative": (
                "Dein Betrieb liefert. Die Aufträge kommen herein, die "
                "Kunden bleiben, das Team ist ausgelastet. Und trotzdem "
                "endet kein Tag pünktlich. Nach dem letzten Kundentermin "
                "beginnt der zweite Teil deiner Arbeit. Diese Schicht steht "
                "in keinem Kalender und auf keiner Rechnung. Wir haben ihr "
                "einen Namen gegeben. Die zweite Schicht. Sie ist unsichtbar, "
                "und sie kostet jeden Tag etwas.",
                "68 Stunden pro Woche, aufs Jahr gerechnet 310.000 € an "
                "gebundener Arbeitszeit. Gemessen in unseren eigenen "
                "Projektbetrieben, nicht geschätzt.",
                "Dieser Report zeigt, wo diese Stunden entstehen, warum sie "
                "in gut geführten Betrieben am größten sind und wie "
                "Unternehmen wie deines sie zurückgeholt haben. Lies zuerst "
                "die Fallstudien, wenn du wenig Zeit hast. Am Ende weißt "
                "du, was es kostet, die zweite Schicht zu behalten.",
            ),
            "anchor": (
                "Gemessene Verwaltungszeit und ihre Jahreskosten im "
                "Durchschnitt unserer Projektbetriebe",
            ),
        },
        2: {
            "headline": (
                "Der Ausbau deiner Verwaltung war richtig. Genau dort liegt "
                "jetzt das Risiko.",
            ),
            "narrative": (
                "Du hast in den vergangenen Jahren alles richtig gemacht. "
                "Mehr Aufträge angenommen, Personal eingestellt, Abläufe "
                "dokumentiert, Verantwortung verteilt. Dein Betrieb ist "
                "gewachsen, weil du an den entscheidenden Stellen zugepackt "
                "hast. Niemand muss dir erklären, wie dein Geschäft "
                "funktioniert. Genau deshalb lohnt sich der Blick auf die "
                "Stelle, die beim Wachsen niemand geplant hat.",
                "Jede neue Kollegin und jeder neue Auftrag hat eine kleine "
                "Menge Verwaltung mitgebracht. Eine zusätzliche Liste, eine "
                "weitere Abstimmung, ein Zwischenschritt zur Sicherheit. "
                "Einzeln war jeder dieser Schritte vernünftig. Zusammen "
                "bilden sie heute ein Geflecht, das mit jedem Auftrag "
                "dichter wird. Es wächst schneller als dein Umsatz, weil "
                "jede Ausnahme eine neue Regel erzeugt. Dieses Wachstum hat "
                "eine eigene Logik. Wer gut arbeitet, bekommt mehr "
                "Aufträge. Mehr Aufträge erzeugen mehr Übergaben. Mehr "
                "Übergaben verlangen mehr Absicherung. So bestraft sich "
                "gute Arbeit selbst, solange die Strecken dazwischen "
                "Handarbeit bleiben.",
                "Dieser Report nimmt genau diese Strecken in den Blick. "
                "Er zeigt an drei dokumentierten Projekten, wie aus "
                "gewachsener Verwaltung wieder ein Betrieb wird, der seine "
                "Zeit am Kunden verbringt. Er rechnet vor, was die zweite "
                "Schicht heute kostet, und er beschreibt den Weg hinaus so "
                "konkret, dass du ihn Schritt für Schritt an deinem "
                "eigenen Betrieb und deinen eigenen Zahlen prüfen "
                "kannst.",
                "Von außen ist davon nichts zu sehen. Die Kunden werden "
                "bedient, die Termine werden gehalten, die Zahlen stimmen. "
                "Der Preis wird an anderer Stelle bezahlt. In Abenden, die "
                "im Büro enden. In Führungskräften, die zu Sachbearbeitern "
                "werden. In Entscheidungen, die warten, weil die Person mit "
                "dem Überblick keine freie Stunde hat.",
                "Dieser Report nimmt sich diese unsichtbare Struktur vor. "
                "Er zeigt, welche falschen Annahmen sie am Leben halten, an "
                "welchen Stellen sie reißt und in welcher Reihenfolge sich "
                "der Umbau lohnt. Du bekommst keine Werkzeugliste. Du "
                "bekommst eine Landkarte, gezeichnet aus echten Betrieben, "
                "mit den Zahlen, die deren Inhaber selbst gemessen haben.",
                "Am Ende steht keine große Umstellung über Nacht. Der Weg "
                "führt über wenige Strecken, die nacheinander umgebaut "
                "werden, während das Tagesgeschäft weiterläuft. Was das "
                "konkret bedeutet, zeigen die Fallstudien in der Mitte "
                "dieses Reports. Ihre Ausgangslage wird dir bekannt "
                "vorkommen.",
            ),
            "anchor": (
                "Blick in die Werkhalle eines begleiteten Projektbetriebs",
            ),
        },
        3: {
            "headline": (
                "Wir bauen Strecken um. Den Betrieb führst weiterhin du.",
            ),
            "narrative": (
                "Feldmann Automation ist eine Agentur für "
                "Ablaufautomatisierung im Mittelstand. Gegründet von Jonas "
                "Feldmann, der vorher selbst einen Fertigungsbetrieb "
                "geführt hat. Aus dieser Zeit stammt die Grundüberzeugung "
                "hinter unserer Arbeit. Ein Ablauf, den niemand versteht, "
                "wird auch automatisiert kein guter Ablauf. Deshalb beginnt "
                "bei uns jedes Projekt mit dem Vermessen, nie mit der "
                "Technik.",
                "Wir arbeiten ausschließlich mit Betrieben, die bereits "
                "funktionieren. Maschinenbauer, technische Händler, "
                "Elektrotechniker, Dienstleister mit erklärungsbedürftigem "
                "Angebot. Unternehmen mit echten Kunden und vollen "
                "Auftragsbüchern, deren Verwaltung mit dem Wachstum kaum "
                "Schritt hält. Für Gründungen ohne laufendes Geschäft sind "
                "wir die falsche Adresse. Das sagen wir im ersten Gespräch "
                "und ersparen beiden Seiten den Umweg.",
                "Unsere Arbeitsweise hat einen Namen. Der Taktplan. Er legt "
                "fest, in welcher Reihenfolge die Strecken eines Betriebs "
                "umgebaut werden, damit jede Stufe die nächste finanziert. "
                "Kein Projekt beginnt mit einem Systemwechsel. Jedes "
                "beginnt mit der Strecke, die am meisten Zeit bindet und "
                "am wenigsten Widerstand erzeugt.",
                "Was uns von Softwarehäusern unterscheidet, ist der "
                "Auftrag. Wir verkaufen keine Lizenzen und keine Tagessätze "
                "für Entwicklung um ihrer selbst willen. Wir werden daran "
                "gemessen, wie viele Stunden pro Woche dein Betrieb "
                "zurückbekommt und ob deine Mitarbeiter die neuen Abläufe "
                "nach der Übergabe selbst weiterführen.",
                "Dieser Report ist unser Arbeitsnachweis. Jede Zahl darin "
                "stammt aus einem begleiteten Projekt oder aus unserer "
                "eigenen Auswertung. Nichts davon ist eine Branchenschätzung "
                "aus fremder Quelle. Wo wir etwas nicht gemessen haben, "
                "schreiben wir es nicht.",
                "Der Rest dieses Reports zeigt die Arbeitsweise an "
                "konkreten Projekten. Lies ihn mit deinem eigenen Betrieb "
                "vor Augen. Die Namen und Branchen unterscheiden sich, "
                "die Strecken dahinter gleichen sich auf eine Weise, die "
                "dich überraschen wird. Was du hier liest, stammt aus "
                "Messungen und Projektunterlagen, nicht aus Werbetexten. "
                "Wo eine Zahl steht, steht dahinter ein dokumentierter "
                "Vorgang aus einem echten Betrieb.",
            ),
            "anchor": (
                "Jonas Feldmann im Gespräch mit einem Projektbetrieb",
            ),
        },
        4: {
            "headline": (
                "Die stillen Kosten stehen in keiner Auswertung. Gemessen "
                "haben wir sie trotzdem.",
            ),
            "narrative": (
                "So sieht der Vormittag in einem gewachsenen Betrieb aus. "
                "Eine Anfrage kommt herein. Der Vertrieb sucht die letzte "
                "Kalkulation eines vergleichbaren Auftrags, findet sie im "
                "Postfach eines Kollegen und überträgt die Positionen in "
                "eine neue Tabelle. Zwischendurch Rückfragen an die "
                "Fertigung, ein Anruf beim Lieferanten, eine Notiz im "
                "eigenen System. Bis das Angebot steht, ist der halbe "
                "Vormittag vorbei.",
                "Wir haben diesen Ablauf in unseren Projektbetrieben mit "
                "der Stoppuhr vermessen. Im Durchschnitt vergehen 41 "
                "Minuten, bis eine einfache Anfrage beantwortet ist. Nicht "
                "wegen fehlender Erfahrung. Die Information liegt verteilt "
                "in 5 Systeme umfassenden Insellösungen, und der Mensch ist "
                "die Brücke dazwischen. Jede dieser Brücken kostet Zeit, "
                "und jede ist eine eigene Fehlerquelle.",
                "Der teurere Teil ist unsichtbar. Während dein bester "
                "Mitarbeiter Daten überträgt, verkauft er nichts, plant er "
                "nichts und entwickelt er niemanden. Die Anfragen, die in "
                "dieser Zeit liegen bleiben, tauchen in keiner Auswertung "
                "auf. Ein Interessent, der zu spät eine Antwort erhält, "
                "beschwert sich selten. Er bestellt woanders und bleibt "
                "still.",
                "Mit jedem neuen Mitarbeiter wächst das Geflecht weiter. "
                "Der neue Kollege lernt die Abkürzungen der alten, erfindet "
                "eigene dazu und gibt beide an den nächsten weiter. Nach "
                "wenigen Jahren weiß niemand mehr, welche Schritte ein "
                "Auftrag wirklich braucht und welche nur aus Gewohnheit "
                "überleben. Der eigentliche Kostentreiber ist die Übergabe "
                "zwischen den Systemen.",
                "Nichtstun ist an dieser Stelle eine Entscheidung. Das "
                "Geflecht baut sich niemals von selbst zurück. Es wächst "
                "mit jedem Auftrag, den dein Betrieb gewinnt, und es wächst "
                "am schnellsten in den Betrieben, die am besten laufen. "
                "Du erkennst es am Abend daran, wer noch im Büro sitzt. "
                "Nicht die Auszubildenden, sondern die Leute, die dein "
                "Geschäft am besten kennen. Genau deren Stunden verbrennt "
                "die zweite Schicht zuerst.",
                "Und du erkennst es an den Ausnahmen. Für jeden Sonderfall "
                "gibt es inzwischen eine eigene Absprache, für jede "
                "Absprache eine Liste, für jede Liste einen Verantwortlichen. "
                "Niemand hat dieses Geflecht beschlossen. Es ist die Summe "
                "vieler vernünftiger Einzelentscheidungen, und es wird erst "
                "sichtbar, wenn man die Strecke eines einzigen Auftrags "
                "einmal vollständig nachzeichnet.",
            ),
            "anchor": (
                "Aus der Ablaufmessung in unseren Projektbetrieben",
            ),
        },
        5: {
            # Opening stays heading-only: body copy here pushes the dark
            # belief card below the measured top band and collapses the
            # family's vertical hierarchy under its pixel-policy minimum.
            "opening": (
                "Diese Sätze halten die zweite Schicht am Leben, und jeder "
                "klingt zunächst vernünftig.",
            ),
            "beliefs": (
                "„Meine Abläufe sind zu speziell dafür.“",
                "Das Gegenteil zeigt sich beim Vermessen. Der Kern fast "
                "jeder Strecke folgt wenigen wiederkehrenden Mustern. Die "
                "berühmten Sonderfälle betreffen den kleineren Teil der "
                "Vorgänge und bleiben bei deinen erfahrenen Mitarbeitern. "
                "Automatisiert wird der wiederkehrende Kern. Genau dort "
                "entsteht die verlorene Zeit.",
                "„Dafür haben wir gerade keine Zeit.“ Der Satz beschreibt "
                "das Problem, das er verhindert. Die Zeit fehlt, weil die "
                "zweite Schicht sie verbraucht. Der Umbau beginnt deshalb "
                "mit einer einzigen Strecke und läuft neben dem "
                "Tagesgeschäft. Die erste zurückgewonnene Stunde finanziert "
                "die zweite.",
                "„Meine Mitarbeiter machen da nicht mit.“ Verständlich, "
                "denn sie haben Umstellungen erlebt, die ihre Arbeit "
                "schwerer gemacht haben. Deshalb beginnt jeder Umbau bei "
                "der Strecke, die dein Team selbst als lästig benennt. Der "
                "Unterschied zeigt sich schnell im Alltag. Wer "
                "das Abtippen los ist, verteidigt den neuen Weg von allein. "
                "In den Projekten kam der Vorschlag für die zweite Strecke "
                "fast immer aus dem Team, nicht aus der Leitung.",
                "„Software haben wir schon genug.“ Stimmt. Genau das ist "
                "der Befund. Die Programme sind da, sie sprechen nur "
                "wenig miteinander, und der Mensch trägt die Daten von "
                "einem ins andere. Der Umbau ergänzt selten ein neues "
                "System. Er verbindet die vorhandenen, bis die Übergaben "
                "ohne Abtippen laufen. Zu jeder umgebauten Strecke "
                "gehört deshalb eine Übergabe an dein Team, eine "
                "dokumentierte Beschreibung in deiner Ablage und ein "
                "benannter Ansprechpartner im Betrieb.",
                "„Am Ende kontrolliert mich das System.“ Diese Sorge nennt "
                "fast jeder Inhaber, meistens leise. Die Antwort steht in "
                "den Verträgen unserer Projekte. Ausgewertet werden "
                "Strecken und Durchlaufzeiten, keine Personen. Du siehst, "
                "wo ein Vorgang wartet und wie lange eine Übergabe dauert. "
                "Wer ihn bearbeitet hat, bleibt Sache deiner Führung.",

                "„Das rechnet sich für einen Betrieb meiner Größe nie.“ "
                "Die Rechnung dreht sich beim Nachmessen um. Je kleiner das "
                "Team, desto teurer ist jede Stunde, die in Übergaben "
                "fließt, denn sie fehlt direkt am Kunden. Große Konzerne "
                "leisten sich Reibungsverluste. Ein Betrieb wie deiner "
                "bezahlt sie aus dem Ergebnis, Monat für Monat und ohne "
                "eine Rechnung, auf der sie stehen.",
                "Bleibt der häufigste Satz von allen. „Bisher ging es doch "
                "auch so.“ Das stimmt, und es bleibt wahr, bis ein "
                "Schlüsselmitarbeiter kündigt, ein Großauftrag die "
                "Verwaltung überrollt oder ein Wettbewerber schneller "
                "antwortet. Die zweite Schicht ist geduldig. Sie wird nur "
                "teurer, nie billiger. Jeder dieser Sätze schützt einen "
                "Zustand, den niemand bestellt hat. Die folgenden Seiten "
                "prüfen jeden einzelnen davon an dokumentierten Projekten "
                "aus Betrieben deiner Größe, nicht an Meinungen.",
            ),
        },
        6: {
            "case_story": (
                "Reber Anlagenbau. Der Angebotsstau war zuerst unsichtbar, "
                "dann teuer.",
                "Martin Reber führt einen Anlagenbaubetrieb mit einem "
                "eingespielten Team und einem vollen Auftragsbuch. Sein "
                "Engpass war zu keinem Zeitpunkt die Fertigung. Es war der "
                "Weg von der Anfrage zum Angebot. Jede Kalkulation lief "
                "über seinen Schreibtisch, weil nur er alle Preise, "
                "Lieferzeiten und Sonderfälle im Kopf hatte. Kunden "
                "warteten auf Antworten, während er abends Tabellen "
                "füllte.",
                "Die Messung zum Projektstart ergab 42 Stunden pro Woche "
                "für die Angebotsvorbereitung im gesamten Betrieb, verteilt "
                "auf den Inhaber und seine Projektleiter. Der größte Anteil "
                "entfiel auf das Zusammensuchen von Preisen aus alten "
                "Projekten und auf Rückfragen, deren Antworten längst "
                "dokumentiert waren, nur eben an verschiedenen Orten.",
                "Der Umbau folgte dem Taktplan. Zuerst wurde die "
                "Preisfindung aus alten Projekten in eine gepflegte "
                "Stammliste überführt. Danach wurde die Anfrage selbst "
                "strukturiert, sodass wiederkehrende Positionen automatisch "
                "vorbelegt werden. Erst am Ende kam die Angebotserstellung "
                "an die Reihe. Das Team hat jede Stufe im laufenden Betrieb "
                "übernommen, ohne einen einzigen Systemwechsel.",
                "Heute stehen für denselben Umfang 6 Stunden pro Woche im "
                "Plan, und der Engpass am Schreibtisch des Inhabers ist "
                "verschwunden. Martin Reber besucht wieder Bestandskunden, "
                "und der Auftragseingang lag nach dem Umbau bei +31 % "
                "gegenüber dem Vorjahreszeitraum. Sein Fazit im "
                "Abschlussgespräch war trocken. Das hätte er Jahre früher "
                "machen sollen.",
                "Übertragbar ist an diesem Projekt weniger die Branche als "
                "das Muster. Ein Engpass, der am Wissen einer einzelnen "
                "Person hängt, verschwindet nie durch mehr Personal. Er "
                "verschwindet, wenn das Wissen in die Strecke wandert und "
                "dort für alle nutzbar wird.",
            ),
            "evidence_rail": (
                "Kennzahlen aus dem Projekt Reber Anlagenbau",
            ),
        },
        7: {
            "principle": (
                "Warum gewachsene Betriebe Zeit verlieren, während sie "
                "wachsen.",
                "Das Prinzip hinter den Fallstudien dieses Reports ist "
                "immer dasselbe, und es hat mit Technik wenig zu tun. In "
                "einem gewachsenen Betrieb sammelt sich Wissen in Personen. "
                "Preise, Sonderfälle, Kundengeschichte, ungeschriebene "
                "Regeln. Solange der Betrieb klein ist, ist das ein "
                "Vorteil, denn die Wege sind kurz und die Abstimmung ist "
                "schnell. Ab einer bestimmten Größe kippt derselbe Vorteil "
                "ins Gegenteil.",
                "Unsere Auswertung über die begleiteten Betriebe zeigt das "
                "Ausmaß. 63 % der bezahlten Arbeitszeit in den vermessenen "
                "Verwaltungsstrecken vergehen ohne jeden Kundenkontakt. "
                "Der größte Einzelposten darin ist das Suchen und "
                "Übertragen von Informationen, im Durchschnitt 4,2 Stunden "
                "pro Mitarbeiter und Woche. Beides sind Tätigkeiten, die "
                "niemand bestellt hat und die auf keiner Rechnung stehen.",
                "Entscheidend ist die Richtung dieser Zahlen. Sie sinken "
                "nie von selbst. Jeder zusätzliche Auftrag erhöht die Zahl "
                "der Übergaben, und jede Übergabe erzeugt Suchzeit. Ein "
                "Betrieb, der wächst, ohne seine Strecken umzubauen, "
                "bezahlt sein Wachstum mit immer teurerer Verwaltungszeit. "
                "Die Fallstudie nebenan zeigt, wie der Ausstieg aus diesem "
                "Muster gelingt.",
                "Für die Praxis folgt daraus eine einfache Prüffrage. Wie "
                "viel Zeit vergeht in deinem Betrieb zwischen einer "
                "Anfrage und der ersten belastbaren Antwort. Wer diese "
                "Zahl kennt, kennt den Zustand seiner Strecken. Wer sie "
                "schätzen muss, hat die Antwort damit ebenfalls gegeben.",
            ),
            "mechanism": (
                "Wo die bezahlte Woche tatsächlich bleibt",
                "Suchen und Übertragen von Informationen bindet den "
                "größten Einzelanteil.",
                "Abstimmung über Zuruf erzeugt täglich dieselben "
                "Rückfragen erneut.",
                "Doppelte Datenpflege hält Listen synchron, die es nur "
                "aus Gewohnheit gibt.",
                "Kontrollschleifen sichern Fehler ab, die aus den "
                "Übergaben stammen.",
            ),
        },
        8: {
            "principle": (
                "Einarbeitung dauert so lange, wie die Strecke unklar ist.",
                "Der zweite Befund aus unseren Projekten betrifft neue "
                "Mitarbeiter. In Betrieben mit undokumentierten Abläufen "
                "vergingen im Durchschnitt 12 Wochen, bis eine neue Kraft "
                "ohne ständige Rückfragen arbeitete. Der Grund liegt selten "
                "in der Aufgabe selbst. Der Weg zu jeder Information führt "
                "über Kollegen, und jeder Kollege kennt eine andere "
                "Abkürzung. Einarbeitung wird so zur Ortsbegehung durch "
                "gewachsene Strukturen.",
                "Sichtbar wird das an den Übergaben. Ein durchschnittlicher "
                "Auftrag durchlief in den vermessenen Betrieben 7 "
                "Übergaben, von der Anfrage bis zur Rechnung. An jeder "
                "dieser Stellen wartet Arbeit, verliert Information ihren "
                "Zusammenhang und entsteht neue Suchzeit. Wer Einarbeitung "
                "verkürzen will, begradigt zuerst diese Kette. Ein sauber "
                "beschriebener Ablauf macht aus Wochen der Begleitung Tage "
                "mit klaren Antworten.",
                "Für dich als Inhaber gehören Personalarbeit und "
                "Streckenarbeit deshalb zusammen. Jede Stunde, die in die "
                "Klarheit der Abläufe fließt, senkt die Kosten jeder "
                "künftigen Einstellung. Die Wirkung ist doppelt, denn "
                "klare Strecken entlasten erfahrene Mitarbeiter von "
                "Erklärarbeit und machen neue schneller produktiv.",
                "Die Fallstudien dieses Reports zeigen die Wirkung in "
                "beide Richtungen. Betriebe mit klaren Strecken gewinnen "
                "ihre Einarbeitung als Vorteil zurück, denn sie können "
                "einstellen, wenn der Markt es zulässt. Betriebe ohne "
                "diese Klarheit vererben ihr Geflecht an jede neue "
                "Generation von Mitarbeitern. Wie lernfähig ein Betrieb "
                "bleibt, entscheidet sich damit an seinen Strecken, lange "
                "bevor eine Stellenanzeige erscheint.",
            ),
            "mechanism": (
                "Was eine unklare Strecke jede Woche kostet",
                "Erfahrene Mitarbeiter beantworten dieselben Fragen in "
                "jeder Einarbeitung erneut.",
                "Ungeschriebene Regeln verlassen den Betrieb mit jeder "
                "Kündigung.",
                "Jede Übergabe erzeugt Wartezeit und verliert "
                "Zusammenhang.",
                "Vertretungen scheitern, weil Wissen an Personen hängt.",
            ),
        },
        9: {
            "principle": (
                "Fehler entstehen zwischen den Systemen, selten darin.",
                "Der dritte Befund widerspricht dem Bauchgefühl vieler "
                "Inhaber. Die Programme selbst arbeiten zuverlässig. Teuer "
                "wird der Weg dazwischen. In den vermessenen Betrieben "
                "liefen Auftragsdaten über 9 Schnittstellen, und an jeder "
                "davon wurden Angaben von Menschen gelesen, interpretiert "
                "und neu eingetippt. Jede dieser Stellen arbeitet unter "
                "Zeitdruck, und jede produziert eigene Abweichungen.",
                "Die Folge steht in den Auftragsdaten. 30 % der Aufträge "
                "durchliefen mindestens eine Korrekturschleife, weil "
                "Positionen, Preise oder Termine auf dem Weg verändert "
                "wurden. Jede dieser Schleifen bindet die erfahrensten "
                "Mitarbeiter, denn Fehler suchen darf nur, wer das "
                "Gesamtbild kennt.",
                "Mehr Kontrolle ist die teure Antwort auf dieses Muster. "
                "Sie fügt der Kette eine weitere Station hinzu und "
                "verlangsamt jeden Vorgang, auch die fehlerfreien. Die "
                "günstigere Antwort entfernt die Nahtstelle selbst. Was "
                "einmal sauber erfasst wird und die Strecke ohne "
                "Neueingabe durchläuft, braucht keine zweite Prüfung.",
                "Der Reihenfolge nach gehört diese Erkenntnis an den "
                "Anfang jedes Umbaus. Zuerst wird die Erfassung sauber, "
                "dann werden die Übergaben verbunden, und erst danach "
                "lohnt der Blick auf einzelne Programme. Wer die Kette "
                "andersherum angeht, automatisiert seine Fehlerquellen "
                "gleich mit. Die Fallstudie auf der nächsten Seite zeigt "
                "diese Reihenfolge im laufenden Projektgeschäft.",
            ),
            "mechanism": (
                "Wo Korrekturschleifen tatsächlich entstehen",
                "Ein Tippfehler in der Auftragsposition wandert bis auf "
                "die Rechnung.",
                "Gleiche Listen laufen auseinander, und jede gilt als "
                "führend.",
                "Telefonisch zugesagte Änderungen erreichen die Fertigung "
                "zu spät.",
                "Die Korrektur bindet die Personen mit dem Gesamtbild.",
            ),
        },
        10: {
            "case_story": (
                "Kolbe Technischer Handel. Wachstum ohne zusätzliche "
                "Stellen im Innendienst.",
                "Sandra Kolbe führt einen technischen Großhandel für "
                "Antriebselemente. Ihr Innendienst war das Nadelöhr des "
                "gesamten Vertriebs. Anfragen kamen per Mail, Telefon und "
                "über das Portal der Einkaufsverbände herein, und jede "
                "davon bedeutete Suchen in Preislisten, Rückfragen zur "
                "Verfügbarkeit und Abstimmung über Frachtkosten. "
                "Rahmenvertragskunden warteten genauso wie Neukunden.",
                "Im Jahr 2023, dem ersten Jahr der Messung, verließen 310 "
                "Angebote das Haus. Das Team war vollständig ausgelastet, "
                "und trotzdem blieben Anfragen unbeantwortet liegen. "
                "Zusätzliches Personal war auf dem Arbeitsmarkt schlicht "
                "kaum zu finden, und jede neue Kraft hätte zuerst das "
                "gewachsene Geflecht lernen müssen.",
                "Der Umbau begann bei den Produktdaten. Preise, Staffeln "
                "und Verfügbarkeiten wurden aus getrennten Listen in eine "
                "führende Quelle überführt. Danach wurden die eingehenden "
                "Anfragen strukturiert erfasst und Standardfälle "
                "automatisch vorbelegt. Der Innendienst prüft seitdem "
                "Angebote, statt sie abzutippen, und behält die "
                "Sonderfälle.",
                "Die Wirkung steht in der Jahresreihe auf dieser Seite. "
                "540 Angebote im Jahr 2024, dann 780 Angebote im Jahr "
                "2025, mit derselben Mannschaft. Der zusätzliche "
                "Auftragswert aus schneller beantworteten Anfragen "
                "summiert sich auf 2,1 Mio. €. Sandra Kolbe stellt "
                "inzwischen wieder ein, allerdings im Außendienst.",
                "Das Muster ist übertragbar. Ein Engpass im Innendienst "
                "ist selten ein Personalproblem. Er ist ein "
                "Streckenproblem, und Strecken lassen sich umbauen, "
                "während das Geschäft weiterläuft.",
                "Bemerkenswert ist, was sich im Team verändert hat. Aus "
                "Abtippern wurden Prüfer, und aus dem Nadelöhr wurde die "
                "Stelle, an der Marge entsteht. Kein einziger Arbeitsplatz "
                "ist entfallen. Die Arbeit ist eine andere geworden, und "
                "sie ist näher am Kunden.",
            ),
            "evidence_rail": (
                "Angebote pro Jahr bei Kolbe Technischer Handel",
            ),
        },
        11: {
            "principle": (
                "Der Sonderfall ist seltener, als er sich anfühlt.",
                "Jeder Inhaber hält seinen Betrieb für schwer "
                "automatisierbar, und jeder nennt dieselbe Begründung. Zu "
                "viele Ausnahmen, zu viel Erfahrungswissen, zu viel Zuruf. "
                "Die Messung zeichnet ein anderes Bild. 80 % der "
                "eingehenden Anfragen folgten wiederkehrenden Mustern, "
                "über alle Branchen unserer Projektbetriebe hinweg. Der "
                "gefühlte Ausnahmebetrieb ist in den Daten ein "
                "Regelbetrieb mit Ausnahmen.",
                "Über alle Projekte genügten 20 Muster, um diesen "
                "wiederkehrenden Kern abzubilden. Das ist die eigentliche "
                "Nachricht hinter der Zahl. Niemand muss seinen Betrieb "
                "vollständig beschreiben, um ihn zu entlasten. Es reicht, "
                "die wenigen Muster zu erfassen, die täglich vorkommen, "
                "und genau diese sauber laufen zu lassen.",
                "Die Ausnahmen bleiben bei deinen erfahrenen Mitarbeitern, "
                "und genau das ist ihre neue Rolle. Wer den "
                "wiederkehrenden Kern an die Strecke abgibt, hat Zeit für "
                "die Fälle, an denen Marge und Kundenbindung tatsächlich "
                "entschieden werden. Automatisierung sortiert die Arbeit. "
                "Sie schafft sie für die wichtigen Fälle erst frei.",
                "Der erste Schritt dorthin ist unspektakulär. Der Eingang "
                "wird strukturiert, die Muster werden benannt, und jedes "
                "Muster bekommt eine Strecke. Ab diesem Punkt lässt sich "
                "jede Woche messen, welcher Anteil der Arbeit ohne "
                "Eingriff läuft und wo sich die Ausnahmen häufen. Aus "
                "dieser Messung entsteht nebenbei das erste ehrliche Bild "
                "der eigenen Auslastung.",
            ),
            "mechanism": (
                "So verteilt sich das eingehende Anfragevolumen",
                "Wiederkehrende Standardanfragen laufen dennoch über "
                "Einzelbearbeitung.",
                "Varianten bekannter Fälle brauchen nur wenige Angaben.",
                "Echte Sonderfälle verdienen Erfahrung und bekommen sie "
                "erst, wenn der Kern läuft.",
                "Fehlgeleitete Anfragen verschwinden mit dem "
                "strukturierten Eingang.",
            ),
        },
        12: {
            "case_story": (
                "Brandt Elektrotechnik. Die Baustelle wartet nie auf die "
                "Verwaltung.",
                "Thomas Brandt führt einen Elektrotechnikbetrieb für "
                "Gewerbebauten. Sein Projektgeschäft lebt von Nachträgen, "
                "und genau dort stockte es. Aufmaße entstanden auf Papier, "
                "wanderten ins Büro, wurden übertragen, kalkuliert und zur "
                "Freigabe vorgelegt. Auf der Baustelle war der Zustand "
                "längst weiter, wenn die Verwaltung ihn erreichte.",
                "Die Messung zum Projektstart ergab 14 Tage zwischen "
                "Aufmaß und freigegebenem Nachtrag. In dieser Zeit "
                "arbeitete der Betrieb auf eigenes Risiko weiter oder ließ "
                "die Baustelle warten. Beides kostete Geld, und beides "
                "blieb im Tagesgeschäft unsichtbar, weil jeder Einzelfall "
                "erklärbar schien.",
                "Der Umbau setzte am Anfang der Strecke an. Aufmaße werden "
                "seitdem digital erfasst, mit Positionen, Fotos und Mengen "
                "in einer Struktur, die die Kalkulation direkt "
                "weiterverarbeitet. Der Nachtrag wird automatisch "
                "vorbereitet, die Freigabe erreicht den Verantwortlichen "
                "auf dem Telefon. Eine erneute manuelle Übertragung gibt "
                "es auf dieser Strecke seither nirgends mehr.",
                "Heute vergehen zwischen Aufmaß und Freigabe 2 Tage. Der "
                "Betrieb betreut 44 Projekte parallel, mit derselben "
                "Projektleitung wie vor dem Umbau. Thomas Brandt "
                "beschreibt die Wirkung nüchtern. Die Baustellen sind "
                "dieselben geblieben. Der Betrieb hinter ihnen ist ein "
                "anderer.",
                "Übertragbar ist vor allem der Ansatzpunkt. Wer eine "
                "Strecke entlasten will, beginnt an ihrem Anfang, bei der "
                "ersten Erfassung. Alles, was dort sauber ankommt, muss "
                "später nie repariert werden.",
                "Auf die Frage nach dem Aufwand antwortet Thomas Brandt "
                "mit dem Blick auf seine Projektliste. Der Umbau lief "
                "neben dem Tagesgeschäft, Stufe für Stufe, und keine "
                "Baustelle hat davon etwas bemerkt. Genau so war es "
                "geplant, und genau daran wurde er gemessen.",
            ),
            "evidence_rail": (
                "Kennzahlen aus dem Projekt Brandt Elektrotechnik",
            ),
        },
        13: {
            "principle": (
                "Die Reihenfolge entscheidet, ob sich der Umbau selbst "
                "trägt.",
                "Die meisten Automatisierungsvorhaben beginnen an der "
                "falschen Stelle. Am sichtbarsten Ärgernis, am lautesten "
                "Wunsch aus dem Team oder an dem Werkzeug, das gerade "
                "beworben wird. Der Taktplan wählt anders. Die erste "
                "Strecke ist die mit der größten gebundenen Zeit und dem "
                "geringsten Widerstand im Team. Beides wird vorher "
                "gemessen, nichts wird geraten.",
                "Der Grund ist wirtschaftlich. Bei richtiger Streckenwahl "
                "trägt der Umbau seine Kosten nach 3 Monaten selbst, weil "
                "die zurückgewonnene Zeit sofort in produktive Arbeit "
                "fließt. Jede weitere Stufe wird aus der vorigen "
                "finanziert. Ein Projekt, das sich selbst trägt, braucht "
                "keinen langen Atem und keine Geduldreserven.",
                "Gesteuert wird mit wenigen Größen. 5 Kennzahlen je "
                "Strecke genügen, von der Durchlaufzeit bis zur "
                "Fehlerquote. Alles darüber hinaus ist Berichtswesen ohne "
                "Entscheidung. Wenn eine Kennzahl kippt, wird die Strecke "
                "angepasst. Wenn alle stabil laufen, kommt die nächste "
                "Strecke an die Reihe.",
                "In der Praxis scheitert die Reihenfolge selten am "
                "Verstand und häufig an der Ungeduld. Die verlockende "
                "Strecke ist selten die richtige erste. Wer mit der "
                "lauten Baustelle beginnt, kämpft gegen Gewohnheiten und "
                "Technik gleichzeitig. Wer nach den Kriterien wählt, baut "
                "mit Rückenwind. Die Kriterien stehen im Kasten nebenan, "
                "und sie gelten unabhängig von Branche und Betriebsgröße.",
            ),
            "mechanism": (
                "Die Auswahlkriterien für die erste Strecke",
                "Gebundene Zeit pro Woche, gemessen statt geschätzt.",
                "Fehleranfälligkeit entlang der Übergaben zwischen den "
                "Systemen.",
                "Widerstand im Team, erhoben aus den Aussagen der "
                "Beteiligten.",
                "Sichtbarkeit des Ergebnisses in den ersten Wochen.",
            ),
        },
        14: {
            "method_frame": (
                "Der Taktplan. So läuft der Umbau.",
                "Die meisten Projekte dieser Art beginnen mit einer "
                "Systemauswahl und enden in einer Einführung, die niemand "
                "wollte. Der Taktplan dreht die Reihenfolge um. Zuerst "
                "wird gemessen, dann wird die Strecke mit dem größten "
                "Hebel umgebaut, und erst wenn sie läuft, folgt die "
                "nächste. Dein Tagesgeschäft läuft dabei ununterbrochen "
                "weiter.",
                 "Die erste Strecke läuft nach 14 Tagen im Tagesbetrieb. "
                 "Nach 90 Tagen ist die erste Stufe messbar, an denselben "
                 "Kennzahlen, die zum Start erhoben wurden. Was der Umbau "
                 "im Einzelnen enthält, hängt von deiner Messung ab und "
                 "wird im Erstgespräch konkret. Die Messung bleibt dabei "
                 "die Grundlage für jede spätere Entscheidung im Projekt.",
            ),
            "steps": (
                "Vermessen. Wir erfassen die Strecken deines Betriebs mit "
                "Zeiten, Übergaben und Beteiligten. Am Ende liegt eine "
                "Landkarte vor, zu der dein Team sagt, ja, genau so läuft "
                "es bei uns.",
                "Priorisieren. Aus der Landkarte entsteht die Reihenfolge "
                "des Umbaus. Bewertet wird nach gebundener Zeit, "
                "Fehleranfälligkeit und Widerstand im Team. Die erste "
                "Strecke gewinnt nach Zahlen, nie nach Geschmack.",
                "Umbauen. Die gewählte Strecke wird verbunden und "
                "automatisiert. Vorhandene Programme bleiben im Einsatz, "
                "sofern sie ihren Teil zuverlässig erledigen. Neues kommt "
                "nur dorthin, wo eine Lücke tatsächlich klafft.",
                "Einführen. Dein Team übernimmt die Strecke im laufenden "
                "Betrieb, mit direkter Begleitung in den ersten Wochen. "
                "Eingeführt ist eine Strecke erst, wenn die Mitarbeiter "
                "sie ohne uns bedienen.",
                "Messen. Dieselben Kennzahlen wie zum Start zeigen die "
                "Wirkung. Was sich verbessert hat, wird gesichert. Was "
                "hakt, wird angepasst, bevor die nächste Stufe beginnt.",
                "Ausbauen. Strecke für Strecke wächst der Anteil des "
                "Betriebs, der ohne Reibung läuft. Die Übergabe an dein "
                "Team ist von Beginn an Teil des Plans.",
            ),
        },
        15: {
            "trust_header": (
                "Belege statt Behauptungen aus dokumentierten Projekten",
            ),
            "proof_wall": (
                "Auszug aus dokumentierten Projektbewertungen",
                "Die Umstellung lief neben dem Tagesgeschäft, ohne dass eine "
                "Strecke stillstand.",
                "Wir sehen jede Woche in den Auswertungen, dass die zweite "
                "Schicht kleiner wird.",
            ),
        },
        16: {
            "synthesis": (
                "Die zweite Schicht bleibt, bis du sie abschaffst.",
                "Der Befund dieses Reports passt in wenige Sätze. In "
                "gewachsenen Betrieben sammelt sich Verwaltungsarbeit, die "
                "kein Kunde bestellt und keine Rechnung ausweist. Sie "
                "wächst mit jedem Auftrag, sie hängt am Wissen einzelner "
                "Personen, und sie verbraucht im Durchschnitt 68 Stunden "
                "pro Woche. Das ist die zweite Schicht, und sie steht auch "
                "in deinem Betrieb auf der Gehaltsliste.",
                "Die Fallstudien zeigen den Ausweg, und er beginnt nirgends "
                "mit einem Systemwechsel. Er beginnt mit einer Messung, "
                "einem klaren Bild der eigenen Strecken und einer "
                "Reihenfolge, die sich selbst finanziert. Reber, Kolbe und "
                "Brandt haben nichts erfunden. Sie haben die Reibung "
                "entfernt, die sich über Jahre angesammelt hatte.",
                "Ein weiteres Jahr im gewohnten Zustand ist ebenfalls eine "
                "Entscheidung, und sie hat einen Preis. Im Durchschnitt "
                "unserer Messungen sind es 310.000 € an gebundener "
                "Arbeitszeit, dazu wartende Kunden und Führungskräfte im "
                "Dauereinsatz als Sachbearbeiter. Dieser Preis erscheint "
                "auf keiner Rechnung. Bezahlt wird er trotzdem.",
                "Ob dein Betrieb über oder unter diesen Durchschnitten "
                "liegt, weiß heute niemand. Genau deshalb steht am Anfang "
                "jeder Zusammenarbeit die Messung. Sie ersetzt Vermutungen "
                "durch Zahlen aus deinem eigenen Haus. Danach entscheidest "
                "du auf Grundlage deiner Daten.",
                "Der Reihenfolge dieses Reports folgt auch die "
                "Entscheidung. Erst das eigene Bild prüfen, dann die "
                "Fallstudien mit dem eigenen Betrieb vergleichen, dann "
                "messen lassen. Jeder dieser Schritte ist klein, keiner "
                "verpflichtet zu einem Projekt, und jeder liefert etwas, "
                "das bleibt. Klarheit über den eigenen Betrieb.",
            ),
            "payoff": (
                "Ein weiteres Jahr wie bisher",
                "Gebundene Führung, wartende Angebote, wachsende Reibung",
                "Das erste Jahr nach dem Umbau",
                "Gemessene Strecken, schnelle Antworten, Zeit für Führung",
            ),
        },
        17: {
            "objection_frame": (
                "Was jetzt vermutlich in dir arbeitet.",
                "Diese Einwände hören wir in fast jedem Erstgespräch. Sie "
                "sind berechtigt, und sie verdienen klare Antworten statt "
                "Beschwichtigung.",
            ),
            "responses": (
                "„Wir haben so etwas schon einmal versucht.“",
                "Dann kennst du den üblichen Verlauf. Ein Werkzeug wurde "
                "gekauft, die Einführung blieb stecken, der Alltag gewann. "
                "Gescheitert ist dabei selten die Technik. Es fehlte die "
                "Messung davor und die Reihenfolge danach. Der Taktplan "
                "beginnt deshalb mit deinen Strecken und wählt die erste "
                "Stufe nach Zahlen aus deinem Betrieb.",
                "„Dafür fehlt uns gerade die Zeit.“ Der Einwand bestätigt "
                "den Befund, denn die Zeit fehlt, weil die zweite Schicht "
                "sie verbraucht. Der Einstieg braucht von dir ein Gespräch "
                "und von deinem Team wenige Stunden für die Messung. Alles "
                "Weitere läuft neben dem Tagesgeschäft, in Stufen, die "
                "einzeln abgeschlossen werden.",
                "„Unsere Branche funktioniert anders.“ Das stimmt, und es "
                "ändert weniger, als du erwartest. Die Muster hinter der "
                "gebundenen Zeit gleichen sich über alle vermessenen "
                "Betriebe, vom Anlagenbau bis zum Großhandel. Verschieden "
                "sind die Inhalte der Strecken. Der Weg, sie zu vermessen "
                "und umzubauen, bleibt derselbe.",
                "„Am Ende hängen wir an einem Dienstleister.“ Das "
                "Gegenteil ist der vertragliche Zweck. Jede Strecke wird "
                "dokumentiert übergeben, dein Team wird im laufenden "
                "Betrieb eingearbeitet, und die Unterlagen gehören dir. "
                "Eingeführt gilt eine Stufe erst, wenn sie ohne uns läuft. "
                "Gebunden bist du an dein eigenes Team.",
                "„Meine Mitarbeiter sehen darin eine Kontrolle.“ Diese "
                "Sorge ist ernst, und sie entscheidet über das Gelingen. "
                "Gemessen werden Strecken und Durchlaufzeiten, keine "
                "Personen. Dein Team benennt selbst, welche Aufgaben "
                "lästig sind, und genau dort beginnt der Umbau. Wer "
                "zuerst entlastet wird, trägt die Veränderung mit.",
                "„Woher weiß ich, ob es bei uns wirkt.“ Aus deinen "
                "eigenen Zahlen. Die Messung zum Start liefert die "
                "Ausgangswerte, dieselben Kennzahlen zeigen nach jeder "
                "Stufe die Wirkung. Wenn die erste Strecke nichts trägt, "
                "endet das Projekt dort. Auch das ist eine saubere "
                "Antwort.",
            ),
        },
        18: {
            "commitment": (
                "Zusammenarbeit beginnt mit einem Gespräch, nie mit einem "
                "Vertrag.",
                "Das Erstgespräch dauert 45 Minuten und ist eine "
                "beidseitige Prüfung. Du zeigst uns, wie dein Betrieb "
                "arbeitet. Wir sagen dir, ob ein Umbau bei euch trägt und "
                "wo er beginnen würde. Danach prüfen wir intern, ob wir "
                "dir tatsächlich helfen können.",
                "Ein Angebot erhältst du nur, wenn wir von messbaren "
                "Ergebnissen überzeugt sind. Falls das anders ausfällt, "
                "sagen wir es offen, und du behältst die Erkenntnisse aus "
                "dem Gespräch. Nach 90 Tagen entscheiden deine eigenen "
                "Kennzahlen über die Fortsetzung.",
                 "Der gesamte Einstieg bleibt bewusst klein. Kein "
                 "Rahmenvertrag, keine Lizenzbindung, kein Umbau auf "
                 "Verdacht. Erst die Messung, dann die Entscheidung. "
                 "Jede Stufe wird im laufenden Betrieb geprüft, "
                 "bevor die nächste beginnt.",
            ),
            "pathway": (
                 "Erstgespräch. Wir klären Ausgangslage, Engpass und "
                 "Erwartung. Du erfährst im Gegenzug, wie der Taktplan "
                 "arbeitet und ob dein Betrieb dafür geeignet ist.",
                "Streckenmessung. Wir erheben Zeiten, Übergaben und "
                "Beteiligte der wichtigsten Abläufe vor Ort. Dein Team ist "
                "eingebunden, der Aufwand bleibt klein und planbar.",
                "Taktplan. Du erhältst die Reihenfolge des Umbaus mit dem "
                "erwarteten Zeitgewinn je Strecke. Das Dokument gehört "
                "dir, unabhängig von jeder weiteren Zusammenarbeit.",
                "Erste Strecke. Der Umbau startet an der Stelle mit dem "
                "größten Hebel. Dein Tagesgeschäft läuft unverändert "
                "weiter, die Strecke geht stufenweise in Betrieb.",
                "Messung und Nachweis. Dieselben Kennzahlen wie zum Start "
                "zeigen die Wirkung. Über die Fortsetzung entscheidet das "
                "Ergebnis, nie das Bauchgefühl. Alle Werte stammen aus "
                "deinem Betrieb, nichts wird geschönt.",
                 "Ausbau und Übergabe. Weitere Strecken folgen im Takt, "
                 "dein Team übernimmt jede davon dokumentiert. Am Ende "
                 "führt ihr das System selbst, und unsere Rolle wird "
                 "kleiner, während deine Strecken wachsen.",
            ),
        },
        19: {
            "headline": (
                "Was sich ändert, wenn sich nichts ändert.",
            ),
            "narrative": (
                "Es gibt einen einfachen Test für die Dringlichkeit dieses "
                "Themas. Stell dir deinen Betrieb in einem Jahr vor, "
                "unverändert geführt, mit gleichem Team und wachsendem "
                "Auftragsbuch. Nichts daran ist ein Krisenszenario. Es ist "
                "die naheliegendste aller Zukünfte, und genau deshalb "
                "lohnt der genaue Blick darauf.",
                "Die Anfragen werden mehr, also wächst der Stapel zwischen "
                "Eingang und Angebot. Die erfahrenen Mitarbeiter tragen "
                "mehr Wissen, also werden Urlaube und Kündigungen teurer. "
                "Die Abstimmung braucht mehr Zuruf, also wandern "
                "Führungsstunden in Sachbearbeitung. Jede dieser "
                "Bewegungen ist klein. Zusammen ergeben sie die Richtung.",
                "Auf der anderen Seite steht der Betrieb, der seine "
                "Strecken kennt. Anfragen laufen strukturiert ein, "
                "Angebote verlassen das Haus, während der Wettbewerb noch "
                "sucht, und neue Mitarbeiter arbeiten nach Tagen produktiv "
                "statt nach Monaten. Der Unterschied zwischen beiden "
                "Betrieben ist kein Talent. Es ist Reihenfolge und "
                "Handwerk.",
                "Beide Wege kosten. Der eine kostet einen Umbau mit "
                "Anfang, Ende und messbarem Ergebnis. Der andere kostet "
                "jede Woche ein Stück Führungszeit, und er stellt seine "
                "Rechnung leise. Welcher Weg günstiger ist, entscheidet "
                "sich in deinen Zahlen, und genau dort beginnt die Arbeit.",
                "Die letzte Seite dieses Reports ist bewusst kurz. Sie "
                "verlangt keine Unterschrift und keine Entscheidung über "
                "ein Projekt. Sie bietet ein Gespräch an, mehr nicht. Was "
                "daraus wird, bestimmen deine Strecken und deine Ziele.",
                "Wenn du beim Lesen an eine bestimmte Strecke in deinem "
                "Betrieb gedacht hast, ist das kein Zufall. Es ist der "
                "Punkt, an dem die Messung beginnen würde. Nimm diesen "
                "Gedanken mit in das Gespräch auf der letzten Seite. Mehr "
                "Vorbereitung braucht es nicht."
                "Zur Einordnung der Zahlen in diesem Report. Wir haben in "
                "den vergangenen Jahren die Abläufe von Betrieben aus "
                "Maschinenbau, Großhandel und Elektrotechnik vermessen, "
                "immer mit derselben Frage. Wie viel Zeit fließt in Arbeit, "
                "die kein Kunde je sieht und kein Angebot je enthält. Die "
                "68 Stunden auf dem Titel sind der Durchschnitt aus diesen "
                "eigenen Projektdaten, gemessen vor dem ersten Umbau. Kein "
                "Ausreißer, sondern der Normalzustand in gewachsenen "
                "Betrieben mit vollem Auftragsbuch.",
            ),
            "anchor": (
                "Werkhalle am Abend nach der letzten Übergabe",
            ),
        },
        20: {
            "closing_statement": (
                "Ein Gespräch. Danach weißt du, wo dein Betrieb steht.",
            ),
            "identity_close": (
                "Feldmann Automation",
                "Jonas Feldmann liest jede Anfrage selbst und antwortet "
                "innerhalb eines Arbeitstages. Schreib an "
                "gespraech@feldmann-automation.de oder buche den Termin "
                "direkt über feldmann-automation.de. Das Gespräch ist der "
                "einzige nächste Schritt.",
            ),
        },
    }


def _apex_dense_source() -> tuple[dict, list[dict]]:
    """Build the single synthetic source and every claim with exact spans."""
    sentences = [
        sentence for _, _, sentence in _APEX_SPAN_CLAIMS.values()
    ]
    sentences.extend(_APEX_QUOTE_CLAIMS.values())
    verbatim_text = _APEX_SOURCE_HEADER + "\n" + "\n".join(sentences)
    source = {
        "source_id": _APEX_SOURCE_ID,
        "source_kind": "document",
        "locator": (
            "Betriebsauswertung und Interviewprotokoll, Feldmann "
            "Automation GmbH, interne Projektablage"
        ),
        "captured_at": "2026-05-11T09:00:00Z",
        "rights_status": "client_supplied_cleared",
        "verbatim_text": verbatim_text,
        "language": "de",
        "allowed_uses": ["report"],
    }
    claims: list[dict] = []
    for claim_id, (value, unit, sentence) in _APEX_SPAN_CLAIMS.items():
        offset = verbatim_text.index(sentence)
        start = offset + sentence.index(value)
        end = start + len(value)
        claim = {
            "claim_id": claim_id,
            "claim_type": "number",
            "normalized_value": value,
            "source_ids": [_APEX_SOURCE_ID],
            "source_spans": [
                {
                    "source_id": _APEX_SOURCE_ID,
                    "start": start,
                    "end": end,
                    "verbatim": value,
                }
            ],
        }
        if unit is not None:
            claim["unit"] = unit
        scopes = _APEX_SERIES_SCOPES.get(claim_id)
        if scopes is not None:
            claim["entity_scope"], claim["time_scope"] = scopes
        claims.append(claim)
    for claim_id, quote_text in _APEX_QUOTE_CLAIMS.items():
        start = verbatim_text.index(quote_text)
        claims.append(
            {
                "claim_id": claim_id,
                "claim_type": "quote",
                "normalized_value": quote_text,
                "source_ids": [_APEX_SOURCE_ID],
                "source_spans": [
                    {
                        "source_id": _APEX_SOURCE_ID,
                        "start": start,
                        "end": start + len(quote_text),
                        "verbatim": quote_text,
                    }
                ],
                "allowed_uses": ["report", "quotation"],
            }
        )
    for claim_id, (value, formula, operands) in _APEX_COMPUTED_CLAIMS.items():
        claims.append(
            {
                "claim_id": claim_id,
                "claim_type": "number",
                "normalized_value": value,
                "computation": {
                    "formula": formula,
                    "operand_claim_ids": list(operands),
                },
            }
        )
    return source, claims


def apex_dense_envelope(profile: dict, asset_dir: Path) -> dict:
    """The apex-dense-report recipe: reference-density authored envelope."""
    registry = load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)
    family_by_id = {family.family_id: family for family in registry.families}
    fixture_id = profile["fixture_id"]
    copy_by_face = _apex_dense_copy()
    source, claims = _apex_dense_source()

    pages: list[dict] = []
    faces: list[dict] = []
    assets: list[dict] = []
    facts: list[dict] = []
    case_index = 0

    for index, role in enumerate(ROLES, start=1):
        face_id = f"face.{index:02d}"
        family = family_by_id[FAMILY_BY_ROLE[role]]
        face_copy = copy_by_face[index]
        claim_ids = list(_APEX_CLAIMS_BY_FACE.get(index, ()))
        proof_requirements: list[dict] = []
        asset_requirements: list[dict] = []
        selected_asset_ids: list[str] = []

        asset_class = _APEX_ASSETS.get(index)
        if asset_class is not None:
            # Blue-toned gradient photo fields (Apex prints full-bleed blue
            # photography, never flat gray voids). Deterministic bytes: the
            # composition is a pure function of the semantic class.
            if asset_class == "identity":
                # Dark-to-accent gradient with a bust-like figure; the exact
                # accent band stays at the image foot so the case rail's
                # proof band carries the declared brand blue.
                gradient = (
                    (0.0, _APEX_DARK),
                    (0.86, _APEX_BLUE),
                    (1.0, _APEX_BLUE),
                )
                figure = ((0.5, 0.3, 0.14, 0.14), (0.5, 0.68, 0.33, 0.25))
            else:
                # context / proof: accent-to-dark photo field with a lighter
                # figure subject in the lower third.
                gradient = ((0.0, _APEX_BLUE), (1.0, _APEX_DARK))
                figure = ((0.5, 0.42, 0.13, 0.13), (0.5, 0.82, 0.32, 0.28))
            asset = _asset(
                asset_dir, face_id, asset_class, gradient=gradient, figure=figure
            )
            assets.append(asset)
            selected_asset_ids.append(asset["asset_id"])
            if index == 15:
                # Trust wall: four client logo marks join the proof asset so
                # the materialize stage groups them into one logo wall, the
                # way the reference trust pages carry client rows.
                for logo_index in range(1, 5):
                    shade = 0.35 + 0.12 * logo_index
                    logo = _asset(
                        asset_dir,
                        face_id,
                        "logo",
                        gradient=(
                            (0.0, _APEX_DARK),
                            (1.0, tuple(int(c * shade) for c in (230, 236, 240))),
                        ),
                        figure=((0.5, 0.5, 0.3, 0.16),),
                        name_suffix=f"logo{logo_index}",
                    )
                    assets.append(logo)
                    selected_asset_ids.append(logo["asset_id"])
            if asset_class in {"identity", "proof"}:
                asset_requirements.append(
                    {
                        "requirement_id": f"{face_id}.{asset_class}",
                        "semantic_class": asset_class,
                        "required_for_ship": True,
                    }
                )

        if role == "case_study":
            case_index += 1
        if role == "trust_proof":
            proof_requirements.append(
                {
                    "requirement_id": f"{face_id}.trust",
                    "proof_type": "trust",
                    "claim_ids": ["claim.trust.clients"],
                    "required_for_ship": True,
                }
            )

        faces.append(
            {
                "face_id": face_id,
                "face_index": index,
                "role": role,
                "narrative_act": f"apex arc act {index}",
                "argument": face_copy[next(iter(face_copy))][0],
                "claim_ids": claim_ids,
                "proof_requirements": proof_requirements,
                "asset_requirements": asset_requirements,
                "dominant_mechanism": MECHANISM_BY_ROLE[role],
                # Per-face editorial mode, matching the corpus: covers and
                # identity faces are photo-led (light), the argument pages
                # (outlook, status quo, beliefs, summary) are Richard's
                # dense text pages, everything else sits moderate.
                "density_band": (
                    "light"
                    if index in (1, 3)
                    else "dense"
                    if index in (2, 4, 5, 16, 19)
                    else "moderate"
                ),
                "case_id": f"case.{case_index}" if role == "case_study" else None,
            }
        )
        pages.append(
            {
                "slot": index,
                "type": ST_BY_ROLE[role],
                "page_numbers": str(index),
                "data": {
                    # Digit-free: the legacy numeric scan walks page data and
                    # matches full normalized claim values only. The printed
                    # copy lives in composition_facts_v3, never here.
                    "title": "Die zweite Schicht",
                    "body": "Der Inhalt dieser Seite ist im Streckenplan verankert.",
                },
            }
        )

        content_by_ref: dict[str, str] = {}
        region_facts: dict[str, dict] = {}
        stats_region: str | None = None
        for region in family.regions:
            if "stat" in region.allowed_element_kinds and stats_region is None:
                stats_region = region.region_id
        image_regions = {
            region.region_id
            for region in family.regions
            if "image" in region.allowed_element_kinds
        }
        first_image_region = next(
            (
                region.region_id
                for region in family.regions
                if region.region_id in image_regions
            ),
            None,
        )
        consumed_by_viz = set()
        for claim_id in claim_ids:
            if claim_id in _APEX_COMPUTED_CLAIMS:
                consumed_by_viz.add(claim_id)
                consumed_by_viz.update(_APEX_COMPUTED_CLAIMS[claim_id][2])
            if claim_id in _APEX_SERIES_SCOPES:
                consumed_by_viz.add(claim_id)
        stat_claims = [
            claim_id for claim_id in claim_ids if claim_id not in consumed_by_viz
        ]
        for region in family.regions:
            texts = face_copy.get(region.region_id, ())
            refs = []
            for item_index, text in enumerate(texts, start=1):
                ref = f"content.{face_id}.{region.region_id}.{item_index:02d}"
                refs.append(ref)
                content_by_ref[ref] = text
            has_image = (
                selected_asset_ids
                and region.region_id == first_image_region
            )
            region_facts[region.region_id] = {
                "content_refs": refs,
                "font_size_pt": _APEX_FONT_PT[(family.family_id, region.region_id)],
                "image_aspect_ratio": 1.0 if has_image else None,
                "stat_count": (
                    len(stat_claims) if region.region_id == stats_region else 0
                ),
                "list_item_count": len(refs),
            }
        facts.append(
            {
                "face_id": face_id,
                "language": "de",
                "content_by_ref": content_by_ref,
                "regions": region_facts,
                "asset_ids": selected_asset_ids,
            }
        )

    envelope = {
        "payload": {
            "meta": {
                "client_slug": fixture_id,
                "report_id": fixture_id,
                "lang": "de",
                "page_format": "A4",
                "page_count_target": 20,
            },
            "pages": pages,
        },
        "images": {},
        "brand_tokens": {
            "founder_full_name": "Jonas Feldmann",
            "brand_accent": APEX_DENSE_ACCENT,
            "calibration_visual_brand": profile["visual_brand"],
            "calibration_tone": profile["tone"],
        },
        # The client profile id reaches the render bundle (G1).
        "brand_profile_id": profile.get("profile_id"),
        "sources": [source],
        "claims": claims,
        "source_appendix_v3": {
            "schema_version": "1.0",
            "entries": [
                {
                    "source_id": _APEX_SOURCE_ID,
                    "citation_text": (
                        "Feldmann Automation GmbH (2026). Betriebsauswertung "
                        "und Interviewprotokoll der eigenen Kundenprojekte. "
                        "Interne Projektablage."
                    ),
                }
            ],
        },
        "assets": assets,
        "editorial_brief_v3": {
            "product_profile_id": "dmc_house_20_face",
            "faces": faces,
            # Richard's own format model, measured from four of the six reference
            # reports: an A4 cover, NINE A3 double-page spreads carrying two
            # faces each, and an A4 back cover. 11 physical objects, 20 faces.
            "formats": ["a4"] + ["a3"] * 9 + ["a4"],
            "audience": "German B2B founder (Mittelstand)",
            "central_thesis": (
                "Die zweite Schicht, die unbezahlte Verwaltungsarbeit "
                "gewachsener Betriebe, ist messbar und lässt sich Strecke "
                "für Strecke abschaffen."
            ),
            "promise": (
                "Der Leser erkennt die eigenen Strecken und weiß, in "
                "welcher Reihenfolge sich der Umbau trägt."
            ),
            "tone_profile": "Richard house",
            "design_features": _design_features_for_profile(profile),
        },
        "composition_facts_v3": facts,
    }
    return envelope
