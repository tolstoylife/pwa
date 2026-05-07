# Tolstoy e-reader: Yjs schema and sync architecture

This document specifies the concrete CRDT shape, the IndexedDB layout, and the sync-relay contract. It assumes the overall architecture from `local-first-architecture.md` and focuses on the "how exactly" of the annotation layer's storage and sync.

## 1. Design principles for the CRDT layer

Four rules that all the specific choices below follow from:

1. **The server never parses user data.** The relay stores opaque binary updates. It cannot tell the difference between a bookmark and a note. This is both a privacy property and a simplicity win.
2. **Every annotation is independent.** Moving, merging, or deleting one annotation never requires understanding any other. This keeps the CRDT shape flat and the merge semantics predictable.
3. **Offline writes always succeed.** The local Y.Doc accepts writes with no network involvement. Sync is reconciliation, not coordination.
4. **The on-wire format is a Yjs update blob.** Not JSON. Not a custom delta. This means the full Yjs ecosystem (y-indexeddb, y-websocket, y-webrtc) works without adaptation.

## 2. The Y.Doc shape

One Y.Doc per user. Not one per work, not one per device — one.

Why one doc for everything: the user's annotation set is a single semantic unit. They want to search across it, export it, delete it. A single Y.Doc with well-chosen top-level types keeps this simple and keeps the sync contract clean.

### 2.1 Top-level types

```javascript
const ydoc = new Y.Doc()

// The annotations themselves, keyed by UUID.
// Each value is a Y.Map representing one W3C annotation.
const annotations = ydoc.getMap('annotations')

// Per-work metadata the user has explicitly set
// (custom titles, reading-list ordering, etc.).
// Keyed by work URI.
const workMeta = ydoc.getMap('workMeta')

// Reading positions, keyed by work URI.
// Updated frequently; separated so position updates
// don't churn the annotations map.
const readingPositions = ydoc.getMap('readingPositions')

// Tags the user has defined, keyed by tag slug.
// Value is a Y.Map with the tag's display name,
// colour, and description.
const tags = ydoc.getMap('tags')

// User preferences that should sync across devices
// (font size, theme, reading goals).
// Distinct from session state, which stays device-local.
const preferences = ydoc.getMap('preferences')
```

Five top-level maps. Each one represents a kind of user-owned data. Session state (scroll position within the current view, current UI panel) is deliberately *not* in the Y.Doc — it stays in sessionStorage and never syncs.

### 2.2 Annotation shape

Each entry in the `annotations` map is itself a Y.Map. Using Y.Map rather than a plain object lets individual fields be updated without rewriting the whole annotation, which matters when two devices edit the same annotation's body concurrently.

```javascript
// Creating a new annotation
const annotation = new Y.Map()
annotation.set('id', 'urn:uuid:9c5b2f...')
annotation.set('type', 'Annotation')
annotation.set('created', new Date().toISOString())
annotation.set('modified', new Date().toISOString())
annotation.set('creator', 'local:johan')
annotation.set('motivation', 'highlighting')

// Body: Y.Array of body items (W3C allows a list of bodies —
// e.g., a highlight with a note AND a tag reference).
// Each body item is itself a Y.Map so individual fields can be
// updated concurrently without replacing the whole item.
// A TextualBody's `value` is a Y.Text so concurrent edits to a note
// merge at character level rather than producing silent duplicates.
// See §2.3 for the reasoning.
const body = new Y.Array()

const textBody = new Y.Map()
textBody.set('type', 'TextualBody')
textBody.set('value', new Y.Text('The most Tolstoyan sentence.'))
body.push([textBody])

annotation.set('body', body)

// Target: single target per annotation.
// Stored as a Y.Map so selectors can be updated if the anchoring changes.
const target = new Y.Map()
target.set('source', 'urn:tolstoy-life:war-and-peace:book-1-chapter-3#v2026-03-01-a3f5c8')

// Selectors: array of selector objects, tried in order.
const selectors = new Y.Array()
selectors.push([
  { type: 'TextPositionSelector', start: 15420, end: 15467 },
  {
    type: 'TextQuoteSelector',
    exact: 'The most Tolstoyan sentence in the book.',
    prefix: 'After a long digression, he wrote: ',
    suffix: ' Nothing more needed saying.'
  }
])
target.set('selector', selectors)
annotation.set('target', target)

annotations.set(annotation.get('id'), annotation)
```

### 2.3 The body Y.Array, reasoned out

The `body` field is a `Y.Array` of `Y.Map`s. A `TextualBody` item's `value` is a `Y.Text`. This matches §8 item 1. Earlier drafts of this section argued for a `Y.Array` of plain objects on "plain replacement is a better semantic fit" grounds; that reasoning was wrong. The cost of the wrong shape is a **silent duplicate** on concurrent edit, walked through below.

**The failure mode with plain objects.** Two devices are offline with the same annotation. Each user edits the note text. On each device the only available operation on a plain-object body item is to replace it wholesale:

```javascript
// Naïve plain-object replace, running independently on each device:
body.delete(0)                                       // remove the old TextualBody
body.insert(0, { type: 'TextualBody', value: newText })   // insert a new one
```

When the devices come online and Yjs merges:

- Each `delete(0)` removes the original. The original is tombstoned once. Fine.
- Each `insert(0, …)` appends a new object. Y.Array has no "same logical item" concept for plain objects — it sees two unrelated inserts.
- The merged array ends up with **both** new objects: `[{…user A's text}, {…user B's text}]`.

The user opens the annotation and sees two TextualBody entries where they expect one. No conflict indicator. No "choose one" prompt. A phantom duplicate. This is exactly the class of bug that makes users stop trusting a tool.

**Why `Y.Map` + `Y.Text` fixes it.** A `Y.Map` representing a body item has a stable identity across merges — both devices mutate the *same* Y.Map rather than replacing it. A `Y.Text` `value` merges at character level using Yjs's text CRDT: a deterministic interleaving based on Lamport timestamps. The concurrent-edit result is one coherent string (e.g., `"Tolstoy notesBook club notes"`) — not elegant, but visible as a single merged field the user can clean up.

Interleaved text is not beautiful, but it is *visible*. A silent duplicate is not. Making conflicts visible is the correct trade-off for a project where data integrity is load-bearing.

**Non-text body items.** A body item referencing a tag (`SpecificResource` with a `source` URI) or a linked resource is identity-by-URI. If two devices add the same tag concurrently, both inserts produce items whose `source` is the same, and a render-time or observe-time deduplication pass collapses them. These items do not need a `Y.Text` — their "content" is the URI, and the URI is the same on both devices. They live in the Y.Array as `Y.Map`s whose fields are plain values.

**Wire format is unchanged.** JSON-LD export (the W3C Web Annotation serialisation) projects `Y.Text` back to a plain string and `Y.Map` back to a plain object. External consumers see a standard W3C Annotation body; only the internal storage shape is Yjs-typed.

**A thin helper.** Because the construction is slightly fiddly, a single factory function hides it:

```javascript
function createTextualBody(value) {
  const m = new Y.Map()
  m.set('type', 'TextualBody')
  m.set('value', new Y.Text(value))
  return m
}
```

All call sites that add or replace a TextualBody use this helper. Consistency is mechanical rather than cultural.

**Test fixture to prevent regression.** A single vitest/mocha case covers the concurrent-edit scenario end-to-end: two Y.Doc instances, offline edits to the same TextualBody on each, cross-merge via `Y.applyUpdate`, assertion that the resulting body array has length 1 and the value is a Y.Text. This test belongs in the annotation-layer package from its first commit; without it, a future refactor could silently reintroduce the plain-object shape and the bug comes back invisibly.

### 2.4 Reading positions

Reading position is a high-churn field — it updates every few seconds of reading. Keeping it out of the annotations map prevents those updates from bloating the annotation history.

```javascript
readingPositions.set('urn:tolstoy-life:war-and-peace', {
  workUri: 'urn:tolstoy-life:war-and-peace',
  lastVersion: 'v2026-03-01-a3f5c8',
  chapterUri: 'urn:tolstoy-life:war-and-peace:book-1-chapter-3',
  selector: {
    type: 'TextPositionSelector',
    start: 15420,
    end: 15420  // zero-length range = cursor position
  },
  updated: new Date().toISOString()
})
```

Last-write-wins is fine here. The user's position on their laptop five minutes ago is more relevant than their position on their phone an hour ago. Yjs's default Y.Map semantics handle this correctly.

### 2.5 Tags

Tags are a separate concept from annotations because one tag can be applied to many annotations, and the tag itself has properties (display name, colour) that the user may edit.

```javascript
const tag = new Y.Map()
tag.set('slug', 'non-resistance')
tag.set('name', 'Non-resistance')
tag.set('colour', '#7a5c3f')
tag.set('description', 'Passages about non-resistance to evil.')
tags.set('non-resistance', tag)
```

An annotation references a tag by putting it in its body:

```javascript
body.push([
  { type: 'SpecificResource', source: 'local:tags/non-resistance' }
])
```

When the tag's colour changes, every annotation using it immediately reflects the change, because the annotation doesn't copy the tag — it points to it.

## 3. Persistence: y-indexeddb

The full Y.Doc persists to IndexedDB via y-indexeddb. This is the whole persistence story on the local side:

```javascript
import * as Y from 'yjs'
import { IndexeddbPersistence } from 'y-indexeddb'

const ydoc = new Y.Doc()
const persistence = new IndexeddbPersistence('tolstoy-life-annotations', ydoc)

persistence.on('synced', () => {
  // Local IndexedDB has loaded into the Y.Doc.
  // Safe to render the UI now.
})
```

The IndexedDB database created by y-indexeddb stores Yjs updates, not parsed annotations. Querying "all annotations on *War and Peace*" is done against the Y.Doc in memory, not against IndexedDB directly.

### 3.1 When the annotation set grows large

For a typical reader with a few hundred annotations, the whole Y.Doc fits comfortably in memory. For power users with tens of thousands, two strategies:

1. **Incremental loading.** y-indexeddb already loads in the background and emits `synced` when done. The UI should work with a partial Y.Doc, rendering what's loaded and filling in as more arrives.
2. **Secondary index in IndexedDB.** In parallel with the Y.Doc, maintain a plain IndexedDB object store indexed by work URI. When the Y.Doc observes a change, update the index. Queries like "all annotations on *War and Peace*" hit the index first, then pull full annotations from the Y.Doc only for the matching IDs.

The secondary index is a Stage 5 concern. Stage 3 and Stage 4 can scan the Y.Doc directly.

## 4. The sync relay

### 4.1 What it is

A Cloudflare Worker that accepts WebSocket connections from clients and relays Yjs updates between them. It uses Durable Objects to maintain per-room state, where "room" means "one user's annotation set".

**Implementation: y-durableobjects-style, not Node y-websocket-server.** The reference implementation follows the open-source `y-durableobjects` pattern: each room is a Durable Object instance that handles WebSocket connections for that room directly (via Cloudflare's `hibernatable WebSockets`), stores the compacted Yjs state in Durable Object storage, and forwards updates between clients without running any Node process. This gives the relay global edge distribution, hibernation-based billing (no idle cost for inactive rooms), and no servers to maintain. The alternative — running Node y-websocket-server on a VPS — trades these properties for a more familiar stack and is rejected.

The Worker + per-room Durable Object is around 150-200 lines of TypeScript.

### 4.2 What it is not

- Not a parser of user data.
- Not an authoritative store of annotations.
- Not a conflict resolver.
- Not an access-control system beyond "do you have the room key?"

### 4.3 Authentication model

A user's annotation set is identified by a room ID — a UUID. Knowledge of the room ID plus a shared secret (the "sync key") is sufficient to connect. No accounts, no email, no passwords.

The sync key is generated on first device setup and transferred to additional devices via the pairing flow in §6. The key never leaves the user's devices; the relay only sees HMACs of messages signed with the key, which lets it verify connection attempts without learning the key itself.

### 4.3.1 Threat model and what this does not protect against

The "the server never parses user data" property (§1, rule 1) is an integrity-of-design claim, not a cryptographic guarantee. In the default Stage-4 design, Yjs update blobs are opaque to a casual observer but **not encrypted at rest**. A reader should understand the threat model precisely:

- **Protected against:** accidental leaks in relay logs, server operators casually browsing data, subpoena-level requests that ask "what is user X reading" (there is no user X; there is an opaque blob in room Y).
- **Not protected against:** a motivated adversary with access to the Durable Object storage *and* knowledge of the Yjs wire format. Yjs blobs are a documented format; parsing them without the sync key is tedious but not cryptographic.
- **Elevated protection via opt-in encryption-at-rest:** Stage 4+ adds client-side symmetric encryption of every update blob with the sync key before upload, using an AEAD cipher (AES-GCM with a per-update nonce). With this enabled, the relay stores ciphertext that is infeasible to decrypt without the sync key. This is the recommended default once the encryption path is implemented.

The UI is honest about this: settings shows "End-to-end encryption: on / off" with a one-line explanation. The goal is that a user who reads the setting knows what they're getting.

### 4.4 Message flow

```
client A                  relay (CF Worker)              client B
   |                              |                          |
   |---[connect, roomId, HMAC]--->|                          |
   |<---[connected]---------------|                          |
   |                              |<---[connect, HMAC]-------|
   |                              |-->[connected]----------->|
   |                              |                          |
   |---[sync step 1, state]------>|                          |
   |<---[sync step 2, update]-----|                          |
   |                              |<---[sync step 1, state]--|
   |                              |-->[sync step 2, update]->|
   |                              |                          |
   |---[update blob]------------->|-->[update blob]--------->|
   |<---[update blob]-------------|<---[update blob]---------|
```

Every update is a Yjs binary encoding. The relay forwards it to all other connected clients in the same room and stores it in the Durable Object's state for clients that connect later.

### 4.5 Storage on the relay

The Durable Object for a room keeps:

- A merged Yjs state (the full update history compressed into a single blob, refreshed periodically — typically when the in-memory update log reaches ~100 entries or 30 minutes pass).
- The last update timestamp (for quota pruning).
- A count of connected clients.
- A device ID list (opaque per-device tokens; see §4.7).

That's it. No user ID, no email, no annotation content in parseable form. A subpoena of the relay's data would reveal: N rooms exist, each containing binary CRDT blobs of sizes X, Y, Z. It could not reveal what anyone was reading or annotating (and with encryption-at-rest enabled, §4.3.1, even the blob structure is opaque).

### 4.6 Quotas and pruning

A sensible policy: rooms with no connection for 90 days are flagged; after 180 days they're pruned unless the user has opted for longer retention. Users should be able to see how much relay storage their account uses and explicitly extend retention or download their state for safekeeping.

This is important: the relay is a *courier*, not a storage guarantee. The user's devices are the authoritative copy. The relay going away — which it should be able to, without tragedy — means users fall back to local-only mode, which is the mode they started in.

### 4.7 Device list and revocation

Each paired device gets a unique 128-bit device ID issued during pairing (not derived from any device-identifying property — it's a fresh random value). The Durable Object maintains the set of authorized device IDs for the room.

A connecting client supplies its device ID alongside the HMAC. The relay refuses connections from device IDs not in the room's authorized set.

This enables device management:

- Settings → "Synced devices" lists every paired device with a friendly name (chosen by the user at pairing time, e.g., "iPhone", "Work laptop"), the date it was paired, and a "Remove" action.
- Removing a device deletes its device ID from the Durable Object's authorized set. The removed device can no longer connect; if it tries, it falls back cleanly to local-only mode.
- A new pairing generates a new device ID and adds it to the set. The old device's ID stays authorized.
- The full device list is itself stored in the Y.Doc's `preferences` map so all devices see a consistent view; the relay's authorized set is the *enforcement* copy, kept in sync by the device-list owner (the device that initiates each pairing or revocation).

Revocation is immediate from the relay's perspective. Any update the revoked device made before revocation is still in the Y.Doc on other devices — that's how CRDTs work; the relay revokes future *connections*, not past *content*.

### 4.8 Key rotation

If a user suspects their sync key is compromised (e.g., a stolen device they couldn't remotely revoke before it synced):

1. From a device they still control, settings → "Rotate sync key".
2. The device generates a new sync key and a new room ID.
3. It re-encrypts the current Y.Doc state with the new key (if encryption-at-rest is on) and uploads it to the new room.
4. It updates its own local sync key + room ID.
5. All other still-trusted devices need to be re-paired using the new key (the user is told this explicitly).
6. The old room is left to be pruned by the §4.6 inactivity policy.

This is a deliberate, manual flow. There is no automatic rotation — the user knows when they want to rotate and why.

## 5. Connection lifecycle

```javascript
import { WebsocketProvider } from 'y-websocket'

const provider = new WebsocketProvider(
  'wss://sync.tolstoy.life',
  roomId,
  ydoc,
  {
    params: { hmac: computeHmac(syncKey, connectNonce) }
  }
)

provider.on('status', ({ status }) => {
  // 'connecting' | 'connected' | 'disconnected'
  // Show appropriate UI, but never block the user.
})

provider.on('sync', (isSynced) => {
  if (isSynced) {
    // Peer has sent us all updates we didn't have.
    // Local state is now at least as fresh as the peer's.
  }
})
```

The WebSocket provider runs alongside y-indexeddb. Writes go to the Y.Doc, y-indexeddb persists them locally, and the WebSocket provider broadcasts them to peers. If the WebSocket is disconnected, everything else keeps working. When it reconnects, Yjs's sync protocol reconciles missing updates both ways.

## 6. Pairing flow for a new device

### 6.1 Happy path: QR code

1. Device A (already set up) navigates to Settings → Pair a device.
2. It generates a fresh device ID for device B, signs an expiring pairing payload with the sync key, and displays a QR code encoding the URL described in §6.2.
3. Device B scans the QR code (via the browser's `BarcodeDetector` API or a hosted decoder fallback if `BarcodeDetector` is unavailable — see §6.3).
4. Device B follows the URL, which opens the PWA (already installed via the same origin) and initiates the pairing handshake.
5. Device A and device B exchange a confirmation through the relay (so that an attacker who somehow obtained the QR can't silently pair without device A noticing).
6. Device B stores the roomId, sync key, and assigned device ID in its local secure storage.
7. Device A adds device B to the authorized device set on the relay (§4.7).
8. Device B connects to the relay and syncs.

The QR code is valid for five minutes. After that it expires (the `exp` parameter, §6.2) and a new one must be generated. This mitigates the "user screenshots QR code, leaves it on desktop forever" risk.

### 6.2 The pairing URL scheme

The QR encodes a URL to the live origin so a scanned code can be opened by any browser:

```
https://tolstoy.life/pair#room=<roomId>&key=<base64url-syncKey>&did=<deviceId>&exp=<unix-timestamp>&sig=<hmac>
```

Properties of this scheme:

- **All sensitive material is in the URL fragment** (after `#`). Browsers do not transmit fragments to servers, so even though the URL hits `tolstoy.life`, the origin's logs see only `/pair` — never the room ID, sync key, device ID, expiry, or signature.
- **No new domain to whitelist.** Camera apps, browser scanners, and OS-level QR readers all open `https://` URLs without prompting for permission to a strange custom scheme.
- **The PWA installed from this origin can register a handler for `/pair`** so scanning the code opens the app directly when installed, falls back to the website otherwise.
- **`sig` is an HMAC-SHA-256 of the other parameters**, signed with the sync key. The receiving device verifies the signature before importing — so an injected malicious URL with a different room ID can't trick the user into pairing into someone else's room.

### 6.3 Fallback: BIP-39 six-word phrase

`BarcodeDetector` is not available in Firefox and was only enabled by default in Safari 17. For browsers without it — and for any time the user doesn't want to use a camera (e.g., they are pairing two devices in two different physical locations over a phone call) — the pairing flow falls back to a six-word BIP-39 phrase:

1. Device A displays six words from the BIP-39 English wordlist (e.g., `tribe vintage forum patient nominee piano`).
2. Device B has a six-input field and the user types the words.
3. The six-word phrase encodes a one-time pairing token (66 bits — well above brute-force reach for a five-minute window) that device B presents to device A through the relay; once device A confirms it, the same handshake as §6.1 step 5 onwards completes.

The wordlist is BIP-39 because it's well-tested, has high redundancy (no two words share a prefix), and is widely localised (a future Russian, Spanish, or French interface gets the same UX automatically).

The phrase fallback is exposed prominently in the Pair-a-device UI — it's not a hidden last-resort; it's a peer of the QR code option.

### 6.4 Recovery when all devices are lost

With no account system, losing all devices means losing access to the sync key. Mitigations, in increasing strength of trade-off against the no-account principle:

- **Explicit backup (default).** Settings → Export sync key. Saves a plain text file the user can put in a password manager, a safe-deposit box, or a paper wallet. The export bundle includes the room ID, the sync key, and the BIP-39 phrase form of the key for paper resilience.
- **Encrypted backup to a user-controlled URL (opt-in).** Settings → "Back up my annotations to my own server". The user provides a writeable URL (their own server, an S3 bucket, a Nextcloud share, etc.) and a passphrase. The PWA uploads an encrypted snapshot of the Y.Doc plus the sync key wrapped under the passphrase. Recovery is by re-installing the PWA, supplying the URL and passphrase, and pulling the snapshot back. The relay is not involved. Anthropic's word for this elsewhere is "bring-your-own-storage"; in this design it deliberately does not introduce a Tolstoy-operated storage service.
- **Optional email recovery (opt-in, reluctantly).** A user who wants the simplest possible recovery story can associate an email with their room and use magic-link authentication. This moves the user away from "no accounts" but is fully opt-in and visible in settings. Where possible the magic-link verifier runs on the same Cloudflare Worker so no third-party email service is in the trust path.

The trade-off is stated clearly in settings: "We don't have your annotations on our servers in a form we can read. If you lose every device and you've made no backup, your data is gone. This is a property of the system, not a bug."

## 7. What this costs to run

Rough back-of-envelope for hosting the sync relay:

- Cloudflare Workers free tier: 100,000 requests per day. Each sync session might be a few hundred messages.
- Durable Objects: free tier covers low thousands of rooms.
- Realistically, until the project has thousands of active synced readers, this fits in the free tier.

At scale, the cost scales linearly with active users and is bounded. There's no surprise cost growth because the relay doesn't do any work beyond forwarding bytes.

## 8. Resolved decisions

Captured here so the design intent is explicit (these were the open questions in earlier drafts):

1. **Y.Text for TextualBody value; Y.Map for every body item.** Decision: the `body` Y.Array contains `Y.Map` entries (not plain objects), and any `TextualBody` item's `value` is a `Y.Text` (not a plain string). Concurrent edits to the same note therefore merge at character level — an interleaved-but-visible result — rather than producing the silent duplicate that a Y.Array of plain objects would produce (see §2.3 for the failure-mode walk-through). JSON-LD wire shape is unchanged: Y.Text projects to a plain string on export.
2. **HMAC vs JWT for connection auth.** Decision: HMAC-SHA-256. The relay only needs to verify "did you sign with the room's sync key", not parse capabilities.
3. **Single Y.Doc vs per-work sub-docs.** Decision: one Y.Doc per user. Add sub-doc partitioning only if real users hit performance walls.
4. **Relay endpoint discovery.** Decision: hardcoded `wss://sync.tolstoy.life` in build, overridable via preferences for self-hosters.
5. **Encryption at rest on the relay.** Decision: ship Stage 4 with opt-in encryption-at-rest (§4.3.1). Default it on once the implementation has stabilised on the three target browsers.
6. **Relay implementation.** Decision: Cloudflare Worker + Durable Object per room, following the `y-durableobjects` pattern, hibernatable WebSockets. Not a Node y-websocket-server. (§4.1)
7. **Pairing URL scheme.** Decision: fragment-based URL on the live origin (§6.2). All sensitive material in the fragment so the origin's logs see only `/pair`.
8. **No-camera fallback.** Decision: BIP-39 six-word phrase (§6.3), exposed as a peer of the QR option, not a buried last resort.
9. **Recovery options.** Decision: explicit sync-key export (default), encrypted-backup-to-user-URL (opt-in), email-magic-link (opt-in, reluctant). No always-on cloud backup.
10. **Device list and revocation.** Decision: per-device IDs maintained in the Durable Object; Settings → "Synced devices" shows and removes (§4.7).
11. **Key rotation.** Decision: explicit, manual, user-initiated; new room ID + new key; old room left to inactivity-prune (§4.8).

## 9. Remaining questions for `/ultraplan`

1. What's the right cadence for merging the in-memory update log into a snapshot in the Durable Object? Current intuition: every ~100 updates or every 30 minutes, whichever first. Confirm against `y-durableobjects` reference numbers.
2. The pairing handshake (§6.1 step 5) requires the relay to ferry one round-trip between the two devices before authorization completes. What is the message format and does it need to be in-band on the WebSocket protocol or out-of-band over a separate HTTP endpoint?
3. For the encrypted-backup-to-user-URL recovery option, what is the snapshot format (raw Y.Doc state vs JSON-LD export of annotations)? Trade-off: raw is smaller and exact; JSON-LD is portable to other systems but loses CRDT history.
4. Should the device's friendly name be set on device A (the inviter) or device B (the joiner)? Either works; the choice affects UX.

## 10. Summary

- One Y.Doc per user, with five top-level maps (annotations, workMeta, readingPositions, tags, preferences).
- Each annotation is a Y.Map using the W3C Web Annotation shape.
- y-indexeddb handles local persistence.
- y-websocket connects to a Cloudflare Worker + Durable Object relay (`y-durableobjects` pattern, hibernatable WebSockets) that stores opaque CRDT blobs, with opt-in client-side AEAD encryption-at-rest.
- Pairing between devices uses a fragment-based URL QR code or a BIP-39 six-word phrase, with a confirmation handshake; HMAC for connection auth; per-device IDs for revocation.
- Recovery is sync-key export by default, encrypted-backup-to-user-URL or email magic link as opt-in alternatives.
- The server is a courier; the user's devices are the source of truth.

The whole sync layer, from local storage to pairing and recovery, fits in around 600 lines of client code plus 150–200 lines of TypeScript on the Worker side. Yjs does the hard work.
