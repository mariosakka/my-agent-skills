#!/usr/bin/env python3
"""Checks for the markdown features added for notebook companions:
inline/display math, blockquote boxes, figure captions, SVG images, indented
output blocks and the math backend chain. Run: python tests/run_checks.py"""
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r2p", HERE.parent / "scripts" / "build_report_pdf.py")
r2p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2p)

# -- LaTeX -> Unicode (inline math)
tu = r2p.tex_to_unicode
assert tu(r"t_a \le t_{mr}") == "tₐ ≤ tₘᵣ", tu(r"t_a \le t_{mr}")
assert tu(r"\varphi = p_v / p_{sat}(t)") == "φ = pᵥ / pₛₐₜ(t)"
assert tu(r"x^2 + \Delta t") == "x² + Δt"
assert tu(r"\frac{a+b}{2}") == "(a+b)/2"
assert tu(r"t_{dp}") == "t_dp"                      # no Unicode subscript for d: plain fallback
assert tu(r"\text{W/(m}^2\text{K)}") == "W/(m²K)"
assert r2p.prepare_markdown_text("rate $x_1$ and $5 or $6") == "rate x₁ and $5 or $6"   # prices are not math

# -- parser: box, caption, display math, indented output
text = (HERE / "fixture.md").read_text(encoding="utf-8").split("---", 2)[2]
_, blocks = r2p.parse_markdown(text)
kinds = [b["type"] for b in blocks]
assert kinds.count("quote") == 2 and kinds.count("math") == 1 and kinds.count("image") == 3, kinds
assert [b.get("caption", "")[:6] for b in blocks if b["type"] == "image"] == ["Figure"] * 3
assert blocks[kinds.index("math")]["tex"].startswith("k = ")
assert [b for b in blocks if b["type"] == "code" and not b["lang"]][0]["text"] == "PMV = 0.278\nPPD = 6.4 %"

# -- SVG routing: markers or non-Latin text need the raster path, plain ASCII SVG stays vector
svg = lambda n: (HERE / "figures" / n).read_text(encoding="utf-8")
assert not r2p._svg_native_ok(svg("arrow.svg")) and r2p._svg_native_ok(svg("plain.svg"))
assert r2p.svg_size(svg("arrow.svg")) == (400.0, 120.0)

# -- math backend chain degrades silently (no TeX needed: PATH lookups are mocked)
real_which = shutil.which
shutil.which = lambda name, *a, **k: None
assert r2p._latex_tools() is None
shutil.which = lambda name, *a, **k: "x" if name in ("pdflatex", "pdftocairo") else None
assert r2p._latex_tools() == ("pdflatex", "pdftocairo")
shutil.which = lambda name, *a, **k: "x" if name in ("latex", "dvipng") else None
assert r2p._latex_tools() == ("latex", "dvipng")
shutil.which = real_which
r2p.MATH_MODE = "auto"
shutil.which = lambda name, *a, **k: "no-such-binary" if name == "pdflatex" else None   # "installed" but broken
r2p._MATH_CACHE.clear(); r2p.MATH_STATS.clear()
png = r2p.math_png(r"x^2 + \frac{1}{2}", (0, 0, 0))
shutil.which = real_which
backend = "mathtext" if png else "unicode"
assert r2p.MATH_STATS == {backend: 1}, r2p.MATH_STATS
r2p.MATH_MODE = "unicode"
assert r2p.math_png("x", (0, 0, 0)) is None

# -- end to end: build the fixture and read the text back
out = Path(tempfile.mkdtemp()) / "fixture.pdf"
import subprocess
run = subprocess.run([sys.executable, str(HERE.parent / "scripts" / "build_report_pdf.py"),
                      str(HERE / "fixture.md"), "-o", str(out)], capture_output=True, text=True)
assert out.exists(), run.stdout + run.stderr
try:
    import pymupdf
    pages = "".join(p.get_text() for p in pymupdf.open(str(out)))
    for needle in ("tₐ ≤ tₘᵣ", "Operative temperature", "Second box", "Figure: a PNG chart", "PMV = 0.278"):
        assert needle in pages, needle
except ImportError:
    print("pymupdf missing: skipped reading the PDF text")
print("report-to-pdf checks: OK")
print(run.stdout.strip().splitlines()[-1])
