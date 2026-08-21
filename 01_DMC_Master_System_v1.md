# DMC-REPORT MASTER SYSTEM v1.0
## Einzige verbindliche Regelquelle für alle KI-Agenten
**Status: AKTIV — überschreibt alle anderen Dokumente in Regelfragen**
**Wissensdatenbank (KB v2, Masterbook v3, Layer v4, v5) = Hintergrundwissen, NICHT Regelwerk**
**Letzte Aktualisierung: 2026**

---

# ⚠️ KONFLIKT-AUFLÖSUNG: DIESE DATEI GEWINNT IMMER

Wenn ein Agent in einer anderen Datei eine Regel findet die dieser widerspricht:
→ Diese Datei gilt. Keine Ausnahme.

Bekannte Widersprüche die hiermit aufgelöst sind:
- Fallstudien: Einzelseite ist Standard (nicht Doppelseite)
- ST-07 wurde in ST-07A/B/C aufgeteilt
- Slot-Plan wurde entsprechend korrigiert
- Kombinationsverbote wurden auf korrekte ST-Nummern aktualisiert
- Design-System v1 ist veraltet — Design-System v2 gilt

---

# MODUL 1: AGENTEN-ARCHITEKTUR UND ZUSTÄNDIGKEITEN

## 1.1 Die 6 Agenten im System

```
AGENT 0: Strategie-Gate        → Prüft ob Report-Kern stark genug ist
AGENT 1: Input-Analyse         → Extrahiert Briefing-JSON aus Rohdaten
AGENT 2: Research              → Füllt externe Quellen und Lücken
AGENT 3: Struktur              → Baut Seitenplan aus Seitentypen-DB
AGENT 4: Copy                  → Schreibt seitenweise Copy
AGENT 5: QA                    → Prüft Gesamtqualität, gibt Freigabe
```

## 1.2 Welche Wissensdatenbank welcher Agent bekommt

| Agent | Pflicht-Kontext aus KB | Zweck |
|-------|----------------------|-------|
| Agent 0 | Modul 3 (Input-Gates), Modul 5 (psychologische Architektur) | Strategie-Bewertung |
| Agent 1 | Modul 3 (Input-Gates), Modul 4 (Briefing-Schema) | Vollständige Extraktion |
| Agent 2 | Modul 6 (Quellen-Hierarchie), Modul 7 (Diagramm-Spec) | Quellen-Recherche |
| Agent 3 | Modul 8 (Seitentypen-Datenbank), Modul 9 (Slot-Plan), Modul 10 (Kombinations-Logik) | Struktur-Entscheidung |
| Agent 4 | Modul 11 (Copy-Regeln), Modul 12 (Seitentyp-Regelsets), Modul 13 (Voice-Marker + Brücken) | Copy-Produktion |
| Agent 5 | Modul 14 (QA-Matrix), Modul 3 (Input-Gates) | Qualitätskontrolle |

## 1.3 Pflicht-Reihenfolge — kein Überspringen

```
Agent 0 → Agent 1 → Agent 2 → Agent 3 → [Kunden-Approval optional] → Agent 4 (Loop) → Agent 5
```

Wenn Agent 0 FAIL → Prozess stoppt. Agent 1 wird nicht gestartet.
Wenn Agent 5 Score < 80 → Betroffene Seiten zurück zu Agent 4. Max. 2 Revisions-Loops.
Wenn Agent 5 Score < 80 nach 2 Loops → Menschlicher Review durch Richard.

---

# MODUL 2: PRODUKT-DEFINITION

## 2.1 Was ein DMC-Report ist

Ein DMC-Report ist ein physisches, gedrucktes Magazin im DIN-A4-Format (16–28 Seiten) das per Post an B2B-Entscheider verschickt wird. Er ist kein Produktkatalog, keine Imagebroschüre und kein Flyer.

**Einziges Ziel:** Der Leser bucht ein kostenloses Erstgespräch.

**Was ein Report NIE tut:**
- Produkte oder Pakete vorstellen
- Preise nennen
- Als Werbemittel wahrgenommen werden wollen
- Den Leser vollständig über die Lösung aufklären (How-to-Verbot)

## 2.2 Wirtschaftliche Logik

- Versandkosten: 2,50–4,50 EUR pro Report
- Inbound-Quote bei starker Copy: 1–3%
- ROAS nur aus Inbound (ohne Calls): 300–500%
- Follow-up-Frequenz: alle 6–8 Wochen neue Mailings an dieselbe Liste
- Mindest-Zielgruppe: B2B-Entscheider, Monatsumsatz Empfänger min. 15.000–20.000 EUR

---

# MODUL 3: INPUT-GATES — HARTE STOPP-BEDINGUNGEN

## 3.1 Pflicht-Inputs vor Report-Start

Agent 0 prüft diese Gates. Fehlt eines → Prozess stoppt, Lückenliste an VA.

| Pflicht-Input | Konsequenz wenn fehlend |
|--------------|------------------------|
| Zielgruppe spezifisch (nicht "alle Unternehmer") | STOPP — kein Report |
| Min. 1 wörtlicher Irrglaube der Zielgruppe | STOPP — kein Report |
| Unique Mechanism (Name + Grundlogik) | STOPP — erst Mechanismus entwickeln |
| Min. 2 Fallstudien mit Vorher/Nachher-Zahlen | STOPP — kein Report, nur Rohstruktur |
| CTA-Ziel (URL oder Buchungsseite) | STOPP — Rückseite nicht möglich |
| Bewusstseinszustand der Zielgruppe (Level 1–5) | WARNUNG — Agent schätzt selbst, flaggt |
| Autorenfoto vorhanden | WARNUNG — Cover-Platzhalter |
| Trustpilot-Score oder vergleichbarer Trust-Anker | WARNUNG — Autorität-Seite geschwächt |

## 3.2 Strategie-Gate (Agent 0)

Agent 0 prüft zusätzlich:

**Kernthese-Test:** Kann dieser Satz formuliert werden?
"Diese Zielgruppe glaubt [X], aber in Wahrheit ist [Y] das Problem. Deshalb braucht sie [Z]."

Wenn nicht → Agent 0 formuliert 3 Vorschläge und wartet auf menschliche Entscheidung.

**Mechanismus-Test:** Ist der Unique Mechanism eigenständig?
- Hat er einen proprietären Namen? (nicht "unser System" oder "unsere Methode")
- Ist er in 2 Sätzen erklärbar?
- Unterscheidet er sich vom Standard-Marktangebot?

Wenn nicht → Agent 0 schlägt Namen vor und flaggt für menschliche Freigabe.

**Denkfehler-Test:** Gibt es eine klare Fehldiagnose der Zielgruppe?
- Was glaubt die Zielgruppe ist das Problem?
- Was ist das echte Problem?
- Warum ist das nicht dasselbe?

Wenn nicht → Schwacher Report-Kern, WARNUNG.

---

# MODUL 4: BRIEFING-SCHEMA (Agent 1 Output)

## 4.1 Vollständiges JSON-Schema

```json
{
  "meta": {
    "kunde": "[Firmenname]",
    "autor": "[Name des Absenders]",
    "erstellungsdatum": "[YYYY-MM-DD]",
    "version": "1.0"
  },
  "strategie": {
    "kernthese": "[Diese ZG glaubt X, aber Y ist das echte Problem. Deshalb braucht sie Z.]",
    "fehldiagnose_zg": "[Was ZG für das Problem hält]",
    "echtes_problem": "[Was wirklich dahinter steckt]",
    "denkfehler_kette": "[Symptom → falsches Problem → falsche Lösung → echtes Problem → echte Lösung]"
  },
  "zielgruppe": {
    "bezeichnung": "[Spezifisch — nicht generisch]",
    "bewusstseinszustand": 2,
    "begruendung_level": "[Warum dieser Level — 2 Sätze]",
    "branche": "[Branche]",
    "unternehmensgroesse": "[Umsatz/MA wenn bekannt]",
    "volltreffer_anfrage": "[Was der Idealkunde sagt nach dem Report]",
    "falsche_anfrage": "[Wen wir nicht wollen]"
  },
  "schmerzen": [
    {
      "rang": 1,
      "symptom_konkret": "[Konkrete Situation — KEIN Konzept]",
      "falsches_problem": "[Wie sie es selbst deuten]",
      "echtes_problem": "[Eigentliche Ursache]",
      "zitat": "[Wortwörtliches Zitat oder null]"
    }
  ],
  "irrglauben": [
    {
      "rang": 1,
      "zitat_woertlich": "[Wie ZG wirklich denkt — in ihrer Sprache]",
      "warum_logisch": "[Warum dieser Irrglaube entsteht]",
      "warum_falsch": "[Warum er nicht stimmt]",
      "wahrheit": "[Neue Überzeugung die zur Lösung führt]"
    }
  ],
  "ausloeser_moment": "[Konkretes Ereignis das Kunden zum Handeln bringt]",
  "aha_moment": "[Satz der im Gespräch den Rahmen verändert]",
  "hidden_magic": "[Was ihr im Hintergrund erledigt das Kunden kaum sehen]",
  "unique_mechanism": {
    "name": "[Proprietärer Begriff]",
    "kurzbeschreibung": "[Was es ist — 2 Sätze Vogelperspektive]",
    "abgrenzung": "[Warum anders als Standard]",
    "schritte": ["[Schritt 1]", "[Schritt 2]", "[Schritt 3]"]
  },
  "fallstudien": [
    {
      "rang": 1,
      "name_pseudonym": "[Name oder Pseudonym]",
      "kurzportraet": "[Wer ist das, 2 Sätze]",
      "ausgangsproblem": "[Konkrete Situation, 2 Sätze]",
      "wendepunkt": "[DER eine Moment der alles veränderte]",
      "loesung_skizze": "[Was verändert wurde — ohne How-to]",
      "ergebnis_vorher": "[Zahl]",
      "ergebnis_nachher": "[Zahl]",
      "zeitraum": "[X Wochen/Monate]",
      "verifizierbar": true,
      "verifizierung_url": "[URL oder null]",
      "foto_vorhanden": true
    }
  ],
  "autoritaet": {
    "kundenzahl": "[Zahl mit Zeitraum]",
    "jahre_im_markt": "[Zahl]",
    "trustpilot_score": "[Score + Anzahl]",
    "zertifikate": ["[TÜV]"],
    "presse": ["[Forbes]"],
    "team_groesse": "[Zahl]"
  },
  "sprache_der_zg": {
    "eigene_woerter": ["[Begriff 1]", "[Begriff 2]"],
    "metaphern": ["[Metapher 1]"],
    "abwehr_begriffe": ["[Begriff der Abwehr auslöst]"],
    "falsche_schublade": "[Als was darf der Absender nicht wahrgenommen werden]",
    "mundpropaganda": "[Wie zufriedene Kunden es anderen beschreiben]"
  },
  "einwaende": {
    "offene_einwaende": ["[Einwand 1 wörtlich]"],
    "versteckte_einwaende": ["[Was wirklich dahinter steckt]"],
    "interne_gegenargumente": ["[Was sich ZG selbst sagt um nicht zu handeln]"]
  },
  "energie_woerter": ["[Markenbegriff 1]"],
  "verbotene_begriffe": ["[Begriff der nie benutzt werden darf]"],
  "verbotene_themen": ["[Thema das nicht vorkommt]"],
  "must_have_inhalt": "[Was unbedingt vorkommt]",
  "cta": {
    "typ": "Erstgespräch",
    "url": "[URL]",
    "qr_code": true
  },
  "sprache": {
    "anrede": "du",
    "aggro_level": 2
  },
  "design": {
    "primaerfarbe_hex": "[Hex aus Kunden-CD]",
    "akzentfarbe_hex": "[Hex]",
    "logo_vorhanden": true,
    "autorenfoto_vorhanden": true
  },
  "luecken": {
    "fehlende_fallstudien_anzahl": 0,
    "offene_research_anforderungen": ["[These X braucht noch Beleg]"],
    "fehlende_assets": ["[Asset-Typ]"]
  }
}
```

---

# MODUL 5: PSYCHOLOGISCHE REPORT-ARCHITEKTUR

## 5.1 Die 6 Phasen

**Phase 1 — Status & Machtposition (Cover bis ca. S4)**
Ziel: Vertrauen aufbauen, Autorität etablieren, Zielgruppe scharf selektieren
Nie: Produktverkauf, Preis, konkretes Angebot

**Phase 2 — Spiegel & Konfrontation (ca. S4–S8)**
Ziel: Status quo zerlegen, Mindset-Fehler benennen, Schmerz rationalisieren
Schuld liegt immer beim System — nie beim Leser

**Phase 3 — Systemische Erklärung (ca. S8–S10)**
Ziel: Echtes Problem strukturell erklären, Named Mechanism einführen
Vogelperspektive — kein vollständiges How-to

**Phase 4 — Proof (ca. S10–S16)**
Ziel: Emotionaler + rationaler Beweis durch Fallstudien und externe Quellen

**Phase 5 — Unique Mechanism (ca. S15–S17)**
Ziel: Eigenes System als einzig logische Konsequenz positionieren

**Phase 6 — Entscheidungsdruck (ca. S17–S20)**
Ziel: Einwände vorwegnehmen, lösungsneutralen CTA setzen

## 5.2 Bewusstseinszustände der Zielgruppe

| Level | Zustand | Copy-Aufgabe | Bevorzugte Seitentypen |
|-------|---------|-------------|----------------------|
| 1 | Kein Problembewusstsein | Ist-Zustand als abnormal kennzeichnen | ST-09, ST-12 |
| 2 | Falsches Problembewusstsein | Fehldiagnose → echte Diagnose | ST-14, ST-16, ST-09 |
| 3 | Richtige Diagnose, keine Lösung | Mechanismus einführen | ST-06, ST-14, ST-15 |
| 4 | Lösung bekannt, nicht umgesetzt | Ausreden zertrümmern, Kosten quantifizieren | ST-10, ST-15, ST-13 |
| 5 | Lösung versucht, nicht funktioniert | Warum bisherige Versuche scheitern | ST-11, ST-17 |

Regel: Copy immer für Level+1 schreiben (Zielgruppe auf Level 2 → Level-3-Content)

---

# MODUL 6: RESEARCH-REGELN (Agent 2)

## 6.1 Quellen-Hierarchie

Tier 1: McKinsey, BCG, Bain, Deloitte, Roland Berger
Tier 2: Statista, Destatis, DIHK, ZDH, Bitkom, GfK
Tier 3: Fraunhofer-Institute, Hochschulen
Tier 4: Branchenverbände, Peer-reviewed Journale
VERBOTEN: SEO-Blogs, Foren, nicht verifizierbare Quellen

## 6.2 Quellen-Zieldichte

- Min. 2 hochwertige externe Quellen pro inhaltlicher These
- Gesamtreport: min. 6–8 belegte Claims mit Quelle
- Wenn keine gute Quelle: Status "nicht belegt" — niemals erfinden

## 6.3 Research-Output-Format

```json
{
  "research_paket": [
    {
      "these": "[Aussage die belegt werden soll]",
      "quelle_name": "[Name]",
      "quelle_herausgeber": "[Organisation]",
      "quelle_jahr": "2024",
      "tier": 1,
      "kernaussage": "[Was die Quelle sagt — 1 Satz]",
      "zitierbare_zahl": "[Konkrete Statistik]",
      "status": "belegt"
    }
  ]
}
```

---

# MODUL 7: DIAGRAMM-SPEZIFIKATIONS-SYSTEM

## 7.1 Diagramm-Datenpaket (Pflicht pro geplantem Diagramm)

```json
{
  "diagramm_id": "D-01",
  "seite": 9,
  "titel": "[Kurztitel des Diagramms]",
  "claim": "[These die das Diagramm visualisiert]",
  "typ": "Kreislauf | Balken | Treppe | Flowchart | Matrix | Donut | Radar | Verlauf",
  "datenpunkte_anzahl": 4,
  "datenpunkte": [
    {"label": "[Name]", "wert": "[Zahl oder Beschreibung]"}
  ],
  "datenquelle": "[Quelle oder 'eigene Kundendaten']",
  "muss_ohne_text_verstaendlich_sein": true,
  "design_farbe": "Primär | Akzent | Grau-Skala",
  "legende": false
}
```

## 7.2 Universelle Diagramm-Verbote

- Kein 3D
- Keine Legenden-Boxen (Beschriftung direkt am Element)
- Maximal 6 Datenpunkte
- Keine Komposit-Farben — eine Primärfarbe dominiert, Rest in Grau
- Schwarzer Text auf dunklem Hintergrund: nicht erlaubt

---

# MODUL 8: SEITENTYPEN-DATENBANK (vollständig, korrigiert)

## 8.0 Klassen-Übersicht

| Klasse | Typen | Pflicht? |
|--------|-------|---------|
| FIXED | ST-01, ST-02, ST-03 | Ja, immer |
| ANCHOR | ST-04, ST-05, ST-06, ST-07A, ST-08 | Fast immer |
| PROBLEM | ST-09, ST-10, ST-11, ST-12, ST-13 | 1–2 wählen |
| DENKFEHLER | ST-14, ST-15, ST-16, ST-17, ST-18 | 1–2 wählen, nie alle |
| MECHANISMUS | ST-19, ST-20, ST-21, ST-22 | 1–2 zusätzlich zu ST-06 |
| PROOF | ST-07A, ST-07B, ST-07C, ST-23, ST-24, ST-25, ST-26, ST-27, ST-28 | 3–5 gesamt |
| TRUST | ST-29, ST-30, ST-31 | 0–2 |
| SPECIAL | ST-32, ST-33, ST-34, ST-35, ST-36, ST-37 | 1–3 |

---

## ST-01 | COVER
**Klasse:** FIXED | **Position:** S1 | **Seiten:** 1
**Textbudget:** ~600 Zeichen
**Psychologische Phase:** 1

**Pflicht-Elemente:** Headline (max. 12 Wörter), Subheadline (5–8 Wörter), Zielgruppen-Nennung, Autorenfoto, 3–4 Inhaltsteaser, Logo, Datum

**Headline-Typen (einer davon):**
- A Problem-Blockierung: "Die X Gründe warum [ZG] bei [Level] steckenbleibt"
- B Potenzial-Enthüllung: "X% aller [ZG] könnten [Ergebnis] — wenn sie [Hebel] kennen"
- C Wahrheitsschock: "Der Wahrheitsschock [Jahr] für [ZG]"
- D Test-Format: "[Frage die Selbsttest auslöst]"
- E Transformation: "Von [Ist] zu [Soll] — wie [ZG] [Ergebnis] erreicht"

**VERBOTEN:** Preis, Angebot, Fließtext-Absätze, mehr als eine Hauptaussage

---

## ST-02 | AUSBLICK / EDITORIAL
**Klasse:** FIXED | **Position:** S2 oder S3 | **Seiten:** 1
**Textbudget:** 900–1.200 Zeichen
**Psychologische Phase:** 1→2

**Struktur (Pflicht):**
1. Konkreter Einstieg (Szene, Test, Zahl — KEINE abstrakte These)
2. Status-Anerkennung (1–2 Sätze)
3. Destabilisierung ("Und trotzdem...")
4. Problem (echtes, nicht offensichtliches)
5. Richtung (wohin der Report führt — ohne Lösung zu verraten)
6. Soft-CTA (optional, 1 Satz)
7. Autorname + Funktion

**Ausblick-Varianten:**
- A Test-Format (Urlaubstest-Stil)
- B Szenen-Format (Alltagsmoment)
- C Zahlen-Format (Statistik als Einstieg)
- D Konfrontations-Format (direkte Herausforderung)
- E Story-Format (Beobachtung aus Alltag des Autors)

**Bewertungs-Benchmark:** Stark (8–9/10) = konkreter Test oder Zahl + Widerspruch zur Selbstwahrnehmung. Schwach (3–4/10) = abstrakte These, bekannte Wahrheiten, Floskeln.

**VERBOTEN:** "Digitalisierung ist wichtig", "In der heutigen Geschäftswelt", generische Eröffnungen

---

## ST-03 | RÜCKSEITE / HARD-CTA
**Klasse:** FIXED | **Position:** S20 (letzte Seite) | **Seiten:** 1
**Textbudget:** 150–200 Zeichen
**Psychologische Phase:** 6

**Pflicht-Elemente:** CTA-Headline (4–6 Wörter), 2–3 Sätze, URL groß, QR-Code (Pflicht, min. 40×40 mm)
**Optional:** Proof-Streifen (Trustpilot + Kundenzahl, 1 Zeile)

**ABSOLUT VERBOTEN:** Produktpreis, konkretes Angebot, "Kaufe jetzt", mehr als 3 Sätze

---

## ST-04 | INNENKLAPPE / EINGANGS-IMPULS
**Klasse:** ANCHOR | **Position:** S2 wenn Ausblick auf S3 | **Seiten:** 1
**Textbudget:** 600–800 Zeichen
**Einsatz:** Wenn Cover sehr kurz, gibt persönlichen Einstieg vor Ausblick

---

## ST-05 | AUTORITÄT / ÜBER-UNS
**Klasse:** ANCHOR | **Position:** S3–S4 | **Seiten:** 1
**Textbudget:** 700–900 Zeichen
**Psychologische Phase:** 1

**Pflicht-Elemente:** Kundenzahl mit Zeitraum, Umsatz/aggregierte Kundenergebnisse, Jahre im Markt, min. 2 Trust-Anker (Trustpilot, TÜV, Presse), Team/Office-Bild, Autoritäts-Brücken-Satz am Ende

**Autoritäts-Typen:**
- A Zahlen-dominant
- B Story-dominant (kurze Geschichte + Ergebnis heute)
- C Team-dominant
- D Kunden-dominant (Logos/Sektoren)

**VERBOTEN:** Lange Unternehmensgeschichte, Services-Auflistung, Selbstlob ohne Beleg

---

## ST-06 | MECHANISMUS-EINFÜHRUNG
**Klasse:** ANCHOR | **Position:** S8–S10 | **Seiten:** 1–2
**Textbudget:** 800–1.100 Zeichen (Einzelseite) / 1.800–2.200 (Doppelseite)
**Psychologische Phase:** 3

**Pflicht-Elemente:** Named Mechanism (proprietärer Begriff), Vogelperspektive-Erklärung, Abgrenzung zum alten Weg, Prozessgrafik oder Framework-Darstellung, Soft-CTA

**3-Wellen-Integration:**
- Welle 1 (Ausblick S3): kurze beiläufige Erwähnung, noch nicht erklärt
- Welle 2 (diese Seite): vollständige Einführung
- Welle 3 (Fallstudien): implizite Referenz als Grund für Ergebnis

**Mechanismus-Visualisierungs-Typen:** Schritte-Flowchart, Kreislauf, Vergleichsmatrix, Treppe, Flussdiagramm

**VERBOTEN:** Vollständige How-to-Erklärung, mehr als 30% des "Wie" aufdecken

---

## ST-07A | FALLSTUDIE EINZELSEITE (STANDARD)
**Klasse:** ANCHOR/PROOF | **Seiten:** 1
**Textbudget:** 600–800 Zeichen
**Psychologische Phase:** 4
**REGEL: Das ist der Standard. Fallstudien sind Einzelseiten.**

**Pflicht-Elemente:**
- Ergebnis als Headline (Zahl zuerst, z.B. "342.000 EUR in 8 Wochen")
- Kurzporträt (2–3 Sätze, Identifikation erzeugen)
- Ausgangsproblem als konkrete Situation (nicht Konzept)
- Wendepunkt (DER eine Satz der alles veränderte — Pflicht)
- Ergebnis-Zahl visuell groß (min. 40pt Design-Hinweis)
- Kundenfoto (Pflicht wenn vorhanden)
- Verifikations-Hinweis (Trustpilot/Website, 1 Zeile)

**VERBOTEN:** Fehlender Wendepunkt, unspezifische Ergebnisse ("mehr Anfragen"), mehr als 30% Methodenerklärung, Fallstudie ohne Zahlen

---

## ST-07B | FALLSTUDIEN-GEGENSEITE (EIGENSTÄNDIGE VERTIEFUNG)
**Klasse:** PROOF | **Seiten:** 1
**Textbudget:** 600–900 Zeichen
**Psychologische Phase:** 4

**Funktion:** Erklärt das Warum hinter dem Ergebnis der gegenüberliegenden Fallstudie — ohne direkten Rückbezug. Der Leser liest die Fallstudie, sieht dann diese Seite, und versteht den Mechanismus tiefer. Beide Seiten funktionieren aber eigenständig.

**ABSOLUT VERBOTEN:** Direkter Verweis auf die Fallstudie ("wie bei Max zu sehen", "genau das hat FS1 gezeigt"). Die Seite muss eigenständig stehen.

**Was diese Seite zeigt:**
- Den systemischen Grund warum das Ergebnis möglich war
- Ein Diagramm, eine Zahl oder einen Mechanismus-Element
- Einen Prinzip-Satz der das Warum erklärt

**Einsatz:** Steht immer gegenüber einer ST-07A wenn im 20-Seiten-Report Platz vorhanden

---

## ST-07C | FALLSTUDIE DOPPELSEITE (AUSNAHMEFALL)
**Klasse:** PROOF | **Seiten:** 2
**Textbudget:** 1.200–1.500 Zeichen
**Psychologische Phase:** 4

**Wann einsetzen (ALLE Bedingungen müssen erfüllt sein):**
- Report 2 oder 3 desselben Kunden (bewusste Abwechslung) ODER
- Außergewöhnlich starke Fallstudie mit viel Proof-Material ODER
- 28+ Seiten wo mehr Platz vorhanden ist
- Und: Das Fallstudien-Thema hergibt inhaltlich wenig

**NICHT als Standard-Format für Report #1**

---

## ST-08 | FAQ / EINWANDVORWEGNAHME
**Klasse:** ANCHOR | **Position:** S18–S19 | **Seiten:** 1
**Textbudget:** 500–700 Zeichen
**Psychologische Phase:** 6

**Struktur:** 3–5 Fragen (wortwörtlich wie ZG sie stellt) + je 2–3 Zeilen direkte Antwort + Soft-Hard-Bridge am Ende

**FAQ-Typen:**
- A Einwand-fokussiert
- B Prozess-fokussiert ("wie läuft das ab?")
- C Ergebnis-fokussiert ("was kann ich erwarten?")

**VERBOTEN:** Diplomatisch ausgewichene Antworten, Produktpreis, Paketnamen

---

## ST-09 | STATUS-QUO-SPIEGEL
**Klasse:** PROBLEM | **Seiten:** 1
**Textbudget:** 900–1.100 Zeichen
**Bewusstseinszustand:** Level 1–2

**Struktur:**
1. Konkreter Alltagseinstieg (Szene, nicht Konzept)
2. Symptom-Kaskade (3–5 konkrete Situationen — "Wenn du... Wenn du... Wenn du...")
3. Falsche Interpretation ("Die meisten deuten das als...")
4. Echte Ursache (1 starker Satz)
5. Bridge zur nächsten Seite

**Varianten:** A Szenen-basiert, B Frage-basiert (5 Selbsttest-Fragen), C Zitat-basiert (echte O-Töne)

---

## ST-10 | KOSTEN-DES-NICHTSTUNS
**Klasse:** PROBLEM | **Seiten:** 1
**Textbudget:** 800–1.000 Zeichen
**Bewusstseinszustand:** Level 3–4

**Pflicht-Elemente:** Konkrete Zahl (was kostet Nichtstun pro Monat/Quartal), Zeitlicher Kontext, Kumulativer Verlust ("In 12 Monaten..."), sachliche Ursachen-Erklärung

**Varianten:** A Geld, B Zeit, C Marktposition

---

## ST-11 | MARKT-VERÄNDERUNGS-SEITE
**Klasse:** PROBLEM | **Seiten:** 1
**Textbudget:** 900–1.100 Zeichen
**Bewusstseinszustand:** Level 1–2

**Varianten:** A Technologie-Wandel, B Marktkonsolidierung, C Verbraucherverhalten, D Regulierung

---

## ST-12 | ALLTAGSMOMENT-SEITE
**Klasse:** PROBLEM | **Seiten:** 1
**Textbudget:** 700–900 Zeichen

**Prinzip:** Nur EINE Situation — extrem detailliert. Als würde man nur zu einer einzigen Person sprechen. "Intimste Momente" — Dinge die jeder kennt aber niemand ausspricht.

**Varianten:** A Sonntagabend-Moment, B Personalausfall-Moment, C Urlaubsmoment, D Jahresabschluss-Moment

---

## ST-13 | FEIND-FRAME-SEITE
**Klasse:** PROBLEM | **Seiten:** 1
**Textbudget:** 800–1.000 Zeichen

**Varianten:** A Alte Methoden als Feind, B Falsche Berater (ohne Namensnennnung), C Marktmechanismus als Feind, D Eigene Untätigkeit als Feind

---

## ST-14 | IRRGLAUBEN-DREIER-BLOCK
**Klasse:** DENKFEHLER | **Seiten:** 1
**Textbudget:** 1.100–1.300 Zeichen gesamt
**Bewusstseinszustand:** Level 2–3

**Struktur je Irrglaube:**
```
[ZITAT — wortwörtlich, in Anführungszeichen]
[VALIDIERUNG — 1 Satz: warum dieser Gedanke logisch ist]
[ZERTRÜMMERUNG — 2–3 Sätze mit konkretem Beleg]
[WAHRHEIT — 1–2 Sätze: neue Überzeugung, kein Kaufargument]
```

**Varianten:** A Alle drei zum selben Thema, B Drei verschiedene Themenbereiche, C Eskalierend (kleinstem zu größtem)

**VERBOTEN:** Zitat klingt nach Marketing-Formulierung, Zertrümmerung ohne Beleg, direkte Produkterwähnung

---

## ST-15 | EINZEL-IRRGLAUBE-DEEP-DIVE
**Klasse:** DENKFEHLER | **Seiten:** 1
**Textbudget:** 900–1.100 Zeichen

**Einsatz:** Wenn ein Irrglaube besonders tief sitzt. NICHT zusätzlich zu ST-14 sondern stattdessen.

---

## ST-16 | DENKFEHLER-KETTE
**Klasse:** DENKFEHLER | **Seiten:** 1
**Textbudget:** 700–900 Zeichen + Visualisierung

**Visualisierung:** Symptom → falsches Problem → falsche Lösung → echtes Problem → echte Lösung (als Pfeil-Schema)

---

## ST-17 | MYTHEN-BUSTING-SEITE
**Klasse:** DENKFEHLER | **Seiten:** 1
**Textbudget:** 900–1.100 Zeichen

Sachlicher als ST-14 — weniger emotional, mehr informativ.

---

## ST-18 | TRANSFORMATION / PARADIGMENWECHSEL
**Klasse:** DENKFEHLER / ÜBERGANG | **Seiten:** 1
**Textbudget:** 800–1.000 Zeichen

**Funktion:** Emotionaler Übergang von altem zu neuem Denken. Brücke zwischen Problem und Lösung.

---

## ST-19 | MECHANISMUS-VERTIEFUNG
**Klasse:** MECHANISMUS | **Seiten:** 1
**Textbudget:** 800–1.000 Zeichen

**Einsatz:** Nur wenn Mechanismus 5+ Schritte hat und ein Schritt besonders erklärungsbedürftig ist.

---

## ST-20 | SYSTEM-DIAGRAMM-SEITE
**Klasse:** MECHANISMUS | **Seiten:** 1
**Textbudget:** 300–500 Zeichen

Diagramm füllt 70–80% der Seite. Text = Headline + 2–3 Erklärsätze.

---

## ST-21 | VERGLEICHSMATRIX (ALT VS. NEU)
**Klasse:** MECHANISMUS | **Seiten:** 1
**Textbudget:** 400–600 Zeichen (Tabellenbeschriftungen)

2-Spalten-Tabelle: Links "Alte Methode" (grau), Rechts "Mit [Named Mechanism]" (Primärfarbe). 5–8 Kriterien.

---

## ST-22 | PROZESS-ABLAUF / ZUSAMMENARBEIT
**Klasse:** MECHANISMUS | **Seiten:** 1
**Textbudget:** 600–800 Zeichen
**Ausnahme:** Hier sind nummerierte Listen (4–6 Schritte) erlaubt

---

## ST-23 | MINI-FALLSTUDIEN-CLUSTER
**Klasse:** PROOF | **Seiten:** 1
**Textbudget:** 600–800 Zeichen gesamt

3 kurze Fallstudien auf einer Seite. Je: Name/Typ + Problem (1 Satz) + Ergebnis (Zahl + Zeitraum).

---

## ST-24 | VORHER-NACHHER-SEITE
**Klasse:** PROOF | **Seiten:** 1
**Textbudget:** 400–600 Zeichen

Zwei Hälften: Vorher (grau/rot) → Nachher (Primärfarbe). Zahlen groß typografiert.

---

## ST-25 | ZAHLEN-SEITE / AGGREGIERTER PROOF
**Klasse:** PROOF | **Seiten:** 1
**Textbudget:** 300–500 Zeichen

3–5 große Zahlen dominant. Je Zahl: Label + 1 Erklärsatz + Zeitraum/Basis-Angabe.

---

## ST-26 | TESTIMONIAL-CLUSTER
**Klasse:** PROOF | **Seiten:** 1
**Textbudget:** 600–800 Zeichen gesamt

3–4 Zitate (je 2–4 Sätze) + Foto + Name + Quellenhinweis (Trustpilot o.ä.)

---

## ST-27 | BRANCHEN-STATISTIK-SEITE
**Klasse:** PROOF | **Seiten:** 1
**Textbudget:** 700–900 Zeichen

2–3 externe Statistiken mit Quelle + Einordnung was das für die ZG bedeutet.
**VERBOTEN:** Nicht verifizierbare Quellen, mehr als 3 Statistiken

---

## ST-28 | FALLSTUDIE DEEP-DIVE EINZELSEITE
**Klasse:** PROOF | **Seiten:** 1
**Textbudget:** 700–900 Zeichen

Kurzversion einer Fallstudie wenn kein Platz für ST-07A. Oder: ein besonders starkes Element einer bereits gezeigten Fallstudie vertieft.

---

## ST-29 | TEAM-SEITE
**Klasse:** TRUST | **Seiten:** 1
**Textbudget:** 400–600 Zeichen

---

## ST-30 | PRESSE / MEDIEN-SEITE
**Klasse:** TRUST | **Seiten:** 1
**Einsatz:** Nur wenn echte Medienerwähnungen vorhanden. Niemals fälschen.

---

## ST-31 | KOMPETENZ-BLOCK / TRUST-CLUSTER
**Klasse:** TRUST | **Seiten:** 1
**Textbudget:** 200–400 Zeichen

Trust-Elemente gebündelt: Trustpilot + TÜV + Kundenzahl + Presse. Überwiegend visuell.

---

## ST-32 | ATEMSEITE / TYPOGRAFISCHES WALLPAPER
**Klasse:** SPECIAL | **Seiten:** 1

Ein einziger Satz oder eine Zahl. Typografisch groß. Viel Weißraum ODER farbige Vollflächenfläche.
**Einsatz:** Alle 5–7 Seiten maximal eine. **NIEMALS** direkt nach einer anderen Atemseite.

---

## ST-33 | TEST / CHECK-SEITE
**Klasse:** SPECIAL | **Seiten:** 1
**Textbudget:** 500–700 Zeichen

5–7 Ja/Nein-Fragen + Auswertung.
**Einsatz:** Max. 1× pro Report. **NIEMALS** wenn Ausblick schon Selbsttest enthält.

---

## ST-34 | ZUKUNFTSVISIONS-SEITE
**Klasse:** SPECIAL | **Seiten:** 1
**Textbudget:** 700–900 Zeichen

Konkrete Zukunftsszene + was sich ändert + Machbarkeits-Teaser.

---

## ST-35 | WELTBILD-SEITE
**Klasse:** SPECIAL | **Seiten:** 1
**Textbudget:** 600–900 Zeichen

**Vorsicht:** Eher für Mailing 2/3. Bei kalten Erstmailings kann zu philosophisch wirken.

---

## ST-36 | BONUS-SEITE
**Klasse:** SPECIAL | **Seiten:** 1
**Einsatz:** 1× pro Report wenn Breite gewünscht. Überraschender Mehrwert-Inhalt.

---

## ST-37 | SOFT-CTA-ZWISCHENSEITE
**Klasse:** SPECIAL | **Seiten:** 1
**Textbudget:** 300–500 Zeichen

Mid-Report Gesprächseinladung. **Lösungsneutral** — kein Produktname, kein Preis.

---

# MODUL 9: SLOT-PLÄNE (KORRIGIERT)

## 9.1 Standard 20-Seiten-Report

```
S1:  ST-01 — Cover (FIXED)
S2:  ST-02 — Ausblick/Editorial (FIXED)
     ODER: ST-04 Innenklappe auf S2, ST-02 auf S3
S3:  ST-05 — Autorität/Über-Uns (ANCHOR)
     ODER S2/S3 Ausblick + S4 Autorität (je nach Ausblick-Variante)
S4:  VARIABLE — aus PROBLEM-Gruppe (ST-09 bis ST-13)
S5:  VARIABLE — aus PROBLEM oder DENKFEHLER-Gruppe
S6:  VARIABLE — aus DENKFEHLER-Gruppe (ST-14 bis ST-18)
S7:  VARIABLE — aus DENKFEHLER oder ÜBERGANG-Gruppe
S8:  ST-06 — Mechanismus-Einführung (ANCHOR)
S9:  VARIABLE — aus MECHANISMUS-Gruppe (ST-19 bis ST-22)
     ODER ST-37 Soft-CTA-Zwischenseite
S10: ST-07A — Fallstudie #1 (ANCHOR/PROOF)
S11: ST-07B — Gegenseite zu FS1 (PROOF) — eigenständige Vertiefung
S12: ST-07A — Fallstudie #2 (ANCHOR/PROOF)
S13: ST-07B — Gegenseite zu FS2 (PROOF) — oder VARIABLE aus PROOF-Gruppe
S14: VARIABLE — Fallstudie #3 (ST-07A) ODER PROOF-Sonderformat (ST-23–ST-27)
S15: VARIABLE — Gegenseite zu FS3 ODER PROOF-Gruppe ODER SPECIAL
S16: VARIABLE — aus PROOF oder TRUST-Gruppe
S17: ST-05-Variante / ST-31 — Kompetenz & Trust gebündelt (ANCHOR)
S18: ANCHOR — Einladungs-Seite / Zusammenarbeit (ST-22 oder ST-37)
S19: ST-08 — FAQ / Einwandvorwegnahme (ANCHOR)
S20: ST-03 — Rückseite/Hard-CTA (FIXED)
```

**CTA-Kadenz:** S2 (Soft im Ausblick), S9 (Mid nach Mechanismus), S18 (Mid Einladung), S20 (Hard)

## 9.2 24-Seiten-Report

+4 Slots zwischen S13 und S14 (aus VARIABLE-Gruppen wählen).
Mögliche Erweiterungen: Dritte vollständige Fallstudie + Gegenseite, zusätzliche Statistik-Seite, Zukunftsvision, Weltbild-Seite.

## 9.3 16-Seiten-Report

Streiche: S5, S7, S14, S15.
Behalte alle FIXED und ANCHOR Pflichttypen.
Nur 2 Fallstudien (ST-07A) ohne Gegenseiten.

## 9.4 28-Seiten-Report

+8 Slots. Hier können ST-07C (Doppelseiten-Fallstudien) sinnvoll eingesetzt werden.

---

# MODUL 10: KOMBINATIONS-LOGIK

## 10.1 Kombinationsverbote (HART)

- ST-14 (Irrglauben-Dreier) + ST-15 (Einzel-Deep-Dive) → nicht gleichzeitig, nur eines
- ST-32 (Atemseite) direkt nach ST-32 → verboten
- ST-33 (Test-Seite) + Selbsttest im Ausblick (ST-02 Variante A) → verboten
- ST-10 (Kosten Nichtstun) + ST-11 (Marktveränderung) direkt hintereinander → zu viel Druck-Dichte
- ST-23 (Mini-Fallstudien-Cluster) + ST-07A auf derselben Doppelseite → Redundanz

## 10.2 Pflicht-Sequenzen

- ST-06 (Mechanismus) MUSS vor erster ST-07A (Fallstudie) kommen
- ST-07B (Gegenseite) DARF NICHT direkt auf eine andere ST-07B folgen
- Hard-CTA (ST-03) MUSS lösungsneutral sein — kein Produkt, kein Preis
- Soft-CTA: alle 2–3 Seiten in beliebigem Seitentyp als Abschluss

## 10.3 Bewusstseinszustand-gesteuerte Auswahl

```
WENN bewusstseinszustand == 1:
  → BEVORZUGE: ST-09, ST-12, ST-11
  → VERMEIDE: ST-10 (braucht Problembewusstsein)

WENN bewusstseinszustand == 2:
  → BEVORZUGE: ST-14, ST-16, ST-09
  → KERN: Denkfehler-Kette aufzeigen

WENN bewusstseinszustand == 3:
  → BEVORZUGE: ST-06, ST-14, ST-15
  → KERN: Mechanismus als Lösung einführen

WENN bewusstseinszustand == 4:
  → BEVORZUGE: ST-10, ST-15, ST-13
  → KERN: Ausreden zertrümmern

WENN bewusstseinszustand == 5:
  → BEVORZUGE: ST-11, ST-17, ST-21
  → KERN: Warum bisherige Lösung scheiterte
```

---

# MODUL 11: COPY-REGELN (ABSOLUT VERBINDLICH)

## 11.1 Sprach-Grundregeln

- Generisches Maskulinum ausschließlich — kein Gendern
- "Du"-Ansprache (außer Briefing gibt "Sie" vor)
- Fließtext überall — keine Bullet-Listen (Ausnahme: ST-22 Prozessablauf)
- Aggro-Level Standard: 2 (ruhig dominant)

## 11.2 Die 4 Satz-Jobs (PFLICHT)

Jeder Satz erfüllt einen dieser Jobs — sonst streichen:
1. Konkrete Realität beschreiben (Situation, Symptom)
2. Zusammenhang erklären (Kausalität, Warum)
3. Folge sichtbar machen (Konsequenz, Kosten des Nichtstuns)
4. Schlussfolgerung ziehen (Was das für den Leser bedeutet)

## 11.3 Das Symptom-Prinzip (wichtigste Einzelregel)

NIEMALS Konzepte — IMMER konkrete Situationen:

❌ "Du hast Probleme bei der Neukundengewinnung."
✅ "Deine Ads verbrennen Budget, ohne qualifizierte Anfragen zu bringen."

❌ "Die Mitarbeitergewinnung läuft schlecht."
✅ "Du hast 3 offene Stellen. Auf die letzte Bewerbung hast du 4 Monate gewartet."

## 11.4 Verbotene Konstruktionen (HART, keine Ausnahmen)

- "Nicht X, sondern Y" → max. 1× pro gesamtem Report
- Dreiwort-Satz-Ketten ("Klare Struktur. Einfache Schritte. Schnelle Umsetzung.") → max. 1× als Trick
- Gedankenstriche → max. 1× pro Seite
- Inhaltsleere Sätze ohne konkretes Beispiel
- Buzzwords ohne Nutzen: "innovativ", "maßgeschneidert", "ganzheitlich", "state-of-the-art"
- Wiederholung desselben normalen Worts 3× auf einer Seite → Synonymisierung
- Abstrakte Aussage ohne sofortige Konkretisierung
- How-to-Vollständigkeit: max. 30% des "Wie" darf erklärt werden

## 11.5 Verbotene Einstiege

NIEMALS:
- "In der heutigen Geschäftswelt..."
- "Digitalisierung ist heute wichtiger denn je."
- "Das Agenturbusiness boomt."
- "Wir alle kennen das Gefühl..."
- Irgendetwas mit "Passion" oder "Leidenschaft"

## 11.6 Schuld-Prinzip

Schuld liegt IMMER beim System, nie beim Leser.
"Es ist nicht deine Schuld, nicht zu wissen wie man das löst."
Formel: Druck aufbauen → Entlasten → Mechanismus zeigen

## 11.7 Asymmetrie-Mechanismus (Pflicht im Ausblick)

Status anerkennen → sofort destabilisieren:
"Du hast bereits [Bestätigung]. Und trotzdem [Defizit]. [Möglichkeit]."

## 11.8 How-to-Verbot

Der Report erklärt nie vollständig wie die Lösung funktioniert. Er zeigt:
- Dass das Problem existiert (konkret)
- Was das echte Problem ist (Umframing)
- Dass es eine Lösung gibt (Named Mechanism, Vogelperspektive)
- Dass andere es gelöst haben (Fallstudien)

Das Wie bleibt für das Erstgespräch.

## 11.9 CTA-Regeln

- IMMER lösungsneutral: "Erstgespräch" — kein Produktname, kein Preis
- Soft-CTA: 1 Satz, alle 2–3 Seiten
- Hard-CTA: nur auf S20 (Rückseite)
- Niemals mehrere Hard-CTAs in einem Report

---

# MODUL 12: SEITENTYP-SPEZIFISCHE COPY-REGELSETS (Agent 4)

## 12.1 Für ST-01 (Cover)

- Max. 600 Zeichen, kein Fließtext
- Headline nach Typ A–E aus Modul 8
- Teaser-Liste: "In diesem Report erfährst du:" + 3–4 Punkte
- Zielgruppe muss im Cover-Text direkt genannt sein

## 12.2 Für ST-02 (Ausblick)

- PFLICHT: Konkreter Einstieg (kein abstrakter Satz)
- PFLICHT: Status anerkennen dann destabilisieren
- PFLICHT: Mindestens ein Selbsttest-Moment oder direkte Konfrontation
- Named Mechanism: kurze erste Erwähnung (Welle 1) — noch nicht erklären
- VERBOTEN: Sofortiger Produktverkauf, abstrakte Eröffnungsthesen

## 12.3 Für ST-05 (Autorität)

- PFLICHT: Kundenzahl + Trust-Anker + Brücken-Satz am Ende
- Brücken-Satz: "Was das, was du auf den nächsten Seiten liest, bedeutet: Es stammt aus der Praxis mit [X] Unternehmen."
- VERBOTEN: Lange Unternehmensgeschichte, Services-Liste

## 12.4 Für ST-06 (Mechanismus)

- Named Mechanism MUSS namentlich eingeführt werden
- Erklärung bleibt Vogelperspektive — max. 30% des Wie
- PFLICHT: Soft-CTA am Ende

## 12.5 Für ST-07A (Fallstudie Einzelseite)

- PFLICHT: Wendepunkt — der konkrete Moment der alles veränderte
- PFLICHT: Ergebnis-Zahlen (Vorher + Nachher + Zeitraum)
- PFLICHT: Kundenfoto-Hinweis in Design-Anweisung
- VERBOTEN: Mehr als 30% Methodenerklärung
- VERBOTEN: Unspezifische Ergebnisse

## 12.6 Für ST-07B (Fallstudien-Gegenseite)

- ABSOLUT VERBOTEN: Jede direkte Referenz auf die gegenüberliegende Fallstudie
- Seite erklärt ein Prinzip, zeigt eine Zahl oder ein Diagramm
- Steht eigenständig

## 12.7 Für ST-08 (FAQ)

- Fragen: wortwörtlich wie ZG sie stellt — nicht diplomatisch umformuliert
- Antworten: direkt, 2–3 Zeilen, kein Ausweichen
- VERBOTEN: Preis, Produktname

## 12.8 Für ST-14/15 (Irrglauben)

- PFLICHT: Zitat muss klingen wie echte Zielgruppe denkt — nicht wie Marketing
- PFLICHT: Erst validieren (Schritt 1), dann zertrümmern (Schritt 2)
- VERBOTEN: Direkt angreifen ohne Validierung

## 12.9 Für ST-32 (Atemseite)

- Max. 15 Wörter total
- Ein einziger Satz oder eine Zahl
- VERBOTEN: Mehr als einen Satz, Fließtext, Diagramme

## 12.10 Für ST-03 (Rückseite)

- Max. 200 Zeichen Fließtext
- URL + QR-Code PFLICHT
- ABSOLUT VERBOTEN: Produktpreis, Angebot, "Kaufe jetzt"

---

# MODUL 13: VOICE-MARKER UND BRÜCKEN-BIBLIOTHEK (Agent 4)

## 13.1 Voice-Marker (min. 2 pro Inhaltsseite)

**Klarstellungs-Marker:**
- "Fakt ist:" | "Die Wahrheit lautet:" | "Seien wir ehrlich:"
- "Das stimmt nicht." | "Das ist kein Zufall." | "Das ist kein Taktikproblem."

**Einordnungs-Marker:**
- "Was ich hier täglich sehe:" | "Was die meisten Unternehmer nicht wissen:"
- "Das ist ein Muster, das sich wiederholt." | "Genau hier liegt der Engpass."

**Konfrontations-Marker:**
- "Du magst denken, aber..." | "Niemand redet offen darüber."
- "Das klingt hart. Ist es auch." | "Das traut sich kaum jemand zu sagen."

**Führungs-Marker:**
- "Dazu gleich mehr." | "Was das für dich konkret bedeutet:"
- "Damit wird klar, warum der nächste Schritt unvermeidlich ist."

## 13.2 Brücken-Bibliothek (Seitenübergänge)

**Bridge zur nächsten Problem-Ebene:**
- "Doch bevor man X löst, muss man verstehen, warum Y entsteht."
- "Aber das ist erst die Oberfläche."

**Bridge zur Lösung:**
- "Die gute Nachricht: Es gibt eine Antwort darauf."
- "Das lässt sich ändern. Und es ist keine Frage von Talent."

**Bridge zu Beweisen:**
- "Wie das konkret funktioniert, zeigt folgendes Beispiel."
- "Kein theoretisches Konstrukt — eine reale Geschichte."

**Bridge zur Handlung:**
- "An diesem Punkt entscheidet sich alles."
- "Wer das versteht, weiß was zu tun ist."

## 13.3 Rhythmus-Pflicht

- Kurze Impuls-Sätze wechseln mit langen Erklärsätzen
- Absolut-Sätze (kurz, kein Weichmacher) für Impact
- Mindestens jede zweite Seite eine Konfliktformulierung
- Jede Seite endet mit Brücke oder Micro-CTA

---

# MODUL 14: QA-MATRIX (Agent 5)

## 14.1 Bewertungsmatrix

| Kategorie | Gewichtung | Mindest-Score für Freigabe |
|-----------|-----------|--------------------------|
| Relevanz | 20% | 14/20 |
| Klarheit | 20% | 14/20 |
| Emotion | 15% | 10/15 |
| Beweisführung | 20% | 14/20 |
| Struktur | 15% | 10/15 |
| CTA-Logik | 10% | 7/10 |

**Gesamt-Schwellenwert:**
- ≥ 80 Punkte: Druckfreigabe
- ≥ 90 Punkte: "Eklige Qualität"
- < 80 Punkte: Revision erforderlich (max. 2 Loops)
- < 70 Punkte: Menschlicher Review durch Richard

## 14.2 Rote Linien (sofortige Disqualifikation)

Unabhängig vom Score:
- Produktpreis im Report genannt → FAIL
- Konkretes Angebot/Paket beschrieben → FAIL
- Mehr als 2 generische Sätze ohne Kontext pro Seite → FAIL
- Fallstudie ohne Zahlen (nur qualitativ) → FAIL
- Cover ohne spezifische Zielgruppe → FAIL
- Hard-CTA auf Rückseite fehlt → FAIL
- Named Mechanism nicht eingeführt → FAIL
- Direkter Rückbezug in ST-07B → FAIL

## 14.3 Vollständige Prüfliste

**FORMAT:**
□ Seitenanzahl ist 16/20/24/28 (4er-Schritt)?
□ Cover + Rückseite korrekt strukturiert?
□ Mindestens 2 Fallstudien mit Zahlen vorhanden?
□ Fallstudien sind Einzelseiten (außer explizit ST-07C)?
□ ST-07B enthält keinen direkten Fallstudien-Rückbezug?
□ Mechanismus vor erster Fallstudie eingeführt?
□ CTA-Kadenz eingehalten (S2/S9/S18/S20)?

**COPY-QUALITÄT:**
□ Keine verbotenen Einstiegsformulierungen?
□ Keine verbotenen Konstruktionen ("Nicht X sondern Y" max. 1×)?
□ Keine Dreiwort-Satz-Ketten (max. 1× als Trick)?
□ Gedankenstriche max. 1× pro Seite?
□ Jeder Satz hat einen der 4 Jobs?
□ Keine Redundanzen zwischen Seiten (Context-Protokoll)?
□ Synonymisierung eingehalten?
□ Keine abstrakten Aussagen ohne Konkretisierung?
□ Keine Buzzwords ohne Nutzen?
□ Symptome als Situationen beschrieben (nicht Konzepte)?
□ Schuld liegt beim System nicht beim Leser?

**INHALT:**
□ Named Mechanism auf min. 2 Seiten referenziert?
□ Min. 6 externe Quellen-Referenzen im Report?
□ Kernthese aus Modul 3.2 trägt den Report?
□ Bewusstseinszustand korrekt getroffen?
□ Asymmetrie-Mechanismus im Ausblick vorhanden?
□ Lösungsneutraler CTA (kein Preis, kein Produktname)?
□ How-to-Verbot eingehalten (max. 30% des Wie)?
□ ST-07B eigenständig (kein Rückbezug)?

**DESIGN-PLANUNG:**
□ Je Doppelseite min. 1 visuelles Element geplant?
□ Min. 4 Diagramme im Report geplant?
□ Alle Diagramme mit Diagramm-Datenpaket (Modul 7)?
□ Atemseite(n) vorhanden (alle 5–7 Seiten)?
□ Foto-Briefing für alle Fallstudien-Seiten vollständig?

---

# MODUL 15: DESIGN-ÜBERGABE-FORMAT (Agent 4 Output)

## 15.1 Vollständiges Seiten-Output-Schema

```json
{
  "seite": 10,
  "seitentyp_id": "ST-07A",
  "seitentyp_name": "Fallstudie Einzelseite",
  "psychologische_phase": 4,
  "copy": {
    "headline": "[Ergebnis-Headline mit Zahl]",
    "subheadline": "[Optional, 5–10 Wörter]",
    "fliestext": "[Vollständiger Fließtext nach Zeichenlimit]",
    "pullquote": "[Stärkster Satz der Seite, 5–15 Wörter, für Design]",
    "soft_cta": "[1 Satz oder null]"
  },
  "design_briefing": {
    "visuelles_hauptelement": "Foto | Diagramm | Grosse-Zahl | Tabelle | Wallpaper",
    "foto_briefing": {
      "motiv": "[Was das Foto zeigen soll — Person/Kontext/Atmosphäre]",
      "stil": "[Professionell-Portrait | Arbeitskontext | Atmosphäre]",
      "emotion": "[Souverän | Entspannt | Fokussiert | ...]",
      "hintergrund": "[Freigestellt | Büro | Branchenkontext]"
    },
    "diagramm_spec": {
      "diagramm_id": "D-01",
      "typ": "[Kreislauf | Balken | Treppe | Flowchart | Matrix | Donut]",
      "titel": "[Kurztitel]",
      "claim": "[These die visualisiert wird]",
      "datenpunkte": [{"label": "[Name]", "wert": "[Zahl]"}],
      "quelle": "[Quelle oder null]"
    },
    "grosse_zahl": {
      "wert": "[z.B. 342.000 EUR]",
      "label": "[z.B. Monatsumsatz nach 8 Wochen]",
      "kontext": "[z.B. Vorher: 28.000 EUR]"
    },
    "layout_hinweis": "Links-Text-Rechts-Bild | Foto-Dominant-Links | Voll-Bild-Hintergrund | Zweispaltig",
    "farb_hinweis": "Hell | Dunkel-Primärfarbe | Akzentfarbe-Akzent",
    "atemseite": false
  },
  "context_update": {
    "neuer_claim": "[Hauptaussage dieser Seite]",
    "verwendeter_beweis": "[Quelle oder null]",
    "haeufige_woerter": ["[Wort1]", "[Wort2]"],
    "soft_cta_gesetzt": false,
    "named_mechanism_referenziert": false
  },
  "qualitaets_selbstcheck": {
    "symptom_als_situation": true,
    "voice_marker_min_2": true,
    "schuld_beim_system": true,
    "saetze_haben_jobs": true,
    "keine_verbotenen_konstruktionen": true,
    "zeichenlimit_eingehalten": true,
    "selbst_check_bestanden": true
  }
}
```

## 15.2 Context-Protokoll zwischen Copy-Calls

```json
{
  "bereits_gemachte_claims": [],
  "bereits_gelieferte_beweise": [],
  "wort_frequenz": {},
  "soft_cta_count": 0,
  "letzter_soft_cta_seite": null,
  "named_mechanism_eingefuehrt": false,
  "named_mechanism_seite": null,
  "named_mechanism_referenz_count": 0,
  "emotionaler_bogen": [],
  "verwendete_seitentypen": []
}
```

---

# MODUL 16: WISSENSDATENBANK-ZUORDNUNG

## 16.1 Was die Wissensdatenbank ist und was sie nicht ist

Die folgenden Dateien sind WISSENSARCHIV — keine Regelwerke:
- DMC_Report_KB_v2.md → Hintergrundwissen, Copy-Mechanismen, Baulig-Analyse
- DMC_Copy_Masterbook_v3.md → Hook-Formeln, Headline-System, Evergreen-Strukturen
- DMC_Intelligence_Layer_v4.md → Style-DNA, Seiten-Vorlagen, Proof-Architektur
- DMC_Final_Intelligence_v5.md → Ausblick-Analyse, Reframing-Formeln, Warmup-Sequenz

Bei Widerspruch zwischen Wissensdatenbank und dieser Master-Datei: Diese Master-Datei gewinnt.

## 16.2 Welcher Agent welche KB-Dateien liest

| Agent | KB-Dateien die als Kontext übergeben werden |
|-------|-------------------------------------------|
| Agent 0 | Nur Master-Datei Module 3, 5 |
| Agent 1 | Master-Datei Module 3, 4 |
| Agent 2 | Master-Datei Modul 6, 7 |
| Agent 3 | Master-Datei Module 8, 9, 10 |
| Agent 4 | Master-Datei Module 11, 12, 13 + KB_v2 Block F (Copy-Regeln) + Masterbook v3 Teil 3 (Grundprinzipien) |
| Agent 5 | Master-Datei Modul 14 |

**Begründung:** Agenten bekommen nur was sie brauchen — nicht die gesamte Wissensdatenbank. Zu viel Kontext verschlechtert die Präzision.

---

# MODUL 17: OFFENE LÜCKEN UND BEKANNTE GRENZEN

## 17.1 Was noch manuell bleibt (Stand v1.0)

1. **Foto-Beschaffung:** KI kann keine Fotos auswählen oder beschaffen. VA wählt aus vorbereiteter Bibliothek anhand des Foto-Briefings (Modul 15.1).

2. **Gamma/InDesign-Workflow:** Wie der Agent-Output in Gamma-Prompts oder InDesign-Templates übersetzt wird, ist noch nicht dokumentiert. Nächster Entwicklungsschritt.

3. **Goldstandard-Beispiele je Seitentyp:** Für präzisere Copy-Kalibrierung fehlen Few-Shot-Beispiele (gut/schlecht) pro Seitentyp. Nach erstem Testlauf ergänzen.

4. **Menschlicher Strategie-Check:** Agent 0 flaggt aber entscheidet nicht final über Kernthese-Qualität. Richard entscheidet bei schwachem Strategie-Gate.

5. **Feedback-Loop nach Testlauf:** Erste Reports manuell auswerten → Prompts nachschärfen → v2.0 dieser Master-Datei.

## 17.2 Nächste Entwicklungsschritte

1. Testlauf mit echtem Kunden (manuell, ohne n8n)
2. 2–3 Seitentypen nachschärfen auf Basis des Testlaufs
3. Gamma-Prompt-System für Cover und Signature-Seiten
4. InDesign-Baukasten-Spec für Freelancer
5. Goldstandard-Beispiele aus erstem echten Report extrahieren
6. n8n-Workflow technisch aufsetzen

---

*DMC-Report Master System v1.0*
*Erstellt: 2026 | Gilt für alle Agenten als einzige Regelquelle*
*Nächste Version: Nach erstem Testlauf mit echten Kundendaten*
