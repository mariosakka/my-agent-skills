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
    python3 build_report_pdf.py report.md --dark  # dark theme

Dependencies: fpdf2 (import name `fpdf`), Pillow (import name `PIL`),
Pygments (import name `pygments`, for fenced-code syntax highlighting).
All three are checked/auto-installed (best-effort) in main().
"""

import argparse
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

# ── Colours (defaults — override accent via CLI/frontmatter) ─────────────────
#
# Two full palettes: LIGHT (the original, unsuffixed names — used unless
# --dark / frontmatter `theme: dark` is set) and DARK (explicit _DARK
# suffix). `make_pdf_class(accent, dark)` picks one set of *lowercase*
# locals from these at build time and every render method closes over
# those locals — see make_pdf_class for why they're lowercase.

C_BRAND   = (220,  50,  50)
C_H1      = ( 30,  30,  30)
C_H2      = ( 60,  60,  60)
C_TEXT    = ( 40,  40,  40)
C_MUTED   = (120, 120, 120)
C_CODE_BG = (245, 245, 245)
C_CODE_FG = ( 50,  50, 160)
C_RULE    = (210, 210, 210)
C_LINK    = ( 30,  90, 180)
C_TABLE_HEAD_BG = C_H2
C_ROW_BASE      = (255, 255, 255)
C_ROW_ALT       = (245, 245, 245)

C_PAGE_BG_DARK       = ( 24,  25,  28)
C_H1_DARK            = (235, 235, 238)
C_H2_DARK            = (225, 225, 228)
C_TEXT_DARK          = (215, 215, 218)
C_MUTED_DARK         = (150, 150, 158)
C_CODE_BG_DARK       = ( 40,  41,  46)
C_CODE_FG_DARK       = (225, 225, 228)
C_RULE_DARK          = ( 75,  76,  82)
C_LINK_DARK          = (120, 170, 255)
C_TABLE_HEAD_BG_DARK = ( 55,  56,  62)
C_ROW_BASE_DARK      = C_PAGE_BG_DARK
C_ROW_ALT_DARK       = ( 34,  35,  39)

# Syntax-highlight palettes — LIGHT chosen against the light C_CODE_BG
# background, DARK against C_CODE_BG_DARK; neither is tied to a specific
# Pygments theme. Keyed by Pygments token type; a token not listed is
# resolved by walking up `.parent` until one matches, terminating at the
# bare `Token` root (see `_code_token_color`). Built lazily (and cached per
# theme) once `pygments.token.Token` is known importable.
_CODE_STYLES_CACHE = {}

# ── Layout ────────────────────────────────────────────────────────────────────

MARGIN    = 18
PAGE_W    = 210
CONTENT_W = PAGE_W - 2 * MARGIN

def _find_font_dir():
    """First directory that contains DejaVuSans.ttf (Linux, Windows, macOS)."""
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("C:/Windows/Fonts"),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path.home() / ".fonts",
        Path.home() / "Library" / "Fonts",
    ]
    for d in candidates:
        if (d / "DejaVuSans.ttf").exists():
            return d
    return candidates[0]


FONT_DIR = _find_font_dir()
KEEP_FIRST_H1 = False   # set in main(): frontmatter/CLI title => keep first `#`
BASE_DIR = Path(".")    # set in main(): images resolve relative to the .md file
IMG_RE = re.compile(r"^!\[(.*?)\]\((.+?)\)$")
QUOTE_RE = re.compile(r"^>\s?(.*)$")
CAPTION_RE = re.compile(r"^\*(?!\*)(.+?)\*$")        # a whole line in *italics*
EXTRA_BLOCK_RE = re.compile(r"^(>|\$\$)")            # blockquote / display math start
INLINE_MATH_RE = re.compile(r"(?<![\\$])\$(?=\S)([^$\n]*?\S)\$(?![\d$])")
MATH_MODE = "auto"      # set in main(): auto | latex | mathtext | unicode
MATH_STATS = {}         # backend name -> number of display formulas rendered with it
BR_RE = re.compile(r"^<br\s*/?>$", re.IGNORECASE)
PAGEBREAK_RE = re.compile(r"^<!--\s*pagebreak\s*-->$", re.IGNORECASE)


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


# ── Math ──────────────────────────────────────────────────────────────────────
#
# Inline `$...$` is always turned into Unicode text (fpdf2 cannot place an
# image inside a wrapped text line). Display `$$...$$` becomes a centered image
# from the first backend that works: real LaTeX (pdflatex/xelatex/tectonic or
# latex+dvipng on PATH) -> matplotlib mathtext -> Unicode text.

_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "varrho": "ϱ",
    "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ",
    "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
_SYMBOLS = {
    **_GREEK, "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠", "approx": "≈",
    "sim": "∼", "propto": "∝", "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓",
    "to": "→", "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒", "leftrightarrow": "↔",
    "infty": "∞", "partial": "∂", "nabla": "∇", "sum": "∑", "prod": "∏", "int": "∫",
    "in": "∈", "ll": "≪", "gg": "≫", "circ": "°", "degree": "°", "ldots": "…", "dots": "…",
    "cdots": "⋯", "ast": "∗", "equiv": "≡", "cap": "∩", "cup": "∪", "forall": "∀", "exists": "∃",
    "log": "log", "ln": "ln", "exp": "exp", "sin": "sin", "cos": "cos", "tan": "tan", "min": "min",
    "max": "max", "lim": "lim",
}
_SPACES = {",": "\u2009", ";": " ", ":": " ", " ": " ", "quad": "  ", "qquad": "    ", "!": ""}
_TEXT_CMDS = {"text", "mathrm", "mathbf", "mathit", "operatorname", "textbf", "textit", "mathbb",
              "boldsymbol", "mathcal"}
_DROP_CMDS = {"left", "right", "big", "Big", "bigg", "Bigg", "displaystyle", "limits", "nolimits"}
_ACCENTS = {"dot": "\u0307", "ddot": "\u0308", "hat": "\u0302", "bar": "\u0304", "vec": "\u20d7",
            "tilde": "\u0303", "overline": "\u0304"}
_SUB = str.maketrans("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")
_SUP = str.maketrans("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")


def _tex_arg(s, i):
    """One TeX argument starting at s[i]: a {group}, a \\command, or one character."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        depth, j = 0, i
        while j < len(s):
            depth += (s[j] == "{") - (s[j] == "}")
            j += 1
            if depth == 0:
                break
        return s[i + 1:j - 1], j
    if s[i] == "\\":
        m = re.match(r"\\([A-Za-z]+|.)", s[i:])
        return m.group(0), i + len(m.group(0))
    return s[i], i + 1


def _tex_paren(t):
    return t if re.fullmatch(r"[\w.°]+", t) else f"({t})"


def _tex_script(t, op):
    table = _SUB if op == "_" else _SUP
    if t and all(ord(ch) in table for ch in t):
        return t.translate(table)
    return op + (t if op == "_" and re.fullmatch(r"[\w.]+", t) else f"({t})")


def tex_to_unicode(tex):
    """Best-effort LaTeX -> plain Unicode text (no TeX needed). Handles greek,
    common operators, \\frac, \\sqrt, \\text{}, accents, sub/superscripts."""
    s, i, out = tex.strip(), 0, []
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            cmd, i = m.group(1), i + len(m.group(0))
            if cmd in ("frac", "dfrac", "tfrac"):
                a, i = _tex_arg(s, i)
                b, i = _tex_arg(s, i)
                out.append(_tex_paren(tex_to_unicode(a)) + "/" + _tex_paren(tex_to_unicode(b)))
            elif cmd == "sqrt":
                a, i = _tex_arg(s, i)
                out.append("√" + _tex_paren(tex_to_unicode(a)))
            elif cmd in _TEXT_CMDS:
                a, i = _tex_arg(s, i)
                out.append(tex_to_unicode(a))
            elif cmd in _ACCENTS:
                a, i = _tex_arg(s, i)
                base = tex_to_unicode(a)
                out.append(base + _ACCENTS[cmd] if len(base) == 1 else f"{base}{_ACCENTS[cmd]}")
            elif cmd in _DROP_CMDS:
                pass
            elif cmd in _SYMBOLS:
                out.append(_SYMBOLS[cmd])
                if cmd in _GREEK and re.match(r" +[A-Za-z]", s[i:]):   # `\Delta t` -> Δt
                    i += len(s[i:]) - len(s[i:].lstrip(" "))
            elif cmd in _SPACES:
                out.append(_SPACES[cmd])
            elif len(cmd) == 1:
                out.append(cmd)            # \% \{ \} \$ \_ \&
            else:
                out.append(cmd)            # unknown command: show its name
        elif c in "^_":
            a, i = _tex_arg(s, i + 1)
            out.append(_tex_script(tex_to_unicode(a), c))
        elif c in "{}":
            i += 1
        else:
            out.append(c)
            i += 1
    return re.sub(r" {2,}", " ", "".join(out)).strip()


def _tex_for_mathtext(tex):
    """The LaTeX subset matplotlib mathtext understands."""
    tex = re.sub(r"\\(dfrac|tfrac)", r"\\frac", tex)
    tex = re.sub(r"\\(text|textbf|textit|operatorname|mathbf)\{([^{}]*)\}",
                 lambda m: "\\mathrm{" + m.group(2).replace(" ", "\\ ") + "}", tex)
    tex = re.sub(r"\\(displaystyle|limits|nolimits|!)", "", tex)
    tex = tex.replace("\\;", "\\ ").replace("\\:", "\\ ")
    return tex


def _mathtext_png(tex, color):
    from matplotlib.figure import Figure
    fig = Figure(figsize=(0.1, 0.1))
    fig.text(0, 0, "$" + _tex_for_mathtext(tex) + "$", fontsize=12,
             color=tuple(v / 255 for v in color))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, transparent=True,
                bbox_inches="tight", pad_inches=0.04)
    return buf.getvalue()


def _latex_tools():
    """(engine, converter) of a usable TeX install on PATH, or None."""
    which = shutil.which
    engine = next((e for e in ("pdflatex", "xelatex", "tectonic") if which(e)), None)
    if engine:
        try:
            import pymupdf  # noqa: F401
            have_mupdf = True
        except ImportError:
            have_mupdf = False
        conv = ("pdftocairo" if which("pdftocairo") else "pymupdf" if have_mupdf
                else "dvisvgm" if which("dvisvgm") else None)
        return (engine, conv) if conv else None
    if which("latex") and which("dvipng"):
        return ("latex", "dvipng")
    return None


def _latex_png(tex, color):
    tools = _latex_tools()
    if not tools:
        return None
    engine, conv = tools
    tmp = Path(tempfile.mkdtemp(prefix="r2p-tex-"))
    try:
        r, g, b = color
        (tmp / "m.tex").write_text(
            "\\documentclass[12pt,border=2pt]{standalone}\n\\usepackage{amsmath,amssymb,xcolor}\n"
            f"\\begin{{document}}\\color[RGB]{{{r},{g},{b}}}\\(\\displaystyle {tex}\\)\\end{{document}}\n",
            encoding="utf-8")
        if engine == "tectonic":
            cmd = [engine, "m.tex"]
        else:
            cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", "m.tex"]
        subprocess.run(cmd, cwd=tmp, capture_output=True, timeout=120, check=True)
        if conv == "dvipng":
            subprocess.run(["dvipng", "-D", "300", "-T", "tight", "-bg", "Transparent",
                            "-o", "m.png", "m.dvi"], cwd=tmp, capture_output=True, timeout=60, check=True)
            return (tmp / "m.png").read_bytes()
        if conv == "pdftocairo":
            subprocess.run(["pdftocairo", "-png", "-r", "300", "-transp", "-singlefile", "m.pdf", "m"],
                           cwd=tmp, capture_output=True, timeout=60, check=True)
            return (tmp / "m.png").read_bytes()
        if conv == "pymupdf":
            import pymupdf
            return pymupdf.open(str(tmp / "m.pdf"))[0].get_pixmap(dpi=300, alpha=True).tobytes("png")
        subprocess.run(["dvisvgm", "--pdf", "-o", "m.svg", "m.pdf"], cwd=tmp,
                       capture_output=True, timeout=60, check=True)
        return svg_to_png(tmp / "m.svg", scale=300 / 96)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_MATH_CACHE = {}


def math_png(tex, color):
    """PNG bytes (300 dpi, transparent) of a display formula from the first
    working backend, or None -> caller falls back to Unicode text."""
    key = (tex, color, MATH_MODE)
    if key in _MATH_CACHE:
        return _MATH_CACHE[key]
    order = {"auto": ["latex", "mathtext"], "latex": ["latex", "mathtext"],
             "mathtext": ["mathtext"], "unicode": []}[MATH_MODE]
    png = None
    for name in order:
        try:
            png = {"latex": _latex_png, "mathtext": _mathtext_png}[name](tex, color)
        except Exception:
            png = None
        if png:
            MATH_STATS[name] = MATH_STATS.get(name, 0) + 1
            break
    if not png:
        MATH_STATS["unicode"] = MATH_STATS.get("unicode", 0) + 1
    _MATH_CACHE[key] = png
    return png


# ── SVG images ────────────────────────────────────────────────────────────────
#
# fpdf2 draws SVG natively (vector) but ignores <marker> (arrowheads), filters
# and masks, uses a core font for text (no Greek) and mis-colours unfilled text.
# So every SVG is rasterised at 2.5x by a headless Chrome/Edge (or cairosvg)
# and embedded as PNG; native vector drawing is only the last-resort fallback.

_SVG_NEEDS_RASTER = re.compile(r"<(marker|filter|mask|pattern|foreignObject)\b|marker-(start|mid|end)=")


def _svg_native_ok(svg_text):
    """fpdf2's own SVG drawing is vector and sharp, but it skips markers/filters
    and draws text in a core font (no Greek, no accents beyond Latin-1)."""
    return not _SVG_NEEDS_RASTER.search(svg_text) and all(ord(c) < 256 for c in svg_text)


def find_browser():
    cands = [os.environ.get("REPORT_PDF_BROWSER", "")] + [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    cands += [shutil.which(n) or "" for n in
              ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge")]
    return next((c for c in cands if c and os.path.exists(c)), None)


def svg_size(svg_text):
    """(width, height) in px from the root tag's width/height or viewBox."""
    root = re.search(r"<svg\b[^>]*>", svg_text, re.S).group(0)

    def dim(name):
        m = re.search(rf'\s{name}="([\d.]+)\s*(px|pt|mm|cm|in)?"', root)
        if not m:
            return None
        return float(m.group(1)) * {"pt": 4 / 3, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96}.get(m.group(2), 1)

    w, h = dim("width"), dim("height")
    vb = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', root)
    if (w is None or h is None) and vb:
        w, h = float(vb.group(1)), float(vb.group(2))
    return (w or 300.0), (h or 150.0)


_SVG_CACHE = {}


def svg_to_png(path, scale=2.5):
    """Rasterise an SVG with headless Chrome/Edge, else cairosvg; None if neither."""
    path = Path(path)
    key = (str(path), path.stat().st_mtime, scale)
    if key in _SVG_CACHE:
        return _SVG_CACHE[key]
    png = None
    svg = path.read_text(encoding="utf-8")
    w, h = svg_size(svg)
    browser = find_browser()
    if browser:
        tmp = Path(tempfile.mkdtemp(prefix="r2p-svg-"))
        try:
            root = re.search(r"<svg\b[^>]*>", svg, re.S).group(0)
            fixed = re.sub(r'\s(width|height)="[^"]*"', "", root)
            fixed = fixed.replace("<svg", f'<svg width="{w:g}" height="{h:g}"', 1)
            (tmp / "i.svg").write_text(svg.replace(root, fixed, 1), encoding="utf-8")
            subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars",
                            f"--force-device-scale-factor={scale}",
                            f"--window-size={int(w) + 40},{int(h) + 200}",
                            f"--screenshot={tmp / 'o.png'}", (tmp / "i.svg").as_uri()],
                           capture_output=True, timeout=90)
            if (tmp / "o.png").exists():
                from PIL import Image
                with Image.open(tmp / "o.png") as im:
                    buf = io.BytesIO()
                    im.convert("RGB").crop((0, 0, round(w * scale), round(h * scale))).save(buf, "PNG")
                    png = buf.getvalue()
        except Exception as exc:
            print(f"  warning: browser rasterising failed for {path.name}: {exc}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if png is None:
        try:
            import cairosvg
            png = cairosvg.svg2png(url=str(path), scale=scale)
        except Exception:
            png = None
    _SVG_CACHE[key] = png
    return png


def prepare_markdown_text(text):
    """Normalize inline markdown so fpdf2's `markdown=True` renderer can
    handle it directly: keep **bold** and [text](url) as-is (fpdf2 renders
    both natively, the latter as a real clickable link), fold single-marker
    italics into fpdf2's `__italic__` form, and strip inline `code`
    backticks to plain text (fpdf2 has no inline-monospace support).
    Inline `$math$` is converted to Unicode first (before `_`/`*` handling)."""
    text = INLINE_MATH_RE.sub(lambda m: tex_to_unicode(m.group(1)), text)
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


def _resolve_version(cli_value, frontmatter):
    """No version given -> today's date. `version: none` (or empty) hides it."""
    v = cli_value if cli_value is not None else frontmatter.get("version")
    if v is None:
        return date.today().isoformat()
    if str(v).strip().lower() in ("", "none", "false", "off", "no"):
        return ""
    return v


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

        if PAGEBREAK_RE.match(stripped):
            blocks.append({"type": "pagebreak"})
            i += 1
            continue

        if BR_RE.match(stripped):
            blocks.append({"type": "br"})
            i += 1
            continue

        # Display math: `$$ ... $$` on one line, or spread over several
        if stripped.startswith("$$"):
            parts, rest = [], stripped[2:]
            i += 1
            if "$$" in rest:
                parts.append(rest.split("$$")[0])
            else:
                parts.append(rest)
                while i < n and "$$" not in lines[i]:
                    parts.append(lines[i].strip())
                    i += 1
                if i < n:
                    parts.append(lines[i].split("$$")[0])
                    i += 1
            blocks.append({"type": "math", "tex": " ".join(parts).strip()})
            continue

        # Blockquote -> one shaded box; blank `>` lines split paragraphs
        if QUOTE_RE.match(stripped):
            paras, cur_para = [], []
            while i < n and QUOTE_RE.match(lines[i].strip()):
                content = QUOTE_RE.match(lines[i].strip()).group(1).strip()
                if content:
                    cur_para.append(content)
                elif cur_para:
                    paras.append(" ".join(cur_para))
                    cur_para = []
                i += 1
            if cur_para:
                paras.append(" ".join(cur_para))
            if paras:
                blocks.append({"type": "quote",
                               "paras": [prepare_markdown_text(q) for q in paras]})
            continue

        # Indented block after a blank line (4 spaces / tab) = code, as in
        # standard Markdown (notebook exports print cell output this way)
        if (line.startswith("    ") or line.startswith("\t")) \
                and (i == 0 or not lines[i - 1].strip()) \
                and not (blocks and blocks[-1]["type"] in ("bullets", "numbered")):
            code_lines = []
            while i < n and (lines[i].startswith("    ") or lines[i].startswith("\t")
                             or not lines[i].strip()):
                code_lines.append(lines[i][4:] if lines[i].startswith("    ")
                                  else lines[i].lstrip("\t"))
                i += 1
            while code_lines and not code_lines[-1].strip():
                code_lines.pop()
            if code_lines:
                blocks.append({"type": "code", "lang": "", "text": "\n".join(code_lines)})
            continue

        img_m = IMG_RE.match(stripped)
        if img_m:
            blocks.append({"type": "image", "alt": img_m.group(1),
                           "path": img_m.group(2)})
            i += 1
            # An italic line right after the image (blank lines allowed) is its caption
            j = i
            while j < n and not lines[j].strip():
                j += 1
            cap_m = CAPTION_RE.match(lines[j].strip()) if j < n else None
            if cap_m:
                blocks[-1]["caption"] = prepare_markdown_text(cap_m.group(1))
                i = j + 1
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
            if level == 1 and doc_title is None and not KEEP_FIRST_H1:
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
                    or TABLE_ROW_RE.match(cur) or HR_RE.match(cur) \
                    or EXTRA_BLOCK_RE.match(cur) or IMG_RE.match(cur):
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

def _code_styles(dark=False):
    """Build (lazily, once per theme, once Pygments is known importable)
    the token-type -> RGB color table used by `_code_token_color`."""
    if dark in _CODE_STYLES_CACHE:
        return _CODE_STYLES_CACHE[dark]

    from pygments.token import Token

    fg = C_CODE_FG_DARK if dark else C_CODE_FG
    styles = {
        Token:                    fg,               # fallback: plain code color
        Token.Punctuation:        fg,
    }
    styles.update({
        Token.Keyword:            (255, 121, 198) if dark else (170,  30, 130),
        Token.Name.Builtin:       (102, 217, 239) if dark else (  0, 110, 110),
        Token.Name.Builtin.Pseudo:(102, 217, 239) if dark else (  0, 110, 110),
        Token.Name.Function:      (130, 170, 255) if dark else (  0,  90, 170),
        Token.Name.Class:         (130, 170, 255) if dark else (  0,  90, 170),
        Token.Name.Decorator:     (255, 184, 108) if dark else (150, 100,   0),
        Token.Name.Tag:           (255, 121, 198) if dark else (170,  30, 130),
        Token.Name.Attribute:     (130, 170, 255) if dark else (  0,  90, 170),
        Token.Literal.String:     (166, 226, 130) if dark else ( 20, 130,  20),
        Token.Literal.Number:     (255, 184, 108) if dark else (180,  90,   0),
        Token.Comment:            (130, 132, 142) if dark else (130, 130, 130),
        Token.Operator:           (255, 121, 198) if dark else (120,  40,  40),
        Token.Error:              (255,  85,  85) if dark else (200,   0,   0),
    })

    _CODE_STYLES_CACHE[dark] = styles

    return styles


def _code_token_color(ttype, dark=False):
    """Walk a Pygments token type up its `.parent` chain until one is found
    in the style table — e.g. Token.Keyword.Declaration has no entry of its
    own, but its parent Token.Keyword does. The bare `Token` root is always
    in the table, so this always terminates."""
    styles = _code_styles(dark)
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


def _tokenize_lines(lexer, text, dark=False):
    """Tokenize `text` with `lexer` and regroup the token stream by source
    line, returning a list (one entry per line in `text.split("\\n")`) of
    `[(color, token_text), ...]` segments. A single token can itself span
    multiple lines (block comments, template literals) and is split at each
    embedded newline. Returns None on any mismatch or failure — callers
    should treat that as "fall back to flat rendering", not an error."""
    try:
        lines = [[]]
        for ttype, value in lexer.get_tokens(text):
            color = _code_token_color(ttype, dark)
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


def make_pdf_class(accent, dark=False):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    # Every render method below closes over these *lowercase* names instead
    # of the module-level UPPERCASE constants — same mechanism already used
    # for `accent`. Deliberately lowercase so there's no ambiguity with the
    # module globals of the same name (Python would otherwise raise
    # UnboundLocalError on any attempt to read-then-shadow a same-named
    # global inside this function).
    if dark:
        c_page_bg       = C_PAGE_BG_DARK
        c_h1            = C_H1_DARK
        c_h2            = C_H2_DARK
        c_text          = C_TEXT_DARK
        c_muted         = C_MUTED_DARK
        c_code_bg       = C_CODE_BG_DARK
        c_code_fg       = C_CODE_FG_DARK
        c_rule          = C_RULE_DARK
        c_link          = C_LINK_DARK
        c_table_head_bg = C_TABLE_HEAD_BG_DARK
        c_row_base      = C_ROW_BASE_DARK
        c_row_alt       = C_ROW_ALT_DARK
        c_quote_bg, c_quote_bd = (34, 40, 52), (96, 130, 190)
    else:
        c_page_bg       = None  # no fill needed — page defaults to white
        c_h1            = C_H1
        c_h2            = C_H2
        c_text          = C_TEXT
        c_muted         = C_MUTED
        c_code_bg       = C_CODE_BG
        c_code_fg       = C_CODE_FG
        c_rule          = C_RULE
        c_link          = C_LINK
        c_table_head_bg = C_TABLE_HEAD_BG
        c_row_base      = C_ROW_BASE
        c_row_alt       = C_ROW_ALT
        c_quote_bg, c_quote_bd = (238, 243, 250), (74, 111, 165)

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
            self.MARKDOWN_LINK_COLOR = c_link

        # ── Header / Footer ───────────────────────────────────────────────

        def multi_cell(self, *args, **kwargs):
            # fpdf2 justifies multi_cell text by default, which stretches
            # word gaps badly on short/wrapped lines (headings with a long
            # word, lines with links). Left-align unless `justify: true`.
            kwargs.setdefault("align", "J" if self.meta.get("justify") else "L")
            return super().multi_cell(*args, **kwargs)

        def header(self):
            # fpdf2 has no "page background color" setting — the dark theme
            # fakes one by filling the whole page first, before anything
            # else (including the title page's own drawing) gets a chance
            # to draw on top of it. This runs even on page 1 (the title
            # page), which is why it comes before the `self.page <= 1`
            # early-return just below, not after it.
            if c_page_bg is not None:
                self.set_fill_color(*c_page_bg)
                self.rect(0, 0, PAGE_W, self.h, style="F")

            if self.page <= 1:
                return
            self._content_top = self.get_y()
            if not self.meta.get("running_header", True):
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
            self.set_text_color(*c_muted)
            self.cell(0, 6, title, new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(1)
            self._content_top = self.get_y()

        def _at_top(self):
            """True while nothing has been drawn on the current page yet."""
            return self.get_y() <= getattr(self, "_content_top", MARGIN) + 0.5

        def footer(self):
            if self.page <= 1:
                return
            self.set_y(-14)
            self.set_draw_color(*c_rule)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(1)
            self.set_font("DejaVu", size=8)
            self.set_text_color(*c_muted)
            self.cell(0, 6, f"Page {self.page - 1}", align="R",
                      new_x=XPos.RIGHT, new_y=YPos.TOP)

        # ── Title page ────────────────────────────────────────────────────

        def title_page(self, logos=None):
            """`logos`: list of (png_buf, w_px, h_px), drawn side by side."""
            logos = logos or []
            self.add_page()

            self.set_fill_color(*accent)
            self.rect(0, 0, PAGE_W, 10, style="F")

            cover_left = self.meta.get("cover") == "left"
            align = "L" if cover_left else "C"
            text_x = MARGIN

            title = self.meta["title"]
            title_size = 16
            for size in [24, 22, 20, 18, 16]:
                self.set_font("DejaVu", style="B", size=size)
                title_size = size
                if self.get_string_width(title) <= CONTENT_W - 2:
                    break

            def _n_lines(text, size, bold=False):
                self.set_font("DejaVu", style="B" if bold else "", size=size)
                return len(self.multi_cell(
                    CONTENT_W, 1, text, dry_run=True, output="LINES",
                    align=align))

            subtitle = self.meta.get("subtitle") or ""
            author = self.meta.get("author") or ""
            version = self.meta.get("version") or ""

            title_h = _n_lines(title, title_size, True) * 10 + 2
            sub_h = (_n_lines(subtitle, 14) * 8 + 1) if subtitle else 0
            auth_h = (_n_lines(author, 12) * 7 + 3) if author else 0
            ver_h = 6 if version else 0
            block_h = title_h + sub_h + auth_h + ver_h

            # The whole block (logo included) is centered vertically between the
            # top bar and the copyright line. "center" also centers it
            # horizontally; "left" left-justifies it (logo at the left too).
            top_limit, bottom_limit = 10, self.h - 22
            # Logos share one row: each scaled to the same height (capped in
            # width), separated by a gap; the row is centered or left-aligned
            # like the text below it.
            logo_h_mm, logo_max_w, logo_gap = 32, 55, 14
            sized = []
            for buf, w_px, h_px in logos:
                w_mm = logo_h_mm * w_px / h_px
                h_mm = logo_h_mm
                if w_mm > logo_max_w:
                    w_mm, h_mm = logo_max_w, logo_max_w * h_px / w_px
                sized.append((buf, w_mm, h_mm))
            row_h = max((h for _, _, h in sized), default=0)
            row_w = sum(w for _, w, _ in sized) + logo_gap * max(0, len(sized) - 1)
            total_h = block_h + (row_h + 10 if sized else 0)
            y = top_limit + max(8, (bottom_limit - top_limit - total_h) / 2)
            if sized:
                x = MARGIN if cover_left else (PAGE_W - row_w) / 2
                for buf, w_mm, h_mm in sized:
                    self.image(buf, x=x, y=y + (row_h - h_mm) / 2,
                               w=w_mm, h=h_mm)
                    x += w_mm + logo_gap
                y += row_h + 10

            self.set_xy(text_x, y)
            self.set_font("DejaVu", style="B", size=title_size)
            self.set_text_color(*c_h1)
            self.multi_cell(CONTENT_W, 10, title, align=align,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(2)

            if subtitle:
                # multi_cell wraps within the content width; a long centered
                # cell() would run off both page edges.
                self.set_font("DejaVu", size=14)
                self.set_text_color(*c_muted)
                self.multi_cell(CONTENT_W, 8, subtitle, align=align,
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
                self.ln(1)

            if author:
                self.set_font("DejaVu", size=12)
                self.set_text_color(*c_text)
                self.ln(3)
                self.multi_cell(CONTENT_W, 7, author, align=align,
                                new_x=XPos.LEFT, new_y=YPos.NEXT)

            if version:
                self.set_font("DejaVu", size=10)
                self.set_text_color(*c_muted)
                self.multi_cell(CONTENT_W, 6, f"Version {version}",
                                align=align, new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.ln(10)
            self._toc_y = self.get_y()

            # Copyright pinned to page bottom — disable auto-page-break so
            # set_y(-18) doesn't trigger a phantom extra page
            self.set_auto_page_break(False)
            self.set_y(-18)
            self.set_draw_color(*c_rule)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(2)
            self.set_font("DejaVu", size=8)
            self.set_text_color(*c_muted)
            if self.meta.get("vendor"):
                self.multi_cell(CONTENT_W, 5, f"© {self.meta['vendor']}",
                                align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.set_auto_page_break(True, margin=22)

        # ── TOC back-fill ─────────────────────────────────────────────────

        def write_toc(self):
            """Write the Table of Contents onto its own page (page 2) after
            all content has rendered — this is the only way to know final page numbers
            with fpdf2's single forward pass."""
            if self._toc_y is None or not self._toc_entries:
                return

            last_page = self.page
            self.page  = 2
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
            self.set_text_color(*c_h2)
            self.cell(0, 7, "Contents", new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.set_draw_color(*c_rule)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(4)

            # title_page() reserves the last ~18mm of page 1 for a fixed
            # copyright line — TOC rows must stop well clear of it, not just
            # clear of the normal auto-page-break margin.
            toc_bottom_limit = self.h - 22
            row_h = 6.5 if len(self._toc_entries) <= 22 else 6.0
            # Level-2 (subheading) entries indent under their nearest
            # preceding level-1 (major heading) entry and use a slightly
            # smaller base font, so the TOC visually nests them instead of
            # listing every heading tier as flush-left equals.
            indent_step = 7

            for level, title, abs_page in self._toc_entries:
                display_page = abs_page - 1
                y_row = self.get_y()
                if y_row + row_h > toc_bottom_limit:
                    break  # ran out of room on page 1 — clip, don't overflow

                indent = indent_step if level >= 2 else 0
                base_size = 9 if level >= 2 else 10
                x_start = MARGIN + indent

                # Clicking anywhere on the row (title, dot leader, or page
                # number) jumps straight to the page that heading lives on.
                link_id = self.add_link(page=abs_page)

                num_str = str(display_page)
                self.set_font("DejaVu", size=base_size)
                num_w = self.get_string_width(num_str) + 2
                title_max_w = CONTENT_W - indent - num_w - 6

                # Long entry titles shrink to fit their single-line slot
                # rather than running into the dot-leader/page-number area.
                size = base_size
                self.set_font("DejaVu", size=size)
                while (self.get_string_width(title) > title_max_w
                        and size > 6.5):
                    size -= 0.5
                    self.set_font("DejaVu", size=size)

                self.set_text_color(*(c_text if level == 1 else c_muted))
                self.set_xy(x_start, y_row)
                self.cell(title_max_w, row_h, title, link=link_id,
                          new_x=XPos.LEFT, new_y=YPos.TOP)

                title_x_end = x_start + self.get_string_width(title) + 2
                dot_gap = (PAGE_W - MARGIN - num_w) - title_x_end
                if dot_gap > 3:
                    self.set_font("DejaVu", size=base_size)
                    dot_w    = self.get_string_width(".")
                    n_dots   = max(0, int(dot_gap / (dot_w + 0.3)) - 1)
                    dots_str = " " + "." * n_dots
                    self.set_xy(title_x_end, y_row)
                    self.set_text_color(*c_muted)
                    self.cell(dot_gap, row_h, dots_str, link=link_id,
                              new_x=XPos.LEFT, new_y=YPos.TOP)

                self.set_font("DejaVu", size=base_size)
                self.set_xy(PAGE_W - MARGIN - num_w, y_row)
                self.set_text_color(*c_muted)
                self.cell(num_w, row_h, num_str, align="R", link=link_id,
                          new_x=XPos.LEFT, new_y=YPos.NEXT)

            self.set_auto_page_break(True, margin=22)
            self.page = last_page

        # ── Helpers ───────────────────────────────────────────────────────

        def _text(self, txt, size=10, bold=False, color=c_text, line_h=5.5):
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
            if not self._at_top():
                self.add_page()

            self._toc_entries.append((1, text, self.page))

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
            self.set_text_color(*c_h1)
            self.multi_cell(text_w, line_h, text, markdown=True,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(3)

        def render_h2(self, text):
            if not self._at_top():
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

            self._toc_entries.append((2, text, self.page))

            self.set_text_color(*accent)
            self.multi_cell(CONTENT_W, line_h, text, markdown=True,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            rule_w = min(CONTENT_W, self.get_string_width(text) + 4)
            self.set_draw_color(*accent)
            self.line(MARGIN, self.get_y(), MARGIN + rule_w, self.get_y())
            self.ln(3)

        def render_h3(self, text):
            if not self._at_top():
                self.ln(4)
            if self.get_y() > self.h - self.b_margin - 30:
                self.add_page()   # don't strand a heading at the bottom of a page
            self.set_font("DejaVu", style="B", size=12)
            self.set_text_color(*c_h2)
            self.multi_cell(CONTENT_W, 7, text, markdown=True,
                            new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.set_draw_color(*c_rule)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(3)

        def render_p(self, text):
            self._text(text, size=10, color=c_text, line_h=5.5)
            self.ln(1)

        def render_bullets(self, items):
            self.set_font("DejaVu", size=10)
            self.set_text_color(*c_text)
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
            self.set_text_color(*c_text)
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
                self.set_text_color(*c_muted)
                self.cell(0, 5, lang, new_x=XPos.LEFT, new_y=YPos.NEXT)

            lines    = text.split("\n")
            pad      = 3
            avail_w  = CONTENT_W - pad * 2
            base_size = 8.5

            # Real tokenization via Pygments, keyed off the fence's language
            # tag — None (no tag, unrecognized language, or Pygments itself
            # unavailable) means "render in flat color", never an error.
            lexer = _get_code_lexer(lang)
            tokenized = _tokenize_lines(lexer, text, dark) if lexer else None

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

            self.set_fill_color(*c_code_bg)
            self.set_draw_color(*c_rule)
            x, y = MARGIN, self.get_y()
            self.rect(x, y, CONTENT_W, block_h, style="FD")
            self.set_xy(x + pad, y + pad)

            for i, line in enumerate(lines):
                row_y = y + pad + i * line_h
                self.set_xy(x + pad, row_y)
                segments = tokenized[i] if tokenized else [(c_code_fg, line)]
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
                self.set_fill_color(*c_table_head_bg)
                self.set_draw_color(*c_rule)
                self.rect(x0, y0, col_w[j], header_h, style="FD")
                self.set_xy(x0 + 1, y0 + 1)
                self.multi_cell(col_w[j] - 2, 5, h, markdown=True,
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
                x0 += col_w[j]
            self.set_y(y0 + header_h)

            self.set_font("DejaVu", size=9)
            self.set_text_color(*c_text)
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
                    bg = c_row_alt if fill else c_row_base
                    self.set_fill_color(*bg)
                    self.set_draw_color(*c_rule)
                    self.rect(x0, y0, col_w[j], row_h, style="FD")
                    self.set_xy(x0 + 2, y0 + 2)
                    self.multi_cell(col_w[j] - 4, 5, cells[j], markdown=True,
                                    new_x=XPos.LEFT, new_y=YPos.NEXT)
                    x0 += col_w[j]
                self.set_y(y0 + row_h)
                fill = not fill
            self.ln(3)

        def render_image(self, path, alt="", caption=None):
            from PIL import Image as _I
            img_path = Path(path)
            if not img_path.is_absolute():
                img_path = BASE_DIR / img_path
            if not img_path.exists():
                print(f"  warning: image not found: {img_path}")
                return
            source = str(img_path)
            if img_path.suffix.lower() == ".svg":
                svg_text = img_path.read_text(encoding="utf-8")
                w, h = svg_size(svg_text)
                # Raster first (exact text, markers, fonts); fpdf2's native vector
                # drawing is the fallback when no Chrome/Edge/cairosvg exists.
                png = svg_to_png(img_path)
                if png:
                    source = io.BytesIO(png)
                elif not _svg_native_ok(svg_text):
                    print(f"  warning: {img_path.name} needs markers/filters/non-Latin text "
                          "and no Chrome/Edge/cairosvg was found: drawn natively, may be incomplete")
            else:
                with _I.open(img_path) as im:
                    w, h = im.size
            # A figure (image + caption) and any SVG may use the full text
            # width; a bare raster image under 900 px keeps the original 130 mm cap.
            wide = bool(caption) or img_path.suffix.lower() == ".svg" or w >= 900
            max_w = CONTENT_W if wide else min(CONTENT_W * 0.8, 130)
            max_h = 120 if wide else 105
            scale = min(max_w / w, max_h / h)
            dw, dh = w * scale, h * scale
            cap_h = 0
            if caption:
                self.set_font("DejaVu", style="I", size=8.5)
                cap_h = len(self.multi_cell(CONTENT_W, 4.2, caption, markdown=True,
                                            dry_run=True, output="LINES", align="C")) * 4.2 + 2
            if self.get_y() + dh + cap_h + 6 > self.h - self.b_margin:
                # Shrink to the space left (down to 70 %) rather than leave a gap; else new page.
                room = self.h - self.b_margin - self.get_y() - cap_h - 6
                if room >= max(0.7 * dh, 50):
                    dw, dh = dw * room / dh, room
                else:
                    self.add_page()
            x = MARGIN + (CONTENT_W - dw) / 2
            y = self.get_y() + 1
            try:
                self.image(source, x=x, y=y, w=dw, h=dh)
            except Exception as exc:       # native SVG drawing can fail on unusual SVGs
                print(f"  warning: could not draw {img_path.name}: {exc}")
                return
            self.set_draw_color(*c_rule)
            self.rect(x, y, dw, dh)
            self.set_y(y + dh + 2)
            self.set_x(MARGIN)
            if caption:
                self.set_font("DejaVu", style="I", size=8.5)
                self.set_text_color(*c_muted)
                self.multi_cell(CONTENT_W, 4.2, caption, markdown=True, align="C",
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.ln(2)

        def render_quote(self, paras):
            """Definition box: one bordered, lightly shaded box per blockquote."""
            pad, line_h, gap = 3, 5.2, 1.5
            width = CONTENT_W - 2 * pad
            self.set_font("DejaVu", size=10)
            heights = [len(self.multi_cell(width, line_h, p, markdown=True,
                                           dry_run=True, output="LINES")) * line_h
                       for p in paras]
            total = sum(heights) + gap * (len(paras) - 1) + 2 * pad
            self.ln(1)
            if self.get_y() + total > self.h - self.b_margin:
                self.add_page()
            x, y = MARGIN, self.get_y()
            self.set_fill_color(*c_quote_bg)
            self.set_draw_color(*c_quote_bd)
            self.set_line_width(0.35)
            self.rect(x, y, CONTENT_W, total, style="FD")
            self.set_line_width(0.2)
            self.set_text_color(*c_text)
            cy = y + pad
            for p, hgt in zip(paras, heights):
                self.set_xy(x + pad, cy)
                self.multi_cell(width, line_h, p, markdown=True,
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
                cy += hgt + gap
            self.set_xy(x, y + total)
            self.ln(3)

        def render_math(self, tex):
            """Display formula: centered image (LaTeX / mathtext) or Unicode text."""
            png = math_png(tex, c_text)
            if png:
                from PIL import Image as _I
                with _I.open(io.BytesIO(png)) as im:
                    w_px, h_px = im.size
                dw, dh = w_px * 25.4 / 300, h_px * 25.4 / 300
                if dw > CONTENT_W:
                    dw, dh = CONTENT_W, dh * CONTENT_W / dw
                self.ln(1)
                if self.get_y() + dh + 4 > self.h - self.b_margin:
                    self.add_page()
                self.image(io.BytesIO(png), x=MARGIN + (CONTENT_W - dw) / 2,
                           y=self.get_y(), w=dw, h=dh)
                self.set_y(self.get_y() + dh + 3)
                self.set_x(MARGIN)
            else:
                self.set_font("DejaVu", size=11)
                self.set_text_color(*c_text)
                self.ln(1)
                self.multi_cell(CONTENT_W, 6, tex_to_unicode(tex), align="C",
                                new_x=XPos.LEFT, new_y=YPos.NEXT)
                self.ln(2)

        def render_br(self):
            self.ln(5.5)

        def render_pagebreak(self):
            if not self._at_top():
                self.add_page()

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
                elif btype == "image":
                    self.render_image(block["path"], block.get("alt", ""),
                                      block.get("caption"))
                elif btype == "quote":
                    self.render_quote(block["paras"])
                elif btype == "math":
                    self.render_math(block["tex"])
                elif btype == "br":
                    self.render_br()
                elif btype == "pagebreak":
                    self.render_pagebreak()
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
    parser.add_argument("--logo", type=Path, action="append", default=None,
                        help="Optional logo image (PNG/WebP/JPEG); repeat "
                             "for several logos side by side")
    parser.add_argument("--title", default=None, help="Override title")
    parser.add_argument("--subtitle", default=None, help="Override subtitle")
    parser.add_argument("--version", default=None, help="Override version")
    parser.add_argument("--no-header", action="store_true", default=False,
                        help="Omit the running header (and its reserved space)")
    parser.add_argument("--author", default=None,
                        help="Author name(s) shown on the cover page")
    parser.add_argument("--cover", default=None, choices=["center", "left"],
                        help="Cover layout: title centered (default) or "
                             "left-justified (both vertically centered)")
    parser.add_argument("--vendor", default=None,
                        help="Copyright line vendor name")
    parser.add_argument("--accent", default=None,
                        help='Accent color as "R,G,B", e.g. "30,80,180"')
    parser.add_argument("--math", default=None,
                        choices=["auto", "latex", "mathtext", "unicode"],
                        help="Display-math backend: auto (LaTeX if installed, "
                             "else matplotlib mathtext, else Unicode text), "
                             "or force one (also frontmatter `math:`)")
    parser.add_argument("--dark", action="store_true", default=None,
                        help="Render using the dark color theme "
                             "(also settable via frontmatter `theme: dark`)")

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
    global KEEP_FIRST_H1, BASE_DIR, MATH_MODE
    KEEP_FIRST_H1 = bool(args.title or frontmatter.get("title"))
    BASE_DIR = input_path.resolve().parent
    MATH_MODE = (args.math or frontmatter.get("math") or "auto").strip().lower()
    if MATH_MODE not in ("auto", "latex", "mathtext", "unicode"):
        print(f"  warning: unknown math backend {MATH_MODE!r}, using auto")
        MATH_MODE = "auto"
    doc_title, blocks = parse_markdown(body_text)

    meta = {
        "title": (
            args.title or frontmatter.get("title") or doc_title
            or input_path.stem
        ),
        "subtitle": args.subtitle or frontmatter.get("subtitle", ""),
        "version": _resolve_version(args.version, frontmatter),
        "justify": str(frontmatter.get("justify", "false")).strip().lower()
            in ("true", "yes", "on", "1"),
        "running_header": not (
            args.no_header
            or str(frontmatter.get("header", "true")).strip().lower()
            in ("false", "no", "off", "0", "none")
        ),
        "vendor": args.vendor or frontmatter.get("vendor", ""),
        "author": args.author or frontmatter.get("author", ""),
        "cover": (args.cover or frontmatter.get("cover") or "center").strip().lower(),
    }

    accent = C_BRAND
    accent_spec = args.accent or frontmatter.get("accent")
    if accent_spec:
        try:
            accent = tuple(int(v.strip()) for v in accent_spec.split(","))
        except ValueError:
            print(f"  warning: invalid --accent {accent_spec!r}, using default")
            accent = C_BRAND

    # Logos: --logo (repeatable) wins; otherwise frontmatter `logo:` with
    # comma-separated paths (relative to the .md file).
    logo_paths = list(args.logo or [])
    if not logo_paths and frontmatter.get("logo"):
        for part in frontmatter["logo"].split(","):
            part = part.strip()
            if part:
                p = Path(part)
                logo_paths.append(p if p.is_absolute() else BASE_DIR / p)
    logos = []
    for lp in logo_paths:
        if not lp.exists():
            print(f"  warning: logo not found: {lp}")
            continue
        buf, w_px, h_px = load_logo_png(lp)
        if buf:
            logos.append((buf, w_px, h_px))

    # --dark wins if passed; otherwise fall back to frontmatter `theme:`.
    dark = args.dark if args.dark is not None else (
        frontmatter.get("theme", "").strip().lower() == "dark"
    )

    print("=" * 55)
    print("report-to-pdf — Markdown -> PDF")
    print(f"  Input   : {input_path}")
    print(f"  Output  : {output_path}")
    print(f"  Title   : {meta['title']}")
    print(f"  Theme   : {'dark' if dark else 'light'}")
    print(f"  Blocks  : {len(blocks)}")
    print("=" * 55)

    PDFClass = make_pdf_class(accent, dark)
    pdf = PDFClass(meta)
    pdf.title_page(logos)
    # The Table of Contents always gets its own page (page 2), back-filled
    # by write_toc() once real page numbers are known.
    pdf.add_page()
    pdf._toc_y = pdf.get_y()
    pdf.add_page()
    pdf.render(blocks)
    pdf.write_toc()
    pdf.output(str(output_path))

    print(f"\nCreated: {output_path}")
    print(f"  Size: {output_path.stat().st_size // 1024} KB")
    print(f"  Pages: {pdf.page}")
    if MATH_STATS:
        used = ", ".join(f"{k} x{v}" for k, v in MATH_STATS.items())
        print(f"  Math  : display formulas via {used}; inline math as Unicode text")


if __name__ == "__main__":
    main()
