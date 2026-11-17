import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_questions.py"

GOOD = [
    {"id": 1, "type": "single", "question": "Q?", "options": [{"key": "A", "text": "x"}, {"key": "B", "text": "y"}], "answer": ["A"]},
    {"id": 2, "type": "multi", "question": "Q?", "options": [{"key": "A", "text": "x"}, {"key": "B", "text": "y"}, {"key": "C", "text": "z"}], "answer": ["A", "C"]},
    {"id": 3, "type": "matrix", "question": "Q?", "items": [{"text": "s", "options": ["Yes", "No"], "answer": "No"}]},
    {"id": 4, "type": "ordering", "question": "Q?", "options": [{"key": "option_1", "text": "x"}, {"key": "option_2", "text": "y"}], "answer": ["option_2", "option_1"]},
    {"id": 5, "type": "matching", "question": "Q?", "items": [{"text": "s", "options": ["a", "b"], "answer": "a"}]},
]


def run(py, tmp_path, bank, *args):
    f = tmp_path / "q.json"
    f.write_text(json.dumps(bank), encoding="utf-8")
    return py(SCRIPT, f, *args)


def test_valid_bank_passes(py, tmp_path):
    r = run(py, tmp_path, GOOD, "--expect", "5")
    assert r.returncode == 0 and "OK" in r.stdout


def test_bad_answer_key_duplicate_option_and_wrong_count_are_reported(py, tmp_path):
    bad = json.loads(json.dumps(GOOD))
    bad[0]["answer"] = ["Z"]
    bad[1]["options"][2]["text"] = "y"
    bad[2]["items"][0]["answer"] = "Maybe"
    bad[3]["answer"] = ["option_1", "option_1"]
    bad[4]["items"][0]["answer"] = "c"
    r = run(py, tmp_path, bad, "--expect", "9")
    assert r.returncode == 1
    for needle in ("Q1: answer", "Q2: two options have identical text", "Q3: item 1", "Q4: ordering answer repeats", "Q5: item 1", "expected 9"):
        assert needle in r.stdout
