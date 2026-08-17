/** Require explicit claim IDs for every high-risk writer assertion. */


const WORKFLOW_VERSIONS_V3 = Object.freeze({
  workflow_contract_version: "3.2.1",
  writer_prompt_version: "5.1.1",
  schema_resolver_version: "5.2.1",
  writer_gate_version: "3.1.1",
  source_ledger_version: "3.2.1",
  claim_gate_version: "3.2.1",
});
const CLAIM_GATE_VERSION = WORKFLOW_VERSIONS_V3.claim_gate_version;
const NUMBER = /(?:^|([^\p{L}\p{N}]))(-?\d+(?:[.,]\d+)*)/gu;
const CREDENTIAL = /\b(?:TÜV|TUEV|TUV|ISO(?:[ -]?\d+)?|zertifiziert\w*|certified|Marktführer\w*)\b/iu;
const OUTCOME = /\b(?:Ergebnis\w*|Umsatz\w*|Einspar\w*|Reduktion\w*|Steigerung\w*|verdoppelt|halbiert|gesenkt|gesteigert)\b/iu;
const SCALE_TOKENS = [
  ["millionen", "million"],
  ["million", "million"],
  ["mio.", "million"],
  ["mio", "million"],
  ["tausend", "thousand"],
  ["tsd.", "thousand"],
  ["tsd", "thousand"],
  ["k", "thousand"],
];
const MEASURE_TOKENS = [
  ["sekunden", "unit", "second"],
  ["sekunde", "unit", "second"],
  ["seconds", "unit", "second"],
  ["second", "unit", "second"],
  ["minuten", "unit", "minute"],
  ["minute", "unit", "minute"],
  ["stunden", "unit", "hour"],
  ["stunde", "unit", "hour"],
  ["hours", "unit", "hour"],
  ["hour", "unit", "hour"],
  ["kunden", "unit", "customer"],
  ["kunde", "unit", "customer"],
  ["customers", "unit", "customer"],
  ["customer", "unit", "customer"],
  ["personen", "unit", "person"],
  ["person", "unit", "person"],
  ["prozent", "unit", "percent"],
  ["percent", "unit", "percent"],
  ["euro", "currency", "eur"],
  ["dollar", "currency", "usd"],
  ["pfund", "currency", "gbp"],
  ["eur", "currency", "eur"],
  ["usd", "currency", "usd"],
  ["gbp", "currency", "gbp"],
  ["min.", "unit", "minute"],
  ["min", "unit", "minute"],
  ["std.", "unit", "hour"],
  ["std", "unit", "hour"],
  ["sek.", "unit", "second"],
  ["sek", "unit", "second"],
  ["%", "unit", "percent"],
  ["€", "currency", "eur"],
  ["$", "currency", "usd"],
  ["£", "currency", "gbp"],
];


function canonicalText(value) {
  return String(value)
    .normalize("NFKC")
    .replace(/[„“”"'«»‹›]/g, "")
    .replace(/\s+/gu, " ")
    .trim()
    .toLowerCase();
}


function canonicalNumber(integerDigits, fractionDigits, negative) {
  const integer = integerDigits.replace(/^0+(?=\d)/, "");
  const fraction = (fractionDigits || "").replace(/0+$/, "");
  const magnitude = fraction ? `${integer}.${fraction}` : integer;
  return negative && magnitude !== "0" ? `-${magnitude}` : magnitude;
}


function normalizedNumber(lexeme) {
  const negative = lexeme.startsWith("-");
  const unsigned = negative ? lexeme.slice(1) : lexeme;
  const dotCount = (unsigned.match(/\./g) || []).length;
  const commaCount = (unsigned.match(/,/g) || []).length;

  if (!dotCount && !commaCount) return canonicalNumber(unsigned, "", negative);

  if (dotCount && commaCount) {
    const decimalSeparator = unsigned.lastIndexOf(".") > unsigned.lastIndexOf(",") ? "." : ",";
    const groupingSeparator = decimalSeparator === "." ? "," : ".";
    if (unsigned.split(decimalSeparator).length !== 2) return null;
    const [groupedInteger, fraction] = unsigned.split(decimalSeparator);
    const groups = groupedInteger.split(groupingSeparator);
    if (
      !/^\d+$/.test(fraction)
      || !/^\d{1,3}$/.test(groups[0])
      || groups.slice(1).some((group) => !/^\d{3}$/.test(group))
    ) return null;
    return canonicalNumber(groups.join(""), fraction, negative);
  }

  const separator = dotCount ? "." : ",";
  const groups = unsigned.split(separator);
  if (groups.some((group) => !/^\d+$/.test(group))) return null;
  if (groups.length > 2) {
    if (!/^\d{1,3}$/.test(groups[0]) || groups.slice(1).some((group) => group.length !== 3)) {
      return null;
    }
    return canonicalNumber(groups.join(""), "", negative);
  }
  if (groups[1].length === 3) return null;
  return canonicalNumber(groups[0], groups[1], negative);
}


function tokenBoundary(character) {
  return character === undefined || /[\s/.,;:!?()[\]{}€$£%]/u.test(character);
}


function consumeKnownToken(text, offset, tokens) {
  const whitespace = text.slice(offset).match(/^\s*/u)[0];
  const start = offset + whitespace.length;
  const remainder = text.slice(start).toLowerCase();
  for (const token of tokens) {
    const lexeme = token[0];
    if (remainder.startsWith(lexeme) && tokenBoundary(remainder[lexeme.length])) {
      return { token, end: start + lexeme.length };
    }
  }
  return null;
}


function consumeUnknownUnit(text, offset) {
  const whitespace = text.slice(offset).match(/^\s*/u)[0];
  const start = offset + whitespace.length;
  const match = text.slice(start).match(/^([\p{L}][\p{L}\p{M}-]*)(?=$|[\s/.,;:!?()[\]{}])/u);
  if (!match) return null;
  const unit = canonicalText(match[1]);
  if (["pro", "per", "je"].includes(unit)) return null;
  return { value: `unknown:${unit}`, end: start + match[1].length };
}


function consumeRateConnector(text, offset) {
  const whitespace = text.slice(offset).match(/^\s*/u)[0];
  const start = offset + whitespace.length;
  if (text[start] === "/") return start + 1;
  const remainder = text.slice(start).toLowerCase();
  for (const connector of ["pro", "per", "je"]) {
    if (remainder.startsWith(connector) && tokenBoundary(remainder[connector.length])) {
      return start + connector.length;
    }
  }
  return null;
}


function measureContext(text, offset, prefix) {
  let cursor = offset;
  const context = {
    scale: null,
    unit: null,
    currency: /[€$£]/.test(prefix || "")
      ? { "€": "eur", "$": "usd", "£": "gbp" }[prefix]
      : null,
    denominator: null,
  };
  const scale = consumeKnownToken(text, cursor, SCALE_TOKENS);
  if (scale) {
    context.scale = scale.token[1];
    cursor = scale.end;
  }
  if (!context.currency) {
    const measure = consumeKnownToken(text, cursor, MEASURE_TOKENS);
    if (measure) {
      context[measure.token[1]] = measure.token[2];
      cursor = measure.end;
    } else {
      const unknownUnit = consumeUnknownUnit(text, cursor);
      if (unknownUnit) {
        context.unit = unknownUnit.value;
        cursor = unknownUnit.end;
      }
    }
  }
  const connectorEnd = consumeRateConnector(text, cursor);
  if (connectorEnd !== null) {
    const knownDenominator = consumeKnownToken(text, connectorEnd, MEASURE_TOKENS);
    if (knownDenominator && knownDenominator.token[1] === "unit") {
      context.denominator = knownDenominator.token[2];
    } else {
      const unknownDenominator = consumeUnknownUnit(text, connectorEnd);
      if (unknownDenominator) context.denominator = unknownDenominator.value;
    }
  }
  return context;
}


function isAmbiguousNumber(lexeme) {
  const unsigned = lexeme.startsWith("-") ? lexeme.slice(1) : lexeme;
  const separators = (unsigned.match(/[.,]/g) || []);
  if (separators.length !== 1) return false;
  const groups = unsigned.split(separators[0]);
  return groups.length === 2
    && /^\d{1,3}$/.test(groups[0])
    && /^\d{3}$/.test(groups[1]);
}


function canonicalRawNumber(lexeme) {
  return String(lexeme).normalize("NFKC").trim();
}


function numericAssertions(value) {
  const text = String(value);
  return [...text.matchAll(NUMBER)].map((match) => {
    const number = normalizedNumber(match[2]);
    return {
      number,
      raw_number: canonicalRawNumber(match[2]),
      ambiguous: number === null && isAmbiguousNumber(match[2]),
      measure: measureContext(text, match.index + match[0].length, match[1]),
      token: match[2],
    };
  });
}


function numbersMatch(candidate, assertion) {
  if (candidate.number !== null && assertion.number !== null) {
    return candidate.number === assertion.number;
  }
  return candidate.ambiguous
    && assertion.ambiguous
    && candidate.raw_number === assertion.raw_number;
}


function measuresMatch(candidate, assertion) {
  return candidate.scale === assertion.scale
    && candidate.unit === assertion.unit
    && candidate.currency === assertion.currency
    && candidate.denominator === assertion.denominator;
}


function hasUnknownMeasure(context) {
  return [context.unit, context.denominator].some(
    (value) => typeof value === "string" && value.startsWith("unknown:"),
  );
}


function containsBoundedCanonicalPhrase(text, phrase) {
  const canonical = canonicalText(text);
  const target = canonicalText(phrase);
  if (!target) return false;
  let offset = 0;
  while (offset <= canonical.length - target.length) {
    const index = canonical.indexOf(target, offset);
    if (index < 0) return false;
    const before = index > 0 ? canonical[index - 1] : null;
    const afterIndex = index + target.length;
    const after = afterIndex < canonical.length ? canonical[afterIndex] : null;
    if (
      (before === null || !/[\p{L}\p{N}]/u.test(before))
      && (after === null || !/[\p{L}\p{N}]/u.test(after))
    ) return true;
    offset = index + 1;
  }
  return false;
}


function hasSupportingClaim(claimById, claimIds, claimType, text, numericAssertion) {
  return claimIds.some((claimId) => {
    const claim = claimById[claimId];
    if (!claim || (claimType && claim.claim_type !== claimType)) return false;
    if (numericAssertion) {
      return numericAssertions(claim.normalized_value).some((candidate) => {
        if (!numbersMatch(candidate, numericAssertion)) return false;
        if (hasUnknownMeasure(candidate.measure) || hasUnknownMeasure(numericAssertion.measure)) {
          return containsBoundedCanonicalPhrase(text, claim.normalized_value);
        }
        return measuresMatch(candidate.measure, numericAssertion.measure);
      });
    }
    return canonicalText(text) === canonicalText(claim.normalized_value);
  });
}


const OUTCOME_KEYS = /^ergebnis(?:_text)?$/;
const CREDENTIAL_KEYS = /^(?:vertrauenspunkte|zertifikate)$/;


function gateClaims(writerOutput, ledger) {
  const claimById = Object.fromEntries((ledger.claims || []).map((claim) => [claim.claim_id, claim]));
  const violations = [];

  function checkString(value, path, claimIds, keyHint) {
    const key = (keyHint || "").toLowerCase();
    for (const assertion of numericAssertions(value)) {
      if (!hasSupportingClaim(claimById, claimIds, null, value, assertion)) {
        violations.push({ code: "ungrounded_number", field: path, token: assertion.token });
      }
    }
    const isQuote = key.includes("quote") || /[„“”"]/.test(value);
    if (isQuote && !hasSupportingClaim(claimById, claimIds, "quote", value)) {
      violations.push({ code: "ungrounded_quote", field: path, token: value });
    }
    const isCredential = key.includes("credential") || CREDENTIAL_KEYS.test(key) || CREDENTIAL.test(value);
    if (isCredential && !hasSupportingClaim(claimById, claimIds, "credential", value)) {
      violations.push({ code: "ungrounded_credential", field: path, token: value });
    }
    const isOutcome = key.includes("outcome") || OUTCOME_KEYS.test(key) || OUTCOME.test(value);
    if (isOutcome && !hasSupportingClaim(claimById, claimIds, "named_result", value)) {
      violations.push({ code: "ungrounded_named_outcome", field: path, token: value });
    }
  }

  function checkNumber(value, path, claimIds) {
    if (!Number.isFinite(value)) return;
    const token = String(value);
    const assertion = numericAssertions(token)[0];
    if (!assertion) return;
    if (!hasSupportingClaim(claimById, claimIds, null, token, assertion)) {
      violations.push({ code: "ungrounded_number", field: path, token });
    }
  }

  function visit(node, path, inheritedClaimIds, keyHint) {
    if (node === null || node === undefined) return;
    if (typeof node === "number") {
      checkNumber(node, path, inheritedClaimIds);
      return;
    }
    if (typeof node === "string") {
      checkString(node, path, inheritedClaimIds, keyHint);
      return;
    }
    if (typeof node !== "object") return;
    if (Array.isArray(node)) {
      node.forEach((item, index) => visit(item, `${path}[${index}]`, inheritedClaimIds, keyHint));
      return;
    }
    let localClaimIds = inheritedClaimIds;
    if (Object.prototype.hasOwnProperty.call(node, "claim_ids")) {
      if (
        !Array.isArray(node.claim_ids)
        || node.claim_ids.length === 0
        || node.claim_ids.some((claimId) => typeof claimId !== "string" || !claimId.trim())
      ) {
        violations.push({ code: "invalid_claim_ids", field: `${path}.claim_ids`, token: node.claim_ids });
      } else {
        localClaimIds = [...new Set([...inheritedClaimIds, ...node.claim_ids])];
        node.claim_ids.forEach((claimId) => {
          if (!claimById[claimId]) {
            violations.push({ code: "unknown_claim_id", field: `${path}.claim_ids`, token: claimId });
          }
        });
      }
    }
    for (const [key, value] of Object.entries(node)) {
      if (key === "claim_ids" || key === "claim_id") continue;
      visit(value, `${path}.${key}`, localClaimIds, key);
    }
  }

  visit(writerOutput, "$", [], null);
  return { pass: violations.length === 0, violations };
}


function runClaimGateNode(item) {
  const sourceItem = item && typeof item === "object" ? item : {};
  const json = sourceItem.json && typeof sourceItem.json === "object" ? sourceItem.json : {};
  if (json.claim_gate && json.claim_gate.pass === false) {
    return {
      ...sourceItem,
      json: { ...json, ...WORKFLOW_VERSIONS_V3 },
    };
  }

  const violations = [];
  const ledger = json.source_ledger;
  const writerOutput = json.parsed_writer_output ?? json.writer_output ?? json.writerOutput;
  if (!ledger || typeof ledger !== "object" || !Array.isArray(ledger.claims)) {
    violations.push({
      code: "source_ledger_missing",
      field: "$.source_ledger",
      token: null,
    });
  }
  if (!writerOutput || typeof writerOutput !== "object" || Array.isArray(writerOutput)) {
    violations.push({
      code: "writer_output_missing",
      field: "$.parsed_writer_output",
      token: null,
    });
  }
  if (json.gate && json.gate.pass === false) {
    violations.unshift({
      code: "prior_gate_failure",
      field: "$.gate",
      token: null,
    });
  }

  let result;
  if (violations.length) {
    result = { pass: false, violations };
  } else {
    try {
      result = gateClaims(writerOutput, ledger);
    } catch (error) {
      result = {
        pass: false,
        violations: [{
          code: "claim_gate_error",
          field: "$",
          token: error instanceof Error ? error.message : String(error),
        }],
      };
    }
  }

  return {
    ...sourceItem,
    json: {
      ...json,
      ...WORKFLOW_VERSIONS_V3,
      claim_gate: result,
    },
  };
}


if (typeof module !== "undefined" && module && module.exports) {
  module.exports = {
    WORKFLOW_VERSIONS_V3,
    CLAIM_GATE_VERSION,
    gateClaims,
    runClaimGateNode,
  };
}

if (typeof $input !== "undefined") {
  return $input.all().map(runClaimGateNode);
}
