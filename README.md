# my-agent-skills

Personal AI agent skill library, packaged as a plugin marketplace for Claude Code and kept compatible with GitHub Copilot CLI, Codex, Muse Code, and Gemini CLI.

Skills live in two plugins. Each skill is a self-contained folder with a `SKILL.md` file that tells the agent what to do and how.

The repo is private, so every install path needs git credentials for `mariosakka/my-agent-skills`.

---

## Install

### Claude Code

```
/plugin marketplace add mariosakka/my-agent-skills
/plugin install colete-online@mario-agent-skills
/plugin install general@mario-agent-skills
```

Notes for a private repo:
- Manual add/install uses your existing git credentials (`gh auth login` or an SSH key).
- Background auto-update of the marketplace can't prompt for credentials, so set `GITHUB_TOKEN` in your environment for it to work.

### GitHub Copilot CLI

```bash
copilot plugin marketplace add mariosakka/my-agent-skills
```

Copilot CLI reads `.claude-plugin/marketplace.json`. For installing a plugin from it, run `copilot plugin --help` or see the [Copilot CLI plugin docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-marketplace).

### Codex

```bash
codex plugin marketplace add mariosakka/my-agent-skills
```

Then install the plugins from the marketplace, see the [Codex plugin docs](https://developers.openai.com/codex/plugins/build).

### Muse Code (experimental, unverified)

Muse plugins are behind `MUSE_EXPERIMENTAL_PLUGINS=1`. The `.muse-plugin/marketplace.json` and `.muse-plugin/plugin.json` shapes here follow public Muse plugin repos, not official docs, so treat them as unverified. Install with `muse plugins install`, then `muse plugins approve <name>`; for the marketplace-add command, see the Muse Code docs.

### Gemini CLI (manual install)

**Gemini has no plugin marketplace, so it can't install this repo automatically.** Its extensions only auto-discover a root `skills/` directory, and this repo keeps skills under `plugins/`. Install each skill yourself with `gemini skills install`, using `--path` to point at the skill's folder:

```bash
REPO=https://github.com/mariosakka/my-agent-skills.git

# colete-online
gemini skills install $REPO --path plugins/colete-online/skills/colete-flow --consent
gemini skills install $REPO --path plugins/colete-online/skills/eod-weekly-log --consent
gemini skills install $REPO --path plugins/colete-online/skills/issue-audit --consent
gemini skills install $REPO --path plugins/colete-online/skills/pr-audit --consent
gemini skills install $REPO --path plugins/colete-online/skills/slack-work-communication --consent

# general
gemini skills install $REPO --path plugins/general/skills/explain-syntax --consent
gemini skills install $REPO --path plugins/general/skills/humanizer --consent
gemini skills install $REPO --path plugins/general/skills/pr-inspect-and-act --consent
gemini skills install $REPO --path plugins/general/skills/report-to-pdf --consent
```

Install only the skills you want. `--consent` skips the security confirmation prompt; drop it to review each one. Check the result with `gemini skills list`, and remove one with `gemini skills uninstall <name>`.

Notes:
- There is no auto-update. To pick up changes, uninstall a skill and install it again.
- The repo is private, so the install needs git credentials for `mariosakka/my-agent-skills` (for example `gh auth login`). This has not been tested with Gemini.
- Command syntax is from the [Gemini CLI skills docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md).
---

## Plugins and skills

### `colete-online`

| Skill | Description |
|-------|-------------|
| [`colete-flow`](plugins/colete-online/skills/colete-flow/SKILL.md) | Standing workflow for real tasks on Colete Online repos: issue lifecycle, alignment gate, PR review loop, Slack status |
| [`eod-weekly-log`](plugins/colete-online/skills/eod-weekly-log/SKILL.md) | Adds items to the EOD and weekly work logs via scripts and formats them for Slack |
| [`issue-audit`](plugins/colete-online/skills/issue-audit/SKILL.md) | Fetches approved+unassigned issues (script) and validates each for staleness/overlap (agent) |
| [`pr-audit`](plugins/colete-online/skills/pr-audit/SKILL.md) | Fetches Mario's in-flight PRs (assigned/backing-issue) and PRs he owes a review on, with draft/review-history status |
| [`slack-work-communication`](plugins/colete-online/skills/slack-work-communication/SKILL.md) | Sends structured Slack status messages for work events |

### `general`

| Skill | Description |
|-------|-------------|
| [`explain-syntax`](plugins/general/skills/explain-syntax/SKILL.md) | Explains framework/language syntax to learners by anchoring it to something they already know |
| [`humanizer`](plugins/general/skills/humanizer/SKILL.md) | Removes AI-writing patterns from text to make it sound natural |
| [`pr-inspect-and-act`](plugins/general/skills/pr-inspect-and-act/SKILL.md) | Standard `gh` commands for reading, inspecting and acting on pull requests (comments, CI, reviews) |
| [`report-to-pdf`](plugins/general/skills/report-to-pdf/SKILL.md) | Renders a Markdown report into a consistently styled PDF (title page, TOC, syntax-highlighted code, tables) |

The old `homepage` skill is gone; the Desk VS Code extension (`mariosakka/vscode-desk`) replaces it.

---

## Tool compatibility

| Tool | Marketplace file | Per-plugin manifest | Marketplace? |
|---|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` | yes |
| Copilot CLI | `.github/plugin/marketplace.json` or `.claude-plugin/marketplace.json` | `plugin.json` | yes |
| Codex | `.agents/plugins/marketplace.json` | `.codex-plugin/plugin.json` | yes |
| Muse Code | `.muse-plugin/marketplace.json` (and `.agents/plugins/marketplace.json`) | `.muse-plugin/plugin.json` (`schemaVersion: 1`) | yes, experimental and unverified (`MUSE_EXPERIMENTAL_PLUGINS=1`) |
| Gemini CLI | none | none (manual `gemini skills install <url> --path <dir>` per skill) | no |

---

## Add a new skill

1. Pick a plugin (`plugins/colete-online` or `plugins/general`) and create `plugins/<group>/skills/<name>/`
2. Add a `SKILL.md` inside it with frontmatter `name` (equal to the folder name) and a non-empty `description`
3. Commit and push
4. Update: marketplace tools pick it up on marketplace update. For Gemini, add a `gemini skills install` line to the Gemini section above.

```
my-agent-skills/
└── plugins/
    └── general/
        └── skills/
            └── my-skill/
                └── SKILL.md   ← required; marks this folder as a skill
```

---

## CI

`.github/workflows/validate.yml` runs `scripts/validate.sh` on every push, pull request, and weekly. It validates all manifests: JSON validity, plugin names and versions matching across formats, marketplace `source` paths existing, LF line endings on shell scripts, and each `SKILL.md` frontmatter. Drift between formats fails the build.
