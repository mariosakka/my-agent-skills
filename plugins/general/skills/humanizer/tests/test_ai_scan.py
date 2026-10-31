import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ai-scan.sh"


def scan(sh, text, tmp_path, via_file=False):
    if via_file:
        f = tmp_path / "in.txt"
        f.write_text(text, encoding="utf-8")
        return sh(SCRIPT, f)
    return sh(SCRIPT, stdin=text)


def total(r):
    return int(re.search(r"Total AI-isms flagged: (\d+)", r.stdout).group(1))


def test_clean_text_scores_zero_and_low(sh, tmp_path):
    r = scan(sh, "The cat sat on the mat.\n", tmp_path)
    assert r.returncode == 0
    assert total(r) == 0 and "Low" in r.stdout


def test_counts_words_case_insensitively_and_lists_them(sh, tmp_path):
    r = scan(sh, "This is Crucial. A crucial and pivotal step.\n", tmp_path)
    assert total(r) == 3
    assert re.search(r"2 × crucial", r.stdout) and re.search(r"1 × pivotal", r.stdout)


def test_reads_a_file_argument_and_stdin_the_same_way(sh, tmp_path):
    text = "We leverage a robust, seamless tapestry.\n"
    assert total(scan(sh, text, tmp_path)) == total(scan(sh, text, tmp_path, via_file=True)) == 4


def test_multiword_phrases_are_matched(sh, tmp_path):
    r = scan(sh, "It's worth noting that, in conclusion, this is a game changer.\n", tmp_path)
    assert total(r) == 3


def test_em_dashes_count_and_rule_of_three_is_only_reported(sh, tmp_path):
    r = scan(sh, "One — two — three. We need speed, safety, and style.\n", tmp_path)
    assert total(r) == 2 and "em dash" in r.stdout  # the rule-of-three pattern is listed but not added to the total
    assert "rule-of-three" in r.stdout


@pytest.mark.parametrize("n_words,verdict", [(3, "Low"), (4, "Moderate"), (11, "High density")])
def test_verdict_thresholds(sh, tmp_path, n_words, verdict):
    r = scan(sh, " ".join(["pivotal"] * n_words) + "\n", tmp_path)
    assert total(r) == n_words
    assert verdict in r.stdout.split("Total AI-isms flagged")[1]
