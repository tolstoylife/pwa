# Documentation conventions — tolstoy.life

Last updated: 2026-04-26

How internal project documentation in `docs/` and `_generated/` is maintained over time. Complements `editorial.md`, which covers content stance and voice for the public wiki and works.

The question this file answers: when reality changes, what do you do to the doc that described the old reality?

---

## Two kinds of doc

**Evergreen docs.** Design specifications, principles, operational references. They describe the *current* state and are expected to evolve. Examples: `editorial.md`, `internal-operations.md`, the PWA design specs (`local-first-architecture.md`, `wiki-integration.md`, `stage-1-implementation.md`, `tl-pipeline-integration.md`, `yjs-schema-and-sync.md`).

**Dated reports.** Snapshot documents — research reports, session handoffs, audits, plans. The date in the filename or at the top is meaningful: it records what was known on that day. Examples: `architecture-review.html`, `lightrag-performance-report-2026-04-18.md`, `epub-a11y-w3c-review-2026-04-22.md`, `scalability-deep-dive-2026-04-15.md`.

The two get treated differently when the world moves on.

---

## Evergreen docs — changelog frontmatter

Edit the body in place. Log changes via a `changelog:` block in the YAML frontmatter:

```yaml
changelog:
  - 2026-04-24 — cascade-bug fix from 2026-04-23 architecture review: removed `wikiPreviewsUrl` from per-work manifests; tightened §3.2 hash-input definition.
  - 2026-04-24 — added §6.4 documenting the deterministic-build CI check.
```

One entry per change, dated, with enough detail to decide whether to read the diff. Body always reflects current truth. Used in `tl-pipeline-integration.md`, `yjs-schema-and-sync.md`.

---

## Dated reports — Status block

**Never rewrite the body.** It's the record of what was known on its date — that's its value.

When subsequent work invalidates a finding, supersedes a recommendation, or fixes a bug, add a Status block at the top of the doc, immediately after the title and subtitle:

```markdown
> **Status update — YYYY-MM-DD.** Part X (subject) — fixed. See [target doc §Y](../target.md).
```

Or, in HTML, an `<aside class="status-update">` with the same content. One bullet per delta. Link forward to where the current state lives. Don't summarise the body; just bridge to current truth.

New deltas append to the same Status block over time. The body stays untouched.

Examples in use: `_generated/sessions/tl-proofread-plan.md` (whole-doc supersession), `architecture-review.html` (per-finding follow-ups).

---

## When the report is fully superseded

If a dated report's findings are *all* obsolete, the Status block becomes a one-line `**SUPERSEDED.**` with a pointer to whatever replaced it. The body stays intact for the record; the reader is told upfront not to act on it.

An evergreen doc never gracefully degrades to dated. If it is no longer the current spec, archive it (move to `_generated/`, add a Status block) rather than continue editing it as evergreen.

---

## Scope

This file covers documentation maintenance over time. It does not cover voice or content stance — those are in `editorial.md`. It does not cover commit messages or git workflow — those are in `AGENTS.md`. It is specifically about how documents in `docs/` and `_generated/` are maintained when the underlying reality changes.
