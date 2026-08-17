# Source ledger and claim gate wiring v3

Build the source ledger once before prose generation, then keep the same ledger
on every chapter item:

```text
raw client evidence
  -> Source Ledger v3
  -> scoped evidence and permitted claim IDs
  -> Section Writer v5 (German output)
  -> Parse Writer Response
  -> Claim Gate v3
  -> Writer Gate v3
  -> fail or retry when either gate is false
  -> report envelope
```

`runSourceLedgerNode` reads `$json.source_ledger_input` (or the item's top-level
`sources` and `claims`), preserves the complete item, and attaches the canonical
`source_ledger` plus all six workflow versions:

```js
return runSourceLedgerNode({ json: $json, binary: $binary });
```

The ledger contains stable source and claim IDs, exact source spans, and explicit
computation records. Store it unchanged with the report build. For each chapter,
pass only permitted claim IDs and exact excerpts to the writer.

After `Parse Writer Response`, `runClaimGateNode` consumes
`$json.source_ledger` and `$json.parsed_writer_output`. Similar raw text is not
approval. Numbers, quotes, credentials, certifications, and named outcomes must
carry an existing exact claim ID whose type and normalized value support the
assertion. Missing inputs, malformed or unknown claim IDs, prior failures, and
unsupported assertions all return a failing `claim_gate` result.

Run the writer copy gate only after the claim gate. Continue only when both
`$json.claim_gate.pass` and `$json.writer_gate.pass` are true. Retry at most
twice, then surface the violations and stop the run.
