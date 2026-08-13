const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");


const SOURCE_PATH = path.resolve(__dirname, "../../resolve-schema-node-v5.js");


function runResolver(jsonItems) {
  const source = fs.readFileSync(SOURCE_PATH, "utf8");
  const execute = new Function("$input", "$getWorkflowStaticData", source);
  const store = {};
  return execute(
    { all: () => jsonItems.map((json) => ({ json })) },
    () => store,
  );
}


function visitObjectFields(fields, pathPrefix, paths) {
  const claimFields = fields.filter((field) => field.key === "claim_ids");
  assert.equal(claimFields.length, 1, `${pathPrefix} must declare claim_ids exactly once`);
  assert.deepEqual(claimFields[0], {
    key: "claim_ids",
    required: false,
    type: "array",
    min_items: 1,
    max_items: 32,
    item: { type: "string", min: 1, max: 96 },
    desc: "Claim IDs from the canonical source ledger that support assertions in this object. Omit when this object makes no evidence-bearing assertion.",
  });
  paths.push(`${pathPrefix}.claim_ids`);

  for (const field of fields) {
    if (field.type === "object") {
      visitObjectFields(field.fields || [], `${pathPrefix}.${field.key}`, paths);
    }
    if (field.type === "array" && field.item && field.item.type === "object") {
      visitObjectFields(field.item.fields || [], `${pathPrefix}.${field.key}[]`, paths);
    }
  }
}


function containsClaimIds(value) {
  if (Array.isArray(value)) return value.some(containsClaimIds);
  if (!value || typeof value !== "object") return false;
  return Object.prototype.hasOwnProperty.call(value, "claim_ids")
    || Object.values(value).some(containsClaimIds);
}


test("resolver declares optional claim IDs at the root and every nested content object", () => {
  const [item] = runResolver([
    { page_st_type: "ST-09", content_id: "content.1", untouched: true },
  ]);
  const expectedPaths = [];

  visitObjectFields(item.json.output_schema, "$", expectedPaths);

  assert.deepEqual(item.json.claim_ids_paths, expectedPaths);
  assert.equal(item.json.untouched, true);
  for (const claimPath of expectedPaths) {
    assert.match(item.json.output_schema_text, /claim_ids/);
    assert.ok(claimPath.startsWith("$."));
  }
});


test("optional claim IDs never enter the required output skeleton", () => {
  const [item] = runResolver([
    { page_st_type: "ST-09", content_id: "content.1" },
  ]);
  const skeleton = JSON.parse(item.json.output_schema_skeleton);

  assert.equal(containsClaimIds(skeleton), false);
  assert.deepEqual(item.json.required_fields, [
    "titel",
    "einleitung",
    "schmerzpunkte",
  ]);
  assert.equal(skeleton.schmerzpunkte[0].titel, "string");
  assert.equal(skeleton.schmerzpunkte[0].beschreibung, "string");
});


test("resolver still rejects unknown ST types", () => {
  assert.throws(
    () => runResolver([{ page_st_type: "ST-UNKNOWN", content_id: "content.1" }]),
    /unknown ST type/,
  );
});


test("ST-08 (objections / FAQ) resolves without throwing", () => {
  const [item] = runResolver([
    { page_st_type: "ST-08", content_id: "content.1" },
  ]);
  const skeleton = JSON.parse(item.json.output_schema_skeleton);
  assert.deepEqual(item.json.required_fields, [
    "titel",
    "einleitung",
    "faqs",
  ]);
  assert.equal(skeleton.faqs[0].frage, "string");
  assert.equal(skeleton.faqs[0].antwort, "string");
});


test("writer prompt matches renderer-backed bildwunsch and ST-03 schema", () => {
  const prompt = fs.readFileSync(path.resolve(__dirname, "../../writer-prompt-v5.md"), "utf8");
  const [cover, cta] = runResolver([
    { page_st_type: "ST-01", content_id: "content.1" },
    { page_st_type: "ST-03", content_id: "content.1" },
  ]);
  const imageIntent = cover.json.output_schema.find((field) => field.key === "bildwunsch");

  assert.deepEqual(
    imageIntent.fields.filter((field) => field.key !== "claim_ids").map((field) => field.key),
    ["art"],
  );
  assert.equal(cta.json.output_schema.some((field) => field.key === "kennzahlen"), false);
  assert.doesNotMatch(prompt, /bildwunsch[^\n]*zweck/iu);
  assert.doesNotMatch(prompt, /ST-03[^\n]*kennzahlen/iu);
  assert.doesNotMatch(prompt, /CTA[^\n]*\[kennzahlen/iu);
});
