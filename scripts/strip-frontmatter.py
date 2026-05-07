#!/usr/bin/env python3
"""
strip-frontmatter.py <src_dir> <dest_dir>

For .md files:
  Copies all .md files from src_dir to dest_dir, stripping YAML frontmatter.
  Preserves the section subdirectory structure. Removes stale files from dest_dir.

For .html files that have NO matching .md counterpart:
  Copies them to <project_root>/public/docs/.

For INDEX.html:
  Rewrites internal hrefs to the Astro URL structure and copies to
  public/docs/index.html (served at /docs/).
"""

import os
import sys
import re
import json


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Files excluded from both the content collection and the index listing.
EXCLUDED_FILENAMES = {"README.md", "README.html"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_frontmatter(content: str) -> str:
    """Remove the leading ---...--- block if present."""
    if content.startswith("---"):
        rest = content[3:]
        end = rest.find("\n---")
        if end != -1:
            return rest[end + 4:].lstrip("\n")
    return content


def write_if_changed(path: str, content: str) -> bool:
    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
    if content != existing:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    return False


def remove_excluded_cards(content: str) -> str:
    """Remove index-card <a> blocks that link to excluded files."""
    for name in EXCLUDED_FILENAMES:
        slug = os.path.splitext(name)[0]  # e.g. README
        # Match an <a class="index-card" href="...README...">...</a> block
        pattern = rf'<a\s+class="index-card"\s+href="[^"]*{re.escape(slug)}[^"]*".*?</a>'
        content = re.sub(pattern, "", content, flags=re.DOTALL)
    return content


def rewrite_hrefs(content: str, md_files: set, current_rel: str = "") -> str:
    """
    Rewrite hrefs for the Astro site URL structure.

    current_rel: path of the file being rewritten, relative to src_dir
                 (e.g. "architecture/architecture-review.html").
                 Used to resolve relative hrefs. Empty for INDEX.html.

    Rules:
      /INDEX.html              → /docs/
      /section/file.html       → /docs/section/file   (if .md counterpart exists)
      /section/file.html       → /docs/section/file.html  (HTML-only)
      ../section/file.html     → resolved relative, then same logic as above
      ./file.html  file.html   → same as above
    """
    current_dir = os.path.dirname(current_rel)  # e.g. "architecture" or ""

    def rewrite(m):
        href = m.group(1)

        # Skip anchors, mailto, external URLs, and empty hrefs
        if not href or href.startswith("#") or "://" in href or href.startswith("mailto:"):
            return m.group(0)

        if href == "/INDEX.html":
            return 'href="/docs/"'

        # Absolute path starting with /
        if href.startswith("/") and href.endswith(".html"):
            rel_html = href[1:]  # strip leading /
            rel_md   = rel_html[:-5] + ".md"
            if rel_md in md_files:
                return f'href="/docs/{rel_html[:-5]}"'
            else:
                return f'href="/docs/{rel_html}"'

        # Relative path ending in .html
        if href.endswith(".html") and not href.startswith("/"):
            # Resolve relative to current file's directory
            resolved = os.path.normpath(os.path.join(current_dir, href)) if current_dir else href
            resolved = resolved.replace("\\", "/")  # normalise on Windows
            rel_md   = resolved[:-5] + ".md"
            if rel_md in md_files:
                # Rewrite to relative path without .html
                target_dir = os.path.dirname(resolved)
                target_base = os.path.basename(resolved)[:-5]
                if target_dir == current_dir:
                    new_href = target_base
                else:
                    rel_to_current = os.path.relpath(
                        os.path.join(target_dir, target_base),
                        current_dir if current_dir else "."
                    ).replace("\\", "/")
                    new_href = rel_to_current
                return f'href="{new_href}"'
            # HTML-only: leave relative path as-is (both files in public/docs/)

        return m.group(0)

    return re.sub(r'href="([^"]*)"', rewrite, content)


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

def sync(src_dir: str, dest_dir: str) -> None:
    src_dir  = os.path.abspath(src_dir)
    dest_dir = os.path.abspath(dest_dir)

    # Project root: three levels up from dest_dir (src/content/docs)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(dest_dir)))
    public_docs  = os.path.join(project_root, "public", "docs")

    # ------------------------------------------------------------------
    # Pass 1: .md files → src/content/docs/
    # ------------------------------------------------------------------

    src_md: set = set()
    for dirpath, _, filenames in os.walk(src_dir):
        for filename in filenames:
            if filename.endswith(".md") and filename not in EXCLUDED_FILENAMES:
                rel = os.path.relpath(os.path.join(dirpath, filename), src_dir)
                src_md.add(rel)

    for rel in sorted(src_md):
        src_path  = os.path.join(src_dir, rel)
        dest_path = os.path.join(dest_dir, rel)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = strip_frontmatter(content)
        changed = write_if_changed(dest_path, content)
        print(f"  {'updated' if changed else 'unchanged'} {rel}")

    # Remove stale .md files from dest
    for dirpath, _, filenames in os.walk(dest_dir, topdown=False):
        for filename in filenames:
            if filename.endswith(".md"):
                rel = os.path.relpath(os.path.join(dirpath, filename), dest_dir)
                if rel not in src_md:
                    os.remove(os.path.join(dest_dir, rel))
                    print(f"  removed {rel}")
        try:
            os.rmdir(dirpath)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Pass 2: HTML files → public/docs/
    # ------------------------------------------------------------------

    # INDEX.html → src/data/docs-index.html (read by index.astro at build time)
    data_dir   = os.path.join(project_root, "src", "data")
    index_dest = os.path.join(data_dir, "docs-index.html")

    index_src = os.path.join(src_dir, "INDEX.html")
    if os.path.exists(index_src):
        with open(index_src, "r", encoding="utf-8") as f:
            content = f.read()
        content = remove_excluded_cards(content)
        content = rewrite_hrefs(content, src_md)
        changed = write_if_changed(index_dest, content)
        print(f"  {'updated' if changed else 'unchanged'} (index) INDEX.html → src/data/docs-index.html")

    # Other HTML files: only copy if no .md counterpart
    for dirpath, _, filenames in os.walk(src_dir):
        for filename in filenames:
            if not filename.endswith(".html"):
                continue

            html_path = os.path.join(dirpath, filename)
            rel_html  = os.path.relpath(html_path, src_dir)

            if rel_html == "INDEX.html":
                continue  # handled above

            rel_md = rel_html[:-5] + ".md"
            if rel_md in src_md:
                continue  # .md version takes precedence

            dest_path = os.path.join(public_docs, rel_html)
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = rewrite_hrefs(content, src_md, current_rel=rel_html)
            changed = write_if_changed(dest_path, content)
            print(f"  {'updated' if changed else 'unchanged'} (html) {rel_html}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <src_dir> <dest_dir>", file=sys.stderr)
        sys.exit(1)
    sync(sys.argv[1], sys.argv[2])
