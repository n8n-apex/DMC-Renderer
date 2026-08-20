"""Artifact delivery for the n8n outtake (US-2026-08-19).

After a shipped report job, the finished PDF + the editable IDML ZIP (the
deliverable Richard's people open in InDesign) are uploaded to a shared file
host. The job's webhook payload then carries the PUBLIC download URLs, so n8n
can populate an Airtable row or attach the files to an email.

Two independent pieces:
  * ``upload_artifacts`` — best-effort multipart upload of the PDF + IDML ZIP
    to ``upload_url`` (the host's accept endpoint). Returns a URL per file.
  * ``build_idml_delivery`` — runs the renderer's ``--export-idml`` path to
    produce the IDML + Links/ + the mail-ready ZIP, then uploads it.

Both are strictly best-effort: a missing IDML, an unset host, or an unreachable
endpoint NEVER crashes the ship (the payload falls back to local paths).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("artifact_delivery")

# The multipart file field the file host's accept endpoint expects.
_UPLOAD_FIELD = "file"


@dataclass
class ArtifactDelivery:
    """The deliverable set for one shipped report."""

    pdf_path: Optional[Path] = None
    idml_zip_path: Optional[Path] = None
    # public download URLs (when the host accepted the uploads)
    pdf_url: Optional[str] = None
    idml_zip_url: Optional[str] = None
    # local paths preserved (fallback when upload is unavailable)
    local_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _upload_one(
    client: Callable[[str, dict], object],
    path: Path,
    upload_url: str,
    public_base: str,
) -> Optional[str]:
    """Upload one file via ``client`` (post_fn-shaped; injectable for tests).

    Returns the public download URL or None on failure. ``client`` is the
    httpx.POST-like callable (path, files) -> response with .status_code and
    optional .json()/text for the returned URL.
    """
    if not path or not path.exists():
        return None
    with open(path, "rb") as fh:
        try:
            resp = client(
                upload_url,
                {"files": (path.name, fh)},
            )
            if getattr(resp, "status_code", None) is not None and resp.status_code >= 400:
                logger.warning("upload %s -> HTTP %s", path.name, resp.status_code)
                return None
            # the host may return a JSON {url} or a plain-text URL
            url = None
            try:
                data = resp.json()
                if isinstance(data, dict):
                    url = data.get("url") or data.get("public_url") or data.get("path")
            except Exception:
                txt = getattr(resp, "text", "")
                url = txt.strip() if txt and txt.startswith(("http", "/")) else None
            if url:
                if url.startswith("/"):
                    base = public_base.rstrip("/")
                    url = f"{base}{url}"
                return url
        except Exception as exc:  # noqa: BLE001 -- best-effort upload
            logger.warning("upload %s failed: %s", path.name, exc)
    return None


def upload_artifacts(
    *,
    pdf_path: Optional[Path],
    idml_zip_path: Optional[Path],
    upload_url: Optional[str],
    public_base: Optional[str],
    client: Optional[Callable[[str, dict], object]] = None,
) -> ArtifactDelivery:
    """Upload the PDF + IDML ZIP (when present) to the file host.

    ``client`` defaults to an httpx POST; injectable for tests. Best-effort.
    """
    import httpx  # local import: only needed on the real path

    if not upload_url or not public_base:
        return ArtifactDelivery(
            pdf_path=pdf_path, idml_zip_path=idml_zip_path,
            local_paths=[str(p) for p in (pdf_path, idml_zip_path) if p],
        )

    client = client or (
        lambda url, files: httpx.post(url, files=files, timeout=120.0)
    )

    deliv = ArtifactDelivery(pdf_path=pdf_path, idml_zip_path=idml_zip_path)
    if pdf_path:
        deliv.pdf_url = _upload_one(client, pdf_path, upload_url, public_base)
        if not deliv.pdf_url:
            deliv.local_paths.append(str(pdf_path))
            deliv.errors.append("pdf upload failed")
    if idml_zip_path:
        deliv.idml_zip_url = _upload_one(client, idml_zip_path, upload_url, public_base)
        if not deliv.idml_zip_url:
            deliv.local_paths.append(str(idml_zip_path))
            deliv.errors.append("idml zip upload failed")
    return deliv


def build_idml_delivery(
    *,
    package_dir: Path,
    renderer_dir: Path,
    out_dir: Path,
    upload_url: Optional[str],
    public_base: Optional[str],
    client: Optional[Callable[[str, dict], object]] = None,
) -> ArtifactDelivery:
    """Build the mail-ready IDML ZIP and upload it (best-effort)."""
    deliv = ArtifactDelivery()
    try:
        tmp = Path(tempfile.mkdtemp(prefix="dmc_idml_"))
        import sys
        sys.path.insert(0, str(renderer_dir))
        from export_idml import export_idml, package_delivery  # type: ignore

        pkg_json = package_dir / "resolved_package.json"
        idml = export_idml(pkg_json, tmp / "report", assets_dir=package_dir / "assets")
        zip_out = tmp / "ApexReport_InDesign.zip"
        extra = [
            out_dir / "report.pdf",
        ] if (out_dir / "report.pdf").exists() else []
        zip_out = package_delivery(idml, zip_out, extra_files=extra)
        deliv.idml_zip_path = Path(zip_out)
        # upload the zip + the already-rendered PDF together
        uploaded = upload_artifacts(
            pdf_path=out_dir / "report.pdf" if (out_dir / "report.pdf").exists() else None,
            idml_zip_path=deliv.idml_zip_path,
            upload_url=upload_url, public_base=public_base, client=client,
        )
        return uploaded
    except Exception as exc:  # noqa: BLE001 -- never crash the ship
        logger.warning("idml delivery failed: %s", exc)
        deliv.errors.append(str(exc))
        deliv.idml_zip_path = None
        if (out_dir / "report.pdf").exists():
            deliv.pdf_path = out_dir / "report.pdf"
            deliv.local_paths.append(str(out_dir / "report.pdf"))
        return deliv


def _cleanup(zip_path: Optional[Path]) -> None:
    """Best-effort cleanup of the temp IDML/zip dir."""
    if zip_path:
        try:
            shutil.rmtree(zip_path.parent, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass
