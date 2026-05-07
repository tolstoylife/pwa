# EPUB 3.3 & Accessibility 1.1 — W3C Spec Review
*Reviewed: 2026-04-22 | Scope: tolstoy.life e-reader, `tl` toolset, distributed EPUBs*

---

## Spec status (as of April 2026)

- **EPUB 3.3** — W3C Recommendation, May 2025; updated January 2026. EPUB 3.4 drafts already in progress.
- **EPUB Accessibility 1.1** — W3C Recommendation since October 2024. Now integrated *into* EPUB 3.3 core (no longer a separate annex).
- **EPUB Reading Systems 3.3** — W3C Recommendation since October 2024.
- **EPUB Type to ARIA Role Authoring Guide 1.1** — companion guidance for the epub:type → ARIA migration.

---

## 1. Mandatory accessibility metadata (EPUB A11y 1.1)

Every EPUB publication **must** include the following `schema.org` properties in `content.opf`, regardless of whether full conformance is claimed:

| Property | Required | Notes |
|---|---|---|
| `accessMode` | Yes | e.g. `textual`, `visual` |
| `accessibilityFeature` | Yes | e.g. `tableOfContents`, `readingOrder`, `alternativeText` |
| `accessibilityHazard` | Yes | e.g. `noFlashingHazard`, `noMotionSimulationHazard` |
| `accessibilitySummary` | Strongly recommended | Human-readable prose summary |

**Important nuance:** Features that are structurally guaranteed by EPUB (e.g. `tableOfContents`, `readingOrder`) must still be explicitly declared in `accessibilityFeature`. Omitting them reduces discoverability when users search by feature.

**Current gap in `tl`:** The `tl create-draft` templates likely do not auto-populate all required metadata. Every ebook produced under the tolstoy.life imprint should declare these fields. This is the highest-priority compliance item.

---

## 2. Semantic inflection: epub:type vs. ARIA roles

This is the area where the spec has shifted most significantly since EPUB 3.0.

### What epub:type does (and doesn't do)
- **Does:** Triggers reading-system behaviours — footnote popups, media overlay associations, navigation identification.
- **Does not:** Expose information to assistive technologies. Screen readers ignore it entirely.

### What ARIA role does
- Surfaces structural information directly to screen readers and AT.
- More restricted in where it can be applied — only use where semantically appropriate.

### Rule: always use both together on interactive reference elements

```html
<!-- Note reference — correct markup -->
<a href="#note-1" epub:type="noteref" role="doc-noteref">[1]</a>

<!-- Note content — correct markup -->
<aside id="note-1" epub:type="footnote" role="doc-footnote">
  <p>Note text here.</p>
</aside>
```

### Key pairs for tolstoy.life

| Purpose | epub:type | ARIA role |
|---|---|---|
| Footnote/note reference | `noteref` | `doc-noteref` |
| Glossary term reference | `glossref` | `doc-glossref` |
| Footnote content | `footnote` | `doc-footnote` |
| Chapter | `chapter` | `doc-chapter` |
| Endnotes section | `endnotes` | `doc-endnotes` |
| Glossary section | `glossary` | `doc-glossary` |
| Page break (print replica) | `pagebreak` | `doc-pagebreak` |

---

## 3. Wikilinks and W3C standards — analysis

The W3C has no concept of "wikilinks." From the spec's perspective, a rendered wikilink is either:
- A standard hyperlink (`<a href="...">`) to content inside the EPUB container, or
- An interactive element with ARIA attributes presenting supplementary content.

### Closest W3C analogue: `doc-glossref`

The `role="doc-glossref"` pattern is semantically identical to what wikilinks do — an inline term reference that links to a defined article. Some reading systems (notably Apple Books) render glossary references with special UI (tap-to-preview). This is the closest standards-native equivalent.

### The footnote popup pattern

EPUB 3.3's footnote popup mechanism — a `noteref` anchor linking to an `aside` containing note content — maps directly onto the wikilink modal preview pattern used by the tolstoy.life PWA. The wiki stub (summary prose from the wiki article) can be placed in an `aside` at chapter end, and the JS intercepts the tap to show a modal instead of navigating.

```html
<!-- In chapter body -->
<a href="#wiki-sophia-tolstaya" epub:type="noteref" role="doc-noteref">
  Sophia Tolstaya
</a>

<!-- At chapter end (or in separate spine doc) -->
<aside id="wiki-sophia-tolstaya" epub:type="footnote" role="doc-footnote">
  <p>Sophia Andreevna Tolstaya (1844–1919), Tolstoy's wife and primary copyist...</p>
</aside>
```

### `aria-details` for richer cross-references

Where a full wiki article is included in the EPUB spine, `aria-details` on the inline term can point to that article section — more semantically appropriate for extended reference content than footnote markup.

---

## 4. Core problems and tensions

### Problem 1 — Spine vs. graph
An EPUB spine is a linear sequence. The wiki is a graph. Wikilinks in chapter text point to articles that are not in the spine. Options:

- **(a) In-EPUB glossary** — include a condensed wiki as a spine document. Linked with `doc-glossref`. Keeps everything self-contained and epubcheck-clean.
- **(b) Strip wikilinks from distributed EPUBs** — replace with plain text or endnotes. Wikilinks remain a PWA-only feature.
- **(c) External links** — technically valid EPUB, but breaks offline reading and epubcheck flags unresolved fragment identifiers.

**Recommended path:** Option (a) for scholarly EPUBs where the wiki enrichment is core to the reading experience; option (b) for plain reading editions.

### Problem 2 — Popup interoperability
The spec does not mandate how reading systems display footnote/glossary popups. Apple Books shows speech-bubble popups; Kobo navigates to the note and back; others do nothing. Any wikilink-as-popup behaviour cannot be guaranteed in distributed EPUBs. The PWA can implement a consistent experience; distributed EPUBs cannot.

### Problem 3 — epubcheck validation
Any wikilink `href` pointing to a resource not in the EPUB spine will fail epubcheck. The `tl lint` pipeline will surface these as errors. All wiki cross-references in chapter files must either resolve to something inside the container or be stripped before distribution.

### Problem 4 — epub:type deprecation trajectory
The spec increasingly steers authors toward ARIA roles. `epub:type` alone is not sufficient for accessibility. Long-term: prefer `role`, use `epub:type` only as a reading-system behaviour trigger alongside `role`.

---

## 5. Opportunities

### O1 — Compliance: accessibility metadata in `tl create-draft`
Auto-populate mandatory schema.org fields in `content.opf` templates. This is a template change only — no logic required. Brings every `tl`-produced ebook into EPUB Accessibility 1.1 compliance by default.

### O2 — Wikilinks as `doc-glossref` in the PWA e-reader
In the PWA's rendered XHTML, mark up wikilinks as:
```html
<a role="doc-glossref" epub:type="glossref" href="#wiki-stub-id">term</a>
```
with matching `<aside role="doc-glossary">` stubs at chapter end. Standards-compliant, degrades gracefully for screen readers, and the PWA JS can intercept clicks for modal previews. Also works in `tl recompose-epub` single-file output.

### O3 — Landmarks nav
Include condensed wiki / key-figures appendix in the EPUB `<nav epub:type="landmarks">` with `epub:type="glossary"`. Enables one-tap navigation to the reference section in supporting reading systems.

### O4 — Page list nav (print replica ebooks)
EPUB 3.3 requires `<nav epub:type="page-list">` for ebooks that reproduce a print edition. Applies to the Birukoff biography and similar scan-based projects. Required for EPUB A11y 1.1 `printPageNumbers` accessibilityFeature declaration. Also useful for scholarly citation (page references).

### O5 — `aria-details` for in-EPUB wiki articles
Where a full wiki article appears in the EPUB spine (e.g. a key-figures appendix), use `aria-details` on inline terms to associate them with the article:
```html
<span aria-details="wiki-sophia-tolstaya">Sophia Tolstaya</span>
```
More semantically correct than `aria-describedby` for extended reference content.

### O6 — Future: Media Overlays
EPUB 3.3 supports synchronised text-audio (SMIL). Not relevant now, but correct semantic markup now (`id` attributes on structural elements, proper `epub:type` on chapters/sections) makes adding audio narration tractable later without structural rewrites.

---

## 6. Immediate action items

See `_generated/project/TODO.md` for the full tracked backlog. Summary of items flowing from this review:

1. **Audit `tl create-draft` templates** against EPUB A11y 1.1 mandatory metadata checklist
2. **Add schema.org accessibility metadata** defaults to `content.opf` template
3. **Add `<nav epub:type="page-list">`** support to `tl build-toc` for print-replica ebooks
4. **Define wikilink strategy for distributed EPUBs** — in-EPUB glossary vs. strip-and-endnote
5. **Update chapter XHTML templates** to use `epub:type` + `role` pairs on all interactive reference elements (not `epub:type` alone)
6. **Document the `doc-glossref` pattern** in the Manual of Style as the canonical wikilink representation in EPUB output

---

## References

- [EPUB 3.3 — W3C Recommendation](https://www.w3.org/TR/epub-33/)
- [EPUB Accessibility 1.1 — W3C Recommendation](https://www.w3.org/TR/epub-a11y-11/)
- [EPUB Accessibility Techniques 1.1](https://www.w3.org/TR/epub-a11y-tech-11/)
- [EPUB Type to ARIA Role Authoring Guide 1.1](https://www.w3.org/TR/epub-aria-authoring-11/)
- [EPUB Structural Semantics Vocabulary 1.1](https://www.w3.org/TR/epub-ssv-11/)
- [Digital Publishing WAI-ARIA Module 1.0](https://www.w3.org/TR/dpub-aria-1.0/)
- [Updated W3C Recommendation: EPUB 3.3 (Jan 2026)](https://www.w3.org/news/2025/updated-w3c-recommendation-epub-3-3/)
- [EDRLab: W3C Pushes EPUB Forward (April 2025)](https://www.edrlab.org/2025/04/08/w3c-pushes-epub-forward/)
- [DAISY: What Does EPUB 3.3 Mean For Accessibility?](https://daisy.org/news-events/articles/what-does-epub-3-3-mean-for-accessibility/)
- [DAISY Knowledge Base: epub:type attribute](https://kb.daisy.org/publishing/docs/html/epub-type.html)
