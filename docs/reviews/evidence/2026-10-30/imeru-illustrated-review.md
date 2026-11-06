# Illustrated Imeru verification

Reviewed archive SHA256:
`2C77C4164ADAFF4FFE4BB7A1C4FE9DB9F2950965187B7EE5F42E36992A51F612`.

The model uses the original transparent illustration plates directly as
textures. Its 23 drawables include continuous body/head/hair and sleeve meshes,
facial details, hand alternatives and invisible interaction regions. Standard
input controls, eight motions, seven expressions and the pet script remain
available. The canvas is 1024 × 1664, including motion margins above and below
the 1024 × 1536 source artwork.

The production OpenGL renderer captured 74 poses and motion samples plus 81
wave animation frames. Inspection covered neutral, both waves, combined lean
and wave, gaze extremes, blinking while turned, mouth movement and expressions.
Solid-background captures distinguish visible edges from RGB values stored in
transparent pixels. The tracked neutral and wave PNG previews use these native
solid-background renders; the animated WebP retains transparency.

The initial illustrated candidate let the sleeve's elbow weights pull the
orange ribbon across the ivory elbow. The final source contour assigns the
ribbon and its boundary grid vertices to the shoulder. The final opposite-arm
wave has no orange slash across the sleeve. Added canvas margins prevent the
crown from being clipped during combined motion.

An independent source and visual review found no remaining blocking issues.
Regression checks cover original texture bytes, connected sleeves, both waves,
eye closure and gaze, mouth and cheek controls, fixed feet during breathing,
mesh orientation, head/body clicks, ribbon attachment and posed canvas bounds.
The focused suite passed 46 tests. The ten-language documentation parity check
passed 22 tests. Schema validation returned no issues, and Ruff passed.

All captures used an offscreen context with no visible window creation or
injected desktop input. The final foreground window observations matched.

The full offscreen suite passed 17,828 tests with 1,436 skips and 9 warnings in
1,370.06 seconds. The first completed run had one failure in the unrelated folder
scan test's 80 ms timer wait. All 12 folder scan tests passed immediately in
isolation, and the full rerun passed without changes to that code or test.
Both run receipts are retained here. GUI skips are separate from the native
OpenGL verification above. Bandit reported no issues.
