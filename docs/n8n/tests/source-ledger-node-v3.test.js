const test = require("node:test");
const assert = require("node:assert/strict");

const {
  WORKFLOW_VERSIONS_V3,
  buildSourceLedger,
  runSourceLedgerNode,
  sha256,
} = require("../source-ledger-node-v3.js");


function input() {
  return {
    sources: [
      {
        source_kind: "interview",
        locator: "client-interview.txt",
        captured_at: "2026-08-05T09:30:00+05:30",
        rights_status: "client_authorized",
        text: "Die Bearbeitung sank von 120 auf 20 Minuten. TÜV geprüft.",
        language: "de",
        allowed_uses: ["report", "quotation"],
      },
    ],
    claims: [
      {
        key: "start-time",
        kind: "direct",
        claim_type: "number",
        value: "120 Minuten",
        source_locator: "client-interview.txt",
        verbatim: "120",
        confidence: 0.98,
        allowed_uses: ["body", "chart"],
      },
      {
        key: "end-time",
        kind: "direct",
        claim_type: "number",
        value: "20 Minuten",
        source_locator: "client-interview.txt",
        verbatim: "20",
        confidence: 0.99,
        allowed_uses: ["body", "chart"],
      },
      {
        key: "time-saved",
        kind: "computed",
        claim_type: "number",
        operation: "difference",
        formula: "start-time - end-time",
        operand_keys: ["start-time", "end-time"],
        value: "100 Minuten",
        confidence: 0.97,
        allowed_uses: ["body", "chart"],
      },
      {
        key: "credential",
        kind: "direct",
        claim_type: "credential",
        value: "TÜV geprüft",
        source_locator: "client-interview.txt",
        verbatim: "TÜV geprüft",
        confidence: 1,
        allowed_uses: ["body"],
      },
      {
        key: "quote",
        kind: "direct",
        claim_type: "quote",
        value: "Die Bearbeitung sank von 120 auf 20 Minuten.",
        source_locator: "client-interview.txt",
        verbatim: "Die Bearbeitung sank von 120 auf 20 Minuten.",
        confidence: 1,
        allowed_uses: ["quotation"],
      },
    ],
  };
}


function computationInput(left, right, result) {
  const text = `${left} | ${right}`;
  return {
    sources: [
      {
        source_kind: "document",
        locator: "numbers.txt",
        captured_at: "2026-08-05T09:30:00+05:30",
        rights_status: "client_authorized",
        text,
        language: "de",
        allowed_uses: ["report"],
      },
    ],
    claims: [
      {
        key: "left",
        kind: "direct",
        claim_type: "number",
        value: left,
        source_locator: "numbers.txt",
        verbatim: left,
      },
      {
        key: "right",
        kind: "direct",
        claim_type: "number",
        value: right,
        source_locator: "numbers.txt",
        verbatim: right,
      },
      {
        key: "result",
        kind: "computed",
        claim_type: "number",
        operation: "difference",
        formula: "left - right",
        operand_keys: ["left", "right"],
        value: result,
      },
    ],
  };
}


function multiOperandComputationInput(operation, operands, result) {
  const text = operands.join(" | ");
  return {
    sources: [{
      source_kind: "document",
      locator: "numbers.txt",
      captured_at: "2026-08-05T09:30:00+05:30",
      rights_status: "client_authorized",
      text,
      language: "de",
      allowed_uses: ["report"],
    }],
    claims: [
      ...operands.map((value, index) => ({
        key: `operand-${index}`,
        kind: "direct",
        claim_type: "number",
        value,
        source_locator: "numbers.txt",
        verbatim: value,
      })),
      {
        key: "result",
        kind: "computed",
        claim_type: "number",
        operation,
        operand_keys: operands.map((_, index) => `operand-${index}`),
        value: result,
      },
    ],
  };
}


test("source ledger emits only canonical top-level and source fields", () => {
  const ledger = buildSourceLedger(input());

  assert.deepEqual(Object.keys(ledger).sort(), ["claims", "schema_version", "sources"]);
  assert.deepEqual(Object.keys(ledger.sources[0]).sort(), [
    "allowed_uses",
    "captured_at",
    "content_hash",
    "language",
    "locator",
    "rights_status",
    "source_id",
    "source_kind",
    "verbatim_text",
  ]);
  assert.equal(ledger.sources[0].source_kind, "interview");
  assert.equal(ledger.sources[0].rights_status, "client_authorized");
  assert.match(ledger.sources[0].content_hash, /^[0-9a-f]{64}$/);
});


test("portable SHA-256 matches canonical ASCII and UTF-8 vectors", () => {
  assert.equal(
    sha256("abc"),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
  assert.equal(
    sha256("TÜV geprüft."),
    "84411ed1c7de21ad6869f35d74fd0dfd7218afa999a73d7bf1512bee9fa69aaf",
  );
});


test("source ledger produces stable IDs and exact source spans", () => {
  const first = buildSourceLedger(input());
  const second = buildSourceLedger(input());

  assert.deepEqual(first, second);
  assert.match(first.sources[0].source_id, /^source\.[0-9a-f]{16}$/);
  for (const claim of first.claims.filter((item) => item.computation === null)) {
    assert.equal(claim.source_spans.length, 1);
    const span = claim.source_spans[0];
    assert.equal(
      first.sources[0].verbatim_text.slice(span.start, span.end),
      span.verbatim,
    );
  }
});


test("claims emit canonical fields and explicit claim types", () => {
  const ledger = buildSourceLedger(input());

  for (const claim of ledger.claims) {
    assert.deepEqual(Object.keys(claim).sort(), [
      "allowed_uses",
      "claim_id",
      "claim_type",
      "computation",
      "confidence",
      "normalized_value",
      "source_ids",
      "source_spans",
    ]);
  }
  assert.deepEqual(
    ledger.claims.map((claim) => claim.claim_type),
    ["number", "number", "number", "credential", "quote"],
  );
});


test("computed claim declares only its formula and operands and recomputes its value", () => {
  const ledger = buildSourceLedger(input());
  const computed = ledger.claims.find((claim) => claim.computation !== null);

  assert.equal(computed.normalized_value, "100 Minuten");
  assert.deepEqual(Object.keys(computed.computation).sort(), ["formula", "operand_claim_ids"]);
  assert.equal(computed.computation.formula, "start-time - end-time");
  assert.equal(computed.computation.operand_claim_ids.length, 2);
});


test("computed claims parse dot decimals without treating the dot as a thousands separator", () => {
  const ledger = buildSourceLedger(computationInput("3.5", "1.25", "2.25"));

  assert.equal(ledger.claims[2].normalized_value, "2.25");
});


test("computed claims parse German comma decimals", () => {
  const ledger = buildSourceLedger(computationInput("3,5", "1,25", "2,25"));

  assert.equal(ledger.claims[2].normalized_value, "2,25");
});


test("computed claims parse unambiguous repeated thousands groups", () => {
  const ledger = buildSourceLedger(computationInput("1.234.500", "234500", "1.000.000"));

  assert.equal(ledger.claims[2].normalized_value, "1.000.000");
});


test("computed claims reject ambiguous single-separator numbers", () => {
  assert.throws(
    () => buildSourceLedger(computationInput("1.000", "1", "999")),
    /ambiguous numeric format/,
  );
});


test("computed claims reject malformed numeric grouping", () => {
  assert.throws(
    () => buildSourceLedger(computationInput("1,23,4", "1", "0,23")),
    /malformed numeric format/,
  );
});


test("computed difference rejects incompatible operand and result dimensions", () => {
  assert.throws(
    () => buildSourceLedger(
      multiOperandComputationInput("difference", ["120 Minuten", "20 Stunden"], "100 Tage"),
    ),
    /incompatible computation units/,
  );
});


test("difference and ratio require exactly two operands", () => {
  for (const operation of ["difference", "ratio"]) {
    assert.throws(
      () => buildSourceLedger(
        multiOperandComputationInput(operation, ["30 Minuten", "20 Minuten", "10 Minuten"], "0 Minuten"),
      ),
      /requires exactly two operands/,
      operation,
    );
  }
});


test("sum uses every operand and requires compatible dimensions", () => {
  const valid = buildSourceLedger(
    multiOperandComputationInput("sum", ["10 Minuten", "20 Minuten", "30 Minuten"], "60 Minuten"),
  );
  assert.equal(valid.claims.at(-1).computation.operand_claim_ids.length, 3);

  assert.throws(
    () => buildSourceLedger(
      multiOperandComputationInput("sum", ["10 Minuten", "20 Stunden", "30 Minuten"], "60 Minuten"),
    ),
    /incompatible computation units/,
  );
});


test("claim source text must match an exact source span", () => {
  const invalid = input();
  invalid.claims[0].verbatim = "121";

  assert.throws(() => buildSourceLedger(invalid), /verbatim not found/);
});


test("source rights metadata is required", () => {
  const invalid = input();
  delete invalid.sources[0].rights_status;

  assert.throws(() => buildSourceLedger(invalid), /rights_status/);
});


test("source-ledger node adapter preserves the item and attaches the canonical handshake", () => {
  const original = {
    json: { source_ledger_input: input(), correlation_id: "corr.1" },
    binary: { evidence: { id: "binary.1" } },
  };

  const adapted = runSourceLedgerNode(original);

  assert.equal(adapted.binary, original.binary);
  assert.equal(adapted.json.correlation_id, "corr.1");
  assert.deepEqual(adapted.json.source_ledger, buildSourceLedger(input()));
  assert.deepEqual(
    Object.fromEntries(Object.keys(WORKFLOW_VERSIONS_V3).map((key) => [key, adapted.json[key]])),
    WORKFLOW_VERSIONS_V3,
  );
});
