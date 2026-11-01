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
gemini skills install $REPO --path plugins/general/skills/explanation-notebooks --consent
gemini skills install $REPO --path plugins/general/skills/explain-syntax --consent
gemini skills install $REPO --path plugins/general/skills/humanizer --consent
gemini skills install $REPO --path plugins/general/skills/pr-inspect-and-act --consent
gemini skills install $REPO --path plugins/general/skills/report-to-pdf --consent
gemini skills install $REPO --path plugins/general/skills/repo-foundations --consent
gemini skills install $REPO --path plugins/general/skills/lab-creation --consent
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
| [`explanation-notebooks`](plugins/general/skills/explanation-notebooks/SKILL.md) | Teaches any subject from any source (docx, pptx, xlsx, csv, pdf, md): scripts extract metadata, text and images; simple and in-depth rules; define each concept at first use |
| [`humanizer`](plugins/general/skills/humanizer/SKILL.md) | Removes AI-writing patterns from text to make it sound natural |
| [`pr-inspect-and-act`](plugins/general/skills/pr-inspect-and-act/SKILL.md) | Standard `gh` commands for reading, inspecting and acting on pull requests (comments, CI, reviews) |
| [`report-to-pdf`](plugins/general/skills/report-to-pdf/SKILL.md) | Renders a Markdown report into a consistently styled PDF (title page, TOC, syntax-highlighted code, tables) |
| [`repo-foundations`](plugins/general/skills/repo-foundations/SKILL.md) | Establishes project-specific structure, testing, CI, release, privacy, and workspace standards |
| [`lab-creation`](plugins/general/skills/lab-creation/SKILL.md) | Creates or completes educational labs from assignments and existing course conventions |

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

## Tests

Every skill has pytest tests next to it (`plugins/<plugin>/skills/<skill>/tests/`), plus repo-level checks in `tests/` (frontmatter, referenced files, script syntax, manifest consistency). The shell scripts run for real against a stub `gh`, so nothing touches the network or an account.

```
pip install -r requirements-dev.txt
bash scripts/run_tests.sh            # all tests; extra args go to pytest, e.g. -k pr_audit
```

The shell-script tests need `bash` and `jq` (they skip when missing); the PDF tests need `fpdf2`, `Pillow` and `Pygments` (they skip when missing).

### Test Strategy

For every feature or behavior change, assess each layer below and record either
the tests/evidence or a reasoned N/A. Add tests for new behavior, update tests
when behavior changes, and remove or rewrite tests when their feature is removed.

| Layer | Decision and evidence |
| --- | --- |
| Drift/contract | Covered by `tests/test_manifests.py` and `scripts/validate.sh`. |
| Unit | Covered by `tests/` and `plugins/general/skills/repo-foundations/tests/`. |
| Integration | Covered by `plugins/general/skills/repo-foundations/tests/test_check_release.py` and subprocess-based tool tests. |
| UI/component/accessibility | N/A: this repository provides agent skills and has no interactive product UI. |
| End-to-end/smoke | Covered by `.github/workflows/validate.yml` plugin-install smoke test. |
| Performance/load | N/A: there is no long-running product runtime to profile. |
| Security/privacy/data integrity | Covered by `plugins/general/skills/repo-foundations/tests/test_repo_check.py`. |
| Domain-specific | N/A: reassess when a new feature introduces additional domain risks. |

---

## CI

`.github/workflows/validate.yml` runs the Bash validator and its PowerShell mirror on every push, pull request, and weekly. They check manifest JSON and version/name consistency, marketplace sources, skill frontmatter, duplicate skills, and LF-only shell scripts. Drift between formats fails the build.

Run the same repository checks natively on Windows with `powershell -NoProfile -File scripts/validate.ps1`; CI continues to use the Bash version.

Install the local pre-push documentation and source/test checks with `bash scripts/install_hooks.sh`.
The hook also runs Gitleaks against committed Git history. Install Gitleaks
from its [official instructions](https://github.com/gitleaks/gitleaks#installing)
before pushing; missing Gitleaks blocks the push. The `secret-scan` workflow
runs the pinned scanner on pull requests, pushes, and weekly against full
history.
Implementation, workflow, and command changes need a relevant Markdown update;
source additions/edits require related test additions/updates, and source
removals require obsolete tests to be updated or removed. Test-only changes
also require a Markdown update. For documented exceptions, use
`Docs-Not-Required: <reason>` and/or `Tests-Not-Required: <reason>` in the PR
description, or set `DOC_SYNC_BYPASS_REASON` and/or `TEST_SYNC_BYPASS_REASON`
locally. CI runs both checks on pushes and pull requests; the hook is local
feedback, not a substitute for CI. Test deletions without a related source
change are blocked so feature coverage is not removed by itself.

`.github/workflows/release-please.yml` manages separate releases for the
`general` and `colete-online` plugins. Use Conventional Commits for plugin
changes (`feat(scope):` for new behavior, `fix(scope):` for corrections,
`perf(scope):` for meaningful performance changes); scopes should identify the
plugin or skill. Release Please opens a version/changelog PR, and merging that
PR creates the plugin's versioned GitHub Release. Current package versions in
`.release-please-manifest.json` are the baseline; after the history consolidation,
new Conventional Commits determine future version bumps. Repository
administrators must allow GitHub Actions to create pull requests for the
workflow's `GITHUB_TOKEN`. The Release Please workflow dispatches full validation
for its generated PR because `GITHUB_TOKEN`-created PR events may await approval.
The `validate` workflow's merge job runs only on that dispatched branch after the
full validation job succeeds, verifies the bot author and exact current PR head
SHA, then squash-merges that commit. A stale result or another branch cannot
merge a newer PR head.
