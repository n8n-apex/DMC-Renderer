# Missing source authorities

The copy-law Word document, Luka Martic report, and Frese Recruiting v2 report
are unresolved primary authorities. Transcriptions and derived notes are useful
but are not substitutes for the original bytes.

On recovery:

1. Put the file under `refs/source-authorities/`, never in Downloads.
2. Hash it before interpreting it.
3. Record its relative path and SHA-256 in `manifest.json` and change only that
   authority’s status to `recovered`.
4. Run `reconcile.py`. For copy law, retain the line-level differences against
   the writer prompt and handoff transcription. Do not silently edit policy.
5. For PDFs, create a new atlas version. Do not replace or rewrite the 120-face
   v1 evidence set.
