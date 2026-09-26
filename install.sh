#!/usr/bin/env bash
#
# ============================================================
# AI Skills Installer
# ============================================================
#
# WHAT THIS SCRIPT DOES:
#   Clones (or updates) a GitHub repo containing AI agent
#   skills into ~/.my-agent-skills/, then symlinks each skill folder
#   into the skills directory for every configured AI platform
#   (Claude Code, Gemini CLI, Copilot CLI, etc.).
#
# HOW TO RUN (private repo — requires gh CLI authenticated):
#   gh repo clone mariosakka/my-agent-skills ~/.my-agent-skills && bash ~/.my-agent-skills/install.sh
#
#   Re-run to update (pulls latest and re-links):
#   bash ~/.my-agent-skills/install.sh
#
#   Custom repo:
#   SKILLS_REPO=git@github.com:you/your-skills.git bash install.sh
#
#   Skip specific platforms:
#   SKIP_PLATFORMS="gemini copilot" bash install.sh
#
# HOW TO ADD A NEW SKILL:
#   1. Pick a plugin group (plugins/colete-online or plugins/general)
#      and create plugins/<group>/skills/<name>/
#   2. Add a SKILL.md file inside it (this marks it as a skill)
#   3. Commit and push to GitHub
#   4. Re-run this script — it pulls the update and symlinks
#      the new skill automatically across all platforms
#
# HOW TO ADD A NEW PLATFORM:
#   Add an entry to the PLATFORMS array below in the form:
#     "name:~/.path/to/platform/skills"
#
# ============================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────
SKILLS_REPO="${SKILLS_REPO:-git@github.com:mariosakka/my-agent-skills.git}"
INSTALL_DIR="${HOME}/.my-agent-skills"

# Platform entries: "label:target_directory"
# Add or remove entries here to control which agents get the skills.
PLATFORMS=(
  "claude:${HOME}/.claude/skills"
  "gemini:${HOME}/.gemini/skills"
  "copilot:${HOME}/.config/gh-copilot/skills"
)

# Platforms to skip (space-separated, can also be set via env)
SKIP_PLATFORMS="${SKIP_PLATFORMS:-}"

# ── Helpers ──────────────────────────────────────────────────
log()  { echo "[skills] $*"; }
ok()   { echo "[skills] ✓ $*"; }
warn() { echo "[skills] ⚠  $*" >&2; }
die()  { echo "[skills] ✗ $*" >&2; exit 1; }

is_skipped() {
  local name="$1"
  for skip in ${SKIP_PLATFORMS}; do
    [ "${skip}" = "${name}" ] && return 0
  done
  return 1
}

# ── 1. Check dependencies ────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  die "git is required but was not found. Install git and try again."
fi

# ── 2. Clone or update the skills repo ──────────────────────
if [ -d "${INSTALL_DIR}/.git" ]; then
  log "Repo already exists at ${INSTALL_DIR} — pulling latest changes..."
  git -C "${INSTALL_DIR}" pull --ff-only \
    || warn "git pull failed (offline or diverged?). Proceeding with existing files."
else
  if [ -e "${INSTALL_DIR}" ]; then
    die "${INSTALL_DIR} exists but is not a git repo. Remove it and try again."
  fi
  log "Cloning ${SKILLS_REPO} into ${INSTALL_DIR}..."
  git clone --depth=1 "${SKILLS_REPO}" "${INSTALL_DIR}"
fi

# ── 3. Collect skill directories from the repo ───────────────
skill_dirs=()
while IFS= read -r -d '' skill_md; do
  skill_dir="$(dirname "${skill_md}")"

  skill_name="$(basename "${skill_dir}")"

  # Skip hidden directories (.git, etc.)
  case "${skill_name}" in
    .*) continue ;;
  esac

  skill_dirs+=("${skill_dir}")
done < <(find "${INSTALL_DIR}/plugins" -mindepth 4 -maxdepth 4 -path "${INSTALL_DIR}/plugins/*/skills/*/SKILL.md" -name "SKILL.md" -print0 | sort -z)

if [ "${#skill_dirs[@]}" -eq 0 ]; then
  warn "No skills found in ${INSTALL_DIR}/plugins. Each skill needs plugins/<group>/skills/<name>/SKILL.md."
  exit 0
fi

# ── 4. Symlink into each platform's skills directory ─────────
echo ""
for platform_entry in "${PLATFORMS[@]}"; do
  platform_name="${platform_entry%%:*}"
  platform_dir="${platform_entry#*:}"
  # Expand ~ manually (not expanded inside strings)
  platform_dir="${platform_dir/#\~/$HOME}"

  if is_skipped "${platform_name}"; then
    log "Skipping platform: ${platform_name}"
    continue
  fi

  linked=()
  mkdir -p "${platform_dir}"

  # Remove stale symlinks (old flat paths, deleted skills): only symlinks
  # that point into INSTALL_DIR and whose target no longer exists.
  for link in "${platform_dir}"/*; do
    [ -L "${link}" ] || continue
    [ -e "${link}" ] && continue
    case "$(readlink "${link}")" in
      "${INSTALL_DIR}"/*) rm -f "${link}"; log "[${platform_name}] Removed stale link: $(basename "${link}")" ;;
    esac
  done

  for skill_dir in "${skill_dirs[@]}"; do
    skill_name="$(basename "${skill_dir}")"
    ln -sfn "${skill_dir}/" "${platform_dir}/${skill_name}"
    linked+=("${skill_name}")
  done

  if [ "${#linked[@]}" -gt 0 ]; then
    ok "[${platform_name}] Linked: $(IFS=', '; echo "${linked[*]}")"
    log "        → ${platform_dir}"
  fi
done

echo ""
log "Done."
