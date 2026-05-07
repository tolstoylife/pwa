# Deep Dive: True Scale of a Complete Tolstoy Resource

Report: 2026-04-15  
Context: Follows up on the initial scalability report of the same date. This analysis digs into the "connective tissue" — data categories that don't fall neatly into the basic wiki/ and works/ buckets but are essential for a complete scholarly resource.

---

## Executive summary

The initial estimate of ~13,000 files was based on works (767 with chapters) plus basic wiki entities (people, places, events, concepts from the TEI reference data). That estimate captured the skeleton but missed the ligaments.

A complete resource — one that tracks correspondence networks, publication histories, manuscript layers, translations, reception, institutions, chronology, archival references, visual materials, and intertextual connections — would be roughly **~40,000 files totalling ~250 MB of markdown/YAML**.

The wikilink graph would grow from ~60,000 edges to **~120,000+ edges** — a 16x denser knowledge graph than the basic estimate.

This changes the architectural calculus. Obsidian remains viable as an editing tool, but a complementary query layer (LightRAG or similar) shifts from "nice to have" to "practically necessary" for Claude to operate efficiently at this scale.

### Revised numbers at a glance

| Metric | Initial estimate | Revised estimate | Factor |
|--------|:----------------:|:----------------:|:------:|
| Total files | ~13,000 | ~40,000 | 3× |
| Total size (markdown/YAML) | ~46 MB | ~250 MB | 5× |
| Wikilinks (graph edges) | ~60,000 | ~120,000+ | 2× |
| Wiki entity types | 4 | 8–10 | 2.5× |
| Works tracked | 767 | 767 + 10,000 letters | 14× |

---

## What we were missing: category by category

### 1. Correspondence (~31,000 records, ~33 MB)

This is the single largest gap. Tolstoy exchanged an estimated **10,000+ letters** documented in Jubilee Edition volumes 60–90. Each letter is technically a work (genre: letter), but the correspondence network creates an entirely separate dimension of data.

**What needs tracking:**

- ~10,000 outgoing letters (as individual work files with text)
- ~3,500 preserved incoming letters
- ~850 unique correspondents (each needing a wiki page — many are already in the TEI personList, but their role as correspondents adds relationship data)
- Response chains: which letters reply to which
- Topic threads across correspondence (Tolstoy's evolving views on non-resistance, for example, can be traced through 200+ letters spanning 30 years)

**Schema impact:** The works schema already supports `genre: letter`. What's missing is a `replyTo` field linking letters into chains, and a way to surface correspondence networks (who wrote to whom, frequency, date ranges, primary topics).

**Why it matters:** Tolstoy's letters are the primary source for dating and contextualising his other works. A researcher asking "what was Tolstoy thinking about when he started Anna Karenina?" needs to cross-reference letters from 1873–1874. Without indexed correspondence, Claude would need to read hundreds of files to answer that question.

### 2. Publication history (~10,000 records, ~5 MB)

The current schema tracks a work's *first* publication date and venue. But each major work has a complex afterlife: multiple Russian editions (often with textual variants), foreign translations, censored and restored versions, journal serialisations, posthumous publications.

**What needs tracking:**

- ~7,700 distinct Russian edition records (767 works × ~10 editions average)
- ~2,000 foreign-language edition records
- ~30 censorship variant records (works with significant cuts or suppressions)
- ~40 journal serialisation records

**Schema impact:** The sidecar `.data.yaml` is the right place for this — an `editions[]` array per work. No new file type needed, but the sidecars would grow significantly.

**Why it matters:** Textual scholarship depends on knowing *which* edition is being referenced. The Maude translation of War and Peace differs from the Garnett translation, which differs from the Briggs translation. A resource that doesn't track editions can't support serious comparative work.

### 3. Manuscript and draft layers (~6,500 records, ~3 MB)

The schema already has `manuscripts[]` and `transcriptions[]` arrays — they're just empty. War and Peace alone went through 7+ major drafts. The Jubilee Edition documents manuscript details for every major work.

**What needs tracking:**

- ~500 distinct manuscript records across all works
- ~1,500 transcription records (Sophia Tolstaya alone copied thousands of pages)
- Archival locations for each manuscript (6 major repositories)
- Digitisation status (which manuscripts have been scanned and where)

**Schema impact:** Minimal — the fields exist. This is a population effort, not a design effort.

**Why it matters:** The manuscript layer is what separates a reading resource from a scholarly resource. Genetic criticism — studying how a text evolved through drafts — is a major branch of Tolstoy studies.

### 4. Translations and translators (~1,000 records, ~2 MB)

Tolstoy was the most translated Russian author of the 19th century. English translations alone span dozens of translators across 150 years.

**What needs tracking:**

- ~150 translator bio pages (Aylmer Maude, Constance Garnett, Louise and Aylmer Maude, Isabel Hapgood, Leo Wiener, Richard Pevear & Larissa Volokhonsky, etc.)
- ~800 translation edition records
- Translator–work relationships (who translated what, when, from which source text)

**Schema impact:** New wiki entity type: `translator`. New array in work frontmatter: `translationEditions[]`.

**Why it matters:** Translation choice is one of the most common questions readers have ("which translation of Anna Karenina should I read?"). A resource that can't answer this systematically is incomplete for its core audience.

### 5. Reception and criticism (~3,800 records, ~6 MB)

No current schema coverage. Contemporary reviews, later critical works, and adaptations (film, opera, theatre) are entirely untracked.

**What needs tracking:**

- ~1,200 contemporary Russian review records
- ~2,000 English-language critical work records
- ~150 adaptation records (film, opera, stage)
- ~400 scholarly monograph records

**Schema impact:** New arrays: `reviews[]` and `adaptations[]` in work frontmatter. Expanded `relatedWorks[]` relationship types to include `adapted-to-film`, `reviewed-in`, etc.

	**Why it matters:** Reception history contextualises works for readers. Knowing that Anna Karenina was initially received poorly by Russian critics, or that Tolstoy disliked the first film adaptation of his work, adds scholarly depth.

### 6. Institutions (~140 records, ~500 KB)

Publishers, journals, literary circles, religious movements, schools, archives. Currently scattered across person and place pages with no dedicated entity type.

**What needs tracking:**

- ~35 publishing houses (Russian, Western European, American)
- ~55 journals and newspapers
- ~18 literary circles and salons
- ~12 archival repositories
- ~9 religious/philosophical movements (Tolstoyans, Doukhobors, etc.)
- ~6 educational institutions

**Schema impact:** New wiki entity type: `institution`.

### 7. Chronology and events (~7,350 records, ~4 MB)

The current estimate of ~500 events is too conservative. A day-by-day chronology of Tolstoy's life (well-documented from diaries, letters, and Sophia's diary) yields ~3,000 documented events. Add biographical milestones, work milestones, and historical events, and the total approaches 7,000+.

**What needs tracking:**

- ~3,000 day-by-day chronology entries
- ~2,000 biographical events (births of children, relocations, illnesses, meetings)
- ~2,300 work milestone events (completion dates, publication announcements, censorship actions)
- ~50 major historical events Tolstoy witnessed or responded to

**Schema impact:** The `event` wiki entity type exists but needs timeline-specific fields: `dateStart`, `dateEnd`, and relationship arrays to people, works, and places.

### 8. Visual materials (~2,360 metadata records, ~3 MB)

Photographs, portraits, manuscript facsimiles, maps. The binary files exist (or will be sourced), but there's no metadata layer connecting them to the knowledge graph.

**What needs tracking:**

- ~200 portraits and photographs of Tolstoy
- ~300 family photographs
- ~500 manuscript facsimile key pages
- ~30 maps (estates, journeys, battle sites from War and Peace)
- ~100 artworks and illustrations

**Schema impact:** New entity type or lightweight metadata stub. Each image needs: subject, date, creator, provenance, license, and wikilinks to the entities depicted.

### 9. Intertextual references (~1,500 records, ~3.5 MB)

What Tolstoy read, who influenced him, and who he influenced. This is the scholarly apparatus that connects Tolstoy to the broader literary and philosophical world.

**What needs tracking:**

- ~500 external works cited or referenced in Tolstoy's writing
- ~800 titles from Tolstoy's documented reading lists (from diaries and letters)
- ~100 people significantly influenced by Tolstoy (Gandhi, Rilke, Wittgenstein, Martin Luther King Jr., etc.)
- ~15 ideological movements

**Schema impact:** New arrays: `citedWorks[]`, `readingList[]`, `influencedBy[]`, `influences[]`.

---

## Revised total estimate

### File count by category

| Category | Files | Size (MB) | New entity types needed |
|----------|------:|----------:|------------------------|
| Works (overview + sidecar + text landing) | 2,300 | 8 | — |
| Works (chapter/text files) | 6,100 | 33 | — |
| Letters (as works with text) | 10,000 | 20 | — |
| Wiki: persons (TEI + correspondents + translators) | 4,100 | 16 | `translator` |
| Wiki: places (TEI) | 770 | 2 | — |
| Wiki: events + chronology | 7,350 | 4 | — (expand `event`) |
| Wiki: concepts | 200 | 1 | — |
| Wiki: institutions | 140 | 0.5 | `institution` |
| Publication edition stubs | 2,000 | 2 | — (sidecar data) |
| Reception/criticism stubs | 3,800 | 6 | `adaptation`, `criticalWork` |
| Archival fond pages | 60 | 0.2 | `archivalFond` |
| Image metadata stubs | 2,360 | 3 | `image` |
| Intertextual reference stubs | 1,500 | 3.5 | — |
| Index/derived files | 50 | 2 | — |
| Source cards | 100 | 0.5 | — |
| **TOTAL** | **~40,800** | **~250 MB** | **5 new types** |

### Wikilink graph density

| Source | Edges |
|--------|------:|
| Chapter files (10 links/chapter avg.) | 61,000 |
| Letter files (8 links/letter avg.) | 80,000 |
| Person pages (5 outbound links avg.) | 20,500 |
| Place pages (3 outbound links avg.) | 2,300 |
| Event pages (2 outbound links avg.) | 14,700 |
| Institution pages (4 outbound links avg.) | 560 |
| Edition/translation stubs (3 links avg.) | 6,000 |
| Image metadata (2 links avg.) | 4,700 |
| Intertextual stubs (3 links avg.) | 4,500 |
| **Total (with overlap)** | **~120,000** |
| **Unique edges (estimated)** | **~45,000** |

---

## Implications for architecture

### Obsidian

40,000 files is within Obsidian's documented operational range on desktop (users report 50,000+ files working), but it's firmly in the "needs management" zone:

- **Link autocomplete** will be slow (4+ second lag per keystroke is documented at this scale)
- **Graph view** requires aggressive filtering — global graph with 40,000 nodes and 45,000 edges is unusable without folder/tag scoping
- **Search** remains fast after initial indexing
- **Mobile** is effectively unusable at this scale (3+ minute startup)

**Verdict:** Obsidian works as a *selective editing tool* — you open it to work on specific files, not to browse the full vault. For navigation and discovery, you need something else.

### LightRAG (or equivalent query layer)

At 120,000 wikilinks and 40,000 files, a knowledge graph becomes essential for three operations:

1. **Cross-reference queries**: "Which people appear in both War and Peace and the 1870s letters?" requires traversing the graph, not reading files sequentially.

2. **Lint operations**: Checking for contradictions, orphan pages, missing cross-references across 40,000 files is computationally expensive without an index.

3. **Contextual writing**: When Claude writes a new wiki article about a person, it needs to know every work, letter, event, and place associated with that person — information scattered across potentially hundreds of files.

**Verdict:** LightRAG shifts from "Phase B nice-to-have" to "co-requisite with Phase 3 TEI ingestion." Without it, Claude's context window becomes the bottleneck.

### Dual-system architecture (recommended)

```
┌─────────────────────────────────────────────────────────┐
│  Obsidian vault (editing)                               │
│  40,000 .md files · 250 MB · wiki/ + works/ + sources/  │
└──────────────────────┬──────────────────────────────────┘
                       │ git commit
                       ▼
              ┌────────────────┐
              │  File watcher  │  (watchdog, 5-min debounce)
              └────────┬───────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  LightRAG index (querying)                               │
│  Ollama (Qwen2.5-14B) · NetworkX graph · NanoVectorDB    │
│  120,000 edges · 40,000 nodes · ~2 GB index on disk      │
└──────────────────────┬───────────────────────────────────┘
                       │ query API
                       ▼
              ┌────────────────┐
              │  Claude (ops)  │  ingest · query · lint
              └────────────────┘
```

**Initial indexing cost:** ~40,000 docs × 10 sec/doc = ~111 hours with Qwen2.5-14B locally. Can run as an overnight batch over 5 nights, or ~2 hours with API ($20–30 one-time cost).

**Daily incremental sync:** 50 changed files × 10 sec = ~8 minutes. Negligible.

---

## Local model recommendation: Ollama on Mac Mini 24 GB

For the entity extraction and relationship mapping that LightRAG needs, the model must handle English and Russian text, extract named entities reliably, and run efficiently enough for batch processing.

### Hardware constraints

Mac Mini with 24 GB unified memory. After OS and Ollama overhead (~4 GB), approximately 20 GB is available for model inference.

### Recommended: Qwen2.5-14B (Q4_K_M quantisation)

| Metric | Value |
|--------|-------|
| VRAM usage | 9–11 GB |
| Tokens/sec (Apple Silicon) | ~20–25 |
| Context window | 128k tokens |
| Russian language support | Trained on 29 languages including Russian |
| Entity extraction quality | 9/10 (strong structured output) |
| Batch time (40,000 docs) | ~110 hours (~5 overnight runs) |

**Why Qwen2.5-14B:**

- Explicitly trained on multilingual data including Russian Cyrillic
- Strong performance on information extraction and structured output tasks
- 128k context window handles full documents with room for prompt
- Fits comfortably in 24 GB with headroom for concurrent processes
- LightRAG developers benchmark against Qwen models

**Installation:**

```bash
ollama pull qwen2.5:14b
```

### Alternative: Mistral-Nemo-12B (if speed is critical)

~40% faster throughput (28–32 tokens/sec) with a slight quality drop and less explicit Russian support. Good fallback if Qwen2.5-14B proves too slow.

```bash
ollama pull mistral-nemo:12b
```

### Not recommended at this time

- **Qwen3-32B**: Excellent quality but uses 21–24 GB — too tight on 24 GB hardware. Risk of OOM under sustained batch load.
- **Llama3.1-8B / Gemma2-9B**: Fast but weaker on Russian and less reliable entity extraction. Would need more human review of results.
- **Any API-based model**: Unnecessary cost for a batch job that can run locally overnight.

---

## What the schema needs

The current `tolstoy-works-schema.md` v5 and `wiki-schema.md` cover ~80% of the full scope. The remaining 20% requires:

### New wiki entity types (5)

1. **`translator`** — name, dates, Wikidata QID, languages, notable translations, bio
2. **`institution`** — name, type (publisher/journal/archive/school/movement), founded, location, relationships
3. **`adaptation`** — title, type (film/opera/stage/radio), year, director/creator, source work
4. **`criticalWork`** — title, author, year, subject works, summary
5. **`archivalFond`** — repository, collection name, call number range, contents summary, digitisation status

### New/expanded frontmatter arrays in works schema

- `editions[]` — edition ID, publisher, date, format, language, translator, textual notes
- `translationEditions[]` — language, translator, publisher, date, source text edition
- `reviews[]` — source, author, publication, date, excerpt
- `citedWorks[]` — external work title, author, context of citation
- `replyTo` — (for letters) link to the letter being replied to

### Derived/index files (new)

- Master timeline (chronological index of all events)
- Correspondence network index (who wrote to whom, frequency, date ranges)
- Translation matrix (which works translated into which languages by whom)
- Digitisation status matrix (which archives have digitised which manuscripts)

---

## Phased approach: what to build when

### Now (Phase 2, current): ~1,500 files
Focus on proving the model with core works and inner-circle entities. No RAG needed yet.

### Phase 3 (TEI ingestion): → ~5,000 files
Ingest 3,113 persons and 770 places from TEI reference data. This is where Obsidian starts feeling the strain on autocomplete, and where a query layer starts paying for itself.

**Decision point: stand up LightRAG before or during Phase 3.**

### Phase 4 (biographical sources): → ~8,000 files
Ingest Birukoff, Maude, and supplementary biographical sources. Events and chronology data grows rapidly. Correspondence tracking begins.

### Phase 5 (source texts + wikilinks): → ~15,000 files
Convert TEI chapter files to markdown. Letters begin ingestion. Publication history and translation data starts populating.

### Phase 6+ (full scope): → ~40,000 files
Manuscript layers, reception history, visual materials, intertextual references. The full scholarly apparatus.

**The RAG layer should be operational by Phase 3. Everything after that assumes it exists.**

---

## Design decisions (resolved 2026-04-15)

### 1. Letters: separate `letters/` folder ✓

Letters get their own top-level folder `website/src/letters/` using the same works schema (`genre: letter`). This keeps `works/` focused on literary and philosophical output while giving the 10,000+ letters their own navigable home. Letters remain part of the unified wikilink namespace — they can `[[link]]` to anything in `wiki/`, `works/`, `images/`, or other letters.

### 2. Events: tiered approach ✓

Following the pattern used by the Darwin Correspondence Project, Van Gogh Letters, and the CIDOC-CRM cultural heritage standard:

- **Tier 1 (~50):** Full wiki pages with prose — major life events (excommunication, flight from Yasnaya Polyana, birth of each child, etc.)
- **Tier 2 (~500):** Lightweight `.md` stubs with frontmatter + 1-2 sentences + wikilinks
- **Tier 3 (~6,500):** A single `chronology.yaml` in `_data/`, rendered into a public timeline view by Eleventy

Rationale: Obsidian's graph is most useful when nodes represent *entities* (people, places, works), not *dates*. 7,000 tiny event stubs would create noise without proportional value.

### 3. Images: separate `images/` section, all individual files ✓

Every image gets its own `.md` metadata stub in `website/src/images/`. Each file has frontmatter (artist, date, subject, collection, license) and a one-line caption. All are fully wikilink-able.

2,360 files at ~500 bytes each adds only ~1.2 MB to the vault — negligible performance impact compared to the 10,000 letter files. Consistency beats compactness: having some images as files and others as frontmatter arrays would be confusing to maintain.

### 4. Editions: always in sidecar `.data.yaml` ✓

Edition data (Russian editions, translations, censored variants) lives in the work's sidecar `.data.yaml` as `editions[]` arrays. No separate file needed — the sidecar is machine-readable YAML, not something browsed by hand, so length isn't a readability concern. Each work has one canonical text (the markdown chapter files) and the overview page is the metadata hub.

### 5. MVP scope: literary works first (~1,000 files) ✓

Focus on the 20-30 most-read works with full text + wikilinks + overview pages. Smaller wiki: ~100 people, ~20 places. Ship something readers can actually read before building the full scholarly apparatus.

This is achievable without RAG and within Obsidian's comfortable operating range.

---

## Revised vault structure (post-decisions)

```
website/src/                 ← Obsidian vault root, one unified wikilink namespace
├── wiki/                    ← people, places, events, concepts, institutions
├── works/                   ← literary & philosophical works (767)
├── letters/                 ← correspondence (NEW — 10,000+)
├── images/                  ← image metadata pages (NEW — 2,360)
├── sources/                 ← source cards, index, log (excluded from Eleventy)
├── _staging/                ← unverified material (not in git)
├── _data/
│   └── chronology.yaml      ← tier-3 events (6,500 daily entries)
├── pages/                   ← static pages
├── posts/                   ← blog/news
└── common/                  ← feeds, sitemap, PWA
```

### Revised file counts (post-decisions)

| Section | Files | Size (MB) |
|---------|------:|----------:|
| works/ (overview + sidecar + text landing + chapters) | 8,400 | 33 |
| wiki/ (persons, places, tier-1/2 events, concepts, institutions) | 5,340 | 15 |
| letters/ | 10,000 | 20 |
| images/ | 2,360 | 1.2 |
| sources, indexes, derived | 350 | 2 |
| _data/ (chronology.yaml, etc.) | 5 | 1 |
| **Total vault files** | **~26,500** | **~72 MB** |

Note: reduced from ~40,000 in the pre-decision estimate because tier-3 events (~6,500) moved to a data file and image stubs replaced heavier image+frontmatter alternatives.

### Revised wikilink density

| Source | Edges |
|--------|------:|
| Chapter files (10 links/chapter avg.) | 61,000 |
| Letter files (8 links/letter avg.) | 80,000 |
| Person pages (5 outbound links avg.) | 20,500 |
| Place pages (3 outbound links avg.) | 2,300 |
| Event pages, tier 1+2 (3 outbound links avg.) | 1,650 |
| Institution pages (4 outbound links avg.) | 560 |
| Image pages (3 links avg.) | 7,080 |
| **Total (with overlap)** | **~115,000** |
| **Unique edges (estimated)** | **~42,000** |

---

## MVP roadmap

### Phase 1 (current): Literary works first → ~1,000 files

- 20-30 most-read works with full text, wikilinks, and overview pages
- ~100 inner-circle person pages
- ~20 key place pages
- No RAG needed. Obsidian handles this easily.

### Phase 2: Expand works + begin wiki backbone → ~3,000 files

- 100 core works with text
- 300 inner-circle persons (from TEI tier-1)
- 50 key places
- 50 major events (tier 1)
- **Decision point: evaluate whether to stand up LightRAG.**

### Phase 3: TEI ingestion → ~8,000 files

- Full TEI person/place ingestion (3,113 + 770)
- 500 notable events (tier 2)
- Chronology data file
- **LightRAG must be operational by this point.**

### Phase 4: Biographical sources + correspondence → ~18,000 files

- Birukoff, Maude, supplementary sources
- Letter ingestion begins
- Publication history and translation data starts populating

### Phase 5: Full scope → ~26,500 files (text layer)

- All images with metadata
- Manuscript layers
- Reception history
- Intertextual references
- Complete scholarly apparatus

---

## Appendix: the scan pipeline — an unresolved scaling question

The estimates above cover the **text and metadata layer** — markdown files and YAML. But the project also aims to acquire scans of original source documents: letters, manuscripts, diary pages, first editions. This creates a second layer of data that dwarfs the text layer.

### Source material scan inventory

| Category | Items | Avg pages | Total scans |
|----------|------:|----------:|------------:|
| Letters (outgoing) | 10,000 | 3 | 30,000 |
| Letters (incoming) | 3,500 | 2 | 7,000 |
| Manuscripts & drafts | 500 | 50 | 25,000 |
| Diary pages | 13 vols | 300 | 3,900 |
| Sophia Tolstaya's diaries | 3 periods | 400 | 1,200 |
| First editions (key pages) | 100 | 15 | 1,500 |
| Photographs & portraits | 500 | 1 | 500 |
| Maps & estate plans | 30 | 1 | 30 |
| Artworks | 100 | 1 | 100 |
| Censorship & legal docs | 50 | 7 | 350 |
| **Total** | **~14,800** | | **~69,600** |

### Storage

- Raw scans (JPEG, 300dpi): ~136 GB
- Compressed scans (WebP): ~34 GB
- OCR text output: ~136 MB
- All binaries live in `primary-sources/`, not in the vault

### The open question: scan metadata granularity

If every scanned page gets its own `.md` metadata stub in `images/`, the vault jumps to **~94,000 files** — past Obsidian's practical limit. Two alternatives:

1. **Per-item stubs** (1 stub per letter/manuscript/diary, pages as frontmatter arrays): vault stays at ~39,000 files. Loses per-page wikilinks.
2. **Per-page stubs for everything**: 94,000 files. Maximum granularity. Obsidian becomes a selective editor; all navigation goes through LightRAG.
3. **Hybrid**: Per-page for short items (letters: 1-3 pages), per-item for long items (manuscripts: 50+ pages). ~65,000 files.

**Decision deferred.** The scan pipeline is a Phase 5+ concern. The important numbers to remember: ~70,000 scanned pages, ~34–136 GB of binary storage, and a vault file count that could triple depending on the metadata granularity we choose.
