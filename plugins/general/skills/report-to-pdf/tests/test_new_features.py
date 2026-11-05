"""report-to-pdf features added for notebook companions: SVG figures, definition boxes, captions, indented output
blocks, display / inline math and the math backend chain, image sizing. Reads the PDFs back with PyMuPDF."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "build_report_pdf.py"
TESTS = Path(__file__).resolve().parent
FIXTURE = TESTS / "fixture.md"          # arrow.svg + plain.svg + chart.png, 2 boxes, 1 display formula, an indented block


def _mupdf():
    for name in ("pymupdf", "fitz"):
        if importlib.util.find_spec(name):
            return __import__(name)
    pytest.skip("pymupdf not installed")


@pytest.fixture(scope="module")
def mod():
    pytest.importorskip("fpdf")
    spec = importlib.util.spec_from_file_location("build_report_pdf_new", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(autouse=True)
def reset_globals(request):
    if "mod" not in request.fixturenames:
        yield
        return
    m = request.getfixturevalue("mod")
    saved = (m.MATH_MODE, dict(m.MATH_STATS))
    m.KEEP_FIRST_H1 = False
    m.MATH_STATS.clear()
    m._MATH_CACHE.clear()
    yield
    m.MATH_MODE = saved[0]
    m.MATH_STATS.clear()
    m.MATH_STATS.update(saved[1])


def run_cli(md, out, *flags, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), str(md), "-o", str(out), *flags], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=300)


def pdf_text(path):
    return "\n".join(p.get_text() for p in _mupdf().open(str(path)))


@pytest.fixture(scope="module")
def built():
    """The fixture rendered once (the SVG rasterising dominates the run time)."""
    for dep in ("fpdf", "PIL", "pygments"):
        pytest.importorskip(dep)
    d = Path(tempfile.mkdtemp(prefix="r2p-feat-"))
    out = d / "fixture.pdf"
    r = run_cli(FIXTURE, out)
    yield r, out
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def make(tmp_path):
    """make(markdown, *flags, files={name: bytes}) -> (CompletedProcess, pdf path); figures are copied next to the .md."""
    for dep in ("fpdf", "PIL", "pygments"):
        pytest.importorskip(dep)

    def go(text, *flags, files=None, env=None):
        shutil.copytree(TESTS / "figures", tmp_path / "figures", dirs_exist_ok=True)
        for name, data in (files or {}).items():
            (tmp_path / name).write_bytes(data)
        md = tmp_path / "doc.md"
        md.write_text(text, encoding="utf-8")
        out = tmp_path / "doc.pdf"
        return run_cli(md, out, *flags, env=env), out

    return go


# ---------------------------------------------------------------- the fixture end to end
def test_fixture_renders_and_reports_the_math_backend(built):
    r, out = built
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.read_bytes().startswith(b"%PDF")
    assert "Math  : display formulas via" in r.stdout and "inline math as Unicode text" in r.stdout


def test_fixture_text_has_no_raw_math_delimiters(built):
    _, out = built
    text = pdf_text(out)
    assert "$" not in text and "\\frac" not in text and "\\varphi" not in text
    assert "tₐ ≤ tₘᵣ" in text and "φ = pᵥ / pₛₐₜ(t)" in text      # inline math became Unicode text


# ---------------------------------------------------------------- SVG figures
def _have_rasteriser(mod):
    return bool(mod.find_browser()) or importlib.util.find_spec("cairosvg") is not None


def test_svgs_and_png_are_embedded_as_images(built, mod):
    if not _have_rasteriser(mod):
        pytest.skip("no headless Chrome/Edge or cairosvg to rasterise SVG")
    doc = _mupdf().open(str(built[1]))
    xrefs = {img[0] for page in doc for img in page.get_images(full=True)}
    assert len(xrefs) >= 3          # arrow.svg, plain.svg, chart.png


def test_svg_arrow_marker_survives_rasterising(mod, tmp_path):
    if not _have_rasteriser(mod):
        pytest.skip("no headless Chrome/Edge or cairosvg to rasterise SVG")
    from PIL import Image
    import io
    png = mod.svg_to_png(TESTS / "figures" / "arrow.svg")
    assert png and png.startswith(b"\x89PNG")
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.size == (1000, 300)                                   # 400x120 at 2.5x
    data = im.tobytes()
    reds = sum(1 for r, g, b in zip(data[0::3], data[1::3], data[2::3]) if r > 150 and g < 80 and b < 80)
    assert reds > 800               # the red arrow line and its head are drawn (a native fpdf2 draw loses the head)


def test_svg_without_any_rasteriser_falls_back_to_native_drawing(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod, "find_browser", lambda: None)
    monkeypatch.setitem(sys.modules, "cairosvg", None)               # import cairosvg -> ImportError
    mod._SVG_CACHE.clear()
    assert mod.svg_to_png(TESTS / "figures" / "arrow.svg") is None
    shutil.copytree(TESTS / "figures", tmp_path / "figures")
    md = tmp_path / "doc.md"
    md.write_text("# T\n\n# Chapter\n\n![plain](figures/plain.svg)\n\n![arrow](figures/arrow.svg)\n", encoding="utf-8")
    out = tmp_path / "doc.pdf"
    monkeypatch.setattr(sys, "argv", ["build_report_pdf.py", str(md), "-o", str(out)])
    mod.main()
    assert out.read_bytes().startswith(b"%PDF")
    assert "may be incomplete" in capsys.readouterr().out          # arrow.svg has a marker: warned, not crashed


def test_broken_svg_warns_and_does_not_crash(make):
    r, out = make("# T\n\n# Chapter\n\nbefore\n\n![broken](broken.svg)\n\nafter\n", files={"broken.svg": b"<svg width='10' height='10'><"})
    assert r.returncode == 0 and out.exists()
    assert "after" in pdf_text(out)


# ---------------------------------------------------------------- definition boxes
def _box_rects(path):
    boxes = []
    for page in _mupdf().open(str(path)):
        for d in page.get_drawings():
            fill = d.get("fill")
            if fill and all(abs(a - b / 255) < 0.01 for a, b in zip(fill, (238, 243, 250))):
                boxes.append(d["rect"])
    return boxes


def test_each_blockquote_is_one_shaded_box(built):
    assert len(_box_rects(built[1])) == 2


def test_box_holds_its_text_and_boxes_keep_document_order(built):
    text = pdf_text(built[1])
    assert text.index("Operative temperature") < text.index("Second box")
    page = next(p for p in _mupdf().open(str(built[1])) if "Operative temperature" in p.get_text())
    box = next(r for r in _box_rects(built[1]) if r.contains(page.search_for("Operative temperature")[0]))
    assert box.width > 400          # a full-width box, text inside its rectangle


def test_blank_quote_lines_split_paragraphs_inside_one_box(make):
    r, out = make("# T\n\n# Chapter\n\n> first para\n>\n> second para\n\nplain\n")
    assert r.returncode == 0
    assert len(_box_rects(out)) == 1 and "second para" in pdf_text(out)


def test_dark_theme_boxes_use_the_dark_fill(make):
    r, out = make("# T\n\n# Chapter\n\n> **Term**: definition\n", "--dark")
    assert r.returncode == 0 and not _box_rects(out)        # the light fill is not used
    assert "definition" in pdf_text(out)


# ---------------------------------------------------------------- captions
def test_caption_is_printed_once_and_alt_text_is_not_repeated(make):
    r, out = make("# T\n\n# Chapter\n\n![UNIQUEALTWORD](figures/chart.png)\n\n*Figure: caption printed once*\n")
    text = pdf_text(out)
    assert r.returncode == 0
    assert text.count("caption printed once") == 1 and "UNIQUEALTWORD" not in text


def test_caption_can_follow_after_blank_lines_and_stays_with_the_image(mod):
    _, blocks = mod.parse_markdown("# T\n\n![a](x.png)\n\n\n*Figure: far caption*\n\nnext paragraph\n")
    img = [b for b in blocks if b["type"] == "image"][0]
    assert img["caption"] == "Figure: far caption"
    assert [b["type"] for b in blocks] == ["image", "p"]


def test_italic_line_without_a_preceding_image_stays_a_paragraph(mod):
    _, blocks = mod.parse_markdown("# T\n\n*just an italic line*\n")
    assert [b["type"] for b in blocks] == ["p"]


# ---------------------------------------------------------------- indented output blocks
def test_indented_block_after_blank_line_is_a_code_block(mod):
    _, blocks = mod.parse_markdown("# T\n\nResult:\n\n    PMV = 0.278\n    PPD = 6.4 %\n\nBack to text.\n")
    code = [b for b in blocks if b["type"] == "code"]
    assert code and code[0]["lang"] == "" and code[0]["text"] == "PMV = 0.278\nPPD = 6.4 %"
    assert blocks[-1]["type"] == "p"


def test_indented_continuation_of_a_bullet_is_not_code(mod):
    _, blocks = mod.parse_markdown("# T\n\n- item one\n    continues here\n- item two\n")
    assert [b["type"] for b in blocks] == ["bullets"]


def test_indented_output_reaches_the_pdf(built):
    text = pdf_text(built[1])
    assert "PMV = 0.278" in text and "PPD = 6.4 %" in text


# ---------------------------------------------------------------- inline math -> Unicode
@pytest.mark.parametrize("tex,expected", [
    (r"\alpha + \beta", "α + β"),
    (r"t_a \le t_{mr}", "tₐ ≤ tₘᵣ"),
    (r"a \ge b", "a ≥ b"),
    (r"x^2 + \Delta t", "x² + Δt"),
    (r"3 \times 4 \cdot 2", "3 × 4 · 2"),
    (r"\frac{a+b}{2}", "(a+b)/2"),
    (r"\sqrt{x}", "√x"),
    (r"\sqrt{x+1}", "√(x+1)"),
    (r"\text{W/(m}^2\text{K)}", "W/(m²K)"),
    (r"t_{dp}", "t_dp"),                      # no Unicode subscript for d: plain fallback
    (r"\unknowncmd", "unknowncmd"),            # unknown commands show their name
])
def test_tex_to_unicode(mod, tex, expected):
    assert mod.tex_to_unicode(tex) == expected


def test_dollar_amounts_are_not_taken_for_math(mod):
    assert mod.prepare_markdown_text("rate $x_1$ and $5 or $6") == "rate x₁ and $5 or $6"


# ---------------------------------------------------------------- math backend chain
def _math_line(r):
    return next((l for l in r.stdout.splitlines() if l.strip().startswith("Math")), "")


DISPLAY = "# T\n\n# Chapter\n\n$$k = \\frac{1}{R}$$\n\ntext\n"


def test_math_unicode_backend_uses_no_image(make):
    r, out = make(DISPLAY, "--math", "unicode")
    assert r.returncode == 0 and "unicode x1" in _math_line(r)
    assert not any(page.get_images() for page in _mupdf().open(str(out)))
    assert "k = 1/R" in pdf_text(out)            # the formula is plain Unicode text instead


def test_math_mathtext_backend_draws_an_image(make):
    pytest.importorskip("matplotlib")
    r, out = make(DISPLAY, "--math", "mathtext")
    assert r.returncode == 0 and "mathtext x1" in _math_line(r)
    assert any(page.get_images() for page in _mupdf().open(str(out)))


def test_math_frontmatter_selects_the_backend_and_flag_wins(make):
    r, _ = make("---\nmath: unicode\n---\n" + DISPLAY)
    assert "unicode x1" in _math_line(r)
    pytest.importorskip("matplotlib")
    r, _ = make("---\nmath: unicode\n---\n" + DISPLAY, "--math", "mathtext")
    assert "mathtext x1" in _math_line(r)


def test_unknown_math_backend_in_frontmatter_warns_and_uses_auto(make):
    r, out = make("---\nmath: bogus\n---\n" + DISPLAY)
    assert r.returncode == 0 and "unknown math backend" in r.stdout and out.exists()


def test_unknown_math_flag_value_is_rejected_by_the_cli(make):
    r, _ = make(DISPLAY, "--math", "bogus")
    assert r.returncode == 2 and "invalid choice" in r.stderr


def test_auto_falls_through_a_broken_latex_install_silently(make, tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    stub = "pdflatex.bat" if os.name == "nt" else "pdflatex"
    (bin_dir / stub).write_text("@echo off\r\nexit /b 1\r\n" if os.name == "nt" else "#!/bin/sh\nexit 1\n")
    (bin_dir / stub).chmod(0o755)
    env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}
    r, out = make(DISPLAY, env=env)
    assert r.returncode == 0 and out.exists()
    assert "Traceback" not in r.stdout + r.stderr and "warning" not in r.stdout.lower()
    line = _math_line(r)
    assert "latex" not in line and ("mathtext x1" in line or "unicode x1" in line)


def test_latex_backend_is_chosen_first_when_it_works(mod, monkeypatch):
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGBA", (30, 10), (0, 0, 0, 0)).save(buf, "PNG")
    monkeypatch.setattr(mod, "_latex_png", lambda tex, color: buf.getvalue())
    mod.MATH_MODE = "auto"
    assert mod.math_png("x^2", (0, 0, 0)) == buf.getvalue()
    assert mod.MATH_STATS == {"latex": 1}


def test_failing_latex_falls_back_to_mathtext_then_unicode(mod, monkeypatch):
    def boom(tex, color):
        raise RuntimeError("tex exploded")
    monkeypatch.setattr(mod, "_latex_png", boom)
    mod.MATH_MODE = "latex"
    png = mod.math_png("x^2", (0, 0, 0))
    expected = "mathtext" if png else "unicode"
    assert mod.MATH_STATS == {expected: 1}
    mod._MATH_CACHE.clear()
    mod.MATH_STATS.clear()
    monkeypatch.setattr(mod, "_mathtext_png", boom)
    assert mod.math_png("y^2", (0, 0, 0)) is None and mod.MATH_STATS == {"unicode": 1}


def test_latex_tool_detection_needs_engine_and_converter(mod, monkeypatch):
    present = lambda *names: (lambda n, *a, **k: "x" if n in names else None)
    monkeypatch.setattr(shutil, "which", present())
    assert mod._latex_tools() is None
    monkeypatch.setattr(shutil, "which", present("pdflatex", "pdftocairo"))
    assert mod._latex_tools() == ("pdflatex", "pdftocairo")
    monkeypatch.setattr(shutil, "which", present("latex", "dvipng"))
    assert mod._latex_tools() == ("latex", "dvipng")


# ---------------------------------------------------------------- image sizing
def test_wide_and_tall_images_scale_to_fit_the_page(make):
    from PIL import Image
    import io

    def png(w, h):
        b = io.BytesIO()
        Image.new("RGB", (w, h), (200, 30, 30)).save(b, "PNG")
        return b.getvalue()

    r, out = make("# T\n\n# Chapter\n\n![wide](wide.png)\n\n![tall](tall.png)\n\n![small](small.png)\n",
                  files={"wide.png": png(3000, 100), "tall.png": png(100, 2500), "small.png": png(40, 30)})
    assert r.returncode == 0, r.stdout + r.stderr
    mm = 72 / 25.4
    infos = [i for page in _mupdf().open(str(out)) for i in page.get_image_info()]
    assert len(infos) == 3
    for i in infos:
        x0, y0, x1, y1 = i["bbox"]
        assert 18 * mm - 1 <= x0 and x1 <= (210 - 18) * mm + 1       # inside the margins
        assert y1 - y0 <= 120 * mm + 1                                # never taller than the cap
    wide, tall, small = infos
    assert wide["bbox"][2] - wide["bbox"][0] > 150 * mm               # wide image uses the text width
    assert small["bbox"][2] - small["bbox"][0] <= 130 * mm + 1        # a bare raster image keeps the 130 mm cap


def test_figure_that_almost_fits_shrinks_instead_of_leaving_a_gap(make):
    from PIL import Image
    import io
    b = io.BytesIO()
    Image.new("RGB", (1200, 1000), (30, 30, 200)).save(b, "PNG")
    mm = 72 / 25.4
    for n in range(14, 30):
        body = "\n\n".join(f"Filler paragraph number {i}." for i in range(n))
        r, out = make(f"# T\n\n# Chapter\n\n{body}\n\n![fig](fig.png)\n\n*Figure: caption*\n",
                      files={"fig.png": b.getvalue()})
        assert r.returncode == 0, r.stdout + r.stderr
        doc = _mupdf().open(str(out))
        for page in doc:
            infos = page.get_image_info()
            if not infos or page.number == 0:
                continue
            text_below_top = [bl for bl in page.get_text("blocks") if "Filler" in bl[4]]
            y_img = infos[0]["bbox"][1]
            if not text_below_top:                      # image alone at the top of a page
                prev = doc[page.number - 1]
                last = max((bl[3] for bl in prev.get_text("blocks") if "Filler" in bl[4]), default=0)
                room = (297 * mm - 22 * mm) - last       # space left on the previous page
                assert room < 84 * mm + 12 * mm, f"n={n}: {room / mm:.0f} mm left unused before the figure"


# ---------------------------------------------------------------- regression: the old behaviour with the new features present
def test_title_page_toc_tables_and_code_still_render_next_to_new_features(make):
    pypdf = pytest.importorskip("pypdf")
    text = ("---\ntitle: Regression Report\nsubtitle: A subtitle\nauthor: Jane Doe\nversion: none\n---\n\n"
            "# First Chapter\n\nIntro with $a \\le b$.\n\n## A subsection\n\n"
            "> **Term**: a definition box\n\n| name | value |\n|------|-------|\n| alpha | 1 |\n\n"
            "```python\ndef hello():\n    return 'world'\n```\n\n# Second Chapter\n\nClosing words.\n")
    r, out = make(text, "--math", "unicode")
    assert r.returncode == 0, r.stdout + r.stderr
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) >= 4                                     # cover, TOC, one page per chapter
    cover = reader.pages[0].extract_text()
    assert "Regression Report" in cover and "A subtitle" in cover and "Jane Doe" in cover
    body = "\n".join(p.extract_text() for p in reader.pages)
    for needle in ("First Chapter", "Second Chapter", "A subsection", "a definition box", "alpha", "return", "Closing words", "a ≤ b"):
        assert needle in body, needle
    assert len(_box_rects(out)) == 1
