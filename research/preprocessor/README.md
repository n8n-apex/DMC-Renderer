# preprocessor — Layer 1

FastAPI service that prepares a render package for the Layer 2 chassis at `../v7-renderer/`. Receives raw Airtable data from n8n, validates/resolves/assembles, returns a render result. The chassis is brand-agnostic; this service is where intelligence lives.

## Phase A scope (current)

- `POST /render` — Stage 1 (validate input) + Stage 2 (resolve fonts). Returns a resolved `brand_tokens` dict matching the chassis's flat 10-field `BrandConfig` shape, plus a `font_config` block. No AI calls, no rendering, no file I/O.
- `POST /onboard` — stub returning `{"status": "not_implemented"}`. Phase F.

## Setup

```bash
cd research/preprocessor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Test

```bash
python -m pytest tests/ -v
```

## Run

```bash
uvicorn main:app --port 8000 --reload
```

## Verify

```bash
curl -X POST http://localhost:8000/render \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_render_request.json
```

Returns a JSON body with `validated_brand_tokens` (10 flat fields), `font_config`, `errors`, `warnings`, and a top-level `status`.

## Boundaries (Phase A)

- Read-only on the chassis (`../v7-renderer/`), the grammar, Richard's files, and the matrix.
- Pre-processor is its own venv (`research/preprocessor/.venv/`), separate from chassis.
- Does NOT call AI APIs (Phase E), does NOT generate SVG components (Phase D), does NOT render PDFs (Phase B integration), does NOT post-process (Phase G).

## Input-driven principle

This service receives data and transforms it. No client name appears in the logic. Brand-agnostic. Hue-agnostic. The regression test `test_no_client_name_in_logic` scans the production source on every test run.
