---
name: in-html
description: Build a reusable local HTML page for a CLI-agent review loop, with selectable boilerplate layers — styling, browser interactions, and optional Shift+click annotations persisted to JSON.
last_updated: 2026-06-29
---

# in-html

Use this skill when the user wants an answer or artifact as a local HTML page. Its purpose is to help you convey dense, complex information to a human in a more brain-friendly way — not with more words, but with the added power of design that HTML, CSS, and JavaScript unlock over Markdown. Approach each page as an information-design product: what can layout, typography, interaction, visual hierarchy, and annotation communicate that chat cannot?

Draw on the basic tenets of universally good design: Edward Tufte’s **visualization**; Josef Müller-Brockmann’s **layout and whitespace**; Richard Saul Wurman’s **information architecture**; Don Norman’s and Jakob Nielsen’s **user experience**; Gestalt **attention management**; Jan Tschichold’s and Robert Bringhurst’s **typography**; and Dieter Rams’s **beauty**; principles like progressive disclosure; etc.

Do not decorate the same prose in boxes; identify the hidden shape of the material and make that shape visible.

Choose the richest layer the environment supports:

1. **Layer 1 — style only.** A single self-contained HTML file with no JavaScript. Use only when the delivery channel cannot run JavaScript.
2. **Layer 2 — style plus interactions.** Adds browser interactions such as segmented tabs, highlights, copy buttons, glossary tooltips, section navigation, and theme switching. Use when JavaScript works but local writes or a Node server do not.
3. **Layer 3 — annotated review loop.** Adds Shift+click annotations saved to JSON on disk, so the user can comment in the page and tell you when to read the saved feedback. This is the default when local Node can run.

Do not ask which layer to use unless the user's environment or intent is unclear. Layer 3 is almost always the right choice because it keeps the rich page experience and lets the user talk back at little cost. Tell the user annotations are enabled and that they can comment in the page, then tell you when they are done.

This skill keeps small HTML shells and modular CSS/JS assets. If the delivery channel truly supports only one physical HTML file, inline the chosen CSS/JS into `<style>` and `<script>` tags instead of linking external files.

Asset paths below are written against `${CLAUDE_SKILL_DIR}` — the directory containing this `SKILL.md`, not your current working directory. Claude Code substitutes this token with the skill's absolute path before you read it. On a harness that does not, export it yourself once to the absolute path you loaded this skill from:

```bash
export CLAUDE_SKILL_DIR=/absolute/path/to/this/skill
```

## Fast path: builder command

When local writes are available, prefer the builder over hand-copying templates. Author only the page body as an HTML fragment, then run:

```bash
"${CLAUDE_SKILL_DIR}/scripts/inhtml" build content.html \
  --title "Brief title" \
  --layer 3 \
  --out /tmp/domainful-page \
  --also-layer1-icloud domainful-page.html
```

The builder copies the right template/assets, injects the fragment, mirrors each `data-annotation-id` into an `id` when missing, validates internal `#links`, creates `annotations.json`, starts the layer-3 annotation server, and writes any requested self-contained layer-1 copies. Use `--no-serve` when you only need files. Use `--allow-missing-links` only while drafting; final pages should validate cleanly.

The content file is an HTML body fragment. A full HTML file also works — only its `<body>` is injected. Markdown conversion is intentionally not part of this command; use the component vocabulary below when shaping the content.

## Manual assembly by layer

Use manual assembly only when the builder is unavailable or when you must control every copied file yourself.

### Layer 1: style only

Use when the page must render without JavaScript. Disclosure, step expansion, and segmented tabs still work through pure CSS (`<details>` and `:has()`). Only chip highlights and bar clicks need layer 2.

```bash
workdir=$(mktemp -d)
cp "${CLAUDE_SKILL_DIR}/templates/template-style.html" "$workdir/index.html"
cp "${CLAUDE_SKILL_DIR}/scripts/style.css" "$workdir/"
cd "$workdir"
```

The result must be a single self-contained HTML file. Inline the CSS with:

```bash
"${CLAUDE_SKILL_DIR}/scripts/inline-css.py" index.html style.css -o page.html
```

Then copy `page.html` wherever the delivery channel can pick it up.

### Layers 1+2: style plus interactions

Use when JavaScript works, but filesystem writes or a local Node server are unavailable.

```bash
workdir=$(mktemp -d)
cp "${CLAUDE_SKILL_DIR}/templates/template-interactive.html" "$workdir/index.html"
cp "${CLAUDE_SKILL_DIR}/scripts/style.css" "$workdir/"
cp "${CLAUDE_SKILL_DIR}/scripts/interactions.js" "$workdir/"
cd "$workdir"
```

### Layers 1+2+3: full annotated review page

Use when a local Node process can run.

```bash
workdir=$(mktemp -d)
cp "${CLAUDE_SKILL_DIR}/templates/template.html" "$workdir/index.html"
cp "${CLAUDE_SKILL_DIR}/scripts/style.css" "$workdir/"
cp "${CLAUDE_SKILL_DIR}/scripts/interactions.js" "$workdir/"
cp "${CLAUDE_SKILL_DIR}/scripts/annotations.css" "$workdir/"
cp "${CLAUDE_SKILL_DIR}/scripts/annotations.js" "$workdir/"
cp "${CLAUDE_SKILL_DIR}/scripts/annotation-writer.mjs" "$workdir/"
cd "$workdir"
node annotation-writer.mjs
```

Then open `http://127.0.0.1:8765/index.html`. Annotation saves work out of the box because the template's `annotation-endpoint` meta is the relative `/annotations` and CORS accepts same-origin requests. If serving the page from a separate static server instead, run `node annotation-writer.mjs` too and set the meta to the absolute `http://127.0.0.1:8765/annotations`; the relative default would post to the wrong server.

## Design contract

Layer 2 and 3 pages should feel like a small docs product, not an essay with sidebars. The shell already builds the Mintlify-style furniture — top bar, left section navigation, right “On this page”, tag legend, and theme toggle — so do not hand-build chrome. What makes the page land is the first screen: an eyebrow or short `h1`, a direct `.sub`/`.lead`, `.stats` for the facts the reader needs at a glance, then one strong `.callout`, `.cardgroup`, or `.record` set. If the first viewport is only title plus paragraphs, the page has failed.

Use the provided classes as the visual vocabulary: `.record` for repeated proposals/findings, `.cardgroup` + `.card` for two to four overview ideas, `.gate` for one governing rule/test, `.callout` for one boxed judgment, `.stats` for quiet Mintlify-style metadata badges, and `table.data` only for row facts. Keep the page’s own structure to real `h2` sections; the shell reads those headings to build navigation. The style system supplies the palette, spacing, code pills, card shadows, and dark-mode behavior; you supply the information architecture.

The page's job is to install knowledge, not to restyle text. Before authoring, identify the **shapes** hiding in the material and give each shape its native representation:

| Content shape | Representation |
| --- | --- |
| Actions, statuses, owners, open questions | `.tasks` status checklist |
| A set of proposals/findings, each with the same fields (rank, source, kind, score) | `.record` card |
| A magnitude, ranking, or score | `.meter` bar |
| A path with barriers (locks, approvals, hops, conversions) | `.chain` gate chain |
| Hierarchy, org chart, who-controls-what | `.tree` |
| Cause → cure, problem → owner, any A-maps-to-B relation | `.relmap` relation map |
| Architecture / system overview; a 2D map of blocks and their connections | SVG diagram (`diagram.py`) |
| Process / sequence of stages | `.pipe` |
| Comparison, before/after, either/or | `.ba` panes, segmented tabs |
| Two versions of one text; exactly what changed | `.diff` line/word-level changeset (`diff_to_html.py`) |
| Asked → answered → replied (multi-round review loops) | `.qa` dialogue block |
| Line items, build-ups, per-row facts with numbers | `table.data` |
| Counts / status at a glance for a page header | `.stats` stat row |
| A jargon term that needs defining in place | `.term` glossary tooltip |
| Background, reference, "later" material | `.disclose`, collapsed |
| Insight, caveat, judgment, status | short prose, `aside.note`, `.callout` variants: `note`, `tip`, `check`, `warning`, `danger` |

Prose is the fallback for what genuinely has no shape — insight, caveat, synthesis — not the default.

## Priorities

1. Order by reader need: actions and answers first, the explanatory model second, reference material last and collapsed. Do not make the reader scroll past theory to find their next move.
2. State each fact exactly once, in its best representation. If the same fact appears in two sections, one of them is the wrong representation — cut it from there. Target roughly a third of the source's word count.
3. Encode state and urgency visually — state badges, gate colors, verdicts — never only in words. A status page where everything looks equally calm has failed.
4. Collapse background and reference; never collapse operationally critical content. `open`-by-default is reserved for what the reader needs right now.
5. Interaction must pay for itself: a click should reveal something the reader did not need before clicking. Highlighting prose the reader must read anyway is decoration — omit it.
6. The visually loudest element must be the most consequential one. Audit every `hot`, badge, and accent: does emphasis track importance?
7. Do not force the densest content into the narrowest container, and do not let one section mix timescales or audiences: now versus later, action versus reference. Split it instead.
8. Before shipping, run the installation test: after a 30-second read, could the reader redraw the diagrams and recite the next actions from memory? If a section only re-reads well rather than recalls well, reshape it.

## Authoring rules

Edit `index.html` by replacing only the `CONTENT START` block with page content. Keep the imports intact for the chosen layer set, including the small inline `<script>` in `<head>`; it picks a warm dark or light theme from local time before first paint, while the OS color-scheme setting remains the fallback when JavaScript is off. Theming is fully automatic across every layer, so author content as usual and leave colors alone.

At layers 2 and 3 the page is automatically wrapped in a three-pane docs frame built by `interactions.js` from the page's `h2` headings. Give the page real `h2` sections and author no separate navigation chrome. The frame collapses to a single column with a nav drawer on phones, fades its table of contents out of the way whenever an annotation panel opens, and is absent at layer 1. A tag-filter legend, code-block copy buttons, and touch-tap glossary tooltips come with the same layer-2 set, also with no extra markup.

Use normal HTML first: `h1`, `.sub`, `.lead`, `h2`, `p`, `aside.note`, `.card`, `.callout`, `.grid`, `.pane`, `.row`, `.chip`, `.btn`, `.kbd`.

For ready-made components, read `${CLAUDE_SKILL_DIR}/scripts/components.md`. For a rendered reference, open `${CLAUDE_SKILL_DIR}/scripts/component-gallery.html` with the full layer set. To show exactly what changed between two versions of a text, generate the `.diff` component with `${CLAUDE_SKILL_DIR}/scripts/diff_to_html.py`; see the “Line / word-level diff” section of `components.md`. For a 2D architecture / hub-and-spoke diagram, generate an inline `<svg>` with `${CLAUDE_SKILL_DIR}/scripts/diagram.py`; see the “SVG diagram” section of `components.md`.

Cross-references must be real links. Never write a bare “§7”, “Draft 2”, or “the table above”; use `<a href="#stable-name">§7</a>`. Every `data-annotation-id` doubles as a link target: the builder mirrors it into `id`, and at layers 2–3 `interactions.js` also mirrors it in the browser. If building manually for layer 1, write the `id` attribute on the target yourself. Internal links are styled automatically, scroll smoothly, and flash the target on arrival; a “↩ Back to where you were” pill then returns the reader to their departure point. A link whose target does not exist renders red with a console warning — fix it before shipping.

When a previous round's questions were answered through annotations, regenerate the page with the answered items as `.qa` dialogue blocks: question → reviewer's answer → your reply. Give new asks fresh `data-annotation-id`s so old JSON keys stay harmlessly orphaned instead of colliding with new content.

## Annotation authoring

When annotations are enabled, add `data-annotation-id="stable-name"` to important elements so JSON keys survive later edits. Without one, the key is a structural CSS path from the nearest `data-annotation-id` ancestor or `<body>` down to the element: tag + id + `:nth-of-type`, never classes. Classes are visual/interaction state, not persistent identity.

Add `data-annotate-whole` when Shift+click should annotate the whole box rather than a leaf text node. Each block you mark this way, such as a `.record` card, can also carry a one-word **verdict** for statements that invite agreement rather than a written reply. A block can hold many notes and exactly one verdict; the verdict is stored in a separate `choice` field and overwrites the previous value. Component units pulled in automatically (`.step`, `.bar`, `.callout`, `.relrow`) and tables take notes only; verdicts are reserved for blocks you explicitly mark `data-annotate-whole`.

Annotating is a deliberate gesture kept separate from a plain press, so any element whose press already does something keeps that behavior. On desktop the annotation gesture is Shift+click (or ⌘+click / the `※` marker to read); a bare click is left to the page. On touch it is a long press (~0.75s); a shorter tap is a plain tap the page owns — a link navigates, a glossary tip expands, a toggle toggles. On top of that, elements that are never annotation targets — links (`<a href>`), the glossary term (`.term`, whose press expands its own tooltip), and page UI — are ignored outright, so even the annotation gesture skips them. Write cross-references, external links, and glossary terms normally; nothing opts them out.

The reviewer opens annotations with Shift+click. Bare clicks remain available for page interactions. Elements with saved annotations get a subtle `※` marker; clicking the marker or Cmd+clicking the element toggles a styled preview beside the content column, and multiple previews can remain open. Bare Enter submits; modified Enter inserts a line break. Escape closes annotation UI. The editor can be dragged by the grip at its top and grown from its bottom-right corner like a native textarea. Submitting reads the note back from disk and confirms only once the write is verified present.

Saved notes are editable in place from their preview. Each note has Save, Revert, and Delete actions: Save and Revert stay inactive until the text differs from disk, while Delete removes the note from JSON. A deleted note stays in the open preview as a struck-through tombstone where only Revert is live; pressing it restores the annotations file exactly as it was the moment before deletion. This undo exists only while the preview stays open.

Selecting text inside the annotated element before Shift+click, or drag-selecting it while the editor is open, captures that span alongside the note. The captured phrase is highlighted in the page and shown in the editor as `↳ “selected text”`; only selections fully inside the annotated element are recorded.

Every layer adapts to touch screens on its own — same files, same markup rules, nothing extra to author. A long press (~0.75s) on an element opens its annotation panel; the block depresses and a rim charges in the instant the finger lands, so the hold reads as registering, and it resets on lift. A shorter tap is left to the page. The `※` rail badge is still the way to view saved notes. The panel opens as a bottom sheet with explicit Save, Cancel, and close buttons.

Annotation JSON shape: each key maps to the element text plus accumulated reviewer notes. Re-annotating the same element appends rather than overwrites. Every note is an object with `userInput` and a local ISO 8601 `timestamp` with timezone offset; `specificallySelected` appears only when the reviewer had text selected. The optional `choice` object holds the single mutually-exclusive quick answer, independent of `userInputs`:

```json
{
  "body > main > section#summary > div > p:nth-of-type(2)": {
    "text": "The element text",
    "userInputs": [
      {"userInput": "A note on the whole element", "timestamp": "2026-06-03T14:32:07+03:00"},
      {"userInput": "A note on a specific phrase", "specificallySelected": "the highlighted phrase", "timestamp": "2026-06-03T14:33:11+03:00"}
    ],
    "choice": {"value": "Agreed", "timestamp": "2026-06-03T14:34:02+03:00"}
  }
}
```
