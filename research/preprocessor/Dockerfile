# DMC pre-processor (Layer 1) — container image.
#
# Base = the official Playwright Python image, which BAKES IN Chromium and
# all the system libraries it needs (libnss3, libatk, fonts, etc.). This is
# why we don't need `playwright install --with-deps` or a long apt-get list.
# The tag MUST match the playwright version in requirements.txt (1.60).
FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

WORKDIR /app

# 1) Python deps first so this layer caches when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Ensure the Chromium build matching this Playwright version is present
#    (idempotent — already in the base image, fast no-op if so).
RUN playwright install chromium

# 3) App code.
COPY . .

# Railway (and most PaaS) inject $PORT at runtime; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# Env vars (OPENROUTER_API_KEY, OPENROUTER_VISION_MODEL,
# REPORT_GENERATOR_WEBHOOK, optional ONBOARD_OUTPUT_DIR) are provided by the
# platform's variable store at runtime — NOT copied into the image.
#
# NOTE: /onboard needs no on-disk fonts. /render's Stage 2 resolves chassis
# fonts from ../v7-renderer/fonts — if you deploy /render from this image,
# also COPY that fonts directory in, or mount it.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
