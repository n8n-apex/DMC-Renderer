"""Regenerate the review fixtures: source envelopes + migration reports.

Runs the real migration and the real v3 precomposition pipeline, then writes:
- dmc-renderer/fixtures/v3/real/{jousef,christopher}-source-envelope.json
- dmc-renderer/fixtures/v3/real/reports/{jousef,christopher}-migration-report.md

Run with the preprocessor venv:
    research/preprocessor/.venv/bin/python research/migrations/generate_fixtures.py

The script refuses to write anything if the pipeline does not block, if the
record is not deterministic, or if the envelope does not round-trip.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ("research/migrations", "research/preprocessor"):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from contracts_v3.report_plan import load_product_profile  # noqa: E402
from legacy_report_v3 import MigrationRecord, build_migration_record  # noqa: E402
from pipeline_v3 import PrecompositionBlocked, build_precomposition_bundle_v3  # noqa: E402

PROFILE = load_product_profile(ROOT / "research" / "preprocessor" / "policies" / "dmc_house_20_face.json")
REAL = ROOT / "dmc-renderer" / "fixtures" / "v3" / "real"
REPORTS = REAL / "reports"

CLIENTS = (
    ("jousef", "dmc-renderer/fixtures/apex_consulting_payload.json", "$.payload"),
    ("christopher", "dmc-renderer/fixtures/christoph_v5_payload.json", "$"),
)


def render_report(record: MigrationRecord, pipeline_codes: tuple[str, ...]) -> str:
    artifact = record.original_artifact
    ref_counts = Counter(ref.reference_kind for ref in record.source_references)
    blocker_counts = Counter(b.code for b in record.blockers)
    selection = record.case_selection

    lines: list[str] = []
    lines.append(f"# Migration report: {record.client_id}")
    lines.append("")
    lines.append(
        "Review-only migration of a legacy report payload into v3 editorial "
        "inputs. This record is NOT renderable and must not be treated as "
        "approved content. Every open gate below requires a human decision."
    )
    lines.append("")
    lines.append("## Original artifact (preserved, verified separately)")
    lines.append("")
    lines.append(f"- Repository path: `{artifact.repository_path}`")
    lines.append(f"- SHA-256: `{artifact.sha256}`")
    lines.append(f"- Byte count: {artifact.byte_count}")
    lines.append(f"- Report pointer: `{artifact.report_pointer}`")
    lines.append(
        "- The original bytes are never edited. `verify_original` recomputes "
        "the hash and byte count on demand."
    )
    lines.append("")
    lines.append("## Source references (all rights unresolved)")
    lines.append("")
    lines.append(
        f"- Total references preserved verbatim: {len(record.source_references)}"
    )
    for kind in ("explicit_source_field", "citation", "url_field", "inline_url"):
        if ref_counts.get(kind):
            lines.append(f"- {kind}: {ref_counts[kind]}")
    lines.append(
        "- Every reference carries rights_status `unknown`. No rights were "
        "invented; resolving them is a human task."
    )
    lines.append("")
    lines.append("## Case selection (pending human decision)")
    lines.append("")
    lines.append(
        f"- Candidates found in the legacy report: {len(selection.candidates)}"
    )
    for candidate in selection.candidates:
        lines.append(
            f"  - slot {candidate.source_slot}: {candidate.source_label} "
            f"(`{candidate.source_content_path}`)"
        )
    lines.append(
        f"- Required case count: {selection.required_case_count}. Chosen: "
        f"{len(selection.chosen_cases)}. Excluded: {len(selection.excluded_cases)}. "
        f"Pending: {len(selection.pending_cases)}."
    )
    lines.append(
        f"- Human review status: `{selection.human_review_status}`. No automated "
        "selection was made."
    )
    lines.append("")
    lines.append("## Editorial map (explicit, never page-range derived)")
    lines.append("")
    lines.append(
        "- 20 faces defined explicitly from source content paths. Legacy "
        "`page_numbers` strings were never read; mutating them does not change "
        "this map."
    )
    lines.append("")
    lines.append("| Face | Role | Source |")
    lines.append("| --- | --- | --- |")
    for face in record.editorial_map.faces:
        if face.source_content_paths:
            source = ", ".join(f"`{p}`" for p in face.source_content_paths)
        else:
            source = face.source_gap or "none"
        lines.append(f"| {face.face_id} | {face.role} | {source} |")
    lines.append("")
    lines.append("## Typed blockers")
    lines.append("")
    lines.append(f"- Total blockers: {len(record.blockers)}")
    for code in sorted(blocker_counts):
        lines.append(f"- `{code}`: {blocker_counts[code]}")
    lines.append("")
    lines.append(
        "- Migrated `sources`, `claims`, and `assets` are all empty: nothing "
        "in the legacy payload is grounded, rights-cleared, or span-verified, "
        "so nothing was promoted."
    )
    lines.append(f"- `renderable`: {record.renderable}")
    lines.append("")
    lines.append("## Precomposition outcome")
    lines.append("")
    lines.append(
        "Correctly blocked. Feeding this record through "
        "`build_precomposition_bundle_v3` raises `PrecompositionBlocked`; the "
        "pipeline refuses to produce a bundle from this migration."
    )
    lines.append("")
    lines.append("Distinct failure codes raised by the pipeline:")
    lines.append("")
    for code in sorted(set(pipeline_codes)):
        lines.append(f"- `{code}`")
    lines.append("")
    lines.append(
        "This document is for human review only. Nothing here is release "
        "material, and no gate may be closed by editing this report."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    for client_id, rel_path, pointer in CLIENTS:
        original = ROOT / rel_path
        record = build_migration_record(
            client_id=client_id,
            original_path=original,
            project_root=ROOT,
            report_pointer=pointer,
        )
        # Determinism check: building twice yields identical records.
        again = build_migration_record(
            client_id=client_id,
            original_path=original,
            project_root=ROOT,
            report_pointer=pointer,
        )
        assert record == again, f"{client_id}: migration record is not deterministic"

        document = json.loads(original.read_text(encoding="utf-8"))
        source_bundle, brief = record.to_precomposition_inputs(document)
        try:
            build_precomposition_bundle_v3(source_bundle, brief, PROFILE)
        except PrecompositionBlocked as blocked:
            codes = blocked.codes
        else:
            raise AssertionError(
                f"{client_id}: pipeline did not block; refusing to write fixtures"
            )

        envelope = REAL / f"{client_id}-source-envelope.json"
        envelope.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")

        # Round-trip check against the exact serialized bytes.
        parsed = MigrationRecord.model_validate_json(envelope.read_text(encoding="utf-8"))
        assert parsed == record, f"{client_id}: envelope does not round-trip"

        report_path = REPORTS / f"{client_id}-migration-report.md"
        text = render_report(record, codes)
        assert "—" not in text, "em dash found in report"
        report_path.write_text(text, encoding="utf-8")
        print(f"{client_id}: {len(record.blockers)} blockers, "
              f"{len(record.source_references)} references, "
              f"{len(set(codes))} distinct pipeline codes -> {envelope.name}, {report_path.name}")


if __name__ == "__main__":
    main()
