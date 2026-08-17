const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");


const {
  WORKFLOW_VERSIONS_V3,
  gateSection,
  runWriterGateNode,
} = require("../writer_gate.js");


const GERMAN = {
  text: "Die Bearbeitung beginnt mit einer klaren Sicht auf den Ablauf. Das Team erkennt den Engpass und ordnet die nächsten Schritte gemeinsam.",
};
const ENGLISH = {
  text: "The process begins with a clear view of the work. The team sees the bottleneck and chooses the next steps together with confidence.",
};


test("German-direct writer output passes and English prose fails", () => {
  assert.deepEqual(gateSection(GERMAN), {
    pass: true,
    violations: [],
    retry_instruction: null,
  });

  const result = gateSection(ENGLISH);
  assert.equal(result.pass, false);
  assert.equal(result.violations[0].rule, "language_not_german");
  assert.match(result.retry_instruction, /German/i);
});


test("short English titles and labels fail while short German labels pass", () => {
  for (const value of ["Business growth strategy", "Customer success metrics"] ) {
    const result = gateSection({ title: value });
    assert.equal(result.pass, false, value);
    assert.equal(result.violations[0].rule, "language_not_german", value);
  }

  for (const value of ["Klare Abläufe", "Nächste Schritte", "Ergebnis im Überblick"]) {
    assert.deepEqual(
      gateSection({ titel: value }),
      { pass: true, violations: [], retry_instruction: null },
      value,
    );
  }
});


test("mixed English prose fails despite isolated German function words", () => {
  const result = gateSection({
    text: "The process is clear und the team can see die next step with confidence and better results.",
  });

  assert.equal(result.pass, false);
  assert.equal(result.violations[0].rule, "language_not_german");
});


test("writer gate retains deterministic German copy-law checks", () => {
  const result = gateSection({
    body: "Das könnte innovativ sein — nicht langsam, sondern nahtlos.",
  });
  const rules = result.violations.map((violation) => violation.rule);

  assert.ok(rules.includes("dash"));
  assert.ok(rules.includes("hedge"));
  assert.ok(rules.includes("banned_word"));
  assert.ok(rules.includes("negation_sondern"));
});


test("German banned vocabulary rejects common adjective inflections", () => {
  for (const value of [
    "Eine revolutionäre Methode",
    "Ein robuster Prozess",
    "Die robuste Lösung",
    "Mit revolutionärem Ansatz",
  ]) {
    const result = gateSection({ titel: value });
    assert.equal(result.pass, false, value);
    assert.ok(
      result.violations.some((violation) => violation.rule === "banned_word"),
      value,
    );
  }
});


test("writer gate source contains no translation mode architecture", () => {
  const source = fs.readFileSync(path.resolve(__dirname, "../writer_gate.js"), "utf8");

  assert.doesNotMatch(source, /translated|translation|pre-translation/i);
  assert.doesNotMatch(source, /number_not_in_data|claim_not_in_data|dataText|dataDigits/);
});


test("writer node adapter preserves the item, attaches versions, and fails closed", () => {
  const original = {
    json: { parsed_writer_output: ENGLISH, correlation_id: "corr.1" },
    binary: { report: { id: "binary.1" } },
  };

  const adapted = runWriterGateNode(original);

  assert.equal(adapted.binary, original.binary);
  assert.equal(adapted.json.correlation_id, "corr.1");
  assert.deepEqual(
    Object.fromEntries(Object.keys(WORKFLOW_VERSIONS_V3).map((key) => [key, adapted.json[key]])),
    WORKFLOW_VERSIONS_V3,
  );
  assert.equal(adapted.json.writer_gate.pass, false);
  assert.equal(adapted.json.writer_gate.violations[0].rule, "language_not_german");

  const missing = runWriterGateNode({ json: { correlation_id: "corr.2" } });
  assert.equal(missing.json.writer_gate.pass, false);
  assert.equal(missing.json.writer_gate.violations[0].rule, "writer_output_missing");
});
