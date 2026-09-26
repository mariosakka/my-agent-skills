#!/bin/bash
# Scan text for AI vocabulary patterns before rewriting
# Usage: ai-scan < input.txt   OR   ai-scan file.txt
FILE="${1:-}"
if [ -n "$FILE" ]; then
  INPUT=$(cat "$FILE")
else
  INPUT=$(cat)
fi

echo "=== AI vocabulary scan ==="
echo ""

TOTAL=0

scan_word() {
  local WORD="$1"
  local COUNT
  COUNT=$(echo "$INPUT" | grep -oi "$WORD" | wc -l | tr -d ' ')
  if [ "$COUNT" -gt 0 ]; then
    printf "  %3d × %s\n" "$COUNT" "$WORD"
    TOTAL=$((TOTAL + COUNT))
  fi
}

# Significance inflation
scan_word "pivotal"
scan_word "crucial"
scan_word "groundbreaking"
scan_word "game-changer"
scan_word "game changer"
scan_word "revolutionary"
scan_word "transformative"

# Vague elevation
scan_word "showcase"
scan_word "showcases"
scan_word "showcasing"
scan_word "delve"
scan_word "delves"
scan_word "delving"
scan_word "realm"
scan_word "tapestry"
scan_word "holistic"

# Corporate filler
scan_word "leverage"
scan_word "leverages"
scan_word "leveraging"
scan_word "utilize"
scan_word "utilizes"
scan_word "utilizing"
scan_word "robust"
scan_word "seamless"
scan_word "seamlessly"
scan_word "streamline"
scan_word "streamlines"
scan_word "cutting-edge"
scan_word "paradigm"
scan_word "synergy"
scan_word "empower"
scan_word "reimagine"
scan_word "diverse range"

# Throat-clearing phrases
scan_word "it's worth noting"
scan_word "it is worth noting"
scan_word "I cannot emphasize enough"
scan_word "in conclusion"
scan_word "in summary"
scan_word "to summarize"
scan_word "at the end of the day"

# Em dashes (common AI tell)
EM_COUNT=$(echo "$INPUT" | grep -o '—' | wc -l | tr -d ' ')
if [ "$EM_COUNT" -gt 0 ]; then
  printf "  %3d × em dash (—) — replace with comma, semicolon, or reword\n" "$EM_COUNT"
  TOTAL=$((TOTAL + EM_COUNT))
fi

# Rule-of-three openers
RULE3=$(echo "$INPUT" | grep -oi '\b\w\+, \w\+, and \w\+' | wc -l | tr -d ' ')
if [ "$RULE3" -gt 0 ]; then
  printf "  %3d × rule-of-three pattern (X, Y, and Z)\n" "$RULE3"
fi

echo ""
echo "Total AI-isms flagged: $TOTAL"
if [ "$TOTAL" -gt 10 ]; then
  echo "High density — rewrite before sending"
elif [ "$TOTAL" -gt 3 ]; then
  echo "Moderate — review flagged phrases"
else
  echo "Low — spot-check em dashes if any"
fi
