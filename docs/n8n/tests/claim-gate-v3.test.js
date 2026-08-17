const test = require("node:test");
const assert = require("node:assert/strict");

const { buildSourceLedger } = require("../source-ledger-node-v3.js");
const {
  WORKFLOW_VERSIONS_V3,
  gateClaims,
  runClaimGateNode,
} = require("../claim-gate-v3.js");
const { resolveSchemaItems } = require("../../resolve-schema-node-v5.js");


function ledger() {
  return buildSourceLedger({
    sources: [
      {
        source_kind: "document",
        locator: "evidence.txt",
        captured_at: "2026-08-05T09:30:00+05:30",
        rights_status: "client_authorized",
        text: "Die Bearbeitung dauert 20 Minuten. TÜV geprüft. Ergebnis dokumentiert.",
        language: "de",
        allowed_uses: ["report", "quotation"],
      },
    ],
    claims: [
      {
        key: "duration",
        kind: "direct",
        claim_type: "number",
        value: "20 Minuten",
        source_locator: "evidence.txt",
        verbatim: "20 Minuten",
      },
      {
        key: "credential",
        kind: "direct",
        claim_type: "credential",
        value: "TÜV geprüft",
        source_locator: "evidence.txt",
        verbatim: "TÜV geprüft",
      },
      {
        key: "result",
        kind: "direct",
        claim_type: "named_result",
        value: "Ergebnis dokumentiert",
        source_locator: "evidence.txt",
        verbatim: "Ergebnis dokumentiert",
      },
      {
        key: "quote",
        kind: "direct",
        claim_type: "quote",
        value: "Die Bearbeitung dauert 20 Minuten.",
        source_locator: "evidence.txt",
        verbatim: "Die Bearbeitung dauert 20 Minuten.",
      },
    ],
  });
}


test("valid claim IDs ground numbers, quotes, credentials, and named results", () => {
  const claims = ledger();
  const byType = Object.fromEntries(
    claims.claims.map((claim) => [claim.claim_type, claim.claim_id]),
  );
  const output = {
    sections: [
      { text: "20 Minuten", claim_ids: [byType.number] },
      { quote: "„Die Bearbeitung dauert 20 Minuten.“", claim_ids: [byType.quote, byType.number] },
      { credential: "TÜV geprüft", claim_ids: [byType.credential] },
      { outcome: "Ergebnis dokumentiert", claim_ids: [byType.named_result] },
    ],
  };

  assert.deepEqual(gateClaims(output, claims), { pass: true, violations: [] });
});


test("a number present in source text still fails without a claim ID", () => {
  const result = gateClaims({ body: "Die Bearbeitung dauert 20 Minuten." }, ledger());

  assert.equal(result.pass, false);
  assert.equal(result.violations[0].code, "ungrounded_number");
});


test("integer and decimal JSON primitives at the root fail without claim IDs", () => {
  for (const [value, token] of [[20, "20"], [2.5, "2.5"]]) {
    assert.deepEqual(gateClaims(value, { claims: [] }), {
      pass: false,
      violations: [{ code: "ungrounded_number", field: "$", token }],
    });
  }
});


test("nested numeric primitives use inherited claim IDs through objects and arrays", () => {
  const claims = {
    claims: [
      { claim_id: "claim.integer", claim_type: "number", normalized_value: "20" },
      { claim_id: "claim.decimal", claim_type: "number", normalized_value: "2,5" },
    ],
  };
  const output = {
    claim_ids: ["claim.integer"],
    chart: {
      values: [
        20,
        { claim_ids: ["claim.decimal"], value: 2.5 },
      ],
    },
  };

  assert.deepEqual(gateClaims(output, claims), { pass: true, violations: [] });
});


test("nested numeric primitives fail when the nearest inherited claims do not match", () => {
  const result = gateClaims(
    { claim_ids: ["claim.integer"], chart: { values: [2.5] } },
    {
      claims: [
        { claim_id: "claim.integer", claim_type: "number", normalized_value: "20" },
      ],
    },
  );

  assert.deepEqual(result, {
    pass: false,
    violations: [{ code: "ungrounded_number", field: "$.chart.values[0]", token: "2.5" }],
  });
});


test("unknown and malformed claim ID declarations fail closed", () => {
  const unknown = gateClaims(
    { body: "Eine neutrale Aussage.", claim_ids: ["claim.unknown"] },
    ledger(),
  );
  assert.equal(unknown.pass, false);
  assert.equal(unknown.violations[0].code, "unknown_claim_id");

  const malformed = gateClaims(
    { body: "Eine neutrale Aussage.", claim_ids: "claim.invalid" },
    ledger(),
  );
  assert.equal(malformed.pass, false);
  assert.equal(malformed.violations[0].code, "invalid_claim_ids");
});


test("numeric grounding compares values exactly instead of by substring", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.three",
        claim_type: "number",
        normalized_value: "3",
      },
    ],
  };

  const result = gateClaims({ body: "30", claim_ids: ["claim.three"] }, claims);

  assert.equal(result.pass, false);
  assert.deepEqual(result.violations, [
    { code: "ungrounded_number", field: "$.body", token: "30" },
  ]);
});


test("numeric grounding requires compatible units", () => {
  const claims = ledger();
  const duration = claims.claims.find((claim) => claim.normalized_value === "20 Minuten");

  for (const body of ["20 %", "20 €", "20 Stunden"]) {
    const result = gateClaims({ body, claim_ids: [duration.claim_id] }, claims);
    assert.equal(result.pass, false, body);
    assert.equal(result.violations[0].code, "ungrounded_number", body);
  }
});


test("different unrecognized unit words do not ground each other", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.days",
        claim_type: "number",
        normalized_value: "20 Tage insgesamt",
      },
    ],
  };

  const result = gateClaims(
    { body: "20 Wochen", claim_ids: ["claim.days"] },
    claims,
  );

  assert.equal(result.pass, false);
  assert.equal(result.violations[0].code, "ungrounded_number");
});


test("an exact unrecognized unit word remains groundable", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.days",
        claim_type: "number",
        normalized_value: "20 Tage",
      },
    ],
  };

  assert.deepEqual(
    gateClaims({ body: "20 Tage später", claim_ids: ["claim.days"] }, claims),
    { pass: true, violations: [] },
  );
});


test("a shared adjective cannot ground different unknown compound measures", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.new-customers",
        claim_type: "number",
        normalized_value: "20 neue Kunden",
      },
    ],
  };

  const result = gateClaims(
    { body: "20 neue Standorte", claim_ids: ["claim.new-customers"] },
    claims,
  );

  assert.equal(result.pass, false);
  assert.equal(result.violations[0].code, "ungrounded_number");
});


test("unknown compound measures require bounded full-phrase matches", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.new-customers",
        claim_type: "number",
        normalized_value: "20 neue Kunden",
      },
    ],
  };

  assert.deepEqual(
    gateClaims(
      {
        body: "Im Quartal kamen '20   neue Kunden' hinzu.",
        claim_ids: ["claim.new-customers"],
      },
      claims,
    ),
    { pass: true, violations: [] },
  );
  const unbounded = gateClaims(
    { body: "20 neue Kundenservice", claim_ids: ["claim.new-customers"] },
    claims,
  );
  assert.equal(unbounded.pass, false);
  assert.equal(unbounded.violations[0].code, "ungrounded_number");
});


test("numeric grounding compares complete per-unit context", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.hourly-rate",
        claim_type: "number",
        normalized_value: "20 Euro pro Stunde",
      },
    ],
  };

  assert.deepEqual(
    gateClaims(
      { body: "20 Euro pro Stunde", claim_ids: ["claim.hourly-rate"] },
      claims,
    ),
    { pass: true, violations: [] },
  );
  for (const equivalent of ["20 Euro per Stunde", "20 Euro je Stunde", "20 Euro/Stunde"]) {
    assert.deepEqual(
      gateClaims({ body: equivalent, claim_ids: ["claim.hourly-rate"] }, claims),
      { pass: true, violations: [] },
      equivalent,
    );
  }
  const wrongDenominator = gateClaims(
    { body: "20 Euro pro Minute", claim_ids: ["claim.hourly-rate"] },
    claims,
  );
  assert.equal(wrongDenominator.pass, false);
  assert.equal(wrongDenominator.violations[0].code, "ungrounded_number");
});


test("numeric grounding compares currency following a scale", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.millions-eur",
        claim_type: "number",
        normalized_value: "20 Mio. €",
      },
    ],
  };

  assert.deepEqual(
    gateClaims(
      { body: "20 Mio. €", claim_ids: ["claim.millions-eur"] },
      claims,
    ),
    { pass: true, violations: [] },
  );
  const wrongCurrency = gateClaims(
    { body: "20 Mio. $", claim_ids: ["claim.millions-eur"] },
    claims,
  );
  assert.equal(wrongCurrency.pass, false);
  assert.equal(wrongCurrency.violations[0].code, "ungrounded_number");
});


test("ambiguous German numeric tokens require exact raw equality", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.one-thousand",
        claim_type: "number",
        normalized_value: "1.000 Kunden",
      },
    ],
  };

  assert.deepEqual(
    gateClaims(
      { body: "1.000 Kunden", claim_ids: ["claim.one-thousand"] },
      claims,
    ),
    { pass: true, violations: [] },
  );
  const scalar = gateClaims(
    { body: "1 Kunden", claim_ids: ["claim.one-thousand"] },
    claims,
  );

  assert.equal(scalar.pass, false);
  assert.equal(scalar.violations[0].code, "ungrounded_number");
});


test("credential grounding rejects partial canonical text", () => {
  const claims = {
    claims: [
      {
        claim_id: "claim.iso",
        claim_type: "credential",
        normalized_value: "ISO 9001 zertifiziert",
      },
    ],
  };

  const result = gateClaims(
    { credential: "ISO", claim_ids: ["claim.iso"] },
    claims,
  );

  assert.equal(result.pass, false);
  assert.equal(result.violations[0].code, "ungrounded_credential");
});


test("unsupported quote, credential, and named result fail independently", () => {
  const result = gateClaims(
    {
      quote: "„Ein frei erfundenes Zitat.“",
      credential: "ISO 9001 zertifiziert",
      outcome: "Umsatz verdoppelt",
    },
    ledger(),
  );

  assert.deepEqual(
    result.violations.map((violation) => violation.code).sort(),
    [
      "ungrounded_credential",
      "ungrounded_named_outcome",
      "ungrounded_number",
      "ungrounded_quote",
    ],
  );
});


test("actual resolver outcome and trust fields fail without supporting claims", () => {
  const store = {};
  const [caseItem, aboutItem] = resolveSchemaItems(
    [
      { json: { page_st_type: "ST-07A", content_id: "content.1" } },
      { json: { page_st_type: "ST-05", content_id: "content.1" } },
    ],
    () => store,
  );
  assert.ok(caseItem.json.output_schema.some((field) => field.key === "ergebnis_text"));
  assert.ok(aboutItem.json.output_schema.some((field) => field.key === "vertrauenspunkte"));

  const result = gateClaims(
    {
      ergebnis_text: "Dokumentiert und freigegeben.",
      vertrauenspunkte: ["Meisterbetrieb seit Generationen"],
    },
    { claims: [] },
  );

  assert.deepEqual(
    result.violations.map((violation) => [violation.code, violation.field]),
    [
      ["ungrounded_named_outcome", "$.ergebnis_text"],
      ["ungrounded_credential", "$.vertrauenspunkte[0]"],
    ],
  );
});


test("claim-gate node adapter consumes parsed output and the canonical ledger", () => {
  const claims = ledger();
  const number = claims.claims.find((claim) => claim.claim_type === "number");
  const original = {
    json: {
      source_ledger: claims,
      parsed_writer_output: { body: "20 Minuten", claim_ids: [number.claim_id] },
      correlation_id: "corr.1",
    },
    binary: { report: { id: "binary.1" } },
  };

  const adapted = runClaimGateNode(original);

  assert.equal(adapted.binary, original.binary);
  assert.equal(adapted.json.correlation_id, "corr.1");
  assert.deepEqual(adapted.json.claim_gate, { pass: true, violations: [] });
  assert.deepEqual(
    Object.fromEntries(Object.keys(WORKFLOW_VERSIONS_V3).map((key) => [key, adapted.json[key]])),
    WORKFLOW_VERSIONS_V3,
  );
});


test("claim-gate node adapter fails closed without inputs or on violations", () => {
  const missing = runClaimGateNode({ json: { correlation_id: "corr.1" } });
  assert.equal(missing.json.claim_gate.pass, false);
  assert.deepEqual(
    missing.json.claim_gate.violations.map((violation) => violation.code),
    ["source_ledger_missing", "writer_output_missing"],
  );

  const violated = runClaimGateNode({
    json: {
      source_ledger: ledger(),
      parsed_writer_output: { body: "20 Minuten" },
    },
  });
  assert.equal(violated.json.claim_gate.pass, false);
  assert.equal(violated.json.claim_gate.violations[0].code, "ungrounded_number");
});


test("claim-gate node adapter preserves and propagates a prior failure", () => {
  const prior = { pass: false, violations: [{ code: "writer_parse_failed" }] };
  const adapted = runClaimGateNode({
    json: {
      gate: prior,
      source_ledger: ledger(),
      parsed_writer_output: { body: "Plain text without a risky assertion." },
    },
  });

  assert.equal(adapted.json.gate, prior);
  assert.equal(adapted.json.claim_gate.pass, false);
  assert.equal(adapted.json.claim_gate.violations[0].code, "prior_gate_failure");
});
