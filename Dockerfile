# dmc-renderer: envelope -> print-ready PDF service (P3 deploy).
# Build from the REPO ROOT (the image needs dmc-renderer/ + research/v7-renderer/
# + research/preprocessor/):
#   docker build -t dmc-renderer .
#   docker run --rm -p 8099:8099 dmc-renderer
# Optional keys (copy-fit / image generation) pass through at run time:
#   docker run -e OPENROUTER_API_KEY=... -e FAL_KEY=... -p 8099:8099 dmc-renderer
FROM python:3.11-slim-bookworm

# System deps:
#   - WeasyPrint 68.1 runtime libs (pango/cairo/gdk-pixbuf/glib + shared-mime-info)
#   - ghostscript: the Layer-3 transparency FLATTEN pass after Chromium print
#   - fonts: none needed from apt; the brand faces ship in research/v7-renderer/fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
      libffi8 shared-mime-info ghostscript poppler-utils curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first (layer-cached), then the Playwright Chromium ship engine
# (--with-deps pulls its own apt libs).
COPY dmc-renderer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && playwright install --with-deps chromium

# The three code roots the service imports across, plus the source-of-truth
# grammar file the renderer's grammar_loader reads from the repo root
# (renderer_root/../../richard-grammar-v2.md -> /app/richard-grammar-v2.md).
COPY dmc-renderer/ /app/dmc-renderer/
COPY research/v7-renderer/ /app/research/v7-renderer/
COPY research/preprocessor/ /app/research/preprocessor/
# Stage-9 reference QC: the perception/rubric loop + the classified 84-page
# Richard reference corpus it grades against. The service runs it on EVERY deck.
COPY research/quality_loop/ /app/research/quality_loop/
# V3 composition, policy, reference, and export dependencies imported by
# build_v3.py after the precomposition package is frozen.
COPY research/composition_registry/ /app/research/composition_registry/
COPY research/reference-atlas/ /app/research/reference-atlas/
COPY research/postprocessor/ /app/research/postprocessor/
COPY research/design_policy/ /app/research/design_policy/
# Build-record schema + atomic artifact store (Task 4). Retained builds land
# under DMC_V3_ARTIFACT_ROOT (mount a volume there in real deployments);
# local runs/ never enter the image (.dockerignore).
COPY research/artifacts/ /app/research/artifacts/
# The workflow contract and its five immutable paste targets are retained in
# the image so /health/v3 can verify their exact deployed bytes.
COPY docs/writer-prompt-v5.md /app/docs/writer-prompt-v5.md
COPY docs/resolve-schema-node-v5.js /app/docs/resolve-schema-node-v5.js
COPY docs/n8n/writer_gate.js /app/docs/n8n/writer_gate.js
COPY docs/n8n/source-ledger-node-v3.js /app/docs/n8n/source-ledger-node-v3.js
COPY docs/n8n/claim-gate-v3.js /app/docs/n8n/claim-gate-v3.js
COPY docs/n8n/workflow-contract-v3.json /app/docs/n8n/workflow-contract-v3.json
COPY richard-grammar-v2.md /app/richard-grammar-v2.md
# Client assets (founder portrait, product mockups): the repo-local door the
# product router + founder slots resolve from (build_live defaults to
# <dmc-renderer>/../client_assets = /app/client_assets in-image; override with
# DMC_CLIENT_ASSETS_DIR + a volume for per-client swaps). Without this layer
# the container silently rendered every deck with NO client imagery.
COPY client_assets/ /app/client_assets/

# Point the service at the in-image roots (same code, env-switched paths).
ENV DMC_RENDERER_ROOT=/app/research/v7-renderer \
    DMC_PREPROC_ROOT=/app/research/preprocessor \
    PYTHONUNBUFFERED=1

EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD curl -fsS http://127.0.0.1:8099/health || exit 1

CMD ["python", "-m", "uvicorn", "service:app", "--app-dir", "/app/dmc-renderer", \
     "--host", "0.0.0.0", "--port", "8099"]
