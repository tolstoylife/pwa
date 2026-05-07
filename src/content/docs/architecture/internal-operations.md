# Internal Operations — Tolstoy Research Platform

Cost estimates, hardware specifications, and capacity planning details. Supplements `AGENTS.md` with operational context for anyone implementing or running the platform.

---

## Token economy

### Current cost model (Phase 2)

Direct Claude access — vault is small enough to fit relevant pages in context. No scripted pipeline or RAG layer yet.

### Projected cost at full scale (Phase 5, ~26,500 files)

- **Token budget:** ~6.3M tokens/month
- **Estimated cost:** ~$28/month
- **Without scripted pipeline:** costs would be ~3× higher (~$84/month)
- **Maximum scenario (~94,000 files):** ~9.6M tokens/month, ~$41/month

The scripted pipeline (Layer 1) saves ~65% of token costs by pre-computing graph extraction, frontmatter indexing, and change detection — work that would otherwise require Claude to read and parse files.

---

## Hardware

- **Primary machine:** Mac Mini, 24 GB unified memory
- **LLM inference:** Qwen2.5-14B via Ollama (9–11 GB VRAM, ~20–25 tok/s, 128k context)
- **Embedding model:** all-MiniLM-L6-v2 via Sentence-Transformers (22 MB, 384 dimensions)

---

## LightRAG capacity planning

### Storage backends (current configuration)

| Layer | Backend | Notes |
|---|---|---|
| KV (key-value) | JsonKVStorage (JSON files) | Standard local backend |
| Graph | NetworkXStorage (in-memory + file) | Standard local backend |
| Vector | NanoVectorDB (local file) | Standard local backend |
| Document status | JsonDocStatusStorage (JSON file) | Standard local backend |

No OpenSearch, no external databases. All data in a local `WORKING_DIR/`.

### Upgrade path (if needed)

PostgreSQL with pgvector + AGE extension — one database covering all four layers. Only consider at 100k+ files or if query latency becomes a problem.

### Indexing times

- **Full initial indexing (~26,500 files):** ~110 hours with Qwen2.5-14B (5 overnight runs)
- **Full initial indexing with 7B model:** ~13 hours
- **Daily incremental sync (50 files):** ~8 minutes
- **Embedding 5,000 docs:** 2.5–5 minutes on CPU

### Sync model

Nightly cron job (`lightrag_sync.py`) identifies changed files since last run and performs incremental re-indexing. Not real-time — runs after each daily session or on a schedule.

```bash
# cron: 02:00 every night
python3 lightrag_sync.py --working-dir ./rag-index --source-dir ./website/src/
```

### TEI ingestion scenario (Phase 3)

```
3,113 person pages + 770 place pages = ~3,883 new markdown files

If creating 50 files per session:
  78 sessions × ~8 min RAG sync = ~10 hours total RAG time (spread over weeks)

If running full batch indexing after all files are created:
  ~13 hours one-time cost (overnight)
```

---

## Alternatives considered and rejected

| System | Reason rejected |
|---|---|
| GraphRAG (Microsoft) | $350–500 initial indexing, requires full re-index on each change |
| Cognee | Enterprise pricing (€1,970/month on-premises) |
| Gemini Vertex AI RAG | $50–200/month, adds nothing over local + OCR pipeline |
| OpenSearch backend | Only needed at 10M+ documents, $360–720/month for AWS cluster |

**Fallback:** nano-graphrag (~1,100 lines, simpler) if LightRAG proves too complex to set up.

---

## Scalability report reference

Full analysis: `./scalability-deep-dive-2026-04-15.md`
Wiki rewrite workflow: `./wiki-rewrite-workflow-2026-04-15.md`
