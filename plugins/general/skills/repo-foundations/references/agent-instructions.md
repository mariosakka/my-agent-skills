# Agent Instruction Files

Treat `AGENTS.md` and `CLAUDE.md` as concise entrypoints, not full engineering
manuals. Keep each file at or below 300 lines; aim well below the ceiling.

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
