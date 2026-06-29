# in-html development

Read this file when you are changing, testing, or releasing the `in-html` skill itself. Keep runtime instructions for agents using the skill in `SKILL.md`; keep implementation architecture, maintenance decisions, and release workflow here or in `docs/`.

## Root documentation roles

1. `SKILL.md` is the only always-loaded guide for agents using `in-html` to make pages. It should stay operational: when to use the skill, which layer to choose, how to build a page, and how to author content and annotations.
2. `DEVELOPMENT.md` is for agents or humans working on the skill implementation. It should not duplicate usage prose from `SKILL.md`.

## Architecture: input handling

Mobile support was added under one constraint: it must be invisible to agents instantiating pages — same files, same recipes, same markup rules. That ruled out a separate mobile module and produced the current shape: shared, input-agnostic actions in `annotations.js` (open editor, submit, toggle preview, highlight), with desktop gestures and touch gestures as two thin binding layers that call the same actions. To add an interaction, extend the action once and wire it from both binding sections; never branch on device inside an action.

Two deliberate splits follow from this, and both are easy to mistake for accidents:

1. Behavior follows the event (`pointerType`), while layout follows the device class through the single `(hover: none) and (pointer: coarse)` query shared verbatim by `annotations.js` and both stylesheets. Hybrid devices therefore get both gesture sets over one layout.
2. Geometry on phones is owned by CSS alone: the coarse-pointer blocks override the JavaScript positioners' inline styles with `!important` so the positioning code stays mobile-ignorant. They look like hacks; they are the seam.

The iOS quirks the touch bindings absorb — no click synthesis on non-interactive elements, sticky hover, and the keyboard overlaying fixed elements — are each documented where they are handled. Fix that class of problem in the bindings or the CSS media blocks, never in core.

## Release workflow

Pushing to `main` ships the plugin. Installs track the branch, so the next `/plugin update` picks it up. When a change is meaningful, bump the version in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`; keep them equal.

For a manual install smoke test:

```text
/plugin marketplace add giladbarnea/in-html
/plugin install in-html@giladbarnea
```

After adding the marketplace, the plugin should also appear under `/plugin > Discover`.
