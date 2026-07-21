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

Dependencies: fpdf2 (import name `fpdf`), Pillow (import name `PIL`).
Both are checked/auto-installed (best-effort) in main().
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
# Inline emphasis (**bold**, *italic*, _em_, `code`) is *stripped*, not
# rendered — fpdf's core/DejaVu fonts don't do inline bold spans inside a
# single multi_cell without manual character-by-character width tracking,
# which is a rabbit hole not worth it for a first version. See SKILL.md.

FRONTMATTER_RE = re.compile(r"^---\s*$")
FENCE_RE       = re.compile(r"^```(\S*)\s*$")
HEADING_RE     = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE      = re.compile(r"^[-*+]\s+(.*)$")
NUMBERED_RE    = re.compile(r"^\d+\.\s+(.*)$")
HR_RE          = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
TABLE_ROW_RE   = re.compile(r"^\|.*\|\s*$")
TABLE_SEP_RE   = re.compile(r"^\|?[\s:|-]+\|?$")


def strip_inline_emphasis(text):
    """Strip markdown inline emphasis/backticks/links — render plain text."""
    # Links: [text](url) -> text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    # Bold/italic: **x**, __x__, *x*, _x_
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    # Inline code: `x` -> x
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
            heading_text = strip_inline_emphasis(heading_match.group(2).strip())
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
                    strip_inline_emphasis(c.strip())
                    for c in row_line.strip("|").split("|")
                ]
                rows.append(cells)
            blocks.append({
                "type": "table",
                "headers": [strip_inline_emphasis(h) for h in headers],
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
                    items.append(strip_inline_emphasis(bullet_match.group(1)))
                    i += 1
                elif cur and not HEADING_RE.match(cur) and not BULLET_RE.match(cur) \
                        and not NUMBERED_RE.match(cur) and not FENCE_RE.match(cur) \
                        and not TABLE_ROW_RE.match(cur) and not HR_RE.match(cur) \
                        and items and (len(lines[i]) - len(lines[i].lstrip())) > 0:
                    # indented continuation line — append to previous item
                    items[-1] += " " + strip_inline_emphasis(cur)
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
                    items.append(strip_inline_emphasis(numbered_match.group(1)))
                    i += 1
                elif cur and not HEADING_RE.match(cur) and not BULLET_RE.match(cur) \
                        and not NUMBERED_RE.match(cur) and not FENCE_RE.match(cur) \
                        and not TABLE_ROW_RE.match(cur) and not HR_RE.match(cur) \
                        and items and (len(lines[i]) - len(lines[i].lstrip())) > 0:
                    items[-1] += " " + strip_inline_emphasis(cur)
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
            "text": strip_inline_emphasis(" ".join(para_lines)),
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
                "DejaVuMono", fname=str(FONT_DIR / "DejaVuSansMono.ttf"))
            self._h1_count    = 0
            self._toc_entries = []
            self._toc_y       = None

        # ── Header / Footer ───────────────────────────────────────────────

        def header(self):
            if self.page <= 1:
                return
            self.set_font("DejaVu", size=8)
            self.set_text_color(*C_MUTED)
            self.cell(0, 6, self.meta["title"],
                      new_x=XPos.LEFT, new_y=YPos.NEXT)
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
                self.set_font("DejaVu", size=14)
                self.set_text_color(*C_MUTED)
                self.cell(0, 8, self.meta["subtitle"], align="C",
                          new_x=XPos.LEFT, new_y=YPos.NEXT)
                self.ln(1)

            self.set_font("DejaVu", size=10)
            self.set_text_color(*C_MUTED)
            self.cell(0, 6, f"Version {self.meta['version']}", align="C",
                      new_x=XPos.LEFT, new_y=YPos.NEXT)

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
                self.cell(0, 5, f"© {self.meta['vendor']}", align="C",
                          new_x=XPos.LEFT, new_y=YPos.NEXT)
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

            self.set_font("DejaVu", style="B", size=12)
            self.set_text_color(*C_H2)
            self.cell(0, 7, "Contents", new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.set_draw_color(*C_RULE)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(4)

            for title, abs_page in self._toc_entries:
                display_page = abs_page - 1
                y_row = self.get_y()

                self.set_font("DejaVu", size=10)
                self.set_text_color(*C_TEXT)
                self.set_xy(MARGIN, y_row)
                self.cell(CONTENT_W - 16, 6.5, title,
                          new_x=XPos.LEFT, new_y=YPos.TOP)

                title_x_end = MARGIN + self.get_string_width(title) + 2
                num_str = str(display_page)
                num_w   = self.get_string_width(num_str) + 2
                dot_gap = (PAGE_W - MARGIN - num_w) - title_x_end
                if dot_gap > 3:
                    dot_w    = self.get_string_width(".")
                    n_dots   = max(0, int(dot_gap / (dot_w + 0.3)) - 1)
                    dots_str = " " + "." * n_dots
                    self.set_xy(title_x_end, y_row)
                    self.set_text_color(*C_MUTED)
                    self.cell(dot_gap, 6.5, dots_str,
                              new_x=XPos.LEFT, new_y=YPos.TOP)

                self.set_xy(PAGE_W - MARGIN - num_w, y_row)
                self.set_text_color(*C_MUTED)
                self.cell(num_w, 6.5, num_str, align="R",
                          new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.page = last_page

        # ── Helpers ───────────────────────────────────────────────────────

        def _text(self, txt, size=10, bold=False, color=C_TEXT, line_h=5.5):
            self.set_font("DejaVu", style="B" if bold else "", size=size)
            self.set_text_color(*color)
            self.multi_cell(CONTENT_W, line_h, txt,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)

        # ── Section renderers ───────────────────────────────────────────────
        # Mapping from markdown heading level to renderer (documented in
        # SKILL.md): frontmatter/first `#` -> title page only; markdown `##`
        # -> render_h1 (new page + accent bar, gets a TOC entry); markdown
        # `###`+ -> render_h2 (bold + rule, no TOC entry).

        def render_h1(self, text):
            self._h1_count += 1
            if self._h1_count > 1:
                self.add_page()
            else:
                self.ln(4)

            self._toc_entries.append((text, self.page))

            y0    = self.get_y()
            bar_h = 10
            self.set_fill_color(*accent)
            self.rect(MARGIN, y0, 3, bar_h, style="F")

            self.set_xy(MARGIN + 7, y0)
            self.set_font("DejaVu", style="B", size=16)
            self.set_text_color(*C_H1)
            self.cell(CONTENT_W - 7, bar_h, text,
                      new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(3)

        def render_h2(self, text):
            self.ln(4)
            self.set_font("DejaVu", style="B", size=12)
            self.set_text_color(*C_H2)
            self.multi_cell(CONTENT_W, 7, text,
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
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(1)

        def render_code(self, text, lang=""):
            self.ln(2)
            if lang:
                self.set_font("DejaVu", style="I", size=8)
                self.set_text_color(*C_MUTED)
                self.cell(0, 5, lang, new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.set_fill_color(*C_CODE_BG)
            self.set_draw_color(*C_RULE)
            self.set_font("DejaVuMono", size=8.5)
            self.set_text_color(*C_CODE_FG)
            lines   = text.split("\n")
            pad     = 3
            block_h = len(lines) * 4.5 + pad * 2

            # Fixed-width monospace block can overflow the page height for
            # very long snippets — start a fresh page rather than letting a
            # tall rect run past the footer.
            if self.get_y() + block_h > self.h - self.b_margin:
                self.add_page()

            x, y = MARGIN, self.get_y()
            self.rect(x, y, CONTENT_W, block_h, style="FD")
            self.set_xy(x + pad, y + pad)
            for line in lines:
                self.set_x(x + pad)
                self.cell(CONTENT_W - pad * 2, 4.5, line,
                          new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(4)

        def render_table(self, headers, rows):
            self.ln(2)
            n_cols = len(headers)
            col_w  = [CONTENT_W / n_cols] * n_cols

            self.set_font("DejaVu", style="B", size=9)
            self.set_text_color(255, 255, 255)
            self.set_fill_color(*C_H2)
            for i, h in enumerate(headers):
                self.cell(col_w[i], 6, h, border=1, fill=True,
                          new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.ln()

            self.set_font("DejaVu", size=9)
            self.set_text_color(*C_TEXT)
            fill = False
            for row in rows:
                cells = list(row) + [""] * (n_cols - len(row))
                max_lines = max(
                    len(self.multi_cell(col_w[j], 5, cells[j],
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
                    self.multi_cell(col_w[j] - 4, 5, cells[j],
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
                    # Markdown level 1 (`#`) is consumed as the doc title and
                    # never reaches here as a body block (see parse_markdown).
                    # Level 2 (`##`) is the body's top-level section -> the
                    # page-break/accent-bar/TOC-entry renderer. Level 3+
                    # (`###`, `####`, ...) all collapse onto the bold+rule
                    # subsection renderer.
                    if level <= 2:
                        self.render_h1(block["text"])
                    else:
                        self.render_h2(block["text"])
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
