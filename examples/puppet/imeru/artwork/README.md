# Imeru illustration sources

The four PNG files are stored source artwork, not runtime downloads. The builder
references their original pixels through authored UV meshes. Transparent pixels
can retain colored RGB values; their alpha channel controls visibility.

The original design brief is in
[`../concepts/modern-design-brief.md`](../concepts/modern-design-brief.md).
The following edit prompts produced the animation plates from that design.

## Master cutout

Use the provided image as the exact edit target, not loose inspiration. Preserve
this entire adult modern-anime female character, her exact design, face,
hairstyle and rich hair volume, intricate outfit, pose, body proportions, fabric
folds, hands, accessories and boots. Remove ONLY all background, including every
dark gradient, colored haze, glow and shadow behind her. Output the single
complete character as a clean production cutout on genuinely fully transparent
alpha background. Preserve fine outer hair strands and clothing edges with
smooth alpha. No surrounding colored aura, no floor shadow, no background
remnants, no new props, no redesign, no panel layout. Full body and boots
entirely inside the canvas with margin; keep original front-facing relaxed
arms-out pose. This polished illustration will become the actual textured
source of an animated Puppet, so the original coherent detailed anime artwork
must be preserved.

## Hidden underpainting

Precise production image edit for animation hidden underpainting. Input is exact
master character, maintain identical canvas 1024x1536, scale, placement, head
position, hair silhouette, body posture and all unchanged pixels as closely as
possible. Output ONE full-body underlying character plate in the SAME location,
transparent background, NOT a sprite sheet, NO rearrangement. Make only these
two edits: (1) Remove both complete arms including sleeves, cuffs, hands and
attached sleeve ornaments from shoulder seams downward, leaving transparent
space where these arms were. Reconstruct the small naturally occluded jacket
side edges and shoulder attachments as needed, preserving the entire torso
jacket, neckline, belt, shorts, long side sash, legs and boots EXACTLY. Preserve
ALL flowing hair, including strands that had overlapped the sleeves. (2) On the
face only, erase both eyes including irises, lashes, brows and erase the mouth
line, filling those tiny regions with smooth matching face skin and the
original soft facial shading. Preserve face outline, nose, cheeks, ears,
earrings, hairline and hair EXACTLY. This is an INTERNAL animation underlay, so
a blank facial skin plate and armless torso are intentional; moving full
illustrated arms and original eyes/mouth are composited back at runtime. Do not
alter outfit design, do not shorten or thin the hair, do not change overall
artwork quality, do not add seams or new shadows. Keep true transparent alpha
outside retained artwork, no background glow or haze.

## Alternate facial details and hands

Precise image edit for alternate animation details. Preserve the exact provided
modern anime character illustration at the same 1024x1536 canvas, same scale,
same pose, same placement of head, face, body, wrists, all clothing, hair,
accessories and boots. Edit ONLY: (1) both eyes naturally closed in gentle
relaxed anime eyelids with elegant curved eyelash lines, not squeezed grimaces,
eyebrows remain natural; (2) mouth slightly open for speaking, a small natural
anime mouth opening with dark warm interior and subtle tongue/lower lip, no
exaggerated large smile; (3) both hands have open palms facing the viewer with
five naturally separated fingers each, attached at EXACTLY the existing wrist
position with fingers generally pointing downward in the current relaxed
arms-down pose. Do not raise or move the arms, wrists or elbows. Everything
else matches the master. This image supplies tiny alternate eyelid, mouth and
hand regions for the same animated Puppet. Keep full detailed flowing hair,
original refined face, fabric folds and shading. Transparent alpha background,
no haze, glow, shadow, scenery, labels or sprite-sheet panels. Produce one full
character in place.

## Complete arms

Exact animation asset extraction/edit from this master character. Preserve the
same 1024x1536 canvas and EXACT original arm and hand scale, coordinates, pose,
clothing, colors, linework, fabric folds, wrist positions and detailed shading.
Output ONLY the TWO COMPLETE ARMS from rounded shoulder roots through the
fingertips in their original locations. Remove every other element: ALL head,
hair, neck, torso, jacket torso panels, shorts, sash, legs and boots. All removed
regions must be truly transparent alpha. Inpaint only the small portions of the
upper sleeves and shoulder roots previously hidden by the hair or torso jacket,
reconstructing the same sleeve fabric smoothly. The viewer-left arm wears the
dark teal gathered sleeve, brass shoulder ring and gold-trimmed cuff; the
viewer-right arm wears the ivory gathered sleeve, dark/brass ring, rust-orange
ribbon ornament and cuff. Keep each entire arm as one visually continuous
natural sleeve with a relaxed hand, no transverse elbow line, no seam separating
upper/forearm. Do not change the relaxed fingers. Keep shoulder roots at about
original x410,y275 and x625,y275 and wrists about x260,y670 and x770,y670,
matching the input more exactly than these approximate coordinates. Do not move
or rotate arms. Do not arrange a sprite sheet or bring the arms together. No
remaining hair attached to sleeves. No glow/haze/shadow/background. This is a
precise hidden-overlap source for assembling the same original illustration
seamlessly.

The resulting arm plate uses a larger layout than requested. The builder
registers its shoulder and wrist landmarks to the master coordinates, without
resampling or repainting the source PNG.
