---
name: lean-research-en
description: Discipline skill (model-invoked — applies when the user asks for research). Evidence-first research workflow — a background agent reads primary sources and the main session synthesizes a document with per-claim citations, evidence grading, and falsifiability conditions. Triggers: research, investigate, deep dive, due diligence, industry analysis, look into this.
invocation: model
---

# Lean Research — Evidence-First Research

**Iron law: every claim traces back to the source that owns it. A secondhand write-up is a lead, not evidence.**

## Step 0: Frame the question (lightweight — no full interrogation)

Turn the request into an **answerable, bounded** research question. Ask the user at most one round, and only when: the question has multiple legitimate readings, or the boundary decides the answer (time range, market, definitions). Everything else you decide yourself and record in the "search boundaries" appendix.

## Step 1: Background research (dispatch a subagent; the user keeps working)

A background agent does the reading; the main session only synthesizes. The agent's contract:

1. **Primary sources first**: official docs, source code, regulatory filings, financial statements, API docs, original papers. Secondhand articles are used only to *find* primary sources, never cited
2. **Search with multiple phrasings**, not just the first obvious keyword; stop when further searching stops changing conclusions
3. Record **search boundaries**: which sources, what date range, what was excluded and why
4. Write raw notes to a temp file (URL + key excerpts per source) — **never paste full text back into the main session**

## Step 2: Evidence grading and citation-circle detection (main session)

Grade every key claim:

| Grade | Meaning | Weight |
|-------|---------|--------|
| **[Primary]** | The source itself (docs / filings / regulations / code) | Citable |
| **[Secondary]** | Edited reporting (reputable press / official blogs) | Usable, must be labeled |
| **[Opinion]** | Personal blogs / social media / commentary | Sentiment only, never factual basis |

**Citation-circle check**: when N sources say the same thing, trace whether they share one origin — if so, they count as **one** piece of evidence, and say so in the text.

## Step 3: Synthesize

Single-file deliverable (Markdown notes; HTML when the user wants a report). Fixed structure:

1. **Conclusions first** (3-5 items, each with an evidence-grade marker)
2. **Evidence table**: claim | grade | source (link per row)
3. **Conflicts and uncertainty**: present conflicting evidence side by side — never bury it; if evidence is thin, say "thin"
4. **Falsifiability**: each core conclusion states what evidence would overturn it
5. **Appendix: search boundaries** (what was searched, date range, exclusions) — coverage must be auditable

**Report mode** (equity/FX/industry coverage): when the user prefers it — tables + embedded charts + bull/base/bear scenarios + explicit assumptions.

## Filing

Follow the target project's conventions. In the wiki project: sources go to `raw/` (read-only), notes to `wiki/<category>/`, and update index.md and log.md. Without a convention, state where you put it.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Official docs are long — a summary blog will do" | Secondhand is for finding primary sources. Citations land on the origin |
| "Three sources all say it" | Check for a citation circle first. Three retellings of one source = one piece of evidence |
| "Hedging with 'maybe' means I don't need to verify" | Vague wording is not a waiver. Grade the evidence |
| "Nothing online — I'll write from experience" | Parametric knowledge is untrusted. Not found means write "no primary source found" |
| "Read everything before writing anything" | Stop at diminishing returns; record the boundary in the appendix |
| "Cherry-pick the convenient side of conflicting evidence" | Present both sides. Research that hides conflict is advocacy |
