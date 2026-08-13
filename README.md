# my-agent-skills

Personal AI agent skill library for Claude Code, Gemini CLI, GitHub Copilot CLI, and other agents that support a skills/plugin system.

Each folder is a self-contained skill with a `SKILL.md` file that tells the agent what to do and how.

---

## Install

Requires [GitHub CLI](https://cli.github.com/) authenticated with your account.

```bash
gh repo clone mariosakka/my-agent-skills /tmp/mas && bash /tmp/mas/install.sh
```

This will:
1. Clone the repo to `~/.my-agent-skills/`
2. Symlink each skill folder into the skills directory for every configured platform:
   - Claude Code → `~/.claude/skills/`
   - Gemini CLI → `~/.gemini/skills/`
   - GitHub Copilot CLI → `~/.config/gh-copilot/skills/`

**To update** (pull latest skills and re-link):
```bash
bash ~/.my-agent-skills/install.sh
```

**To skip a platform:**
```bash
SKIP_PLATFORMS="gemini copilot" bash ~/.my-agent-skills/install.sh
```

---

## Skills

| Skill | Description |
|-------|-------------|
| [`homepage`](homepage/SKILL.md) | Manages the personal study hub (`index.html`) — add/remove guides and bookmarks |
| [`humanizer`](humanizer/SKILL.md) | Removes AI-writing patterns from text to make it sound natural |
| [`issue-audit`](issue-audit/SKILL.md) | Fetches approved+unassigned issues (script) and validates each for staleness/overlap (agent) |
| [`pr-audit`](pr-audit/SKILL.md) | Fetches Mario's in-flight PRs (assigned/backing-issue) and PRs he owes a review on, with draft/review-history status |
| [`slack-work-communication`](slack-work-communication/SKILL.md) | Sends structured Slack status messages for work events |

---

## How agents use skills

### Claude Code
Skills are auto-discovered from `~/.claude/skills/`. Invoke with the `Skill` tool or by name:
```
/homepage
```

### Gemini CLI
Skills are referenced via `GEMINI.md`. Invoke with the `activate_skill` tool.

### GitHub Copilot CLI
Skills are auto-discovered from installed plugins. Invoke with the `skill` tool.

### Other agents
Point the agent at the relevant `SKILL.md` file and instruct it to follow the steps using its native file-editing tools.

---

## Add a new skill

1. Create a folder in the repo root: `my-skill/`
2. Add a `SKILL.md` inside it describing what the agent should do
3. Commit and push
4. Re-run `bash ~/.my-agent-skills/install.sh` — it will pick up the new skill automatically

```
my-agent-skills/
├── my-skill/
│   └── SKILL.md        ← required; marks this folder as a skill
├── install.sh
└── README.md
```

---

## Add a new platform

Edit the `PLATFORMS` array near the top of `install.sh`:

```bash
PLATFORMS=(
  "claude:${HOME}/.claude/skills"
  "gemini:${HOME}/.gemini/skills"
  "copilot:${HOME}/.config/gh-copilot/skills"
  "myplatform:${HOME}/.myplatform/skills"   # ← add here
)
```
