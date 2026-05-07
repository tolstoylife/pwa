# Editorial handbook — tolstoy.life

Last updated: 2026-04-26

This file describes how content for tolstoy.life is written: voice, what is included, what is excluded, and how to handle outside scrutiny. The public account of *what* the project is lives in `MANIFEST.md`. Documentation maintenance — how files in `docs/` and `_generated/` change over time — is in `conventions.md`.

---

## Tone

tolstoy.life is:

- **Factual.** Facts, documents, texts. No polemic, no ideological packaging.
- **Straightforward.** Plain English, plain layout, plain claims. Where Tolstoy's own positions are reported, they are reported as his, with sources.
- **Restrained.** As little editorialising as possible. The texts do the work.

### The model: architecture-review style

The file `docs/architecture/architecture-review.html` is the tonal reference for all wiki and works content. Not in subject matter, but in register: it states what exists, what it does, and where the problems are — without marketing, without hedging, without performing expertise. Every sentence carries information. Nothing is there to sound good.

Applied to the wiki this means: a person article states who the person was, what their documented relationship to Tolstoy was, what the primary sources record. A works article states what the work is, when it was written, what the manuscripts show, what the publication history was. No throat-clearing, no scene-setting, no verdicts on literary significance.

The test for any sentence in the wiki or works pages: does it convey a verifiable fact, or a directly sourced claim? If not, it should not be there. Interpretive language — "remarkably", "one of his greatest", "deeply influenced" — is excluded unless it is a direct quotation from a named source.

---

## Editorial line

### What we include
- Primary sources: texts, letters, diaries, manuscripts, photographs, documents.
- Plain fact: dates, places, events, bibliographic data.
- Biographical material that can be verified against primary sources.

### What we exclude
- Academic interpretation and literary criticism (except as plain reference — "X argued Y").
- Ideological frameworks that insert themselves between the reader and Tolstoy.
- Material under restrictive licences that prevent free distribution — if we cannot make it freely available, it is incompatible with the project's purpose.

### The grey zone
Material may be offered with conditions attached. Each such offer is assessed on its own terms, but the default position is: if material cannot be made freely available to readers, we should be cautious about building it into the resource.

---

## Preparing for criticism

The project will likely be scrutinised — especially as it grows and becomes visible. That is expected and should not come as a surprise.

Likely objections:

- **Source credibility.** "Who are you to publish this without academic peer review?" Our answer is verifiability: every claim must be traceable to a named primary source. We do not need peer review if we have transparency.
- **Competence.** "You lack academic qualifications." Irrelevant if the material speaks for itself — but that requires us to be extremely rigorous with facts. Every factual error will be used to challenge the entire project.
- **Copyright.** "You are reproducing material without permission." This is the legally sensitive point. Everything we publish must be either public domain, licensed for free use, or original. No grey zones.
- **Interpretation.** "You have an agenda." The answer is the editorial line above: we do not interpret, we make accessible. The less editorialising in the texts, the harder the project is to attack.

The principle: **build so that it withstands scrutiny.** Not by hiding weaknesses, but by eliminating them. A systematic review of the project from a critical perspective should be conducted regularly — see TODO.md.

---

## How this shapes the work

- **AGENTS.md** defines *how* we build (schema, conventions, architecture). This handbook defines *with what voice and editorial discipline.*
- **Skills** should reflect these principles. For example: the ebook-creator skill produces free, DRM-free EPUBs — that is not a technical detail, it is a matter of principle.
- **The scalability report** inventories material that is largely controlled by third parties. The inventory itself is unproblematic; acquiring the material requires the tone described above.
- **The wiki's voice** is encyclopedic — factual, verifiable, without agenda. Tolstoy's radical ideas are presented as historical fact, not as advocacy.
- **Documentation discipline.** Evergreen docs are edited in place with `changelog:` frontmatter. Dated reports get a Status block at the top rather than retroactive body edits — the body stays as a record of what was known on its date. See `conventions.md`.
