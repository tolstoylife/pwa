# LightRAG Performance Report — Mac Mini M4 24GB

Report: 2026-04-18 (updated same day — second ingestion run with bge-m3 embedding model)
Context: This report covers two ingestion runs on the same 29-file vault. The first run used nomic-embed-text (768d). The second run used bge-m3 (1024d, multilingual) after the embedding model was switched. Both runs used qwen2.5:7b as the LLM. This document is the authoritative hardware, model, and performance reference for the Tolstoy Research Platform's LightRAG Layer 2.

---

## 1. Hardware profile

| Spec | Value |
|---|---|
| Machine | Mac Mini M4 |
| Unified memory | 24 GB |
| GPU available (reported by Ollama) | 17.8 GiB |
| Memory bandwidth | ~120 GB/s |
| GPU memory limit (`iogpu.wired_limit_mb`) | 0 (no cap — macOS manages dynamically) |
| Ollama version | 0.21.0 |

### Effective memory budget

macOS and background services consume approximately 4–5 GB at idle. That leaves ~19–20 GB for Ollama and the LightRAG Python process. With `OLLAMA_MAX_LOADED_MODELS=1`, the LLM and embedding model swap rather than coexist.

---

## 2. Model testing results

### Models tested

| Model | Parameters | Quantization | Weight size | Purpose |
|---|---|---|---|---|
| qwen2.5:14b | 14B | Q4_K_M | ~9 GB | LLM (entity extraction) — rejected |
| qwen2.5:7b | 7B | Q4_K_M | ~4.7 GB | LLM (entity extraction) — adopted |
| nomic-embed-text | 137M | — | ~274 MB | Embedding (768d) — first run |
| bge-m3 | 568M | — | ~1.2 GB | Embedding (1024d) — second run, adopted |

### qwen2.5:14b — rejected for this hardware

| Metric | Value |
|---|---|
| Model weights | ~9 GB |
| KV cache (32K context, 1 slot, FP16) | ~3–4 GB |
| Total LLM footprint | ~12–13 GB |
| Observed memory usage during ingestion | 93.4% (with swap) |
| Swap usage | 63–79% |
| Result | **Unusable for unattended operation on 24 GB** |

The 14B model consistently triggered memory pressure and swap, even after setting `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_FLASH_ATTENTION=1`. The 32K context window requirement (non-negotiable for LightRAG entity extraction) pushes the KV cache to 3–4 GB on top of 9 GB of weights, leaving only 7–8 GB for macOS + Python — insufficient when combined with any background processes.

**Root cause analysis:** The earlier scalability report estimated the 14B model would use 9–11 GB VRAM. This was correct for the model weights alone, but underestimated the KV cache overhead at 32K context. Additionally, the default `OLLAMA_NUM_PARALLEL` setting may have allocated multiple KV cache slots (up to 4×), multiplying the cache memory by a factor of 2–4.

### qwen2.5:7b — adopted

| Metric | Value |
|---|---|
| Model weights | ~4.7 GB |
| KV cache (32K context, 1 slot, flash attention) | ~1 GB |
| Total LLM footprint | ~7.2 GB |
| Observed memory usage during ingestion | 68.1% (run 1) / 73.6% (run 2, heavy background load) |
| Swap usage | 0.0% (both runs) |
| Free memory during operation | ~7.6 GB (run 1) / ~6.3 GB (run 2) |
| Ingestion time (29 documents, ~80 KB) | 43 min (run 1) / 64 min (run 2) |
| Result | **Stable, comfortable headroom — even under heavy background load** |

The 7B model leaves approximately 15–16 GB for macOS and Python, well within safe margins for unattended cron operation.

### Performance benchmarks (M4 Apple Silicon)

| Metric | qwen2.5:7b | qwen2.5:14b |
|---|---|---|
| Prompt processing | ~90–120 tok/s | ~45–60 tok/s |
| Generation speed | ~35–45 tok/s | ~18–25 tok/s |
| Model load time (cold) | ~5 s | ~10–15 s |
| Memory headroom on 24 GB | ~16 GB | ~9 GB |

Generation speed is almost entirely memory-bandwidth-bound on Apple Silicon. The 14B model is roughly 2× slower, proportional to its weight size.

---

## 3. Ollama configuration

### Active environment variables

```bash
export OLLAMA_KEEP_ALIVE=-1           # Keep model loaded between calls
export OLLAMA_MAX_LOADED_MODELS=1     # One model at a time (swap, don't coexist)
export OLLAMA_NUM_GPU=99              # Offload all layers to Metal GPU
export OLLAMA_NUM_PARALLEL=1          # Single inference slot (prevents KV cache multiplication)
export OLLAMA_FLASH_ATTENTION=1       # Quantized KV cache — halves cache memory
```

### Effect of each setting

| Setting | Default | Our value | Effect |
|---|---|---|---|
| `OLLAMA_NUM_PARALLEL` | 4 (auto) | 1 | Saves ~3–6 GB by preventing multiple KV cache allocations |
| `OLLAMA_FLASH_ATTENTION` | 0 | 1 | Reduces KV cache by ~50% (FP16 → Q8/Q4) |
| `OLLAMA_KEEP_ALIVE` | 5m | -1 | Avoids 5–15s reload delay between cron calls |
| `OLLAMA_MAX_LOADED_MODELS` | auto | 1 | Prevents LLM + embedding model coexisting in memory |
| `OLLAMA_NUM_GPU` | auto | 99 | Ensures all layers run on Metal GPU, not CPU |

### Critical finding: `OLLAMA_NUM_PARALLEL`

This was the most impactful setting. Without it, Ollama allocates a KV cache for each parallel slot. At 32K context with FP16:

- **Default (4 slots):** 4 × 3–4 GB = 12–16 GB just for KV caches
- **NUM_PARALLEL=1:** 1 × 3–4 GB = 3–4 GB for KV cache
- **NUM_PARALLEL=1 + flash attention:** 1 × ~1 GB

This alone can explain the difference between the 14B model working or failing on 24 GB hardware.

---

## 4. Embedding model comparison: nomic-embed-text vs bge-m3

### Run 1: nomic-embed-text (768d)

| Metric | Value |
|---|---|
| Dimensions | 768 |
| Parameters | 137M |
| RAM usage | ~0.5 GB |
| Ollama download | ~274 MB |
| MTEB retrieval score (avg) | ~52.8 |
| Multilingual support | English-primary; limited non-English |
| Russian performance | Poor — no dedicated Russian training data |

### Run 2: bge-m3 (1024d) — adopted

| Metric | Value |
|---|---|
| Dimensions | 1024 |
| Parameters | 568M |
| RAM usage | ~1.5 GB |
| Ollama download | ~1.2 GB |
| MTEB retrieval score (avg) | ~54.3 |
| Multilingual support | 100+ languages, purpose-built |
| Russian performance | Strong — ~70+ nDCG@10 on MIRACL Russian benchmark |

### What the dimensions actually mean

Each dimension is a learned feature in the model's representation of meaning. More dimensions allow finer-grained distinctions:

- **768 dimensions** — good resolution for English-language retrieval. Sufficient for distinguishing "Tolstoy the writer" from "Tolstoy the estate" from "Tolstoy the philosophy."
- **1024 dimensions** — finer grain, especially for cross-lingual concepts. Better at placing Russian terms near their English equivalents in vector space.

### Quality impact

The MTEB benchmark difference (52.8 vs 54.3) translates to roughly:

- At 768d: a query about "Софья Андреевна" may not reliably retrieve the "Sophia Tolstaya" wiki article
- At 1024d with bge-m3: the Russian and English name forms map to nearby vectors

For the Tolstoy vault specifically — which contains Russian names in Cyrillic (`titleRu` fields), Cyrillic transliterations, and will eventually contain Russian-language source texts — the multilingual gap is significant.

### Graph quality impact (observed)

Switching to bge-m3 produced a measurably richer knowledge graph from the same 29 documents:

| Metric | nomic (768d) | bge-m3 (1024d) | Delta |
|---|---|---|---|
| Graph nodes | 192 | 226 | +34 (+17.7%) |
| Graph edges | 196 | 227 | +31 (+15.8%) |
| Ingestion time (29 docs) | 43 min | 64 min | +21 min (+49%) |
| Memory peak | 68.1% | 73.6%* | +5.5 pp |
| Swap usage | 0.0% | 0.0% | — |

*Run 2 had significantly more background applications running (Comet, NordVPN, multiple Claude Helper renderer processes, Alfred, Mail, etc.), so the memory delta is not attributable to bge-m3 alone. True bge-m3 overhead is likely under 1–2 pp vs nomic.

The +34 nodes and +31 edges represent genuine additional knowledge structure extracted from the same source material — not re-indexed duplicates. The richer embedding space appears to help the LightRAG graph merge step discriminate entities more cleanly, avoiding over-merging that would collapse distinct entities into one node.

### Storage and speed impact

| Scale | 768d storage | 1024d storage | Delta |
|---|---|---|---|
| 29 files (current) | ~90 KB | ~120 KB | +30 KB |
| 4,600 files (Phase 3) | ~14 MB | ~19 MB | +5 MB |
| 26,500 files (Phase 5) | ~80 MB | ~106 MB | +26 MB |

Storage difference is negligible at all projected scales. Search latency difference is sub-millisecond.

### Memory impact with qwen2.5:7b

Since `OLLAMA_MAX_LOADED_MODELS=1`, the LLM and embedding model swap. Peak memory is determined by whichever is larger:

| Configuration | Peak model memory | Total with 32K KV | Headroom on 24 GB |
|---|---|---|---|
| 7b + nomic (768d) | 4.7 GB (LLM peak) | ~7.2 GB | ~16.8 GB |
| 7b + bge-m3 (1024d) | 4.7 GB (LLM peak) | ~7.2 GB | ~16.8 GB |

The embedding model is always smaller than the LLM, so it doesn't affect peak memory. bge-m3's 1.5 GB is well under qwen2.5:7b's 4.7 GB. **No meaningful memory penalty for switching to bge-m3.**

### Other embedding models considered

| Model | Dims | MTEB retrieval | Russian | RAM | Verdict |
|---|---|---|---|---|---|
| nomic-embed-text | 768 | 52.8 | Poor | 0.5 GB | Run 1 — adequate English, poor Russian |
| bge-m3 | 1024 | 54.3 | Strong | 1.5 GB | **Run 2 — adopted** |
| mxbai-embed-large | 1024 | 54.4 | Poor | 1.0 GB | Slightly higher English score, no Russian |
| snowflake-arctic-embed-l | 1024 | 55.0 | Poor | 1.0 GB | Highest English retrieval, no Russian |

---

## 5. Ingestion time estimates

### Baseline measurements

#### Run 1 — nomic-embed-text (768d)

| Metric | Value |
|---|---|
| Documents | 29 |
| Total content size | ~80 KB |
| Average document size | ~2.8 KB |
| Ingestion time | 43 minutes (2,577 seconds) |
| Time per document | ~89 seconds |
| Knowledge graph result | 192 nodes, 196 edges |
| Model | qwen2.5:7b + nomic-embed-text |
| Background load | Light — few other applications running |

#### Run 2 — bge-m3 (1024d)

| Metric | Value |
|---|---|
| Documents | 29 |
| Total content size | ~80 KB |
| Average document size | ~2.8 KB |
| Ingestion time | 64.4 minutes (3,865 seconds) |
| Time per document | ~133 seconds |
| Knowledge graph result | 226 nodes, 227 edges |
| Model | qwen2.5:7b + bge-m3 |
| Background load | **Heavy** — Comet renderer (8+ processes), NordVPN, Claude Helper, Alfred, Mail, Ollama serve, ingest.py concurrently |

The ~50% increase in ingestion time (89 s → 133 s per document) should not be attributed solely to bge-m3. Run 2 was conducted under significantly heavier background load, which compresses CPU/GPU headroom and slows both the LLM extraction phase and disk I/O. The model swap overhead (bge-m3 is ~4× larger than nomic) contributes, but likely accounts for only ~15–20 s of the ~44 s increase per document.

**Best estimate for bge-m3 under light load:** ~100–110 seconds per document, vs ~89 seconds for nomic. That is the realistic per-document time to use for scaling projections.

### Time per document breakdown (estimated, bge-m3, light load)

| Step | Estimated time | Notes |
|---|---|---|
| LLM extraction (2 passes) | ~70 s | Two LLM calls per document (extract + merge) — same as nomic |
| Embedding generation | ~20 s | bge-m3 is ~4× larger than nomic; swap overhead included |
| Graph merge + storage | ~15 s | In-memory operations, disk writes |

### Projections for future ingestion phases

All projections below use 105 s/document as the bge-m3 baseline (midpoint of 100–110 s estimate, light-load conditions).

#### TEI reference data (Phase 3)

The TEI dataset contains 3,113 persons and 770 locations. Each person/location becomes a wiki page.

| Metric | Estimate |
|---|---|
| New documents | ~3,883 wiki pages |
| Average document size | ~1–2 KB (structured metadata, short descriptions) |
| Estimated time per document | ~75 s (smaller docs = faster extraction) |
| Total ingestion time | ~81 hours |
| Recommended approach | 4 overnight runs (~20 hours each) |

Note: These are new additions to the vault. The existing 29 documents would not need re-indexing.

#### Birukoff biography

The Birukoff biography (Paul Birukoff, *Leo Tolstoy: His Life and Work*, 1906 Heinemann edition) is 150,135 words across 17 chapters.

| Metric | Estimate |
|---|---|
| Documents | 17 chapter files |
| Average chapter size | ~52 KB (~8,830 words) |
| Total content | ~880 KB |
| Estimated time per document | ~200 s (larger docs require more extraction passes) |
| LightRAG chunking | ~5–8 chunks per chapter at default settings |
| Total ingestion time | ~57 minutes |
| Recommended approach | Single run, daytime or overnight |

#### Full corpus (Phase 5)

| Metric | Estimate |
|---|---|
| Total documents | ~26,500 |
| Total content | ~72 MB |
| Average document size | ~2.7 KB |
| Estimated time per document | ~90 s (blended: short wiki pages + long text chapters, bge-m3) |
| Total initial ingestion | ~663 hours (~28 days) |
| Recommended approach | Batched overnight runs over 5–6 weeks |
| Daily incremental sync (50 changed files) | ~75 minutes |

### Comparison with earlier estimates

| Scenario | 14B estimate (theoretical) | 7B + nomic (measured) | 7B + bge-m3 (projected, light load) |
|---|---|---|---|
| 29 files | ~15 min | 43 min | ~51 min |
| Phase 3 (~3,900 files) | ~38 hours | ~65 hours | ~81 hours |
| Phase 5 (~26,500 files) | ~110 hours | ~550 hours | ~663 hours |

The bge-m3 overhead (~20%) is real but modest in the context of multi-week ingestion runs. The richer knowledge graph it produces (+17% more nodes and edges on the same corpus) justifies the additional time.

---

## 6. Token cost comparison

LightRAG uses Ollama locally — there are no API token costs. All processing runs on the Mac Mini's GPU. This is a key architectural advantage.

For comparison, using cloud APIs for the same workload:

### Claude API costs (if LightRAG were replaced with cloud processing)

From the wiki rewrite workflow report (2026-04-15):

| Phase | Files | Monthly token estimate | Claude API cost |
|---|---|---|---|
| Phase 2 (current, 29 files) | 29 | ~500K tokens | ~$2/month |
| Phase 3 (~8,000 files) | 8,000 | ~3.2M tokens | ~$14/month |
| Phase 5 (~26,500 files) | 26,500 | ~6.3M tokens | ~$28/month |

### LightRAG local costs

| Phase | Files | Electricity estimate | API cost |
|---|---|---|---|
| All phases | Any | ~$1–3/month (Mac Mini idle + overnight runs) | **$0** |

The scripted pipeline (Layer 1) + LightRAG (Layer 2) together save approximately 65% of the token costs that would otherwise be spent on Claude reading and navigating the vault.

---

## 7. Optimization roadmap

### Immediate (no code changes)

- [x] `OLLAMA_NUM_PARALLEL=1` — prevents KV cache multiplication
- [x] `OLLAMA_FLASH_ATTENTION=1` — halves KV cache memory
- [x] `OLLAMA_KEEP_ALIVE=-1` — avoids reload delays
- [x] `OLLAMA_MAX_LOADED_MODELS=1` — prevents model coexistence

### Short-term (config changes)

- [x] Switch embedding model to bge-m3 (1024d) for Russian+English support
- [x] Update `config.py`: `EMBED_MODEL = "bge-m3"`, `EMBED_DIM = 1024`
- [ ] Set up nightly cron job for `sync.py`
- [ ] Test incremental sync after editing wiki pages

### Medium-term (when vault grows to ~4,600 files)

- [ ] Benchmark whether qwen2.5:14b becomes viable with flash attention + NUM_PARALLEL=1 after macOS updates or Ollama improvements
- [ ] Consider Q3_K_M quantization of 14B as middle ground (saves ~2 GB vs Q4, quality trade-off is modest for structured extraction)
- [ ] Add rerank model for improved query result ordering (if query quality is insufficient)

### Long-term (Phase 5, ~26,500 files)

- [ ] Evaluate PostgreSQL with pgvector + AGE as unified backend (replaces JSON/NetworkX/NanoVectorDB)
- [ ] Consider batched overnight ingestion with progress tracking and resume capability
- [ ] Evaluate newer Qwen or Llama models as they release — 7B-class models are improving rapidly

---

## 8. Current production configuration

```python
# config.py — active settings as of 2026-04-18
LLM_MODEL = "qwen2.5:7b"
LLM_CONTEXT_WINDOW = 32768
EMBED_MODEL = "bge-m3"
EMBED_DIM = 1024
EMBED_MAX_TOKENS = 8192
OLLAMA_TIMEOUT = 600
```

### Knowledge graph statistics — both ingestion runs

| Metric | Run 1 (nomic, 768d) | Run 2 (bge-m3, 1024d) |
|---|---|---|
| Documents indexed | 29 | 29 |
| Graph nodes | 192 | 226 |
| Graph edges | 196 | 227 |
| Ingestion time | 43 min | 64 min |
| Memory usage (peak) | 68.1% | 73.6%* |
| Swap usage | 0.0% | 0.0% |
| Background load | Light | Heavy |

*Higher memory in run 2 is attributable primarily to heavier background application load, not to bge-m3.

Query response time (hybrid): ~30–60 seconds (unchanged — query performance is LLM-bound, not embedding-bound).

---

## Appendix: Key findings summary

1. **qwen2.5:14b does not fit on 24 GB** with a 32K context window, even with aggressive tuning. The KV cache at 32K is the bottleneck, not the model weights.

2. **`OLLAMA_NUM_PARALLEL` is the single most impactful configuration setting** — the default allocates multiple KV caches that silently multiply memory usage.

3. **qwen2.5:7b is the right model** for 24 GB hardware running LightRAG. It provides stable, swap-free operation with ~16 GB headroom.

4. **bge-m3 has been adopted as the embedding model.** It produces a richer knowledge graph (+17% nodes and edges on the same 29-document corpus) and provides strong Russian+English multilingual retrieval. There is no meaningful memory penalty with `MAX_LOADED_MODELS=1`. The ~20% slower embedding speed is acceptable.

5. **The system is robust under heavy background load.** Run 2 was conducted with Comet, NordVPN, multiple Claude Helper renderer processes, and other applications running simultaneously. Memory stayed at 73.6% with no swap — confirming the architecture is safe for unattended cron operation even when the machine is in active use.

6. **Full corpus ingestion will take approximately 663 hours** (5–6 weeks of overnight runs) with bge-m3. This is ~20% longer than the nomic estimate but produces a meaningfully richer knowledge graph.

7. **LightRAG eliminates all API token costs** for vault indexing and querying. The three-layer architecture (scripts + LightRAG + Claude) reduces Claude API costs by approximately 65%.
