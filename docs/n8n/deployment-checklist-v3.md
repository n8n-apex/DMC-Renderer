# n8n v3 deployed workflow parity checklist

Use this checklist after pasting or changing any v3 n8n node. It is read-only
with respect to the deployed workflow. Never export credentials.

1. Open the deployed workflow and record its workflow ID and verification time.
2. Copy the deployed source text for the five authoritative nodes —
   `Section Writer v5`, `Resolve Schema and Build Prompts v5`, `Writer Gate v3`,
   `Source Ledger v3`, and `Claim Gate v3` — into a temporary local
   verification directory.
3. Record each deployed node’s visible name, semantic version, input schema
   version, and output schema version.
4. Hash the copied bytes with SHA-256. Do not normalize line endings, spacing, or
   trailing newlines.
5. Compare node names, versions, schema versions, and hashes with
   `workflow-contract-v3.json` by running `verify_workflow_contract.py`.
6. Construct `workflow_verification_v3` with only `schema_version`,
   `workflow_contract_version`, `artifacts`, and
   `verification_bundle_sha256`. Each artifact contains only its ID, semantic
   version, SHA-256, expected node name, input schema version, and output schema
   version.
7. Compute `verification_bundle_sha256` from canonical sorted compact JSON before
   adding that field.
8. Send one v3 verification request. A mismatch must return HTTP 409 before the
   renderer runs.
9. Confirm the response header `X-DMC-Workflow-Verification-SHA256` equals the
   submitted bundle hash and the same hash appears in the v3 build manifest.
10. Delete the temporary copied node sources after verification if local policy
    requires it. Do not store API keys, n8n credentials, session cookies, or
    credential object IDs in the bundle or repository.

`POST /render` does not use this handshake. The legacy route remains isolated
until the migration decision is approved.
