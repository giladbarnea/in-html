#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Render a block-and-connector SVG diagram from a declarative spec.

Emits an inline `<svg>` fragment (see the "SVG diagram" section of
components.md): styled blocks joined by connectors, for architecture / system
overviews, pipelines, and hub-and-spoke maps that the pure-CSS `.tree` /
`.chain` / `.relmap` shapes can't express. Paste the output into the `CONTENT`
block of a template; it reads its palette from CSS custom properties, so it
inherits the page theme with no inlining step.

You declare blocks with ids and connectors between ids; a layout pass resolves
every box into a registry, and connectors look their endpoints up by id and
choose anchor sides from geometry. Coordinates are an output, never an input.
The engine does three things you would otherwise hand-plot per diagram:
  - identity: every block has an id; connectors reference ids, not points.
  - auto-anchor: the side of each endpoint is inferred from relative position.
  - port spread: when several connectors share one side of a block, they are
    distributed along that edge and ordered by their far end, so they fan
    without crossing.
And it keeps text honest: measure-then-wrap-or-shrink so nothing bleeds,
dominant-baseline + symmetric stacking for vertical centring, and a
paint-order halo so connector labels stay legible over the lines they cross.

A spec is a Python file that sets `DIAGRAM = Diagram(...)`; the names
`Diagram`, `Grid`, `Block`, and `Conn` are already in scope (no import). See
the built-in `HUB` and `PIPE` specs at the bottom of this file for the shape.

Usage:
    ./diagram.py spec.py > frag.svg      # render a spec to an <svg> fragment
    ./diagram.py spec.py -o frag.svg
    ./diagram.py --demo                  # self-check the built-in examples
"""
from dataclasses import dataclass
import xml.etree.ElementTree as ET

# role -> (css class, font px, monospace, line height)
ROLES = {
    "title": ("title", 12.5, False, 17), "hd": ("hd", 12.5, False, 17),
    "sub": ("sub", 12, False, 16), "brand": ("brand", 22, False, 28),
    "coresub": ("coresub", 12.5, False, 18), "monoacc": ("monoacc", 11, True, 17),
    "faint": ("eyebrow", 11, True, 15), "plabel": ("plabel", 11.5, True, 16),
    "rule": ("rule", 0, False, 14),
}
# kind -> (box class, default title role, corner radius)
KINDS = {
    "node": ("node", "title", 10), "dim": ("node", "hd", 10),
    "step": ("node step", "hd", 10), "core": ("core", "brand", 14),
    "term": ("term", "title", 10), "probe": ("probe", "plabel", 9),
}
CONN = {  # kind -> (path class, marker id or None)
    "flow": ("flow", "ar"), "link": ("link", None), "probe": ("probe", "ard"),
}
CONTENT_PAD, VPAD = 14, 7

STYLE = """<style>
  svg{font-family:var(--sans,'Inter',system-ui,sans-serif)}
  text{dominant-baseline:central}
  .eyebrow{font-family:var(--mono,'JetBrains Mono',ui-monospace,monospace);font-size:11px;letter-spacing:1px;fill:var(--faint,#897B65)}
  .title{font-size:12.5px;fill:var(--ink,#F4ECDD)}
  .sub{font-size:12px;fill:var(--muted,#B6A88F)}
  .hd{font-size:12.5px;font-weight:600;fill:var(--gold,#F6C063)}
  .node{fill:var(--surface,#1A140C);stroke:var(--line,#2C2316);stroke-width:1}
  .step{stroke:var(--line2,#3C2E1B)}
  .core{fill:url(#core);stroke:var(--accent,#C8821F);stroke-width:1.4}
  .term{fill:var(--core1,#241B10);stroke:var(--accent,#C8821F)}
  .flow{stroke:var(--accent,#C8821F);stroke-width:1.6;fill:none}
  .link{stroke:var(--line2,#3C2E1B);stroke-width:1.4;fill:none}
  .probe{fill:none;stroke:var(--danger,#D9542B);stroke-width:1.4;stroke-dasharray:4 4}
  .rule{stroke:var(--line2,#3C2E1B);stroke-width:1}
  .brand{font-family:var(--serif,'Fraunces',Georgia,serif);font-weight:600;font-size:22px;fill:var(--gold,#F6C063)}
  .coresub{font-size:12.5px;fill:var(--muted,#B6A88F)}
  .monoacc{font-family:var(--mono,'JetBrains Mono',ui-monospace,monospace);font-size:11px;fill:var(--accentb,#E9A53C)}
  .plabel{font-family:var(--mono,'JetBrains Mono',ui-monospace,monospace);font-size:11.5px;fill:var(--dangerink,#DF7763)}
  .elabel{font-family:var(--mono,'JetBrains Mono',ui-monospace,monospace);font-size:10.5px;fill:var(--faint,#897B65);
          paint-order:stroke;stroke:var(--halo,#0b0a07);stroke-width:4px;stroke-linejoin:round}
  #ar path{fill:var(--accent,#C8821F)}
  #ard path{fill:var(--danger,#D9542B)}
  #core .s1{stop-color:var(--core1,#241B10)}
  #core .s2{stop-color:var(--core2,#1A140C)}
</style>"""
DEFS = """<defs>
  <linearGradient id="core" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="s1"/><stop offset="1" class="s2"/></linearGradient>
  <marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z"/></marker>
  <marker id="ard" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z"/></marker>
</defs>"""


# ---------------- authoring model ----------------
@dataclass
class Block:
    id: str
    title: str
    body: tuple = ()          # entries: (text, role) | (text, role, mode)  mode: "wrap"|"shrink"; role "rule" => divider
    col: int = 0
    row: int = 0
    rowspan: int = 1
    kind: str = "node"
    title_role: str = ""


@dataclass
class Conn:
    src: str
    dst: str
    kind: str = "flow"
    label: str = ""


@dataclass
class Grid:
    col_widths: list[int]
    node_h: int = 48
    gap_x: int = 118
    gap_y: int = 14
    top: int = 56
    pad: int = 40


@dataclass
class Diagram:
    grid: Grid
    blocks: list[Block]
    conns: list[Conn]
    aria: str
    annotations: tuple = ()   # (col, text) | (col, text, y)


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self): return self.x + self.w / 2
    @property
    def cy(self): return self.y + self.h / 2

    def anchor(self, side, frac):
        if side == "left":  return (self.x, self.y + self.h * frac)
        if side == "right": return (self.x + self.w, self.y + self.h * frac)
        if side == "top":   return (self.x + self.w * frac, self.y)
        return (self.x + self.w * frac, self.y + self.h)  # bottom


# ---------------- text primitives (the invariants) ----------------
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def measure(s, fs, mono): return len(s) * fs * (0.6 if mono else 0.55)


def wrap(s, max_w, fs, mono):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, fs, mono) > max_w:
            lines.append(cur); cur = word
        else:
            cur = trial
    if cur: lines.append(cur)
    return lines or [""]


def txt(x, y, s, cls, anchor="middle", extra=""):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}"{a}{extra}>{esc(s)}</text>'


# resolve a block's content into physical lines: (text|None, cls, line_h, textLength|None)
def physical_lines(block, inner_w):
    title_role = block.title_role or KINDS[block.kind][1]
    entries = [(block.title, title_role, "wrap")]
    for e in block.body:
        entries.append(e if len(e) == 3 else (*e, "wrap"))
    out = []
    for text, role, mode in entries:
        cls, fs, mono, lh = ROLES[role]
        if role == "rule":
            out.append((None, cls, lh, None)); continue
        if mode == "shrink" and measure(text, fs, mono) > inner_w:
            out.append((text, cls, lh, inner_w))
        else:
            for ln in wrap(text, inner_w, fs, mono):
                out.append((ln, cls, lh, None))
    return out


# ---------------- layout pass: declarations -> registry ----------------
def layout(d: Grid, blocks):
    colx, x = [], d.pad
    for w in d.col_widths:
        colx.append(x); x += w + d.gap_x
    pitch = d.node_h + d.gap_y
    reg: dict[str, Box] = {}
    for b in blocks:
        bx, bw = colx[b.col], d.col_widths[b.col]
        by = d.top + b.row * pitch
        grid_h = b.rowspan * d.node_h + (b.rowspan - 1) * d.gap_y
        content_h = sum(lh for _, _, lh, _ in physical_lines(b, bw - 2 * CONTENT_PAD))
        reg[b.id] = Box(bx, by, bw, max(grid_h, content_h + 2 * VPAD))
    return reg, colx


# ---------------- connector geometry ----------------
def sides(a: Box, b: Box):
    dx, dy = b.cx - a.cx, b.cy - a.cy
    if abs(dx) >= abs(dy):
        return ("right", "left") if dx > 0 else ("left", "right")
    return ("bottom", "top") if dy > 0 else ("top", "bottom")


def resolve_ports(conns, reg):
    """Assign (side, frac) to both ends of every connector; spread shared sides."""
    ends = []  # (conn_i, which, block_id, side, far_center_along_side)
    for i, c in enumerate(conns):
        a, b = reg[c.src], reg[c.dst]
        sa, sb = sides(a, b)
        key_a = a.cy if sa in ("left", "right") else a.cx
        key_b = b.cy if sb in ("left", "right") else b.cx
        ends.append([i, "src", c.src, sa, key_b])   # order src port by the *far* (dst) center
        ends.append([i, "dst", c.dst, sb, key_a])
    groups: dict[tuple, list] = {}
    for e in ends:
        groups.setdefault((e[2], e[3]), []).append(e)
    port = {}  # (conn_i, which) -> (side, frac)
    for (bid, side), grp in groups.items():
        grp.sort(key=lambda e: e[4])
        n = len(grp)
        for rank, e in enumerate(grp):
            frac = 0.5 if n == 1 else (rank + 1) / (n + 1)
            port[(e[0], e[1])] = (side, frac)
    return port


def bezier(a, b, orient):
    ax, ay = a; bx, by = b
    if orient == "h":
        dx = (bx - ax) * 0.5
        c1, c2 = (ax + dx, ay), (bx - dx, by)
    else:
        dy = (by - ay) * 0.5
        c1, c2 = (ax, ay + dy), (bx, by - dy)
    d = f"M{ax:.1f},{ay:.1f} C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {bx:.1f},{by:.1f}"
    mid = ((ax + 3 * c1[0] + 3 * c2[0] + bx) / 8, (ay + 3 * c1[1] + 3 * c2[1] + by) / 8)
    return d, mid


# ---------------- render ----------------
def render(dg: Diagram):
    reg, colx = layout(dg.grid, dg.blocks)
    port = resolve_ports(dg.conns, reg)
    body = []

    for col, *rest in dg.annotations:
        text = rest[0]
        y = rest[1] if len(rest) > 1 else dg.grid.top - 26
        body.append(txt(colx[col], y, text, "eyebrow", "start"))

    for b in dg.blocks:
        box = reg[b.id]
        cls, _, rx = KINDS[b.kind]
        body.append(f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" '
                    f'height="{box.h:.1f}" rx="{rx}" class="{cls}"/>')
        lines = physical_lines(b, box.w - 2 * CONTENT_PAD)
        total = sum(lh for _, _, lh, _ in lines)
        y = box.cy - total / 2
        for text, lcls, lh, tl in lines:
            yc = y + lh / 2
            if text is None:
                body.append(f'<line class="rule" x1="{box.x+CONTENT_PAD:.1f}" y1="{yc:.1f}" '
                            f'x2="{box.x+box.w-CONTENT_PAD:.1f}" y2="{yc:.1f}"/>')
            else:
                extra = f' textLength="{tl:.0f}" lengthAdjust="spacingAndGlyphs"' if tl else ""
                body.append(txt(box.cx, yc, text, lcls, "middle", extra))
            y += lh

    for i, c in enumerate(dg.conns):
        sa, fa = port[(i, "src")]
        sb, fb = port[(i, "dst")]
        a = reg[c.src].anchor(sa, fa)
        b = reg[c.dst].anchor(sb, fb)
        orient = "h" if sa in ("left", "right") else "v"
        pcls, marker = CONN[c.kind]
        d, mid = bezier(a, b, orient)
        mk = f' marker-end="url(#{marker})"' if marker else ""
        body.append(f'<path class="{pcls}" d="{d}"{mk}/>')
        if c.label:
            body.append(txt(mid[0], mid[1], c.label, "elabel", "middle"))

    W = colx[-1] + dg.grid.col_widths[-1] + dg.grid.pad
    H = max(bx.y + bx.h for bx in reg.values()) + dg.grid.pad
    return (f'<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="{esc(dg.aria)}" '
            f'xmlns="http://www.w3.org/2000/svg">{STYLE}{DEFS}{"".join(body)}</svg>'), W, H


def check(markup, w, h):
    root = ET.fromstring(markup)
    ns = "{http://www.w3.org/2000/svg}"
    for r in root.iter(f"{ns}rect"):
        x, y, bw, bh = (float(r.get(k)) for k in ("x", "y", "width", "height"))
        assert 0 <= x and x + bw <= w and 0 <= y and y + bh <= h, f"rect out of bounds {r.attrib}"
    for t in root.iter(f"{ns}text"):
        assert 0 <= float(t.get("x")) <= w and 0 <= float(t.get("y")) <= h, f"text out of bounds {t.attrib}"


# ---------------- the two diagrams, now pure declarations ----------------
HUB = Diagram(
    grid=Grid(col_widths=[150, 232, 280], node_h=48, gap_x=118, gap_y=14, top=56, pad=40),
    annotations=[(0, "AGENT FLEET"), (2, "FOUR GOVERNANCE DIMENSIONS")],
    blocks=[
        Block("dev", "\U0001F99E DevClaw", col=0, row=0),
        Block("sec", "\U0001F6E1 SecurityClaw", col=0, row=1),
        Block("quant", "\U0001F4C8 QuantClaw", col=0, row=2),
        Block("comp", "⚖ ComplianceClaw", col=0, row=3),
        Block("mem", "MemClaw", kind="core", col=1, row=0, rowspan=4, body=[
            ("Governed shared memory", "coresub"), ("", "rule"),
            ("F = (A, M, G, P, T)", "monoacc"),
            ("multi-tenant · multi-fleet · audited", "faint", "shrink")]),
        Block("scope", "Scope", kind="dim", col=2, row=0, body=[("who may read it", "sub")]),
        Block("time", "Time", kind="dim", col=2, row=1, body=[("which version is current", "sub")]),
        Block("prov", "Provenance", kind="dim", col=2, row=2, body=[("where it came from", "sub")]),
        Block("prop", "Propagation", kind="dim", col=2, row=3, body=[("how it crosses boundaries", "sub")]),
        Block("argus", "ArgusFleet — one probe per dimension", kind="probe", col=1, row=4),
    ],
    conns=[
        Conn("dev", "mem", label="write · recall"), Conn("sec", "mem"),
        Conn("quant", "mem"), Conn("comp", "mem"),
        Conn("mem", "scope", "link"), Conn("mem", "time", "link"),
        Conn("mem", "prov", "link"), Conn("mem", "prop", "link"),
        Conn("argus", "mem", "probe"),
    ],
    aria="System overview: an agent fleet writes to and reads from governed shared memory "
         "through MemClaw, which exposes four governance dimensions, probed by ArgusFleet.")

PIPE = Diagram(
    grid=Grid(col_widths=[158] * 5, node_h=56, gap_x=28, gap_y=14, top=40, pad=8),
    annotations=[(0, "RETRIEVAL = f( query, agent, governance, time )", 24)],
    blocks=[
        Block("cand", "Semantic", kind="node", col=0, body=[("candidates", "sub")]),
        Block("pol", "Policy", kind="step", col=1, body=[("scope · trust", "sub")]),
        Block("temp", "Temporal", kind="step", col=2, body=[("supersession", "sub")]),
        Block("prov", "Provenance", kind="step", col=3, body=[("lineage", "sub")]),
        Block("rank", "Ranked", kind="term", col=4, body=[("delivery", "sub")]),
    ],
    conns=[Conn("cand", "pol"), Conn("pol", "temp"), Conn("temp", "prov"), Conn("prov", "rank")],
    aria="Policy-governed retrieval pipeline: candidate generation, policy filtering, temporal "
         "resolution, provenance enrichment, ranked delivery.")


def load_spec(path):
    ns = {n: globals()[n] for n in ("Diagram", "Grid", "Block", "Conn")}
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), ns)
    if "DIAGRAM" not in ns:
        raise SystemExit(f"{path}: spec must set DIAGRAM = Diagram(...)")
    return ns["DIAGRAM"]


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Render a block-and-connector SVG diagram.")
    ap.add_argument("spec", nargs="?", help="Python spec file that sets DIAGRAM = Diagram(...)")
    ap.add_argument("-o", "--out", help="write to this file instead of stdout")
    ap.add_argument("--demo", action="store_true", help="self-check the built-in HUB/PIPE examples")
    args = ap.parse_args()

    if args.demo or not args.spec:
        for name, dg in [("hub", HUB), ("pipeline", PIPE)]:
            markup, w, h = render(dg)
            check(markup, w, h)
            print(f"{name}: {w:.0f}x{h:.0f} ok ({len(markup)} bytes)", file=sys.stderr)
    else:
        markup, w, h = render(load_spec(args.spec))
        check(markup, w, h)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(markup + "\n")
        else:
            sys.stdout.write(markup + "\n")
