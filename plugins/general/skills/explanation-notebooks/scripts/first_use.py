"""List where each term is first mentioned in a notebook's markdown cells, to catch terms used before they are defined.

    python first_use.py notebook.ipynb "thermostat,setpoint,heat load,\bK\b"

Terms are case-insensitive regexes. Output: term -> (cell index, nearest heading above it).
If a term's first cell is not the chapter that defines it, the term is used too early: move the
definition up to that cell, or reword the early mention.
"""
import json, re, sys

nb = json.load(open(sys.argv[1], encoding="utf8"))
terms = sys.argv[2].split(",")
head, first = "", {}
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] != "markdown":
        continue
    s = "".join(c["source"])
    m = re.match(r"#+ [^\n]*", s)
    if m:
        head = m.group(0)[:60]
    for t in terms:
        if t not in first and re.search(t, s, re.I):
            first[t] = (i, head)
for t in terms:
    print(t, first.get(t, "NOT FOUND"))
