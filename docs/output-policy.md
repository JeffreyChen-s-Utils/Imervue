# Output entry-point audit

| Entry | Conflict and source replacement | Metadata / colour | Durable result |
|---|---|---|---|
| Single Export | Explicit existing-file/source confirmation; replace transaction | Shared selectable all/no_location/none; sRGB ICC except none | Background Jobs output/error; retry in originating dialog |
| Batch Export | Shared rename reservation, including across windows | Same selectable policy; default no_location | Background Jobs, failed-only retry, full JSON and file links |
| Batch Convert | Shared rename, including same-format conversion | Preserve descriptive EXIF/location and normalized sRGB ICC | Background Jobs; skipped sources in full JSON; retries keep originals |
| Per-image CLI including bridged writers | Deterministic unique cohort destinations; skip default; --overwrite/replace explicit source consent; optional rename/skip/replace | Legacy encoder unchanged by default; explicit --export-metadata uses shared policy; strip always none | Ordered stdout/errors; --result-report JSON with committed file URI; Ctrl+C exit 130 and partial report |
| CLI collage/anaglyph | Explicit chosen destination, unique same-format stage | Composite sRGB pixels; no copied per-source EXIF | Printed final output after commit |
| PDF contact/shortcut sheets | Explicit chosen destination; unique atomic stage | Composite document, no per-image metadata policy | Existing dialog success/error after complete painter shutdown |
| MP4 slideshow | Explicit chosen destination; same-suffix atomic stage | Composite video sRGB frames, no per-image EXIF | Error for no decodable frames; prior video preserved |
| Web gallery | Original copies renamed through shared reservation; thumbnails/index individually atomic | Original bytes/metadata preserved; sRGB JPEG thumbnails omit source metadata | Existing index link after publication; missing/bad thumbnails logged and skipped |

Reservations are process-wide, not an interprocess lock. Atomic replacement prevents partial
files on encoder failure or cooperative cancellation; it is not a power-loss durability claim.
Completed commits survive later cancellation. GUI conversion's optional original deletion remains
an explicit recycle-bin action after successful conversion; global retries keep originals.
A gallery directory is not a single atomic transaction. PDF/video results continue using their
existing dialogs; the image job panel does not promise a composite export retry adapter.
Explicit CLI metadata may re-encode lossy images and change byte size, including optimize outputs;
the default encoder/budget remains unchanged. Metadata and ICC are stored only where the codec
supports them (BMP has no EXIF). RGB ICC on grayscale output requires RGB/RGBA conversion.
EXIF orientation, obsolete pixel dimensions and maker notes are never copied to edited output.
