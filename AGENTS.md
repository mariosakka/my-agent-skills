# my-agent-skills

Plugin marketplace of agent skills. One plugin (`general`) under `plugins/general/`; each skill is a folder with a `SKILL.md`. See [README.md](README.md) for install steps.

## Rules
- MUST use Conventional Commits (`feat(scope):`, `fix(scope):`); release-please builds releases from them.
- MUST add or update tests when changing skill scripts; skill tests live in each skill's `tests/` folder.
- MUST keep `AGENTS.md` and `CLAUDE.md` at the repo root consistent (see the repo-foundations skill).
- MUST NOT commit secrets; secret scanning runs in CI.

## Commands
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Run tests: `python -m pytest -q`
- Audit this repo: `python plugins/general/skills/repo-foundations/scripts/foundations_audit.py .`
- Check instruction files: `python plugins/general/skills/repo-foundations/scripts/check_agent_instructions.py .`
