# Multi-agent marketplace design

Date: 2026-09-26
Status: written; implementation started on branch `marketplace-restructure`

## Goal

Turn `mariosakka/my-agent-skills` (private) into an installable plugin marketplace for
Claude Code, and keep it compatible with GitHub Copilot CLI, Codex, Muse Code and
Gemini CLI, with CI that catches drift between the formats.

## Decisions (agreed with the repo owner)

- Two plugins, many skills each (every tool bundles many skills per plugin):
  - `colete-online`: colete-flow, issue-audit, pr-audit, slack-work-communication, eod-weekly-log
  - `general`: pr-inspect-and-act, explain-syntax, humanizer, report-to-pdf
- `homepage` is removed. It is replaced by the Desk VS Code extension
  (`mariosakka/vscode-desk`), and it hardcoded a local path.
- `eod-weekly-log` stays in `colete-online` for now. The owner will check whether
  Desk supersedes it.
- `install.sh` was removed after the initial rollout (see "install.sh removal"). Gemini,
  which has no marketplace, installs skills manually per the README.

## Layout

```
.claude-plugin/marketplace.json          Claude Code + Copilot CLI marketplace
.agents/plugins/marketplace.json         Codex + Muse Code marketplace
.muse-plugin/marketplace.json            Muse Code native marketplace (Claude-shaped)
(no Gemini manifest: see "Corrections" below)
plugins/
  colete-online/
    .claude-plugin/plugin.json
    .codex-plugin/plugin.json
    .muse-plugin/plugin.json
    skills/<skill>/SKILL.md (+ scripts/, config/)
  general/
    (same three manifests)
    skills/<skill>/SKILL.md
scripts/validate.sh                      drift + lint checks (used by CI)
.github/workflows/validate.yml           CI
README.md                                install docs + compatibility table
```

## Tool compatibility matrix

| Tool | Marketplace file | Per-plugin manifest | Marketplace? |
|---|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` | yes |
| Copilot CLI | reads `.github/plugin/marketplace.json` and `.claude-plugin/marketplace.json` | `plugin.json` | yes |
| Codex | `.agents/plugins/marketplace.json` | `.codex-plugin/plugin.json` | yes |
| Muse Code | `.muse-plugin/marketplace.json` (and `.agents/plugins/marketplace.json`) | `.muse-plugin/plugin.json` (`schemaVersion: 1`, explicit `capabilities.skills[{id,path}]`) | yes, experimental (`MUSE_EXPERIMENTAL_PLUGINS=1`) |
| Gemini CLI | none | none | no |

Sources: Claude plugin-marketplaces docs, GitHub Docs (Copilot CLI plugin marketplace),
developers.openai.com/codex/plugins/build, geminicli.com extension docs, third-party
Muse plugin PRs. The Muse manifest shape is NOT confirmed by official docs; mark it
unverified in the README until `muse plugins validate` has been run against it.

## Manifests

- Plugin names are identical in every manifest and marketplace file
  (`colete-online`, `general`). Marketplace name: `mario-agent-skills`.
- Marketplace `source` paths are relative to the repo root and start with `./`
  (`./plugins/colete-online`, `./plugins/general`). No `..`.
- Each plugin manifest carries `name`, `version` (start at `0.1.0`), `description`,
  `author`. Versions are kept in sync across a plugin's manifests.
- Claude marketplace: top-level `name`, `owner`, `plugins[]` (`name`, `source`,
  `description`).
- Codex/Muse marketplace: one entry per plugin with `source.path` (`./`-prefixed) and
  `interface.displayName`.
- Muse marketplace (`.muse-plugin/marketplace.json`): same shape as the Claude
  marketplace file. Muse plugin manifests list skills explicitly.
- Gemini: no manifest (see Corrections).

## Corrections made during implementation

- Gemini has no `skills` field or globs in `gemini-extension.json`; extensions only
  auto-discover a root `skills/` directory. The planned root `gemini-extension.json`
  was dropped. Gemini users install with `gemini skills install <url> --path <dir>`.
- Muse's native marketplace file is `.muse-plugin/marketplace.json` (Claude-shaped),
  as seen in public Muse plugin repos; `.agents/plugins/marketplace.json` is kept too,
  as `obra/superpowers` does. Both are third-party-sourced and unverified.
- `.gitattributes` pins LF on scripts, Markdown, JSON and YAML, because the owner
  develops on Windows and CRLF breaks shell scripts in CI.

## Path-independence fix (found during implementation)

Some skills hardcode install-specific paths that only exist with the symlink install:

- `~/.my-agent-skills/<skill>/...`: slack-work-communication (SKILL.md, config/channels.sh
  comment), eod-weekly-log (SKILL.md), humanizer (SKILL.md)
- `~/.claude/skills/<skill>/...`: pr-inspect-and-act (SKILL.md), report-to-pdf (SKILL.md)

A marketplace install puts files in a plugin cache, so these break. Rewrite them to
refer to the skill's own directory ("the `scripts/` folder next to this SKILL.md, i.e.
the skill's base directory"). Do not change behavior or wording beyond the path.
`humanizer/README.md` and `WARP.md` are upstream install docs; leave them.
Out of scope: eod-weekly-log's dependency on `~/.desk/` symlinks. Flag it, don't
change it.

## install.sh removal

The symlink installer was updated for the new layout in the initial rollout, then
removed. Every tool except Gemini installs from a marketplace, using the script for
Claude alongside the marketplace would duplicate skills, and it does not work well
on Windows (`ln -s` in Git Bash needs Developer Mode or admin rights). Gemini gets
manual per-skill `gemini skills install` commands in the README instead.

## CI (`.github/workflows/validate.yml`)

Triggers: push, pull_request, weekly `schedule`, `workflow_dispatch`. No secrets.

1. Skill lint: each `SKILL.md` has frontmatter `name` equal to its folder name and a
   non-empty `description`.
2. Drift check (`scripts/validate.sh`): every skill is in exactly one plugin; plugin
   names and versions match across all manifests; every marketplace `source` path
   exists; JSON is valid; Muse `capabilities.skills` paths exist; shell scripts have no
   CRLF.
3. `claude plugin validate .` (npm-installed CLI).
4. `muse plugins validate` on each plugin if it can be installed headlessly; otherwise
   skipped with a notice. Codex and Gemini get `jq` schema checks only.
5. Install smoke test: add the marketplace from the checkout to a temporary Claude
   Code home and confirm both plugins install.
6. The weekly schedule opens an issue on failure.

## README

Update install instructions per tool, add the compatibility table above, remove the
`homepage` row, and add the two plugins with their skills.

## Out of scope

Renaming skills, editing skill logic, publishing anywhere public, Muse manifest
verification beyond the validator, and the eod-weekly-log / Desk decision.
