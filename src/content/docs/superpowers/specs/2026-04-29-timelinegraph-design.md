# timelinegraph — Design Spec

A 2D knowledge-graph visualisation of Tolstoy's universe, intended for the landing page of [tolstoy.life](https://tolstoy.life). Combines a horizontal multi-lane timeline spine with an orbital cloud of related entities; uses Tolstoy's lifespan (1828–1910), divided into the four canonical periods, as the visual frame.

This spec is the output of two research rounds (see [`projects/timelinegraph/RESEARCH.md`](../../../projects/timelinegraph/RESEARCH.md)) plus a structured brainstorming pass. It locks in the v1 design and serves as input to the implementation plan.

---

## 1. Decisions locked in

| # | Decision | Choice |
|---|---|---|
| 1 | v1 staging | Build privately, ship publicly when corpus passes ~200 nodes |
| 2 | Primary task | Visitor exploration of Tolstoy's universe |
| 3 | Entity scope | All wiki types (person, place, event, concept, translator, institution, adaptation, criticalWork, archivalFond) + works + (eventually) letters; sidebar type filters; default all on |
| 4 | Edge model | Typed by relationship (frontmatter `relatedArticles`, `relatedWorks` with `relationshipType`, body `[[wikilinks]]`); colour/style encodes type |
| 5 | Focus model | Tolstoy default + URL-controlled focus param (`/graph/?focus=anna-karenina`) |
| 6 | Layout | Horizontal multi-lane spine + orbital cloud (NOT radial-around-Tolstoy) |
| 7 | Lanes | Works · Family Events · Historical Events · (Letters lane planned, deferred until corpus exists) |
| 8 | Cloud positioning | Above + below spine; time-anchored where dates exist |
| 9 | Lifespan band | Four colored period zones (Green / Red / Amber / Blue) with vertical guidelines at transitions; pre/post zones subdued gray |
| 10 | Tolstoy representation | The colored band IS him; family-event nodes deep-link to anchored sections of his wiki page (e.g. `/wiki/leo-tolstoy/#starting-university`) |
| 11 | Hover | Small floating stub-preview card (wikilink-style peek) |
| 12 | Click | Opens larger modal with full stub; click modal again → navigate; click outside → close |
| 13 | Zoom semantics | Zoom = time resolution (decades → years → months → days); reveals more nodes near cursor |
| 14 | No draggable brush | Zoom IS the time filter |

---

## 2. Architecture

A single Eleventy page (`website/src/pages/graph.njk`, served at `/graph/`), implemented as a vanilla-ES-module JavaScript bundle.

Two stacked render layers, one shared data model, one shared coordinate system:

```
┌─────────────────────────────────────────────────┐
│   D3 SVG layer (top, transparent over PIXI)     │
│   • Spine axis (years), period zones,           │
│     vertical period dividers, period labels     │
│   • Lane backgrounds                            │
│   • Work bars + event points                    │
│   • Hover stub card                             │
│   • Click modal                                 │
│   • Sidebar UI (type filters)                   │
├─────────────────────────────────────────────────┤
│   PIXI.js v8 WebGL canvas (bottom)              │
│   • Cloud nodes (bloom-filtered sprites)        │
│   • Cloud edges (typed by relationship)         │
│   • Parallax starfield                          │
│   • Edge-flow particles (deferred — post-v1)    │
└─────────────────────────────────────────────────┘
```

Both layers share:

- A **graphology** graph instance (single source of truth for nodes + edges).
- A **D3 zoom transform** representing the current time window. Both layers project from `(date, force_y) → (pixel_x, pixel_y)` using the same shared `timeScale`.
- A **focus state** (currently-focused entity ID, sourced from URL param or default `leo-tolstoy`).

The page is fully static — no backend, no runtime queries. All data ships as a JSON artifact built at Eleventy build time.

The bundle is `assets/graph/main.mjs`. No framework. Bundling step (esbuild or rollup) chosen to match what `website/` already uses.

**Two-layer rationale:** SVG is best for axes / text / accessibility / interactivity. WebGL is best for many sprites with bloom effects. Each layer does what its tech is good at.

---

## 3. Components

```
assets/graph/
├── main.mjs                 ← entry: wires everything, mounts to DOM
├── data/
│   ├── load.mjs             ← fetch + parse graph.json into graphology
│   └── types.mjs            ← shared type definitions (nodes, edges)
├── scale/
│   └── timeScale.mjs        ← shared d3.scaleTime + zoom transform math
├── spine/
│   ├── axis.mjs             ← year ticks, period zones, period dividers + labels
│   ├── lanes.mjs            ← lane backgrounds + lane labels
│   └── items.mjs            ← work bars + event points; hover/click handlers
├── cloud/
│   ├── physics.mjs          ← d3-force (forceX/Y/Link/Collide)
│   ├── render.mjs           ← PIXI sprites, bloom filter, edges
│   └── starfield.mjs        ← parallax background layer
├── interact/
│   ├── zoom.mjs             ← scroll-wheel handler; updates timeScale
│   ├── hover.mjs            ← stub-preview tooltip rendering
│   ├── modal.mjs            ← click modal: open/close state, click-out-to-close, Esc handler
│   └── route.mjs            ← URL focus param handling
├── ui/
│   ├── sidebar.mjs          ← entity-type filter checkboxes + reset button
│   └── stub.mjs             ← shared stub-card content (hover and modal both render this)
└── index.css                ← styles for SVG layer + UI chrome
```

### Module responsibilities

- **`load.mjs`** — fetches `graph.json` and `wiki-previews-*.json`, validates shapes, populates a graphology instance, returns it joined with stub data.
- **`timeScale.mjs`** — owns the `(date) → (pixel_x)` transform and the current zoom state. Other modules subscribe to changes.
- **`spine/axis.mjs`** — draws the time axis ticks (resolution adapts to zoom: decades → years → months → days), the four colored period zones (Youth/Soldier/Great Works/Prophet), the vertical period-transition guidelines (1851 / 1862 / 1880), the period labels, and the subdued pre-1828 / post-1910 grey zones.
- **`spine/lanes.mjs`** — draws horizontal lane bands and lane labels (Works / Family / History / Letters).
- **`spine/items.mjs`** — places work bars (start-of-writing → publication) and event points on the lanes. Wires hover and click events.
- **`cloud/physics.mjs`** — runs the d3-force loop. Anchors nodes to time via `forceX(node => timeScale(node.dates.primary))`. Force-pulls cloud nodes away from the spine band via `forceY`. `forceLink` for edges. `forceCollide` for spacing.
- **`cloud/render.mjs`** — every animation tick, syncs PIXI sprite positions to physics state. Owns the `AdvancedBloomFilter`.
- **`cloud/starfield.mjs`** — three-layer parallax background. Drift speed scales with zoom-pan, not real time.
- **`interact/zoom.mjs`** — scroll-wheel handler. Updates `timeScale` zoom transform. Notifies subscribers (`axis`, `items`, `physics`, `cloud render`, `starfield`).
- **`interact/hover.mjs`** — picks up hover events from both layers, renders a small floating stub card following the cursor (8px offset, snaps inside viewport).
- **`interact/modal.mjs`** — picks up click events from both layers, opens a larger centered modal, owns open/close state. Click anywhere on modal content → navigate (using the entity's `wikiUrl`, plus `#anchor` fragment for family events). Click outside modal or Esc → close. Click another node while a modal is open → swap to the new node's modal (no need to close first).
- **`interact/route.mjs`** — reads `?focus=` on load, listens for `popstate`, exposes `setFocus(id)` API, updates URL via `history.replaceState`.
- **`ui/sidebar.mjs`** — checkbox list of entity types; toggles set a `visibleTypes` Set; physics + render react. "Reset" button: clears focus, restores all type filters, resets zoom to full lifespan view.
- **`ui/stub.mjs`** — shared stub-card content (rendered identically into hover tooltip and click modal, just at different sizes / detail levels). Sources content from the existing `wiki-previews-*.json` bundle.

### Module boundaries

- Modules communicate via a small **event bus** (mitt-style): `zoom:change`, `focus:change`, `filter:change`, `hover:enter`, `hover:leave`, `node:click`, `modal:open`, `modal:close`. No module imports another module's internal state.
- The graphology instance and `timeScale` are passed in at construction; modules don't reach for globals.
- Each module file should stay under ~200 lines. Growth past that is a signal it's doing too much.

---

## 4. Data pipeline

The viz consumes a single build-time JSON artifact: `graph.json`, built by a Node script that runs as a pre-build step inside the existing Eleventy chain (precedent: `website/.github/scripts/validate-frontmatter.mjs`).

```
website/src/wiki/*.md       ─┐
website/src/works/**/*.md   ─┼─→  build-graph.mjs  ─→  graph.json
website/src/letters/*.md    ─┘    (pre-Eleventy)        (passthrough-copied
                                                         to /assets/graph/data/)
                                                              │
                                            ┌─────────────────┘
wiki-previews-v<date>-<hash>.json ──────────┤    runtime: viz fetches both
(existing Layer-1 artifact)                 ┘
```

### Pipeline rules

- **Script location:** `website/scripts/build-graph.mjs`. Node, ES module, follows existing JS conventions.
- **Trigger:** runs as a `prebuild` npm script. Also runnable standalone (`npm run build:graph`).
- **Output:** `website/src/_data/graph.json` (Eleventy data cascade) AND passthrough-copied to `/assets/graph/data/graph.json` for runtime fetch.
- **Stub data is NOT duplicated.** `graph.json` contains a `stubKey` per node pointing into `wiki-previews-*.json`. Viz fetches both at load and joins them.
- **No new Python dependency.** Layer 1 (Python) keeps producing `wiki-previews-*.json`. The graph artifact is its sibling, maintained in Node.

### `graph.json` shape

```json
{
  "version": "1.0",
  "generatedAt": "2026-04-29T12:00:00Z",
  "stats": { "nodeCount": 29, "edgeCount": 84 },

  "nodes": [
    {
      "id": "leo-tolstoy",
      "type": "person",
      "title": "Leo Tolstoy",
      "dates": { "primary": "1828-09-09", "end": "1910-11-20", "approximate": false },
      "lane": null,
      "stubKey": "leo-tolstoy",
      "wikiUrl": "/wiki/leo-tolstoy/",
      "metrics": { "degree": 14, "bfsFromTolstoy": 0 }
    },
    {
      "id": "war-and-peace",
      "type": "work",
      "title": "War and Peace",
      "dates": { "primary": "1863-01-01", "end": "1869-01-01", "approximate": true },
      "lane": "works",
      "period": "great-works",
      "stubKey": "war-and-peace",
      "wikiUrl": "/works/fiction/war-and-peace/",
      "metrics": { "degree": 12, "bfsFromTolstoy": 1 }
    }
  ],

  "edges": [
    { "source": "leo-tolstoy", "target": "war-and-peace", "type": "author", "provenance": "frontmatter" },
    { "source": "sophia-tolstaya", "target": "war-and-peace", "type": "transcriber", "provenance": "frontmatter" }
  ]
}
```

### Field rules

- **`dates.primary`** — X-anchor on the spine. People: `birthDate`. Works: `dateAuthored` (start of writing). Events: the event date.
- **`dates.end`** — optional. People: `deathDate` (visual extension; doesn't change anchor). Works: `dateFirstPublished` (makes work render as a bar). Events: usually omitted.
- **`lane`** — `"works"` | `"family"` | `"history"` | `"letters"` | `null`. Determines whether entity renders on the spine or in the cloud:
  - `type: work` → `"works"`
  - `type: event` + `scope: family` → `"family"` (note: schema may need `scope` field added — flag for content team)
  - `type: event` + `scope: external` → `"history"`
  - everything else → `null` (cloud)
- **`period`** — for entities on the `works` lane only: `"youth"` | `"soldier"` | `"great-works"` | `"prophet"`. Computed from `dates.primary` falling within period bounds. Drives bar colour.
- **`stubKey`** — key into `wiki-previews-*.json`. Identical to `id` in 99% of cases.
- **`metrics.degree`** — node degree (used for LOD: hide low-degree nodes when zoomed out).
- **`metrics.bfsFromTolstoy`** — graph distance from `leo-tolstoy`. Used to dim/hide irrelevant clusters as corpus grows.

### Special case: the `leo-tolstoy` node

The `leo-tolstoy` node is **always present** in `nodes` (anchors edges, supports BFS, drives metrics). The renderer special-cases his ID and **draws no sprite for him on the cloud or the spine**: the four colored period zones ARE his visual representation. He's in the data model, not in the visible graph. Clicking anywhere on the period band does nothing; visitors reach his wiki page through family-event nodes (which deep-link to anchored sections of `/wiki/leo-tolstoy/`).

### Edge types (controlled vocab)

| Type | Source | Visual encoding |
|---|---|---|
| `author` | `relatedWorks.relationshipType: author` | gold solid line |
| `transcriber` | `relatedWorks.relationshipType: transcriber` | silver solid |
| `editor` / `translator` / `publisher` | `relatedWorks.relationshipType: editor` etc. | varied solid |
| `related` | `relatedArticles` (untyped) | white thin solid |
| `mention` | body `[[wikilink]]`, no frontmatter pair | white thin dashed |

### Build script edge cases

| Condition | Behavior |
|---|---|
| Malformed YAML | Warn with file path, skip file. `--strict` flag fails build. |
| Wikilink resolves to nothing | Warn once per dangling target, drop edge. |
| Frontmatter + body wikilink for same pair | Frontmatter wins; provenance recorded as `frontmatter`. |
| Self-loop wikilink (page → itself) | Skip silently. |
| Pre-1918 dates | `birthDate` (NS) is canonical; OS ignored for the viz. |
| Approximate dates | `dates.approximate: true`. Visual encoding (§5) fades the bar/point edges. |
| Missing required `id` | Fail build. Should be caught upstream by `validate-frontmatter.mjs`. |
| Duplicate `id` | Fail build. Data corruption. |
| Date in unsupported format | Warn, set `dates.primary: null` (cloud), continue. |

The script writes a `graph.build.log` alongside the output so warnings are auditable without re-running.

---

## 5. Interaction & visual spec

### Viewport layout

```
┌────────┬───────────────────────────────────────────────┐
│ FILTER │  CLOUD (above)                                │
│ TYPES  │     • •  •     •                              │
│        │   •     •  •      • •                         │
│ ☑ Person│   ⎯⎯⎯ pre-1828 (gray) ⎯⎯⎯|═══ Y ║║ S ║║ G ║║ P ═══|⎯⎯ post-1910 ⎯⎯
│ ☑ Place│   Works:    ⎯⎯⎯[War & Peace ━━]⎯⎯[Anna Karenina ━]⎯⎯       │
│ ☑ Work │   Family:   ●        ●  ●  ●              ●   ●              │
│ ☑ Event│   History:  ●           ●          ●        ●                │
│ ☑ Conc │   Letters:  (deferred until corpus exists)                   │
│ ☐ ...  │   ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
│        │  CLOUD (below)                                │
│ Reset  │     •  •      •     •                         │
│        │   •     • •     •  •                          │
└────────┴───────────────────────────────────────────────┘

Y = Youth (1828–1851) · S = Soldier (1851–1862) · G = Great Works (1862–1880) · P = Prophet (1880–1910)
║║ = vertical period-transition guidelines
```

- **Sidebar:** left, fixed ~180px wide, collapsible on mobile.
- **Spine block:** vertically centered, ~200px tall (4 lanes × 50px). Lane labels at left edge.
- **Cloud:** fills remaining vertical above and below the spine.
- **Background:** deep blue-black `#0a0e1a`. Three-layer parallax starfield.

### Period colour integration

The four-period system from [`docs/design/period-colours-research.md`](../../design/period-colours-research.md) is the spine's visual identity.

| Period | Years | Colour | Hex |
|---|---|---|---|
| I — Youth & Formation | 1828–1851 | Green | `#4A7C59` |
| II — The Soldier & Sinner | 1851–1862 | Red | `#B83232` |
| III — The Great Works | 1862–1880 | Amber | `#C8860A` |
| IV — The Prophet | 1880–1910 | Blue | `#2B5F8E` |

- **Lifespan band** splits into four sequential colored zones, each rendered as a soft overlay (~12% opacity) covering the spine's full vertical extent across all lanes.
- **Pre-1828 and post-1910** zones use cool gray (rgba 50/50/60/0.20).
- **Period transitions** (1851 / 1862 / 1880) render as faint vertical guidelines across all lanes (base color at 25% opacity, 1px wide). Small period labels above the spine ("Youth", "Soldier", "Great Works", "Prophet") are always visible at any zoom.
- **Work bars** inherit the colour of the period they were written in. *War and Peace* (1863–1869) → Amber. *The Kingdom of God Is Within You* (1893) → Blue. Bar fill: period base lightened ~65%; border + bloom: period base at 100%.
- **Cloud entities** (people, places, concepts) keep type-based colours (provisional palette below — designer pass needed before public launch). They live across periods, so don't carry period colour.

**Provisional cloud-type palette** (designer pass needed):
person `#f4ebd5` · work `#d4a85e` · place `#a8c4a1` · event `#ec8853` · concept `#c2b1d1` · translator `#d4a8b5` · institution `#8a99a8` · adaptation `#b88a99` · criticalWork `#e6dcb5` · archivalFond `#a89a85`.

### Visual encoding

- **Cloud nodes:** filled circles, radius `8 + log₂(degree+1) × 2` px. PIXI `AdvancedBloomFilter` halo.
- **Spine work bars:** rounded rectangles, height 24px, period-coloured.
- **Spine event points:** filled circles 10px, color = lane (family vs history).
- **Edges:** colored by relationship type per §4 table, opacity `0.6 − bfsFromTolstoy × 0.1`. Frontmatter edges solid; body-wikilink-only edges dashed.

### Redundant encoding rule

Per `docs/design/period-colours-research.md`: colour is never the only signal. Every coloured element carries at least one secondary signal:

- Period zones — colour + label
- Work bars — colour + bar shape + title text + lane position
- Cloud nodes — colour + node shape (we may differentiate types by shape for colour-blind robustness; designer pass)
- Edges — colour + line style (solid/dashed) + thickness
- Period transitions — colour shift + vertical guideline + label

Johan has deuteranopia and is the primary reviewer for the red-green boundary at 1851. Period labels make the meaning unambiguous; the *aesthetic* of the transition needs eyes-on validation before prototype 02 ships.

### Dark-background tints

- **Spine zones** — base colour at 12% opacity over dark canvas.
- **Work bars** — fill: base lightened ~65% (e.g. amber `#C8860A` → `#EBC780`); border + bloom: base at 100%.
- **Period dividers** — base at 25% opacity, 1px wide.
- **Period labels** — base at 90%, small caps, ~12pt.

### Interactions

| Input | Effect |
|---|---|
| **Hover** (cloud or spine) | Small floating stub card follows cursor (8px offset, snaps to viewport). Card shows: title, type chip, dates, 1-line description. |
| **Click on a node** | Opens larger centered modal with full stub. Modal content: title, type chip, dates, full description, related entities, "click anywhere on this card to open the full article" hint. **Modal has no explicit close (X) button** — close affordances are click-outside, Esc, or clicking another node (which swaps in that node's modal). Keeping the modal small lets the cursor reach outside it easily. |
| **Click on the open modal** | Navigate to entity's `wikiUrl` (same tab). Family-event modals use `#anchor` fragment for deep section linking. |
| **Click outside modal** | Close, no navigation. |
| **Esc** | Close modal. |
| **Click another node while modal is open** | Swap to the new node's modal. No need to close first. |
| **Scroll wheel up / pinch out** | Zoom in: time window narrows. Resolution shifts decade → year → month → day with depth. More cloud nodes near cursor become visible (LOD culls hide low-degree nodes when zoomed out). |
| **Scroll wheel down / pinch in** | Zoom out. |
| **Click and drag (on empty space)** | Pan around the universe in 2D. Horizontal pan moves through time (same as panning the time scale). Vertical pan reveals more of the cloud above or below the current view. The two axes are independent. A drag-distance threshold (~5px) distinguishes pan from click — below the threshold the gesture is treated as a click on whatever was under the cursor; above, as a pan and any node-click is ignored. |
| **Reset button (sidebar)** | Reset zoom to full lifespan view, clear URL focus param, restore all type filters. |
| **Sidebar checkbox toggle** | Hide/show all entities of that type — both cloud and spine. |
| **URL `?focus=anna-karenina` on load** | Zoom transform animates to entity's date range; entity briefly highlights (1-second pulse); modal auto-opens. |

### Out of scope for v1

- Full-text search inside the viz (sidebar type filter is the only finding affordance for v1).
- Edge-flow particles (deferred — interesting but not blocking).
- Audio / cinematic intro animation.
- Saved custom views / "tour" feature.
- Keyboard navigation through the graph (screen-reader fallback covers basic accessibility — see §6).

---

## 6. Error handling

### Build-time (`build-graph.mjs`)

See §4 "Build script edge cases" table. Behavior summary: warn-and-continue for soft errors, fail-build for data integrity violations (duplicate id, missing id), `--strict` flag escalates warnings to failures.

### Runtime (browser)

| Condition | Behavior |
|---|---|
| `graph.json` fetch fails | Render fallback message in canvas: *"Could not load Tolstoy's universe."* + Retry button. Console error. |
| `wiki-previews-*.json` fetch fails | Graph renders; hover and modal cards show *"Preview unavailable — click to read full article."* No retry. |
| WebGL not supported | Fall back to D3-only render: cloud nodes as plain SVG circles, no bloom, no starfield. Detected at boot via PIXI's `isWebGLSupported()`. |
| JS disabled | Static `<noscript>` fallback: *"This page requires JavaScript. Browse Tolstoy's universe at [Wiki](/wiki/)."* |
| Bundle parse error | `<noscript>`-equivalent visible by default; JS hides on successful boot. |
| Unhandled JS error in render loop | `window.onerror` shows fallback message. No telemetry. |

### UX edge cases

| Condition | Behavior |
|---|---|
| All filters unchecked → zero visible entities | Empty-state overlay: *"No entities match your filters."* + "Reset filters" button. |
| Only 1 visible entity | Render normally — node at its time anchor or canvas center. |
| Sparse corpus (today's 29 nodes) | Render normally. Sparse is the launch reality. |
| Dense corpus (Phase 5+ ~26k nodes) | LOD culling first (mandatory). Web-Worker offload of the force simulation is deferred to v2 — only built if v1 framerate is unacceptable at scale. Spec doesn't commit to it. |
| `?focus=nonexistent-id` | Log warning; fall back to default view. URL rewritten to remove the bad param. |
| `?focus=` with unsafe characters | URL-decode, validate against slug regex `^[a-z0-9-]+$`, reject if invalid. |
| Zoom past single-day resolution | Hard cap. |
| Zoom out past full corpus extent | Hard cap. |
| Pan past corpus extremes | Hard-stop at edges (no rubber-band). |

### Accessibility

- `prefers-reduced-motion` → disable starfield drift, snap zoom transitions instead of tweening, disable any pulse animations.
- `prefers-contrast: more` → period zones at 25% opacity instead of 12%; bloom disabled; edges thicker.
- **Screen-reader fallback** — page includes a hidden `<nav aria-label="Tolstoy's universe">` listing all currently-visible entities as wikilinks, regenerated on filter/zoom change. Lets a screen-reader user navigate the same set of entities even though the visual graph is unreadable.
- **Keyboard navigation** — out of v1 scope, flagged as v2 gap.

### Browser support

Modern evergreen (Chrome / Firefox / Safari / Edge, last 2 versions). Older browsers → static fallback.

### Performance budget

| Metric | Target |
|---|---|
| First paint | < 1.5s on broadband |
| Time-to-interactive | < 3s on broadband |
| Idle framerate | 60fps |
| Pan/zoom framerate floor | 30fps |
| Memory at full corpus | < 200MB |

Budget breach at scale → degrade gracefully (hide starfield, reduce bloom radius, raise LOD threshold) with `console.warn` documenting what was dropped.

---

## 7. Testing

### Build-script tests (mandatory)

`website/scripts/__tests__/build-graph.test.mjs`. Fast, run on every commit.

- **Unit:** YAML parsing, wikilink resolution, date normalization, edge dedup, lane assignment, period assignment, BFS metric.
- **Snapshot:** runs against `tests/fixtures/` (synthetic mini-corpus of ~10 `.md` files covering every entity type, every edge type, plus deliberate edge cases: missing date, malformed YAML, dangling wikilink, self-loop, duplicate id). Output diffed against `tests/fixtures/expected/graph.json`.
- **Schema validation:** `graph.json` validated against `scripts/graph.schema.json` after build. Fails CI on drift.

### Browser smoke tests (recommended for v1)

`website/tests/e2e/graph-smoke.spec.mjs`. Playwright, headless Chromium. Run on PRs.

- Mount: page loads, canvas appears, no console errors.
- Data: `graph.json` fetched and parsed.
- Hover: hovering a known node triggers the small stub tooltip.
- Click: clicking a node opens the larger modal (asserts modal visible, asserts URL did NOT change).
- Click modal: clicking the open modal navigates (asserts URL matches `wikiUrl`).
- Click outside: clicking outside the modal closes it without navigating.
- Filter: unchecking `person` hides all person nodes.
- Focus URL: `/graph/?focus=anna-karenina` highlights + zooms-to-range + auto-opens modal.
- Empty state: filtering everything off shows empty-state message.

Uses the same `tests/fixtures/` corpus to decouple from real wiki data.

### Visual regression (recommended for v1)

Playwright + pixel-diff. Three reference shots:

1. Default view — full lifespan, all types visible.
2. Zoomed in — 1869 ±5 years, *War and Peace* visible.
3. Filtered to `person` only.

Diffs flagged in PRs; threshold ~2% pixel delta.

### Manual QA (mandatory before public launch)

Documented checklist in `projects/timelinegraph/QA.md`:

- Aesthetic check (bloom, starfield drift, period colours, transitions).
- Period-colour validation under deuteranopia (Johan signs off — primary reviewer).
- Label legibility at all zoom levels.
- Cross-browser spot check (Chrome, Firefox, Safari, mobile Safari iPad).
- Modal behavior (open, click-to-navigate, click-out-to-close, swap-on-other-click, Esc).
- URL focus deep-link from a wiki page works end-to-end.
- Empty state actually offers a way out.

### Performance regression (deferred to public-launch readiness)

Lighthouse CI on PRs touching `assets/graph/`. Budget enforced in `lighthouserc.json`.

### Accessibility (deferred to public-launch readiness)

`axe-core` CI scan on `/graph/`. Failures block merges. Manual screen-reader spot check (VoiceOver on macOS) before public ship.

### What is NOT tested

- Cross-browser automation matrix — manual smoke is enough for v1.
- Stress test at full corpus scale — Phase 5+ concern.
- Visual diff under different OS font rendering — accept the variance.
- Network throttling beyond Lighthouse defaults.

---

## 8. Provisional / unresolved items (carried into the implementation plan)

- **Period labels** ("Youth", "Soldier", "Great Works", "Prophet") above the spine — kept for v1, may be removed after first prototype review.
- **Tolstoy entry path** — family-event nodes deep-link to anchored sections of his wiki page. Wiki page needs to actually have those anchor headings (content task, not viz task; degrades gracefully if anchors missing).
- **Cloud-type palette** — provisional values listed in §5; designer pass before public launch.
- **Color-blind validation** — Johan eyes-on the red↔green period transition (1851) before prototype 02 ships.
- **Schema gap** — `event` type may need a `scope` field (`family` | `external`) to drive lane assignment. Flag for content team.
- **Bundler choice** — esbuild vs rollup; pick to match existing `website/` build chain during the implementation plan.

---

## 9. Out of scope for v1 (explicitly deferred)

- Full-text search inside the viz.
- Edge-flow particles.
- Audio / cinematic intro animation.
- Saved custom views / "tour" feature.
- Keyboard navigation (screen-reader fallback covers basic a11y).
- Cross-browser automation matrix.
- Stress test at Phase 5+ scale.
- Public landing-page placement (deferred until corpus passes ~200 nodes).

---

## 10. References

- Two research rounds: [`projects/timelinegraph/RESEARCH.md`](../../../projects/timelinegraph/RESEARCH.md)
- Project home + prototype scaffolds: [`projects/timelinegraph/`](../../../projects/timelinegraph/)
- Period colour system: [`docs/design/period-colours-research.md`](../../design/period-colours-research.md)
- Wiki schema (entity types, frontmatter): [`website/schema/wiki-schema.md`](../../../website/schema/wiki-schema.md)
- Works schema: [`website/schema/tolstoy-works-schema.md`](../../../website/schema/tolstoy-works-schema.md)
- Project content / architecture: [`AGENTS.md`](../../../AGENTS.md)
- Closest prior art (visit and study): [Six Degrees of Francis Bacon](http://www.sixdegreesoffrancisbacon.com/) · [Kindred Britain](https://kindred.stanford.edu/) · [Mapping the Republic of Letters / Voltaire's Network](http://republicofletters.stanford.edu/publications/voltaire/letters/) · [Connected Papers](https://www.connectedpapers.com) · [Nomic Atlas](https://atlas.nomic.ai/)
