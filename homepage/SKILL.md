# Homepage Skill

> **Agent-agnostic.** Instructions below use plain English for file operations. See the [Platform Notes](#platform-notes) section at the bottom for the exact tool names per agent.

Manages the personal study hub at `/home/mmswflow/Documents/work/studying/index.html`.

## Context

The homepage is a single HTML file that centralises all local guides and external bookmarks. It shares `ddd-guide.css` (same directory) for all styling. Two sections are managed:

- **Guides** — cards linking to local `.html` guide files, inside `<div id="guides-grid">`
- **Bookmarks** — cards linking to external URLs, inside `<div id="bookmarks-grid">`

Always **read the file first** before any edit.

---

## Scripts

Run these when adding or removing cards to catch structural regressions immediately.

| Script | When to run | What it does |
|---|---|---|
| `scripts/list-cards.sh` | Before adding a card | Prints all existing guide and bookmark slugs so you don't collide |
| `scripts/validate.sh` | After any edit | Confirms `#guides-grid` / `#bookmarks-grid` exist, no duplicate slugs, no absolute hrefs |

```bash
# Check existing slugs
~/.my-agent-skills/homepage/scripts/list-cards.sh

# Validate after edit
~/.my-agent-skills/homepage/scripts/validate.sh
```

---

## Card Templates

### Guide card

```html
<a class="hub-card guide-card" href="RELATIVE_FILENAME.html" data-guide-id="kebab-slug">
  <div class="hc-eyebrow">CATEGORY</div>
  <h3>TITLE</h3>
  <p>DESCRIPTION</p>
  <!-- optional: sub-links for multi-part guides -->
  <div class="hc-sub-links">
    <a href="part-file.html" class="hc-part-link" onclick="event.stopPropagation()">Part label</a>
  </div>
  <div class="hc-arrow">→</div>
</a>
```

### Bookmark card

```html
<a class="hub-card bookmark-card" href="https://FULL_URL" target="_blank" rel="noopener" data-bookmark-id="kebab-slug">
  <div class="bm-icon">EMOJI</div>
  <div class="bm-body">
    <div class="bm-title">TITLE</div>
    <div class="bm-desc">SHORT DESCRIPTION</div>
  </div>
  <div class="bm-arrow">↗</div>
</a>
```

---

## Operations

### Add a guide

1. Read `/home/mmswflow/Documents/work/studying/index.html`.
2. Choose a unique `data-guide-id` slug in `kebab-case` derived from the title.
3. Use `href` as a bare filename (e.g. `my-guide.html`) — never an absolute path.
4. Insert the new guide card as the last child inside `<div id="guides-grid">`.
5. If the guide has multiple parts, add `<a class="hc-part-link" onclick="event.stopPropagation()">` links inside a `<div class="hc-sub-links">` block within the card.

### Remove a guide

1. Read the file.
2. Locate the `<a data-guide-id="SLUG">` block.
3. Delete the entire `<a>…</a>` element (including all nested content).

### Add a bookmark

1. Read the file.
2. Choose a unique `data-bookmark-id` slug in `kebab-case`.
3. Always include `target="_blank" rel="noopener"` — all bookmarks are external.
4. Choose an emoji icon that represents the service (e.g. `⚙` GitHub, `💬` Slack, `📄` docs, `🔗` generic link).
5. Insert the new bookmark card as the last child inside `<div id="bookmarks-grid">`.

### Remove a bookmark

1. Read the file.
2. Locate the `<a data-bookmark-id="SLUG">` block.
3. Delete the entire `<a>…</a>` element.

### Edit a guide or bookmark

1. Read the file.
2. Locate the element by `data-guide-id` or `data-bookmark-id`.
3. Edit only the specific field the user asked to change (title, description, href, icon, etc.).

---

## Design Rules (always enforce)

- **Never add inline styles** to cards — only use classes from `ddd-guide.css` and the page-local `<style>` block.
- The theme toggle must always be present: `<button id="theme-toggle" onclick="toggleTheme()">`.
- `localStorage` key for theme persistence is `ddd-theme` (values: `"light"` / `"dark"`).
- Bookmark icons must be emoji — no external image URLs.
- Sub-links inside guide cards must be `<a>` tags (not buttons) with `onclick="event.stopPropagation()"` so they navigate independently without triggering the parent card.
- `href` in guide cards: relative filename only (e.g. `my-guide.html`), not `/home/…` or `file://…`.

---

## File Location Conventions

| Item | Location |
|------|----------|
| Homepage | `/home/mmswflow/Documents/work/studying/index.html` |
| Shared CSS | `/home/mmswflow/Documents/work/studying/ddd-guide.css` |
| All guide files | `/home/mmswflow/Documents/work/studying/*.html` |
| Guide `href` in cards | bare filename, e.g. `angular-client-guide.html` |

---

## Platform Notes

The operations in this skill use three abstract file actions. Map them to your platform's tools:

| Action | Claude Code | Gemini CLI | GitHub Copilot CLI | Codex (OpenAI) |
|--------|-------------|------------|--------------------|----------------|
| Read file contents | `Read` tool | built-in file read | `read_file` tool | built-in read |
| Edit specific text in file | `Edit` tool | built-in edit | `edit_file` tool | built-in edit |
| Write new file from scratch | `Write` tool | built-in write | `write_file` tool | built-in write |

**Skill discovery per platform:**
- **Claude Code** — place this folder in `~/.claude/skills/homepage/` or `.claude/skills/homepage/` (project-level); invoke via the `Skill` tool
- **Gemini CLI** — referenced via `GEMINI.md`; invoked via the `activate_skill` tool
- **GitHub Copilot CLI** — auto-discovered from installed plugins; invoked via the `skill` tool
- **Other agents** — point the agent at this `SKILL.md` file and instruct it to follow the steps using its native file-editing capabilities
