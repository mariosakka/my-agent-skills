#!/usr/bin/env python3
"""
report-to-pdf — Markdown -> polished PDF report generator.

Parses a constrained "report-style" Markdown subset (frontmatter, headings,
paragraphs, bullet/numbered lists, fenced code blocks, pipe tables, hr) and
renders it into a fixed, brand-styled PDF: title page, running header/footer,
auto-generated Table of Contents (back-filled onto page 1 after content
renders), and the same section-renderer visual language as the reference
ColeteOnline user-guide generator
(magento_dev/.../DeliveryMagento/bin/dev/build-user-guide.py) — just driven
by parsing a real .md file instead of a hand-authored Python SECTIONS list.

Usage:
    python3 build_report_pdf.py report.md
    python3 build_report_pdf.py report.md -o out.pdf --logo logo.png
    python3 build_report_pdf.py report.md --vendor "ColeteOnline SRL" \
        --title "Custom Title" --accent "30,80,180"

Dependencies: fpdf2 (import name `fpdf`), Pillow (import name `PIL`),
Pygments (import name `pygments`, for fenced-code syntax highlighting).
All three are checked/auto-installed (best-effort) in main().
"""

import argparse
import io
import re
import sys
from datetime import date
from pathlib import Path

# ── Colours (defaults — override accent via CLI/frontmatter) ─────────────────

C_BRAND   = (220,  50,  50)
C_H1      = ( 30,  30,  30)
C_H2      = ( 60,  60,  60)
C_TEXT    = ( 40,  40,  40)
C_MUTED   = (120, 120, 120)
C_CODE_BG = (245, 245, 245)
C_CODE_FG = ( 50,  50, 160)
C_RULE    = (210, 210, 210)

# Syntax-highlight palette — chosen against the light C_CODE_BG background,
# not any particular Pygments theme. Keyed by Pygments token type; a token
# not listed here is resolved by walking up `.parent` until one matches,
# terminating at the bare `Token` root (see `_code_token_color`).
CODE_STYLES = None  # populated lazily once pygments.token.Token is importable

# ── Layout ────────────────────────────────────────────────────────────────────

MARGIN    = 18
PAGE_W    = 210
CONTENT_W = PAGE_W - 2 * MARGIN

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


# ── Markdown parsing ──────────────────────────────────────────────────────────
#
# Deliberately a small hand-rolled block parser rather than a full Markdown
# engine — this only needs to cover a "report" subset: headings, paragraphs,
# bullet/numbered lists, fenced code blocks, pipe tables, and hr dividers.
#
# Inline **bold** and [text](url) links are left INTACT here and rendered by
# fpdf2's own built-in `markdown=True` support on cell()/multi_cell() calls —
# fpdf2 natively parses **bold**, __italic__, and [text](url) into real
# clickable link annotations, so there's no need (and no reason) to hand-roll
# that. Only single-marker *italic*/_italic_ (not recognized by fpdf2, which
# only understands the double-underscore form) and inline `code` backticks
# (no monospace-inline support in fpdf2's markdown mode) are normalized/
# stripped here, before the text ever reaches a markdown=True render call.

FRONTMATTER_RE = re.compile(r"^---\s*$")
FENCE_RE       = re.compile(r"^```(\S*)\s*$")
HEADING_RE     = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE      = re.compile(r"^[-*+]\s+(.*)$")
NUMBERED_RE    = re.compile(r"^\d+\.\s+(.*)$")
HR_RE          = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
TABLE_ROW_RE   = re.compile(r"^\|.*\|\s*$")
TABLE_SEP_RE   = re.compile(r"^\|?[\s:|-]+\|?$")

# Single-asterisk italics, carefully excluding `**bold**` runs on either side.
SINGLE_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
# Single-underscore italics — `__x__` (fpdf2 italics) is left alone; only a
# lone `_x_` with word boundaries on the outside is normalized.
SINGLE_UNDERSCORE_RE = re.compile(r"(?<!_)(?<!\w)_(?!_)(.+?)(?<!_)_(?!_)(?!\w)")


def prepare_markdown_text(text):
    """Normalize inline markdown so fpdf2's `markdown=True` renderer can
    handle it directly: keep **bold** and [text](url) as-is (fpdf2 renders
    both natively, the latter as a real clickable link), fold single-marker
    italics into fpdf2's `__italic__` form, and strip inline `code`
    backticks to plain text (fpdf2 has no inline-monospace support)."""
    text = SINGLE_STAR_RE.sub(r"__\1__", text)
    text = SINGLE_UNDERSCORE_RE.sub(r"__\1__", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    return text


def parse_frontmatter(lines):
    """If the file opens with a `---` block, parse simple `key: value`
    pairs out of it and return (meta_dict, remaining_lines)."""
    if not lines or not FRONTMATTER_RE.match(lines[0]):
        return {}, lines

    meta = {}
    i = 1
    while i < len(lines) and not FRONTMATTER_RE.match(lines[i]):
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip().strip('"').strip("'")
        i += 1

    return meta, lines[i + 1:]


def parse_markdown(text):
    """Parse markdown body text into a list of block dicts:
    {"type": "h1"|"h2"|"h3"..., "text": str}
    {"type": "p", "text": str}
    {"type": "bullets"|"numbered", "items": [str, ...]}
    {"type": "code", "lang": str, "text": str}
    {"type": "table", "headers": [...], "rows": [[...], ...]}
    {"type": "spacer"}
    Plus a synthetic {"type": "doc_title", "text": str} for the first
    top-level `#` heading found (used for the title page, not the body).
    """
    lines = text.split("\n")
    blocks = []
    doc_title = None
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code block
        fence_match = FENCE_RE.match(stripped)
        if fence_match:
            lang = fence_match.group(1)
            code_lines = []
            i += 1
            while i < n and not FENCE_RE.match(lines[i].strip()):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            blocks.append({
                "type": "code",
                "lang": lang,
                "text": "\n".join(code_lines),
            })
            continue

        # Horizontal rule -> spacer
        if HR_RE.match(stripped):
            blocks.append({"type": "spacer"})
            i += 1
            continue

        # Heading
        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = prepare_markdown_text(heading_match.group(2).strip())
            if level == 1 and doc_title is None:
                doc_title = heading_text
                i += 1
                continue
            blocks.append({"type": f"h{level}", "text": heading_text})
            i += 1
            continue

        # Pipe table
        if TABLE_ROW_RE.match(stripped):
            table_lines = []
            while i < n and TABLE_ROW_RE.match(lines[i].strip()):
                table_lines.append(lines[i].strip())
                i += 1
            headers = [
                c.strip() for c in table_lines[0].strip("|").split("|")
            ]
            data_lines = table_lines[1:]
            if data_lines and TABLE_SEP_RE.match(data_lines[0]):
                data_lines = data_lines[1:]
            rows = []
            for row_line in data_lines:
                cells = [
                    prepare_markdown_text(c.strip())
                    for c in row_line.strip("|").split("|")
                ]
                rows.append(cells)
            blocks.append({
                "type": "table",
                "headers": [prepare_markdown_text(h) for h in headers],
                "rows": rows,
            })
            continue

        # Bullet list
        if BULLET_RE.match(stripped):
            items = []
            while i < n:
                cur = lines[i].strip()
                bullet_match = BULLET_RE.match(cur)
                if bullet_match:
                    items.append(prepare_markdown_text(bullet_match.group(1)))
                    i += 1
                elif cur and not HEADING_RE.match(cur) and not BULLET_RE.match(cur) \
                        and not NUMBERED_RE.match(cur) and not FENCE_RE.match(cur) \
                        and not TABLE_ROW_RE.match(cur) and not HR_RE.match(cur) \
                        and items and (len(lines[i]) - len(lines[i].lstrip())) > 0:
                    # indented continuation line — append to previous item
                    items[-1] += " " + prepare_markdown_text(cur)
                    i += 1
                else:
                    break
            blocks.append({"type": "bullets", "items": items})
            continue

        # Numbered list
        if NUMBERED_RE.match(stripped):
            items = []
            while i < n:
                cur = lines[i].strip()
                numbered_match = NUMBERED_RE.match(cur)
                if numbered_match:
                    items.append(prepare_markdown_text(numbered_match.group(1)))
                    i += 1
                elif cur and not HEADING_RE.match(cur) and not BULLET_RE.match(cur) \
                        and not NUMBERED_RE.match(cur) and not FENCE_RE.match(cur) \
                        and not TABLE_ROW_RE.match(cur) and not HR_RE.match(cur) \
                        and items and (len(lines[i]) - len(lines[i].lstrip())) > 0:
                    items[-1] += " " + prepare_markdown_text(cur)
                    i += 1
                else:
                    break
            blocks.append({"type": "numbered", "items": items})
            continue

        # Paragraph — collect consecutive plain lines until a blank line or
        # the start of another block type
        para_lines = []
        while i < n:
            cur = lines[i].strip()
            if not cur or HEADING_RE.match(cur) or BULLET_RE.match(cur) \
                    or NUMBERED_RE.match(cur) or FENCE_RE.match(cur) \
                    or TABLE_ROW_RE.match(cur) or HR_RE.match(cur):
                break
            para_lines.append(cur)
            i += 1
        blocks.append({
            "type": "p",
            "text": prepare_markdown_text(" ".join(para_lines)),
        })

    return doc_title, blocks


def load_logo_png(path):
    """Load any Pillow-readable image (WebP, PNG, …) as a PNG BytesIO."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            w_px, h_px = img.size
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[3])
            elif img.mode == "P" and "transparency" in img.info:
                rgba = img.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[3])
            else:
                bg.paste(img.convert("RGB"))
        buf = io.BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)

        return buf, w_px, h_px
    except Exception as exc:
        print(f"  warning: logo not loaded: {exc}")

        return None, 0, 0


# ── Syntax highlighting (fenced code blocks) ──────────────────────────────────
#
# Real tokenization via Pygments, not a hand-rolled regex highlighter — code
# is exactly the kind of thing a small ad hoc parser gets subtly wrong (string
# escapes, nested comments, template literals). Falls back to flat, single-
# color rendering (the pre-highlighting behavior) whenever a language tag is
# missing, unrecognized by Pygments, or Pygments itself isn't importable —
# highlighting is a bonus, never a hard requirement to render a code block.

def _code_styles():
    """Build (lazily, once Pygments is known importable) the token-type ->
    RGB color table used by `_code_token_color`."""
    global CODE_STYLES
    if CODE_STYLES is not None:
        return CODE_STYLES

    from pygments.token import Token

    CODE_STYLES = {
        Token:                    C_CODE_FG,        # fallback: plain code color
        Token.Keyword:            (170,  30, 130),
        Token.Name.Builtin:       (  0, 110, 110),
        Token.Name.Builtin.Pseudo:(  0, 110, 110),
        Token.Name.Function:      (  0,  90, 170),
        Token.Name.Class:         (  0,  90, 170),
        Token.Name.Decorator:     (150, 100,   0),
        Token.Name.Tag:           (170,  30, 130),
        Token.Name.Attribute:     (  0,  90, 170),
        Token.Literal.String:     ( 20, 130,  20),
        Token.Literal.Number:     (180,  90,   0),
        Token.Comment:            (130, 130, 130),
        Token.Operator:           (120,  40,  40),
        Token.Punctuation:        C_CODE_FG,
        Token.Error:              (200,   0,   0),
    }

    return CODE_STYLES


def _code_token_color(ttype):
    """Walk a Pygments token type up its `.parent` chain until one is found
    in the style table — e.g. Token.Keyword.Declaration has no entry of its
    own, but its parent Token.Keyword does. The bare `Token` root is always
    in the table, so this always terminates."""
    styles = _code_styles()
    t = ttype
    while t not in styles:
        t = t.parent

    return styles[t]


def _get_code_lexer(lang):
    """Return a Pygments lexer for `lang`, or None if unavailable/unknown —
    None means "render this block in flat, unhighlighted color", never an
    error. A handful of common aliases are covered for tags people actually
    write in fenced blocks that don't match a Pygments lexer name exactly."""
    if not lang:
        return None

    try:
        from pygments.lexers import get_lexer_by_name
        from pygments.util import ClassNotFound
    except ImportError:
        return None

    aliases = {
        "ts": "typescript", "tsx": "typescript",
        "js": "javascript", "jsx": "javascript",
        "sh": "bash", "shell": "bash", "zsh": "bash",
        "yml": "yaml", "prisma": "graphql",  # closest built-in match
    }
    for name in (lang, aliases.get(lang.lower())):
        if not name:
            continue
        try:
            return get_lexer_by_name(name, stripall=False)
        except ClassNotFound:
            continue

    return None


def _tokenize_lines(lexer, text):
    """Tokenize `text` with `lexer` and regroup the token stream by source
    line, returning a list (one entry per line in `text.split("\\n")`) of
    `[(color, token_text), ...]` segments. A single token can itself span
    multiple lines (block comments, template literals) and is split at each
    embedded newline. Returns None on any mismatch or failure — callers
    should treat that as "fall back to flat rendering", not an error."""
    try:
        lines = [[]]
        for ttype, value in lexer.get_tokens(text):
            color = _code_token_color(ttype)
            parts = value.split("\n")
            for i, part in enumerate(parts):
                if part:
                    lines[-1].append((color, part))
                if i < len(parts) - 1:
                    lines.append([])

        # Pygments' get_tokens() ends the stream with a forced trailing
        # newline, which produces one extra empty trailing line entry here.
        if lines and not lines[-1]:
            lines.pop()

        expected = len(text.split("\n"))
        if len(lines) != expected:
            return None  # tokenizer disagreed on line count — don't guess

        return lines
    except Exception:
        return None


# ── PDF class ─────────────────────────────────────────────────────────────────

class ReportPDF:
    """Thin wrapper is unnecessary — subclass FPDF directly, as the
    reference script does."""


def make_pdf_class(accent):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    class _ReportPDF(FPDF):
        def __init__(self, meta):
            super().__init__(orientation="P", unit="mm", format="A4")
            self.meta = meta
            self.set_margins(MARGIN, MARGIN, MARGIN)
            self.set_auto_page_break(auto=True, margin=22)
            self.add_font(
                "DejaVu", fname=str(FONT_DIR / "DejaVuSans.ttf"))
            self.add_font(
                "DejaVu", style="B",
                fname=str(FONT_DIR / "DejaVuSans-Bold.ttf"))
            self.add_font(
                "DejaVu", style="I",
                fname=str(FONT_DIR / "DejaVuSans-Oblique.ttf"))
            self.add_font(
                "DejaVu", style="BI",
                fname=str(FONT_DIR / "DejaVuSans-BoldOblique.ttf"))
            self.add_font(
                "DejaVuMono", fname=str(FONT_DIR / "DejaVuSansMono.ttf"))
            self._toc_entries = []
            self._toc_y       = None
            # fpdf2's markdown=True renderer turns [text](url) into a real
            # clickable link annotation, underlined by default — give it a
            # distinct color so it actually reads as a link, not plain text.
            self.MARKDOWN_LINK_COLOR = (30, 90, 180)

        # ── Header / Footer ───────────────────────────────────────────────

        def header(self):
            if self.page <= 1:
                return
            # Running header is one line by design (it repeats on every
            # page) — shrink the font rather than let a long title run off
            # the right edge, since cell() doesn't wrap.
            size = 8
            self.set_font("DejaVu", size=size)
            title = self.meta["title"]
            while self.get_string_width(title) > CONTENT_W and size > 5:
                size -= 0.5
                self.set_font("DejaVu", size=size)
            self.set_text_color(*C_MUTED)
            self.cell(0, 6, title, new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(1)

        def footer(self):
            if self.page <= 1:
                return
            self.set_y(-14)
            self.set_draw_color(*C_RULE)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(1)
            self.set_font("DejaVu", size=8)
            self.set_text_color(*C_MUTED)
            self.cell(0, 6, f"Page {self.page - 1}", align="R",
                      new_x=XPos.RIGHT, new_y=YPos.TOP)

        # ── Title page ────────────────────────────────────────────────────

        def title_page(self, logo_buf=None, logo_w_px=1, logo_h_px=1):
            self.add_page()

            self.set_fill_color(*accent)
            self.rect(0, 0, PAGE_W, 10, style="F")

            y = 18

            if logo_buf:
                logo_mm_w = 52
                logo_mm_h = logo_mm_w * logo_h_px / logo_w_px
                self.image(logo_buf, x=(PAGE_W - logo_mm_w) / 2, y=y,
                           w=logo_mm_w, h=logo_mm_h)
                y += logo_mm_h + 8

            self.set_y(y)

            title = self.meta["title"]
            for size in [24, 22, 20, 18, 16]:
                self.set_font("DejaVu", style="B", size=size)
                if self.get_string_width(title) <= CONTENT_W - 2:
                    break
            self.set_text_color(*C_H1)
            self.multi_cell(0, 10, title, align="C",
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(2)

            if self.meta.get("subtitle"):
                # A long subtitle centered via cell() draws at a computed
                # x that can run off both edges of the page — multi_cell
                # wraps it within the content width instead.
                self.set_font("DejaVu", size=14)
                self.set_text_color(*C_MUTED)
                self.multi_cell(CONTENT_W, 8, self.meta["subtitle"],
                                align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
                self.ln(1)

            self.set_font("DejaVu", size=10)
            self.set_text_color(*C_MUTED)
            self.multi_cell(CONTENT_W, 6, f"Version {self.meta['version']}",
                            align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.ln(10)
            self._toc_y = self.get_y()

            # Copyright pinned to page bottom — disable auto-page-break so
            # set_y(-18) doesn't trigger a phantom extra page
            self.set_auto_page_break(False)
            self.set_y(-18)
            self.set_draw_color(*C_RULE)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(2)
            self.set_font("DejaVu", size=8)
            self.set_text_color(*C_MUTED)
            if self.meta.get("vendor"):
                self.multi_cell(CONTENT_W, 5, f"© {self.meta['vendor']}",
                                align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.set_auto_page_break(True, margin=22)

        # ── TOC back-fill ─────────────────────────────────────────────────

        def write_toc(self):
            """Write the Table of Contents onto page 1 after all content
            has rendered — this is the only way to know final page numbers
            with fpdf2's single forward pass."""
            if self._toc_y is None or not self._toc_entries:
                return

            last_page = self.page
            self.page  = 1
            self.set_xy(MARGIN, self._toc_y)

            # A long section list can run past the bottom of page 1 —
            # auto-page-break must stay OFF for this whole back-fill, or
            # fpdf2 inserting a "new" page mid-back-fill (while self.page is
            # artificially pinned to 1) corrupts whatever real page follows.
            # Entries that don't fit are clipped rather than triggering a
            # page break — the same tradeoff title_page() already makes for
            # the copyright line.
            self.set_auto_page_break(False)

            self.set_font("DejaVu", style="B", size=12)
            self.set_text_color(*C_H2)
            self.cell(0, 7, "Contents", new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.set_draw_color(*C_RULE)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(4)

            # title_page() reserves the last ~18mm of page 1 for a fixed
            # copyright line — TOC rows must stop well clear of it, not just
            # clear of the normal auto-page-break margin.
            toc_bottom_limit = self.h - 26
            row_h = 6.5 if len(self._toc_entries) <= 22 else 6.0

            for title, abs_page in self._toc_entries:
                display_page = abs_page - 1
                y_row = self.get_y()
                if y_row + row_h > toc_bottom_limit:
                    break  # ran out of room on page 1 — clip, don't overflow

                num_str = str(display_page)
                self.set_font("DejaVu", size=10)
                num_w = self.get_string_width(num_str) + 2
                title_max_w = CONTENT_W - num_w - 6

                # Long entry titles shrink to fit their single-line slot
                # rather than running into the dot-leader/page-number area.
                size = 10
                self.set_font("DejaVu", size=size)
                while (self.get_string_width(title) > title_max_w
                        and size > 7):
                    size -= 0.5
                    self.set_font("DejaVu", size=size)

                self.set_text_color(*C_TEXT)
                self.set_xy(MARGIN, y_row)
                self.cell(title_max_w, row_h, title,
                          new_x=XPos.LEFT, new_y=YPos.TOP)

                title_x_end = MARGIN + self.get_string_width(title) + 2
                dot_gap = (PAGE_W - MARGIN - num_w) - title_x_end
                if dot_gap > 3:
                    self.set_font("DejaVu", size=10)
                    dot_w    = self.get_string_width(".")
                    n_dots   = max(0, int(dot_gap / (dot_w + 0.3)) - 1)
                    dots_str = " " + "." * n_dots
                    self.set_xy(title_x_end, y_row)
                    self.set_text_color(*C_MUTED)
                    self.cell(dot_gap, row_h, dots_str,
                              new_x=XPos.LEFT, new_y=YPos.TOP)

                self.set_font("DejaVu", size=10)
                self.set_xy(PAGE_W - MARGIN - num_w, y_row)
                self.set_text_color(*C_MUTED)
                self.cell(num_w, row_h, num_str, align="R",
                          new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.set_auto_page_break(True, margin=22)
            self.page = last_page

        # ── Helpers ───────────────────────────────────────────────────────

        def _text(self, txt, size=10, bold=False, color=C_TEXT, line_h=5.5):
            self.set_font("DejaVu", style="B" if bold else "", size=size)
            self.set_text_color(*color)
            self.multi_cell(CONTENT_W, line_h, txt, markdown=True,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)

        # ── Section renderers ───────────────────────────────────────────────
        # Three distinct heading tiers (documented in SKILL.md):
        #   `#`    -> render_h1: MAJOR heading. Always starts its own fresh
        #             page, big colored left bar, biggest bold text, gets a
        #             TOC entry. For real top-level divisions only — this is
        #             the one tier that costs a page break.
        #   `##`   -> render_h2: SUBHEADING. Same page as whatever came
        #             before it (no forced page break — a subheading right
        #             after a bare major heading, or after a paragraph,
        #             just continues the flow); accent-colored bold text
        #             with a short accent-colored rule under just the text,
        #             visually distinct from both tiers above and below it.
        #             Still gets a TOC entry. Has its own "don't strand a
        #             heading at the very bottom of a page" check, since
        #             nothing else forces it onto a fresh page for it.
        #   `###`+ -> render_h3: tertiary heading. Bold, neutral gray, full-
        #             width thin rule, no page break, no TOC entry — for
        #             fine-grained subsections that don't need navigating to
        #             directly.

        def render_h1(self, text):
            # Every major section always starts its own fresh page — unless
            # nothing has been rendered on the current page yet (cursor
            # still at the top margin), in which case forcing a page break
            # would just waste a blank page. Checking cursor position
            # matters because a report can have intro content (paragraphs,
            # a table) before its first heading, or several headings with
            # nothing in between them.
            if self.get_y() > MARGIN + 2:
                self.add_page()
            else:
                self.ln(4)

            self._toc_entries.append((text, self.page))

            text_w = CONTENT_W - 7
            line_h = 7
            self.set_font("DejaVu", style="B", size=16)
            # Long headings need to wrap like any other text block — measure
            # the wrapped line count first so the accent bar can grow to
            # match instead of a fixed height that a one-line heading was
            # sized for.
            wrapped = self.multi_cell(
                text_w, line_h, text, markdown=True,
                dry_run=True, output="LINES")
            bar_h = max(10, len(wrapped) * line_h + 3)

            y0 = self.get_y()
            self.set_fill_color(*accent)
            self.rect(MARGIN, y0, 3, bar_h, style="F")

            self.set_xy(MARGIN + 7, y0)
            self.set_text_color(*C_H1)
            self.multi_cell(text_w, line_h, text, markdown=True,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(3)

        def render_h2(self, text):
            self.ln(4)
            line_h = 6.5
            self.set_font("DejaVu", style="B", size=13)
            # Subheadings never force a page break, but a heading stranded
            # as the very last line on a page (with its content starting
            # fresh on the next one) reads just as badly as one landing
            # mid-paragraph — leave room for the heading itself plus a
            # little breathing room before deciding it still fits here.
            wrapped = self.multi_cell(
                CONTENT_W, line_h, text, markdown=True,
                dry_run=True, output="LINES")
            needed_h = len(wrapped) * line_h + 12
            if self.get_y() + needed_h > self.h - self.b_margin:
                self.add_page()

            self._toc_entries.append((text, self.page))

            self.set_text_color(*accent)
            self.multi_cell(CONTENT_W, line_h, text, markdown=True,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            rule_w = min(CONTENT_W, self.get_string_width(text) + 4)
            self.set_draw_color(*accent)
            self.line(MARGIN, self.get_y(), MARGIN + rule_w, self.get_y())
            self.ln(3)

        def render_h3(self, text):
            self.ln(4)
            self.set_font("DejaVu", style="B", size=12)
            self.set_text_color(*C_H2)
            self.multi_cell(CONTENT_W, 7, text, markdown=True,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.set_draw_color(*C_RULE)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(3)

        def render_p(self, text):
            self._text(text, size=10, color=C_TEXT, line_h=5.5)
            self.ln(1)

        def render_bullets(self, items):
            self.set_font("DejaVu", size=10)
            self.set_text_color(*C_TEXT)
            indent = 6
            for item in items:
                self.set_x(MARGIN + indent)
                self.cell(5, 5.5, "•",
                          new_x=XPos.RIGHT, new_y=YPos.TOP)
                self.multi_cell(CONTENT_W - indent - 5, 5.5, item,
                                markdown=True,
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(1)

        def render_numbered(self, items):
            self.set_font("DejaVu", size=10)
            self.set_text_color(*C_TEXT)
            indent = 6
            for i, item in enumerate(items, 1):
                self.set_x(MARGIN + indent)
                self.set_font("DejaVu", style="B", size=10)
                self.cell(7, 5.5, f"{i}.", new_x=XPos.RIGHT, new_y=YPos.TOP)
                self.set_font("DejaVu", size=10)
                self.multi_cell(CONTENT_W - indent - 7, 5.5, item,
                                markdown=True,
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(1)

        def render_code(self, text, lang=""):
            self.ln(2)
            if lang:
                self.set_font("DejaVu", style="I", size=8)
                self.set_text_color(*C_MUTED)
                self.cell(0, 5, lang, new_x=XPos.LEFT, new_y=YPos.NEXT)

            lines    = text.split("\n")
            pad      = 3
            avail_w  = CONTENT_W - pad * 2
            base_size = 8.5

            # Real tokenization via Pygments, keyed off the fence's language
            # tag — None (no tag, unrecognized language, or Pygments itself
            # unavailable) means "render in flat color", never an error.
            lexer = _get_code_lexer(lang)
            tokenized = _tokenize_lines(lexer, text) if lexer else None

            # Code shouldn't reflow (it's monospace, indentation-sensitive),
            # but a single long line (a long URL, an unbroken string) can
            # otherwise run straight past the box border and over whatever
            # follows. Measure the widest line and shrink the whole block's
            # font uniformly — never per-line, or the monospace grid breaks,
            # and highlighting colors don't affect character width — so
            # everything fits within the content width.
            self.set_font("DejaVuMono", size=base_size)
            max_line_w = max(
                (self.get_string_width(line) for line in lines), default=0)
            font_size = base_size
            if max_line_w > avail_w > 0:
                font_size = max(5.5, base_size * avail_w / max_line_w)
                self.set_font("DejaVuMono", size=font_size)

            line_h  = font_size / base_size * 4.5
            block_h = len(lines) * line_h + pad * 2

            # Fixed-width monospace block can overflow the page height for
            # very long snippets — start a fresh page rather than letting a
            # tall rect run past the footer.
            if self.get_y() + block_h > self.h - self.b_margin:
                self.add_page()

            self.set_fill_color(*C_CODE_BG)
            self.set_draw_color(*C_RULE)
            x, y = MARGIN, self.get_y()
            self.rect(x, y, CONTENT_W, block_h, style="FD")
            self.set_xy(x + pad, y + pad)

            for i, line in enumerate(lines):
                row_y = y + pad + i * line_h
                self.set_xy(x + pad, row_y)
                segments = tokenized[i] if tokenized else [(C_CODE_FG, line)]
                for color, token_text in segments:
                    self.set_text_color(*color)
                    self.cell(self.get_string_width(token_text), line_h,
                              token_text, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_xy(x, y + pad + len(lines) * line_h)
            self.ln(4)

        def render_table(self, headers, rows):
            self.ln(2)
            n_cols = len(headers)
            col_w  = [CONTENT_W / n_cols] * n_cols

            self.set_font("DejaVu", style="B", size=9)
            header_lines = max(
                len(self.multi_cell(col_w[j], 5, headers[j], markdown=True,
                                    dry_run=True, output="LINES"))
                for j in range(n_cols)
            )
            header_h = max(6, header_lines * 5 + 2)

            self.set_text_color(255, 255, 255)
            y0 = self.get_y()
            x0 = MARGIN
            for j, h in enumerate(headers):
                self.set_fill_color(*C_H2)
                self.set_draw_color(*C_RULE)
                self.rect(x0, y0, col_w[j], header_h, style="FD")
                self.set_xy(x0 + 1, y0 + 1)
                self.multi_cell(col_w[j] - 2, 5, h, markdown=True,
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
                x0 += col_w[j]
            self.set_y(y0 + header_h)

            self.set_font("DejaVu", size=9)
            self.set_text_color(*C_TEXT)
            fill = False
            for row in rows:
                cells = list(row) + [""] * (n_cols - len(row))
                max_lines = max(
                    len(self.multi_cell(col_w[j], 5, cells[j], markdown=True,
                                        dry_run=True, output="LINES"))
                    for j in range(n_cols)
                )
                row_h = max_lines * 5 + 4

                if self.get_y() + row_h > self.h - self.b_margin:
                    self.add_page()

                y0 = self.get_y()
                x0 = MARGIN
                for j in range(n_cols):
                    bg = (245, 245, 245) if fill else (255, 255, 255)
                    self.set_fill_color(*bg)
                    self.set_draw_color(*C_RULE)
                    self.rect(x0, y0, col_w[j], row_h, style="FD")
                    self.set_xy(x0 + 2, y0 + 2)
                    self.multi_cell(col_w[j] - 4, 5, cells[j], markdown=True,
                                    new_x=XPos.LEFT, new_y=YPos.NEXT)
                    x0 += col_w[j]
                self.set_y(y0 + row_h)
                fill = not fill
            self.ln(3)

        def render_spacer(self):
            self.ln(4)

        # ── Main renderer ─────────────────────────────────────────────────

        def render(self, blocks):
            for block in blocks:
                btype = block["type"]
                if btype.startswith("h") and btype[1:].isdigit():
                    level = int(btype[1:])
                    # Only the very FIRST `#` in the whole document is
                    # consumed as the doc title (see parse_markdown) — any
                    # later `#` still reaches here as a level-1 block, same
                    # as every other. Three tiers: level 1 -> major heading
                    # (own page, big accent bar); level 2 -> subheading
                    # (accent-colored, no page break); level 3+ -> tertiary
                    # (bold+rule, no TOC entry).
                    if level == 1:
                        self.render_h1(block["text"])
                    elif level == 2:
                        self.render_h2(block["text"])
                    else:
                        self.render_h3(block["text"])
                elif btype == "p":
                    self.render_p(block["text"])
                elif btype == "bullets":
                    self.render_bullets(block["items"])
                elif btype == "numbered":
                    self.render_numbered(block["items"])
                elif btype == "code":
                    self.render_code(block["text"], block.get("lang", ""))
                elif btype == "table":
                    self.render_table(block["headers"], block["rows"])
                elif btype == "spacer":
                    self.render_spacer()
                else:
                    print(f"  warning: unknown block type: {btype!r}")

    return _ReportPDF


# ── Entry point ────────────────────────────────────────────────────────────────

def ensure_dependencies():
    missing = []
    try:
        import fpdf  # noqa: F401
    except ImportError:
        missing.append("fpdf2")
    try:
        import PIL  # noqa: F401
    except ImportError:
        missing.append("Pillow")
    try:
        import pygments  # noqa: F401
    except ImportError:
        missing.append("Pygments")

    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}…")
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", *missing, "-q"],
            check=False,
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a Markdown report into a polished PDF.")
    parser.add_argument("input", type=Path, help="Input .md file")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output .pdf path (default: <input>.pdf)")
    parser.add_argument("--logo", type=Path, default=None,
                        help="Optional logo image (PNG/WebP/JPEG)")
    parser.add_argument("--title", default=None, help="Override title")
    parser.add_argument("--subtitle", default=None, help="Override subtitle")
    parser.add_argument("--version", default=None, help="Override version")
    parser.add_argument("--vendor", default=None,
                        help="Copyright line vendor name")
    parser.add_argument("--accent", default=None,
                        help='Accent color as "R,G,B", e.g. "30,80,180"')

    return parser.parse_args()


def main():
    args = parse_args()
    ensure_dependencies()

    input_path = args.input
    if not input_path.exists():
        print(f"error: input file not found: {input_path}")
        sys.exit(1)

    output_path = args.output or input_path.with_suffix(".pdf")

    raw_text = input_path.read_text(encoding="utf-8")
    lines = raw_text.split("\n")
    frontmatter, remaining_lines = parse_frontmatter(lines)
    body_text = "\n".join(remaining_lines)
    doc_title, blocks = parse_markdown(body_text)

    meta = {
        "title": (
            args.title or frontmatter.get("title") or doc_title
            or input_path.stem
        ),
        "subtitle": args.subtitle or frontmatter.get("subtitle", ""),
        "version": (
            args.version or frontmatter.get("version")
            or date.today().isoformat()
        ),
        "vendor": args.vendor or frontmatter.get("vendor", ""),
    }

    accent = C_BRAND
    accent_spec = args.accent or frontmatter.get("accent")
    if accent_spec:
        try:
            accent = tuple(int(v.strip()) for v in accent_spec.split(","))
        except ValueError:
            print(f"  warning: invalid --accent {accent_spec!r}, using default")
            accent = C_BRAND

    logo_path = args.logo
    logo_buf, logo_w, logo_h = (
        load_logo_png(logo_path) if logo_path and logo_path.exists()
        else (None, 0, 0)
    )

    print("=" * 55)
    print("report-to-pdf — Markdown -> PDF")
    print(f"  Input   : {input_path}")
    print(f"  Output  : {output_path}")
    print(f"  Title   : {meta['title']}")
    print(f"  Blocks  : {len(blocks)}")
    print("=" * 55)

    PDFClass = make_pdf_class(accent)
    pdf = PDFClass(meta)
    pdf.title_page(logo_buf, logo_w, logo_h)
    pdf.add_page()
    pdf.render(blocks)
    pdf.write_toc()
    pdf.output(str(output_path))

    print(f"\nCreated: {output_path}")
    print(f"  Size: {output_path.stat().st_size // 1024} KB")
    print(f"  Pages: {pdf.page}")


if __name__ == "__main__":
    main()
