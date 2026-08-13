# Ralph Agent Instructions

You are an autonomous coding agent working on a software project.

## THIS PROJECT (DMC Report Generator) - READ FIRST

Repo root: `/Users/utkarsh/Projects/richard` (this is a git repo now; the plan's branch is checked out).

Authoritative plan: `docs/superpowers/plans/2026-08-13-consolidated-gap-closure.md` - read the gap register and your story's task section BEFORE implementing. The story's `notes`/`acceptanceCriteria` name the task.

### Environments (three separate venvs - do NOT mix them)
- **Renderer** (research/v7-renderer): `cd /Users/utkarsh/Projects/richard/research/v7-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q`
- **Preprocessor** (research/preprocessor): `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests -q`
- **dmc-renderer** (uses the renderer venv): `cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q`

`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` is REQUIRED for Chromium/WeasyPrint on macOS.

### Fast guard battery (do this before claiming design work done)
```bash
cd /Users/utkarsh/Projects/richard/research/v7-renderer
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest \
  tests/test_components.py tests/test_tokens.py tests/test_design_conformance.py \
  tests/test_no_literals_in_architecture.py -q
```

### HARD RULES (do not break)
- **No fabrication, ever.** Every figure a device shows must appear verbatim in that page's own copy (see `research/v7-renderer/fixtures/apex/viz_curation.py::_figure_grounded` - it deliberately EXCLUDES `data['viz']` from evidence). Never weaken or bypass it.
- **No client literals, no raw hex, no em dashes (U+2014)** in `templates/`, `styles/`, `patterns/`, `components/`, or `dmc-renderer/*.py` LOGIC. Client names/numbers live in fixtures only. A raw hex or client name in a MULTI-LINE comment still trips the guard.
- **Never weaken a guard or gate to make a test pass.** Fix the drifted side (stale test or stale fixture expectation).
- **"Pre-existing failure" is a claim to verify, not an excuse.** If a test fails, find the actual root cause.
- **box-shadow is banned on viz** (test_viz_flat_on_cream). Use hairline border + surface fill.
- Undefined CSS vars void whole declarations: the real type tiers are `--type-stat-xl` 60pt, `--type-stat` 40pt, `--type-display` 32pt, `--type-signature` 28pt, `--type-h2` 20pt, `--type-pullquote` 18pt, `--type-h3` 14pt. There is NO `--type-h1`.
- `NO git history` means the previous project docs said this was not a git repo - that is now FALSE, git is initialized. Never claim otherwise.

### Verification standard
- **Verify on PIXELS for visual changes**: render the deck, read the page PNG, compare to the reference (see plan). Markup assertions alone are not proof.
- After any layout/size/CSS change, confirm physical==logical page count on `report_print.pdf` (`fitz.open(...).page_count`) - the deck is one flowing document and a +1 change can cascade to +6.
- A "passed test count" is not the deliverable. The artifact (a rendered page, a suite going 0-failed) is.

## Your Task

1. Read the PRD at `prd.json` (in the same directory as this file)
2. Read the progress log at `progress.txt` (check Codebase Patterns section first)
3. Check you're on the correct branch from PRD `branchName`. If not, check it out or create from main.
4. Pick the **highest priority** user story where `passes: false`
5. Implement that single user story
6. Run quality checks (e.g., typecheck, lint, test - use whatever your project requires)
7. Update CLAUDE.md files if you discover reusable patterns (see below)
8. If checks pass, commit ALL changes with message: `feat: [Story ID] - [Story Title]`
9. Update the PRD to set `passes: true` for the completed story
10. Append your progress to `progress.txt`

## Progress Report Format

APPEND to progress.txt (never replace, always append):
```
## [Date/Time] - [Story ID]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns discovered (e.g., "this codebase uses X for Y")
  - Gotchas encountered (e.g., "don't forget to update Z when changing W")
  - Useful context (e.g., "the evaluation panel is in component X")
---
```

The learnings section is critical - it helps future iterations avoid repeating mistakes and understand the codebase better.

## Consolidate Patterns

If you discover a **reusable pattern** that future iterations should know, add it to the `## Codebase Patterns` section at the TOP of progress.txt (create it if it doesn't exist). This section should consolidate the most important learnings:

```
## Codebase Patterns
- Example: Use `sql<number>` template for aggregations
- Example: Always use `IF NOT EXISTS` for migrations
- Example: Export types from actions.ts for UI components
```

Only add patterns that are **general and reusable**, not story-specific details.

## Update CLAUDE.md Files

Before committing, check if any edited files have learnings worth preserving in nearby CLAUDE.md files:

1. **Identify directories with edited files** - Look at which directories you modified
2. **Check for existing CLAUDE.md** - Look for CLAUDE.md in those directories or parent directories
3. **Add valuable learnings** - If you discovered something future developers/agents should know:
   - API patterns or conventions specific to that module
   - Gotchas or non-obvious requirements
   - Dependencies between files
   - Testing approaches for that area
   - Configuration or environment requirements

**Examples of good CLAUDE.md additions:**
- "When modifying X, also update Y to keep them in sync"
- "This module uses pattern Z for all API calls"
- "Tests require the dev server running on PORT 3000"
- "Field names must match the template exactly"

**Do NOT add:**
- Story-specific implementation details
- Temporary debugging notes
- Information already in progress.txt

Only update CLAUDE.md if you have **genuinely reusable knowledge** that would help future work in that directory.

## Quality Requirements

- ALL commits must pass your project's quality checks (typecheck, lint, test)
- Do NOT commit broken code
- Keep changes focused and minimal
- Follow existing code patterns

## Browser Testing (If Available)

For any story that changes UI, verify it works in the browser if you have browser testing tools configured (e.g., via MCP):

1. Navigate to the relevant page
2. Verify the UI changes work as expected
3. Take a screenshot if helpful for the progress log

If no browser tools are available, note in your progress report that manual browser verification is needed.

## Stop Condition

After completing a user story, check if ALL stories have `passes: true`.

If ALL stories are complete and passing, reply with:
<promise>COMPLETE</promise>

If there are still stories with `passes: false`, end your response normally (another iteration will pick up the next story).

## Important

- Work on ONE story per iteration
- Commit frequently
- Keep CI green
- Read the Codebase Patterns section in progress.txt before starting
