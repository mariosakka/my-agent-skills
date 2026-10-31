import re
import subprocess
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config" / "channels.sh"


def sourced_vars(bash):
    script = f'source "{CONFIG.as_posix()}"; set | grep "^SLACK_"'
    out = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8").stdout
    return dict(line.split("=", 1) for line in out.splitlines())


def test_channels_file_defines_the_expected_channel_variables(bash):
    channels = sourced_vars(bash)
    assert {"SLACK_ZDEV_STATUS", "SLACK_ZDEV_WEEKLY"} <= set(channels)


def test_channel_ids_look_like_slack_ids_and_are_distinct(bash):
    channels = sourced_vars(bash)
    for name, value in channels.items():
        assert re.fullmatch(r"C[A-Z0-9]{8,}", value.strip("'\"")), f"{name}={value!r} is not a Slack channel id"
    assert len(set(channels.values())) == len(channels)


def test_skill_md_documents_how_to_source_the_config():
    text = (CONFIG.parents[1] / "SKILL.md").read_text(encoding="utf-8")
    assert "config/channels.sh" in text
