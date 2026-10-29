# Puppet canvas next-stage assessment

Read-only assessment of puppet/canvas.py for the complete runtime complexity repair. No source edits or tests accompanied this assessment.

Repeated parameter mutation is the strongest consolidation candidate. Single, ordinary batch and forced batch setters repeat key filtering, conversion and recompute/redraw, but differ in no-op behavior. Single updates recompute even when equal; ordinary batches skip equal values; forced batches recompute for any known key. Preserve partial mutation when a later conversion raises. Expression layering is also repeated between rig evaluation and physics input.

Cohesive owners are Qt identity/state, document binding and parameters, rig evaluation caches, physics clock, expressions/pose, mesh editing, pointer/view transforms, GL state/FBO ownership and frame orchestration. Keep canvas_render.py as the existing drawing/cache owner rather than transferring excessive complexity there.

Pin these contracts before extraction:

- Document/draw-list assignment precedes texture/buffer invalidation under a current context. Reset parameters, expression/pose and physics before recompute, signals and redraw.
- Expressions feed physics; physics outputs override expression-adjusted values in rendering. Pose/part visibility applies even without parameters. Getters return copies.
- Physics uses fixed steps, elapsed caps and fractional lag. Redraw uses the existing output-key/value threshold; timer activation needs visibility and chains.
- Re-selecting a valid pose still recomputes/emits. Duplicate expressions do not. Successful mesh moves rebuild commands; pointer routing prioritizes pan, mesh drag, then cursor signals.
- Reject invalid offscreen sizes before context acquisition. Failed binding, zero-sized documents and draw/readback exceptions must release resources. Destroy FBO before doneCurrent, retain depth-stencil attachment and restore clear colour, viewport and matrix stacks.
- Offscreen rendering excludes checker, selection overlay and pet shadow. Pet construction restores the temporary default surface format even on failure and retains per-widget translucency/cache state.
- Preserve cursor-anchored zoom and DPR fitting conventions.

Existing canvas, init-state, physics, render-state, fitting, render and mesh-cache tests provide starting coverage. Add baseline traces for parameter conversion/equality/unknown/NaN inputs, signal and recompute counts, expression/physics precedence, timer transitions, document invalidation order and every FBO failure path. Mocked GL checks cannot certify actual rendering/resource destruction; require existing headless Linux Mesa CI in addition to offscreen local tests. Preserve PuppetCanvas, offscreen_framebuffer_format and consumed helpers. Update stale static-rendering docstrings when implementing this unit.
