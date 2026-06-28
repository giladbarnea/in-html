#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pygments>=2.18"]
# ///
"""Render two texts as an in-html `.diff` fragment — line + word-level changeset.

Emits the `.diff` component markup (see the "Line/word-level diff" section of
components.md): a side-by-side ↔ unified view (pure-CSS toggle), collapsible
unchanged context, intraline word highlights, syntax-highlighted code for a
small language whitelist, and #-addressable change blocks with Prev/Next
stepping. Paste the output into the `CONTENT` block of a template, then inline
`style.css` with `inline-css.py`.

Cells render monospace `pre-wrap`, so don't feed space-aligned tables through:
the padding spaces are preserved and wrap into ragged gaps on narrow screens.
Diff the prose only and render tabular content with the `.data` table component.

The diff is the reusable kernel; the *meaning* of each change is yours to
supply. An optional annotations JSON tags change blocks with a badge/title/note:

    [
      {"n": 1, "tag": "blue",  "label": "META",   "title": "...", "note": "..."},
      {"match": "recipes", "tag": "amber", "label": "DEBIAS", "note": "..."}
    ]

Match a block by 1-based change index (`n`) or by a `match` substring found
anywhere in the block. `tag` ∈ {blue, amber, green, red} (reuses `.tag` colors).

Usage:
    ./diff_to_html.py OLD NEW --left-label "world" --right-label "main"
    ./diff_to_html.py a.md b.md --id pricing --language markdown
    ./diff_to_html.py a.md b.md --id pricing --annotations notes.json -o frag.html

To diff two git revisions, materialize them first:
    git show main:path/to/file > /tmp/new.md
    git show other:path/to/file > /tmp/old.md
    ./diff_to_html.py /tmp/old.md /tmp/new.md --left-label other --right-label main
"""
import argparse
import difflib
import html
import json
import re
import sys
from pathlib import Path

from pygments.formatters import HtmlFormatter
from pygments.lexer import Lexer
from pygments.lexers import get_lexer_by_name

_WORD = re.compile(r"(\s+)")

_LANGUAGE_ALIASES: dict[str, str | None] = {
    "none": None,
    "md": "markdown",
    "markdown": "markdown",
    "py": "python",
    "python": "python",
    "sh": "shell",
    "shell": "shell",
    "bash": "shell",
    "zsh": "shell",
    "ts": "typescript",
    "tsx": "typescript",
    "typescript": "typescript",
}
_EXTENSION_LANGUAGES = {
    ".bash": "shell",
    ".cts": "typescript",
    ".markdown": "markdown",
    ".md": "markdown",
    ".mts": "typescript",
    ".py": "python",
    ".sh": "shell",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".zsh": "shell",
}
_SHELL_BASENAMES = {
    ".bash_profile",
    ".bashrc",
    ".profile",
    ".zprofile",
    ".zshrc",
    "bash_profile",
    "bashrc",
    "profile",
    "zprofile",
    "zshrc",
}
_SUPPORTED_LANGUAGE_OPTIONS = ["auto", *_LANGUAGE_ALIASES]
TokenRange = tuple[str, int, int]


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def normalize_language(language: str | None) -> str | None:
    """Return the canonical whitelist language name.

    >>> normalize_language("ts")
    'typescript'
    >>> normalize_language("none") is None
    True
    """
    if language is None:
        return None
    key = language.lower()
    if key == "auto":
        raise ValueError("auto must be resolved from file paths")
    if key not in _LANGUAGE_ALIASES:
        supported = ", ".join(_SUPPORTED_LANGUAGE_OPTIONS)
        raise ValueError(f"unsupported language {language!r}; expected one of: {supported}")
    return _LANGUAGE_ALIASES[key]


def language_for_path(path: Path) -> str | None:
    """Detect a whitelisted language from a path.

    >>> language_for_path(Path("example.tsx"))
    'typescript'
    >>> language_for_path(Path(".zshrc"))
    'shell'
    """
    basename = path.name.lower()
    if basename in _SHELL_BASENAMES:
        return "shell"
    return _EXTENSION_LANGUAGES.get(path.suffix.lower())


def language_for_paths(left_path: Path, right_path: Path, requested: str) -> str | None:
    """Resolve the requested language, preferring the new/right path for auto.

    >>> language_for_paths(Path("old.txt"), Path("new.py"), "auto")
    'python'
    >>> language_for_paths(Path("old.txt"), Path("new.txt"), "auto") is None
    True
    """
    if requested != "auto":
        return normalize_language(requested)
    return language_for_path(right_path) or language_for_path(left_path)


class SyntaxHighlighter:
    def __init__(self, language: str | None) -> None:
        canonical_language = normalize_language(language) if language else None
        self.lexer: Lexer | None = (
            get_lexer_by_name(canonical_language) if canonical_language else None
        )
        self.formatter: HtmlFormatter | None = (
            HtmlFormatter(nowrap=True, classprefix="tok-") if canonical_language else None
        )

    def render_range(self, line: str, start: int, end: int) -> str:
        if not self.lexer or not self.formatter:
            return esc(line[start:end])

        fragments = []
        for token_start, token_type, token_text in self.lexer.get_tokens_unprocessed(line):
            token_end = token_start + len(token_text)
            overlap_start = max(start, token_start)
            overlap_end = min(end, token_end)
            if overlap_start >= overlap_end:
                continue

            fragment = token_text[
                overlap_start - token_start : overlap_end - token_start
            ]
            token_class = self.formatter._get_css_class(token_type)
            escaped = esc(fragment)
            if token_class == "tok-w":
                fragments.append(escaped)
                continue
            fragments.append(
                f'<span class="{token_class}">{escaped}</span>' if token_class else escaped
            )
        return "".join(fragments)

    def render_line(self, line: str) -> str:
        return self.render_range(line, 0, len(line))


PLAIN_HIGHLIGHTER = SyntaxHighlighter(None)


def split_tokens_with_ranges(line: str) -> list[TokenRange]:
    """Split on whitespace while keeping original character ranges.

    >>> split_tokens_with_ranges("a  b")
    [('a', 0, 1), ('  ', 1, 3), ('b', 3, 4)]
    """
    tokens = []
    position = 0
    for token in _WORD.split(line):
        end = position + len(token)
        if token:
            tokens.append((token, position, end))
        position = end
    return tokens


def highlighted_token_range(
    line: str,
    tokens: list[TokenRange],
    start: int,
    end: int,
    highlighter: SyntaxHighlighter,
) -> str:
    if start == end:
        return ""
    return highlighter.render_range(line, tokens[start][1], tokens[end - 1][2])


def word_diff(
    a: str,
    b: str,
    highlighter: SyntaxHighlighter = PLAIN_HIGHLIGHTER,
) -> tuple[str, str]:
    """Intraline diff of two lines → (left_html, right_html) with .wd add/del spans.

    >>> word_diff("the cat sat", "the dog sat")
    ('the <span class="wd del">cat</span> sat', 'the <span class="wd add">dog</span> sat')
    """
    left_tokens = split_tokens_with_ranges(a)
    right_tokens = split_tokens_with_ranges(b)
    sm = difflib.SequenceMatcher(
        a=[token for token, _start, _end in left_tokens],
        b=[token for token, _start, _end in right_tokens],
        autojunk=False,
    )
    left, right = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        left_html = highlighted_token_range(a, left_tokens, i1, i2, highlighter)
        right_html = highlighted_token_range(b, right_tokens, j1, j2, highlighter)
        if tag == "equal":
            left.append(left_html)
            right.append(right_html)
        elif tag == "replace":
            if left_html:
                left.append(f'<span class="wd del">{left_html}</span>')
            if right_html:
                right.append(f'<span class="wd add">{right_html}</span>')
        elif tag == "delete":
            left.append(f'<span class="wd del">{left_html}</span>')
        elif tag == "insert":
            right.append(f'<span class="wd add">{right_html}</span>')
    return "".join(left), "".join(right)


def line_html(line: str, highlighter: SyntaxHighlighter) -> str:
    return highlighter.render_line(line) or "&nbsp;"


def _ctx_row(l: str, r: str, highlighter: SyntaxHighlighter) -> str:
    return (
        f'<div class="drow ctx"><div class="dc l" dir="auto">{line_html(l, highlighter)}</div>'
        f'<div class="dc r" dir="auto">{line_html(r, highlighter)}</div></div>'
    )


def _change_rows(
    left_lines: list[str],
    right_lines: list[str],
    highlighter: SyntaxHighlighter,
) -> str:
    rows = []
    paired = min(len(left_lines), len(right_lines))
    for n in range(paired):
        lh, rh = word_diff(left_lines[n], right_lines[n], highlighter)
        rows.append(
            f'<div class="drow"><div class="dc l del" dir="auto">{lh or "&nbsp;"}</div>'
            f'<div class="dc r add" dir="auto">{rh or "&nbsp;"}</div></div>'
        )
    for n in range(paired, len(left_lines)):  # extra deletions
        rows.append(
            f'<div class="drow"><div class="dc l del" dir="auto">{line_html(left_lines[n], highlighter)}</div>'
            f'<div class="dc r empty"></div></div>'
        )
    for n in range(paired, len(right_lines)):  # extra insertions
        rows.append(
            f'<div class="drow"><div class="dc l empty"></div>'
            f'<div class="dc r add" dir="auto">{line_html(right_lines[n], highlighter)}</div></div>'
        )
    return "".join(rows)


def _annotation_for(n: int, block_text: str, annotations: list[dict]) -> dict | None:
    for a in annotations:
        if a.get("n") == n:
            return a
    plain = html.unescape(re.sub(r"<[^>]+>", "", block_text))
    for a in annotations:
        if "n" not in a and a.get("match") and a["match"] in plain:
            return a
    return None


def render_diff(
    left: str,
    right: str,
    *,
    left_label: str = "before",
    right_label: str = "after",
    diff_id: str = "d1",
    annotations: list[dict] | None = None,
    context: int = 3,
    language: str | None = None,
) -> str:
    """Return the `.diff` fragment comparing left → right (whole texts)."""
    annotations = annotations or []
    highlighter = SyntaxHighlighter(language)
    llines, rlines = left.splitlines(), right.splitlines()
    sm = difflib.SequenceMatcher(a=llines, b=rlines, autojunk=False)

    # split opcodes into context runs and change groups
    raw = []  # ("ctx", l1, l2, r1, r2) | ("chg", l1, l2, r1, r2)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        raw.append(("ctx" if tag == "equal" else "chg", i1, i2, j1, j2))

    body, n = [], 0
    total = sum(1 for kind, *_ in raw if kind == "chg")
    for kind, i1, i2, j1, j2 in raw:
        if kind == "ctx":
            length = i2 - i1
            rows = "".join(
                _ctx_row(llines[i1 + k], rlines[j1 + k], highlighter)
                for k in range(length)
            )
            if length > context:
                body.append(
                    f'<details class="dctx"><summary>{length} unchanged line'
                    f'{"s" if length != 1 else ""}</summary>{rows}</details>'
                )
            else:
                body.append(rows)
            continue
        n += 1
        rows = _change_rows(llines[i1:i2], rlines[j1:j2], highlighter)
        ann = _annotation_for(n, rows, annotations)
        accent = f' {ann["tag"]}' if ann and ann.get("tag") else ""
        badge = f'<span class="tag {ann["tag"]}">{esc(ann["label"])}</span> ' if ann and ann.get("label") else ""
        title = f'<span class="dtitle">{esc(ann["title"])}</span>' if ann and ann.get("title") else ""
        note = f'<p class="why">{ann["note"]}</p>' if ann and ann.get("note") else ""
        head = (
            f'<div class="dhead">{badge}<span class="dnum">Change {n} / {total}</span>'
            f'{title}{note}</div>'
        )
        prev = (
            f'<a class="btn" href="#{diff_id}-c{n-1}">&lsaquo;&nbsp;Prev</a>'
            if n > 1 else '<span class="btn off">&lsaquo;&nbsp;Prev</span>'
        )
        nxt = (
            f'<a class="btn" href="#{diff_id}-c{n+1}">Next&nbsp;&rsaquo;</a>'
            if n < total else '<span class="btn off">Next&nbsp;&rsaquo;</span>'
        )
        nav = (
            f'<div class="dnav">{prev}<span class="dpos">Change {n} / {total}</span>'
            f'<a class="btn" href="#{diff_id}">&uarr;&nbsp;All</a>{nxt}</div>'
        )
        body.append(
            f'<section class="dchange{accent}" id="{diff_id}-c{n}">{head}{rows}{nav}</section>'
        )

    step = f'<a class="btn" href="#{diff_id}-c1">Step through &rarr;</a>' if total else ""
    return (
        f'<div class="diff" id="{diff_id}">'
        f'<div class="diff-bar"><div class="seg diff-view">'
        f'<label><input type="radio" name="{diff_id}-view" checked><span>Side&#8209;by&#8209;side</span></label>'
        f'<label><input type="radio" name="{diff_id}-view"><span>Unified</span></label>'
        f'</div><span class="grow"></span>{step}</div>'
        f'<div class="dcols"><span class="l">{esc(left_label)}</span>'
        f'<span class="r">{esc(right_label)}</span></div>'
        f'<div class="diff-body">{"".join(body)}</div></div>'
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Render two files as an in-html .diff fragment.")
    p.add_argument("left", type=Path, help="the 'before' / left file")
    p.add_argument("right", type=Path, help="the 'after' / right file")
    p.add_argument("--left-label", default="before")
    p.add_argument("--right-label", default="after")
    p.add_argument("--id", dest="diff_id", default="d1", help="unique id prefix (for multiple diffs on one page)")
    p.add_argument("--context", type=int, default=3, help="unchanged lines shown inline before collapsing")
    p.add_argument("--language", default="auto", choices=_SUPPORTED_LANGUAGE_OPTIONS, help="syntax highlighting language; auto uses the input file extension")
    p.add_argument("--annotations", type=Path, help="JSON list of change-block annotations")
    p.add_argument("-o", "--output", type=Path, help="write fragment here (default: stdout)")
    args = p.parse_args()

    annotations = json.loads(args.annotations.read_text()) if args.annotations else None
    if annotations is not None and not isinstance(annotations, list):
        sys.exit("error: --annotations must be a JSON list")

    fragment = render_diff(
        args.left.read_text(),
        args.right.read_text(),
        left_label=args.left_label,
        right_label=args.right_label,
        diff_id=args.diff_id,
        annotations=annotations,
        context=args.context,
        language=language_for_paths(args.left, args.right, args.language),
    )
    if args.output:
        args.output.write_text(fragment)
        print(f"wrote .diff fragment → {args.output}", file=sys.stderr)
    else:
        print(fragment)


if __name__ == "__main__":
    main()
