# Wiki Rewrite Workflow at Scale

Report: 2026-04-15  
Context: How do we keep 26,500+ wiki pages accurate and cross-referenced as new sources are ingested? The current approach (Claude reads everything sequentially) breaks down past ~5,000 files. This document designs the scaled workflow, separates what needs Claude from what can be scripted, and estimates the token costs.

---

## The problem

The LLM Wiki pattern says: when new information arrives, update all affected pages. At small scale this works — Claude reads the source, reads the affected pages, rewrites them. But the cost grows multiplicatively:

- Each ingest session touches **~35 wiki pages**
- Each page update requires reading **~8 related pages** for contradiction checks
- Total: **~280 page reads per ingest**, or **~560K tokens of reading**
- Claude's context window: **200K tokens**

By Phase 3 (~8,000 files), a single ingest can't fit in one context window. By Phase 5 (~26,500 files), it's 3× the context window. We need a different architecture.

---

## Design principle: separate intelligence from computation

Most of what happens during a wiki rewrite session is **mechanical** — reading files, comparing strings, checking wikilink targets, computing diffs. Only a fraction requires **reasoning** — deciding what a new source means for an existing claim, choosing how to phrase a correction, resolving ambiguity.

The workflow splits into three layers:

| Layer | Runs when | Requires Claude? | Runs on |
|-------|-----------|:-----------------:|---------|
| **Scripted pipeline** (Python/bash) | Nightly cron | No | Mac Mini CPU |
| **LightRAG index** (Ollama + local model) | Nightly cron | No | Mac Mini GPU (Qwen2.5-14B) |
| **Claude sessions** (interactive or scheduled) | On demand | Yes | API |

---

## The three-phase rewrite workflow

### Phase A: Scripted pre-processing (cron, nightly, zero tokens)

Python/bash scripts that run as cron jobs with zero API cost. These prepare the ground for Claude.

#### A1. Wikilink graph extraction
```bash
# Runs nightly. Parses all .md files, extracts [[wikilinks]], builds adjacency list.
# Output: _generated/graph.json (nodes, edges, inbound/outbound counts)
python3 scripts/extract-graph.py --vault-dir website/src/ --output _generated/graph.json
```
**What it produces:** A JSON file mapping every page to its inbound and outbound wikilinks. Claude can query this instead of reading files to understand relationships.

**Cost:** 0 tokens. ~30 seconds for 26,500 files.

#### A2. Frontmatter index
```bash
# Extracts all YAML frontmatter into a single searchable index.
# Output: _generated/frontmatter-index.json
python3 scripts/extract-frontmatter.py --vault-dir website/src/ --output _generated/frontmatter-index.json
```
**What it produces:** Every page's frontmatter as a flat JSON array. Claude can search dates, people, places, relationships without reading individual files.

**Cost:** 0 tokens. ~15 seconds for 26,500 files.

#### A3. Change detection
```bash
# Compares current vault state against last-indexed state.
# Identifies new, modified, and deleted files since last LightRAG sync.
# Output: _generated/changes-since-last-sync.json
python3 scripts/detect-changes.py --vault-dir website/src/ --state-file _generated/last-sync-state.json
```
**What it produces:** A list of files that changed since the last sync, with diffs.

**Cost:** 0 tokens. ~5 seconds.

#### A4. Orphan and dead-link detection
```bash
# Uses graph.json to find: orphan pages (no inbound links),
# dead wikilinks (targets that don't exist), pages with 0 outbound links.
# Output: _generated/lint-report.json
python3 scripts/lint-graph.py --graph _generated/graph.json --vault-dir website/src/
```
**What it produces:** Mechanical lint issues that don't require judgement. Claude only needs to see the *results*, not do the scanning.

**Cost:** 0 tokens. ~10 seconds.

#### A5. LightRAG incremental sync
```bash
# Re-indexes changed files in LightRAG. Uses Ollama locally.
# Runs AFTER A3 to know which files changed.
python3 scripts/lightrag-sync.py --changes _generated/changes-since-last-sync.json
```
**What it produces:** Updated LightRAG index (entities, relationships, embeddings).

**Cost:** 0 API tokens. ~10 sec/file × number of changed files. Local compute only (Qwen2.5-14B via Ollama).

#### A6. Contradiction candidate detection
```bash
# Compares frontmatter fields across pages that reference the same entities.
# Flags cases where two pages disagree on a date, location, or relationship.
# Output: _generated/contradiction-candidates.json
python3 scripts/detect-contradictions.py --frontmatter _generated/frontmatter-index.json
```
**What it produces:** Pairs of pages that have conflicting factual claims in their frontmatter (e.g., two pages disagree on a birth date). These are *candidates* — some may be legitimate (OS vs NS dates). Claude resolves the ambiguous ones.

**Cost:** 0 tokens. ~20 seconds.

### Nightly cron summary

```bash
# /etc/crontab or launchd plist — runs at 02:00 every night
# Total runtime: ~5-15 minutes (plus LightRAG sync time for changed files)

#!/bin/bash
cd /path/to/tolstoy-project

# Step 1: Mechanical analysis (30-60 seconds)
python3 scripts/extract-graph.py --vault-dir website/src/ --output _generated/graph.json
python3 scripts/extract-frontmatter.py --vault-dir website/src/ --output _generated/frontmatter-index.json
python3 scripts/detect-changes.py --vault-dir website/src/ --state-file _generated/last-sync-state.json
python3 scripts/lint-graph.py --graph _generated/graph.json --vault-dir website/src/
python3 scripts/detect-contradictions.py --frontmatter _generated/frontmatter-index.json

# Step 2: LightRAG sync (requires Ollama running, ~10 sec/changed file)
python3 scripts/lightrag-sync.py --changes _generated/changes-since-last-sync.json

# Step 3: Generate daily briefing for Claude
python3 scripts/generate-briefing.py \
  --changes _generated/changes-since-last-sync.json \
  --lint _generated/lint-report.json \
  --contradictions _generated/contradiction-candidates.json \
  --output _generated/daily-briefing.md
```

The **daily briefing** is the key output — a single markdown file summarising what changed, what's broken, and what needs Claude's attention. Claude reads this at the start of each session instead of scanning the vault.

---

### Phase B: Claude ingest session (interactive, costs tokens)

This is the part that requires Claude's reasoning. But it's now *much* cheaper because Claude reads pre-processed summaries instead of raw files.

#### B1. Read the daily briefing (~2K tokens)

Claude reads `_generated/daily-briefing.md` — a compact summary of:
- Files changed since last session
- New lint issues (orphans, dead links)
- Contradiction candidates (pairs of pages with conflicting facts)
- LightRAG sync status

#### B2. Source reading and fact extraction (~20-50K tokens per source)

Claude reads the new source (e.g., a chapter of Birukoff biography) and produces a structured **update manifest** — a JSON file listing every factual claim and which wiki pages it affects.

```json
{
  "source": "Birukoff, Chapter 12: The Crisis of 1880-1882",
  "claims": [
    {
      "fact": "Tolstoy began writing Confession in autumn 1879",
      "affects_pages": ["Confession", "Leo Tolstoy"],
      "action": "verify_date",
      "current_value": "1879 (no month specified)",
      "new_value": "1879-09 (autumn 1879)",
      "confidence": "high",
      "source_quote": "В осень 1879 года Толстой начал писать «Исповедь»"
    },
    {
      "fact": "Sophia Tolstaya copied the manuscript of Confession three times",
      "affects_pages": ["Sophia Tolstaya", "Confession"],
      "action": "add_new_claim",
      "confidence": "high",
      "source_quote": "Софья Андреевна переписывала рукопись трижды"
    }
  ]
}
```

**This is where Claude's intelligence is irreplaceable** — understanding Russian text, evaluating reliability, identifying which pages are affected.

**Token cost:** Depends on source length. A Birukoff chapter (~5,000 words / ~7K tokens to read) typically yields 20-40 claims. Total with reasoning: ~20-50K tokens per source chapter.

#### B3. Per-page updates using RAG (~5-10K tokens per page)

For each affected page, Claude:

1. **Queries LightRAG** (not reads files): "What do we currently know about Confession's composition dates?" → gets relevant paragraphs, not full pages.
2. **Reads only the specific page** being updated (~2K tokens)
3. **Writes the edit** (~1K tokens)
4. **Checks the contradiction candidate list** from the nightly scripts — any flagged conflicts involving this page? (~500 tokens)

**Token cost per page:** ~5-10K tokens (down from ~9K in the brute-force approach, but more importantly, no longer limited by needing to read related pages sequentially).

#### B4. Commit update manifest and changes

Claude writes the update manifest to `_generated/update-manifests/YYYY-MM-DD-source-slug.json` and commits the changed wiki pages. The manifest is machine-readable — scripts can use it to verify completeness.

### Token cost for a typical ingest session

| Step | Tokens | Notes |
|------|-------:|-------|
| B1. Read daily briefing | 2,000 | Once per session |
| B2. Read source + extract claims | 30,000 | One source chapter |
| B3. Update 35 affected pages | 245,000 | 35 pages × ~7K avg |
| B4. Write manifest + commit | 3,000 | |
| **Total per ingest session** | **~280,000** | **Fits in one context window** |

Compare to the brute-force approach: **~560,000 tokens** (doesn't fit in context) with no scripted assistance.

---

### Phase C: Scripted post-processing (cron or triggered, zero tokens)

After Claude's session, scripts clean up and verify.

#### C1. Verify update completeness
```bash
# Reads the update manifest, checks that every "affects_pages" entry
# was actually modified in the git diff.
python3 scripts/verify-manifest.py --manifest _generated/update-manifests/latest.json
```
**What it catches:** Claude claimed a page needed updating but didn't actually edit it (forgot, ran out of context, etc.). Flags these for the next session.

**Cost:** 0 tokens.

#### C2. Regenerate indexes
```bash
# Re-runs A1-A4 to update graph, frontmatter index, and lint report
# after Claude's changes.
```
**Cost:** 0 tokens. ~60 seconds.

#### C3. LightRAG re-sync
```bash
# Re-indexes the pages Claude just changed.
python3 scripts/lightrag-sync.py --changes _generated/changes-since-last-sync.json
```
**Cost:** 0 tokens (local Ollama). ~35 pages × 10 sec = ~6 minutes.

---

## Token budget at different scales

### Assumptions
- Claude API: Sonnet for routine updates, Opus for complex reasoning/ambiguity
- Sonnet: ~$3/M input, ~$15/M output tokens (April 2026 pricing)
- Opus: ~$15/M input, ~$75/M output tokens
- Average ingest session: 280K tokens (80% input, 20% output)
- Ratio: 90% Sonnet, 10% Opus (for contradiction resolution)

### Monthly cost estimates

| Activity | Sessions/month | Tokens/session | Monthly tokens | Monthly cost |
|----------|:--------------:|:--------------:|:--------------:|:------------:|
| **Phase 2 (~1,000 files)** | | | | |
| Source ingestion | 8 | 150K | 1.2M | ~$5 |
| Lint/maintenance | 2 | 50K | 100K | ~$0.50 |
| **Phase 2 total** | | | **1.3M** | **~$6** |
| | | | | |
| **Phase 3 (~8,000 files)** | | | | |
| Source ingestion | 12 | 250K | 3.0M | ~$13 |
| Lint/maintenance | 4 | 100K | 400K | ~$2 |
| Query sessions | 4 | 50K | 200K | ~$1 |
| **Phase 3 total** | | | **3.6M** | **~$16** |
| | | | | |
| **Phase 5 (~26,500 files)** | | | | |
| Source ingestion | 16 | 280K | 4.5M | ~$20 |
| Lint/maintenance | 8 | 150K | 1.2M | ~$5 |
| Query sessions | 8 | 80K | 640K | ~$3 |
| **Phase 5 total** | | | **6.3M** | **~$28** |
| | | | | |
| **Maximum (~94,000 files)** | | | | |
| Source ingestion | 20 | 300K | 6.0M | ~$26 |
| Lint/maintenance | 12 | 200K | 2.4M | ~$10 |
| Query sessions | 12 | 100K | 1.2M | ~$5 |
| **Maximum total** | | | **9.6M** | **~$41** |

### What the cron jobs save

Without the scripted pipeline, Claude would need to do all the mechanical work itself — graph extraction, frontmatter scanning, dead-link checking, change detection. That would roughly **triple** the token usage at every scale:

| Scale | With scripts | Without scripts | Savings |
|-------|:-----------:|:---------------:|:-------:|
| Phase 2 | ~$6/mo | ~$15/mo | 60% |
| Phase 3 | ~$16/mo | ~$45/mo | 64% |
| Phase 5 | ~$28/mo | ~$80/mo | 65% |
| Maximum | ~$41/mo | ~$120/mo | 66% |

The scripts pay for themselves in the first month, and the gap widens as the vault grows.

---

## What Claude does vs. what scripts do

### Claude's irreplaceable jobs (require reasoning)
1. **Reading source texts** and understanding what they claim
2. **Evaluating reliability** of new claims against existing claims
3. **Resolving contradictions** when two sources disagree
4. **Writing prose** — composing wiki article text
5. **Deciding significance** — is this fact worth adding to the wiki?
6. **Wikilink placement** in source texts — choosing which mentions to link

### Scripts handle everything else (no reasoning needed)
1. **Graph extraction** — parsing `[[wikilinks]]` from all files
2. **Frontmatter indexing** — extracting YAML metadata into searchable format
3. **Change detection** — what files changed since last sync
4. **Dead link detection** — wikilinks pointing to non-existent files
5. **Orphan detection** — pages with no inbound links
6. **Mechanical contradiction flagging** — same field, different value on two pages
7. **LightRAG sync** — re-indexing changed files (Ollama, local)
8. **Update verification** — checking that Claude's manifest matches actual changes
9. **Statistics and reporting** — page counts, link density, coverage gaps

### LightRAG handles the middle ground (local Ollama, no API)
1. **Semantic search** — "what do we know about X?" across the full vault
2. **Entity extraction** — identifying people, places, works in new text
3. **Relationship mapping** — connecting entities across documents
4. **Similarity detection** — finding pages that discuss related topics

---

## Implementation priority

### Build first (Phase 2, now)
1. `extract-graph.py` — wikilink adjacency list
2. `extract-frontmatter.py` — frontmatter index
3. `generate-briefing.py` — daily briefing for Claude

These three scripts immediately improve Claude's efficiency, even before LightRAG exists. Claude reads a 2K-token briefing instead of scanning the vault.

### Build for Phase 3
4. `detect-changes.py` — change detection
5. `lint-graph.py` — orphan/dead-link detection
6. `detect-contradictions.py` — mechanical contradiction flagging
7. LightRAG setup + `lightrag-sync.py`
8. `verify-manifest.py` — post-update verification

### Build for Phase 5
9. Update manifest format and tooling
10. Agent swarm coordinator (if needed — may not be, given RAG)

---

## Open question: could a local model replace Claude for routine updates?

Some wiki updates are formulaic:
- Adding a birth/death date to a person page (frontmatter update)
- Adding a wikilink to a page that mentions a newly-created entity
- Fixing a dead link by correcting a page name

These don't require Claude's full reasoning capabilities. A local 14B model (Qwen2.5-14B via Ollama) could potentially handle them, reducing API costs further. The workflow would be:

```
Nightly cron:
  1. Scripts identify routine updates (date corrections, dead links, missing wikilinks)
  2. Local model applies them automatically
  3. Non-routine updates (new prose, contradiction resolution) queued for Claude

Morning session:
  Claude reviews what the local model did overnight
  Claude handles the complex updates
```

This is speculative — the quality threshold for "good enough for a scholarly resource" is high. But worth testing once the scripted pipeline is in place.
