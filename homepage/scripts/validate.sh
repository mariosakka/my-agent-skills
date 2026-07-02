#!/bin/bash
# Validate index.html structural integrity after any edit
FILE="${1:-/home/mmswflow/Documents/work/studying/index.html}"
PASS=true

echo "=== Validating $FILE ==="
echo ""

# Required container elements
for ID in "guides-grid" "bookmarks-grid"; do
  if grep -q "id=\"$ID\"" "$FILE"; then
    echo "✓ #$ID present"
  else
    echo "✗ #$ID MISSING"
    PASS=false
  fi
done

# Duplicate guide slugs
echo ""
GUIDE_IDS=$(grep -o 'data-guide-id="[^"]*"' "$FILE" | sed 's/data-guide-id="\([^"]*\)"/\1/')
DUPES=$(echo "$GUIDE_IDS" | sort | uniq -d)
if [ -n "$DUPES" ]; then
  echo "✗ Duplicate guide slugs:"
  echo "$DUPES"
  PASS=false
else
  COUNT=$(echo "$GUIDE_IDS" | grep -c . || true)
  echo "✓ $COUNT guide slugs, no duplicates"
fi

# Duplicate bookmark slugs
BOOKMARK_IDS=$(grep -o 'data-bookmark-id="[^"]*"' "$FILE" | sed 's/data-bookmark-id="\([^"]*\)"/\1/')
DUPES_B=$(echo "$BOOKMARK_IDS" | sort | uniq -d)
if [ -n "$DUPES_B" ]; then
  echo "✗ Duplicate bookmark slugs:"
  echo "$DUPES_B"
  PASS=false
else
  COUNT_B=$(echo "$BOOKMARK_IDS" | grep -c . || true)
  echo "✓ $COUNT_B bookmark slugs, no duplicates"
fi

# No absolute href paths (should be relative)
ABS=$(grep -n 'href="/' "$FILE" | grep -v '<!-' || true)
if [ -n "$ABS" ]; then
  echo ""
  echo "⚠ Absolute href paths found (should be relative):"
  echo "$ABS"
fi

echo ""
if [ "$PASS" = true ]; then
  echo "Validation passed"
else
  echo "Validation FAILED — fix above issues"
  exit 1
fi
