#!/bin/bash
# List all guide and bookmark slugs in index.html
FILE="${1:-/home/mmswflow/Documents/work/studying/index.html}"

echo "=== Guide slugs ==="
grep -o 'data-guide-id="[^"]*"' "$FILE" | sed 's/data-guide-id="\([^"]*\)"/\1/' | sort

echo ""
echo "=== Bookmark slugs ==="
grep -o 'data-bookmark-id="[^"]*"' "$FILE" | sed 's/data-bookmark-id="\([^"]*\)"/\1/' | sort
