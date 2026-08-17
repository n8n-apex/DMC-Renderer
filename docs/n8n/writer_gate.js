/** Deterministic German-direct copy QC for one parsed writer section. */

const WORKFLOW_VERSIONS_V3 = Object.freeze({
  workflow_contract_version: "3.2.1",
  writer_prompt_version: "5.1.1",
  schema_resolver_version: "5.2.1",
  writer_gate_version: "3.1.1",
  source_ledger_version: "3.2.1",
  claim_gate_version: "3.2.1",
});

const BANNED_VOCAB = [
  "innovativ", "maßgeschneidert", "ganzheitlich", "hochmodern",
  "bahnbrechend", "nahtlos", "robust", "synergie", "revolutionär",
  "transformieren", "innovative", "bespoke", "tailor-made", "holistic",
  "state-of-the-art", "cutting-edge", "seamless", "leverage", "unlock",
  "game-changer", "empower", "supercharge", "revolutionize",
  "revolutionise", "transform", "elevate", "streamline",
];
const HEDGES = ["kann helfen", "in vielen fällen", "tends to", "in many cases"];
const HEDGE_WORDS = [
  "könnte", "oft", "tendenziell", "wahrscheinlich", "may", "likely",
];
const DASHES = /[—–]/u;
const DE_MARKERS = /\b(?:und|die|eine[mnr]?|de[rsn]|das|den|dem|wir|mit|für|wird|sind|bei[m]?|auch|ohne|über|auf|aus|zur|zum)\b/giu;
const EN_MARKERS = /\b(?:the|and|with|of|this|that|is|are|can|will|but|for|from|you|your|our|their|business|growth|strategy|customer|success|metrics|process|team|results?|steps?|view|confidence|better|clear|next|work|sees?|chooses?|together|begins?)\b/giu;
const NEGATION_SONDERN = /\b(?:nicht|kein(?:e|en|em|er|es)?)\b[^.!?]{0,160}\bsondern\b/iu;
const ALLOWED_ADDITIVE = /\bnicht\s+nur\b[^.!?]{0,160}\bsondern\s+auch\b/iu;


function walkStrings(node, path, out) {
  if (node === null || node === undefined) return out;
  if (typeof node === "string") {
    out.push([path, node]);
    return out;
  }
  if (Array.isArray(node)) {
    node.forEach((value, index) => walkStrings(value, `${path}[${index}]`, out));
    return out;
  }
  if (typeof node === "object") {
    Object.keys(node).forEach((key) => {
      if (key !== "claim_ids") walkStrings(node[key], `${path}.${key}`, out);
    });
  }
  return out;
}


function excerptAround(text, needle, span) {
  const index = text.toLowerCase().indexOf(String(needle).toLowerCase());
  if (index < 0) return text.slice(0, span);
  const start = Math.max(0, index - 25);
  return text.slice(start, index + String(needle).length + span);
}


function hasProseColon(text) {
  const withoutUrlsOrTimes = String(text)
    .replace(/\bhttps?:\/\/\S+/giu, "")
    .replace(/\b\d{1,2}:\d{2}\b/gu, "");
  return withoutUrlsOrTimes.includes(":");
}


function looksGerman(text) {
  const raw = String(text);
  const words = raw.trim().split(/\s+/u).filter(Boolean);
  const germanHits = (raw.match(DE_MARKERS) || []).length;
  const englishHits = (raw.match(EN_MARKERS) || []).length;
  if (englishHits >= 2 && englishHits > germanHits) return false;
  if (words.length < 12) return true;
  return germanHits >= Math.max(2, words.length * 0.08);
}


function gateSection(writerOutput) {
  const violations = [];
  const fields = walkStrings(writerOutput, "$", []);

  fields.forEach(([path, text]) => {
    if (DASHES.test(text)) {
      violations.push({
        rule: "dash",
        field: path,
        excerpt: excerptAround(text, text.match(DASHES)[0], 30),
      });
    }

    if (hasProseColon(text)) {
      violations.push({ rule: "colon", field: path, excerpt: excerptAround(text, ":", 30) });
    }

    BANNED_VOCAB.forEach((word) => {
      const expression = new RegExp(`\\b${word.replace(/-/g, "[-]")}(?:e[mnrs]?)?\\b`, "iu");
      if (expression.test(text)) {
        violations.push({
          rule: "banned_word",
          field: path,
          excerpt: `${word}: ${excerptAround(text, word, 40)}`,
        });
      }
    });

    const lower = text.toLowerCase();
    HEDGES.forEach((hedge) => {
      if (lower.includes(hedge)) {
        violations.push({ rule: "hedge", field: path, excerpt: hedge });
      }
    });
    HEDGE_WORDS.forEach((hedge) => {
      if (new RegExp(`\\b${hedge}\\b`, "iu").test(text)) {
        violations.push({ rule: "hedge", field: path, excerpt: hedge });
      }
    });

    if (NEGATION_SONDERN.test(text) && !ALLOWED_ADDITIVE.test(text)) {
      violations.push({
        rule: "negation_sondern",
        field: path,
        excerpt: excerptAround(text, "sondern", 40),
      });
    }

    if (/\bEuro\b/iu.test(text)) {
      violations.push({ rule: "euro_word", field: path, excerpt: excerptAround(text, "Euro", 30) });
    }

    if (!looksGerman(text)) {
      violations.push({
        rule: "language_not_german",
        field: path,
        excerpt: text.slice(0, 60),
      });
    }
  });

  let retryInstruction = null;
  if (violations.length) {
    retryInstruction =
      "Your previous output violated these rules. Regenerate the SAME section in German, "
      + "changing ONLY what is needed to fix each violation. Keep every correct fact.\n"
      + violations.map((violation, index) => (
        `${index + 1}. [${violation.rule}] at ${violation.field}: ${violation.excerpt}`
      )).join("\n")
      + "\nRules reminder: write every value in German; no prose colons or dashes; "
      + "no banned vocabulary, hedging, or negation followed by sondern. "
      + "Claim authority is checked separately against exact claim IDs.";
  }

  return {
    pass: violations.length === 0,
    violations,
    retry_instruction: retryInstruction,
  };
}


function missingWriterOutput() {
  return {
    pass: false,
    violations: [{
      rule: "writer_output_missing",
      field: "$.parsed_writer_output",
      excerpt: "Parsed writer output is required.",
    }],
    retry_instruction: "Regenerate the section in German and return one parsed JSON object.",
  };
}


function runWriterGateNode(item) {
  const sourceItem = item && typeof item === "object" ? item : {};
  const json = sourceItem.json && typeof sourceItem.json === "object" ? sourceItem.json : {};
  const writerOutput = json.parsed_writer_output ?? json.writer_output ?? json.writerOutput;
  const result = writerOutput && typeof writerOutput === "object"
    ? gateSection(writerOutput)
    : missingWriterOutput();
  return {
    ...sourceItem,
    json: {
      ...json,
      ...WORKFLOW_VERSIONS_V3,
      writer_gate: result,
    },
  };
}


if (typeof module !== "undefined" && module && module.exports) {
  module.exports = {
    WORKFLOW_VERSIONS_V3,
    gateSection,
    runWriterGateNode,
  };
}

if (typeof $input !== "undefined") {
  return $input.all().map(runWriterGateNode);
}
