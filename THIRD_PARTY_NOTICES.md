# Third-party notices

## LittleCMS generated sRGB test profile

File: `research/postprocessor/tests/fixtures/srgb.icc`

Purpose: automated print-profile tests only. It is not a production printer profile.

Source method: generated locally with Pillow 12.2.0 by wrapping `PIL.ImageCms.createProfile("sRGB")` in `PIL.ImageCms.ImageCmsProfile` and serializing `tobytes()`. Pillow reports LittleCMS version 2.18 for this build. No operating-system ICC file was copied.

Upstream source: https://github.com/mm2/Little-CMS

Upstream license: MIT, copyright 2023 Marti Maria Saguer. The authoritative license is https://github.com/mm2/Little-CMS/blob/master/LICENSE.

SHA-256: `acc4bc8644423b5f69649dab843dc8f64def4c1f5e9d602bf8d63acf5f2458c0`

## TypeUI

Selected files under `research/design_policy/vendor/typeui/` are from
https://github.com/bergside/typeui at commit
`2a977f1f6616ae8a5ea84a478ca35601c67f4322`.

Selected editorial files under
`research/design_policy/vendor/typeui-public-registry/` are from the public
TypeUI registry at https://github.com/bergside/awesome-design-skills, commit
`f631a09b4fcc0166f2e2c1a8c81906ef680c57e8`.

Both are MIT licensed. The complete license snapshots are retained beside the
selected files. Paid and premium TypeUI content is excluded.

## Designer Skills

Selected files under `research/design_policy/vendor/designer-skills/` are from
https://github.com/Owl-Listener/designer-skills at commit
`acc3e574b36ef2895268a176dbae886e1b845ae0`.

The source is MIT licensed, copyright 2026 MC Dean. The complete license text is
stored at `research/design_policy/vendor/designer-skills/LICENSE`.
