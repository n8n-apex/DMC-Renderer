"""Resumable upload of the reference PDFs to Supabase Storage.

Uses Supabase Storage's TUS endpoint because the APEX source PDF is ~721 MB;
the normal object upload is intended for small files. Credentials come only
from environment variables and are never logged.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[2]
BUCKET = "references"
CHUNK_SIZE = 8 * 1024 * 1024
# Supabase Free plan caps each stored object at 50 MB (verified 413/limits).
# APEX (721 MB) and Boss (77 MB) exceed it — the catalog holds their metadata
# + rasters instead; the PDF binaries are skipped by design.
MAX_OBJECT_BYTES = 50 * 1024 * 1024
PDFS = {
    "niklas": "Niklas Niemeyer DMC-Report Druckfertig (1).pdf",
    "buchagentur": "Buchagentur DMC-Report (1).pdf",
    "werkzeugkoffer": "DMC-Report Mein_Werkzeugkoffer.pdf",
    "aerztepartner": "aerztepartner_v0.2 (1).pdf",
}


def _b64(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def _storage_base(project_url: str) -> str:
    project_ref = project_url.rstrip("/").split("//", 1)[-1].split(".", 1)[0]
    return f"https://{project_ref}.storage.supabase.co/storage/v1"


def upload_file(client: httpx.Client, *, project_url: str, object_key: str,
                source: Path, bucket: str = BUCKET, api_key: str | None = None) -> dict:
    """Upload one PDF to the references bucket via TUS.

    `object_key` is the SLUG (e.g. 'niklas'); the Supabase API key comes from
    SUPABASE_SERVICE_ROLE_KEY (env) unless overridden — never conflated.
    """
    api_key = api_key or os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    endpoint = f"{_storage_base(project_url)}/upload/resumable"
    object_name = f"source-pdfs/{object_key}.pdf"
    size = source.stat().st_size
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Tus-Resumable": "1.0.0",
        "Upload-Length": str(size),
        "Upload-Metadata": ",".join(
            f"{name} {_b64(value)}"
            for name, value in (
                ("bucketName", bucket),
                ("objectName", object_name),
                ("contentType", "application/pdf"),
                ("cacheControl", "31536000"),
            )
        ),
        "x-upsert": "true",
    }
    created = client.post(endpoint, headers=headers, timeout=120)
    created.raise_for_status()
    location = created.headers.get("Location") or created.headers.get("location")
    if not location:
        raise RuntimeError(f"TUS create returned no upload location for {object_key}")
    if location.startswith("/"):
        location = _storage_base(project_url) + location

    offset = int(created.headers.get("Upload-Offset", "0"))
    with source.open("rb") as fh:
        fh.seek(offset)
        while offset < size:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                raise RuntimeError(f"source ended early for {object_key}: {offset}/{size}")
            patch_headers = {
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
                "Tus-Resumable": "1.0.0",
                "Upload-Offset": str(offset),
                "Content-Type": "application/offset+octet-stream",
            }
            response = client.patch(location, headers=patch_headers, content=chunk, timeout=300)
            response.raise_for_status()
            next_offset = int(response.headers.get("Upload-Offset", str(offset + len(chunk))))
            if next_offset <= offset:
                raise RuntimeError(f"TUS offset did not advance for {object_key}")
            offset = next_offset
            fh.seek(offset)
    return {"object_key": object_name, "bytes": size}


def main() -> None:
    project_url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    with httpx.Client(follow_redirects=True) as client:
        for slug, filename in PDFS.items():
            source = ROOT / filename
            size = source.stat().st_size
            if size > MAX_OBJECT_BYTES:
                print(f"SKIP {slug}: {size / 1e6:.1f} MB exceeds the 50 MB Free-plan limit")
                continue
            result = upload_file(
                client,
                project_url=project_url,
                object_key=slug,
                source=source,
            )
            print(f"uploaded {result['object_key']}: {result['bytes'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
