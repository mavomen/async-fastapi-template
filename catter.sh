#!/usr/bin/env bash

OUTFILE="project_bundle.txt"
ROOT="$(pwd)"

rm -f "$OUTFILE"

find "$ROOT" \
  -type d \( -name ".git" -o -name "alembic" -o -name "docs" \) -prune -o \
  -type f -name "*.py" -print | sort | while read -r file; do
    echo "===== FILE: $file =====" >> "$OUTFILE"
    cat "$file" >> "$OUTFILE"
    echo -e "\n" >> "$OUTFILE"
done

echo "Python bundle created at $OUTFILE"
