#!/usr/bin/env python3
"""Validate a quiz question bank (questions.json) against the exam-quiz-site schema.

Usage: validate_questions.py questions.json [--expect N]
Exit 0 = valid, 1 = errors (printed one per line). Standard library only.
"""
import json
import sys

TYPES = {"single", "multi", "matrix", "matching", "ordering"}
ITEM_TYPES = {"matrix", "matching"}


def check(bank, expect=None):
    errs = []
    if not isinstance(bank, list) or not bank:
        return ["top level must be a non-empty list"]
    ids = [q.get("id") for q in bank]
    if len(set(ids)) != len(ids):
        errs.append("duplicate ids")
    if expect is not None and len(bank) != expect:
        errs.append(f"expected {expect} questions, found {len(bank)}")
    for q in bank:
        n = q.get("id")
        err = lambda m: errs.append(f"Q{n}: {m}")  # noqa: E731
        if q.get("type") not in TYPES:
            err(f"type must be one of {sorted(TYPES)}")
            continue
        if not str(q.get("question", "")).strip():
            err("empty question text")
        if "\ufffd" in json.dumps(q, ensure_ascii=False):
            err("contains U+FFFD (bad PDF text encoding)")
        if q["type"] in ITEM_TYPES:
            items = q.get("items") or []
            if not items:
                err("matrix needs items")
            for i, it in enumerate(items, 1):
                if it.get("answer") not in (it.get("options") or []):
                    err(f"item {i}: answer {it.get('answer')!r} not in its options")
                if len(set(it.get("options") or [])) != len(it.get("options") or []):
                    err(f"item {i}: duplicate options")
        else:
            opts = q.get("options") or []
            keys = [o.get("key") for o in opts]
            if len(opts) < 2 or len(set(keys)) != len(keys):
                err("needs >=2 options with unique keys")
            if len({o.get("text") for o in opts}) != len(opts):
                err("two options have identical text (PDF typo?)")
            ans = q.get("answer") or []
            if not ans or any(a not in keys for a in ans):
                err(f"answer {ans} not within option keys {keys}")
            if q["type"] == "single" and len(ans) != 1:
                err("single must have exactly one answer")
            if q["type"] == "multi" and len(ans) < 2:
                err("multi must have at least two answers")
            if q["type"] == "ordering" and len(set(ans)) != len(ans):
                err("ordering answer repeats an option")
    return errs


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    expect = int(argv[argv.index("--expect") + 1]) if "--expect" in argv else None
    with open(argv[0], encoding="utf-8") as f:
        errs = check(json.load(f), expect)
    print("\n".join(errs) if errs else "OK")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
