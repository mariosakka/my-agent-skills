"""course-lab-workflow: the bundled build scripts (overview joiner, submission helpers) and the skill's structure."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
REFERENCES = ["lab-layout-and-solving.md", "moodle-submission.md", "course-overview.md", "pitfalls.md"]


def load(name):
    spec = importlib.util.spec_from_file_location(f"clw_{name}", SKILL / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def parts(tmp_path):
    p = tmp_path / "overview" / "parts"
    p.mkdir(parents=True)
    (p / "30-lab-3.md").write_text("# Lab 3: HVAC\n\nthree\n", encoding="utf-8")
    (p / "90-key-relationships.md").write_text("# Relationships\n\nlast\n", encoding="utf-8")
    (p / "00-introduction.md").write_text("# The course in one picture\n\nfirst\n", encoding="utf-8")
    (p / "20-lab-2.md").write_text("# Lab 2: Comfort\n\ntwo\n", encoding="utf-8")
    return tmp_path / "overview"


# ---------------------------------------------------------------- build_overview
def test_overview_joins_parts_in_file_name_order_with_frontmatter(parts):
    md, n, _ = load("build_overview").join_parts(str(parts))
    text = Path(md).read_text(encoding="utf-8")
    assert n == 4 and text.startswith("---\ntitle: Course overview\nsubtitle: labs 2 to 3\n---\n")
    order = [text.index(s) for s in ("first", "two", "three", "last")]
    assert order == sorted(order)


def test_overview_without_parts_exits(tmp_path):
    with pytest.raises(SystemExit):
        load("build_overview").join_parts(str(tmp_path / "overview"))


def test_overview_renderer_comes_from_the_environment_variable(tmp_path, monkeypatch):
    fake = tmp_path / "render.py"
    fake.write_text("")
    monkeypatch.setenv("REPORT_TO_PDF_SCRIPT", str(fake))
    assert load("build_overview").find_renderer() == str(fake)


def test_overview_build_calls_the_renderer_on_the_joined_markdown(parts, tmp_path, monkeypatch):
    fake = tmp_path / "render.py"
    fake.write_text("import sys\nopen(sys.argv[3], 'wb').write(b'%PDF-fake')\n")
    monkeypatch.setenv("REPORT_TO_PDF_SCRIPT", str(fake))
    load("build_overview").build(str(parts))
    assert (parts / "overview.pdf").read_bytes().startswith(b"%PDF") and (parts / "overview.md").exists()


# ---------------------------------------------------------------- build_submission
@pytest.fixture
def bs():
    pytest.importorskip("docx")
    pytest.importorskip("pygments")
    return load("build_submission")


def test_submission_long_code_lines_wrap_with_indentation(bs):
    line = "    " + "word " * 40
    out = [p + line[a:b] for p, a, b in bs.wrap(line)]
    assert len(out) > 1 and all(len(x) <= 92 for x in out) and out[1].startswith("      ")


def test_submission_python_highlighting_colours_keywords_strings_and_numbers(bs):
    cols = bs.highlight(["def f(x):", '    return "a" + 1'])
    assert cols[0][0] != bs.CODE_INK
    assert len({tuple(c) for c in cols[0] + cols[1]}) >= 3


def test_submission_docx_contains_the_title_and_code(bs, tmp_path):
    md = tmp_path / "sub.md"
    md.write_text("# Laboratory 9 - Test\n\n**Team 4**\n\nMembers:\n\n- A B\n\n## 1. Objective\n\nWe did it.\n\n"
                  "```python\nprint(1)\n```\n", encoding="utf-8")
    out = tmp_path / "sub.docx"
    bs.build_docx(str(md), str(out))
    from docx import Document
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs) + "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "Laboratory 9 - Test" in text and "We did it." in text and "print(1)" in text


# ---------------------------------------------------------------- structure
@pytest.mark.parametrize("ref", REFERENCES)
def test_reference_files_exist_and_are_linked_from_skill_md(ref):
    assert (SKILL / "references" / ref).read_text(encoding="utf-8").strip()
    assert f"references/{ref}" in (SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_skill_is_named_course_lab_workflow_and_mentions_the_former_name():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"^name: course-lab-workflow$", text, re.M)
    assert "lab-creation" in text.split("---", 2)[1]          # the description says it supersedes it


def test_bundled_scripts_are_documented_in_skill_md():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for script in ("scripts/build_submission.py", "scripts/build_overview.py"):
        assert script in text and (SKILL / script).exists()
    assert "python-docx" in text and "pygments" in text.lower()
