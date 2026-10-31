"""Behaviour of report-to-pdf that is stable across versions: the markdown parser, frontmatter and the CLI end to end.

The newer features (SVG images, definition boxes, captions, math) are tested in test_new_features.py.
"""
import importlib.util
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "build_report_pdf.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("build_report_pdf", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(autouse=True)
def reset_globals(mod):
    mod.KEEP_FIRST_H1 = False


# ---------------------------------------------------------------- frontmatter and inline text
def test_frontmatter_is_parsed_and_removed(mod):
    meta, rest = mod.parse_frontmatter(["---", "Title: My Report", "subtitle: \"Quoted\"", "---", "# H", "text"])
    assert meta == {"title": "My Report", "subtitle": "Quoted"}
    assert rest == ["# H", "text"]


def test_no_frontmatter_leaves_lines_untouched(mod):
    assert mod.parse_frontmatter(["# H", "x"]) == ({}, ["# H", "x"])
    assert mod.parse_frontmatter([]) == ({}, [])


@pytest.mark.parametrize("cli,fm,expected", [
    (None, {}, "today"), ("2.0", {"version": "1.0"}, "2.0"), (None, {"version": "1.0"}, "1.0"),
    (None, {"version": "none"}, ""), (None, {"version": "OFF"}, ""),
])
def test_version_resolution(mod, cli, fm, expected):
    got = mod._resolve_version(cli, fm)
    assert got == (mod.date.today().isoformat() if expected == "today" else expected)


def test_inline_markdown_is_normalised_for_fpdf(mod):
    assert mod.prepare_markdown_text("a *it* b") == "a __it__ b"
    assert mod.prepare_markdown_text("snake_case_name stays") == "snake_case_name stays"
    assert mod.prepare_markdown_text("call `foo()` now") == "call foo() now"
    assert mod.prepare_markdown_text("**bold** [t](http://x)") == "**bold** [t](http://x)"


# ---------------------------------------------------------------- block parser
def test_first_h1_becomes_the_document_title_later_ones_are_headings(mod):
    title, blocks = mod.parse_markdown("# Title\n\n## Sub\n\n# Second\n")
    assert title == "Title"
    assert [(b["type"], b["text"]) for b in blocks] == [("h2", "Sub"), ("h1", "Second")]


def test_first_h1_is_kept_when_a_title_is_set_elsewhere(mod):
    mod.KEEP_FIRST_H1 = True
    title, blocks = mod.parse_markdown("# Title\n")
    assert title is None and blocks[0] == {"type": "h1", "text": "Title"}


def test_lists_paragraphs_and_continuation_lines(mod):
    _, blocks = mod.parse_markdown("Para one\nstill para\n\n- a\n- b\n  continued\n\n1. x\n2. y\n")
    assert blocks[0] == {"type": "p", "text": "Para one still para"}
    assert blocks[1] == {"type": "bullets", "items": ["a", "b continued"]}
    assert blocks[2] == {"type": "numbered", "items": ["x", "y"]}


def test_code_fence_keeps_language_and_literal_text(mod):
    _, blocks = mod.parse_markdown("```python\nx = '**not bold**'\n\ny = 2\n```\n")
    assert blocks == [{"type": "code", "lang": "python", "text": "x = '**not bold**'\n\ny = 2"}]


def test_table_headers_rows_and_separator_row_dropped(mod):
    _, blocks = mod.parse_markdown("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n")
    assert blocks == [{"type": "table", "headers": ["a", "b"], "rows": [["1", "2"], ["3", "4"]]}]


def test_special_lines(mod):
    _, blocks = mod.parse_markdown("---\n\n<br>\n\n<!-- pagebreak -->\n\n![alt text](pics/a.png)\n")
    assert [b["type"] for b in blocks] == ["spacer", "br", "pagebreak", "image"]
    assert blocks[3] == {"type": "image", "alt": "alt text", "path": "pics/a.png"}


def test_blank_input_gives_no_blocks(mod):
    assert mod.parse_markdown("\n\n") == (None, [])


# ---------------------------------------------------------------- CLI
def test_help_lists_the_documented_flags(py):
    r = py(SCRIPT, "--help")
    assert r.returncode == 0
    for flag in ("--output", "--logo", "--title", "--subtitle", "--version", "--no-header", "--author", "--cover",
                 "--vendor", "--accent", "--dark"):
        assert flag in r.stdout


def test_missing_input_fails_cleanly(py, tmp_path):
    pytest.importorskip("fpdf")
    r = py(SCRIPT, tmp_path / "nope.md")
    assert r.returncode == 1 and "input file not found" in r.stdout


SAMPLE = """---
title: Smoke Report
subtitle: A subtitle
version: 1.2
vendor: ACME
author: Jane Doe
---
# Smoke Report

# First Chapter

Some **bold** text and a [link](https://example.com).

## A subsection

- first bullet
- second bullet

1. step one
2. step two

```python
def hello():
    return "world"
```

| name | value |
|------|-------|
| a    | 1     |

# Second Chapter

Closing words.
"""


@pytest.fixture
def render(py, tmp_path):
    for dep in ("fpdf", "PIL", "pygments"):
        pytest.importorskip(dep)

    def go(text=SAMPLE, *flags):
        md = tmp_path / "report.md"
        md.write_text(text, encoding="utf-8")
        out = tmp_path / "out.pdf"
        r = py(SCRIPT, md, "-o", out, *flags)
        return r, out

    return go


def test_smoke_renders_a_valid_pdf(render):
    r, out = render()
    assert r.returncode == 0, r.stdout + r.stderr
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and b"%%EOF" in data[-1024:]
    assert "Created:" in r.stdout


def test_pdf_has_title_toc_and_body_pages_with_all_content(render):
    pypdf = pytest.importorskip("pypdf")
    r, out = render()
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) >= 4  # title page, table of contents, one page per major chapter
    text = "\n".join(p.extract_text() for p in reader.pages)
    for needle in ("Smoke Report", "A subtitle", "Jane Doe", "First Chapter", "Second Chapter", "A subsection",
                   "first bullet", "step two", 'return "world"', "Closing words"):
        assert needle in text, needle


@pytest.mark.parametrize("flags", [("--dark",), ("--cover", "left"), ("--no-header",), ("--accent", "30,80,180"),
                                   ("--title", "Other", "--subtitle", "S", "--version", "9", "--vendor", "V")])
def test_optional_flags_still_produce_a_pdf(render, flags):
    r, out = render(SAMPLE, *flags)
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.read_bytes().startswith(b"%PDF")


def test_invalid_accent_falls_back_with_a_warning(render):
    r, out = render(SAMPLE, "--accent", "red")
    assert r.returncode == 0 and "invalid --accent" in r.stdout


def test_cli_title_wins_over_frontmatter(render):
    pypdf = pytest.importorskip("pypdf")
    r, out = render(SAMPLE, "--title", "CLI Title")
    assert "CLI Title" in pypdf.PdfReader(str(out)).pages[0].extract_text()


def test_png_image_is_embedded(render, tmp_path):
    pytest.importorskip("pypdf")
    from PIL import Image
    Image.new("RGB", (40, 30), "red").save(tmp_path / "pic.png")
    r, out = render("# T\n\n# Chapter\n\n![a red box](pic.png)\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert b"/Subtype /Image" in out.read_bytes()


def test_missing_image_is_skipped_with_a_warning_not_a_crash(render):
    r, out = render("# T\n\n# Chapter\n\n![gone](nope.png)\n")
    assert r.returncode == 0 and out.exists()
