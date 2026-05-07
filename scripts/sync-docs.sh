#!/usr/bin/env bash
# sync-docs.sh — copy docs/*.md from the Tolstoy repo into src/content/docs/
# Strips frontmatter during copy so Astro never sees malformed YAML.
# Run from splash/tl/ or via: npm run sync-docs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve docs/ relative to this script: splash/tl/ → splash/ → Tolstoy/
DOCS_SRC="$(dirname "$(dirname "$SITE_DIR")")/docs"
DOCS_DEST="$SITE_DIR/src/content/docs"

if [ ! -d "$DOCS_SRC" ]; then
  echo "Error: docs/ source not found at $DOCS_SRC" >&2
  exit 1
fi

echo "Syncing $DOCS_SRC → $DOCS_DEST"

python3 "$SCRIPT_DIR/strip-frontmatter.py" "$DOCS_SRC" "$DOCS_DEST"

echo "Done."
