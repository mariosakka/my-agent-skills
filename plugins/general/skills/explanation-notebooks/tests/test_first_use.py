import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "first_use.py"


def cell(kind, text):
    return {"cell_type": kind, "metadata": {}, "source": text.splitlines(keepends=True)}


@pytest.fixture
def notebook(tmp_path):
    cells = [
        cell("markdown", "# Intro\n\nA room has a setpoint."),
        cell("code", "thermostat = 1  # code cells are ignored"),
        cell("markdown", "## Chapter two\n\nThe Thermostat reads the sensor.\n\nSecond thermostat mention."),
        cell("markdown", "A later paragraph without a heading mentions the K unit and kelvin."),
        cell("markdown", "## Chapter three\n\nThe heat load is the heat per second."),
    ]
    path = tmp_path / "nb.ipynb"
    path.write_text(json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}), encoding="utf-8")
    return path


def lines(py, nb, terms):
    r = py(SCRIPT, nb, terms)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_reports_cell_index_and_heading_of_first_hit(py, notebook):
    assert lines(py, notebook, "setpoint,heat load") == ["setpoint (0, '# Intro')", "heat load (4, '## Chapter three')"]


def test_code_cells_are_ignored_and_match_is_case_insensitive(py, notebook):
    assert lines(py, notebook, "thermostat") == ["thermostat (2, '## Chapter two')"]


def test_missing_term_is_reported_not_found(py, notebook):
    assert lines(py, notebook, "quantum") == ["quantum NOT FOUND"]


def test_terms_are_regexes(py, notebook):
    out = py(SCRIPT, notebook, r"\bK\b").stdout
    assert out.strip() == r"\bK\b (3, '## Chapter two')"


def test_heading_context_carries_over_cells_without_heading(py, notebook):
    assert "Chapter two" in py(SCRIPT, notebook, "kelvin").stdout


def test_one_line_per_term_in_order(py, notebook):
    out = lines(py, notebook, "heat load,setpoint,nothing")
    assert [l.split(" (")[0].split(" NOT")[0] for l in out] == ["heat load", "setpoint", "nothing"]


def test_usage_error_without_arguments(py):
    assert py(SCRIPT).returncode != 0
