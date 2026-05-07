# Tolstoy e-reader: wiki integration

This document specifies how the wiki layer (`website/src/wiki/`) participates in the local-first PWA. It sits alongside `local-first-architecture.md`, `stage-1-implementation.md`, `yjs-schema-and-sync.md`, and `tl-pipeline-integration.md`, and resolves three questions left open by them:

1. When a reader downloads a work for offline use, what happens to the wiki articles that work references?
2. How does the wikilink modal preview load — instantly, online, or both?
3. How does the PWA surface the path from "I noticed something" to "I made a contribution" without taking on identity infrastructure?

Editorial questions — voice, mission, source authority — are out of scope here. They live in `MANIFEST.md` and are handled separately.

## 1. The wiki as a layer

The three-layer separation in `local-first-architecture.md` (works / annotations / session state) is incomplete. The wiki is a fourth kind of data:

**Layer 1a — Works** (read-only, content-addressed). The XHTML chapters, images, and CSS for a published work.

**Layer 1b — Wiki articles** (read-only, content-addressed). The markdown files in `website/src/wiki/` that the works reference via `[[wikilinks]]`. Same lifecycle as works — produced by the build, immutable from the user's perspective, versioned by content hash.

**Layer 2 — Annotations** (local-first, sync-capable). Unchanged.

**Layer 3 — Session state** (ephemeral, local-only). Unchanged.

Wiki and works share a layer-class — both are content-addressed, both are immutable from the user's perspective, both are produced by the same build pipeline. They differ in granularity: a work is a large unit (hundreds of files, tens of MB), a wiki article is a small unit (one markdown file, a few KB). This difference shapes the download and caching strategy.

## 2. The wiki download model

Three plausible models were considered. The chosen one is Model B.

### 2.1 Models considered

**Model A — Download the entire wiki with every work.**

Generous but wasteful. At full project scope (~26,500 wiki articles, ~72 MB), every work download would trigger a 72 MB transfer regardless of which articles the work actually references. Mobile-data-hostile. Storage-wasteful for users with multiple downloaded works.

**Model B — Download only the wiki articles a work references.**

Each work declares its referenced wiki articles in its asset manifest. The download coordinator fetches those alongside the work's chapters. Articles are stored in a shared wiki cache, deduplicating across multiple downloaded works. Modal previews work fully offline for referenced articles; non-referenced articles need network or fall back to title-only.

**Model C — Wiki is online-only, never downloaded.**

Simplest to build, worst experience. A reader on a train who downloaded *War and Peace* would tap `[[Natasha Rostova]]` and see a network error. Contradicts the local-first promise.

### 2.2 Model B in detail

**Per-work `relatedWiki` declaration.** Each work's asset manifest (see `tl-pipeline-integration.md`) gains a `relatedWiki` array listing every wiki article the work directly references via `[[wikilinks]]` in its source text. This is computed at build time by walking the work's text files and collecting all wikilink targets.

```json
{
  "workUri": "urn:tolstoy-life:war-and-peace",
  "version": "v2026-03-01-a3f5c8",
  ...
  "relatedWiki": {
    "version": "v2026-04-20-a3f5c8",
    "articles": [
      {
        "uri": "urn:tolstoy-life:wiki:natasha-rostova",
        "url": "/wiki/natasha-rostova/",
        "sha256": "9b2c11...",
        "bytes": 8421
      },
      {
        "uri": "urn:tolstoy-life:wiki:borodino",
        "url": "/wiki/borodino/",
        "sha256": "c4d7e9...",
        "bytes": 12483
      }
    ],
    "totalBytes": 1842559
  }
}
```

**Transitive depth: one hop, not closure.** A wiki article on Sophia Tolstaya itself contains wikilinks to other articles. The download includes the *directly* referenced articles only — not the transitive closure. The transitive closure would drag in nearly the whole wiki for any major work, defeating the purpose of selective download. Articles reached via "wikilink-from-a-wikilink" are available online or via the bundled previews (section 3) but not as full offline articles.

**Shared cache, deduplication.** Wiki articles live in a single named cache: `tolstoy-wiki-v<version>`. Multiple downloaded works reference the same cache; if `Anna Karenina` and `War and Peace` both reference `[[Sophia Tolstaya]]`, the article downloads once. The cache version is the wiki bundle's content hash; updating the wiki bundle creates a new cache and the old one is pruned after no work references it.

**Cache lifecycle.** When the user removes a downloaded work, the download coordinator checks whether any *remaining* downloaded work still references each of that work's wiki articles. Articles still referenced stay; articles no longer referenced by any downloaded work are removed. The shared cache shrinks correctly on work removal without orphaning articles still in use.

**Settings visibility.** The settings storage panel surfaces wiki storage as a distinct line item:

```
Downloaded works
  War and Peace               8.2 MB
  Anna Karenina               5.1 MB
Wiki articles (shared)        3.4 MB
Total                        16.7 MB
```

This makes the dedup model explicit to the user — they understand that downloading another work won't necessarily double the wiki cost.

**User control.** A setting in the storage panel, default on: "Download related wiki articles when I download a work." A user who wants to save space can turn it off; in that case, the modal preview (section 3) still works for in-bundle previews but full articles require network. The setting is per-device, not synced.

**Standalone wiki download.** A separate explicit action in settings: "Download the entire wiki for offline use." For scholars who want full offline access, this is a single deliberate choice with a clear size warning. At full project scope this is a ~72 MB download. Not the default.

## 3. Wikilink preview bundling

The modal preview that appears when a reader hovers or taps a `[[wikilink]]` should render instantly, work offline, and not require the user to have downloaded the full wiki article. The mechanism is a bundled summaries file produced by the build.

### 3.1 The bundle

A single JSON document, served at a hash-stable URL:

```
/wiki-previews-v2026-04-20-a3f5c8.json
```

The current bundle's URL is referenced from `/works.json` (see `tl-pipeline-integration.md`), so the client always knows which version to fetch.

### 3.2 Bundle structure

Keyed by article slug for O(1) lookup, not as a flat array:

```json
{
  "version": "v2026-04-20-a3f5c8",
  "generated": "2026-04-20T03:00:00Z",
  "schema": "wiki-previews-v1",
  "articles": {
    "sophia-tolstaya": {
      "title": "Sophia Tolstaya",
      "type": "person",
      "summary": "Sophia Andreevna Tolstaya (1844–1919) was Tolstoy's wife from 1862, the mother of his thirteen children, and the first transcriber of his manuscripts.",
      "dates": "1844–1919",
      "image": "/images/sophia-tolstaya-thumb.webp",
      "wordCount": 4521
    },
    "yasnaya-polyana": {
      "title": "Yasnaya Polyana",
      "type": "place",
      "summary": "Tolstoy's family estate in Tula Oblast, where he was born, wrote his major works, and is buried.",
      "coordinates": [54.0667, 37.5167],
      "wordCount": 2103
    }
  }
}
```

Per-article fields:

- `title` (required) — the article's display title.
- `type` (required) — wiki schema type: `person`, `place`, `event`, `concept`, `translator`, `institution`, `adaptation`, `criticalWork`, `archivalFond`. Drives modal layout.
- `summary` (required, may be `null`) — the preview prose. ≤ 250 chars after extraction.
- Type-specific optional fields: `dates` (person/event), `coordinates` (place), `image` (any).
- `wordCount` (recommended) — the full article's length, useful for "read more" UX.

Thumbnail images are referenced by URL; the bundle does not embed image bytes. Images load on-demand when their preview is opened, then service-worker-cache organically.

### 3.3 Summary extraction logic

The Layer-1 script that builds the bundle (`generate-wiki-previews.py`) follows these rules in order:

1. If the article's frontmatter contains a `summary:` field, use it verbatim.
2. Else, extract the first paragraph of prose. Strip wikilink brackets (`[[Sophia Tolstaya]]` becomes `Sophia Tolstaya`). Strip markdown formatting. Truncate at the nearest sentence boundary under 250 characters.
3. If the first paragraph is shorter than 50 characters, append the second paragraph up to the same limit.
4. If no prose exists, set `"summary": null`. The modal renders title and type only — not fake content.

This logic is a single Python function with fixture-based tests. Refining it is cheap; the bundled output regenerates nightly anyway.

### 3.4 Size and growth

Per-article cost is roughly 370 bytes raw (title, type, summary, optional fields, JSON overhead). At full scope (~26,500 articles), the bundle is ~10 MB raw, ~2-3 MB gzipped. For the MVP corpus (first ~1,000 articles), it's ~100 KB gzipped — negligible.

If the bundle ever crosses 5 MB gzipped, two strategies become viable:

1. **Lazy-load.** Don't ship the bundle with the app shell; fetch it after first paint. By the time the reader taps their first wikilink, it's loaded.
2. **Split by domain.** One bundle per wiki type (people, places, events, concepts). Client loads only the bundle relevant to the article currently open.

Neither is needed today. Plain bundled JSON is the right answer until the file gets uncomfortably large.

### 3.5 Compression and caching

The bundle is served with brotli or gzip (both compress repeated field names like `"title"` and `"summary"` extremely well). Cache headers:

```
Cache-Control: public, max-age=31536000, immutable
```

The hashed URL (`wiki-previews-v2026-04-20-a3f5c8.json`) makes immutable safe — when the bundle changes, the URL changes, the old version ages out naturally. The pointer to the current bundle URL lives in `/works.json`, which has a short max-age and is the actual cache-bust mechanism.

### 3.6 Render path

When the reader hovers or taps a `[[wikilink]]`:

1. The wikilink element's `data-wiki-slug` attribute carries the slug.
2. Client looks up `previews.articles[slug]` — synchronous, sub-millisecond.
3. Modal renders from a template using the type field for layout.
4. Optionally, the thumbnail starts loading (service worker may have it cached).

Sub-millisecond first render. No network call required for the preview itself. This is the user-experience reason for bundling: the modal is instant rather than "wait 200 ms for a fetch."

### 3.7 "Read more" — the full article

The modal includes a "Read more" link to the full wiki article. The reader's click resolves through this priority:

1. **Offline wiki cache** (the article was downloaded with a work). Open immediately.
2. **Network fetch** of `/wiki/<slug>/`. Standard navigation.
3. **Offline fallback** — if neither cache nor network works, show "Full article available online" with a retry button.

### 3.8 Settings toggle

A user setting, default on: "Show wiki previews on hover." Some readers find hover previews fiddly, especially with imprecise pointing devices. When off, wikilinks open the full article on click without a preview step. The setting is per-device, not synced.

## 4. The contributor surface

The PWA is the reader surface. Contribution lives on GitHub. The PWA's job is to make the path from "I noticed something" to "I made a contribution" cheap, without taking on identity or moderation infrastructure of its own.

### 4.1 The "Improve this article" link

Every wiki article and work page in the PWA carries a small footer link:

```
Improve this article on GitHub →
```

The link goes to GitHub's web editor for the source file:

```
https://github.com/tolstoylife/website/edit/main/src/wiki/Sophia%20Tolstaya.md
```

A reader who wants to fix a typo:

1. Clicks the footer link.
2. Lands in GitHub's in-browser editor with the file open.
3. Edits, scrolls down, writes a commit message (template provided).
4. Clicks "Propose changes" — GitHub forks, branches, and opens a PR.

Total reader friction: ~90 seconds for someone with a GitHub account. Zero infrastructure on the PWA side.

The link's URL is templated at build time from each page's source file path. The PWA stays a static site; no runtime backend needed.

### 4.2 Issue-template links for non-edit contributions

Some contributions don't fit the edit-this-file flow: reporting a factual error that needs research, requesting a missing wiki article, flagging a broken wikilink across multiple pages. For these, deep links to GitHub Issue templates:

```
https://github.com/tolstoylife/website/issues/new?template=factual-correction.yml&article=/wiki/sophia-tolstaya/
```

GitHub's issue-template URL parameters pre-fill the form. The PWA generates these links per-page, so the issue arrives already tagged with the article it concerns.

Three templates worth shipping with the project:

1. **Factual correction** — required fields: article URL, the claim being corrected, the corrected claim, the source citation.
2. **Missing wikilink** — fields: source text URL, passage where the link should go, target wiki article URL.
3. **Wiki article request** — fields: subject (person / place / concept), why it deserves an article, suggested sources to consult.

The factual-correction template enforces the schema's source-citation rule at submission. No source means the form won't submit. This pushes quality control upstream of human review.

### 4.3 GitHub-side infrastructure (out of PWA scope, but referenced)

For completeness, the GitHub-side mechanisms the PWA's contribution links rely on:

- **Issue templates** (`.github/ISSUE_TEMPLATE/*.yml`) — the structured forms the PWA links to.
- **PR template** (`.github/PULL_REQUEST_TEMPLATE.md`) — checklist for source citations, schema compliance, wikilink resolution.
- **CODEOWNERS** (`.github/CODEOWNERS`) — path-based approval requirements. Schema files require maintainer approval; wiki articles can be approved by trusted contributors.
- **GitHub Actions** — automated validation on every PR (frontmatter schema, wikilink resolution, build success). Failures comment on the PR with what's wrong.
- **Branch protection** on `main` — required reviews, required status checks, no direct pushes.

These are configured once in the `tolstoylife/website` repo and don't change as the PWA evolves.

### 4.4 Attribution surface

For wiki articles with non-trivial contribution history, the article's footer can include a quiet attribution:

```
Contributors: [GitHub username 1], [username 2], and 3 others →
```

The link goes to the file's GitHub history. This is build-time data — Eleventy can read git log for each file at build and embed contributor lists in the rendered page. No runtime API call to GitHub needed.

Attribution is per-article, not site-wide. Readers see who has contributed to the specific article they're reading, which makes the contribution path concrete: "this article was improved by other readers; I can do that too."

### 4.5 What the PWA does not do

- The PWA does not run any auth flow. GitHub login happens entirely on github.com.
- The PWA does not show contributor profiles, comment threads, or issue lists. Those live on GitHub.
- The PWA does not bridge GitHub identity with the QR-pairing identity used for annotation sync. The two identity systems are completely independent — a reader can sync annotations across devices with no GitHub account; a contributor can have a GitHub account with no synced annotations.

Keeping these surfaces separate is the architectural discipline. Bridging them would create a "platform" — exactly what the project is trying to avoid.

## 5. Integration with the three-layer architecture

The Tolstoy Research Platform's three-layer model (CLAUDE.md §"Scaled architecture: three-layer processing model") describes Layer 1 as scripted, deterministic, nightly cron jobs. The PWA's wiki integration plugs in cleanly here.

### 5.1 New Layer-1 outputs

Two new generated artifacts, both produced nightly by Layer-1 scripts:

- **`/works.json`** — the works index (per `tl-pipeline-integration.md` §5). Includes a `currentWikiPreviewsUrl` field pointing to the current preview bundle.
- **`/wiki-previews-v<YYYY-MM-DD>-<hash6>.json`** — the bundled preview file (this document §3).

A new script, `generate-wiki-previews.py`, walks `website/src/wiki/`, applies the extraction logic in §3.3, and writes the bundle. Lives alongside the existing `extract-graph.py`, `extract-frontmatter.py`, and `generate-briefing.py`.

A second new script, `generate-related-wiki.py`, walks each work's text files, collects `[[wikilinks]]`, resolves them to wiki article URIs, and emits the `relatedWiki` section consumed by the work's manifest.

### 5.2 Eleventy build consumption

Eleventy's build reads the Layer-1 outputs as global data:

- The works index becomes `_data/works.json`, available to every template.
- The wiki previews bundle is referenced by URL only — Eleventy doesn't embed it; the PWA fetches it at runtime.
- The relatedWiki sections are merged into each work's manifest at the manifest-generation step (which runs as part of the Eleventy build, per `tl-pipeline-integration.md` §6).

This keeps Layer 1 (scripted, deterministic, content-derived) and the Eleventy build (template rendering) cleanly separated. Layer 1 produces the data, Eleventy consumes it.

### 5.3 Source of truth

Wiki article metadata (title, type, summary if explicit) lives in the article's frontmatter. The previews bundle is derived; the articles are canonical. The bundle can be regenerated from the articles at any time, byte-identical given the same input.

Wiki article URIs (`urn:tolstoy-life:wiki:sophia-tolstaya`) are derived deterministically from the article's filename via the slug rule documented in `nice-permalinks` (the existing skill). The URI is what appears in the `relatedWiki` arrays and in annotation tag references; it is the cross-system identifier.

## 6. Consequences for the staged roadmap

This document changes how `local-first-architecture.md`'s staged roadmap should be read:

- **Stage 1** (offline works) gains the wiki download alongside it. The download coordinator handles both the work's chapters and its `relatedWiki` articles. The wiki previews bundle is fetched as part of app shell.
- **Stage 2 / 3** (annotations and highlights) inherit working wikilink previews and offline wiki articles. Tags can reference wiki article URIs as `urn:tolstoy-life:wiki:non-resistance`.
- **Stage 4** (sync) is unchanged.
- **Stage 5+** (search) can use the previews bundle as a basis for client-side wiki search — the same data that powers modal previews indexes naturally for full-text search.

Wiki integration is not a separate stage. It threads through every stage from 1 onward, because the wiki is part of the reading experience, not a feature on top of it.

## 7. Open questions

Things to flag for `/ultraplan`:

1. Should the `summary:` frontmatter field be required for high-traffic articles (people in Tolstoy's inner circle, his major works), or is the auto-extracted first paragraph good enough across the board?
2. Should the PWA provide a "Why is this article here?" link from each preview, opening the source citation list? Useful for transparency, costs a few bytes per preview.
3. Should `relatedWiki` distinguish between articles linked from the work's prose vs. from the work's overview metadata? Could affect download granularity for very large works.
4. For users with the standalone "download entire wiki" option, should subsequent work downloads skip the per-work `relatedWiki` step (since everything is already cached)? Likely yes; mostly a coordinator implementation detail.
5. Should the contributor footer link be present on every page, or only on pages a reader has spent meaningful time on? The former is honest about how the project works; the latter is less visually noisy.

## 8. Summary

- A fourth data layer: wiki articles, content-addressed and immutable like works, but smaller-grained.
- Per-work `relatedWiki` declarations drive selective wiki downloading. Shared cache deduplicates across works.
- A bundled previews file (~370 bytes per article) ships with the app shell and powers instant offline modal previews. "Read more" promotes to the full article.
- Contribution lives on GitHub, reached via deep links (edit URLs, issue-template URLs) embedded in the PWA. The PWA carries no auth, no comments, no contributor profiles.
- Two new Layer-1 scripts (`generate-wiki-previews.py`, `generate-related-wiki.py`) produce the artifacts the PWA consumes.
- Wiki integration threads through every PWA stage rather than being a stage of its own.
