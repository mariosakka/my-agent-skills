# Agent Instruction Files

Every repository has **both** a root `AGENTS.md` and a root `CLAUDE.md`. Codex,
Copilot CLI, Gemini CLI and similar tools read `AGENTS.md`; Claude Code reads
`CLAUDE.md`. A repo with only one of them silently gives the other tools no
instructions.

- `AGENTS.md` is the canonical, tool-neutral entrypoint. It must stand alone:
  no tool is guaranteed to read `CLAUDE.md`.
- `CLAUDE.md` holds only Claude-specific differences plus a pointer to
  `AGENTS.md`. Claude Code supports `@path` imports, so `CLAUDE.md` may begin
  with `@AGENTS.md` instead of copying rules; do not assume other tools support
  imports, and never make `AGENTS.md` depend on one.
- Create the missing file whenever you create or change either one. Keep the
  two consistent: a rule lives in one place, not in both.

Treat both files as concise entrypoints, not full engineering manuals. Keep each
file at or below 300 lines; aim well below the ceiling.

- Group guidance by a few stable categories, such as workflow, quality gates,
  architecture, and safety. Put mandatory, recommended, and conditional rules
  in distinguishable language.
- Keep only cross-task rules, essential commands, navigation, and local scope
  guidance in the instruction file. Link detailed standards, rationale,
  inventories, and feature-specific procedures from canonical docs.
- Remove repeated rules and conflicting copies across `AGENTS.md`, `CLAUDE.md`,
  and nested instruction files. Keep tool-specific differences only where the
  tools actually behave differently; do not assume one tool supports another's
  include/import mechanism.
- Use nested instruction files only for genuinely local rules. Check how each
  supported agent discovers and prioritizes them, and avoid restating root
  instructions unless an explicit override is needed.
- Keep commands and file links current. When a command or policy changes, update
  its canonical documentation and the concise instruction link, not several
  copied explanations.

When editing these files, check line counts, duplicate/conflicting rules,
commands against the actual scripts, and local inline Markdown links against
the repository. Use a deterministic checker for the line ceiling and local links; this skill provides
`scripts/check_agent_instructions.py`. Run it in CI and pre-push. Do not delete
important policy to meet the limit: group, deduplicate, abstract, and move detail
to linked documentation.
