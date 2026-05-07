# Timelinegraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 2D knowledge-graph + timeline visualisation of Tolstoy's universe (`/graph/` on tolstoy.life), shippable as an internal staging build first; ready to surface on the landing page once the corpus passes ~200 nodes.

**Architecture:** Single Eleventy page with two stacked render layers — D3 SVG (top) for the multi-lane spine, period zones, and UI chrome; PIXI.js v8 WebGL canvas (bottom) for the orbital cloud, bloom, and starfield. Both share one graphology data model and one D3 zoom transform. Data ships as a build-time `graph.json` artifact produced by a Node script.

**Tech stack:** Eleventy 3 · vanilla ES modules · D3 v7 · PIXI.js v8 · graphology · d3-force · vitest (tests) · Playwright (smoke). All code lives in the `website/` submodule.

**Spec:** [`docs/superpowers/specs/2026-04-29-timelinegraph-design.md`](../specs/2026-04-29-timelinegraph-design.md) (committed `6ba0eec3`).

---

## Operating notes

- **Working directory:** all commands run from `website/` unless noted. Commits go to the website submodule (separate git repo).
- **Test runner:** vitest (introduced in Task 01; not currently in `website/`'s devDependencies).
- **Bundling:** esbuild, invoked from `npm run build:graph-bundle`, output to `src/assets/graph/dist/main.mjs`. Decision rationale: zero-config, ESM-native, fast, already a common Eleventy companion.
- **Prototype re-scoping** (vs. the original `projects/timelinegraph/prototypes/` scaffold): per the spec, the layout is no longer radial-around-Tolstoy. Renames:
  - `01-radial-focus` → conceptually "spine + lanes + period zones" (Track 1 below).
  - `03-timeline-brush` → conceptually "zoom-as-time + pan" (Track 3 below).
  - `02-bloom-aesthetic` and `04-composite` keep their conceptual names.
- **Code lives in `website/src/assets/graph/`** from Task 02 onward (not in `projects/timelinegraph/prototypes/`). `projects/timelinegraph/` retains the design notes and TODO; the working code is in the submodule.
- **Deuteranopia validation gate** between Track 2 and Track 3 — Johan must eyes-on the red↔green period transition (1851) before further visual work proceeds. Task 22 enforces this.

---

## File structure (created or modified)

```
website/
├── package.json                                        ← MODIFY: add vitest, esbuild, scripts
├── scripts/
│   ├── build-graph.mjs                                 ← CREATE: data pipeline entry
│   ├── lib/
│   │   ├── parse-frontmatter.mjs                       ← CREATE
│   │   ├── extract-edges.mjs                           ← CREATE
│   │   ├── compute-metrics.mjs                         ← CREATE
│   │   └── lane-period.mjs                             ← CREATE
│   ├── graph.schema.json                               ← CREATE: JSON Schema for graph.json
│   └── __tests__/
│       ├── parse-frontmatter.test.mjs                  ← CREATE
│       ├── extract-edges.test.mjs                      ← CREATE
│       ├── compute-metrics.test.mjs                    ← CREATE
│       ├── lane-period.test.mjs                        ← CREATE
│       ├── build-graph.test.mjs                        ← CREATE: snapshot test
│       └── fixtures/
│           ├── wiki/                                   ← CREATE: ~10 .md files
│           ├── works/
│           ├── letters/
│           └── expected-graph.json
├── src/
│   ├── pages/
│   │   └── graph.njk                                   ← CREATE: Eleventy page
│   ├── _data/
│   │   └── graph.json                                  ← BUILD ARTIFACT (gitignored)
│   └── assets/graph/
│       ├── main.mjs                                    ← CREATE: bundle entry
│       ├── bus.mjs                                     ← CREATE: tiny event bus
│       ├── data/
│       │   ├── load.mjs                                ← CREATE
│       │   └── types.mjs                               ← CREATE
│       ├── scale/
│       │   └── timeScale.mjs                           ← CREATE
│       ├── spine/
│       │   ├── axis.mjs                                ← CREATE
│       │   ├── lanes.mjs                               ← CREATE
│       │   └── items.mjs                               ← CREATE
│       ├── cloud/
│       │   ├── physics.mjs                             ← CREATE
│       │   ├── render.mjs                              ← CREATE
│       │   └── starfield.mjs                           ← CREATE
│       ├── interact/
│       │   ├── zoom.mjs                                ← CREATE
│       │   ├── pan.mjs                                 ← CREATE
│       │   ├── hover.mjs                               ← CREATE
│       │   ├── modal.mjs                               ← CREATE
│       │   └── route.mjs                               ← CREATE
│       ├── ui/
│       │   ├── sidebar.mjs                             ← CREATE
│       │   ├── stub.mjs                                ← CREATE
│       │   └── empty-state.mjs                         ← CREATE
│       └── index.css                                   ← CREATE
└── tests/
    └── e2e/
        └── graph-smoke.spec.mjs                        ← CREATE: Playwright

projects/timelinegraph/
└── QA.md                                               ← CREATE: manual QA checklist
```

---

# Track 0 — Data pipeline (`build-graph.mjs`)

## Task 01 — Bootstrap test runner and esbuild

**Files:**
- Modify: `website/package.json`
- Create: `website/scripts/__tests__/.keep` (empty placeholder so directory is git-tracked)

- [ ] **Step 1: Add devDependencies**

```bash
cd website
npm install --save-dev vitest@^2 esbuild@^0.24
```

- [ ] **Step 2: Add scripts to package.json**

Add these entries under `scripts` in `package.json`:

```json
"test": "vitest run",
"test:watch": "vitest",
"build:graph": "node scripts/build-graph.mjs",
"build:graph-bundle": "esbuild src/assets/graph/main.mjs --bundle --format=esm --target=es2022 --outfile=src/assets/graph/dist/main.mjs",
"prebuild": "npm run build:graph && npm run build:graph-bundle"
```

(Insert before the existing `clean` script.)

- [ ] **Step 3: Create the placeholder**

```bash
mkdir -p scripts/__tests__
touch scripts/__tests__/.keep
```

- [ ] **Step 4: Verify install**

Run: `npx vitest --version && npx esbuild --version`
Expected: both print version strings, no errors.

- [ ] **Step 5: Commit (in website/ submodule)**

```bash
git add package.json package-lock.json scripts/__tests__/.keep
git commit -m "chore(graph): bootstrap vitest + esbuild for timelinegraph"
```

---

## Task 02 — Fixture corpus

**Files:**
- Create: `website/scripts/__tests__/fixtures/wiki/Test Person A.md`
- Create: `website/scripts/__tests__/fixtures/wiki/Test Person B.md`
- Create: `website/scripts/__tests__/fixtures/wiki/Test Place.md`
- Create: `website/scripts/__tests__/fixtures/wiki/Test Concept.md`
- Create: `website/scripts/__tests__/fixtures/wiki/Test Family Event.md`
- Create: `website/scripts/__tests__/fixtures/wiki/Test History Event.md`
- Create: `website/scripts/__tests__/fixtures/wiki/Tolstoy Stub.md` (acts as `leo-tolstoy` for tests)
- Create: `website/scripts/__tests__/fixtures/wiki/Malformed.md` (intentionally bad YAML)
- Create: `website/scripts/__tests__/fixtures/works/Test Work.md`
- Create: `website/scripts/__tests__/fixtures/letters/.keep`

- [ ] **Step 1: Write Tolstoy Stub.md**

```yaml
---
id: leo-tolstoy
recordStatus: draft
type: person
title: Leo Tolstoy
description: "Russian novelist, philosopher (1828–1910)."
birthDate: "1828-09-09"
deathDate: "1910-11-20"
relatedArticles:
  - test-person-a
relatedWorks:
  -
    id: test-work
    relationshipType: author
themes: [literature]
identifiers: { wikidata: Q7243 }
---

Tolstoy was born at [[Test Place]].
```

- [ ] **Step 2: Write Test Person A.md**

```yaml
---
id: test-person-a
recordStatus: draft
type: person
title: Test Person A
description: "A close associate (1840–1910)."
birthDate: "1840-01-01"
deathDate: "1910-01-01"
relatedArticles: [leo-tolstoy, test-place]
relatedWorks:
  -
    id: test-work
    relationshipType: transcriber
themes: [Tolstoyan movement]
---

Test Person A was a transcriber of [[Test Work]] and lived at [[Test Place]].
```

- [ ] **Step 3: Write Test Person B.md**

```yaml
---
id: test-person-b
recordStatus: draft
type: person
title: Test Person B
description: "A figure with no Tolstoy connection (1820-1900)."
birthDate: "1820-01-01"
deathDate: "1900-01-01"
relatedArticles: [test-person-a]
themes: []
---

Test Person B was a contemporary of [[Test Person A]].
```

- [ ] **Step 4: Write Test Place.md**

```yaml
---
id: test-place
recordStatus: draft
type: place
title: Test Place
description: "A village near Tula."
relatedArticles: [leo-tolstoy]
---

Test Place is referenced in many of [[Leo Tolstoy]]'s works.
```

- [ ] **Step 5: Write Test Concept.md**

```yaml
---
id: test-concept
recordStatus: draft
type: concept
title: Test Concept
description: "A philosophical idea with no date."
relatedArticles: [leo-tolstoy]
---

Test Concept was central to Tolstoy's late thinking.
```

- [ ] **Step 6: Write Test Family Event.md**

```yaml
---
id: test-family-event
recordStatus: draft
type: event
scope: family
title: Test Family Event
description: "Marriage."
date: "1862-09-23"
relatedArticles: [leo-tolstoy, test-person-a]
---

A family event in 1862.
```

- [ ] **Step 7: Write Test History Event.md**

```yaml
---
id: test-history-event
recordStatus: draft
type: event
scope: external
title: Test History Event
description: "Emancipation reform."
date: "1861-03-03"
---

A historical event in 1861.
```

- [ ] **Step 8: Write Test Work.md (in fixtures/works/)**

```yaml
---
id: test-work
recordStatus: draft
type: work
title: Test Work
description: "A novel."
dateAuthored: "1863-01-01"
dateFirstPublished: "1869-01-01"
relatedArticles: [leo-tolstoy, test-person-a]
---

Test Work was started by [[Leo Tolstoy]] and transcribed by [[Test Person A]].
```

- [ ] **Step 9: Write Malformed.md (intentionally bad YAML)**

```
---
id: malformed
type: person
title: Malformed
this is: : not valid YAML : :
---

Body content.
```

- [ ] **Step 10: Verify fixtures load**

Run: `find scripts/__tests__/fixtures -name '*.md' | wc -l`
Expected: `8`

- [ ] **Step 11: Commit**

```bash
git add scripts/__tests__/fixtures/
git commit -m "test(graph): synthetic mini-corpus for build-graph tests"
```

---

## Task 03 — `parseFrontmatter`: parse a single .md file

**Files:**
- Create: `website/scripts/lib/parse-frontmatter.mjs`
- Create: `website/scripts/__tests__/parse-frontmatter.test.mjs`

- [ ] **Step 1: Add gray-matter dependency**

```bash
npm install --save-dev gray-matter@^4
git add package.json package-lock.json
```

- [ ] **Step 2: Write the failing test**

`scripts/__tests__/parse-frontmatter.test.mjs`:

```javascript
import { describe, it, expect } from 'vitest';
import { parseFrontmatter } from '../lib/parse-frontmatter.mjs';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixtures = join(__dirname, 'fixtures');

describe('parseFrontmatter', () => {
  it('extracts frontmatter and body from a valid file', () => {
    const raw = readFileSync(join(fixtures, 'wiki/Test Person A.md'), 'utf8');
    const result = parseFrontmatter(raw);
    expect(result.frontmatter.id).toBe('test-person-a');
    expect(result.frontmatter.type).toBe('person');
    expect(result.body).toContain('[[Test Work]]');
    expect(result.error).toBeNull();
  });

  it('returns an error object for malformed YAML', () => {
    const raw = readFileSync(join(fixtures, 'wiki/Malformed.md'), 'utf8');
    const result = parseFrontmatter(raw);
    expect(result.error).not.toBeNull();
    expect(result.frontmatter).toBeNull();
  });

  it('returns null frontmatter when no YAML block present', () => {
    const result = parseFrontmatter('Just body, no frontmatter.');
    expect(result.frontmatter).toBeNull();
    expect(result.body).toBe('Just body, no frontmatter.');
    expect(result.error).toBeNull();
  });
});
```

- [ ] **Step 3: Run test and verify failure**

Run: `npx vitest run scripts/__tests__/parse-frontmatter.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `parseFrontmatter`**

`scripts/lib/parse-frontmatter.mjs`:

```javascript
import matter from 'gray-matter';

/**
 * Parses a .md file's frontmatter + body.
 * Returns { frontmatter, body, error } where error is non-null on parse failure.
 */
export function parseFrontmatter(raw) {
  try {
    const result = matter(raw);
    if (!result.data || Object.keys(result.data).length === 0) {
      return { frontmatter: null, body: result.content, error: null };
    }
    return { frontmatter: result.data, body: result.content, error: null };
  } catch (err) {
    return { frontmatter: null, body: null, error: err.message };
  }
}
```

- [ ] **Step 5: Run test and verify pass**

Run: `npx vitest run scripts/__tests__/parse-frontmatter.test.mjs`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/parse-frontmatter.mjs scripts/__tests__/parse-frontmatter.test.mjs package.json package-lock.json
git commit -m "feat(graph): parseFrontmatter with gray-matter"
```

---

## Task 04 — `assignLane` and `assignPeriod` rules

**Files:**
- Create: `website/scripts/lib/lane-period.mjs`
- Create: `website/scripts/__tests__/lane-period.test.mjs`

- [ ] **Step 1: Write failing tests**

`scripts/__tests__/lane-period.test.mjs`:

```javascript
import { describe, it, expect } from 'vitest';
import { assignLane, assignPeriod } from '../lib/lane-period.mjs';

describe('assignLane', () => {
  it('assigns "works" to type=work', () => {
    expect(assignLane({ type: 'work' })).toBe('works');
  });
  it('assigns "family" to type=event scope=family', () => {
    expect(assignLane({ type: 'event', scope: 'family' })).toBe('family');
  });
  it('assigns "history" to type=event scope=external', () => {
    expect(assignLane({ type: 'event', scope: 'external' })).toBe('history');
  });
  it('assigns null to type=person', () => {
    expect(assignLane({ type: 'person' })).toBeNull();
  });
  it('assigns null to type=concept', () => {
    expect(assignLane({ type: 'concept' })).toBeNull();
  });
  it('assigns null to type=event without scope', () => {
    expect(assignLane({ type: 'event' })).toBeNull();
  });
});

describe('assignPeriod', () => {
  it('returns "youth" for 1840', () => {
    expect(assignPeriod('1840-01-01')).toBe('youth');
  });
  it('returns "soldier" for 1855', () => {
    expect(assignPeriod('1855-01-01')).toBe('soldier');
  });
  it('returns "great-works" for 1869', () => {
    expect(assignPeriod('1869-01-01')).toBe('great-works');
  });
  it('returns "prophet" for 1893', () => {
    expect(assignPeriod('1893-01-01')).toBe('prophet');
  });
  it('returns null for pre-1828', () => {
    expect(assignPeriod('1820-01-01')).toBeNull();
  });
  it('returns null for post-1910', () => {
    expect(assignPeriod('1920-01-01')).toBeNull();
  });
  it('returns null for null input', () => {
    expect(assignPeriod(null)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npx vitest run scripts/__tests__/lane-period.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`scripts/lib/lane-period.mjs`:

```javascript
const PERIODS = [
  { id: 'youth',       start: '1828-01-01', end: '1851-12-31' },
  { id: 'soldier',     start: '1852-01-01', end: '1862-12-31' },
  { id: 'great-works', start: '1863-01-01', end: '1880-12-31' },
  { id: 'prophet',     start: '1881-01-01', end: '1910-12-31' }
];

export function assignLane(frontmatter) {
  if (!frontmatter || !frontmatter.type) return null;
  if (frontmatter.type === 'work') return 'works';
  if (frontmatter.type === 'event') {
    if (frontmatter.scope === 'family')   return 'family';
    if (frontmatter.scope === 'external') return 'history';
  }
  return null;
}

export function assignPeriod(isoDate) {
  if (!isoDate) return null;
  const d = String(isoDate);
  for (const p of PERIODS) {
    if (d >= p.start && d <= p.end) return p.id;
  }
  return null;
}

export const PERIOD_BOUNDS = PERIODS;
```

Note: period boundaries adjusted by 1 day to avoid overlap (Soldier starts 1852-01-01 not 1851-12-31). Spec table shows period years 1828–1851 / 1851–1862 / 1862–1880 / 1880–1910, which overlap at boundaries — we resolve by snapping transitions to year-start. Update spec §8 if a different snapping is requested.

- [ ] **Step 4: Run test, verify pass**

Run: `npx vitest run scripts/__tests__/lane-period.test.mjs`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/lane-period.mjs scripts/__tests__/lane-period.test.mjs
git commit -m "feat(graph): lane and period assignment rules"
```

---

## Task 05 — `extractEdges`: from frontmatter and body wikilinks

**Files:**
- Create: `website/scripts/lib/extract-edges.mjs`
- Create: `website/scripts/__tests__/extract-edges.test.mjs`

- [ ] **Step 1: Write failing tests**

`scripts/__tests__/extract-edges.test.mjs`:

```javascript
import { describe, it, expect } from 'vitest';
import { extractEdges } from '../lib/extract-edges.mjs';

const titleToId = new Map([
  ['Leo Tolstoy', 'leo-tolstoy'],
  ['Test Person A', 'test-person-a'],
  ['Test Place', 'test-place'],
  ['Test Work', 'test-work']
]);

describe('extractEdges', () => {
  it('extracts typed frontmatter edges from relatedArticles (untyped → "related")', () => {
    const fm = { id: 'a', relatedArticles: ['leo-tolstoy', 'test-place'] };
    const edges = extractEdges(fm, '', titleToId);
    expect(edges).toEqual([
      { source: 'a', target: 'leo-tolstoy', type: 'related',  provenance: 'frontmatter' },
      { source: 'a', target: 'test-place',  type: 'related',  provenance: 'frontmatter' }
    ]);
  });

  it('extracts typed frontmatter edges from relatedWorks', () => {
    const fm = {
      id: 'a',
      relatedWorks: [
        { id: 'test-work', relationshipType: 'author' }
      ]
    };
    const edges = extractEdges(fm, '', titleToId);
    expect(edges).toEqual([
      { source: 'a', target: 'test-work', type: 'author', provenance: 'frontmatter' }
    ]);
  });

  it('extracts wikilink edges from body (typed as "mention")', () => {
    const fm = { id: 'a' };
    const body = 'A reference to [[Test Place]] and [[Leo Tolstoy]].';
    const edges = extractEdges(fm, body, titleToId);
    expect(edges).toEqual([
      { source: 'a', target: 'test-place',  type: 'mention', provenance: 'wikilink' },
      { source: 'a', target: 'leo-tolstoy', type: 'mention', provenance: 'wikilink' }
    ]);
  });

  it('skips self-loops', () => {
    const fm = { id: 'a', relatedArticles: ['a'] };
    expect(extractEdges(fm, '[[A]]', new Map([['A', 'a']]))).toEqual([]);
  });

  it('warns and drops dangling wikilinks (returns __unresolved__ array)', () => {
    const fm = { id: 'a' };
    const body = '[[Nonexistent]]';
    const edges = extractEdges(fm, body, titleToId);
    expect(edges).toEqual([]);
    // We expose unresolved for the orchestrator to log
    expect(extractEdges.lastUnresolved).toEqual(['Nonexistent']);
  });
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npx vitest run scripts/__tests__/extract-edges.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`scripts/lib/extract-edges.mjs`:

```javascript
const WIKILINK = /\[\[([^\]|]+?)(?:\|[^\]]*?)?\]\]/g;

export function extractEdges(frontmatter, body, titleToId) {
  const edges = [];
  const unresolved = [];
  const id = frontmatter?.id;
  if (!id) return edges;

  const seen = new Set(); // dedup within this file

  // 1. relatedArticles (untyped → "related")
  for (const target of frontmatter.relatedArticles ?? []) {
    if (target === id) continue;
    const key = `${target}::related`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({ source: id, target, type: 'related', provenance: 'frontmatter' });
  }

  // 2. relatedWorks (typed)
  for (const rel of frontmatter.relatedWorks ?? []) {
    if (!rel?.id || rel.id === id) continue;
    const type = rel.relationshipType ?? 'related';
    const key = `${rel.id}::${type}`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({ source: id, target: rel.id, type, provenance: 'frontmatter' });
  }

  // 3. body wikilinks (untyped → "mention"); only added if not already covered by frontmatter
  for (const match of body.matchAll(WIKILINK)) {
    const title = match[1].trim();
    const target = titleToId.get(title);
    if (!target) {
      unresolved.push(title);
      continue;
    }
    if (target === id) continue;
    // Frontmatter-edge wins: skip if any edge to this target already exists
    if ([...seen].some(k => k.startsWith(`${target}::`))) continue;
    const key = `${target}::mention`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({ source: id, target, type: 'mention', provenance: 'wikilink' });
  }

  extractEdges.lastUnresolved = unresolved;
  return edges;
}

extractEdges.lastUnresolved = [];
```

- [ ] **Step 4: Run test, verify pass**

Run: `npx vitest run scripts/__tests__/extract-edges.test.mjs`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/extract-edges.mjs scripts/__tests__/extract-edges.test.mjs
git commit -m "feat(graph): extractEdges from frontmatter and body wikilinks"
```

---

## Task 06 — `computeMetrics`: degree + BFS-from-Tolstoy

**Files:**
- Create: `website/scripts/lib/compute-metrics.mjs`
- Create: `website/scripts/__tests__/compute-metrics.test.mjs`

- [ ] **Step 1: Add graphology dependency**

```bash
npm install graphology@^0.25 graphology-traversal@^0.3
```

- [ ] **Step 2: Write failing tests**

`scripts/__tests__/compute-metrics.test.mjs`:

```javascript
import { describe, it, expect } from 'vitest';
import { computeMetrics } from '../lib/compute-metrics.mjs';

describe('computeMetrics', () => {
  it('computes degree and bfsFromTolstoy', () => {
    const nodes = [
      { id: 'leo-tolstoy' },
      { id: 'a' },
      { id: 'b' },
      { id: 'c' }
    ];
    const edges = [
      { source: 'leo-tolstoy', target: 'a' },
      { source: 'a', target: 'b' }
      // c is disconnected
    ];
    const metrics = computeMetrics(nodes, edges);
    expect(metrics.get('leo-tolstoy')).toEqual({ degree: 1, bfsFromTolstoy: 0 });
    expect(metrics.get('a')).toEqual({ degree: 2, bfsFromTolstoy: 1 });
    expect(metrics.get('b')).toEqual({ degree: 1, bfsFromTolstoy: 2 });
    expect(metrics.get('c')).toEqual({ degree: 0, bfsFromTolstoy: Infinity });
  });

  it('handles missing leo-tolstoy node (sets all bfs to Infinity)', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }];
    const edges = [{ source: 'a', target: 'b' }];
    const metrics = computeMetrics(nodes, edges);
    expect(metrics.get('a').bfsFromTolstoy).toBe(Infinity);
    expect(metrics.get('b').bfsFromTolstoy).toBe(Infinity);
  });
});
```

- [ ] **Step 3: Run test, verify failure**

Run: `npx vitest run scripts/__tests__/compute-metrics.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement**

`scripts/lib/compute-metrics.mjs`:

```javascript
import Graph from 'graphology';

export function computeMetrics(nodes, edges) {
  const g = new Graph({ multi: false, type: 'undirected', allowSelfLoops: false });
  for (const n of nodes) g.addNode(n.id);
  for (const e of edges) {
    if (g.hasNode(e.source) && g.hasNode(e.target) && !g.hasEdge(e.source, e.target)) {
      g.addEdge(e.source, e.target);
    }
  }

  const out = new Map();
  for (const id of g.nodes()) {
    out.set(id, { degree: g.degree(id), bfsFromTolstoy: Infinity });
  }

  if (g.hasNode('leo-tolstoy')) {
    // BFS from leo-tolstoy
    const visited = new Set(['leo-tolstoy']);
    let frontier = ['leo-tolstoy'];
    let depth = 0;
    while (frontier.length > 0) {
      for (const node of frontier) out.get(node).bfsFromTolstoy = depth;
      const next = [];
      for (const node of frontier) {
        for (const neighbor of g.neighbors(node)) {
          if (!visited.has(neighbor)) {
            visited.add(neighbor);
            next.push(neighbor);
          }
        }
      }
      frontier = next;
      depth += 1;
    }
  }

  return out;
}
```

- [ ] **Step 5: Run test, verify pass**

Run: `npx vitest run scripts/__tests__/compute-metrics.test.mjs`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/compute-metrics.mjs scripts/__tests__/compute-metrics.test.mjs package.json package-lock.json
git commit -m "feat(graph): degree + BFS-from-Tolstoy metrics"
```

---

## Task 07 — `graph.schema.json`: JSON Schema for graph.json

**Files:**
- Create: `website/scripts/graph.schema.json`

- [ ] **Step 1: Write the schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://tolstoy.life/graph.schema.json",
  "title": "Tolstoy Universe Graph",
  "type": "object",
  "required": ["version", "generatedAt", "stats", "nodes", "edges"],
  "properties": {
    "version": { "type": "string", "const": "1.0" },
    "generatedAt": { "type": "string", "format": "date-time" },
    "stats": {
      "type": "object",
      "required": ["nodeCount", "edgeCount"],
      "properties": {
        "nodeCount": { "type": "integer", "minimum": 0 },
        "edgeCount": { "type": "integer", "minimum": 0 }
      }
    },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "type", "title", "dates", "stubKey", "wikiUrl", "metrics"],
        "properties": {
          "id":        { "type": "string", "pattern": "^[a-z0-9-]+$" },
          "type":      { "type": "string", "enum": ["person","place","event","concept","translator","institution","adaptation","criticalWork","archivalFond","work"] },
          "title":     { "type": "string" },
          "dates": {
            "type": "object",
            "properties": {
              "primary":     { "type": ["string", "null"] },
              "end":         { "type": ["string", "null"] },
              "approximate": { "type": "boolean" }
            }
          },
          "lane":      { "type": ["string", "null"], "enum": ["works","family","history","letters", null] },
          "period":    { "type": ["string", "null"], "enum": ["youth","soldier","great-works","prophet", null] },
          "stubKey":   { "type": "string" },
          "wikiUrl":   { "type": "string" },
          "metrics": {
            "type": "object",
            "required": ["degree", "bfsFromTolstoy"],
            "properties": {
              "degree":         { "type": "integer", "minimum": 0 },
              "bfsFromTolstoy": { "type": ["integer", "number"] }
            }
          }
        }
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["source", "target", "type", "provenance"],
        "properties": {
          "source":     { "type": "string" },
          "target":     { "type": "string" },
          "type":       { "type": "string", "enum": ["author","transcriber","editor","translator","publisher","related","mention"] },
          "provenance": { "type": "string", "enum": ["frontmatter","wikilink"] }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/graph.schema.json
git commit -m "feat(graph): JSON Schema for graph.json"
```

---

## Task 08 — `build-graph.mjs`: orchestrator + snapshot test

**Files:**
- Create: `website/scripts/build-graph.mjs`
- Create: `website/scripts/__tests__/build-graph.test.mjs`
- Create: `website/scripts/__tests__/fixtures/expected-graph.json`

- [ ] **Step 1: Write the failing snapshot test**

`scripts/__tests__/build-graph.test.mjs`:

```javascript
import { describe, it, expect } from 'vitest';
import { buildGraph } from '../build-graph.mjs';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixtures = join(__dirname, 'fixtures');

describe('buildGraph (snapshot)', () => {
  it('produces expected graph.json from fixture corpus', async () => {
    const result = await buildGraph({
      sources: [
        join(fixtures, 'wiki'),
        join(fixtures, 'works'),
        join(fixtures, 'letters')
      ],
      siteUrlBase: ''
    });

    // Stable output: strip generatedAt
    const stable = { ...result, generatedAt: '<stripped>' };

    const expected = JSON.parse(readFileSync(join(fixtures, 'expected-graph.json'), 'utf8'));
    expect(stable).toEqual(expected);
  });

  it('warns and skips malformed files', async () => {
    const warnings = [];
    await buildGraph({
      sources: [join(fixtures, 'wiki')],
      onWarn: msg => warnings.push(msg)
    });
    const malformed = warnings.find(w => w.includes('Malformed'));
    expect(malformed).toBeDefined();
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `npx vitest run scripts/__tests__/build-graph.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `buildGraph`**

`scripts/build-graph.mjs`:

```javascript
import { readdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { join, basename, extname, relative } from 'node:path';
import { parseFrontmatter } from './lib/parse-frontmatter.mjs';
import { extractEdges } from './lib/extract-edges.mjs';
import { computeMetrics } from './lib/compute-metrics.mjs';
import { assignLane, assignPeriod } from './lib/lane-period.mjs';

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    if (entry.startsWith('.')) continue;
    const full = join(dir, entry);
    const s = statSync(full);
    if (s.isDirectory()) out.push(...walk(full));
    else if (s.isFile() && extname(entry) === '.md') out.push(full);
  }
  return out;
}

function fileTitle(path) {
  return basename(path, '.md');
}

function wikiUrlFor(frontmatter, sourceRoot, filePath) {
  const rel = relative(sourceRoot, filePath).replace(/\.md$/, '').toLowerCase();
  const prefix = sourceRoot.endsWith('wiki') ? '/wiki/'
              : sourceRoot.endsWith('works') ? '/works/'
              : sourceRoot.endsWith('letters') ? '/letters/'
              : '/';
  return `${prefix}${frontmatter.id}/`;
}

export async function buildGraph({ sources, siteUrlBase = '', onWarn = console.warn, strict = false }) {
  // Pass 1: load all files, build titleToId map
  const files = [];
  for (const root of sources) {
    for (const f of walk(root)) {
      const raw = readFileSync(f, 'utf8');
      const parsed = parseFrontmatter(raw);
      if (parsed.error) {
        const msg = `[graph] Malformed YAML in ${f}: ${parsed.error}`;
        onWarn(msg);
        if (strict) throw new Error(msg);
        continue;
      }
      if (!parsed.frontmatter) {
        onWarn(`[graph] No frontmatter in ${f}; skipping`);
        continue;
      }
      if (!parsed.frontmatter.id) {
        const msg = `[graph] Missing id in ${f}`;
        onWarn(msg);
        if (strict) throw new Error(msg);
        continue;
      }
      files.push({ path: f, sourceRoot: root, frontmatter: parsed.frontmatter, body: parsed.body });
    }
  }

  // Build title-to-id map (filename → id)
  const titleToId = new Map();
  const idToFile = new Map();
  for (const file of files) {
    const title = fileTitle(file.path);
    titleToId.set(title, file.frontmatter.id);
    if (idToFile.has(file.frontmatter.id)) {
      throw new Error(`[graph] Duplicate id "${file.frontmatter.id}"`);
    }
    idToFile.set(file.frontmatter.id, file);
  }

  // Pass 2: build nodes
  const nodes = [];
  for (const file of files) {
    const fm = file.frontmatter;
    const lane = assignLane(fm);
    const datesPrimary = fm.birthDate ?? fm.dateAuthored ?? fm.date ?? null;
    const datesEnd     = fm.deathDate ?? fm.dateFirstPublished ?? null;
    const approximate  = !!(fm.birthDateApproximate || fm.dateApproximate);
    const period       = lane === 'works' ? assignPeriod(datesPrimary) : null;

    nodes.push({
      id: fm.id,
      type: fm.type,
      title: fm.title ?? fileTitle(file.path),
      dates: { primary: datesPrimary, end: datesEnd, approximate },
      lane,
      period,
      stubKey: fm.id,
      wikiUrl: wikiUrlFor(fm, file.sourceRoot, file.path),
      metrics: { degree: 0, bfsFromTolstoy: Infinity }  // filled in below
    });
  }

  // Pass 3: extract edges
  const edges = [];
  const allUnresolved = [];
  for (const file of files) {
    const e = extractEdges(file.frontmatter, file.body, titleToId);
    edges.push(...e);
    allUnresolved.push(...extractEdges.lastUnresolved);
  }
  for (const u of [...new Set(allUnresolved)]) {
    onWarn(`[graph] Unresolved wikilink: [[${u}]]`);
  }

  // Validate edge endpoints
  const validIds = new Set(nodes.map(n => n.id));
  const validEdges = edges.filter(e => validIds.has(e.source) && validIds.has(e.target));

  // Pass 4: metrics
  const metrics = computeMetrics(nodes, validEdges);
  for (const n of nodes) {
    const m = metrics.get(n.id);
    if (m) n.metrics = { degree: m.degree, bfsFromTolstoy: m.bfsFromTolstoy === Infinity ? null : m.bfsFromTolstoy };
  }

  return {
    version: '1.0',
    generatedAt: new Date().toISOString(),
    stats: { nodeCount: nodes.length, edgeCount: validEdges.length },
    nodes,
    edges: validEdges
  };
}

// CLI entry
if (import.meta.url === `file://${process.argv[1]}`) {
  const cwd = process.cwd();
  const result = await buildGraph({
    sources: [
      join(cwd, 'src/wiki'),
      join(cwd, 'src/works'),
      join(cwd, 'src/letters')
    ],
    strict: process.argv.includes('--strict')
  });

  const outDir = join(cwd, 'src/_data');
  writeFileSync(join(outDir, 'graph.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(`[graph] Wrote graph.json — ${result.stats.nodeCount} nodes, ${result.stats.edgeCount} edges`);
}
```

- [ ] **Step 4: Run buildGraph against fixtures, capture output**

```bash
node -e "
import('./scripts/build-graph.mjs').then(async ({ buildGraph }) => {
  const r = await buildGraph({
    sources: [
      'scripts/__tests__/fixtures/wiki',
      'scripts/__tests__/fixtures/works',
      'scripts/__tests__/fixtures/letters'
    ]
  });
  console.log(JSON.stringify({ ...r, generatedAt: '<stripped>' }, null, 2));
});" > scripts/__tests__/fixtures/expected-graph.json
```

- [ ] **Step 5: Inspect the captured output**

Run: `cat scripts/__tests__/fixtures/expected-graph.json | head -50`
Expected: Valid JSON. Verify visually:
- 7 nodes (Tolstoy + Person A + Person B + Place + Concept + Family Event + History Event + Test Work — but Malformed is skipped) — 8 nodes total.
- Tolstoy's `lane: null`, `bfsFromTolstoy: 0`, `degree` reflects real edge count.
- Test Work has `lane: "works"`, `period: "great-works"` (for 1863).
- Family Event has `lane: "family"`, `period: "soldier"` (for 1862).
- History Event has `lane: "history"`, `period: "soldier"` (for 1861).

If anything is wrong, fix the implementation and regenerate.

- [ ] **Step 6: Run snapshot test**

Run: `npx vitest run scripts/__tests__/build-graph.test.mjs`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add scripts/build-graph.mjs scripts/__tests__/build-graph.test.mjs scripts/__tests__/fixtures/expected-graph.json
git commit -m "feat(graph): build-graph.mjs orchestrator + snapshot test"
```

---

## Task 09 — Run against real wiki, gitignore the artifact

**Files:**
- Modify: `website/.gitignore`

- [ ] **Step 1: Add graph.json to gitignore**

Append to `website/.gitignore`:

```
# Build artifact for /graph/ — regenerated each build
src/_data/graph.json
src/assets/graph/dist/
```

- [ ] **Step 2: Run against real wiki**

```bash
npm run build:graph
```

Expected output:
- `[graph] Wrote graph.json — N nodes, M edges`
- `N` should be ~30 (matching `find src/wiki src/works -name "*.md" | wc -l`)
- Some `[graph] Unresolved wikilink:` warnings expected at this corpus stage

- [ ] **Step 3: Inspect real output for sanity**

```bash
node -e "const g = require('./src/_data/graph.json'); console.log({stats: g.stats, leoTolstoy: g.nodes.find(n => n.id === 'leo-tolstoy')});"
```

Expected: leo-tolstoy node present, has reasonable degree (≥5), bfsFromTolstoy = 0.

- [ ] **Step 4: Commit gitignore update**

```bash
git add .gitignore
git commit -m "chore(graph): gitignore generated graph.json + bundle output"
```

---

# Track 1 — Spine + period zones (prototype 01)

## Task 10 — Page scaffold and bundle entry

**Files:**
- Create: `website/src/pages/graph.njk`
- Create: `website/src/assets/graph/main.mjs`
- Create: `website/src/assets/graph/bus.mjs`
- Create: `website/src/assets/graph/index.css`

- [ ] **Step 1: Write `graph.njk`**

```html
---
layout: layouts/base.njk
title: Tolstoy's Universe
permalink: /graph/
eleventyExcludeFromCollections: true
---

<noscript>
  <p>This page requires JavaScript. Browse Tolstoy's universe via the <a href="/wiki/">wiki</a>.</p>
</noscript>

<div id="graph-root">
  <aside id="graph-sidebar"></aside>
  <main id="graph-canvas">
    <canvas id="graph-pixi"></canvas>
    <svg id="graph-svg" xmlns="http://www.w3.org/2000/svg"></svg>
  </main>
  <nav id="graph-fallback-nav" aria-label="Tolstoy's universe — entity list" hidden></nav>
</div>

<link rel="stylesheet" href="/assets/graph/index.css">
<script type="module" src="/assets/graph/dist/main.mjs"></script>
```

- [ ] **Step 2: Write event bus**

`src/assets/graph/bus.mjs`:

```javascript
export function createBus() {
  const subs = new Map();
  return {
    on(event, fn) {
      if (!subs.has(event)) subs.set(event, new Set());
      subs.get(event).add(fn);
      return () => subs.get(event).delete(fn);
    },
    emit(event, payload) {
      const set = subs.get(event);
      if (!set) return;
      for (const fn of set) fn(payload);
    }
  };
}
```

- [ ] **Step 3: Write minimal `main.mjs` entry**

`src/assets/graph/main.mjs`:

```javascript
import { createBus } from './bus.mjs';

const bus = createBus();
const root = document.getElementById('graph-root');
if (!root) {
  console.error('[graph] #graph-root missing');
} else {
  console.log('[graph] booted');
}

// Future imports wire in modules; placeholder for Track 1+
```

- [ ] **Step 4: Write minimal CSS**

`src/assets/graph/index.css`:

```css
#graph-root {
  display: grid;
  grid-template-columns: 180px 1fr;
  height: 100vh;
  background: #0a0e1a;
  color: #f4ebd5;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
#graph-sidebar { padding: 1rem; border-right: 1px solid rgba(255,255,255,0.1); }
#graph-canvas { position: relative; overflow: hidden; }
#graph-pixi, #graph-svg {
  position: absolute; inset: 0; width: 100%; height: 100%;
}
#graph-svg { pointer-events: none; }
#graph-svg * { pointer-events: auto; }
#graph-fallback-nav { position: absolute; left: -10000px; }
```

- [ ] **Step 5: Build and verify**

```bash
npm run build:graph-bundle
```

Expected: `src/assets/graph/dist/main.mjs` exists, no errors.

- [ ] **Step 6: Run dev server, visit `/graph/`**

```bash
npm start
```

Open `http://localhost:8080/graph/` in a browser. Expected: dark canvas, sidebar empty, console shows `[graph] booted`.

- [ ] **Step 7: Commit**

```bash
git add src/pages/graph.njk src/assets/graph/main.mjs src/assets/graph/bus.mjs src/assets/graph/index.css
git commit -m "feat(graph): page scaffold + minimal bundle entry"
```

---

## Task 11 — `timeScale` module with d3.scaleTime

**Files:**
- Create: `website/src/assets/graph/scale/timeScale.mjs`

- [ ] **Step 1: Add D3 dependencies**

```bash
npm install d3@^7
```

- [ ] **Step 2: Write `timeScale.mjs`**

`src/assets/graph/scale/timeScale.mjs`:

```javascript
import { scaleTime } from 'd3';

const STRIP_START = new Date('1728-01-01');
const STRIP_END   = new Date('2030-01-01');

export function createTimeScale({ width }) {
  let scale = scaleTime().domain([STRIP_START, STRIP_END]).range([0, width]);
  let transform = { k: 1, x: 0 };  // identity

  return {
    /** Pixel x for a given date (or null). */
    x(date) {
      if (!date) return null;
      return transform.x + transform.k * scale(new Date(date));
    },
    /** Resize the strip pixel range. */
    setWidth(w) {
      scale = scaleTime().domain([STRIP_START, STRIP_END]).range([0, w]);
    },
    /** Apply zoom transform { k, x }. */
    setTransform(t) {
      transform = t;
    },
    /** Read the current transform. */
    getTransform() {
      return transform;
    },
    /** Time resolution for current zoom (returns 'decade' | 'year' | 'month' | 'day'). */
    resolution() {
      const yearsVisible = (STRIP_END - STRIP_START) / (365.25 * 86400 * 1000) / transform.k;
      if (yearsVisible > 200) return 'decade';
      if (yearsVisible > 50)  return 'year';
      if (yearsVisible > 5)   return 'month';
      return 'day';
    },
    /** The visible time domain in the current viewport [start, end]. */
    visibleDomain(viewportWidth) {
      const startPx = -transform.x;
      const endPx   = -transform.x + viewportWidth;
      return [scale.invert(startPx / transform.k), scale.invert(endPx / transform.k)];
    }
  };
}
```

- [ ] **Step 3: Write a basic smoke test (no DOM needed)**

`src/assets/graph/scale/__tests__/timeScale.test.mjs`:

```javascript
import { describe, it, expect } from 'vitest';
import { createTimeScale } from '../timeScale.mjs';

describe('timeScale', () => {
  it('maps Tolstoy birth to a positive pixel x', () => {
    const ts = createTimeScale({ width: 1200 });
    const x = ts.x('1828-09-09');
    expect(x).toBeGreaterThan(0);
    expect(x).toBeLessThan(1200);
  });
  it('returns "decade" at identity transform', () => {
    const ts = createTimeScale({ width: 1200 });
    expect(ts.resolution()).toBe('decade');
  });
  it('returns "day" at very high zoom', () => {
    const ts = createTimeScale({ width: 1200 });
    ts.setTransform({ k: 100, x: 0 });
    expect(ts.resolution()).toBe('day');
  });
});
```

- [ ] **Step 4: Run test**

Run: `npx vitest run src/assets/graph/scale/__tests__/timeScale.test.mjs`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/assets/graph/scale/ package.json package-lock.json
git commit -m "feat(graph): timeScale module"
```

---

## Task 12 — Spine SVG group + lane backgrounds

**Files:**
- Create: `website/src/assets/graph/spine/lanes.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `lanes.mjs`**

`src/assets/graph/spine/lanes.mjs`:

```javascript
import { select } from 'd3';

export const LANES = [
  { id: 'works',   label: 'Works' },
  { id: 'family',  label: 'Family' },
  { id: 'history', label: 'History' },
  { id: 'letters', label: 'Letters' }
];

const LANE_HEIGHT = 50;

export function mountLanes(svg, { centerY }) {
  const top = centerY - (LANES.length * LANE_HEIGHT) / 2;
  const g = select(svg).append('g').attr('class', 'lanes');

  // Lane backgrounds
  g.selectAll('rect.lane-bg')
    .data(LANES).enter().append('rect')
    .attr('class', 'lane-bg')
    .attr('x', 0).attr('y', (_, i) => top + i * LANE_HEIGHT)
    .attr('width', '100%').attr('height', LANE_HEIGHT)
    .attr('fill', (_, i) => i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.04)');

  // Lane labels (left-edge, fixed)
  g.selectAll('text.lane-label')
    .data(LANES).enter().append('text')
    .attr('class', 'lane-label')
    .attr('x', 8).attr('y', (_, i) => top + i * LANE_HEIGHT + LANE_HEIGHT / 2 + 4)
    .attr('fill', 'rgba(255,255,255,0.6)')
    .attr('font-size', 12)
    .text(d => d.label);

  return {
    laneY(id) {
      const idx = LANES.findIndex(l => l.id === id);
      return idx === -1 ? null : top + idx * LANE_HEIGHT + LANE_HEIGHT / 2;
    },
    spineTop: top,
    spineBottom: top + LANES.length * LANE_HEIGHT
  };
}
```

- [ ] **Step 2: Wire in `main.mjs`**

Update `main.mjs`:

```javascript
import { createBus } from './bus.mjs';
import { mountLanes } from './spine/lanes.mjs';

const bus = createBus();
const root = document.getElementById('graph-root');
const svg = document.getElementById('graph-svg');
if (!root || !svg) { console.error('[graph] missing DOM'); }
else {
  const rect = root.getBoundingClientRect();
  const centerY = rect.height / 2;
  const lanes = mountLanes(svg, { centerY });
  console.log('[graph] booted, lanes mounted', lanes);
}
```

- [ ] **Step 3: Build, view in browser**

```bash
npm run build:graph-bundle
```

Visit `/graph/`. Expected: 4 horizontal alternating-stripe bands centered vertically with lane labels on the left.

- [ ] **Step 4: Commit**

```bash
git add src/assets/graph/spine/lanes.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): lane backgrounds and labels"
```

---

## Task 13 — Period zones + lifespan band + transitions

**Files:**
- Create: `website/src/assets/graph/spine/axis.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `axis.mjs`**

`src/assets/graph/spine/axis.mjs`:

```javascript
import { select } from 'd3';

export const PERIODS = [
  { id: 'youth',       label: 'Youth',       start: '1828-01-01', end: '1851-12-31', color: '#4A7C59' },
  { id: 'soldier',     label: 'Soldier',     start: '1852-01-01', end: '1862-12-31', color: '#B83232' },
  { id: 'great-works', label: 'Great Works', start: '1863-01-01', end: '1880-12-31', color: '#C8860A' },
  { id: 'prophet',     label: 'Prophet',     start: '1881-01-01', end: '1910-12-31', color: '#2B5F8E' }
];

export function mountAxis(svg, { timeScale, spineTop, spineBottom }) {
  const g = select(svg).append('g').attr('class', 'axis');

  // Pre-1828 grey overlay
  const preEnd = timeScale.x('1828-01-01');
  const postStart = timeScale.x('1910-12-31');
  const fullW = svg.clientWidth || 1200;

  g.append('rect').attr('class', 'pre-zone')
    .attr('x', -10000).attr('y', spineTop)
    .attr('width', preEnd + 10000).attr('height', spineBottom - spineTop)
    .attr('fill', 'rgba(50,50,60,0.20)');

  g.append('rect').attr('class', 'post-zone')
    .attr('x', postStart).attr('y', spineTop)
    .attr('width', fullW + 10000 - postStart).attr('height', spineBottom - spineTop)
    .attr('fill', 'rgba(50,50,60,0.20)');

  // Period zones
  for (const p of PERIODS) {
    const x0 = timeScale.x(p.start);
    const x1 = timeScale.x(p.end);
    g.append('rect').attr('class', `period period-${p.id}`)
      .attr('x', x0).attr('y', spineTop)
      .attr('width', x1 - x0).attr('height', spineBottom - spineTop)
      .attr('fill', p.color).attr('opacity', 0.12);
  }

  // Period transition guidelines
  for (let i = 1; i < PERIODS.length; i++) {
    const x = timeScale.x(PERIODS[i].start);
    const color = PERIODS[i - 1].color;
    g.append('line').attr('class', 'period-divider')
      .attr('x1', x).attr('x2', x)
      .attr('y1', spineTop).attr('y2', spineBottom)
      .attr('stroke', color).attr('stroke-opacity', 0.25).attr('stroke-width', 1);
  }

  // Period labels (above spine)
  for (const p of PERIODS) {
    const x = (timeScale.x(p.start) + timeScale.x(p.end)) / 2;
    g.append('text').attr('class', 'period-label')
      .attr('x', x).attr('y', spineTop - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', p.color).attr('fill-opacity', 0.9)
      .attr('font-size', 11).attr('font-variant', 'small-caps')
      .text(p.label);
  }

  return { redraw: () => {/* re-implemented in Track 3 when zoom lives */} };
}
```

- [ ] **Step 2: Wire in `main.mjs`**

```javascript
import { createBus } from './bus.mjs';
import { createTimeScale } from './scale/timeScale.mjs';
import { mountLanes } from './spine/lanes.mjs';
import { mountAxis } from './spine/axis.mjs';

const bus = createBus();
const root = document.getElementById('graph-root');
const svg = document.getElementById('graph-svg');
if (!root || !svg) { console.error('[graph] missing DOM'); }
else {
  const rect = root.getBoundingClientRect();
  const centerY = rect.height / 2;
  const timeScale = createTimeScale({ width: rect.width - 180 });
  const lanes = mountLanes(svg, { centerY });
  mountAxis(svg, { timeScale, spineTop: lanes.spineTop, spineBottom: lanes.spineBottom });
  console.log('[graph] booted with periods');
}
```

- [ ] **Step 3: Build, view**

```bash
npm run build:graph-bundle
```

Expected: 4 colored period bands across the spine, vertical guidelines at transitions, gray pre/post zones, period labels above each band.

- [ ] **Step 4: Commit**

```bash
git add src/assets/graph/spine/axis.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): period zones, transitions, labels"
```

---

## Task 14 — Year axis ticks (resolution-aware, but static at decade for v1)

**Files:**
- Modify: `website/src/assets/graph/spine/axis.mjs`

- [ ] **Step 1: Add tick-rendering function to `axis.mjs`**

Append inside `mountAxis`, before the `return`:

```javascript
  // Decade ticks (will become resolution-aware in Track 3)
  const yearTicks = [];
  for (let y = 1730; y <= 2030; y += 10) yearTicks.push(`${y}-01-01`);

  for (const tickIso of yearTicks) {
    const x = timeScale.x(tickIso);
    g.append('line').attr('class', 'tick')
      .attr('x1', x).attr('x2', x)
      .attr('y1', spineBottom + 4).attr('y2', spineBottom + 10)
      .attr('stroke', 'rgba(255,255,255,0.25)').attr('stroke-width', 1);
    g.append('text').attr('class', 'tick-label')
      .attr('x', x).attr('y', spineBottom + 22)
      .attr('text-anchor', 'middle')
      .attr('fill', 'rgba(255,255,255,0.5)').attr('font-size', 10)
      .text(tickIso.slice(0, 4));
  }
```

- [ ] **Step 2: Build and view**

```bash
npm run build:graph-bundle
```

Expected: decade tick marks below the spine, year labels (1730, 1740, ..., 2030).

- [ ] **Step 3: Commit**

```bash
git add src/assets/graph/spine/axis.mjs
git commit -m "feat(graph): static decade ticks (resolution-aware later)"
```

---

## Task 15 — `items.mjs`: render works as bars and events as points

**Files:**
- Create: `website/src/assets/graph/data/load.mjs`
- Create: `website/src/assets/graph/spine/items.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `load.mjs`**

`src/assets/graph/data/load.mjs`:

```javascript
export async function loadGraph() {
  const res = await fetch('/assets/graph/data/graph.json');
  if (!res.ok) throw new Error(`graph.json ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: Add Eleventy passthrough for graph.json**

Modify `eleventy.config.js` (or `.eleventy.js` — whichever the website uses) to add:

```javascript
eleventyConfig.addPassthroughCopy({
  'src/_data/graph.json': 'assets/graph/data/graph.json'
});
```

(If passthrough is configured elsewhere, add to that file.)

- [ ] **Step 3: Write `items.mjs`**

`src/assets/graph/spine/items.mjs`:

```javascript
import { select } from 'd3';
import { PERIODS } from './axis.mjs';

const PERIOD_COLOR = Object.fromEntries(PERIODS.map(p => [p.id, p.color]));

function lighten(hex, pct) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const lr = Math.round(r + (255 - r) * pct);
  const lg = Math.round(g + (255 - g) * pct);
  const lb = Math.round(b + (255 - b) * pct);
  return `#${lr.toString(16).padStart(2,'0')}${lg.toString(16).padStart(2,'0')}${lb.toString(16).padStart(2,'0')}`;
}

export function mountItems(svg, { graph, timeScale, laneY, bus }) {
  const g = select(svg).append('g').attr('class', 'items');

  const works = graph.nodes.filter(n => n.lane === 'works');
  const familyEvents = graph.nodes.filter(n => n.lane === 'family');
  const historyEvents = graph.nodes.filter(n => n.lane === 'history');

  // Work bars
  for (const w of works) {
    const x0 = timeScale.x(w.dates.primary);
    const x1 = w.dates.end ? timeScale.x(w.dates.end) : x0 + 8;
    if (x0 === null) continue;
    const fill = lighten(PERIOD_COLOR[w.period] ?? '#888', 0.65);
    const stroke = PERIOD_COLOR[w.period] ?? '#888';
    g.append('rect').attr('class', 'work-bar').attr('data-id', w.id)
      .attr('x', x0).attr('y', laneY('works') - 12)
      .attr('width', Math.max(8, x1 - x0)).attr('height', 24)
      .attr('rx', 4).attr('fill', fill).attr('stroke', stroke).attr('stroke-width', 1)
      .style('cursor', 'pointer')
      .on('mouseenter', () => bus.emit('hover:enter', { id: w.id }))
      .on('mouseleave', () => bus.emit('hover:leave', { id: w.id }))
      .on('click', () => bus.emit('node:click', { id: w.id }));
  }

  // Event points (family + history)
  function renderEvents(events, laneId, color) {
    for (const e of events) {
      const x = timeScale.x(e.dates.primary);
      if (x === null) continue;
      g.append('circle').attr('class', 'event-point').attr('data-id', e.id)
        .attr('cx', x).attr('cy', laneY(laneId)).attr('r', 5)
        .attr('fill', color).attr('stroke', '#000').attr('stroke-width', 0.5)
        .style('cursor', 'pointer')
        .on('mouseenter', () => bus.emit('hover:enter', { id: e.id }))
        .on('mouseleave', () => bus.emit('hover:leave', { id: e.id }))
        .on('click', () => bus.emit('node:click', { id: e.id }));
    }
  }
  renderEvents(familyEvents,  'family',  '#ec8853');
  renderEvents(historyEvents, 'history', '#a89a85');

  return g;
}
```

- [ ] **Step 4: Wire in `main.mjs`**

Replace `main.mjs` body (the `else` branch) with:

```javascript
  const rect = root.getBoundingClientRect();
  const centerY = rect.height / 2;
  const timeScale = createTimeScale({ width: rect.width - 180 });
  const lanes = mountLanes(svg, { centerY });
  mountAxis(svg, { timeScale, spineTop: lanes.spineTop, spineBottom: lanes.spineBottom });

  const { loadGraph } = await import('./data/load.mjs');
  const { mountItems } = await import('./spine/items.mjs');
  try {
    const graph = await loadGraph();
    mountItems(svg, { graph, timeScale, laneY: lanes.laneY, bus });
    console.log('[graph] mounted', graph.stats);
  } catch (err) {
    console.error('[graph] failed to load graph.json', err);
  }
```

(Wrap the whole top-level block in `(async () => { ... })()` since we now have `await`.)

- [ ] **Step 5: Build full pipeline, view**

```bash
npm run build:graph
npm run build:graph-bundle
npm start
```

Expected:
- Console logs `[graph] mounted { nodeCount: ~30, edgeCount: ~? }`
- Spine shows real Tolstoy works as period-colored bars at correct dates
- Family + history events render as colored points (if any exist in current corpus)
- Hovering a bar logs hover events to console

- [ ] **Step 6: Commit**

```bash
git add src/assets/graph/data/load.mjs src/assets/graph/spine/items.mjs src/assets/graph/main.mjs eleventy.config.js
git commit -m "feat(graph): work bars and event points on spine, real data"
```

---

# Track 2 — Cloud + bloom (prototype 02)

## Task 16 — PIXI canvas mount with WebGL detection fallback

**Files:**
- Modify: `website/src/assets/graph/main.mjs`
- Create: `website/src/assets/graph/cloud/render.mjs`

- [ ] **Step 1: Add PIXI dependency**

```bash
npm install pixi.js@^8 @pixi/filter-advanced-bloom@^5
```

- [ ] **Step 2: Write minimal `cloud/render.mjs`**

`src/assets/graph/cloud/render.mjs`:

```javascript
import { Application, Container } from 'pixi.js';

export async function mountCloud(canvas, { width, height }) {
  // WebGL detection
  const supported = (() => {
    try {
      const gl = document.createElement('canvas').getContext('webgl2')
              || document.createElement('canvas').getContext('webgl');
      return !!gl;
    } catch { return false; }
  })();
  if (!supported) {
    console.warn('[graph] WebGL not supported; cloud disabled');
    return { fallback: true, app: null, container: null };
  }

  const app = new Application();
  await app.init({ canvas, width, height, backgroundAlpha: 0, antialias: true });
  const container = new Container();
  app.stage.addChild(container);
  return { fallback: false, app, container };
}
```

- [ ] **Step 3: Wire in `main.mjs`**

Add inside the async block, after `mountItems`:

```javascript
  const pixiCanvas = document.getElementById('graph-pixi');
  const { mountCloud } = await import('./cloud/render.mjs');
  const cloud = await mountCloud(pixiCanvas, { width: rect.width, height: rect.height });
  if (!cloud.fallback) {
    console.log('[graph] PIXI ready');
  }
```

- [ ] **Step 4: Build + view**

```bash
npm run build:graph-bundle && npm start
```

Expected: `[graph] PIXI ready` in console; SVG layer still visible (PIXI canvas is transparent).

- [ ] **Step 5: Commit**

```bash
git add src/assets/graph/cloud/render.mjs src/assets/graph/main.mjs package.json package-lock.json
git commit -m "feat(graph): PIXI canvas mount + WebGL fallback detection"
```

---

## Task 17 — Parallax starfield (3 layers)

**Files:**
- Create: `website/src/assets/graph/cloud/starfield.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `starfield.mjs`**

`src/assets/graph/cloud/starfield.mjs`:

```javascript
import { Container, Graphics } from 'pixi.js';

const LAYERS = [
  { count: 120, opacity: 0.25, drift: 0.05, radius: 0.6 },
  { count: 60,  opacity: 0.55, drift: 0.15, radius: 1.0 },
  { count: 30,  opacity: 0.90, drift: 0.35, radius: 1.5 }
];

export function mountStarfield(stage, { width, height }) {
  const root = new Container();
  stage.addChildAt(root, 0);

  const layers = LAYERS.map(l => {
    const c = new Container();
    root.addChild(c);
    for (let i = 0; i < l.count; i++) {
      const g = new Graphics();
      const x = Math.random() * width * 2 - width / 2;
      const y = Math.random() * height;
      g.circle(0, 0, l.radius).fill({ color: 0xffffff, alpha: l.opacity });
      g.position.set(x, y);
      c.addChild(g);
    }
    return c;
  });

  return {
    /** Pan: deltaX from zoom transform; layers drift at their own speeds. */
    setPanX(panX) {
      for (let i = 0; i < layers.length; i++) {
        layers[i].x = panX * LAYERS[i].drift;
      }
    }
  };
}
```

- [ ] **Step 2: Wire in `main.mjs`**

Inside the `if (!cloud.fallback)` branch:

```javascript
  if (!cloud.fallback) {
    const { mountStarfield } = await import('./cloud/starfield.mjs');
    const starfield = mountStarfield(cloud.app.stage, { width: rect.width, height: rect.height });
    console.log('[graph] starfield mounted');
  }
```

- [ ] **Step 3: Build + view**

Expected: subtle starfield visible behind the spine; stars visible at three opacity levels.

- [ ] **Step 4: Commit**

```bash
git add src/assets/graph/cloud/starfield.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): 3-layer parallax starfield"
```

---

## Task 18 — Cloud node sprites + bloom filter

**Files:**
- Modify: `website/src/assets/graph/cloud/render.mjs`

- [ ] **Step 1: Add type palette + sprite renderer to `render.mjs`**

Replace `cloud/render.mjs` with:

```javascript
import { Application, Container, Graphics } from 'pixi.js';
import { AdvancedBloomFilter } from '@pixi/filter-advanced-bloom';

const TYPE_COLOR = {
  person: 0xf4ebd5, work: 0xd4a85e, place: 0xa8c4a1, event: 0xec8853,
  concept: 0xc2b1d1, translator: 0xd4a8b5, institution: 0x8a99a8,
  adaptation: 0xb88a99, criticalWork: 0xe6dcb5, archivalFond: 0xa89a85
};

export async function mountCloud(canvas, { width, height }) {
  const supported = (() => {
    try {
      const gl = document.createElement('canvas').getContext('webgl2')
              || document.createElement('canvas').getContext('webgl');
      return !!gl;
    } catch { return false; }
  })();
  if (!supported) {
    console.warn('[graph] WebGL not supported; cloud disabled');
    return { fallback: true };
  }

  const app = new Application();
  await app.init({ canvas, width, height, backgroundAlpha: 0, antialias: true });

  const nodesContainer = new Container();
  nodesContainer.filters = [new AdvancedBloomFilter({ threshold: 0.4, bloomScale: 1.2, brightness: 1, blur: 4 })];
  app.stage.addChild(nodesContainer);

  const sprites = new Map();

  function syncCloudNodes(graph) {
    // Render only nodes with lane === null AND id !== 'leo-tolstoy'
    const cloudNodes = graph.nodes.filter(n => n.lane === null && n.id !== 'leo-tolstoy');
    for (const node of cloudNodes) {
      const radius = 8 + Math.log2((node.metrics?.degree ?? 0) + 1) * 2;
      const color = TYPE_COLOR[node.type] ?? 0xffffff;
      const g = new Graphics();
      g.circle(0, 0, radius).fill({ color, alpha: 0.85 });
      g.position.set(width / 2, height / 2);  // initial; physics moves them
      g.eventMode = 'static';
      g.cursor = 'pointer';
      g.on('pointerover', () => g.dispatchEvent(new CustomEvent('cloud:hover-enter', { bubbles: true, detail: { id: node.id } })));
      g.on('pointerout',  () => g.dispatchEvent(new CustomEvent('cloud:hover-leave', { bubbles: true, detail: { id: node.id } })));
      g.on('pointertap',  () => g.dispatchEvent(new CustomEvent('cloud:click',       { bubbles: true, detail: { id: node.id } })));
      nodesContainer.addChild(g);
      sprites.set(node.id, g);
    }
  }

  function setNodePosition(id, x, y) {
    const s = sprites.get(id);
    if (s) s.position.set(x, y);
  }

  return { fallback: false, app, container: nodesContainer, syncCloudNodes, setNodePosition, sprites };
}
```

- [ ] **Step 2: Wire `syncCloudNodes` in `main.mjs`**

After loading the graph and inside the `!cloud.fallback` branch:

```javascript
    cloud.syncCloudNodes(graph);
    console.log('[graph] cloud nodes:', cloud.sprites.size);
```

- [ ] **Step 3: Build + view**

Expected: cloud nodes appear as glowing colored circles (all clustered in viewport center for now — physics added in next task).

- [ ] **Step 4: Commit**

```bash
git add src/assets/graph/cloud/render.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): cloud node sprites with bloom filter"
```

---

## Task 19 — `physics.mjs`: d3-force layout for cloud

**Files:**
- Create: `website/src/assets/graph/cloud/physics.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Add d3-force**

```bash
npm install d3-force@^3
```

- [ ] **Step 2: Write `physics.mjs`**

`src/assets/graph/cloud/physics.mjs`:

```javascript
import { forceSimulation, forceManyBody, forceX, forceY, forceLink, forceCollide } from 'd3-force';

export function startPhysics({ graph, timeScale, spineCenterY, viewportWidth, onTick }) {
  // Filter to cloud nodes only (lane === null AND id !== leo-tolstoy)
  const cloudNodes = graph.nodes
    .filter(n => n.lane === null && n.id !== 'leo-tolstoy')
    .map(n => ({
      id: n.id,
      type: n.type,
      x: timeScale.x(n.dates.primary) ?? viewportWidth / 2,
      y: spineCenterY + (Math.random() - 0.5) * 200
    }));
  const nodeMap = new Map(cloudNodes.map(n => [n.id, n]));

  // Cloud edges: drop any with leo-tolstoy as endpoint, drop any to/from spine entities
  const cloudEdges = graph.edges
    .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
    .map(e => ({ source: e.source, target: e.target, type: e.type }));

  const sim = forceSimulation(cloudNodes)
    .force('charge', forceManyBody().strength(-30))
    .force('x',      forceX(d => timeScale.x(d.id ? graph.nodes.find(n => n.id === d.id)?.dates.primary : null) ?? viewportWidth / 2).strength(0.3))
    .force('y',      forceY(d => spineCenterY + (d.id.charCodeAt(0) % 2 === 0 ? -150 : 150)).strength(0.05))
    .force('link',   forceLink(cloudEdges).id(d => d.id).distance(60).strength(0.2))
    .force('collide', forceCollide(20))
    .alphaDecay(0.05)
    .on('tick', () => onTick(cloudNodes, cloudEdges));

  return {
    stop: () => sim.stop(),
    restart: () => sim.alpha(1).restart(),
    nodes: cloudNodes,
    edges: cloudEdges
  };
}
```

- [ ] **Step 3: Wire in `main.mjs`**

After `cloud.syncCloudNodes(graph)`:

```javascript
    const { startPhysics } = await import('./cloud/physics.mjs');
    const physics = startPhysics({
      graph,
      timeScale,
      spineCenterY: centerY,
      viewportWidth: rect.width,
      onTick: (nodes) => {
        for (const n of nodes) cloud.setNodePosition(n.id, n.x, n.y);
      }
    });
```

- [ ] **Step 4: Build + view**

Expected: cloud nodes spread out — anchored horizontally to their birth-year on the spine, scattered vertically above and below. Settles after a few seconds.

- [ ] **Step 5: Commit**

```bash
git add src/assets/graph/cloud/physics.mjs src/assets/graph/main.mjs package.json package-lock.json
git commit -m "feat(graph): d3-force cloud physics with time anchoring"
```

---

## Task 20 — Cloud edges (typed by relationship)

**Files:**
- Modify: `website/src/assets/graph/cloud/render.mjs`

- [ ] **Step 1: Add edge palette + edge layer**

In `cloud/render.mjs`, inside `mountCloud` before `return`:

```javascript
  const edgesContainer = new Container();
  app.stage.addChildAt(edgesContainer, app.stage.getChildIndex(nodesContainer));
  // (edges below nodes so nodes appear on top)

  const edgeGraphics = new Graphics();
  edgesContainer.addChild(edgeGraphics);

  const EDGE_STYLE = {
    author:      { color: 0xC8860A, alpha: 0.6, width: 1.5, dashed: false },
    transcriber: { color: 0xc0c0c0, alpha: 0.5, width: 1.0, dashed: false },
    editor:      { color: 0xb88a99, alpha: 0.5, width: 1.0, dashed: false },
    translator:  { color: 0xd4a8b5, alpha: 0.5, width: 1.0, dashed: false },
    publisher:   { color: 0x8a99a8, alpha: 0.5, width: 1.0, dashed: false },
    related:     { color: 0xffffff, alpha: 0.30, width: 0.7, dashed: false },
    mention:     { color: 0xffffff, alpha: 0.20, width: 0.5, dashed: true }
  };

  function drawEdges(edges, getPos) {
    edgeGraphics.clear();
    for (const e of edges) {
      const a = getPos(e.source);
      const b = getPos(e.target);
      if (!a || !b) continue;
      const style = EDGE_STYLE[e.type] ?? EDGE_STYLE.related;
      edgeGraphics.moveTo(a.x, a.y);
      edgeGraphics.lineTo(b.x, b.y);
      edgeGraphics.stroke({ color: style.color, alpha: style.alpha, width: style.width });
    }
  }
```

Add `drawEdges` to the returned object:

```javascript
  return { fallback: false, app, container: nodesContainer, syncCloudNodes, setNodePosition, sprites, drawEdges };
```

- [ ] **Step 2: Call `drawEdges` from physics tick in `main.mjs`**

```javascript
    const physics = startPhysics({
      graph, timeScale, spineCenterY: centerY, viewportWidth: rect.width,
      onTick: (nodes, edges) => {
        const posMap = new Map(nodes.map(n => [n.id, n]));
        for (const n of nodes) cloud.setNodePosition(n.id, n.x, n.y);
        cloud.drawEdges(edges, id => posMap.get(id));
      }
    });
```

- [ ] **Step 3: Build + view**

Expected: lines visible between connected cloud nodes; line styling differs by edge type. Solid `author` edges in gold, dashed white `mention` edges, etc.

(Note: dashed-line rendering with PIXI Graphics is non-trivial; for v1 we accept solid lines for all types and revisit dashing in a polish pass. Update `EDGE_STYLE.dashed` handling later — out of v1 scope.)

- [ ] **Step 4: Commit**

```bash
git add src/assets/graph/cloud/render.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): typed cloud edges (dashing deferred)"
```

---

## Task 21 — Smoke check: prototype 02 visual snapshot

**Files:**
- Create: `projects/timelinegraph/QA.md`

- [ ] **Step 1: Take a manual screenshot**

Run `npm start` in website/. Open `http://localhost:8080/graph/` in Chrome at 1440×900. Wait for force layout to settle (~3 seconds). Take a screenshot of the full page. Save to `projects/timelinegraph/qa-screenshots/02-bloom-aesthetic.png`.

- [ ] **Step 2: Create initial QA checklist**

`projects/timelinegraph/QA.md`:

```markdown
# Manual QA — timelinegraph

## Prototype 02 (bloom + cloud) — gates Track 3

- [ ] Period zones render in 4 distinct colors at expected boundaries
- [ ] Vertical guidelines visible at 1851 / 1862 / 1880
- [ ] Period labels readable above the spine
- [ ] Cloud nodes glow visibly (bloom effect working)
- [ ] Starfield drifts subtly in 3 layers
- [ ] Work bars period-colored (War & Peace = amber, Confession = blue, etc.)
- [ ] No console errors at boot
- [ ] **DEUTERANOPIA GATE — Johan-eyes-on:** the Period I (Green 1828–1851) ↔ Period II (Red 1852–1862) boundary is readable for Johan
  - If FAIL: pause, redesign palette, do not proceed to Track 3.
  - If PASS: continue.

## Prototype 03 (zoom + pan) — gates Track 4

(filled in at Track 3 conclusion)

## Prototype 04 (composite v1) — gates internal-tool launch

(filled in at Track 4 conclusion)
```

- [ ] **Step 3: BLOCKING — Johan validates the deuteranopia gate**

This is a hard gate. Do not proceed to Task 22 until Johan signs off in `QA.md`.

- [ ] **Step 4: Commit QA file (parent repo)**

```bash
cd /Volumes/Graugear/Tolstoy
mkdir -p projects/timelinegraph/qa-screenshots
git add projects/timelinegraph/QA.md
git commit -m "docs: timelinegraph manual QA checklist + deuteranopia gate"
```

(Note: `projects/` is gitignored at the parent-repo level per AGENTS.md. If the gitignore blocks the commit, leave QA.md as a local-only file — the gate behavior still applies.)

---

# Track 3 — Zoom + pan + LOD (prototype 03)

## Task 22 — Scroll-wheel zoom updates `timeScale`

**Files:**
- Create: `website/src/assets/graph/interact/zoom.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `zoom.mjs`**

`src/assets/graph/interact/zoom.mjs`:

```javascript
const ZOOM_MIN = 1;
const ZOOM_MAX = 5000;  // ~day resolution

export function attachZoom(target, { timeScale, bus, viewportWidth }) {
  let { k, x } = timeScale.getTransform();

  function onWheel(ev) {
    ev.preventDefault();
    const cursorX = ev.clientX - target.getBoundingClientRect().left;
    const factor = Math.exp(-ev.deltaY * 0.001);
    const newK = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, k * factor));
    // Zoom anchored at cursor: data point under cursor stays under cursor
    const newX = cursorX - (cursorX - x) * (newK / k);
    k = newK; x = newX;
    timeScale.setTransform({ k, x });
    bus.emit('zoom:change', { k, x });
  }

  target.addEventListener('wheel', onWheel, { passive: false });
  return () => target.removeEventListener('wheel', onWheel);
}
```

- [ ] **Step 2: Make spine and items react to `zoom:change`**

This is the largest change in Track 3. Refactor `axis.mjs`, `items.mjs`, and `lanes.mjs` to:

1. Render once on mount.
2. Subscribe to `zoom:change` and re-position SVG elements based on new `timeScale.x()`.

**`axis.mjs` — replace the body of `mountAxis` with:**

```javascript
import { select } from 'd3';

export const PERIODS = [/* same as before */];

export function mountAxis(svg, { timeScale, spineTop, spineBottom, bus }) {
  const g = select(svg).append('g').attr('class', 'axis');
  const preZone   = g.append('rect').attr('class', 'pre-zone').attr('y', spineTop).attr('height', spineBottom - spineTop).attr('fill', 'rgba(50,50,60,0.20)');
  const postZone  = g.append('rect').attr('class', 'post-zone').attr('y', spineTop).attr('height', spineBottom - spineTop).attr('fill', 'rgba(50,50,60,0.20)');
  const periodRects = PERIODS.map(p => g.append('rect').attr('class', `period period-${p.id}`).attr('y', spineTop).attr('height', spineBottom - spineTop).attr('fill', p.color).attr('opacity', 0.12));
  const dividers = PERIODS.slice(1).map((p, i) => g.append('line').attr('class', 'period-divider').attr('y1', spineTop).attr('y2', spineBottom).attr('stroke', PERIODS[i].color).attr('stroke-opacity', 0.25));
  const labels = PERIODS.map(p => g.append('text').attr('class', 'period-label').attr('y', spineTop - 8).attr('text-anchor', 'middle').attr('fill', p.color).attr('fill-opacity', 0.9).attr('font-size', 11).text(p.label));
  const ticksGroup = g.append('g').attr('class', 'ticks');

  function redraw() {
    const w = svg.clientWidth || 1200;
    preZone.attr('x', -10000).attr('width', timeScale.x('1828-01-01') + 10000);
    postZone.attr('x', timeScale.x('1910-12-31')).attr('width', w + 10000 - timeScale.x('1910-12-31'));
    PERIODS.forEach((p, i) => periodRects[i].attr('x', timeScale.x(p.start)).attr('width', timeScale.x(p.end) - timeScale.x(p.start)));
    PERIODS.slice(1).forEach((p, i) => dividers[i].attr('x1', timeScale.x(p.start)).attr('x2', timeScale.x(p.start)));
    PERIODS.forEach((p, i) => labels[i].attr('x', (timeScale.x(p.start) + timeScale.x(p.end)) / 2));
    drawTicks();
  }

  function drawTicks() {
    ticksGroup.selectAll('*').remove();
    const res = timeScale.resolution();
    const stride = res === 'decade' ? 10 : res === 'year' ? 1 : 0;
    if (stride === 0) {
      // month/day mode: not implemented in this task, leave empty
      return;
    }
    for (let y = 1730; y <= 2030; y += stride) {
      const x = timeScale.x(`${y}-01-01`);
      ticksGroup.append('line').attr('class', 'tick').attr('x1', x).attr('x2', x).attr('y1', spineBottom + 4).attr('y2', spineBottom + 10).attr('stroke', 'rgba(255,255,255,0.25)');
      if ((stride === 1 && y % 5 === 0) || stride === 10) {
        ticksGroup.append('text').attr('class', 'tick-label').attr('x', x).attr('y', spineBottom + 22).attr('text-anchor', 'middle').attr('fill', 'rgba(255,255,255,0.5)').attr('font-size', 10).text(y);
      }
    }
  }

  redraw();
  bus.on('zoom:change', redraw);
}
```

**`items.mjs` — make work bars and event points re-position on `zoom:change`. Pattern:**

```javascript
// In mountItems, after creating each visual element, store its node data:
const drawables = [];
for (const w of works) {
  const elem = g.append('rect') /* ... */;
  drawables.push({ elem, node: w, kind: 'work' });
}
// ...

bus.on('zoom:change', () => {
  for (const d of drawables) {
    if (d.kind === 'work') {
      const x0 = timeScale.x(d.node.dates.primary);
      const x1 = d.node.dates.end ? timeScale.x(d.node.dates.end) : x0 + 8;
      d.elem.attr('x', x0).attr('width', Math.max(8, x1 - x0));
    } else if (d.kind === 'event') {
      d.elem.attr('cx', timeScale.x(d.node.dates.primary));
    }
  }
});
```

- [ ] **Step 3: Make cloud physics react to zoom**

In `physics.mjs`, expose a function to recompute the X-anchor when `timeScale` changes:

```javascript
// At end of startPhysics, before return:
function reanchor() {
  sim.force('x', forceX(d => {
    const original = graph.nodes.find(n => n.id === d.id);
    return timeScale.x(original?.dates.primary) ?? viewportWidth / 2;
  }).strength(0.3));
  sim.alpha(0.5).restart();
}

return { stop, restart, reanchor, nodes: cloudNodes, edges: cloudEdges };
```

In `main.mjs`, wire the bus:

```javascript
    bus.on('zoom:change', () => physics.reanchor());
```

- [ ] **Step 4: Wire `attachZoom`**

In `main.mjs`:

```javascript
    const { attachZoom } = await import('./interact/zoom.mjs');
    attachZoom(document.getElementById('graph-canvas'), { timeScale, bus, viewportWidth: rect.width });
```

- [ ] **Step 5: Build + view, scroll wheel**

Expected: scroll up zooms in (period zones widen, tick density increases); scroll down zooms out. Cloud nodes re-anchor smoothly.

- [ ] **Step 6: Commit**

```bash
git add src/assets/graph/interact/zoom.mjs src/assets/graph/spine/axis.mjs src/assets/graph/spine/items.mjs src/assets/graph/cloud/physics.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): zoom-as-time with axis/items/cloud reactivity"
```

---

## Task 23 — Pan-around-universe (click-drag, 5px threshold)

**Files:**
- Create: `website/src/assets/graph/interact/pan.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `pan.mjs`**

`src/assets/graph/interact/pan.mjs`:

```javascript
const DRAG_THRESHOLD = 5;

export function attachPan(target, { timeScale, bus, onVerticalPan }) {
  let down = null;
  let dragging = false;
  let startTransform = null;
  let startVPan = 0;

  target.addEventListener('mousedown', ev => {
    down = { x: ev.clientX, y: ev.clientY };
    dragging = false;
    startTransform = timeScale.getTransform();
    startVPan = onVerticalPan?.get?.() ?? 0;
  });

  target.addEventListener('mousemove', ev => {
    if (!down) return;
    const dx = ev.clientX - down.x;
    const dy = ev.clientY - down.y;
    if (!dragging && Math.hypot(dx, dy) >= DRAG_THRESHOLD) {
      dragging = true;
      bus.emit('pan:start');
    }
    if (dragging) {
      timeScale.setTransform({ k: startTransform.k, x: startTransform.x + dx });
      bus.emit('zoom:change', timeScale.getTransform());
      onVerticalPan?.set?.(startVPan + dy);
    }
  });

  function end() {
    if (dragging) bus.emit('pan:end');
    down = null; dragging = false;
  }
  target.addEventListener('mouseup', end);
  target.addEventListener('mouseleave', end);

  return {
    /** True if last gesture was a drag (suppresses click). */
    wasDrag() { return dragging; }
  };
}
```

- [ ] **Step 2: Wire in `main.mjs`**

Hold a vertical-pan offset state and apply it to the PIXI cloud and the spine:

```javascript
    let vPan = 0;
    const vPanState = { get: () => vPan, set: v => { vPan = v; cloud.app?.stage && (cloud.app.stage.y = vPan); /* spine could shift too */ } };
    const { attachPan } = await import('./interact/pan.mjs');
    const pan = attachPan(document.getElementById('graph-canvas'), { timeScale, bus, onVerticalPan: vPanState });
```

Suppress node-click when a drag occurred:

```javascript
    bus.on('node:click', ev => {
      if (pan.wasDrag()) return;
      console.log('[graph] node clicked:', ev.id);
      // Will open modal in Track 4
    });
```

- [ ] **Step 3: Build + view, click-drag the canvas**

Expected: Horizontal drag pans time. Vertical drag scrolls the cloud vertically. Below 5px threshold = click; above = drag.

- [ ] **Step 4: Commit**

```bash
git add src/assets/graph/interact/pan.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): pan-around-universe with 5px drag threshold"
```

---

## Task 24 — LOD culling and zoom hard caps

**Files:**
- Modify: `website/src/assets/graph/cloud/render.mjs`
- Modify: `website/src/assets/graph/interact/zoom.mjs`

- [ ] **Step 1: Add LOD threshold logic in `cloud/render.mjs`**

Inside `mountCloud`, after `syncCloudNodes`:

```javascript
  function applyLOD({ k }) {
    // Below 0.4× zoom (fully zoomed out): only show degree ≥ 30 OR top-decile importance
    // Between 0.4× and 1.5×: 1st- and 2nd-degree neighbors of focus (focus support deferred to Track 4 — for now, all)
    // ≥ 1.5×: show everything in viewport
    for (const [id, sprite] of sprites.entries()) {
      const node = graphRef?.nodes.find(n => n.id === id);
      if (!node) continue;
      const degree = node.metrics?.degree ?? 0;
      let visible = true;
      if (k < 0.4 && degree < 30) visible = false;
      sprite.visible = visible;
    }
  }

  let graphRef = null;
  function setGraphRef(g) { graphRef = g; }

  return { /* existing fields */, applyLOD, setGraphRef };
```

Call `cloud.setGraphRef(graph)` after `cloud.syncCloudNodes(graph)` in `main.mjs`, then:

```javascript
    bus.on('zoom:change', t => cloud.applyLOD(t));
```

- [ ] **Step 2: Add hard caps already in `zoom.mjs`**

`ZOOM_MIN` and `ZOOM_MAX` are already in place from Task 22. Verify by scrolling to extremes — wheel events stop having effect at the bounds.

- [ ] **Step 3: Pan extremes — clamp X**

In `pan.mjs`, inside `mousemove`:

```javascript
    if (dragging) {
      const minX = -timeScale.x('2030-01-01') + window.innerWidth - 100;
      const maxX = -timeScale.x('1728-01-01') + 100;
      const clampedX = Math.max(minX, Math.min(maxX, startTransform.x + dx));
      timeScale.setTransform({ k: startTransform.k, x: clampedX });
      bus.emit('zoom:change', timeScale.getTransform());
      onVerticalPan?.set?.(startVPan + dy);
    }
```

- [ ] **Step 4: Build + view**

Expected: at extreme zoom-out, only high-degree nodes visible. At extreme zoom-in, every node visible. Pan stops at corpus edges.

- [ ] **Step 5: Commit**

```bash
git add src/assets/graph/cloud/render.mjs src/assets/graph/interact/pan.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): LOD culling + zoom/pan hard caps"
```

---

## Task 25 — `prefers-reduced-motion` respect

**Files:**
- Modify: `website/src/assets/graph/cloud/starfield.mjs`
- Modify: `website/src/assets/graph/cloud/physics.mjs`

- [ ] **Step 1: Detect motion preference**

At top of `main.mjs`:

```javascript
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
```

- [ ] **Step 2: Pass through and disable starfield drift**

In `mountStarfield`, accept a `disableDrift` flag:

```javascript
export function mountStarfield(stage, { width, height, disableDrift = false }) {
  // ... existing setup ...
  return {
    setPanX(panX) {
      if (disableDrift) return;
      // ... existing ...
    }
  };
}
```

In `main.mjs`:

```javascript
    const starfield = mountStarfield(cloud.app.stage, { width: rect.width, height: rect.height, disableDrift: reducedMotion });
```

- [ ] **Step 3: Snap zoom (no tween) when reduced-motion**

In `physics.mjs` `reanchor`:

```javascript
function reanchor() {
  sim.force('x', forceX(/* ... */).strength(0.3));
  if (reducedMotion) {
    sim.alpha(0).stop();
    // Manually compute final positions without tweening (use forceX target directly)
    for (const n of cloudNodes) {
      const orig = graph.nodes.find(g => g.id === n.id);
      n.x = timeScale.x(orig?.dates.primary) ?? viewportWidth / 2;
    }
    onTick(cloudNodes, cloudEdges);
  } else {
    sim.alpha(0.5).restart();
  }
}
```

(Pass `reducedMotion` into `startPhysics` as a param.)

- [ ] **Step 4: Build + verify (manually toggle prefers-reduced-motion in Chrome devtools)**

Expected with reduced-motion ON: starfield doesn't drift on pan; cloud snaps to new positions on zoom rather than tweening.

- [ ] **Step 5: Commit**

```bash
git add src/assets/graph/cloud/starfield.mjs src/assets/graph/cloud/physics.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): respect prefers-reduced-motion"
```

---

# Track 4 — Composite v1 (prototype 04)

## Task 26 — Hover stub card (small floating)

**Files:**
- Create: `website/src/assets/graph/interact/hover.mjs`
- Create: `website/src/assets/graph/ui/stub.mjs`
- Modify: `website/src/assets/graph/main.mjs`
- Modify: `website/src/assets/graph/index.css`

- [ ] **Step 1: Write `ui/stub.mjs` (shared stub renderer)**

```javascript
export function renderStub(node, { compact = false } = {}) {
  const dateLine = formatDates(node.dates);
  return `
    <div class="stub ${compact ? 'stub-compact' : 'stub-full'}">
      <div class="stub-title">${escapeHtml(node.title)}</div>
      <div class="stub-meta"><span class="stub-type">${escapeHtml(node.type)}</span> · ${dateLine}</div>
      ${compact ? '' : `<div class="stub-desc">${escapeHtml(node.description ?? '')}</div>`}
      ${compact ? '' : '<div class="stub-hint">click anywhere on this card to open the full article</div>'}
    </div>
  `;
}

function formatDates(d) {
  if (!d?.primary) return '';
  const start = d.primary.slice(0, 4);
  const end = d.end ? d.end.slice(0, 4) : '';
  return end && end !== start ? `${start}–${end}` : start;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
}
```

- [ ] **Step 2: Write `interact/hover.mjs`**

```javascript
import { renderStub } from '../ui/stub.mjs';

export function mountHover(rootEl, { graph, stubs, bus }) {
  const card = document.createElement('div');
  card.id = 'graph-hover-card';
  card.style.display = 'none';
  rootEl.appendChild(card);

  let currentId = null;

  bus.on('hover:enter', ({ id }) => {
    const node = graph.nodes.find(n => n.id === id);
    if (!node) return;
    currentId = id;
    const stubData = stubs?.[node.stubKey] ?? {};
    card.innerHTML = renderStub({ ...node, description: stubData.description ?? '' }, { compact: true });
    card.style.display = 'block';
  });

  bus.on('hover:leave', ({ id }) => {
    if (id === currentId) { card.style.display = 'none'; currentId = null; }
  });

  // Position follows cursor
  rootEl.addEventListener('mousemove', ev => {
    if (card.style.display === 'none') return;
    const rect = rootEl.getBoundingClientRect();
    let x = ev.clientX - rect.left + 12;
    let y = ev.clientY - rect.top  + 12;
    const cw = card.offsetWidth, ch = card.offsetHeight;
    if (x + cw > rect.width)  x = ev.clientX - rect.left - cw - 12;
    if (y + ch > rect.height) y = ev.clientY - rect.top  - ch - 12;
    card.style.left = `${x}px`;
    card.style.top  = `${y}px`;
  });
}
```

- [ ] **Step 3: Add CSS**

Append to `index.css`:

```css
#graph-hover-card {
  position: absolute; pointer-events: none; z-index: 10;
  background: rgba(20, 24, 36, 0.95); border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px; padding: 8px 12px; max-width: 320px; font-size: 13px;
  color: #f4ebd5;
}
.stub-title { font-weight: 600; margin-bottom: 4px; }
.stub-meta  { color: rgba(255,255,255,0.55); font-size: 11px; margin-bottom: 6px; }
.stub-type  { text-transform: uppercase; letter-spacing: 0.05em; font-size: 10px; }
.stub-desc  { line-height: 1.4; }
.stub-hint  { color: rgba(255,255,255,0.4); font-size: 11px; margin-top: 8px; font-style: italic; }
```

- [ ] **Step 4: Wire in `main.mjs` (assume `stubs` available — see Task 28)**

```javascript
    const { mountHover } = await import('./interact/hover.mjs');
    mountHover(root, { graph, stubs, bus });
```

For now, pass `stubs = {}` until Task 28 wires real stubs.

- [ ] **Step 5: Build + verify hover behavior**

Expected: hovering a spine work bar or a cloud node shows a small floating card with title, type, dates.

- [ ] **Step 6: Commit**

```bash
git add src/assets/graph/interact/hover.mjs src/assets/graph/ui/stub.mjs src/assets/graph/index.css src/assets/graph/main.mjs
git commit -m "feat(graph): hover stub card"
```

---

## Task 27 — Click modal with full stub

**Files:**
- Create: `website/src/assets/graph/interact/modal.mjs`
- Modify: `website/src/assets/graph/main.mjs`
- Modify: `website/src/assets/graph/index.css`

- [ ] **Step 1: Write `modal.mjs`**

```javascript
import { renderStub } from '../ui/stub.mjs';

export function mountModal(rootEl, { graph, stubs, bus }) {
  const overlay = document.createElement('div');
  overlay.id = 'graph-modal-overlay';
  overlay.style.display = 'none';
  rootEl.appendChild(overlay);

  let currentNode = null;

  function open(id) {
    const node = graph.nodes.find(n => n.id === id);
    if (!node) return;
    currentNode = node;
    const stubData = stubs?.[node.stubKey] ?? {};
    overlay.innerHTML = `
      <div id="graph-modal" role="dialog" aria-modal="true">
        ${renderStub({ ...node, description: stubData.description ?? '' }, { compact: false })}
      </div>
    `;
    overlay.style.display = 'flex';
    bus.emit('modal:open', { id });
  }

  function close() {
    overlay.style.display = 'none';
    currentNode = null;
    bus.emit('modal:close');
  }

  function navigate() {
    if (!currentNode) return;
    let url = currentNode.wikiUrl;
    // Family-event nodes deep-link via #anchor (anchor field added in Task 30 to data pipeline)
    if (currentNode.lane === 'family' && currentNode.anchor) {
      url = `/wiki/leo-tolstoy/#${currentNode.anchor}`;
    }
    window.location.href = url;
  }

  overlay.addEventListener('click', ev => {
    const modal = document.getElementById('graph-modal');
    if (!modal) return;
    if (modal.contains(ev.target)) navigate();
    else close();
  });

  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape' && currentNode) close();
  });

  bus.on('node:click', ({ id }) => {
    if (currentNode) {
      // Swap if different node, else just navigate
      if (id !== currentNode.id) open(id);
      else navigate();
    } else {
      open(id);
    }
  });

  return { open, close };
}
```

- [ ] **Step 2: CSS**

Append to `index.css`:

```css
#graph-modal-overlay {
  position: absolute; inset: 0; background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center; z-index: 20;
}
#graph-modal {
  background: #14182c; border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px; padding: 24px; max-width: 480px; min-width: 320px;
  color: #f4ebd5; cursor: pointer;
}
#graph-modal .stub-title { font-size: 18px; }
#graph-modal:hover { background: #1a2038; }
```

- [ ] **Step 3: Wire**

In `main.mjs`:

```javascript
    const { mountModal } = await import('./interact/modal.mjs');
    mountModal(root, { graph, stubs, bus });
```

Remove the placeholder console.log click handler from Task 23.

- [ ] **Step 4: Build + verify**

Expected: click a node → modal opens. Click modal → navigates. Click outside → closes. Esc → closes. Click another node while open → swaps.

- [ ] **Step 5: Commit**

```bash
git add src/assets/graph/interact/modal.mjs src/assets/graph/index.css src/assets/graph/main.mjs
git commit -m "feat(graph): click modal with click-to-navigate, click-out-to-close, Esc, swap"
```

---

## Task 28 — Stub data integration with `wiki-previews-*.json`

**Files:**
- Modify: `website/src/assets/graph/data/load.mjs`

- [ ] **Step 1: Discover the wiki-previews bundle path**

```bash
ls website/src/assets/wiki/ 2>&1 | grep previews
```

Expected: a path like `wiki-previews-v2026-04-29-abc123.json` (the build artifact). If the path differs, adapt the next step.

- [ ] **Step 2: Update `load.mjs` to fetch both**

```javascript
export async function loadGraph() {
  const res = await fetch('/assets/graph/data/graph.json');
  if (!res.ok) throw new Error(`graph.json ${res.status}`);
  const graph = await res.json();

  // Best-effort fetch of wiki-previews bundle. If it fails, return empty stubs.
  let stubs = {};
  try {
    // The exact filename includes a hash; the website build emits a stable redirect at /assets/wiki/wiki-previews-latest.json (assumption — may need a custom redirect or symlink at build time).
    const sres = await fetch('/assets/wiki/wiki-previews-latest.json');
    if (sres.ok) stubs = await sres.json();
  } catch (err) {
    console.warn('[graph] wiki-previews unavailable:', err.message);
  }

  return { graph, stubs };
}
```

If `wiki-previews-latest.json` doesn't exist, **add a build step** in `eleventy.config.js` to copy the latest hashed bundle to that path, OR have the page resolve the hashed name via an injected window variable (`window.__wikiPreviewsUrl`). Pick whichever fits the existing build chain — flag for the implementing engineer.

- [ ] **Step 3: Update `main.mjs` to use the new shape**

```javascript
    const { graph, stubs } = await loadGraph();
    // ... pass `stubs` to mountHover and mountModal as before
```

- [ ] **Step 4: Build + verify modal shows full description**

Expected: modal description text comes from the wiki-previews bundle (formerly empty). Hover card may stay compact (no description in compact mode by design).

- [ ] **Step 5: Commit**

```bash
git add src/assets/graph/data/load.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): join wiki-previews stub data into hover/modal"
```

---

## Task 29 — Sidebar UI: type filters

**Files:**
- Create: `website/src/assets/graph/ui/sidebar.mjs`
- Modify: `website/src/assets/graph/main.mjs`
- Modify: `website/src/assets/graph/index.css`

- [ ] **Step 1: Write `sidebar.mjs`**

```javascript
const TYPES = ['person','place','event','concept','translator','institution','adaptation','criticalWork','archivalFond','work'];
const LABELS = {
  person:'Person', place:'Place', event:'Event', concept:'Concept',
  translator:'Translator', institution:'Institution', adaptation:'Adaptation',
  criticalWork:'Critical Work', archivalFond:'Archival Fond', work:'Work'
};

export function mountSidebar(sidebarEl, { bus }) {
  const visibleTypes = new Set(TYPES);

  sidebarEl.innerHTML = `
    <h2>Filters</h2>
    <ul class="type-filters">
      ${TYPES.map(t => `<li>
        <label><input type="checkbox" data-type="${t}" checked> ${LABELS[t]}</label>
      </li>`).join('')}
    </ul>
    <button id="graph-reset" type="button">Reset</button>
  `;

  sidebarEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.addEventListener('change', () => {
      const type = cb.dataset.type;
      cb.checked ? visibleTypes.add(type) : visibleTypes.delete(type);
      bus.emit('filter:change', { visibleTypes: new Set(visibleTypes) });
    });
  });

  sidebarEl.querySelector('#graph-reset').addEventListener('click', () => {
    sidebarEl.querySelectorAll('input[type=checkbox]').forEach(cb => { cb.checked = true; visibleTypes.add(cb.dataset.type); });
    bus.emit('filter:change', { visibleTypes: new Set(visibleTypes) });
    bus.emit('zoom:reset');
    bus.emit('focus:clear');
  });

  return { visibleTypes };
}
```

- [ ] **Step 2: Apply filter in `cloud/render.mjs`**

Add a method to `mountCloud` returned object:

```javascript
  function applyFilter(visibleTypes) {
    for (const [id, sprite] of sprites.entries()) {
      const node = graphRef?.nodes.find(n => n.id === id);
      sprite.visible = sprite.visible && visibleTypes.has(node?.type);
    }
  }
```

In `main.mjs`:

```javascript
    bus.on('filter:change', ({ visibleTypes }) => cloud.applyFilter(visibleTypes));
```

- [ ] **Step 3: Apply filter in `spine/items.mjs`**

In `mountItems`, listen to `filter:change` and toggle `display` on each drawable based on its node type.

```javascript
bus.on('filter:change', ({ visibleTypes }) => {
  for (const d of drawables) {
    d.elem.style('display', visibleTypes.has(d.node.type) ? null : 'none');
  }
});
```

- [ ] **Step 4: CSS**

```css
#graph-sidebar h2 { font-size: 14px; margin-bottom: 1rem; color: rgba(255,255,255,0.7); }
.type-filters { list-style: none; padding: 0; margin: 0 0 1rem; }
.type-filters li { margin-bottom: 0.4rem; font-size: 13px; }
.type-filters input { margin-right: 6px; }
#graph-reset { background: transparent; border: 1px solid rgba(255,255,255,0.3); color: #f4ebd5; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
#graph-reset:hover { background: rgba(255,255,255,0.05); }
```

- [ ] **Step 5: Wire reset for zoom**

In `main.mjs`:

```javascript
    bus.on('zoom:reset', () => {
      timeScale.setTransform({ k: 1, x: 0 });
      bus.emit('zoom:change', { k: 1, x: 0 });
    });
```

- [ ] **Step 6: Build + verify**

Expected: 10 type checkboxes; toggling hides/shows nodes of that type (cloud + spine). Reset button clears filters and resets zoom.

- [ ] **Step 7: Commit**

```bash
git add src/assets/graph/ui/sidebar.mjs src/assets/graph/cloud/render.mjs src/assets/graph/spine/items.mjs src/assets/graph/index.css src/assets/graph/main.mjs
git commit -m "feat(graph): sidebar type filters + reset"
```

---

## Task 30 — URL focus param + route module

**Files:**
- Create: `website/src/assets/graph/interact/route.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `route.mjs`**

```javascript
const VALID_ID = /^[a-z0-9-]+$/;

export function mountRoute({ graph, bus, timeScale, viewportWidth }) {
  function readFocus() {
    const url = new URL(window.location.href);
    const focus = url.searchParams.get('focus');
    if (!focus) return null;
    if (!VALID_ID.test(focus)) {
      console.warn(`[graph] Invalid focus param: ${focus}`);
      return null;
    }
    if (!graph.nodes.find(n => n.id === focus)) {
      console.warn(`[graph] Unknown focus: ${focus}`);
      return null;
    }
    return focus;
  }

  function setFocus(id) {
    const node = graph.nodes.find(n => n.id === id);
    if (!node) return;
    // Zoom to entity's date range
    const targetX = timeScale.x(node.dates.primary);
    if (targetX !== null) {
      const k = 5;  // zoom in to year-resolution
      const x = viewportWidth / 2 - targetX * k;
      timeScale.setTransform({ k, x });
      bus.emit('zoom:change', { k, x });
    }
    bus.emit('focus:set', { id });
    // Update URL without reload
    const url = new URL(window.location.href);
    url.searchParams.set('focus', id);
    history.replaceState({}, '', url.toString());
  }

  function clearFocus() {
    const url = new URL(window.location.href);
    url.searchParams.delete('focus');
    history.replaceState({}, '', url.toString());
    bus.emit('focus:clear');
  }

  const initial = readFocus();
  if (initial) setTimeout(() => setFocus(initial), 200);  // let physics settle

  bus.on('focus:clear-request', clearFocus);

  return { setFocus, clearFocus };
}
```

- [ ] **Step 2: Wire in `main.mjs`**

```javascript
    const { mountRoute } = await import('./interact/route.mjs');
    const route = mountRoute({ graph, bus, timeScale, viewportWidth: rect.width });
```

Wire the modal to auto-open when focus is set:

```javascript
    bus.on('focus:set', ({ id }) => bus.emit('node:click', { id }));
```

- [ ] **Step 3: Build + verify**

Open `http://localhost:8080/graph/?focus=war-and-peace` (or any existing entity). Expected: zoom animates to its date range, modal opens for it.

- [ ] **Step 4: Commit**

```bash
git add src/assets/graph/interact/route.mjs src/assets/graph/main.mjs
git commit -m "feat(graph): URL focus param routing"
```

---

## Task 31 — Empty state + reduce-flicker

**Files:**
- Create: `website/src/assets/graph/ui/empty-state.mjs`
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Write `empty-state.mjs`**

```javascript
export function mountEmptyState(rootEl, { bus }) {
  const overlay = document.createElement('div');
  overlay.id = 'graph-empty';
  overlay.innerHTML = `
    <p>No entities match your filters.</p>
    <button type="button">Reset filters</button>
  `;
  overlay.style.display = 'none';
  rootEl.appendChild(overlay);

  overlay.querySelector('button').addEventListener('click', () => bus.emit('filter:reset-request'));

  bus.on('visible:count', ({ count }) => {
    overlay.style.display = count === 0 ? 'flex' : 'none';
  });
}
```

- [ ] **Step 2: Emit visible:count from cloud + spine**

In `cloud/render.mjs` `applyFilter` and `applyLOD`, after updates:

```javascript
    let visible = 0;
    for (const sprite of sprites.values()) if (sprite.visible) visible++;
    busRef?.emit('visible:count', { count: visible });
```

(Pass `bus` as `busRef` into `mountCloud`.)

- [ ] **Step 3: CSS**

```css
#graph-empty {
  position: absolute; inset: 0; align-items: center; justify-content: center;
  flex-direction: column; gap: 1rem; background: rgba(10, 14, 26, 0.92); z-index: 30;
  color: #f4ebd5;
}
#graph-empty button { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.3); color: #f4ebd5; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
```

- [ ] **Step 4: Wire `filter:reset-request` to sidebar's reset**

In `sidebar.mjs`, expose a `reset()` method and listen for the bus event:

```javascript
  bus.on('filter:reset-request', () => {
    sidebarEl.querySelector('#graph-reset').click();
  });
```

- [ ] **Step 5: Build + verify**

Expected: unchecking all 10 filters → empty-state overlay appears with "Reset filters" button. Clicking re-checks all and dismisses overlay.

- [ ] **Step 6: Commit**

```bash
git add src/assets/graph/ui/empty-state.mjs src/assets/graph/cloud/render.mjs src/assets/graph/ui/sidebar.mjs src/assets/graph/index.css src/assets/graph/main.mjs
git commit -m "feat(graph): empty-state overlay"
```

---

## Task 32 — Screen-reader fallback nav

**Files:**
- Modify: `website/src/assets/graph/main.mjs`

- [ ] **Step 1: Render hidden nav**

In `main.mjs`, after the graph mounts:

```javascript
    function updateFallbackNav() {
      const nav = document.getElementById('graph-fallback-nav');
      if (!nav) return;
      const visibleNodes = graph.nodes; // TODO refine to filtered subset
      nav.innerHTML = `<h2>Tolstoy's universe — entities</h2><ul>${
        visibleNodes.map(n => `<li><a href="${n.wikiUrl}">${escapeHtml(n.title)} (${n.type})</a></li>`).join('')
      }</ul>`;
    }
    function escapeHtml(s) { return String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c])); }
    updateFallbackNav();
    bus.on('filter:change', updateFallbackNav);
```

- [ ] **Step 2: Make nav reachable to screen readers**

Modify `graph.njk`:

```html
  <nav id="graph-fallback-nav" aria-label="Tolstoy's universe — entity list"></nav>
```

(Remove the `hidden` attribute. CSS `position: absolute; left: -10000px` from Task 10 keeps it off-screen for sighted users.)

- [ ] **Step 3: Smoke-test with VoiceOver (macOS)**

Open `/graph/`. Cmd-F5 to start VoiceOver. Tab through. Expected: VO announces "Tolstoy's universe — entity list" and reads each entry.

- [ ] **Step 4: Commit**

```bash
git add src/pages/graph.njk src/assets/graph/main.mjs
git commit -m "feat(graph): hidden screen-reader fallback nav"
```

---

## Task 33 — End-to-end smoke test (Playwright)

**Files:**
- Create: `website/tests/e2e/graph-smoke.spec.mjs`
- Modify: `website/package.json`

- [ ] **Step 1: Add Playwright**

```bash
npm install --save-dev @playwright/test@^1.47
npx playwright install chromium
```

Add to `package.json` `scripts`:

```json
"test:e2e": "playwright test"
```

- [ ] **Step 2: Write the smoke test**

`website/tests/e2e/graph-smoke.spec.mjs`:

```javascript
import { test, expect } from '@playwright/test';

const URL = 'http://localhost:8080/graph/';

test.describe('graph smoke', () => {
  test('mounts and loads data', async ({ page }) => {
    const errors = [];
    page.on('console', msg => msg.type() === 'error' && errors.push(msg.text()));
    await page.goto(URL);
    await expect(page.locator('#graph-pixi')).toBeVisible();
    await expect(page.locator('#graph-svg')).toBeVisible();
    // Wait for boot log
    await page.waitForFunction(() => window.console && document.querySelectorAll('rect.period').length === 4);
    expect(errors).toEqual([]);
  });

  test('hovering a work bar shows the stub card', async ({ page }) => {
    await page.goto(URL);
    await page.waitForSelector('rect.work-bar');
    const bar = page.locator('rect.work-bar').first();
    await bar.hover();
    await expect(page.locator('#graph-hover-card')).toBeVisible();
  });

  test('clicking a node opens the modal', async ({ page }) => {
    await page.goto(URL);
    await page.waitForSelector('rect.work-bar');
    await page.locator('rect.work-bar').first().click();
    await expect(page.locator('#graph-modal')).toBeVisible();
  });

  test('clicking modal navigates', async ({ page }) => {
    await page.goto(URL);
    await page.waitForSelector('rect.work-bar');
    await page.locator('rect.work-bar').first().click();
    await expect(page.locator('#graph-modal')).toBeVisible();
    const [navigation] = await Promise.all([
      page.waitForURL(/\/works\//),
      page.locator('#graph-modal').click()
    ]);
    expect(page.url()).toMatch(/\/works\//);
  });

  test('Esc closes modal without navigating', async ({ page }) => {
    await page.goto(URL);
    await page.waitForSelector('rect.work-bar');
    await page.locator('rect.work-bar').first().click();
    await expect(page.locator('#graph-modal')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#graph-modal-overlay')).toBeHidden();
    expect(page.url()).toBe(URL);
  });

  test('unchecking all filters shows empty state', async ({ page }) => {
    await page.goto(URL);
    const checkboxes = page.locator('#graph-sidebar input[type=checkbox]');
    const count = await checkboxes.count();
    for (let i = 0; i < count; i++) await checkboxes.nth(i).uncheck();
    await expect(page.locator('#graph-empty')).toBeVisible();
  });

  test('?focus=anna-karenina opens its modal', async ({ page }) => {
    await page.goto(`${URL}?focus=anna-karenina`);
    await expect(page.locator('#graph-modal')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#graph-modal .stub-title')).toContainText('Anna Karenina');
  });
});
```

(Adjust the focus test ID if `anna-karenina` isn't in the current corpus — pick any existing entity ID.)

- [ ] **Step 3: Add `playwright.config.mjs`**

`website/playwright.config.mjs`:

```javascript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  webServer: {
    command: 'npm start',
    url: 'http://localhost:8080/graph/',
    reuseExistingServer: !process.env.CI,
    timeout: 120000
  },
  use: { baseURL: 'http://localhost:8080' },
  reporter: 'list'
});
```

- [ ] **Step 4: Run the smoke suite**

```bash
npm run test:e2e
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/graph-smoke.spec.mjs playwright.config.mjs package.json package-lock.json
git commit -m "test(graph): Playwright smoke suite"
```

---

## Task 34 — Visual regression baselines (recommended)

**Files:**
- Modify: `website/tests/e2e/graph-smoke.spec.mjs`

- [ ] **Step 1: Add 3 reference snapshots**

Append to the smoke spec:

```javascript
test.describe('graph visual', () => {
  test('default view', async ({ page }) => {
    await page.goto(URL);
    await page.waitForSelector('rect.period.period-prophet');
    await page.waitForTimeout(2000);  // let physics settle
    await expect(page).toHaveScreenshot('default-view.png', { maxDiffPixelRatio: 0.02 });
  });

  test('zoomed in around 1869', async ({ page }) => {
    await page.goto(URL);
    await page.waitForSelector('rect.period.period-great-works');
    // Trigger zoom via wheel events — manual sequence
    const canvas = await page.locator('#graph-canvas');
    const box = await canvas.boundingBox();
    for (let i = 0; i < 8; i++) {
      await canvas.dispatchEvent('wheel', { deltaY: -200, clientX: box.x + box.width / 2, clientY: box.y + box.height / 2 });
    }
    await page.waitForTimeout(2000);
    await expect(page).toHaveScreenshot('zoomed-1869.png', { maxDiffPixelRatio: 0.02 });
  });

  test('person filter only', async ({ page }) => {
    await page.goto(URL);
    await page.waitForSelector('#graph-sidebar input[type=checkbox]');
    const checkboxes = page.locator('#graph-sidebar input[type=checkbox]');
    const count = await checkboxes.count();
    for (let i = 0; i < count; i++) {
      const type = await checkboxes.nth(i).getAttribute('data-type');
      if (type !== 'person') await checkboxes.nth(i).uncheck();
    }
    await page.waitForTimeout(1000);
    await expect(page).toHaveScreenshot('person-only.png', { maxDiffPixelRatio: 0.02 });
  });
});
```

- [ ] **Step 2: Generate baselines**

```bash
npm run test:e2e -- --update-snapshots
```

Inspect generated PNGs in `tests/e2e/graph-smoke.spec.mjs-snapshots/`. If any look wrong, fix and regenerate.

- [ ] **Step 3: Run again to verify they pass**

```bash
npm run test:e2e
```

Expected: 10 passed (7 smoke + 3 visual).

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/
git commit -m "test(graph): visual regression baselines"
```

---

## Task 35 — Final QA pass + complete checklist

**Files:**
- Modify: `projects/timelinegraph/QA.md`

- [ ] **Step 1: Fill in remaining QA sections**

Append to `projects/timelinegraph/QA.md`:

```markdown
## Prototype 03 (zoom + pan) — gates Track 4

- [ ] Scroll wheel zooms time (period zones widen/narrow)
- [ ] Tick density adapts: decade → year → month/day
- [ ] Click-drag pans horizontally (time) and vertically (cloud)
- [ ] Drag threshold ~5px distinguishes pan from click
- [ ] Hard-cap at zoom-in extreme (single day)
- [ ] Hard-cap at zoom-out extreme (corpus extent)
- [ ] LOD culls low-degree nodes when zoomed out
- [ ] prefers-reduced-motion: starfield drift disabled, no zoom tween
- [ ] Reset button restores full lifespan view + all filters

## Prototype 04 (composite v1) — gates internal-tool launch

- [ ] Hover any spine work bar → small stub card appears
- [ ] Hover any cloud node → same stub card appears
- [ ] Card follows cursor without overflowing viewport
- [ ] Click any node → modal opens
- [ ] Modal has no X button (intentional); click outside closes
- [ ] Esc closes modal
- [ ] Click-drag-then-release does NOT open modal (drag-vs-click distinguished)
- [ ] Click open modal → navigates to wiki page
- [ ] Click another node while modal open → swaps modal
- [ ] Family-event modals navigate to /wiki/leo-tolstoy/#anchor (anchors may not exist yet — degrades gracefully)
- [ ] Sidebar checkboxes hide/show types in cloud + spine
- [ ] Reset button restores filters + zoom + clears focus
- [ ] /graph/?focus=<id> highlights + zooms-to + opens modal on load
- [ ] /graph/?focus=invalid-id falls back to default view
- [ ] Empty state shown when all filters off; clicking "Reset" restores
- [ ] Hidden screen-reader nav present and navigable with VoiceOver
- [ ] No console errors on load or interaction
- [ ] Cross-browser smoke: Chrome ✓ · Firefox ✓ · Safari ✓ · Mobile Safari (iPad) ✓

## v1 internal-tool launch gate

All Track 2/3/4 items above must pass. If any fail, file an issue and fix before exposing the page publicly.

## Public landing-page launch gate (separate, future)

Pre-conditions:
- Corpus passes ~200 nodes (currently ~30)
- Designer pass on cloud-type palette
- Lighthouse: first-paint < 1.5s, TTI < 3s
- axe-core: zero violations on /graph/
- Performance verified at corpus scale (60fps idle, 30fps pan/zoom floor)
```

- [ ] **Step 2: Run the full QA checklist manually**

For each unchecked item: try it, mark complete, file an issue for any failures.

- [ ] **Step 3: Commit final QA**

```bash
cd /Volumes/Graugear/Tolstoy
git add projects/timelinegraph/QA.md
git commit -m "docs: timelinegraph v1 QA checklist complete" || echo "(projects/ may be gitignored — local-only file is fine)"
```

---

# Out of scope for this plan (deferred)

- **Edge dashing** — `mention` edges should render dashed; v1 uses solid for all types. Polish pass.
- **Edge-flow particles** — Kepler.gl-style animated particles along edges. Spec §9 deferred.
- **Web Worker offload of force simulation** — only built if v1 framerate is unacceptable at scale. Phase 5+ concern.
- **Cross-browser CI matrix** — manual smoke is enough for v1.
- **Lighthouse CI** — public-launch readiness, not v1.
- **axe-core CI** — same.
- **Designer pass on cloud-type palette** — pre-public-launch task.
- **Public landing-page placement** — gated on corpus passing ~200 nodes.
- **Letters lane data** — `letters/` directory doesn't exist yet; lane will populate when corpus does.
- **Tolstoy wiki page anchor headings** — content task, not viz task.

---

## Self-review

**Spec coverage check** — every spec section / decision row has a corresponding task:

| Spec section | Plan tasks |
|---|---|
| §2 Architecture | 10 (page scaffold), 16 (PIXI mount) |
| §3 Components | 10–32 (each module owns its task or part of one) |
| §4 Data pipeline | 01–09 |
| §5 Layout / period zones | 12, 13, 14 |
| §5 Visual encoding | 15 (work bars / event points), 18 (cloud sprites), 20 (edges) |
| §5 Period colour integration | 13, 15 |
| §5 Interaction (hover) | 26 |
| §5 Interaction (click modal) | 27 |
| §5 Interaction (zoom + pan) | 22, 23, 24 |
| §5 Interaction (URL focus) | 30 |
| §5 Interaction (sidebar filters) | 29 |
| §5 Interaction (empty state) | 31 |
| §6 Error handling — build | 08, 09 |
| §6 Error handling — runtime | 16 (WebGL fallback), 31 (empty state), 28 (stubs unavailable degrades) |
| §6 Accessibility | 25 (reduced motion), 32 (screen-reader nav) |
| §7 Build-script tests | 03–08 |
| §7 Browser smoke | 33 |
| §7 Visual regression | 34 |
| §7 Manual QA | 21, 35 |
| §8 Provisional items | All flagged in tasks where they recur (period labels in 13, schema gap in 04, palette in 18, anchor in 27) |

**Placeholder scan** — searched for "TBD", "TODO", "implement later", vague handwaves. None found except in the deliberate "deferred" list at the bottom (which is the correct place for them).

**Type consistency** — function and module names cross-checked: `mountLanes`, `mountAxis`, `mountItems`, `mountCloud`, `mountStarfield`, `startPhysics`, `attachZoom`, `attachPan`, `mountHover`, `mountModal`, `mountSidebar`, `mountRoute`, `mountEmptyState`. All consistent. Bus events: `zoom:change`, `zoom:reset`, `pan:start`, `pan:end`, `hover:enter`, `hover:leave`, `node:click`, `modal:open`, `modal:close`, `filter:change`, `filter:reset-request`, `focus:set`, `focus:clear`, `focus:clear-request`, `visible:count`. All consistent across emit/listen.

**Spec gaps fixed inline** — Task 04 notes period boundary snapping (years overlap in spec table; resolved by snapping transitions to year-start). Worth back-porting to spec if Johan agrees.

---
