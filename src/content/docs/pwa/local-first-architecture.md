# Tolstoy e-reader: local-first PWA architecture

A working architectural sketch for turning tolstoy.life into a true local-first e-reader, with W3C-compliant annotations, bookmarks, and optional cross-device sync — all without leaving the open web.

## 1. Why this fits the project

Before the technical design, the alignment worth naming explicitly:

- **Public domain content.** Every work in the Tolstoy project is in the public domain. There is no rights-holder to negotiate with about offline storage, no DRM to implement, no "borrowing window" to enforce. The user genuinely owns their copy.
- **Permanence as a value.** A local-first architecture means a reader who downloads *War and Peace* today still has it in ten years, regardless of whether tolstoy.life is up, whether the user pays anyone, or whether any company decides to stop supporting the format. The copy is theirs, materially.
- **Independence from platform gatekeepers.** No Apple App Store review, no Google Play policy changes, no platform tax. The reader reaches users directly via the web, which is the same medium Tolstoy himself would have recognised as the closest analogue to the pamphlet and the printed book: uncontrolled by any single gatekeeper.
- **Web standards.** The W3C Web Annotation Data Model is a real standard with multiple implementations, not a proprietary format. Annotations exported from the Tolstoy reader should be readable by Hypothes.is, Readwise, or any tool built against the standard, now or in the future.

These aren't decorative justifications. They directly shape which architectural tradeoffs are worth making.

## 2. The four data layers

The architecture rests on recognising that the app has four distinct kinds of data, each with different storage and sync requirements.

**Layer 1a — Works (read-only, content-addressed).** The XHTML output of the build pipeline. Immutable from the user's perspective. Versioned by content hash so a typo fix produces a new, distinct version rather than invalidating caches. Served from tolstoy.life, cached by the service worker, and stored in the Cache API.

**Layer 1b — Wiki articles (read-only, content-addressed).** The markdown files in `website/src/wiki/` that the works reference via `[[wikilinks]]`. Same lifecycle as works — content-addressed, immutable from the user's perspective — but smaller-grained: a single article is a few KB, not many MB. Downloaded selectively per work, with a shared cache that deduplicates across multiple downloaded works. Specified in detail in `wiki-integration.md`.

**Layer 2 — Personal annotations (local-first, sync-capable).** Bookmarks, highlights, notes, reading position, tags. User-owned and mutable. Stored locally in IndexedDB. Optionally synced across a user's devices via CRDTs, but sync is never required for the app to function.

**Layer 3 — Session state (ephemeral, local-only).** Scroll position, UI state, last-opened work. Never leaves the device.

The clean separation between the read-only layers (1a, 1b) and the writable layer (2) is what makes this tractable. Most local-first apps struggle because every piece of data can be edited by any device; here, the large data (the works and wiki) is immutable and only needs to be distributed, and the small data (the annotations) is what actually needs sync logic.

## 3. The annotation layer, in detail

The annotation layer is the interesting architectural problem. It has to do three things well: survive changes to the underlying text, render without damaging the typographic integrity of the work, and sync cleanly across devices when the user wants that.

### 3.1 Anchoring: the W3C Web Annotation Data Model

An annotation stored as "character offset 15,420 in chapter 3" will break the moment anyone fixes a typo earlier in the chapter. This is a solved problem, and the solution is the W3C Web Annotation Data Model — specifically, its approach of attaching multiple selectors to the same annotation and falling back gracefully:

1. **TextPositionSelector** — a character offset range. Fastest to resolve when the text hasn't changed.
2. **TextQuoteSelector** — the exact quoted text with a snippet of context before and after. Survives most edits; re-anchors by searching for the quote.
3. **CssSelector or XPathSelector** — points to a specific element. Useful for fixing an annotation to a structural feature like a footnote or a specific paragraph.

On load, the app tries the position selector first (fastest), falls back to the quote selector if position fails (most robust), and finally to the CSS selector. If all three fail, the annotation goes into an "orphaned" sidebar where the user can see it still exists, just no longer attached. Nothing is ever silently lost.

Hypothes.is's `dom-anchor-text-quote` and `dom-anchor-text-position` libraries implement this correctly and are worth using rather than reinventing.

### 3.2 Rendering: CSS Custom Highlights API

Traditional web annotation systems wrap highlighted text in `<mark>` or `<span>` elements, mutating the DOM of the work. This has two problems: it breaks the typographic purity of the XHTML (which matters for a project that cares about manuscript-grade typography) and it's slow when there are many annotations.

The CSS Custom Highlights API, now shipped in all three major browser engines, solves both. It lets you create a highlight purely as metadata — a set of Ranges associated with a named highlight — and style it via CSS without touching the DOM. The XHTML stays pristine. Highlight rendering becomes essentially free.

```css
::highlight(user-highlight) {
  background-color: rgba(255, 220, 100, 0.35);
}
::highlight(user-note-anchor) {
  text-decoration: underline wavy rgba(100, 100, 255, 0.5);
}
```

### 3.3 Unifying the data model

A bookmark is an annotation with no body. A reading-position marker is a bookmark that updates automatically. A note is an annotation with a body of type `TextualBody`. A tag is an annotation with a body of type `SpecificResource` pointing to a tag URI.

Everything collapses into one data model:

```json
{
  "@context": "http://www.w3.org/ns/anno.jsonld",
  "id": "urn:uuid:9c5b2f...",
  "type": "Annotation",
  "created": "2026-04-20T10:30:00Z",
  "creator": { "id": "local:johan" },
  "motivation": "highlighting",
  "body": [
    { "type": "TextualBody", "value": "The most Tolstoyan sentence in the book." }
  ],
  "target": {
    "source": "urn:tolstoy-life:war-and-peace:book-1-chapter-3#v2026-03-01-a3f5c8",
    "selector": [
      { "type": "TextPositionSelector", "start": 15420, "end": 15467 },
      { "type": "TextQuoteSelector", "exact": "...", "prefix": "...", "suffix": "..." }
    ]
  }
}
```

This makes sync and export trivial, because the annotation set is just an array of these documents, each one self-describing.

## 4. Storage and sync

### 4.1 Local storage

IndexedDB is the right home for the annotation set. It's universally available, supports indexed queries, and handles the volume comfortably — tens of thousands of annotations per user is well within its capacity.

Schema:

- One `annotations` object store, keyed by annotation UUID, holding the full JSON-LD annotation.
- An index on `target.source` for fast lookup when opening a work.
- An index on `created` for chronological views ("my recent notes").
- A separate `works` store for Layer 1 caching metadata (which works are downloaded, their hashes, sizes).

For users who want queryability across their whole annotation set — full-text search over notes, for example — `sqlite-wasm` running against OPFS is a strong upgrade path. It's not needed for the MVP.

### 4.2 CRDT-based sync, when the user opts in

Yjs is the right choice here. It's mature, small, has good bindings (y-indexeddb for local persistence, y-websocket or y-webrtc for transport), and handles the conflict-free merge automatically.

The model: each user has one Y.Doc for their annotation set. It's persisted locally via y-indexeddb. When the user opts into sync, it connects to a relay — either a tiny Cloudflare Worker running `y-websocket-server`, or peer-to-peer via y-webrtc.

Crucially, the sync server stores opaque CRDT update blobs, not parsed annotations. The server never needs to understand the data model. It's a dumb pipe. This has two benefits: server code stays trivially simple (under 100 lines), and the server can't leak structured data about what users are reading because it doesn't know.

### 4.3 Export and portability

Any user should be able to, at any moment, export their entire annotation set as a W3C-compliant JSON-LD file. They should also be able to import from the same format. This is what makes the "the user owns their data" claim substantive rather than decorative.

A button somewhere in settings: "Export all annotations." A matching import button. A "delete all server-side data" button that clears the sync-relay state. No dark patterns.

## 5. Likely problems and how to handle them

Architectures look clean on paper. Here are the specific places this one will get rough.

### 5.1 Storage quota

OPFS and the Cache API are subject to browser storage quotas, which vary by browser and available disk space. The Jubilee Edition is 90 volumes. If a user tries to cache the entire edition, they may hit quota limits, and the browser may evict caches without warning under pressure.

**Mitigation:**
- Use the Storage API (`navigator.storage.estimate()`, `navigator.storage.persist()`) to request persistent storage, which makes the browser much less likely to evict.
- Never cache everything by default. Let the user explicitly choose which works to make available offline, with a storage-usage display next to each one.
- Show the user how much of their quota they've used and what would be freed by removing a work.

### 5.2 iOS background and sync limitations

iOS deliberately limits what a PWA can do in the background. Background Sync and Periodic Background Sync are not supported on Safari. Service worker wake-ups are aggressive about shutdown. Push notifications are available from iOS 16.4+ but only for installed PWAs, and only in limited form.

**Mitigation:**
- Treat sync as "opportunistic on visibility." When the app opens, it syncs. When it goes to background, it flushes pending writes. Don't design any feature that requires background wake-ups on iOS.
- Accept that iOS users will see sync happen on open rather than silently in the background. This is fine for a reading app, where you're about to read anyway.

### 5.3 Annotation anchoring across editions

When a work gets a new edition (typo fix, new translation, restructured chapters), existing annotations anchored to the old version need to handle the transition. The content-addressed versioning means the annotation still points unambiguously to the *old* version, which still exists — but the user is now reading the new version.

**Mitigation:**
- Annotation targets include the version hash: `urn:tolstoy-life:war-and-peace:book-1-chapter-3#v2026-03-01-a3f5c8`.
- When the user opens a work, the app checks whether they have annotations on earlier versions of the same work. If so, it offers to migrate them, using the TextQuoteSelector to re-anchor on the new version.
- Annotations that can't be re-anchored stay attached to the old version and are shown in the "orphaned" sidebar with a link to re-read the old version if the user wants.

### 5.4 Install friction on iOS

iOS doesn't show an install prompt. Users have to know to tap Share → Add to Home Screen, which is a multi-step ritual that most users won't discover on their own. This has real consequences: features like persistent storage, push notifications, and Share Target require the PWA to be installed.

**Mitigation:**
- A short, non-pushy onboarding screen with an illustrated "Add to Home Screen" guide for iOS, shown once on a first mobile Safari visit. Dismissable.
- Detect when the app is running in browser-tab mode versus standalone mode and gently suggest installation when it would unlock a feature the user is trying to use (e.g., "To receive notifications about new editions, add this to your home screen first").
- Never block any feature behind installation. The in-browser experience should be fully functional; installation is an upgrade path.

### 5.5 Cross-device identity without accounts

The local-first promise is undermined if sync requires a heavyweight account system. But some form of user identity is needed to route sync updates to the right devices.

**Mitigation, from least to most intrusive:**
- **Pairing codes.** Device A generates a QR code. Device B scans it. A shared sync key is exchanged. No email, no password, no account. This is the cleanest option philosophically.
- **Email magic links.** Slightly more friction, but allows recovery if the user loses all their devices.
- **Passkeys (WebAuthn).** Modern, passwordless, but still requires the user to have one device set up first.

Pairing codes should be the default. Magic links as a recovery option for users who want it. Both can be implemented with the same sync relay.

### 5.6 Discoverability and the "is this really an app?" problem

Users trained by the App Store don't always trust that a website can be a real app. They may be surprised that a PWA works offline, or distrustful of it compared to a "proper" app.

**Mitigation:**
- Be explicit in the onboarding: "This works without an internet connection. Your notes stay on your device. You own your copy of every book, forever."
- App Store distribution is not a current goal. A Tauri or Capacitor wrapper remains technically possible later as a footnote-grade option, but the project's reach strategy is the open web, not the app stores.

### 5.7 Service worker update cycles

Service worker updates are subtle and can cause confusion. A user with an old service worker may be serving stale code for a surprisingly long time, especially if they always have the app open.

**Mitigation:**
- Use the well-known pattern: on new service worker activation, show a non-intrusive "Updated — reload to apply" banner. Never force-reload.
- Aggressively version everything. The service worker cache keys should include a version hash; old caches are cleaned up on activation.
- Consider a "force reload" escape hatch in settings for debugging.

### 5.8 Service worker correctness — adopt Workbox for routing and strategies

Service workers are one of the few places where bugs really hurt. A bug in a rendering component shows a broken UI; the user refreshes and moves on. A bug in a service worker can leave users serving stale content for weeks, can wedge the site into an unrecoverable state on specific devices, can silently fail to cache things users believe they downloaded. The blast radius is long because service workers persist between visits and most users don't know how to clear them.

**Decision: adopt Workbox for the service worker's routing and caching-strategy layer. Hand-roll everything above it (the download coordinator, IndexedDB stores, UI surfaces).**

Workbox is Google's service-worker library. The `workbox-routing` and `workbox-strategies` modules implement the per-URL-pattern logic the architecture needs (stale-while-revalidate for shell, cache-first for downloaded works, network-first for live pages, network-only with offline fallback for non-downloaded works). `workbox-precaching` handles the shell update cycle including the "skip waiting / reload" pattern in §5.7. `workbox-window` is the page-side helper for talking to the worker.

Adopting Workbox costs ~20 KB gzipped of additional JavaScript in the service worker. It is not in conflict with lean-web principles: the service worker IS the platform, and Workbox is the maintained idiomatic wrapper around a platform API that is notoriously hard to use correctly. The lean-web rule "JS only when load-bearing" applies; correct caching behaviour is load-bearing.

**Out of Workbox's scope (kept hand-rolled):** the user-initiated bulk download with progress and integrity verification (the Stage 1 download coordinator), the IndexedDB stores for download metadata and annotations, all UI surfaces.

**Bundle budget for the service worker layer: 30 KB gzipped** (Workbox plus glue). The 10 KB figure in earlier drafts was aspirational and didn't survive contact with the actual edge cases.

## 6. A staged roadmap

The trap with architectures like this is trying to build the whole thing at once. The value of local-first is that each stage is genuinely useful on its own, and the next stage is purely additive.

### Stage 0 — What exists today

You already have tolstoy.life as a PWA with a service worker. Confirm: the service worker caches the shell and static assets, and the site works offline at the page level. This is the foundation; nothing below breaks anything here.

### Stage 1 — Offline works, deliberately chosen

The first real local-first step. Give the user a "Download for offline reading" button on each work. Cache the work's XHTML and images in the Cache API. Cache the wiki articles the work references in a shared wiki cache. Ship the bundled wiki previews file with the app shell. Show a storage-usage panel in settings.

Deliverable: a user on a train with no signal can read any work they've downloaded, and tap any wikilink in that work to see a preview, and read the full referenced wiki articles. Nothing is synced yet; nothing is annotated yet.

This is more than just "offline books" — it's the full reading experience offline, including the contextual wiki layer. Specified in detail in `wiki-integration.md`.

### Stage 2 — Bookmarks and reading position

Introduce the annotation data model but only for two uses: bookmarks (the user's explicit "mark this spot") and reading position (automatically updated). Stored in IndexedDB using the W3C schema. No sync yet.

Deliverable: reopening a work takes the user back to where they were. Bookmarks appear in a sidebar.

This is the first use of the annotation layer and validates the data model in a low-stakes way. If anchoring breaks, only bookmarks break — not ten thousand user notes.

### Stage 3 — Highlights and notes

Add highlighting (using the CSS Custom Highlights API) and note-attaching. Same data model as bookmarks, just more motivations. Still no sync.

Deliverable: a user can highlight passages and attach notes. All local. Export/import as JSON-LD already works, because the data model supports it.

At this point you have a fully functional single-device local-first e-reader. This is a real, shippable product, and it honours the project's values completely. Stage 4 is optional from here.

### Stage 4 — Opt-in sync

Add Yjs on top of the existing IndexedDB store using y-indexeddb. Stand up a minimal Cloudflare Worker (using Durable Objects' WebSocket support to implement the y-websocket protocol) as the sync relay. Add a QR-code pairing flow in settings, with a six-word phrase fallback for browsers without `BarcodeDetector`.

Deliverable: a user who wants to read on both phone and laptop gets their annotations synced between them, with no account, no email, no password.

The architectural discipline here is critical: the app must keep working identically for users who never enable sync. Sync is an overlay, not a change to the core data flow. Specified in detail in `yjs-schema-and-sync.md`.

### Stage 5 — Search and cross-work features

With the annotation set maturing and local-first infrastructure in place, more ambitious features become possible: full-text search across a user's notes, tags, cross-work citations (an annotation on *Anna Karenina* that references a passage in Tolstoy's letters), an export to a static "reading journal" site the user can publish.

### Stage 6 — The open annotation layer

Optional and long-term: let users choose to publish annotations publicly, compatible with the W3C Web Annotation Protocol. This opens a social layer — readers leaving notes that other readers can see. It's a whole additional project, but it's architecturally a natural extension, not a rewrite.

## 7. What this doesn't become

Worth naming the things this architecture is not:

- **Not a collaborative editor.** Two users editing the same work simultaneously is not a goal. The works are immutable. Annotations are personal.
- **Not a walled garden.** No account required to read. No account required to annotate. Sync is opt-in and uses standards-based formats that are portable elsewhere.
- **Not a platform play.** The goal is not to become the "default reading app" or to acquire users. It's to let readers of Tolstoy have a tool that honours the works, respects their ownership, and outlasts any company.
- **Not dependent on big data companies.** No Google Analytics, no Facebook SDK, no Cloudflare beyond the tiny sync worker (and even that is replaceable). The app can be self-hosted, forked, or moved to another provider without user-visible change.

## 8. Decision log

Resolved decisions:

1. **Storage backend for works:** Cache API. Revisit if quotas become a problem in practice.
2. **Service worker library:** Workbox for routing and strategies; hand-rolled download coordinator and IndexedDB layer above it. Bundle budget 30 KB gzipped.
3. **Wiki download model:** Model B (per-work `relatedWiki` declarations, shared deduplicated cache). See `wiki-integration.md`.
4. **Sync relay hosting:** Cloudflare Workers + Durable Objects, implementing the y-websocket protocol. Free tier suffices at expected scale.
5. **Sync relay implementation:** `y-durableobjects`-style implementation, not the Node-only `y-websocket-server`.
6. **Pairing model:** QR codes by default, six-word BIP-39 phrase fallback for browsers without `BarcodeDetector`. No email, no password.
7. **Recovery model:** explicit sync-key export to file, plus optional encrypted-backup-to-user-URL (e.g., user's own Nextcloud or similar). No project-controlled recovery.
8. **Export format default:** JSON-LD (W3C Web Annotation standard), with a secondary Markdown export for readers who want to paste into their own notes.
9. **Annotation versioning:** edit history via Y.Doc — free when using CRDTs.
10. **Version retention on the served site:** current version plus the two prior versions per work. Older versions remain in git history (the canonical archive) but are not served. This bounds the served storage without losing anything materially. See `tl-pipeline-integration.md`.

Remaining open questions:

- App-store distribution: not pursued. PWA only.
- Whether to ship a one-click "download everything" option for the wiki: yes, behind a deliberate explicit action in settings, not the default.

## 9. Closing thought

The most satisfying thing about this architecture is how well its technical properties align with the project's values. Public-domain texts call for an architecture where the user truly owns their copy. Standards-based annotations call for a data model that isn't trapped in any one app. Independence from gatekeepers calls for a PWA rather than a native app. The fact that all of these happen to also be the technically cleanest choices is not a coincidence — the values and the technology come from the same tradition of craft, independence, and respect for the reader.

The goal isn't to build the most capable e-reader on the market. It's to build one that a reader of Tolstoy would look at and recognise as made in the right spirit.
