# Real legacy migrations (review-only)

This directory holds the v3 migration records for the two real legacy reports:

- `jousef-source-envelope.json`: migrated from
  `dmc-renderer/fixtures/apex_consulting_payload.json` (report pointer `$.payload`)
- `christopher-source-envelope.json`: migrated from
  `dmc-renderer/fixtures/christoph_v5_payload.json` (report pointer `$`)
- `reports/`: human-readable migration reports for each record

Each envelope is the exact serialized `MigrationRecord` produced by
`research/migrations/legacy_report_v3.py` (`build_migration_record`). The test
suites in `research/migrations/tests/` rebuild the record from the original
payload on every run and compare it to these files, so the envelopes can never
drift from the code or the originals.

## What these fixtures are

They are honest inventories of what the legacy payloads actually contain:
the original bytes pinned by SHA-256, every source reference preserved
verbatim, an explicit 20-face editorial map (never derived from legacy page
ranges), the full case-candidate pool, and a typed blocker for everything
unresolved. The migrated `sources`, `claims`, and `assets` lists are empty
because nothing in a rendered legacy payload is grounded, span-verified, or
rights-cleared.

## What they are NOT

These records are review-only. They are not renderable, not approved, and not
inputs for any release build. Feeding them into the v3 precomposition pipeline
raises `PrecompositionBlocked` by design.

## Unresolved human gates

Two gates in particular can only be closed by a human, never by code:

1. **Rights**: every source reference and portrait carries rights_status
   `unknown`. A human must resolve rights for each one; no rights were
   invented during migration.
2. **Case selection**: the legacy reports carry five case studies each; the
   v3 house structure carries exactly three. `case_selection` stays `pending`
   with all candidates listed until a human owner chooses.

Do not edit these files by hand. Regenerate them by running the migration
after any intentional change to the migration code, and let the tests verify
the result.
