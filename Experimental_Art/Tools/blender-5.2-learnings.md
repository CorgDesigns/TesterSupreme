# Blender 5.2 & s&box — things we've looked up

Running log of Blender 5.2 and s&box questions that came up while working through the art-direction plan. Check here first before re-searching; fall back to `blender-manual-5.2/` or `sbox-docs/` (grep them) or the web if it's not covered yet.

---

### Does s&box's Lit material accept object-space normal maps?

No — confirmed tangent-space only. `sbox-docs/docs/rendering/shaders/material.md` declares the shader input as `float3 TangentNormal` (plus `WorldTangentU`/`WorldTangentV` for the tangent basis), and the default vertex input stream carries a `TANGENT` semantic. Their own `HeightToNormal` texture-processor attribute explicitly outputs "tangent-space RGB normal map." No object-space path found anywhere in the docs.

Implication: an object-space bake/paint (like the render.recipes-style workflow) needs converting before use in s&box — re-bake it (Bake Type: Normal, Space: Tangent) onto a second image while the object-space map is still wired into the material's Normal input. Blender re-derives the tangent-space result from the currently-shaded normal, so this captures the painted result without repainting.

Source: `Tools/sbox-docs/docs/rendering/shaders/material.md`, `docs/rendering/shaders/reference/default-vertex-and-pixel-shader-inputs.md`, `docs/rendering/shaders/attributes-and-variables.md`.

---

### Can the mesh be decimated after painting the normal map, without losing detail?

Yes — confirmed by direct comparison (20k-tri sphere vs. decimated-then-shade-smooth ~2k-tri version looked equivalent). This is expected: once a tangent-space normal map is baked, the stroke detail lives in texture pixels, not mesh density — that's the entire point of the standard "sculpt high, bake to low" game-art pipeline. Workflow that worked: subdivide (1–2 levels) → paint the object-space normal map → bake to tangent-space → Decimate the same mesh → Shade Smooth. No need for a separate high/low object pair (selected-to-active) for a simple, non-retopologized shape like a sphere — decimating in place is enough.

### Do UV seams cause problems when baking a normal map?

Yes — manually added UV seams produced visible cut-off/discontinuity artifacts in the baked result. Baked texture data doesn't blend across UV island boundaries, so a seam placed across a visible area shows up as a hard line. This is exactly why the original plan said to leave the default UV Sphere unwrap alone rather than manually unwrap — the stock layout avoids adding seams in visible areas. Revert to the default unwrap for spherical test objects; only add manual seams for shapes that actually need them.

### Do Bevel + Weighted Normal (added before subdivision) cause problems for this pipeline?

Yes — confirmed on two separate props (a sphere, then a cone), so treat this as a settled rule, not a one-off. Applying Bevel and a Weighted Normal modifier *before* subdividing produces irregular, non-grid topology at exactly the beveled edges. That irregularity then shows up downstream wherever the pipeline assumes clean geometry: it caused the Decimate Un-Subdivide seam bug (see above), and on the cone it produced actual visible defects — a dark gap right at a beveled rim opening, and a faceted/notched edge around a beveled base — sitting exactly where the bevels were, not texture from the stroke algorithm.

Rule going forward: keep the base mesh as simple as possible (no bevels, no extra edge loops) before subdividing and running it through the normal-stroke workflow. If beveled/hardened edges are wanted on a prop, add them *after* the stroke texture is baked and decimation is done, not before.

### Does Blender's brush system support pressure-driven color jitter (auto-darken/hue-shift while painting)?

No — checked `sculpt_paint/brush/stroke.html`. Blender's brushes have pressure-sensitive **Jitter**, but only for stroke *position* (spacing/placement randomness), not color/hue/value variation. Tools like Substance Painter or Krita have this as a "dynamics" feature; Blender's Image/Texture Paint brushes don't. A custom add-on for this wouldn't be duplicating an existing feature.

---

### Where is the Normals display toggle in Edit Mode?

Overlays dropdown (top right of viewport) → **Mesh Edit Mode Overlays** section → **Normals** subsection — it's further down the panel, past the edge/crease/seam toggles, not near the top.

Controls: vertex normals icon, split normals icon, face normals icon, **Size** field, **Constant Screen Size Normals** checkbox.

Source: `blender-manual-5.2/.../editors/3dview/display/overlays.html`

---

### Can you add an Empty while in Edit Mode with Shift+A?

No. In Edit Mode, `Shift+A` opens the mesh-primitive Add menu (Plane, Cube, Circle, UV Sphere, Icosphere, etc. — `mesh.primitive_*` operators). Empties are objects, added with the Object-mode-only `object.empty_add` operator, so `Shift+A → Empty` only works in Object Mode.

Workaround: create the Empty in Object Mode first, then Tab back into Edit Mode on your mesh — it's still selectable/targetable (e.g. for `Point to Target`) regardless of which mode it was created in.

Source: `blender-manual-5.2/.../modeling/empties.html` (operator id `bpy-ops-object-empty`) + directly confirmed from the user's own Edit Mode Add-menu screenshot.

---

### `Mesh → Normals → Point to Target` — how the modal tool works

It's a modal operator (Alt+L), not a one-click action:
- **S** — toggle Spherize; move mouse afterward to blend between "normals unchanged" (0) and "fully snapped to target" (1). This is the closest thing to a strength control.
- **A** — toggle Align (all selected normals point the same direction, from selection center to target, rather than each vertex aiming individually).
- **I** — toggle Invert (point away from target instead of toward it — like "Repel").
- Target is set via **M** (mouse), **L** (pivot point), **O** (object origin), **Ctrl+Left-click** (cursor at click point), or **Ctrl+Right-click** (pick an existing mesh/object under the cursor, e.g. an Empty).
- Left-click or Enter confirms.

Source: confirmed via web search of Blender manual content (not yet cross-checked against the local copy — do that if this comes up again and needs re-verifying).

**AVOID — crashes Blender 5.2.** Reproduced a hard crash (`EXCEPTION_ACCESS_VIOLATION` in `blender::point_normals_apply`) using Spherize + Ctrl+Right-click-on-object targeting. This is a known, currently open/confirmed bug: [projects.blender.org #147859](https://projects.blender.org/blender/blender/issues/147859) — cancel doesn't undo correctly, target-picking causes unintended selection changes, no fix milestone as of 5.0 Alpha/4.5/4.2. Older versions of this same operator (2.80) have a history of outright crashes around modal confirm/cancel too. Don't use this operator for normal-combing tests going forward — use the Weight Paint + Normal Edit modifier route, or the blenderNormalBrush add-on, instead.

---

### Weight Paint mode — where's the "Draw" brush?

There isn't one by that name anymore. The new brush-asset picker (asset browser style, replaced the old dropdown list) shows Weight Paint's default brushes as **Average, Blur, Paint, Smear** — "Paint" is the Draw-type brush, just renamed in the UI. No add-on needed; select "Paint."

Source: `blender-manual-5.2/.../sculpt_paint/weight_paint/brushes.html`, line ~3476 (`<dt>Draw</dt><dd>Brushes: Paint</dd>`).
