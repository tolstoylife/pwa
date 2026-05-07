# Tolstoy e-reader: tl pipeline integration

The PWA architecture depends on the `tl` build producing a few additional artifacts. This document specifies exactly what those are and how the existing pipeline extends to produce them, so that the web side and the EPUB side stay coherent.

This is a sibling document to `stage-1-implementation.md` and `yjs-schema-and-sync.md` and will be fed into `/ultraplan` alongside them.

## 1. What the pipeline already does

The `tl` CLI already produces publication-quality EPUBs from typogrified, semanticated source XHTML. The ebook-creator skill documents the full lifecycle: create-draft, typogrify, semanticate, build-manifest, build-toc, build-images, lint, build, prepare-release.

The web build — whatever turns the source content into the tolstoy.life site — is the other half of the story. This document focuses on what needs to come out of the web build (or a closely related build step) for the PWA to do its job.

For clarity: this document is not proposing changes to the EPUB pipeline. The EPUB side is already working and stable. It's proposing additions to the web build.

## 2. Five new artefacts

The PWA architecture needs five things from the build output that don't exist today:

1. **A content-addressed versioning scheme** applied to works and chapters, surfaced in URIs and identifiers.
2. **An asset manifest** per work listing every URL and hash needed for offline reading.
3. **A `relatedWiki` list** per work — the slugs of every wiki article referenced from any chapter of the work. Used by the download coordinator to populate the shared wiki cache. See `wiki-integration.md` §2.
4. **A wiki-previews bundle** (`wiki-previews-v<YYYY-MM-DD>-<hash6>.json`) containing summary stubs for every wiki article in the vault. Hashed URL, immutable per build. See `wiki-integration.md` §3.
5. **A works index** listing every published work with metadata, including a pointer to the current wiki-previews bundle URL, for library and discovery UIs.

None of these require changing the content itself. They're metadata and summaries, derived from the build.

### 2.1 Where these artefacts come from

The web build is part of the Layer-1 scripted pipeline (CLAUDE.md, scaled architecture model). The asset manifest, `relatedWiki` list, wiki-previews bundle, and works index are emitted by Layer-1 generators that run after Eleventy renders the site. Two new Python scripts live alongside the existing `extract-graph.py` / `extract-frontmatter.py` family:

- `generate-wiki-previews.py` — walks `website/src/wiki/` and emits the wiki-previews bundle as a hashed JSON file written into the build output. See `wiki-integration.md` §3.
- `generate-related-wiki.py` — for each work, parses every chapter file in its `text/` subfolder for `[[wikilinks]]`, resolves them to wiki article slugs, and emits the resolved set as the work's `relatedWiki` list, written into the work's manifest.json.

The asset manifest and works-index generators are existing-or-new build scripts in the same family; they consume the outputs of the two scripts above.

## 3. Content-addressed versioning

### 3.1 Why it matters

Annotations in later stages will anchor to specific versions of works. If the URL `/war-and-peace/chapter-3/` means different content on Monday and Tuesday, every annotation anchored to "chapter 3" becomes potentially ambiguous. Content-addressing resolves this: each version of a work is identified by a stable hash, and the URL or URI includes that hash.

### 3.2 The versioning scheme

Two identifiers per work, both produced by the build:

**Work URI (stable across versions).**

```
urn:tolstoy-life:war-and-peace
```

This is the canonical identifier for "War and Peace as a work." It never changes.

**Work version identifier.**

```
v2026-03-01-a3f5c8
```

A deterministic, human-readable version tag composed of two parts joined by a hyphen:

- The date of the first commit that produced this content hash, in `YYYY-MM-DD` form. This is the *content's own* canonical date, not the build date — re-running the build on a later day does not advance it.
- A short (6 hex characters) prefix of the SHA-256 content hash of the work's post-Eleventy rendered artefacts (chapters, CSS, images, TOC). Computed over the sorted set of file hashes so ordering is deterministic.

The hash input is **rendered content files only**. Generated metadata files (`manifest.json`, `_related-wiki.json`) and fields that reference *other* build artefacts (e.g. cross-references to the wiki-previews bundle) are explicitly excluded. See §4.6 for the full isolation rule and why it matters.

Two different builds of the same source content produce the same version; a change anywhere in the work's rendered output produces a new version. This means the version is a pure function of the work's *own* content — no build-time randomness, no system-clock drift, and no cascade from unrelated parts of the site (a wiki edit, for example, must not re-version an untouched work).

The hash is computed over **post-Eleventy** artefacts rather than source markdown, because the PWA downloads and caches post-Eleventy HTML; hashing the source would let non-rendering changes (e.g., a schema-only field tweak) change the version without changing what the client actually stores, and vice versa.

Together, a specific version of a work is:

```
urn:tolstoy-life:war-and-peace#v2026-03-01-a3f5c8
```

### 3.3 Where versions live

- In the work's HTML `<head>` as a `<meta name="tl:version" content="v2026-03-01-a3f5c8">`.
- In the asset manifest (see below).
- In the works index.
- In the URL structure, *optionally* — for readers who want to link to a specific version, a URL pattern like `/war-and-peace/v2026-03-01-a3f5c8/book-1-chapter-3/` should resolve to the specific historical version. The canonical URL `/war-and-peace/book-1-chapter-3/` always points to the latest version.

### 3.4 Keeping old versions accessible

Old versions should remain accessible for some retention period. This is what lets annotations anchored to `v2025-11-15-9b2c11` still find their content after `v2026-03-01-a3f5c8` ships.

**Decision: serve current + the two most recent prior versions** at versioned URLs (`/war-and-peace/v2026-03-01-a3f5c8/...`). Older versions live in git history only — they can always be reconstructed by checking out the relevant commit and re-running the build, but they are not served from the live site.

Rationale:

- Three concurrent versions covers ordinary update churn (most readers will be on current; some on the previous; rare stragglers on the one before that).
- Anyone with an annotation pointing at a version older than the live retention can still recover the content via git, and the project can offer a recovery tool if it ever becomes a real user need.
- Served-version retention is bounded — the build always emits at most three versions per work, regardless of corpus age.
- Git is the source of truth for everything older.

Implementation: the build script reads the previous build's `works.json` to discover the prior version slugs, and emits versioned subtrees for current + prior + prior-prior. Versions older than that are pruned from the build output (but remain in git).

## 4. The asset manifest

### 4.1 Purpose

The download coordinator in the PWA needs to know, given a work URI, exactly what URLs to fetch for complete offline availability. It also needs to verify integrity after download. The asset manifest provides both.

### 4.2 Shape

One JSON document per work-version, served at a predictable URL:

```
https://tolstoy.life/war-and-peace/v2026-03-01-a3f5c8/manifest.json
```

Or, for the current version:

```
https://tolstoy.life/war-and-peace/manifest.json
```

Both should exist: the versioned URL is stable, the unversioned URL points to the current version.

### 4.3 Schema

```json
{
  "manifestFormat": "v1",
  "workUri": "urn:tolstoy-life:war-and-peace",
  "version": "v2026-03-01-a3f5c8",
  "title": "War and Peace",
  "author": "Leo Tolstoy",
  "language": "en",
  "translator": "Louise and Aylmer Maude",
  "description": "A novel of Russia during the Napoleonic wars.",
  "published": "2026-03-01T12:00:00Z",
  "totalBytes": 8421554,
  "chapters": 361,
  "relatedWiki": [
    "napoleon-bonaparte",
    "moscow-1812",
    "battle-of-borodino",
    "yasnaya-polyana",
    "tula"
  ],
  "assets": [
    {
      "url": "/war-and-peace/v2026-03-01-a3f5c8/",
      "type": "text/html",
      "sha256": "a3f5c8...",
      "bytes": 4521,
      "role": "table-of-contents"
    },
    {
      "url": "/war-and-peace/v2026-03-01-a3f5c8/book-1/chapter-1/",
      "type": "text/html",
      "sha256": "9b2c11...",
      "bytes": 24108,
      "role": "chapter",
      "chapterUri": "urn:tolstoy-life:war-and-peace:book-1-chapter-1"
    },
    {
      "url": "/war-and-peace/v2026-03-01-a3f5c8/styles/reading.css",
      "type": "text/css",
      "sha256": "c4d7e9...",
      "bytes": 2847,
      "role": "style"
    }
  ]
}
```

### 4.4 Field notes

- `manifestFormat` declares the schema version (currently `v1`). Clients reject unknown formats rather than guessing.
- `sha256` is the hash of the raw bytes served at that URL — the post-Eleventy artefact actually transmitted to the browser. Not the hash of source markdown, not the hash after any CDN transformation. This has to match what the browser actually downloads.
- `bytes` is the content-length the server will report.
- `role` is a hint for grouping in UI (e.g., "show me just the chapters, not the CSS").
- `chapterUri` is the canonical identifier for the chapter, sourced from explicit `chapterUri` frontmatter on the chapter file (not derived from URL or position). It must be present on every chapter file; the build script fails if a chapter is missing it. This guarantees stability across reorganisation: a chapter can be moved or renumbered and its URI still matches existing annotations.
- `relatedWiki` is the deduplicated set of wiki article slugs referenced by any chapter of this work. The download coordinator iterates this list, fetching any article not already in the shared wiki cache. Only slugs — no per-article hashes, versions, or sizes. The coordinator resolves each slug against the shared wiki cache (`tolstoy-wiki-v<version>`) whose version is known from `/works.json`.
- **No `wikiPreviewsUrl` in per-work manifests.** The canonical pointer to the current wiki-previews bundle lives only in `/works.json` (see §5.2). Embedding it in every work manifest would re-version every work on every wiki edit — see §4.6.
- Every URL in the manifest is an absolute path on the origin. The download coordinator prepends the origin at fetch time.

### 4.5 Stability guarantees

Once a manifest for a specific version is published, it never changes. If an error is found in the content, a new version is produced with a new manifest. This means a client with a cached manifest for `v2026-03-01-a3f5c8` can trust it forever.

The unversioned manifest (`/war-and-peace/manifest.json`) can change, but only by pointing at a new version's manifest. It should always redirect to or embed the same content as the current versioned manifest.

### 4.6 Cross-reference isolation (the no-cascade rule)

The work hash and the work's manifest must not transitively depend on other parts of the site. If a wiki edit — or anything else outside the work folder — can change a work's version, the three-version retention discipline in §3.4 collapses: every work in the corpus re-versions on every unrelated edit, the served-retention count blows up, and every download client is forced to re-download unchanged works.

Two concrete rules enforce the isolation:

**Rule 1 — The work hash is computed over rendered content files only.** Chapters, CSS, images, TOC. Not `manifest.json`. Not `_related-wiki.json`. Not anything else produced by a Layer-1 generator. This is a walk-time exclusion: `generate-asset-manifests.py` must filter those filenames out when assembling the list to hash, even if the files happen to already exist in the work directory (e.g. from a previous build on a persisted workspace).

**Rule 2 — The per-work manifest carries no cross-references to the wiki-previews bundle.** The wiki-previews bundle URL lives at the top level of `/works.json` (§5.2) and nowhere else in the per-work artefacts. The `relatedWiki` array is slugs only — no per-article hashes, no wiki-bundle version. A work's slugs change only when *that work's own chapters* change their wikilinks, which is a legitimate content change for that work.

Together these rules mean: a wiki article edit changes `/works.json` and the wiki-previews bundle URL, but no work's hash, no work's manifest, and no work's versioned subtree. The retention discipline holds.

This is the fix for the cascade bug identified in the 2026-04-23 architecture review (`../architecture/architecture-review.html` Part 7).

## 5. The works index

### 5.1 Purpose

For library UIs ("show me all works I can read"), search, and discovery, the PWA needs a list of every published work with its metadata. This is the works index.

### 5.2 Shape

One JSON document for the whole site, served at:

```
https://tolstoy.life/works.json
```

```json
{
  "indexFormat": "v1",
  "updated": "2026-04-20T10:00:00Z",
  "wikiPreviewsUrl": "/wiki-previews-v2026-04-20-a3f5c8.json",
  "works": [
    {
      "workUri": "urn:tolstoy-life:war-and-peace",
      "title": "War and Peace",
      "author": "Leo Tolstoy",
      "currentVersion": "v2026-03-01-a3f5c8",
      "priorVersions": ["v2025-11-15-9b2c11", "v2025-08-02-7e3a4f"],
      "manifestUrl": "/war-and-peace/v2026-03-01-a3f5c8/manifest.json",
      "indexUrl": "/war-and-peace/",
      "totalBytes": 8421554,
      "relatedWikiBytes": 412800,
      "chapters": 361,
      "language": "en",
      "translator": "Louise and Aylmer Maude",
      "description": "A novel of Russia during the Napoleonic wars.",
      "tags": ["novel", "war", "peace", "historical"]
    },
    {
      "workUri": "urn:tolstoy-life:anna-karenina",
      "title": "Anna Karenina",
      "author": "Leo Tolstoy",
      "currentVersion": "v2026-03-01-d4e9f1",
      "priorVersions": ["v2025-12-20-c83a17"],
      "manifestUrl": "/anna-karenina/v2026-03-01-d4e9f1/manifest.json",
      "indexUrl": "/anna-karenina/",
      "totalBytes": 5318412,
      "relatedWikiBytes": 287400,
      "chapters": 239,
      "language": "en",
      "translator": "Louise and Aylmer Maude"
    }
  ]
}
```

The top-level `wikiPreviewsUrl` is the **sole** canonical pointer to the current wiki-previews bundle. The service worker reads `works.json` on startup to discover this URL and precaches the bundle. It is deliberately *not* duplicated in per-work manifests — doing so would cascade every wiki edit into every work's hash (see §4.6).

`relatedWikiBytes` is the total size of the work's `relatedWiki` articles when fetched fresh — used by the storage panel and quota check (§9 of `stage-1-implementation.md`) to estimate combined download size.

`priorVersions` lists the served prior versions (per the retention policy in §3.4).

### 5.3 Size considerations

The works index is fetched on every app open (to check for new works and version updates). It should stay small — a few kilobytes per entry is fine, but multi-kilobyte descriptions for every work will bloat it unnecessarily.

If the index grows beyond, say, 100 KB, it should be paginated or split by language. For the current corpus size, this isn't a concern.

### 5.4 Caching

The works index should be served with aggressive cache headers that still allow revalidation — e.g., `Cache-Control: public, max-age=300, must-revalidate`. Five minutes of staleness is fine; longer would make new-version detection slow.

The service worker can implement stale-while-revalidate for the index: serve the cached version instantly, fetch a fresh version in the background, notify the UI if it changed.

## 6. The build step

### 6.1 Where it fits

All five artefacts are produced by Layer-1 scripted-pipeline generators that run after Eleventy renders the site, but before deployment. They live in the same Python script family as `extract-graph.py` and `extract-frontmatter.py` (CLAUDE.md, scaled architecture). The order is:

1. Eleventy renders the site to a build output directory.
2. `generate-wiki-previews.py` walks `website/src/wiki/`, builds the previews JSON, hashes it, and writes `wiki-previews-v<YYYY-MM-DD>-<hash6>.json` to the build output root.
3. `generate-related-wiki.py` walks each work's `text/` subfolder for `[[wikilinks]]`, resolves them to wiki article slugs, and writes the `relatedWiki` array to a sidecar `_related-wiki.json` next to the work folder for the next step to consume.
4. `generate-asset-manifests.py` walks each work's build output, computes SHA-256 of each file, gathers frontmatter metadata, reads the `_related-wiki.json` sidecar, and writes `manifest.json` to both the unversioned and versioned URLs.
5. `generate-works-index.py` aggregates every per-work manifest plus the wiki-previews URL into the top-level `works.json`.

### 6.2 Implementation sketch

Roughly (Python, fitting the existing Layer-1 toolchain):

```
# generate-wiki-previews.py
previews = {}
for article in walk_md(vault_root / "wiki"):
    previews[article.slug] = extract_summary(article)
bundle_bytes = canonical_json(previews)
hash6 = sha256(bundle_bytes)[:6]
date = first_commit_date(vault_root / "wiki")  # YYYY-MM-DD, deterministic
filename = f"wiki-previews-v{date}-{hash6}.json"
write(build_root / filename, bundle_bytes)
write(build_root / "wiki-previews-current.txt", filename)

# generate-related-wiki.py
for work_dir in build_root.glob("**/*.md"):  # works only
    related = set()
    for chapter in work_dir.glob("text/*.md"):
        related.update(extract_wikilink_targets(chapter))
    write(work_dir / "_related-wiki.json", sorted(related))

# generate-asset-manifests.py

# Filenames that must never contribute to the work's content hash.
# See §4.6 — these are generated cross-references, not rendered content.
HASH_EXCLUDE = {"manifest.json", "_related-wiki.json"}

for work_dir in iter_works(build_root):
    assets = []
    for path in walk_files(work_dir):
        if path.name in HASH_EXCLUDE:
            continue  # exclude generated artefacts from the work hash
        assets.append({
            "url": make_url(path),
            "sha256": sha256(path.read_bytes()),
            "bytes": path.stat().st_size,
            "type": detect_mime(path),
            "role": detect_role(path),
            "chapterUri": frontmatter(path).get("chapterUri"),
        })
    assets.sort(key=lambda a: a["url"])

    # Content hash is computed over rendered content files only (§4.6).
    # It does NOT include relatedWiki, wiki-previews URL, or any other
    # cross-reference to another build artefact.
    content_hash = sha256(canonical_json(assets))[:6]
    content_date = resolve_content_date(work_dir, content_hash)  # §3 — stateful, not git-derived
    version = f"v{content_date}-{content_hash}"

    related_wiki = read_json(work_dir / "_related-wiki.json")  # flat list of slugs
    manifest = {
        "manifestFormat": "v1",
        "workUri": work_uri(work_dir),
        "version": version,
        "relatedWiki": related_wiki,
        "totalBytes": sum(a["bytes"] for a in assets),
        "assets": assets,
        ...
        # Note: wikiPreviewsUrl intentionally absent — see §4.4 and §4.6.
    }
    # Manifests are written AFTER the hash is computed, so they can't feed back
    # into it. The versioned subtree is materialised from the asset list, not
    # by re-walking work_dir.
    write(work_dir / "manifest.json", manifest)
    write(work_dir / version / "manifest.json", manifest)
    materialize_versioned_subtree(work_dir, version, retention=3)

# generate-works-index.py
index = {"indexFormat": "v1", "updated": iso_now(), "wikiPreviewsUrl": ..., "works": [...]}
write(build_root / "works.json", index)
```

### 6.3 Determinism

The build must be deterministic: same source input produces identical manifest, wiki-previews, and works-index bytes. Non-determinism would mean every build looks like a new version even when nothing changed, breaking the version-retention discipline and forcing clients to re-download unchanged works.

Sources of non-determinism to eliminate:

- File ordering in the `assets` array (sort by URL — done above).
- Slug ordering in `relatedWiki` (sort lexicographically — done above).
- Key ordering in JSON serialization (use a canonical JSON encoder with sorted keys).
- Timestamps in the manifest. The `published` field is the content's first-commit date, not build time. The `updated` field in `works.json` is the only build-time timestamp; it does not affect any hash.
- Locale-dependent formatting of numbers or strings (force C locale).
- Floating-point round-trips (avoid floats in metadata; use integers for bytes).
- Filesystem walk order (sort directory entries explicitly).

A determinism test in CI: build twice in succession from the same git revision; the artefact set must be byte-identical.

### 6.4 The deterministic-build CI check (implemented 2026-04-24)

The determinism test in §6.3 is wired in as a blocking CI job in the `tolstoylife/website` repository:

- **Script:** `.github/scripts/check-determinism.mjs` — a self-contained Node harness that runs `npm run build` twice, computes SHA-256 of every file under `dist/`, and diffs the two hash maps. Prints the differing paths, short hash prefixes, and common non-determinism sources on failure. Exits non-zero if any file differs.
- **Workflow:** `.github/workflows/determinism.yml` — runs on every PR to `main` and on push to `main`, plus `workflow_dispatch` for ad-hoc manual runs.
- **Block policy:** failures return a red check on the PR. Enforcement as a *required* status check is a branch-protection policy decision, separate from this file.

Scope: the check currently covers the Eleventy output in `dist/`. When the four Layer-1 generators (`generate-wiki-previews.py`, `generate-related-wiki.py`, `generate-asset-manifests.py`, `generate-works-index.py`) land, they emit into the same `dist/` tree and inherit the determinism coverage automatically — no changes to the harness are required.

Limitation: the check runs both builds in the *same* environment, so it catches within-environment non-determinism (timestamps, walk order, random IDs, PID-based names). Cross-environment determinism — e.g. Netlify vs. Cloudflare Pages producing identical bytes — is the companion test introduced in `../architecture/architecture-review.html` Part 8 and will be added alongside the CF Pages parallel deploy (TODO priority 5, subsection D).

## 7. Integration with the existing `tl` CLI

The web build is separate from the `tl` EPUB pipeline, but the two share source content. Decision on division of labour:

- **Manifest, versioning, wiki-previews, `relatedWiki`, works index: all in the Layer-1 scripted pipeline (Python), not in `tl`.** The EPUB pipeline doesn't need asset manifests (EPUBs are self-contained files with their own internal manifest). The web build is the consumer of the metadata and is where the post-Eleventy assets actually exist. Adding it to `tl` would couple the EPUB side to the web side unnecessarily.
- **`tl export-wiki` stays scoped to plain markdown export.** The `tl` toolset's job is to round-trip between source XHTML and Obsidian markdown; it does not infuse wikilinks, generate previews, or compute manifests. Wikilink infusion (matching plain text against the wiki to insert `[[…]]` references) is a separate downstream pass run by an LLM + LightRAG, operating on the markdown that `tl` already produced.
- **Shared metadata source.** The canonical work metadata (title, author, translator, description, language, dates, genre, themes) lives in the work's `.md` frontmatter and `.data.yaml` sidecar inside the vault. Both the EPUB pipeline (`content.opf` population) and the web build (manifest + works-index population) read from the same vault files. There is no duplicate metadata store.

## 8. Chapter URIs and stable anchoring

For annotations to anchor to specific chapters, each chapter needs a stable URI that survives reorganisation. Two properties matter:

1. The URI identifies the chapter, not its position in the book. Moving "Chapter 5" to become "Chapter 6" shouldn't break annotations on it.
2. The URI is human-readable enough to be useful in URLs if desired.

Pattern:

```
urn:tolstoy-life:war-and-peace:book-1-chapter-1
urn:tolstoy-life:war-and-peace:epilogue-2-chapter-4
```

The URI is based on the chapter's structural identity within the work (book and chapter number, or a meaningful slug), not its position in a flat list. For a work where "chapter 5" genuinely moves to become "chapter 6" because new content was added, a decision has to be made: keep the URI (so annotations don't break) or renumber (so URIs match the new numbering). Preferring stability is almost always right.

### 8.1 Explicit frontmatter, not derivation

`chapterUri` is **declared explicitly in each chapter file's frontmatter**, not derived from URL or filename. Example:

```yaml
---
title: Book 1, Chapter 1
work: war-and-peace
part: 1
chapter: 1
chapterUri: urn:tolstoy-life:war-and-peace:book-1-chapter-1
---
```

The build script reads this field directly into the asset manifest's `chapterUri` field. If a chapter file is missing it, the build fails loudly — silent derivation from URL or position would re-introduce the very fragility this scheme is meant to prevent.

Why explicit:

- Annotations point at this URI for the lifetime of the project. A typo or unintended change ought to be visible in a diff, not invisibly silent in build logic.
- A chapter that legitimately needs renumbering (rare) keeps its URI; the URL changes but annotations follow the URI.
- A chapter that legitimately needs a new URI (also rare — only on a structural redefinition) is an explicit, reviewable change.

This URI is what appears in the `chapterUri` field of the asset manifest.

### 8.2 Validation (implemented 2026-04-24)

Enforcement of the §8.1 rule lives in `website/.github/scripts/validate-frontmatter.mjs`, which the existing `validate.yml` workflow runs on every PR that touches `src/works/**/*.md`. The validator checks four invariants on every chapter file (anything in `src/works/**/text/*.md` whose frontmatter has `work` and `part`/`chapter` keys):

1. `chapterUri` is present.
2. The value matches `urn:tolstoy-life:<work-slug>:<chapter-id>` (both segments kebab-case).
3. The work-slug inside the URI matches the chapter's `work` frontmatter field (catches the common copy-paste-and-forget-to-update case).
4. The URI is globally unique across the corpus (catches duplication, which would make annotations anchored at that URI ambiguous).

No migration script is needed today: the corpus currently contains zero chapter files (no work has a `text/` subfolder yet). When chapter files begin to appear — Phase 5 TEI ingestion, or the first manual import — they must carry `chapterUri` from file one. The validator catches any miss on the PR rather than after the fact.

Should a bulk import ever produce a batch of chapter files without URIs (e.g. a scan-and-OCR pipeline not yet wired to emit them), a one-shot migration script can be added alongside that pipeline. Deferring it until a concrete need exists avoids speculative tooling.

## 9. Metadata vocabulary

A small, disciplined vocabulary of metadata fields used across the manifests:

Required per work:
- `workUri`, `version`, `title`, `author`, `language`, `published`, `totalBytes`

Recommended per work:
- `translator`, `description`, `tags`, `originalLanguage`, `originalPublished`

Required per asset:
- `url`, `type`, `sha256`, `bytes`

Recommended per asset:
- `role`, `chapterUri` (for chapters)

Extensible: additional fields can be added without breaking older clients, as long as they're additive and optional.

## 10. Testing the pipeline changes

Two kinds of tests:

1. **Unit tests on the build script.** Given a fixture work directory, the manifest output matches a golden file. Catches regressions in manifest shape.
2. **End-to-end.** After a build, the download coordinator can successfully fetch the manifest, download every asset, and verify every hash. Catches discrepancies between the manifest and the actual served content.

The end-to-end test is the important one. It verifies that the contract between the build and the PWA is honoured.

## 11. Migration

### 11.1 Rolling out to existing works

The first build after the pipeline change produces manifests and the works index for every existing work. No content changes. Deploy normally.

### 11.2 Versioning the first time

The first build's version for each work is `v<build-date>`. All works get the same version tag on first rollout, which is fine — they're all at their current state. Subsequent changes produce new versions per-work.

### 11.3 Backwards compatibility

The existing site continues to work. URLs don't change. The manifest and index are new files that didn't exist before; their absence didn't break anything and their presence doesn't break anything.

A client that doesn't know about manifests (say, an old service worker) simply doesn't fetch them. Nothing degrades.

## 12. Future extensions

Things enabled by this scheme but not needed for Stage 1:

- **Multi-format downloads.** The same manifest could list an EPUB and a plain-text version alongside the HTML, letting users download their preferred format.
- **Signed manifests.** The manifest could be signed so clients verify it hasn't been tampered with. Interesting for high-trust use cases, probably overkill for public domain literature.
- **Incremental updates.** Instead of re-downloading a whole work on version change, the manifest could list only changed assets.
- **Alternative translations and editions.** A single work URI could group multiple translations as versions, or a higher-level "work family" concept could emerge.

None of these are blocking. The current scheme leaves room for all of them without baking assumptions that would close doors.

## 13. Open questions for `/ultraplan`

1. Where does the web build currently run (Netlify build environment, primarily)? The Layer-1 generators (`generate-wiki-previews.py`, `generate-related-wiki.py`, `generate-asset-manifests.py`, `generate-works-index.py`) need to be runnable both in the Netlify build and locally for development. Confirm Python availability in Netlify's build image.
2. Is Netlify's hosting such that we can serve `manifest.json` alongside `index.html` for every work, or is there a constraint that would push manifests to a single `/manifests/` directory? (Default Eleventy + Netlify behaviour should accommodate the per-work layout.)
3. How should we handle works that are split across multiple translations? One work URI with multiple versions distinguished by translator, or separate work URIs? Current inclination: separate work URIs (e.g., `urn:tolstoy-life:war-and-peace-maude` and `urn:tolstoy-life:war-and-peace-garnett`) to keep the per-work asset hash meaningful.
4. The version scheme is `v<date>-<hash>` (§3.2); the manifest carries `"manifestFormat": "v1"` (§4.3). The works-index also carries `"indexFormat": "v1"`. Confirm both schema-version markers are present in `/ultraplan` planning so future format changes are non-breaking.
5. Does Netlify's CDN respect the `Cache-Control: public, max-age=300, must-revalidate` header on `works.json` and the per-work `manifest.json`? Netlify-specific overrides may be needed in `netlify.toml` to prevent over-caching of the version-pointer files.
6. The wiki-previews bundle URL is `/wiki-previews-v<hash>.json` (immutable). When the bundle changes hash, the old file is left in the build output for one build cycle (so existing service workers can still resolve their precached URL during the swap). Is that retention sufficient, or should we keep more historical bundles for slow-updating clients?
7. The `relatedWiki` resolver runs on post-Eleventy markdown. It must resolve wikilinks the same way Eleventy does (Obsidian-compatible name resolution, including aliases). Confirm the resolver shares the resolution logic with the rendering layer rather than re-implementing it.

## 14. Summary

Five additions to the Layer-1 scripted pipeline (web build):

1. Deterministic content-addressed versioning (`v<date>-<hash6>`) with stable work URIs and explicit chapter URIs in frontmatter.
2. An asset manifest per work-version, listing every URL with hash and size, plus a `relatedWiki` list.
3. A site-wide works index linking to every manifest, with a top-level pointer to the current wiki-previews bundle.
4. A wiki-previews bundle (`wiki-previews-v<YYYY-MM-DD>-<hash6>.json`) containing summary stubs for every wiki article, hashed and immutable per build.
5. A served retention of current + 2 prior versions per work; older versions remain in git only.

These are metadata and summary additions. They don't touch primary content, don't change canonical URLs, don't modify the EPUB pipeline. They provide the contract the PWA consumes to make offline reading real.

With these in place, the Stage 1 download coordinator has everything it needs, and future stages — annotations (Stage 3), sync (Stage 4+), cross-work search — all inherit the same versioning and identification scheme.
