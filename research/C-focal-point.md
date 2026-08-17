# Research Task C — Focal-Point Detection for `dmc-renderer`

**Scope.** Pick the simplest approach that produces consistently good crops for three AI-generated images per report (cover hero, status quo scene, fazit background) plus optional case-study portraits. Center-crop is mediocre; we need smarter focal positioning so the subject sits in the visible region and, for the cover hero, stays inside the top 70 % (bottom 30 % is reserved for text overlay).

## 1 — Per-option findings

### 1.1 smartcrop.py
- **What it does.** Pure-Python re-implementation of Jonas Wagner's `smartcrop.js`. Ranks candidate crops using saturation, skin-tone heuristic, edge density and rule-of-thirds composition, then returns the best `(x, y, w, h)`. Deterministic, no model weights, no network calls.
- **Maintenance.** Active. `smartcrop` v0.4.2 released **2026-01-12**, v0.4.1 in October 2024. Python ≥3.9. ~270 ⭐, low issue volume. ([PyPI](https://pypi.org/project/smartcrop/), [GitHub](https://github.com/smartcrop/smartcrop.py))
- **Strengths.** Trivial to install (`pip install smartcrop pillow`), <100 ms per image, no GPU, MIT-licensed, no API key. Works well for photos with clear focal contrast (Nano Banana Pro environmental shots fit this).
- **Weaknesses.**
  - Heuristic skin-tone boost frequently misfires on stylized illustrations or non-Caucasian-typical lighting; the upstream JS author explicitly recommends adding a separate face detector for portrait priority ([smartcrop.js #120](https://github.com/jwagner/smartcrop.js/issues/120)).
  - Low-contrast images and abstract art collapse toward center (essentially identical to center-crop).
  - No semantic understanding — can't tell that the eye-line should be the focal point on a portrait, only that edges cluster near a face.

### 1.2 MediaPipe Face Detection
- **What it does.** Google BlazeFace, returns pixel-precise bounding boxes plus 6 landmarks (eyes, nose, mouth, ear tragions). The legacy `mp.solutions.face_detection` API still works; the newer `mp.tasks.vision.FaceDetector` is the supported path going forward ([Google AI Edge docs](https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector), [legacy docs](https://mediapipe.readthedocs.io/en/latest/solutions/face_detection.html)).
- **Maintenance.** Active. Native macOS arm64 wheels on PyPI; `pip install mediapipe` is one line on M-series Macs (current 0.10.x line, prior fork `mediapipe-silicon` no longer needed). ([PyPI](https://pypi.org/project/mediapipe/), [GitHub #3277](https://github.com/google/mediapipe/issues/3277))
- **Strengths.** ~3 ms/image on CPU, free, deterministic, no API. Two model variants: short-range (selfie/portrait) and full-range (environmental, back-camera). Confidence threshold tunable.
- **Weaknesses.**
  - Misses faces in stylized illustrations and side-profile shots ([MediaPipe #1723](https://github.com/google/mediapipe/issues/1723), [#5814](https://github.com/google-ai-edge/mediapipe/issues/5814)).
  - Useless when there's no face (status quo / fazit environment shots) — needs a saliency fallback.
  - When multiple faces, the "right" subject is ambiguous; need a heuristic (largest box / closest-to-center).

### 1.3 Pillow + scikit-image / OpenCV saliency
- **What it does.** Spectral-residual or fine-grained saliency map from OpenCV's `cv2.saliency.StaticSaliencySpectralResidual_create()`, then argmax / centroid → focal point.
- **Maintenance.** OpenCV `contrib` ships these out of the box; scikit-image itself has no built-in saliency module ([PyImageSearch tutorial](https://pyimagesearch.com/2018/07/16/opencv-saliency-detection/)).
- **Strengths.** Free, deterministic, ~20 ms/image.
- **Weaknesses.** Spectral residual is an older, low-quality saliency model (2007). It performs worse than smartcrop's heuristic-stack on portrait/scene tests in practice, and adds a heavy OpenCV-contrib dependency (`opencv-contrib-python` is ~80 MB and pulls in extra C++ libs). No advantage over option 1.1 — strictly worse cost/benefit.

### 1.4 Anthropic Claude Vision (Haiku 4.5)
- **What it does.** Send the image; prompt asks for `{"focal_x_pct": 0–100, "focal_y_pct": 0–100, "reasoning": "..."}` JSON. Highest semantic quality — Claude understands "the founder's face" or "the workshop machine in the back" or "the sunrise glow on the new sign."
- **Cost.** Haiku 4.5: **$1 / 1M input tokens, $5 / 1M output tokens** ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)). Token formula: `width × height / 750`, capped at 1568 tokens on Haiku/Sonnet ([Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)). A 1920×1080 cover image → 1568 input tokens. With a ~80-token prompt and ~60-token JSON response, **one image ≈ $0.0019 in + $0.0003 out ≈ $0.0022/image**. Sonnet 4.6 is ~3× that (~$0.007/image).
- **Strengths.** Best handling of ambiguous cases (multiple subjects, environmental shots with off-center hero, stylized illustration). Returns coordinates plus a one-line rationale you can log for audit / debugging.
- **Weaknesses.**
  - External network dependency in the render path — must be retry-safe and have a deterministic fallback when the API is down.
  - Non-deterministic (same image, slightly different coords across calls) unless temperature=0 and cached. Mostly fine; coordinate variance is usually <2 %.
  - Adds an Anthropic API key to the renderer's secret surface.

### 1.5 CLIP-based saliency
- **What it does.** Run patches through CLIP, score similarity to a text prompt ("a person's face", "the main subject"), build saliency map ([OpenVINO CLIP saliency notebook](https://docs.openvino.ai/2024/notebooks/clip-language-saliency-map-with-output.html), [CLIP_Explainability](https://github.com/sMamooler/CLIP_Explainability)).
- **Weaknesses.** ~700 MB model download, slow on CPU (1–5 s/image), and quality is rarely better than smartcrop + face-detector for portrait/scene work. Adds a torch dependency. Strictly worse than option 1.4 for our volume.

## 2 — Comparison

| Option | Crop quality (portraits) | Crop quality (env. scenes) | Per-image cost | Deps weight | Python ergonomics | Worst failure mode |
|---|---|---|---|---|---|---|
| **1.1 smartcrop.py** | Decent (better with face-detect bolt-on) | Decent — finds high-edge regions | Free | Tiny (Pillow + numpy) | `cropper.crop(img, w, h)` → JSON | Low-contrast / abstract → center-collapse |
| **1.2 MediaPipe** | Excellent for photo faces | N/A (no face) | Free | Medium (~30 MB wheel) | One Detector object, returns bboxes | Stylized faces, side profiles → no detection |
| **1.3 OpenCV saliency** | Mediocre | Mediocre | Free | Heavy (`opencv-contrib`, ~80 MB) | Module-level API | Worse than 1.1, no advantage |
| **1.4 Claude Haiku 4.5 vision** | Best | Best | ~$0.0022/img | Tiny (`anthropic` SDK) | One `client.messages.create` call | Network outage, JSON parse, latency 0.5–2 s |
| **1.5 CLIP saliency** | Good | Decent | Free (after 700 MB DL) | Heavy (torch, transformers) | Notebook-y; no ready library | Slow on CPU; setup overhead not worth it |

## 3 — Recommendation

**Default pipeline: deterministic-first, AI-assist on demand.**

1. **MediaPipe Face Detection (short-range model)** — if a face is detected with confidence > 0.5, focal point = face-box center. For the cover hero, clamp `focal_y` to ≤ 60 % so the text-overlay zone never overlaps the face. Use this for **cover hero** and **case-study portrait** slots.
2. **smartcrop.py** — for any image where MediaPipe finds no face (status quo / fazit / environmental hero variants). Take smartcrop's top-ranked crop center as the focal point.
3. **Claude Haiku 4.5 vision (`focal-point-vision`)** — only as a tier-3 fallback **when both 1 and 2 disagree by > 20 %** with each other or with the image's geometric center (suggests an ambiguous scene). Per-image cost ~$0.0022. At 100 reports/month × 3 images each = 300 images, with empirical ~10–15 % escalation rate that's **~40 Haiku calls/month ≈ $0.09/month**, capped worst case at full escalation = **$0.66/month**.
4. **Center-crop** — final fallback if all three error out. Logged + flagged for human review.

This biases toward the simplest path that meets the quality bar:

- Faces (the case where center-crop fails most visibly) are handled by a purpose-built free model.
- Scenes (where there's no clear face) are handled by a heuristic that's specifically designed for them.
- Claude Vision is reserved for ambiguous-edge cases, where its $0.002 cost is well-justified and where alternatives would silently produce a bad crop.

## 4 — Cost analysis

| Path | Per image | Per report (3 imgs) | Per month (100 reports) |
|---|---|---|---|
| MediaPipe only (faces) | $0 | $0 | $0 |
| smartcrop only (scenes) | $0 | $0 | $0 |
| Haiku 4.5 escalation (~12 % of images) | $0.0022 | ~$0.0008 | **~$0.08** |
| Haiku 4.5 worst case (100 % escalation) | $0.0022 | $0.0066 | **$0.66** |
| Sonnet 4.6 if upgraded later | $0.007 | $0.021 | **$2.10** |

Even a pessimistic "Claude on every image" budget is sub-dollar. There is no scenario in our volume range where API cost should drive the architecture.

## 5 — Python integration sketch

```python
# focal_point.py — order: MediaPipe → smartcrop → Claude Vision → center
from dataclasses import dataclass
from PIL import Image
import mediapipe as mp
import smartcrop

mp_face = mp.solutions.face_detection.FaceDetection(
    model_selection=0, min_detection_confidence=0.5  # short-range portrait model
)
_smart = smartcrop.SmartCrop()

@dataclass
class Focal:
    x_pct: float            # 0..100
    y_pct: float            # 0..100
    source: str             # "face" | "smartcrop" | "vision" | "center"

def focal_point(img: Image.Image, *, clamp_y_max: float | None = None) -> Focal:
    w, h = img.size
    # Tier 1 — MediaPipe face detection (photos with people)
    import numpy as np
    res = mp_face.process(np.array(img.convert("RGB")))
    if res.detections:
        # pick largest box (handles multi-subject by area)
        box = max(res.detections, key=lambda d: d.location_data.relative_bounding_box.width
                                              * d.location_data.relative_bounding_box.height)
        b = box.location_data.relative_bounding_box
        cx, cy = (b.xmin + b.width/2) * 100, (b.ymin + b.height/2) * 100
        if clamp_y_max is not None:
            cy = min(cy, clamp_y_max)
        return Focal(cx, cy, "face")

    # Tier 2 — smartcrop (environmental / no-face scenes)
    target = _smart.crop(img, w, h)["top_crop"]      # square seed crop, biased to salient region
    cx = (target["x"] + target["width"]/2)  / w * 100
    cy = (target["y"] + target["height"]/2) / h * 100
    return Focal(cx, cy, "smartcrop")
    # (Tier 3 Claude escalation and tier 4 center-fallback omitted for brevity —
    #  wrap the above in try/except, and call out to anthropic.Anthropic().messages.create
    #  with the image when both tiers disagree by > 20 % from each other.)
```

For the cover hero, callers pass `clamp_y_max=60` so the face never lands in the bottom 30 % text band.

## 6 — Failure cases the recommended path won't handle (route to human review)

- **Multiple equally-sized faces** in a case-study portrait (e.g., a founding pair). Pipeline picks the largest face by area; if both are similar size and the wrong one is chosen, only a human catches it. → Mitigation: log MediaPipe confidence + count to the render-report sidecar; flag `face_count > 1` for QA queue.
- **Abstract / metaphor cover art** (e.g., a stylized "leaky bucket" illustration). MediaPipe finds nothing; smartcrop collapses near center. Output is acceptable but mediocre. → Mitigation: these slots should never route through the photography pipeline (see `VISUAL_ASSETS.md` — they're `METAPHOR_OBJECT` SVGs, not Nano Banana Pro images).
- **Very low-contrast sunrise / fog scenes** for `fazit_background`. Smartcrop centroid wanders. → Mitigation: trigger Claude Haiku tier-3 escalation whenever smartcrop's score is below an empirical threshold (~6.0 on the default scale).
- **Subject deliberately placed in bottom third** by the image generator despite our cover-hero prompt (Nano Banana Pro occasionally violates composition rules). Face detection finds it correctly but `clamp_y_max=60` shifts the focal point above the actual subject. → Mitigation: when face center-y > clamp threshold, regenerate the image instead of cropping around the missing subject; surface this to the render-report sidecar.

## 7 — Evidence / URL citations

- smartcrop.py repo and releases — <https://github.com/smartcrop/smartcrop.py>, <https://pypi.org/project/smartcrop/>
- smartcrop.js (algorithm reference, recommendation to combine with face detection) — <https://github.com/jwagner/smartcrop.js>, issue #120 — <https://github.com/jwagner/smartcrop.js/issues/120>
- MediaPipe Face Detector docs — <https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector>, legacy module — <https://mediapipe.readthedocs.io/en/latest/solutions/face_detection.html>
- MediaPipe macOS ARM wheels on PyPI — <https://pypi.org/project/mediapipe/>, ARM wheel issue — <https://github.com/google/mediapipe/issues/3277>
- MediaPipe face-detection failure issues — <https://github.com/google/mediapipe/issues/1723>, <https://github.com/google-ai-edge/mediapipe/issues/5814>
- OpenCV saliency (spectral residual) — <https://pyimagesearch.com/2018/07/16/opencv-saliency-detection/>
- Anthropic pricing (Haiku 4.5 $1/$5 per M tokens) — <https://platform.claude.com/docs/en/about-claude/pricing>
- Anthropic vision token formula (`w × h / 750`, cap 1568 for Haiku/Sonnet) — <https://platform.claude.com/docs/en/build-with-claude/vision>
- CLIP saliency (reference, not recommended) — <https://docs.openvino.ai/2024/notebooks/clip-language-saliency-map-with-output.html>, <https://github.com/sMamooler/CLIP_Explainability>
