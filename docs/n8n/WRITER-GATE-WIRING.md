# German-direct writer and gate wiring v3

The executable order is fixed:

```text
raw client evidence
  -> Source Ledger v3
  -> Section Writer v5 (German output)
  -> Parse Writer Response
  -> Claim Gate v3
  -> Writer Gate v3
  -> IF both gates pass
       true  -> continue
       false -> append retry instruction to Section Writer v5
                (maximum 2 retries, then fail the run loudly)
```

The writer returns German JSON values directly. `Parse Writer Response` must
produce `parsed_writer_output` before either gate runs. The writer attaches the
exact source-ledger `claim_ids` at the root or nearest nested content object.

Run the adapters in n8n Code nodes set to **Run Once for Each Item**:

```js
return runClaimGateNode({ json: $json, binary: $binary });
```

```js
return runWriterGateNode({ json: $json, binary: $binary });
```

`runClaimGateNode` reads `$json.source_ledger` and
`$json.parsed_writer_output`, preserves the item, and writes
`$json.claim_gate`. It fails closed when either input is absent, when a prior
gate already failed, or when a risky assertion lacks an exact supporting claim
ID.

`runWriterGateNode` reads `$json.parsed_writer_output`, preserves the item, and
writes `$json.writer_gate`. It checks German language and deterministic copy
law only: dashes, prose colons, banned vocabulary, hedging, the forbidden
negation-plus-`sondern` construction, and the word `Euro`. Evidence authority
belongs to Claim Gate v3.

The IF condition is:

```text
{{ $json.claim_gate.pass && $json.writer_gate.pass }}
```

On failure, append the writer gate's `retry_instruction` plus the structured
claim-gate violations to the next writer request. Never continue when either
gate is missing or false. All three adapters reassert the canonical six workflow
versions on the item.
