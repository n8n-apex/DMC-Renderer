"""Supabase reference catalog — unified ingestion + selection.

The system has TWO reference corpora (legacy quality-loop index, 84 objects;
reference atlas, 120 faces) that were never joined. This module is the bridge:
it ingests BOTH into the Supabase `ref_reports` / `ref_faces` tables (the
authoritative catalog), deduplicates by (report, page_no, face_index), and
exposes the semantic selector the Director uses.

Page roles (st_type) come from the REPORT JSON when known (authoritative —
a client deck's own content knows its page roles; the text classifier blanks
client decks to OTHER, which hid apex's A3 spreads) and fall back to the
legacy text classification otherwise.

Connection: Supabase Transaction Pooler (pgbouncer) — asyncpg REQUIRES
`statement_cache_size=0` (prepared statements are not supported by pgbouncer
in transaction/statement mode; verified 2026-08-14).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent.parent

LEGACY_INDEX = ROOT / "research" / "quality_loop" / "references" / "index.json"
ATLAS_JSON = ROOT / "research" / "reference-atlas" / "reference-atlas.json"

# Authoritative per-report slot → st_type maps (from each client's own
# report_content.json). A client deck KNOWS its page roles; the legacy text
# classifier forces client decks to OTHER. Extend per client as they onboard.
REPORT_SLOT_MAPS: dict[str, dict[int, str]] = {
    "apex": {
        1: "ST-01", 2: "ST-02", 3: "ST-05", 4: "ST-09", 5: "ST-14",
        6: "ST-31", 7: "ST-07A", 8: "ST-07B", 9: "ST-07A", 10: "ST-07B",
        11: "ST-31", 12: "ST-07A", 13: "ST-07B", 14: "ST-07A", 15: "ST-07A",
        16: "ST-06", 17: "ST-31", 18: "ST-FAZIT", 19: "ST-22", 20: "ST-03",
    },
}

# Authoritative per-report page ARGUMENTS (title + client) from the report
# JSON — the atlas annotations for client decks are stale (built from an older
# layout) and misalign; the report's own copy is the truth the Director reads.
# key: (report, page_no) -> (client_name, title)
REPORT_PAGE_ARGUMENTS: dict[tuple[str, int], tuple[str, str]] = {
    ("apex", 1): ("", "Dein Wachstum frisst dich selbst auf"),
    ("apex", 2): ("", "Dein Wachstum scheitert nicht am Markt"),
    ("apex", 3): ("", "Über 100 AI-Projekte. Ein Ergebnis: Betrieb in Zahlen"),
    ("apex", 4): ("", "Dein Unternehmen wächst. Deine Prozesse nicht."),
    ("apex", 5): ("", "Drei Lügen, die dein Wachstum blockieren"),
    ("apex", 7): ("Martina Ammon", "Von operativem Chaos zu skalierbarer KI-Infrastruktur"),
    ("apex", 8): ("", "Wachstum entsteht nicht durch mehr Köpfe"),
    ("apex", 9): ("Cordes Consulting", "6 manuelle Prozesse automatisiert, Kapazität verdoppelt"),
    ("apex", 10): ("", "Kapazität entsteht nicht durch Köpfe, sondern durch Systeme"),
    ("apex", 12): ("Frese Recruiting", "Von 24-Stunden-Reaktionszeit zu Minuten"),
    ("apex", 13): ("", "Kommunikation skaliert nicht durch Köpfe"),
    ("apex", 14): ("Conesso GmbH", "Onboarding von 30 Minuten auf 2 Minuten"),
    ("apex", 15): ("Hanisch & Klein", "Von fragmentierten Tools zu skalierbarem End-to-End"),
    ("apex", 16): ("", "Das Done-For-You AI Automation Framework"),
    ("apex", 18): ("", "Dein Wachstum wartet nicht auf deine Entscheidung"),
    ("apex", 19): ("", "Von Erstgespräch zu laufendem AI-System in Wochen"),
    ("apex", 20): ("", "Buche jetzt dein kostenloses Erstgespräch mit APEX"),
}


def _page_argument(report: str, page_no: int, fallback: str) -> str:
    """Authoritative page argument from the report JSON when known."""
    entry = REPORT_PAGE_ARGUMENTS.get((report, page_no))
    if entry:
        client, title = entry
        return f"{client} — {title}" if client else title
    return fallback or ""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_legacy_rows() -> list[dict]:
    """Load the legacy quality-loop index rows (deck, page_no, st_type,
    axes, png_path)."""
    if not LEGACY_INDEX.exists():
        return []
    return json.loads(LEGACY_INDEX.read_text(encoding="utf-8"))


def load_atlas_rows() -> list[dict]:
    """Load the reference-atlas faces (report, physical_face, role, density,
    mechanism, devices, thumbnail, etc.)."""
    if not ATLAS_JSON.exists():
        return []
    data = json.loads(ATLAS_JSON.read_text(encoding="utf-8"))
    return data.get("faces", [])


def _atlas_face_index(row: dict) -> int:
    """Map an atlas spread_side (None|'L'|'R'|0|1) to a face index."""
    side = row.get("spread_side")
    if side is None:
        return 0
    if isinstance(side, str):
        return 0 if side.strip().upper() in ("", "L", "LEFT") else 1
    return int(side)


def _page_st_type(report: str, page_no: int, fallback: str) -> str:
    """Authoritative st_type: report slot map wins; legacy classifier else."""
    slot_map = REPORT_SLOT_MAPS.get(report)
    if slot_map and page_no in slot_map:
        return slot_map[page_no]
    return fallback or "OTHER"


def _devices_csv(row: dict | None) -> str:
    if not row:
        return ""
    anatomy = row.get("anatomy") or []
    if isinstance(anatomy, list):
        return ",".join(str(x) for x in anatomy)
    return str(anatomy)


def build_catalog_rows() -> list[dict]:
    """Join the two corpora into canonical catalog rows.

    The atlas is the richer source (role/density/mechanism/devices/format);
    the legacy index contributes st_type + axes; the report slot map
    OVERRIDES st_type. Keyed by (report, page_no, face_index).
    """
    legacy = load_legacy_rows()
    atlas = load_atlas_rows()

    legacy_by_key: dict[tuple, dict] = {}
    for row in legacy:
        legacy_by_key[(str(row.get("deck")), int(row.get("page_no", 0)))] = row

    atlas_by_key: dict[tuple, dict] = {}
    for row in atlas:
        atlas_by_key[
            (str(row.get("report")), int(row.get("physical_face", 0)), _atlas_face_index(row))
        ] = row

    rows: list[dict] = []
    for (report, page_no), lrow in sorted(legacy_by_key.items()):
        faces = [
            atlas_by_key.get((report, page_no, 0)),
            atlas_by_key.get((report, page_no, 1)),
        ]
        faces = [f for f in faces if f]
        a0 = faces[0] if faces else None
        format_ = "a3" if len(faces) > 1 else "a4"
        st_type = _page_st_type(report, page_no, str(lrow.get("st_type") or "OTHER"))
        rows.append({
            "report": report,
            "page_no": page_no,
            "face_index": 0,
            "st_type": st_type,
            "role": (a0 or {}).get("role") or "",
            "format": format_,
            "density": (a0 or {}).get("density_band") or "",
            "mechanism": (a0 or {}).get("visual_mechanism") or "",
            "devices": _devices_csv(a0),
            "axes": lrow.get("axes") or {},
            "argument": _page_argument(report, page_no, (a0 or {}).get("title") or ""),
            "png_path": str(lrow.get("png_path") or ""),
            "metadata": {
                "atlas_ids": [f.get("id") for f in faces],
                "atlas_confidence": [
                    (f.get("confidence"), f.get("pattern_family")) for f in faces
                ],
            },
        })
        for f in faces[1:]:
            rows.append({
                "report": report,
                "page_no": page_no,
                "face_index": _atlas_face_index(f),
                "st_type": st_type,
                "role": f.get("role") or "",
                "format": "a3",
                "density": f.get("density_band") or "",
                "mechanism": f.get("visual_mechanism") or "",
                "devices": _devices_csv(f),
                "axes": lrow.get("axes") or {},
                "argument": _page_argument(report, page_no, f.get("title") or ""),
                "png_path": str(lrow.get("png_path") or ""),
                "metadata": {"atlas_ids": [f.get("id")], "atlas_confidence": []},
            })
    return rows


async def upsert_catalog(dsn: str, *, verbose: bool = False) -> dict:
    """Ingest both corpora into Supabase. Idempotent (upsert on unique key)."""
    conn = await asyncpg.connect(dsn, timeout=30, statement_cache_size=0)
    try:
        reports: list[dict] = [
            {"slug": "apex", "display_name": "APEX KI DMC Report", "source_pdf": "APEX - KI DMC Report v1 (1).pdf", "is_client": True, "page_count": 20},
            {"slug": "niklas", "display_name": "Niklas Niemeyer DMC-Report", "source_pdf": "Niklas Niemeyer DMC-Report Druckfertig (1).pdf", "is_client": True, "page_count": 20},
            {"slug": "buchagentur", "display_name": "Buchagentur DMC-Report", "source_pdf": "Buchagentur DMC-Report (1).pdf", "is_client": True, "page_count": 11},
            {"slug": "boss", "display_name": "Alexander Boss DMC-Report", "source_pdf": "DMC-Report Alexander Boss doppelt (1).pdf", "is_client": True, "page_count": 11},
            {"slug": "werkzeugkoffer", "display_name": "Mein Werkzeugkoffer DMC-Report", "source_pdf": "DMC-Report Mein_Werkzeugkoffer.pdf", "is_client": True, "page_count": 11},
            {"slug": "aerztepartner", "display_name": "Ärztepartner DMC-Report", "source_pdf": "aerztepartner_v0.2 (1).pdf", "is_client": True, "page_count": 11},
        ]
        for meta in reports:
            await conn.execute(
                """
                INSERT INTO ref_reports (slug, display_name, source_pdf, is_client, page_count)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (slug) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    source_pdf = EXCLUDED.source_pdf,
                    is_client = EXCLUDED.is_client,
                    page_count = EXCLUDED.page_count
                """,
                meta["slug"], meta["display_name"], meta["source_pdf"], meta["is_client"], meta["page_count"],
            )

        rows = build_catalog_rows()
        inserted = 0
        for r in rows:
            rep_id = await conn.fetchval("SELECT id FROM ref_reports WHERE slug = $1", r["report"])
            if rep_id is None:
                continue
            png_path = r["png_path"]
            sha = ""
            if png_path:
                resolved = ROOT / "research" / "quality_loop" / png_path
                if resolved.exists():
                    sha = _sha256_file(resolved)
            await conn.execute(
                """
                INSERT INTO ref_faces
                    (report_id, page_no, face_index, st_type, role, format, density,
                     mechanism, devices, axes, argument, png_path, sha256, metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT (report_id, page_no, face_index) DO UPDATE SET
                    st_type = EXCLUDED.st_type,
                    role = EXCLUDED.role,
                    format = EXCLUDED.format,
                    density = EXCLUDED.density,
                    mechanism = EXCLUDED.mechanism,
                    devices = EXCLUDED.devices,
                    axes = EXCLUDED.axes,
                    argument = EXCLUDED.argument,
                    sha256 = EXCLUDED.sha256,
                    metadata = EXCLUDED.metadata
                """,
                rep_id, r["page_no"], r["face_index"], r["st_type"], r["role"],
                r["format"], r["density"], r["mechanism"], r["devices"],
                json.dumps(r["axes"]), r["argument"], png_path, sha,
                json.dumps(r["metadata"]),
            )
            inserted += 1
        if verbose:
            print(f"ingested {inserted} faces across {len(reports)} reports")
        return {"reports": len(reports), "faces": inserted}
    finally:
        await conn.close()


async def record_storage_objects(dsn: str, project_url: str, api_key: str,
                                 bucket: str = "references") -> dict:
    """Record which source PDFs are stored in Supabase Storage.

    The PDF binaries live in Storage (bucket `references/source-pdfs/<slug>.pdf`);
    Postgres records the object name + size per report so the pipeline can
    fetch the durable source or fall back to the local raster cache. Skips
    reports whose PDF was NOT uploaded (over the Free-plan limit).
    """
    import base64
    import urllib.parse

    project_ref = project_url.rstrip("/").split("//", 1)[-1].split(".", 1)[0]
    base = f"https://{project_ref}.supabase.co"
    conn = await asyncpg.connect(dsn, timeout=30, statement_cache_size=0)
    try:
        headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}"}
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{base}/storage/v1/object/list/{bucket}",
                headers=headers,
                json={"prefix": "source-pdfs", "limit": 100},
            )
            objects = response.json() if response.status_code == 200 else []
        updated: list[str] = []
        for obj in objects:
            name = obj.get("name") or ""
            if not name.endswith(".pdf") or "/" in name:
                continue
            slug = name.removesuffix(".pdf")
            meta = obj.get("metadata") or {}
            rep_id = await conn.fetchval("SELECT id FROM ref_reports WHERE slug = $1", slug)
            if rep_id is None:
                continue
            await conn.execute(
                """
                UPDATE ref_reports
                SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'),
                        '{storage}',
                        $2::jsonb
                    )
                WHERE id = $1
                """,
                rep_id,
                json.dumps({
                    "object": f"source-pdfs/{name}",
                    "bucket": bucket,
                    "size": meta.get("size"),
                    "mimetype": meta.get("mimetype"),
                }),
            )
            updated.append(slug)
        return {"recorded": updated}
    finally:
        await conn.close()


async def selector_query(dsn: str, st_type: str, *, format_: str | None = None,
                         role: str | None = None, density: str | None = None,
                         exclude_report: str | None = None,
                         k: int = 3) -> list[dict]:
    """Semantic reference selection from the catalog — the Director's selector.

    Filters by st_type (required) + optional format/role/density, ordered by
    how many optional dimensions match (the semantic closeness), then by the
    cached sha256 presence. `exclude_report` drops the client's OWN deck (the
    output being judged is not the reference bar — Richard's hand-designed
    decks are). Returns the top-k faces with their rationale data.
    """
    conn = await asyncpg.connect(dsn, timeout=30, statement_cache_size=0)
    try:
        clauses = ["f.st_type = $1"]
        params: list = [st_type]
        order_bonus: list[str] = []
        if format_:
            params.append(format_)
            clauses.append(f"f.format = ${len(params)}")
            order_bonus.append(f"(f.format = ${len(params)})::int")
        if role:
            params.append(role)
            clauses.append(f"f.role = ${len(params)}")
            order_bonus.append(f"(f.role = ${len(params)})::int")
        if density:
            params.append(density)
            clauses.append(f"f.density = ${len(params)}")
            order_bonus.append(f"(f.density = ${len(params)})::int")
        if exclude_report:
            params.append(exclude_report)
            clauses.append(f"r.slug <> ${len(params)}")
        order_sql = (" + ".join(order_bonus) + " DESC,") if order_bonus else ""
        params.append(k)
        rows = await conn.fetch(
            f"""
            SELECT f.id, r.slug AS report, f.page_no, f.face_index, f.st_type,
                   f.role, f.format, f.density, f.mechanism, f.devices,
                   f.argument, f.png_path, f.sha256
            FROM ref_faces f
            JOIN ref_reports r ON r.id = f.report_id
            WHERE {" AND ".join(clauses)}
            ORDER BY {order_sql} f.sha256 <> '' DESC, f.id
            LIMIT ${len(params)}
            """,
            *params,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def record_director_decision(dsn: str, *, client_slug: str, report_id: str,
                                   face_key: str, st_type: str, ref_face_id: int | None,
                                   rationale: str, visual_job: str,
                                   brief: dict | None = None,
                                   generator_brief: dict | None = None) -> int | None:
    """Persist one Director decision (reference choice + brief) into Supabase.

    Returns the decision id, or None when the DSN is absent (local fallback:
    decisions are not durable but the pipeline still runs).
    """
    if not dsn:
        return None
    conn = await asyncpg.connect(dsn, timeout=30, statement_cache_size=0)
    try:
        if ref_face_id is None:
            return None
        decision_id = await conn.fetchval(
            """
            INSERT INTO director_decisions
                (client_slug, report_id, face_key, st_type, ref_face_id,
                 rationale, visual_job, brief, generator_brief)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            client_slug, report_id, face_key, st_type, ref_face_id,
            rationale, visual_job,
            json.dumps(brief or {}), json.dumps(generator_brief or {}),
        )
        return decision_id
    finally:
        await conn.close()


async def record_render_run(dsn: str, *, client_slug: str, report_id: str,
                            build_id: str, state: str = "started",
                            decisions: list[int] | None = None,
                            review: dict | None = None) -> int | None:
    """Persist one render run (state + review evidence) into Supabase."""
    if not dsn:
        return None
    conn = await asyncpg.connect(dsn, timeout=30, statement_cache_size=0)
    try:
        run_id = await conn.fetchval(
            """
            INSERT INTO render_runs (client_slug, report_id, build_id, state,
                                     decisions, review)
            VALUES ($1,$2,$3,$4,$5,$6)
            RETURNING id
            """,
            client_slug, report_id, build_id, state,
            json.dumps(decisions or []), json.dumps(review or {}),
        )
        return run_id
    finally:
        await conn.close()
