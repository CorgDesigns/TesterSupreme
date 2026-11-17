# Tools

## Blender 5.2 manual — local offline copy

Location: `blender-manual-5.2/html/blender_manual_v520_en.html/` (multi-page HTML, extracted from the official `blender_manual_html.zip`). The zip itself is kept alongside it.
Source: `https://docs.blender.org/manual/en/5.2/blender_manual_html.zip` — official download, not a mirror.
Gitignored (`.gitignore` at repo root) — this is ~1.3GB extracted, a reference tool, not project content. Not committed.

### Why it's here

`docs.blender.org` returns HTTP 403 to automated fetches (Cloudflare), so looking up exact UI/menu wording live wasn't reliable — led to two wrong answers about where the Normals overlay toggle lives before switching to this. Grepping the local copy gives exact, verifiable manual text instead of guessing from memory.

### How to use it

Grep `blender-manual-5.2/html/blender_manual_v520_en.html/` for a topic; each manual page is a separate `.html` file under a path that mirrors the online manual's URL structure (e.g. the Overlays page is at `editors/3dview/display/overlays.html`).

### Confirmed answers so far

Kept in a running log rather than here — see `blender-5.2-learnings.md` in this folder. Check that first before re-searching a Blender 5.2 (or s&box) question; add to it whenever a new one gets resolved.

## s&box docs — local offline copy

Location: `sbox-docs/docs/` (markdown source only — images stripped out, 910MB → 1.3MB).
Source: `https://github.com/Facepunch/sbox-docs`, official docs repo (renders live at sbox.game/dev/doc). Shallow-cloned, `.git` stripped, so it's a point-in-time snapshot — re-clone for updates.
Gitignored, same reasoning as the Blender manual.

### Why it's here

`sbox.game/dev/doc/` pages are client-rendered (WebFetch only sees an empty shell), so live lookups don't work. This is the actual markdown source instead of a mirror.

### How to use it

Grep `sbox-docs/docs/` for a topic; paths roughly mirror the site's URL structure (e.g. `docs/rendering/shaders/material.md`, `docs/editor/model-editor.md`).

## blenderNormalBrush — vendored reference

Source: https://github.com/blackears/blenderNormalBrush
Vendored commit: `03e683527710fa2fe403c706fce72ccaf95b0016` (2025-06-21)
License: GPL-3.0 (see `blenderNormalBrush/LICENSE`) — fine to study/build from locally; check the license again before redistributing any derivative add-on.

`.git` was stripped on vendor-in, so this is a plain snapshot, not a submodule. Re-clone from the source URL above if a newer version is needed.

### Why it's here

Candidate base for a custom Blender brush that paints normal-map detail directly as brush strokes — this is "Technique A" (painted normal detail that catches real-time light) from the reference art-direction plan: strokes that physically deflect light rather than being baked from sculpted geometry.

### Status: fallback, not first choice

Deliberately holding off on installing this one first. The repo is ~5 years old (last real update was a Blender 4.4 compatibility patch in 2025-06) — plausible it needs work to run cleanly on 5.2. Currently testing a fully-native alternative instead (Weight Paint brush → vertex group → Normal Edit modifier, Directional mode, targeting an Empty), which sidesteps installing/patching anything.

Fall back to this only if the native route doesn't give a good enough result. If so, next steps:
1. Install the add-on as-is and see if it even loads/runs on 5.2 without errors — don't assume it does.
2. If it runs, test against the Phase 1 single-stroke-on-a-plane experiment before modifying anything.
3. If it's close enough, skip the custom-brush idea entirely and just use it.
4. If it needs updating for 5.2, read `source/` to find what's broken (API changes between 4.4 and 5.2 are the likely culprit) and patch from there.
