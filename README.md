# in-html

Build a local HTML page an AI agent and a human can review together: rich, readable output the human can annotate directly in the browser, with comments saved to disk for the agent to read back.

## What it builds

`in-html` turns dense agent output into a small docs-style web page, in one of three layers depending on what the delivery channel supports:

- **Layer 1 — style only.** A single self-contained HTML file, no JavaScript. For channels that can render just one static file.
- **Layer 2 — style + interactions.** Adds browser interactions (segmented tabs, highlights, code-copy buttons, glossary tooltips) when JavaScript runs but local writes don't.
- **Layer 3 — annotated review loop.** Adds Shift+click annotations: the reader comments on any element, the notes persist to a JSON file, and the agent reads them back to continue the session.

Layer 3 is the usual choice — it gives the full experience and lets the reader talk back at no real cost.

## When to use

Reach for it whenever an answer or artifact lands better as a page than as a wall of chat: a set of proposals, a diff, a status report, anything with structure worth seeing laid out. The skill supplies the layout vocabulary (records, callouts, meters, line/word diffs, gate chains, and more) and the dark/light theming; you supply the information architecture.

## Install

```
/plugin marketplace add giladbarnea/in-html
/plugin install in-html@giladbarnea
```

After adding the marketplace you can also browse for it under `/plugin > Discover`.

## Use

Ask for it in natural language:

```
> show me this as an annotatable HTML page
```

The skill auto-triggers on requests like "make an HTML page", "render this as a review page", or "let me annotate this". You can also invoke it explicitly as `/in-html:in-html`.

Once the page is open, the reader Shift+clicks any element to leave a note; tell the agent when you're done and it reads the saved JSON back.
