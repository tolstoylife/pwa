# Prototype 10 — Split View Design

A prototype-level design that breaks the **unified projection** model used in 07–09 (graph and time fused on a single canvas) into **separate, dedicated panels**: a pure force-directed graph on the left, a narrow vertical timeline strip in the middle, and a stub-text panel on the right. The motivation is the complexity problem flagged at the end of prototype 09 — five visual signals (period bands, lane separators, work bars, edge web, varying-size nodes) competing for attention on the same canvas. Prototype 10 separates concerns: the graph shows topology, the timeline shows time, the panel shows content, and they coordinate by selection.

This document is **not** an amendment to the canonical spec ([`2026-04-29-timelinegraph-design.md`](./2026-04-29-timelinegraph-design.md)). The canonical spec describes the unified-projection v1 design and is itself overdue for an amendment after 07–09's divergences (anisotropic Y-zoom, degree-based sizing, always-on edges, two-tier collapse). Prototype 10 is a *bigger* divergence still: graph and time become physically separate components. If 10 confirms the new direction, the canonical spec gets rewritten in a follow-up pass.

---

## 1. Decisions locked in

| # | Decision | Choice |
|---|---|---|
| 1 | Graph layout | Pure d3-force, no time bias; nodes draggable (Obsidian-style) |
| 2 | Timeline visualisation | Vertical strip, period colour bands as background, year-level → month-level → day-level zoom |
| 3 | Bidirectional graph↔timeline | A: event-marks on the timeline are clickable → select matching event-node in graph |
| 4 | Graph data | Same fake data as prototype 09 (`cloudData`, `worksData`, `extraEdges`, `familyData`, `historyData`); real wiki integration deferred |
| 5 | Right panel | Stub-only (current `desc`); "View full article" disabled with tooltip; full articles arrive with real data |
| 6 | Minor nodes | Hidden by default; reveal as a local satellite cluster around a clicked work; rest of graph stays put |
| 7 | Edges | Always-on faint web (~0.075), SVG; selection brightens incident edges (carries 09's pattern) |
| 8 | Date anchoring | Works → `[written, published]`; events → centre on `year`, span 5y; cloud entities → optional `dateRange` field, fallback centre on `year`, span 16y |
| 9 | Concept anchoring | When refining `dateRange` for concepts, prefer conception/coining year (not the person who carried it) |
| 10 | Works visual identity | Coloured by period (Youth/Soldier/Great Works/Prophet); naturally larger via degree-based sizing |
| 11 | Initial state | Welcome panel + onboarding hint in the right panel ("Click a node to explore" + colour legend) |
| 12 | Layout widths | Sidebar 168px fixed · graph flex · timeline 90px fixed · right panel 380px fixed |

---

## 2. Layout

Four-column horizontal split, all visible at once, no panels collapsible in v1.

```
┌──────────┬────────────────────────────┬──────┬──────────────┐
│ SIDEBAR  │   GRAPH (force-directed)   │ TIME │ RIGHT PANEL  │
│ 168px    │   flex: 1 (~57% @ 1500px)  │ 90px │ 380px        │
│ fixed    │                            │ fixed│ fixed        │
└──────────┴────────────────────────────┴──────┴──────────────┘
```

- Sidebar: same look as 09 — entity-type filters (person/place/source/concept/work/event), edges/labels toggles, reset button, prototype badge.
- Graph: pure force-directed d3 simulation, runs continuously.
- Timeline: narrow vertical strip with period colour bands as background.
- Right panel: stub content, no border decoration; reads as a quiet companion column.

---

## 3. Graph

### 3.1 Layout engine

- d3 `forceSimulation` with `forceManyBody` (charge), `forceLink`, `forceCollide`, `forceCenter`. No `forceX`/`forceY` — pure topology, no time bias.
- Simulation runs continuously (does not `.stop()` after warm-up like 09 did) so dragging a node ripples through the rest in real time.
- Default `alphaDecay` low enough that the layout stays "alive" but not jittery (~0.02).

### 3.2 Nodes

- ~44 in the default view: cloud (~19) + works (13) + family events (9) + history events (8). Minors hidden until a work is clicked.
- Sized by degree, reusing 09's mapping: `r = NODE_R_BASE + 1.4 × deg^0.55`, clamped 4–13px (no zoom multiplier — graph has no zoom).
- Coloured:
  - **Works** → period colour (Youth `#4A7C59`, Soldier `#B83232`, Great Works `#C8860A`, Prophet `#2B5F8E`). Works inherit 09's spine-bar metaphor.
  - **Cloud entities** → type colour (`TYPE_META`).
  - **Family events** → `#ec8853` (orange). **History events** → `#7aaac8` (blue). Same as 09.
- Halo behind each node (carried from 09) at low opacity to soften visual density.

### 3.3 Edges

- All ~170 edges (with minors hidden — fewer than 09's 252) drawn as straight SVG lines at `stroke-opacity: 0.075`.
- On selection: incident edges brighten to `0.7` in the *other* endpoint's colour; 1-hop neighbour↔neighbour edges glow at `0.32` soft white; everything else dims to `0.025`. Carries 09's renderEdges palette.
- No bundling, no canvas, no on-demand reveal in 10. (Parked for prototype 11+.)

### 3.4 Labels

- At rest: only nodes with `degree ≥ 4` show labels (carries 09's `LABEL_DEGREE_FLOOR`).
- On selection: selected node + 1-hop neighbours show labels regardless of degree.

### 3.5 Drag

- Nodes are draggable using d3-drag. Drag end: pin the node by setting `fx/fy` to its drop position (so the layout you shape is preserved).
- Double-click a node: clear `fx/fy` to release the pin and let the simulation re-claim it.
- Dragging never triggers selection (clicks and drags must be distinguishable; use a small movement threshold ~4px, same as 09's `dragMoved` pattern).

### 3.6 Satellite reveal (work click only)

- Clicking a work-node:
  1. Fetches the work's minors (5–11 of them, already in the data as `worksData[i].minors`).
  2. Renders them as a *separate satellite layer*, not added to the main simulation. Each minor's position is computed deterministically from the clicked work's current screen position: a small radial arrangement (e.g. evenly distributed on a ~70px-radius circle around the work, jittered slightly). The work-node itself stays governed by the main force; satellites move with the work as it drifts.
  3. Edges between work↔minor and minor↔minor (where they exist in `extraEdges`) are drawn in the same SVG layer as the satellites, at the selection-bright opacity.
  4. Satellites fade in over ~250ms.
- Clicking another work or background:
  1. Previous work's satellites fade out (~200ms).
  2. New satellites (if applicable) fade in.
- Satellites are not in the main d3 simulation, so they never exert charge/collide on the global graph. The non-minor nodes' force layout is completely unaffected by satellite reveal.

### 3.7 Selection state

| Trigger | Effect |
|---|---|
| Click a node | Spotlight (selected + 1-hop neighbours full opacity, rest dim to ~0.18); incident edges brighten; if a work, satellites fade in; right panel + timeline update |
| Click background | Drop spotlight; satellites fade out; right panel returns to welcome state; timeline stays at its current zoom |
| Esc | Same as click background |
| Drag a node | Pin (fx/fy); does not change selection |
| Double-click a node | Release pin |

---

## 4. Vertical timeline

### 4.1 Visual identity

- 90px fixed-width vertical strip.
- Background: four period colour bands stacked top-to-bottom — Youth (1828–1851) green, Soldier (1851–1862) red, Great Works (1862–1880) amber, Prophet (1880–1910) blue. Pre/post zones subdued gray, same palette as 09's `PERIODS`.
- Period labels rotated 90° (or vertical-text) on each band.
- Year ticks on the left edge, granularity adapted to current zoom span:
  - span > 60y → every 10 years
  - span 20–60y → every 5 years
  - span 5–20y → every year
  - span 1–5y → every quarter (or month if dense enough)
  - span < 1y → every month (or week / day at extreme zoom)
- Major event marks (small dots, ~3px) at their year position on the right edge of the strip, in the event's subtype colour. ~17 marks total at default zoom (9 family + 8 history).

### 4.2 Zoom-on-click-from-graph

When a node in the graph is selected, the timeline slides+zooms to its date region:

| Node kind | Target span (centre, span) |
|---|---|
| Work | centre = `(written + published) / 2`, span = `max(5, (published − written) × 2)` |
| Event | centre = `year`, span = `5` years |
| Cloud entity with `dateRange = [s, e]` | centre = `(s + e) / 2`, span = `(e − s) × 1.1` |
| Cloud entity without `dateRange` | centre = `year`, span = `16` years (one period of context) |

Animation: ease `viewStart`/`viewEnd` (now scrolling vertically) over 750ms with `easeInOutCubic`. Same animation pattern as 09; respects `prefers-reduced-motion`.

### 4.3 Bidirectional: timeline → graph

- Hovering an event-mark shows a small tooltip with the event title (same tooltip module as graph nodes).
- Clicking an event-mark selects the corresponding event-node in the graph (full selection cycle: spotlight, edge brighten, right panel update). The timeline does not zoom further on its own click — the selection IS the timeline's response.
- No drag-to-pan or wheel-zoom on the timeline strip in prototype 10. Reserved for a later pass.

---

## 5. Right panel

### 5.1 At rest (welcome state)

- Header: `Tolstoy's Universe`.
- One-line hint: `Click a node to explore.`
- Compact colour legend: a small grid of swatches showing the type colours and their labels (Person, Place, Source, Concept, Work [period accent], Event).
- No fake content beyond this; the panel must read as deliberately quiet.

### 5.2 On selection

```
┌──────────────────────────────┐
│ [TITLE in entity colour]     │
│ [Type badge] [Period chip*]  │
│ [Date line]                  │
│                              │
│ [Stub paragraph, ~1–2 sent.] │
│                              │
│ Connected entities:          │
│ • People — Sofia, Chertkov   │
│ • Works — Anna Karenina, …   │
│ • Concepts — Non-resistance  │
│                              │
│ [View full article →]        │
│   (disabled, tooltip)        │
└──────────────────────────────┘
                      * works only
```

- Title in entity colour (same `colorForId` rule as 09).
- Type badge: small pill, same styling as 09's tooltip's `tt-type`.
- Period chip (works only): the period name + range, in the period colour.
- Date line:
  - Work → `Written {written} · Published {published}`
  - Event → `{year}`
  - Cloud with range → `{startYear}–{endYear}`
  - Cloud without range → `{year}`
- Stub paragraph: the existing `desc` from the data, full text (no 160-char truncation like the tooltip).
- Connected entities: a list grouped by type (works, people, places, sources, concepts, events). Each entity is a clickable button that re-runs the selection cycle (spotlight + timeline zoom + panel re-fill). Excludes minors when minors are hidden globally.
- "View full article →" button: visually present but disabled (`opacity: 0.4`, `cursor: not-allowed`); tooltip on hover: `Full articles arrive with real wiki data.`

### 5.3 Scroll

- Panel content overflows vertically when the connected-entities list is long. Standard browser scroll, no custom scrollbar.

### 5.4 Close

- No explicit close button. Clicking background in the graph clears selection, which returns the panel to its welcome state.

---

## 6. Data model

### 6.1 Carried from prototype 09

- `cloudData`, `worksData` (with `minors`), `extraEdges`, `familyData`, `historyData` — copied unchanged.
- `nodeById`, `allEdges`, `degreeById`, `getConnectedSet` — same construction logic.
- `TYPE_META`, `PERIODS`, `periodFor` — same.

### 6.2 Additions for prototype 10

**Optional `dateRange` on cloud entities.** Where the single `year` is misleading (Sofia anchored at her birth, Yasnaya at Tolstoy's birth there, etc.), add `dateRange: [startYear, endYear]`. Concrete entries to add:

| id | Current `year` | Add `dateRange` | Reason |
|---|---|---|---|
| `sofia` | 1844 | `[1862, 1910]` | Married life is the relevant span |
| `yasnaya` | 1828 | `[1828, 1910]` | His entire life there |
| `caucasus-p` | 1851 | `[1851, 1854]` | Deployment span |
| `sevastopol-p` | 1854 | `[1854, 1856]` | Siege span |
| `chertkov-p` | 1854 | `[1883, 1910]` | Discipleship span |
| `non-resistance` | 1880 | `[1880, 1910]` | Articulated post-crisis through to death |
| `tolstoyanism` | 1885 | `[1885, 1910]` | Movement coalesced post-Confession |
| `astapovo` | 1910 | (keep as point year) | Date of death; one moment |
| (others) | — | leave as point year unless meaningful |

For concepts/philosophy, the anchor is conception/coining, not the carrier. The data above already follows this rule (Non-resistance anchored 1880 = post-Confession articulation, not Tolstoy's birth or death).

### 6.3 Removed from prototype 10

- `assignSubLanes`, `NUM_SUB_LANES`, sub-lane packing — works are now nodes, no Gantt placement needed.
- `initGraphForce` (09's bespoke single-tick simulation pinning cloud to year and minors under works) — replaced by a continuously-running pure d3-force.
- Anisotropic Y-zoom (`Y_ANISO`) — graph has no zoom.
- Camera-DY drag — graph has no panning (force layout takes care of itself; user drags individual nodes).
- Period-zone overlay rendering inside the graph — period colour now lives on work-nodes and on the timeline strip.
- Spine, lanes, work-bar rendering — collapsed into nodes.
- Minimap — deferred.

---

## 7. Components (file structure)

Single self-contained HTML, same pattern as 07–09:

```
projects/timelinegraph/prototypes/10-split-view/
├── index.html      single file: HTML, CSS, JS in one document
└── NOTES.md        session handoff notes (written at end of prototype build)
```

The file is structured top-to-bottom in the same sections 09 used: config → fake data → derived structures → state → dimensions → projection → render layers (graph SVG, timeline SVG, panel DOM) → render functions per layer → tooltip → animated view → selection → input handlers (drag, click, keyboard) → sidebar → init/resize.

No build step. d3 v7 from CDN. Open `index.html` in a browser to use.

---

## 8. Out of scope for prototype 10

Explicit non-goals so the prototype stays focused:

- Real wiki-data parsing (`website/src/wiki/**`). Still cross-cutting in `TODO.md`; prototype 10 keeps fake data.
- Edge rendering to canvas (D from Q8). Parked; revisit if perf needs it.
- Edge bundling / curved routing.
- Edges-on-demand or top-N edge filter.
- Bidirectional B/D from Q3 (timeline-driven graph filter, brushing).
- Minimap.
- Touch / pinch gestures.
- Keyboard navigation beyond Escape.
- Screen-reader fallback (a list view of currently-visible entities).
- URL state (focused node + viewport).
- Wheel-zoom or drag-pan on the timeline strip.
- "View full article" wiring (button is visibly disabled).
- Edge-provenance encoding (documented / inferred / biographer's claim).

---

## 9. Testing

No automated tests (consistent with 07–09 prototypes). Verification is Johan-eyes-on:

- Open `prototypes/10-split-view/index.html` in a browser.
- Default state: graph at rest, edges faint, timeline showing 1828–1910 with period bands, right panel in welcome mode.
- Click a few works in different periods → verify timeline slides+zooms to the work's span; satellites fade in around the work; right panel fills with stub + connections.
- Click a connected-entity link in the panel → verify selection updates correctly across all three components.
- Click a cloud entity (e.g. Sofia) → verify timeline zooms to her `dateRange` (1862–1910), no satellites.
- Click an event-mark on the timeline → verify the matching event-node lights up in the graph and the panel fills.
- Drag nodes around in the graph → verify pin behaviour; double-click → verify release.
- Click background or Esc → verify spotlight clears, satellites fade, panel returns to welcome, timeline stays at current zoom.

The success criterion is the same as 09's complexity-reduction goal: at rest, the screen reads as **three calm regions**, not one busy canvas.

---

## 10. After prototype 10

If the structural shift confirms (Johan-eyes-on says yes):

1. Write a NOTES.md handoff (same pattern as 07/08/09 NOTES).
2. Update `projects/timelinegraph/TODO.md` with the prototype 10 outcome and any candidates for prototype 11.
3. Amend the canonical spec ([`2026-04-29-timelinegraph-design.md`](./2026-04-29-timelinegraph-design.md)) to reflect the split-view architecture, since 07–09 plus 10 represent a substantial divergence from the unified-projection v1.
4. Only then start the production track (`docs/superpowers/plans/2026-04-29-timelinegraph.md`, Tracks 0–4) on the new visual baseline.

If the structural shift does *not* confirm, prototype 11 reverts toward 09's unified model and applies the lighter-weight complexity reductions parked in 09's NOTES (canvas edges, edges-on-demand, top-N filter, etc.).
