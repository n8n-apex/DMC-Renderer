# Blind rating kit v1

This kit decides the final acceptance criterion: whether the system's pages
hold up against Richard's, judged blind. Nothing in the pipeline can pass
this gate except real human ratings.

## Protocol

1. **Two raters, independently.** No discussion before both are done. Each
   rater needs their own `rater_id` (e.g. `rater.utkarsh`, `rater.<name>`).
2. **Do not open `KEY-DO-NOT-OPEN-BEFORE-RATING.json`.** It maps images to
   their cohort (Richard's pages vs the system's). Opening it breaks the
   blind and voids the run.
3. Look at each image in `faces/` (`face-01.png` … `face-40.png`) at full
   size. Score all eight dimensions from 1 (far below professional standard)
   to 5 (indistinguishable from a top designer's page), then an `overall`.

## The eight dimensions

| Dimension | Question to answer |
|---|---|
| `hierarchy` | Does one clear reading order lead the eye? |
| `composition` | Does the page hold together as one designed whole? |
| `typography` | Is the type setting confident — scale, weight, spacing? |
| `rhythm` | Do text blocks and devices alternate with intent? |
| `density` | Is the page satisfying to read — full but not crowded? |
| `proof_visibility` | Does evidence (figures, quotes, logos) land visibly? |
| `mechanism_clarity` | Is the page's argument device understandable at a glance? |
| `brand_coherence` | Does the page feel like one brand made it? |

## Recording ratings

Append one JSON line per image per rater to
`research/quality_loop/calibration/ratings.jsonl`, exactly in this shape
(the schema is `research/quality_loop/calibration/ratings.schema.json`;
`face_image_sha256` for each image is in the sealed key file — fill it in
AFTER both raters finish, when unsealing the key):

```json
{"rater_id": "rater.utkarsh", "cohort": "<from key after unsealing>", "face_image_sha256": "<from key>", "rubric_version": "3.0", "scores": {"hierarchy": 4, "composition": 4, "typography": 3, "rhythm": 4, "density": 4, "proof_visibility": 5, "mechanism_clarity": 4, "brand_coherence": 4}, "overall": 4, "rated_at": "2026-08-07T12:00:00+00:00"}
```

Practical flow: rate on paper or in a spreadsheet against the image NAMES,
then unseal the key and merge cohort + sha256 into the rows mechanically.

## What happens afterwards

`derive_visual_threshold_policy` (research/quality_loop/reference_rubric_v3.py)
consumes the rows, derives the threshold (reference mean minus pooled
standard deviation, dataset and code hashes recorded), and produces the
policy for the owner's named approval. Ship-ready release evidence then
requires that approved policy's hash. No step of this can be faked; the
guards reject fabricated rows, single raters, and missing cohorts.
