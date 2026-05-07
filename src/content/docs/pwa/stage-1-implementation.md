# Tolstoy e-reader: Stage 1 implementation plan

The first real local-first step. This stage does not introduce annotations, sync, or CRDTs. It introduces one capability: a user can choose to download a work and have it available offline, forever, on the device they chose.

This document assumes the architecture in `local-first-architecture.md` and is sized to be executed through `/ultraplan` when ready. It's written so a reviewer can read it linearly and know exactly what should exist after Stage 1 is shipped.

## 1. Scope

### 1.1 In scope

- A "Make available offline" control on each work's page.
- A local store of downloaded works, surviving page reloads and app closes.
- An offline-aware reading experience: downloaded works read identically with or without network.
- Wiki articles referenced by each downloaded work are cached alongside it. Shared cache across works, deduplicated. See `wiki-integration.md` §2.
- The bundled wiki-previews file ships with the app shell, so wikilink modal previews work offline for every article in the bundle from first load. See `wiki-integration.md` §3.
- A storage panel in settings showing what's downloaded (works and shared wiki cache) and how much space it takes.
- Graceful handling of browser storage eviction and quota errors.
- Workbox adopted for the service worker's routing and caching-strategy layer (see `local-first-architecture.md` §5.8).

### 1.2 Out of scope

Deliberately excluded from Stage 1:

- Any form of annotation, bookmark, or highlight (the CSS Custom Highlights API and its Safari < 17.4 fallback concern Stage 3, not here).
- Any sync across devices.
- Any account system.
- Push notifications or background updates.
- Automatic pre-caching of works the user hasn't explicitly downloaded.
- Any UI that exists only when offline (the UI is the same; only availability changes).
- A standalone "download the entire wiki" action — present in settings but a separate explicit choice, not part of a work download.

Keeping scope narrow is the whole point of the staged approach. Stage 1 should be shippable and useful on its own, with no latent dependency on stages that haven't been built yet.

## 2. User stories

Three stories define "done" for Stage 1:

1. **The train reader.** A user browses tolstoy.life at home, sees *War and Peace*, taps "Make available offline." They see a progress indicator and a confirmation. The next morning on the train with no signal, they open the app and read *War and Peace* seamlessly.
2. **The storage-conscious user.** A user has downloaded three works. They visit settings and see each work listed with its size. They remove one work and see the storage figure decrease. They close and reopen the app; the change persists.
3. **The accidental offline user.** A user has the app open. Their Wi-Fi drops. They try to navigate to a work they haven't downloaded. They get a clear, friendly message explaining that this work isn't available offline and suggesting they download it when they're back online, without any scary error language.

If all three stories work cleanly, Stage 1 is done.

## 3. Architecture delta

### 3.1 What exists today

The tolstoy.life site is already a PWA with a service worker. At the page level, the site works offline — the shell caches, navigation works, previously-visited pages come out of the cache. What doesn't exist yet is *deliberate, persistent, user-controlled* offline availability of whole works.

### 3.2 What changes in Stage 1

Five additions:

1. A new **offline works store** (Cache API, one named cache per work version) that holds the XHTML, CSS, images, and metadata of each downloaded work.
2. A new **shared wiki cache** (Cache API, `tolstoy-wiki-v<bundle-version>`) holding wiki articles referenced by any downloaded work. Deduplicated across works.
3. A new **download coordinator** module in the client that fetches all assets for a work (chapters + referenced wiki articles), verifies their integrity, and writes them to the appropriate cache.
4. An updated **service worker**, adopting Workbox for routing and caching strategies. The new routes: cache-first for downloaded works, cache-first with network fallback for wiki articles in the shared cache, network-only with graceful fallback for non-downloaded works.
5. The **wiki-previews bundle** (`/wiki-previews-v<YYYY-MM-DD>-<hash6>.json`) is precached with the app shell. Its URL is discovered from `/works.json`.

Everything else — the rendering, the routing, the navigation — stays the same.

## 4. The offline works store

### 4.1 Storage backend choice

Two viable options:

**Cache API.** Simpler model: each work gets a named Cache instance, with asset URLs as keys and Response objects as values. Native integration with the service worker fetch handler. Well-understood quota behaviour.

**OPFS.** More control: each work is a directory, assets are files. Better for large binary blobs. More code to write, but finer-grained access.

**Decision: Cache API for Stage 1.** The Cache API is designed precisely for this use case, the integration with the service worker is almost free, and there's no compelling reason yet to reach for OPFS. If storage or access-pattern issues show up later, switching to OPFS is a self-contained migration.

### 4.2 Cache layout

One named Cache per work:

```
tolstoy-work-v1:war-and-peace:v2026-03-01-a3f5c8
tolstoy-work-v1:anna-karenina:v2026-03-01-7b2d19
tolstoy-work-v1:confession:v2025-11-15-9b2c11
```

The format is `tolstoy-work-v1:<work-slug>:<version>`.

Why include the version in the cache name: when a new version of a work ships, the old cache stays intact until the user explicitly migrates. This means an annotation (in later stages) that points to a specific version can still find its content even after a new version exists.

Why the `v1` schema prefix: leaves room to change the cache format in future without colliding with the old one.

### 4.3 Manifest per work

Each cache contains a special key `__manifest` whose value is a JSON document listing every asset in the cache along with its hash and size.

```json
{
  "workUri": "urn:tolstoy-life:war-and-peace",
  "version": "v2026-03-01-a3f5c8",
  "title": "War and Peace",
  "author": "Leo Tolstoy",
  "downloaded": "2026-04-20T14:15:00Z",
  "totalBytes": 8421554,
  "assets": [
    {
      "url": "/war-and-peace/",
      "type": "text/html",
      "sha256": "a3f5...",
      "bytes": 4521
    },
    {
      "url": "/war-and-peace/chapter-1/",
      "type": "text/html",
      "sha256": "9b2c...",
      "bytes": 24108
    }
  ]
}
```

The manifest is what the settings panel reads to display storage usage. It's also used to verify cache integrity on open: if any asset is missing or has an unexpected size, the work is flagged as damaged and the user is offered a re-download.

### 4.4 Work metadata store

A separate IndexedDB store tracks which works are downloaded, keyed by work URI. This is what the UI reads to know whether to show "Make available offline" or "Downloaded".

```
ObjectStore: downloadedWorks
Key: workUri (string)
Value: {
  workUri: string,
  version: string,
  cacheName: string,
  title: string,
  downloadedAt: ISO8601 string,
  totalBytes: number,
  status: 'downloading' | 'ready' | 'damaged' | 'outdated'
}
```

Separating this from the Cache API lets the UI render a list of downloaded works without opening every Cache, which is faster and simpler.

## 5. The download coordinator

### 5.1 What it does

Given a work URI, the download coordinator:

1. Fetches the work's asset list (a JSON document produced by the `tl` pipeline — see the `tl` integration document for details).
2. Downloads each asset, tracking progress.
3. Writes each asset to the Cache.
4. Verifies each asset's hash against the asset list.
5. Writes the manifest.
6. Updates the `downloadedWorks` record to status `ready`.

### 5.2 Progress and cancellation

The download emits progress events: `started`, `progress` (with bytes downloaded and total), `complete`, `error`, `cancelled`. The UI subscribes to these and updates an inline progress indicator.

Cancellation is important. Users will start downloads they change their minds about. Cancelling mid-download:

- Stops further fetches.
- Deletes the partial cache.
- Removes the `downloadedWorks` record.
- Leaves no trace.

### 5.3 Parallelism

Assets download in parallel up to a concurrency limit (say, 6 simultaneous fetches). Higher isn't better — it can saturate mobile connections and slow the download as a whole. Lower wastes time on sequential latency.

### 5.4 Retry and failure handling

Transient network errors retry with exponential backoff, up to a limit. Hash mismatches are hard failures — they indicate corruption or tampering and the whole download is marked failed. The user sees "Download failed — try again" and can retry; nothing partial is kept.

### 5.5 Resumability

Deferred to Stage 2 or later. For Stage 1, a failed or cancelled download starts over from scratch. This is acceptable for works of reasonable size; if it becomes a problem for the Jubilee Edition's larger volumes, resumability can be added without changing the wire format.

## 6. The service worker update

### 6.1 Workbox adoption

The service worker is structured around Workbox's routing and strategies modules (`workbox-routing`, `workbox-strategies`, `workbox-precaching`). Hand-rolled code is limited to the routing callbacks that need project-specific logic — principally, checking whether a request targets an asset of a downloaded work.

Rationale in `local-first-architecture.md` §5.8. Bundle budget 30 KB gzipped for the service worker layer including Workbox.

### 6.2 Routing rules

Each rule registered via `registerRoute` with a matcher and a strategy:

| URL pattern | Strategy | Notes |
|---|---|---|
| App shell (CSS, JS, fonts) | `StaleWhileRevalidate` | Standard Workbox precache. |
| `/works.json` | `StaleWhileRevalidate` (5-minute max-age) | The version-discovery pointer. |
| `/wiki-previews-v*.json` | `CacheFirst` (immutable) | Hashed URL, precached with shell. |
| Asset in a downloaded work (per `downloadedWorks` lookup) | `CacheFirst` against the work's named cache | Requires IndexedDB lookup in the matcher. |
| Asset of a non-downloaded work | `NetworkOnly` with graceful offline fallback | Shows the "not available offline" page. |
| Wiki article in shared wiki cache | `CacheFirst` against `tolstoy-wiki-v*` | Also handles downloads for standalone-wiki mode. |
| Any other site page | `NetworkFirst` with cache fallback | Wiki, essays, works metadata pages. |

### 6.3 The downloaded-work matcher

This matcher needs IndexedDB access (to know whether the request's work URI is currently downloaded and to look up the cache name). Workbox matchers can be async; they return a truthy value to activate the route or a falsy value to skip to the next rule. The IndexedDB lookup is a single keyed read, so latency is negligible.

### 6.4 Interaction with existing caches

The existing service worker caches — app shell, previously-visited pages — keep working. Workbox precaching manages the shell; the downloaded-works caches and the shared wiki cache are independent and take priority over generic runtime caching.

### 6.5 Cache-versioning discipline

Workbox's precache manifest is versioned by build hash; the shell cache rotates automatically on deploy. The work-specific caches (`tolstoy-work-v1:<slug>:<version>`) and the wiki cache (`tolstoy-wiki-v<bundle-version>`) are independently versioned by their content. Old caches prune when no download references them.

## 7. UI surfaces

### 7.1 Per-work control

On a work's page, somewhere near the top-of-work metadata:

- If not downloaded: a button labelled "Make available offline" with a secondary line showing the size (e.g., "about 8 MB").
- If downloading: a progress indicator with bytes downloaded / total and a "Cancel" link.
- If downloaded: a subtle indicator ("Available offline") and a "Remove" link.
- If an update is available: "A new version is available — update offline copy".

The language matters. "Download" suggests a file. "Make available offline" suggests a capability. The latter is what's actually happening.

### 7.2 Storage panel in settings

A settings page showing:

- Total storage used by the app.
- A list of downloaded works, each with size, download date, and a remove button.
- A single line for the shared wiki cache showing total size and article count (e.g., "Wiki articles: 184 articles, about 2.3 MB"). Not per-work — the cache is shared.
- The bundled wiki-previews file is not shown separately (it's part of the app shell).
- The browser's reported storage quota (via `navigator.storage.estimate()`).
- A "Request persistent storage" button if persistent storage hasn't been granted.
- A separate "Download the entire wiki" toggle in an advanced section, clearly labelled as an explicit opt-in for users who want the full wiki available offline independent of any work.

### 7.3 The "not available offline" screen

When a user tries to navigate to a non-downloaded work while offline, they see a screen that says, in substance:

> This work isn't available offline yet. When you're back online, you can tap "Make available offline" on its page and it'll be there next time you lose signal.

Not an error. Not a modal with an OK button. A clear, friendly page with a link back to the works they do have.

### 7.4 Onboarding and discovery

A first-time visitor should eventually learn that offline availability exists. Options:

- A one-time banner: "Want to read offline? You can save any work to your device."
- An empty-state message in the (yet-to-be-built) "My library" view when the user has zero downloads.
- The "Make available offline" button itself, placed prominently enough to be discovered organically.

For Stage 1, the button alone is probably enough. The banner and library can come later.

## 8. Persistent storage request

Once a user has downloaded a work, the app should request persistent storage via `navigator.storage.persist()`. This significantly reduces the chance the browser evicts the caches under storage pressure.

The request should be:

- Made *after* the first download completes, not on first visit (browsers are more likely to grant persistence to a site the user has meaningfully engaged with).
- Shown with a short explanation if the browser surfaces a permission prompt.
- Silent-failure-tolerant: if not granted, everything still works, just with higher eviction risk.

## 9. Quota handling

The browser may refuse a download or an asset write because the quota is exceeded. Behaviour:

- Before starting a download, sum the work's declared size *and* the size of any wiki articles in the work's `relatedWiki` list that are not already in the shared wiki cache. The user-facing estimate is "this work plus N new wiki articles".
- Check the estimated free quota via `navigator.storage.estimate()`. If the combined size exceeds free quota, show an honest warning before starting: "This work and its wiki articles are about 9 MB. You have about 5 MB free in your browser's storage. You may need to remove another downloaded work first."
- If a quota error occurs mid-download, abort cleanly, remove the partial work cache, leave the shared wiki cache intact (entries already added are useful for other downloads), and tell the user what happened.
- Never fail silently.

## 10. Testing strategy

Stage 1 needs tests at three levels:

1. **Unit tests** for the manifest serialisation, hash verification, cache layout, and the `relatedWiki` deduplication logic (a wiki article referenced by two downloaded works must not be fetched twice or counted twice in storage figures).
2. **Integration tests** for the download coordinator using a mock service worker and fake fetches. Cover success, partial failure, cancellation, quota exceeded, wiki-cache-already-populated (skip fetch), and the wiki-previews bundle precaching.
3. **Manual acceptance tests** for the three user stories in section 2, plus a wiki-specific acceptance test: download two works that share several wiki articles, verify the shared cache contains each article once, verify wikilink modal previews work offline both for articles in the shared cache (full content) and for articles only in the previews bundle (summary only). These are the ones that matter.

Browser-specific edge cases to check manually:

- Safari on iOS (aggressive cache eviction, limited storage).
- Chrome on Android (background tab eviction).
- Firefox (different quota logic).
- Safari on desktop (generally more permissive than mobile).

## 11. Migration and rollback

Because Stage 1 adds new storage without modifying existing structures, rolling back is clean: remove the new service worker rule, stop writing to the new stores, and the existing site behaviour is unchanged. Users who downloaded works during the Stage 1 rollout retain their local data; it just becomes inert.

## 12. Dependencies on the `tl` pipeline

Stage 1 requires three additions to the build pipeline. See `tl-pipeline-integration.md` for the full specification.

1. An **asset manifest** per work — the list of URLs and hashes the download coordinator consumes.
2. A **`relatedWiki`** field on each work's manifest entry — the list of wiki article slugs referenced from any chapter of the work, used by the download coordinator to populate the shared wiki cache.
3. A **wiki-previews bundle** (`wiki-previews-v<YYYY-MM-DD>-<hash6>.json`) emitted at build time, containing summary stubs for every wiki article. Its hashed URL is referenced from `/works.json` so the service worker can precache it deterministically.

If for some reason the pipeline changes can't all ship with Stage 1, two graceful fallbacks exist:

- Without an asset manifest: the download coordinator crawls the work's HTML to discover assets, computes hashes on the fly, and skips verification. Worse — no integrity check — but implementable without pipeline changes.
- Without `relatedWiki`: the download coordinator parses each downloaded chapter for wikilinks and resolves them at download time. Worse — slower, requires HTML parsing in the client, and miscounts size estimates — but acceptable as an interim.
- Without a wiki-previews bundle: wikilink modal previews fall back to network fetch on hover, breaking the offline preview experience. Stage 1 should not ship without the bundle; it's small enough that there's no reason to defer it.

## 13. Estimated scope

Roughly:

- Client code: 800–1,200 lines (download coordinator with wiki-aware deduplication, storage layer, UI surfaces, wikilink modal preview component reading from the bundled previews and falling through to the wiki cache).
- Service worker changes: ~150 lines of project-specific code on top of Workbox (routing registrations, the downloaded-work matcher, the shared wiki cache strategy).
- Workbox dependency: ~30 KB gzipped (within the budget set in `local-first-architecture.md` §5.8).
- `tl` pipeline changes: covered in the pipeline document.
- Settings UI: 150–250 lines (work list, shared wiki cache line, advanced full-wiki download toggle).

Small enough to fit in a focused work session, large enough to deserve real planning. A good fit for `/ultraplan`.

## 14. Open questions for `/ultraplan`

Things worth flagging for the planning session:

1. Should downloads retry automatically on reconnection, or only on user action?
2. Should the storage panel show a breakdown by asset type (text vs images) or just a total per work?
3. What happens when the user visits a work whose new version is available — passive banner, active prompt, automatic update?
4. How do we handle the very first visit, where the user has no works downloaded and may not know the feature exists?
5. Should we ship a "download everything" option (sized to the Jubilee Edition), or deliberately force granular choice?
6. When a work is removed, should its `relatedWiki` entries be pruned from the shared cache if no other downloaded work references them, or should the wiki cache only be cleared via an explicit "Clear wiki cache" action?
7. When the wiki-previews bundle gets a new hash (e.g., a wiki article was added), how should the service worker behave for users who have a downloaded work pointing at the older bundle URL — silent precache swap on next visit, or wait for the work itself to update?

On question 5, the architectural inclination is to deliberately *not* ship a one-click "download everything" option. Making the user choose each work reinforces the idea that storage on their device is a resource, not a free dumping ground, and it aligns with the project's respect-the-reader ethos. The "download the entire wiki" toggle in settings (§7.2) is the deliberate exception — it's a single coherent corpus that some users will reasonably want.

On question 6, the recommended default is automatic pruning (a wiki article with zero referencing downloaded works is removed on the next storage check), with an explicit "Keep all downloaded wiki articles" override in settings for users who prefer manual control.

## 15. Definition of done

Stage 1 is done when:

- [ ] The three user stories in section 2 pass on Chrome, Safari, and Firefox.
- [ ] The storage panel shows correct usage and updates on add/remove, including a single line for the shared wiki cache.
- [ ] Persistent storage is requested after the first download.
- [ ] The service worker, built on Workbox, serves downloaded works offline identically to online, fits within the 30 KB gzipped budget, and uses the routing rules in §6.2.
- [ ] Cancelling a download leaves no trace.
- [ ] The `tl` pipeline produces an asset manifest, a `relatedWiki` list, and a hashed wiki-previews bundle for every build.
- [ ] Downloading a work also populates the shared wiki cache with its `relatedWiki` articles, deduplicated against any wiki entries already present from earlier downloads.
- [ ] Wikilink modal previews work fully offline: bundled summaries appear immediately for any wiki article in the previews bundle; full content is shown for articles in the shared wiki cache.
- [ ] The advanced "Download the entire wiki" toggle in settings works and is clearly distinguished from the per-work flow.
- [ ] The quota-exceeded message is clear and the behaviour is graceful.
- [ ] No regression in non-offline site functionality.

At which point the site is genuinely local-first for the content layer. Stage 2 (bookmarks and reading position) can build on this foundation.
