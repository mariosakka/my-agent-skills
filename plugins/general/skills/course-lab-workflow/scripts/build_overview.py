"""Build the course overview: <dir>/parts/*.md (sorted by file name) -> <dir>/overview.md -> <dir>/overview.pdf.

Run from the course repository root (default folder: overview/):
    python tools/build_overview.py [overview-folder]

Each part starts with a `# Chapter` heading (the introduction, one per lab, the cross-lab chapter); figures live in
<dir>/figures/ and are referenced as figures/<name>. overview.md is committed, overview.pdf is not.
The PDF is rendered by the `report-to-pdf` skill: set REPORT_TO_PDF_SCRIPT to its scripts/build_report_pdf.py, or install the
skill under ~/.claude/plugins (the newest copy found is used).
"""
import glob
import os
import re
import subprocess
import sys


def find_renderer():
    env = os.environ.get("REPORT_TO_PDF_SCRIPT")
    if env and os.path.exists(env):
        return env
    pattern = os.path.expanduser("~/.claude/plugins/**/report-to-pdf/scripts/build_report_pdf.py")
    hits = sorted(glob.glob(pattern, recursive=True), key=os.path.getmtime, reverse=True)
    return hits[0] if hits else None


def join_parts(folder="overview"):
    """Write <folder>/overview.md from the parts and return (md path, number of parts, text length)."""
    parts = sorted(glob.glob(os.path.join(folder, "parts", "*.md")))
    if not parts:
        sys.exit(f"no parts found in {folder}/parts/")
    body = "\n\n".join(open(p, encoding="utf8").read().strip() for p in parts) + "\n"
    labs = sorted({int(n) for n in re.findall(r"^# Lab (\d+)", body, re.M)})
    span = f"labs {labs[0]} to {labs[-1]}" if labs else "all labs"
    head = f"---\ntitle: Course overview\nsubtitle: {span}\n---\n\n"
    md = os.path.join(folder, "overview.md")
    with open(md, "w", encoding="utf8", newline="\n") as f:
        f.write(head + body)
    return md, len(parts), len(body)


def build(folder="overview"):
    md, n, size = join_parts(folder)
    renderer = find_renderer()
    if renderer is None:
        sys.exit("report-to-pdf not found: install the skill or set REPORT_TO_PDF_SCRIPT")
    pdf = os.path.join(folder, "overview.pdf")
    subprocess.run([sys.executable, renderer, md, "-o", pdf], check=True, capture_output=True)
    print(f"{n} parts -> {md} ({size} chars), {pdf} ({os.path.getsize(pdf) // 1024} KB)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "overview")
