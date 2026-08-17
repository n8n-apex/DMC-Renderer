const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { buildSourceLedger } = require("../source-ledger-node-v3.js");


const VERSIONS = {
  workflow_contract_version: "3.2.1",
  writer_prompt_version: "5.1.1",
  schema_resolver_version: "5.2.1",
  writer_gate_version: "3.1.1",
  source_ledger_version: "3.2.1",
  claim_gate_version: "3.2.1",
};


function executePasteTarget(filename, items) {
  const source = fs.readFileSync(path.resolve(__dirname, "..", filename), "utf8");
  const execute = new Function("$input", "require", "module", source);
  return execute({ all: () => items }, undefined, undefined);
}


function sourceInput() {
  return {
    sources: [{
      source_kind: "document",
      locator: "evidence.txt",
      captured_at: "2026-08-05T09:30:00+05:30",
      rights_status: "client_authorized",
      text: "Die Bearbeitung dauert 20 Minuten.",
      language: "de",
      allowed_uses: ["report"],
    }],
    claims: [{
      key: "duration",
      kind: "direct",
      claim_type: "number",
      value: "20 Minuten",
      source_locator: "evidence.txt",
      verbatim: "20 Minuten",
    }],
  };
}


function assertPreservedAndVersioned(result, original) {
  assert.equal(result.binary, original.binary);
  assert.equal(result.json.correlation_id, original.json.correlation_id);
  for (const [field, version] of Object.entries(VERSIONS)) {
    assert.equal(result.json[field], version, field);
  }
}


test("source-ledger full source executes with n8n $input and no CommonJS globals", () => {
  const original = {
    json: { source_ledger_input: sourceInput(), correlation_id: "corr.source" },
    binary: { evidence: { id: "binary.source" } },
  };

  const [result] = executePasteTarget("source-ledger-node-v3.js", [original]);

  assertPreservedAndVersioned(result, original);
  assert.deepEqual(result.json.source_ledger, buildSourceLedger(sourceInput()));
});


test("claim-gate full source executes with n8n $input and no CommonJS globals", () => {
  const ledger = buildSourceLedger(sourceInput());
  const claimId = ledger.claims[0].claim_id;
  const original = {
    json: {
      source_ledger: ledger,
      parsed_writer_output: { body: "20 Minuten", claim_ids: [claimId] },
      correlation_id: "corr.claim",
    },
    binary: { report: { id: "binary.claim" } },
  };

  const [result] = executePasteTarget("claim-gate-v3.js", [original]);

  assertPreservedAndVersioned(result, original);
  assert.deepEqual(result.json.claim_gate, { pass: true, violations: [] });
});


test("writer-gate full source executes with n8n $input and no CommonJS globals", () => {
  const original = {
    json: {
      parsed_writer_output: { titel: "Klare Abläufe" },
      correlation_id: "corr.writer",
    },
    binary: { report: { id: "binary.writer" } },
  };

  const [result] = executePasteTarget("writer_gate.js", [original]);

  assertPreservedAndVersioned(result, original);
  assert.deepEqual(result.json.writer_gate, {
    pass: true,
    violations: [],
    retry_instruction: null,
  });
});
