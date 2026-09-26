#!/usr/bin/env bash
# Drift + lint checks for the multi-agent marketplace. Requires bash + jq.
# Prints one line per failure; exits non-zero if any.
set -u
cd "$(dirname "$0")/.." || exit 2

command -v jq >/dev/null 2>&1 || { echo "FAIL: jq is required"; exit 2; }

fails=0
fail() { echo "FAIL: $*"; fails=$((fails + 1)); }

CLAUDE_MKT=.claude-plugin/marketplace.json
AGENTS_MKT=.agents/plugins/marketplace.json
MUSE_MKT=.muse-plugin/marketplace.json  # optional; checked only if present
MANIFESTS=(.claude-plugin/plugin.json .codex-plugin/plugin.json .muse-plugin/plugin.json)

# jq wrapper tolerant of CRLF in files
jqr() { tr -d '\r' < "$1" | jq -r "${@:2}" 2>/dev/null | tr -d '\r'; }

# --- JSON validity ---------------------------------------------------------
json_files=("$CLAUDE_MKT" "$AGENTS_MKT")
[ -f "$MUSE_MKT" ] && json_files+=("$MUSE_MKT")
for p in plugins/*/; do
  p=${p%/}
  for m in "${MANIFESTS[@]}"; do json_files+=("$p/$m"); done
done
valid_json=()
for f in "${json_files[@]}"; do
  if [ ! -f "$f" ]; then fail "$f: missing"; continue; fi
  if tr -d '\r' < "$f" | jq -e . >/dev/null 2>&1; then valid_json+=("$f"); else fail "$f: invalid JSON"; fi
done
is_valid() { local f; for f in "${valid_json[@]}"; do [ "$f" = "$1" ] && return 0; done; return 1; }

# --- Skill lint (frontmatter) ----------------------------------------------
# Prints "name<TAB>desc_nonempty(0/1)" for a SKILL.md, CRLF- and >-/| safe.
FM_AWK='
  NR==1 { if ($0 != "---") { exit } ; infm=1; next }
  infm && $0 == "---" { exit }
  /^name:/ { v=$0; sub(/^name:[ \t]*/, "", v); sub(/[ \t]+$/, "", v); gsub(/^["\047]|["\047]$/, "", v); name=v; indesc=0; next }
  /^description:/ {
    v=$0; sub(/^description:[ \t]*/, "", v); sub(/[ \t]+$/, "", v)
    indesc=1
    if (v !~ /^[>|][-+]?[0-9]*$/ && v != "" && v != "\"\"" && v != "\047\047") has=1
    next
  }
  /^[^ \t]/ { indesc=0; next }
  indesc && $0 ~ /[^ \t]/ { has=1 }
  END { printf "%s\t%d\n", name, has+0 }
'
parse_frontmatter() {
  if [ "$(head -n1 "$1" | tr -d '\r\357\273\277')" != "---" ]; then return; fi
  tr -d '\r' < "$1" | awk "$FM_AWK"
}

skills=()   # entries: plugin/skill
for skill_md in plugins/*/skills/*/SKILL.md; do
  [ -f "$skill_md" ] || continue
  dir=$(dirname "$skill_md"); folder=$(basename "$dir")
  plugin=$(basename "$(dirname "$(dirname "$dir")")")
  skills+=("$plugin/$folder")
  out=$(parse_frontmatter "$skill_md")
  if [ -z "$out" ]; then fail "$skill_md: missing or malformed frontmatter"; continue; fi
  fname=${out%%$'\t'*}; hasdesc=${out##*$'\t'}
  [ "$fname" = "$folder" ] || fail "$skill_md: frontmatter name '$fname' != folder '$folder'"
  [ "$hasdesc" = "1" ] || fail "$skill_md: description missing or empty"
done
[ ${#skills[@]} -gt 0 ] || fail "no skills found at plugins/*/skills/*/SKILL.md"

# --- Each skill in exactly one plugin --------------------------------------
dups=$(for s in "${skills[@]}"; do echo "${s#*/}"; done | sort | uniq -d)
for d in $dups; do fail "skill '$d' exists in more than one plugin"; done
for d in plugins/*/skills/*/; do
  [ -f "${d}SKILL.md" ] || fail "${d}SKILL.md: missing"
done

# --- Plugin names/versions across manifests --------------------------------
plugin_names=()
for p in plugins/*/; do
  p=${p%/}; dirname_=$(basename "$p")
  plugin_names+=("$dirname_")
  ref_ver=""; ref_src=""
  for m in "${MANIFESTS[@]}"; do
    f="$p/$m"; is_valid "$f" || continue
    n=$(jqr "$f" '.name // empty'); v=$(jqr "$f" '.version // empty')
    [ -n "$n" ] || fail "$f: missing name"
    [ -n "$v" ] || fail "$f: missing version"
    [ "$n" = "$dirname_" ] || fail "$f: name '$n' != directory '$dirname_'"
    if [ -z "$ref_src" ]; then ref_src=$f; ref_ver=$v
    elif [ "$v" != "$ref_ver" ]; then fail "$f: version '$v' != '$ref_ver' in $ref_src"; fi
  done
done

# --- Marketplaces ----------------------------------------------------------
check_src() { # file plugin-name src
  local f=$1 n=$2 s=$3
  case "$s" in ./*) ;; *) fail "$f: source '$s' for '$n' must start with ./"; return;; esac
  case "/$s/" in */../*) fail "$f: source '$s' for '$n' contains .."; return;; esac
  [ -d "$s" ] || fail "$f: source path '$s' for '$n' does not exist"
}
check_marketplace() {
  local f=$1 names n s pn
  is_valid "$f" || return
  names=$(jqr "$f" '.plugins[]?.name')
  while IFS=$'\t' read -r n s; do
    [ -n "$n" ] || continue
    check_src "$f" "$n" "$s"
    [ -d "plugins/$n" ] || fail "$f: plugin '$n' has no plugins/$n directory"
  done < <(jqr "$f" '.plugins[]? | [.name, (.source | if type=="string" then . else (.path // "") end)] | @tsv')
  for pn in "${plugin_names[@]}"; do
    grep -qxF "$pn" <<<"$names" || fail "$f: plugin '$pn' not listed"
  done
}
if is_valid "$CLAUDE_MKT"; then
  [ -n "$(jqr "$CLAUDE_MKT" '.name // empty')" ] || fail "$CLAUDE_MKT: missing name"
fi
check_marketplace "$CLAUDE_MKT"
check_marketplace "$AGENTS_MKT"
[ -f "$MUSE_MKT" ] && check_marketplace "$MUSE_MKT"

# --- Shell scripts must be LF-only ------------------------------------------
while IFS= read -r sh; do
  if [ "$(tr -cd '\015' < "$sh" | wc -c)" -gt 0 ]; then fail "$sh: contains CRLF line endings"; fi
done < <(find . -name '*.sh' -not -path './.git/*' -not -path './node_modules/*')

if [ "$fails" -gt 0 ]; then echo "validate.sh: $fails failure(s)"; exit 1; fi
echo "validate.sh: OK (${#skills[@]} skills, ${#plugin_names[@]} plugins)"
