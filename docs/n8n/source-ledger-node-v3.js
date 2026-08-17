/** Build a deterministic source and claim ledger before prose generation. */

const WORKFLOW_VERSIONS_V3 = Object.freeze({
  workflow_contract_version: "3.2.1",
  writer_prompt_version: "5.1.1",
  schema_resolver_version: "5.2.1",
  writer_gate_version: "3.1.1",
  source_ledger_version: "3.2.1",
  claim_gate_version: "3.2.1",
});
const SOURCE_LEDGER_VERSION = WORKFLOW_VERSIONS_V3.source_ledger_version;

// n8n Code nodes provide no CommonJS require, so hashing is implemented
// portably against FIPS 180-4 and proven by fixed test vectors.
const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];


function utf8Bytes(text) {
  const bytes = [];
  for (let index = 0; index < text.length; index += 1) {
    let code = text.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff && index + 1 < text.length) {
      const low = text.charCodeAt(index + 1);
      if (low >= 0xdc00 && low <= 0xdfff) {
        code = 0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00);
        index += 1;
      }
    }
    if (code < 0x80) {
      bytes.push(code);
    } else if (code < 0x800) {
      bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
    } else if (code < 0x10000) {
      bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    } else {
      bytes.push(
        0xf0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3f),
        0x80 | ((code >> 6) & 0x3f),
        0x80 | (code & 0x3f),
      );
    }
  }
  return bytes;
}


function rotr(value, bits) {
  return ((value >>> bits) | (value << (32 - bits))) >>> 0;
}


function sha256(text) {
  const bytes = utf8Bytes(String(text));
  const bitLength = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  const high = Math.floor(bitLength / 0x100000000);
  const low = bitLength >>> 0;
  bytes.push(
    (high >>> 24) & 0xff, (high >>> 16) & 0xff, (high >>> 8) & 0xff, high & 0xff,
    (low >>> 24) & 0xff, (low >>> 16) & 0xff, (low >>> 8) & 0xff, low & 0xff,
  );
  const state = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  const words = new Array(64);
  for (let offset = 0; offset < bytes.length; offset += 64) {
    for (let t = 0; t < 16; t += 1) {
      words[t] = (
        (bytes[offset + 4 * t] << 24)
        | (bytes[offset + 4 * t + 1] << 16)
        | (bytes[offset + 4 * t + 2] << 8)
        | bytes[offset + 4 * t + 3]
      ) >>> 0;
    }
    for (let t = 16; t < 64; t += 1) {
      const s0 = rotr(words[t - 15], 7) ^ rotr(words[t - 15], 18) ^ (words[t - 15] >>> 3);
      const s1 = rotr(words[t - 2], 17) ^ rotr(words[t - 2], 19) ^ (words[t - 2] >>> 10);
      words[t] = (words[t - 16] + s0 + words[t - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = state;
    for (let t = 0; t < 64; t += 1) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = ((e & f) ^ (~e & g)) >>> 0;
      const temp1 = (h + S1 + ch + SHA256_K[t] + words[t]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
      const temp2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + temp1) >>> 0;
      d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
    }
    state[0] = (state[0] + a) >>> 0;
    state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0;
    state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0;
    state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0;
    state[7] = (state[7] + h) >>> 0;
  }
  return state.map((value) => value.toString(16).padStart(8, "0")).join("");
}


function stableId(prefix, value) {
  return `${prefix}.${sha256(value).slice(0, 16)}`;
}


function canonicalNumber(integerDigits, fractionDigits, negative) {
  const integer = integerDigits.replace(/^0+(?=\d)/, "");
  const fraction = (fractionDigits || "").replace(/0+$/, "");
  const magnitude = fraction ? `${integer}.${fraction}` : integer;
  return negative && magnitude !== "0" ? `-${magnitude}` : magnitude;
}


function normalizedNumber(lexeme) {
  const negative = lexeme.startsWith("-");
  const unsigned = /^[+-]/.test(lexeme) ? lexeme.slice(1) : lexeme;
  const dotCount = (unsigned.match(/\./g) || []).length;
  const commaCount = (unsigned.match(/,/g) || []).length;

  if (!dotCount && !commaCount) return canonicalNumber(unsigned, "", negative);

  if (dotCount && commaCount) {
    const decimalSeparator = unsigned.lastIndexOf(".") > unsigned.lastIndexOf(",") ? "." : ",";
    const groupingSeparator = decimalSeparator === "." ? "," : ".";
    if (unsigned.split(decimalSeparator).length !== 2) {
      throw new Error(`malformed numeric format: ${lexeme}`);
    }
    const [groupedInteger, fraction] = unsigned.split(decimalSeparator);
    const groups = groupedInteger.split(groupingSeparator);
    if (
      !/^\d+$/.test(fraction)
      || !/^\d{1,3}$/.test(groups[0])
      || groups.slice(1).some((group) => !/^\d{3}$/.test(group))
    ) {
      throw new Error(`malformed numeric format: ${lexeme}`);
    }
    return canonicalNumber(groups.join(""), fraction, negative);
  }

  const separator = dotCount ? "." : ",";
  const groups = unsigned.split(separator);
  if (groups.some((group) => !/^\d+$/.test(group))) {
    throw new Error(`malformed numeric format: ${lexeme}`);
  }
  if (groups.length > 2) {
    if (!/^\d{1,3}$/.test(groups[0]) || groups.slice(1).some((group) => group.length !== 3)) {
      throw new Error(`malformed numeric format: ${lexeme}`);
    }
    return canonicalNumber(groups.join(""), "", negative);
  }
  if (groups[1].length === 3) {
    throw new Error(`ambiguous numeric format: ${lexeme}`);
  }
  return canonicalNumber(groups[0], groups[1], negative);
}


function numericLexeme(value) {
  const text = String(value).trim();
  const match = text.match(/^[+-]?\d[\d.,]*/);
  if (!match) throw new Error(`claim has no numeric value: ${value}`);
  const suffix = text.slice(match[0].length);
  if (suffix && !/^(?:\s|[%€$£])/.test(suffix)) {
    throw new Error(`malformed numeric format: ${match[0]}`);
  }
  return { lexeme: match[0], measure: suffix.trim().toLowerCase() };
}


function numberFrom(value) {
  const number = Number(normalizedNumber(numericLexeme(value).lexeme));
  if (!Number.isFinite(number)) {
    throw new Error(`malformed numeric format: ${value}`);
  }
  return number;
}


function measureFrom(value) {
  return numericLexeme(value).measure;
}


function requiredField(raw, field, label) {
  if (raw[field] === undefined || raw[field] === null || raw[field] === "") {
    throw new Error(`${label} requires ${field}`);
  }
  return raw[field];
}


function sourceSpan(source, verbatim) {
  const start = source.verbatim_text.indexOf(verbatim);
  if (start < 0) throw new Error(`verbatim not found in ${source.locator}: ${verbatim}`);
  return {
    source_id: source.source_id,
    start,
    end: start + verbatim.length,
    verbatim,
  };
}


function computedValue(operation, operandKey, operands, resultValue) {
  if ((operation === "difference" || operation === "ratio") && operands.length !== 2) {
    throw new Error(`${operation} requires exactly two operands`);
  }
  if (operands.length < 2) throw new Error("computed claim requires at least two operands");
  const numbers = operands.map((claim) => numberFrom(claim.normalized_value));
  if (operation === "difference" || operation === "sum") {
    const measures = operands.map((claim) => measureFrom(claim.normalized_value));
    const resultMeasure = measureFrom(resultValue);
    if (measures.some((measure) => measure !== measures[0]) || resultMeasure !== measures[0]) {
      throw new Error(`incompatible computation units: ${operandKey}`);
    }
  }
  if (operation === "difference") return numbers[0] - numbers[1];
  if (operation === "sum") return numbers.reduce((a, b) => a + b, 0);
  if (operation === "product") return numbers.reduce((a, b) => a * b, 1);
  if (operation === "ratio") return numbers[0] / numbers[1];
  throw new Error(`unsupported computation: ${operation}`);
}


function buildSourceLedger(input) {
  const sources = (input.sources || []).map((raw) => {
    const locator = requiredField(raw, "locator", "source");
    const verbatimText = raw.verbatim_text ?? requiredField(raw, "text", "source");
    return {
      source_id: stableId("source", `${locator} ${verbatimText}`),
      source_kind: requiredField(raw, "source_kind", "source"),
      locator,
      captured_at: requiredField(raw, "captured_at", "source"),
      content_hash: sha256(verbatimText),
      rights_status: requiredField(raw, "rights_status", "source"),
      verbatim_text: verbatimText,
      language: requiredField(raw, "language", "source"),
      allowed_uses: raw.allowed_uses || [],
    };
  });
  const sourceByLocator = Object.fromEntries(sources.map((source) => [source.locator, source]));
  const claimByKey = {};
  const claims = [];

  for (const raw of input.claims || []) {
    const claimType = requiredField(raw, "claim_type", "claim");
    let sourceIds = [];
    let sourceSpans = [];
    let computation = null;
    if (raw.kind === "computed") {
      const operands = (raw.operand_keys || []).map((key) => {
        if (!claimByKey[key]) throw new Error(`computed claim has unknown operand: ${key}`);
        return claimByKey[key];
      });
      const calculated = computedValue(raw.operation, raw.key, operands, raw.value);
      if (Math.abs(calculated - numberFrom(raw.value)) > 1e-9) {
        throw new Error(`computed value does not match operands: ${raw.value}`);
      }
      computation = {
        formula: raw.formula || raw.operation,
        operand_claim_ids: operands.map((claim) => claim.claim_id),
      };
      sourceIds = [...new Set(operands.flatMap((claim) => claim.source_ids))].sort();
    } else {
      const source = sourceByLocator[raw.source_locator];
      if (!source) throw new Error(`unknown source locator: ${raw.source_locator}`);
      const span = sourceSpan(source, raw.verbatim);
      sourceIds = [source.source_id];
      sourceSpans = [span];
    }
    const identity = JSON.stringify({
      key: raw.key,
      claim_type: claimType,
      value: raw.value,
      source_ids: sourceIds,
      source_spans: sourceSpans,
      computation,
    });
    const claim = {
      claim_id: stableId("claim", identity),
      claim_type: claimType,
      normalized_value: raw.value,
      source_ids: sourceIds,
      source_spans: sourceSpans,
      computation,
      confidence: raw.confidence ?? 1,
      allowed_uses: raw.allowed_uses || [],
    };
    claims.push(claim);
    claimByKey[raw.key] = claim;
  }

  return {
    schema_version: "3.0",
    sources,
    claims,
  };
}


function runSourceLedgerNode(item) {
  const sourceItem = item && typeof item === "object" ? item : {};
  const json = sourceItem.json && typeof sourceItem.json === "object" ? sourceItem.json : {};
  const ledgerInput = json.source_ledger_input ?? json;
  const sourceLedger = buildSourceLedger(ledgerInput);
  return {
    ...sourceItem,
    json: {
      ...json,
      ...WORKFLOW_VERSIONS_V3,
      source_ledger: sourceLedger,
    },
  };
}


if (typeof module !== "undefined" && module && module.exports) {
  module.exports = {
    WORKFLOW_VERSIONS_V3,
    SOURCE_LEDGER_VERSION,
    buildSourceLedger,
    runSourceLedgerNode,
    sha256,
  };
}

if (typeof $input !== "undefined") {
  return $input.all().map(runSourceLedgerNode);
}
