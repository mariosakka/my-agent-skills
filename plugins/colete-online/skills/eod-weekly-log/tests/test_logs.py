import json
import os
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
LOGS = ["daily-log", "weekly-log"]


@pytest.fixture
def run(py, tmp_path):
    """run(log, *args) executes the script with HOME pointing at a temp dir; returns the result."""
    env = {**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

    def go(log, *args):
        return py(SKILL / log, *args, env=env)

    go.data = lambda log: json.loads((tmp_path / ".local/share/desk-logs" / f"{log}.json").read_text(encoding="utf-8"))
    return go


@pytest.mark.parametrize("log", LOGS)
def test_show_on_empty_log_prints_nimic_for_every_section(run, log):
    r = run(log, "show")
    assert r.returncode == 0
    assert r.stdout.splitlines() == [":dart: Focus", "nimic", "", ":construction: Blocaje", "nimic", "",
                                     ":raising_hand: Ajutor necesar", "nimic"]


@pytest.mark.parametrize("log", LOGS)
def test_add_and_show_in_slack_format(run, log):
    assert run(log, "add", "focus", "ship", "the", "report").returncode == 0
    assert run(log, "add", "focus", "review PR").returncode == 0
    assert run(log, "add", "blockers", "waiting on access").returncode == 0
    out = run(log, "show").stdout
    assert "• ship the report" in out and "• review PR" in out and "• waiting on access" in out
    assert out.count("nimic") == 1  # only the help section is empty
    assert run.data(log) == {"focus": ["ship the report", "review PR"], "blockers": ["waiting on access"], "help": []}


@pytest.mark.parametrize("log", LOGS)
def test_remove_is_one_based(run, log):
    for text in ("one", "two", "three"):
        run(log, "add", "help", text)
    assert run(log, "remove", "help", "2").returncode == 0
    assert run.data(log)["help"] == ["one", "three"]


@pytest.mark.parametrize("log", LOGS)
def test_remove_out_of_range_fails_and_keeps_data(run, log):
    run(log, "add", "focus", "only")
    for bad in ("0", "2"):
        r = run(log, "remove", "focus", bad)
        assert r.returncode != 0 and "out of range (1–1)" in r.stderr
    assert run.data(log)["focus"] == ["only"]


@pytest.mark.parametrize("log", LOGS)
def test_unknown_section_command_and_missing_args(run, log):
    assert "Unknown section: nope" in run(log, "add", "nope", "x").stderr
    assert "Unknown section: nope" in run(log, "remove", "nope", "1").stderr
    assert "Unknown command: frobnicate" in run(log, "frobnicate").stderr
    assert "Usage:" in run(log).stderr
    assert "Usage:" in run(log, "add", "focus").stderr
    assert "Usage:" in run(log, "remove", "focus").stderr


@pytest.mark.parametrize("log", LOGS)
def test_clear_resets_everything(run, log):
    run(log, "add", "focus", "a")
    run(log, "add", "help", "b")
    assert run(log, "clear").returncode == 0
    assert run.data(log) == {"focus": [], "blockers": [], "help": []}


@pytest.mark.parametrize("log", LOGS)
def test_unicode_text_round_trips(run, log):
    run(log, "add", "focus", "migrare bază de date – șterge țintă")
    assert "• migrare bază de date – șterge țintă" in run(log, "show").stdout


def test_daily_and_weekly_logs_are_independent(run):
    run("daily-log", "add", "focus", "d")
    run("weekly-log", "add", "focus", "w")
    assert run.data("daily-log")["focus"] == ["d"]
    assert run.data("weekly-log")["focus"] == ["w"]
