# Recipe next-stage assessment

Source inspection of image/recipe.py identified real duplication in optional extra-effect application. Levels, channel mixer, gradient map, lens flare and film grain each check extra data, import their implementation lazily, decode options, then catch the same apply errors and report a stage-specific warning. A shared adapter can remove repeated decisions only if it preserves import and decode timing and the exception boundary. Option decoding currently occurs outside the apply-error handler. Split toning, threshold/posterize, masks, layers and LUT have distinct policies and must not be forced into the same adapter.

Candidate responsibilities are the Recipe data model, identity predicates, normalization/serialization/hash, stage orchestration, ordinary pixel adjustments, optional effect adapters, content identity/cache, and geometry-following file rotation. This is a design candidate, not a completed or measured reduction.

Contracts to retain:

- Identity apply returns the original array before shape/dtype validation, despite the broad docstring allocation claim. Nonidentity apply validates HxWx4, converts dtype and normalizes before running stages.
- Stage order is fixed in STAGE_NAMES. Partial execution uses inclusive named bounds and preserves Python slice behavior when the last stage precedes the first. Unknown names raise ValueError.
- normalized constructs Recipe directly, while from_dict constructs cls. Curve conversion and crop coercion differ across those two paths. Unknown input fields enter extra and missing exif_oriented defaults to False for old saved recipes.
- Hashes are empty for identity recipes. Otherwise normalized sorted compact JSON feeds nonsecurity MD5 truncated to sixteen characters. Preserve exact hashes and serialization rather than only pixel output.
- ImportError skips optional effects. Most decode errors propagate because decoding is outside the application catch. Threshold/posterize retains threshold output if posterize fails. LUT catches OSError/ValueError, unlike the TypeError/ValueError handling of other effects.
- Neutral stages return the input object. Pixel stages preserve alpha, clipping and quantization order. File rotation refuses positioned extras and unoriented recipes, exchanges flip axes and transforms crop in the rotated frame.
- Content identity samples first/middle/last 4096 bytes with a salt and size, also returns the legacy first-chunk digest, and caches by path plus mtime_ns/size. Stat/read failures return empty identities. Preserve recipe-store migration and cache clearing.

Tests in test_recipe.py, test_recipe_store.py and recipe adjustment tests already cover stage order, partial stages, hashes, identity sampling and rotation. Add baseline/candidate pixel and object-identity comparisons, malformed option/import/apply exception traces, exact serialized/hash fixtures, and file-cache invalidation/migration cases. Preserve Recipe, STAGE_NAMES, file_identity, file_identities, clear_identity_cache and turned_with_file imports. This assessment ran no tests and makes no hosted-score claim.
