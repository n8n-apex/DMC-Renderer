"""Typed runtime configuration (pydantic-settings).

Replaces scattered os.getenv() reads with one validated object injected
via FastAPI Depends. Secrets are SecretStr so they never appear in logs
or error reprs. Env-var names are UNCHANGED from the prior os.getenv
calls, so behaviour is identical. Reads PROCESS ENV ONLY (the deployment
supplies keys via exported env / uvicorn --env-file); `.env` is NOT
auto-loaded here, so the test suite stays hermetic. Pure infrastructure —
no client literal.
"""
from __future__ import annotations

from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
    )

    # ── external-service credentials (masked) ──
    openrouter_api_key: Optional[SecretStr] = None
    fal_key: Optional[SecretStr] = None

    # ── model slugs (env-swappable; defaults == the prior literals) ──
    openrouter_vision_model: str = "anthropic/claude-sonnet-4.6"
    openrouter_brief_model: str = "anthropic/claude-opus-4.6"
    openrouter_prompt_model: str = "anthropic/claude-sonnet-4.6"
    # the "editor" tier — condensing dense copy is a judgement task → Opus.
    openrouter_restructure_model: str = "anthropic/claude-opus-4.6"
    restructure_cache_dir: str = "var/restructure_cache"
    fal_image_model: str = "fal-ai/nano-banana-pro"
    fal_image_resolution: str = "2K"

    # ── timeouts / pooling ──
    http_timeout_s: float = 30.0
    http_max_connections: int = 20

    # ── asset budget + cache (load-bearing in Phase 3) ──
    max_generations_per_report: int = 12
    asset_cache_dir: str = "var/asset_cache"

    # ── local client-assets folder (Drive substitute; Phase 4a) ──
    client_assets_dir: str = "client_assets"

    # ── webhook / output dirs ──
    report_generator_webhook: Optional[str] = None
    onboard_output_dir: Optional[str] = None

    # ── artifact delivery (US-2026-08-19: n8n outtake) ──
    # The ship path uploads the finished PDF + the editable IDML ZIP to a
    # shared file host and delivers the PUBLIC download URLs in the webhook
    # payload (so n8n can fill an Airtable row or email Richard's people with
    # the files). `artifact_upload_url` is the host's accept endpoint (a
    # multipart PUT/POST that stores the file and returns its public URL);
    # `artifact_public_base` is what public URLs are built from when the host
    # returns a relative path. Uploading is best-effort: when either is unset
    # or the host is unreachable, the payload falls back to the local
    # artifact paths (never crashes the ship).
    artifact_upload_url: Optional[str] = None
    artifact_public_base: Optional[str] = None

    # ── Supabase reference catalog (weekly-synced; the QA/Director corpus) ──
    supabase_pooler_url: Optional[SecretStr] = None
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[SecretStr] = None
    # internal maintenance cadence (seconds): the app-triggered weekly sync.
    supabase_sync_interval_seconds: int = 7 * 24 * 3600   # 7 days
    supabase_sync_check_seconds: int = 6 * 3600           # loop wake-up

    def supabase_pooler_url_str(self) -> Optional[str]:
        return (
            self.supabase_pooler_url.get_secret_value()
            if self.supabase_pooler_url
            else None
        )

    def supabase_service_role_key_str(self) -> Optional[str]:
        return (
            self.supabase_service_role_key.get_secret_value()
            if self.supabase_service_role_key
            else None
        )

    def openrouter_key_str(self) -> Optional[str]:
        return (
            self.openrouter_api_key.get_secret_value()
            if self.openrouter_api_key
            else None
        )

    def fal_key_str(self) -> Optional[str]:
        return self.fal_key.get_secret_value() if self.fal_key else None
