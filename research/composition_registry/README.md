# DMC Composition Registry

The registry turns observed Richard page families into versioned composition
contracts. A family states what editorial job it can perform, what evidence and
assets it can carry, how much content each named region can contain, and where
the family is known to fail.

`families/dmc-v1.json` is the production input. `golden/manifest.json` pins its
canonical content hash and every family-version hash. A family may change only
through a new version and an intentionally regenerated manifest.

The initial ten families are grounded in exact faces from
`research/reference-atlas/reference-atlas.json`. Their geometry and typography
are bounded hypotheses. Phase Two capacity calibration measures those bounds;
it does not silently rewrite this registry.
