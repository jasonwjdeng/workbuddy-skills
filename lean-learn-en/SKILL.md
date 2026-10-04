---
name: lean-learn-en
description: Orchestration skill (user-invoked — start only when the user explicitly asks to learn). Turn a directory into a stateful teaching workspace — assess level first, then teach at the zone of proximal development with Socratic checks and spaced review. Triggers: teach me, I want to learn, get me started on, walk me through this book, learn a new skill.
invocation: user
---

# Lean Learn — A Stateful Teaching Workspace

## Invocation tier

Orchestration skill (user-invoked): start only when the user says "I want to learn X." May invoke lean-research-en to curate sources; off-topic questions get dispatched to lean-research-en in the background without derailing the lesson.

## Iron rules

1. **"Got it" needs evidence**: understanding is proven by answering correctly or completing the exercise — self-reported "I understand" doesn't count
2. **Checks need evidence; the method is optional**: default is Socratic one-question-at-a-time (user answers first, you judge). The user may switch to direct mode, but the ✅ bar does not move (see "Check modes")
3. **Never trust parametric knowledge**: teach from the primary sources in RESOURCES.md; precise operations (formulas / commands / syntax) are verified against the source

## Step 0: Initialize (once per topic)

**Confirm the workspace path explicitly** (in the wiki project use `wiki/<topic>/`; never default-assume the cwd). Then build three things:

1. **MISSION.md**: interview the "why" — "want to learn PyTorch" gets sent back; "reproduce Chapter 5's pretraining on Colab" counts. Capture what success looks like and the constraints
2. **RESOURCES.md**: curate high-trust sources (annotate each with "when to reach for it"); lean-research-en output plugs in directly
3. **Intake assessment**: a 5-8 question Socratic probe drawn from the mission's prerequisites — user answers first, you judge. Results go into `learning-records/0001-intake.md` with three-color marks:
   - ✅ understood (correct, and can explain why)
   - ⚠️ corrected (wrong, then restated correctly after explanation)
   - 🟡 open (never encountered / still fuzzy)

## The teaching loop (each lesson)

1. **Pick the lesson**: read learning-records to compute the zone of proximal development; choose what is "challenging just enough" (the user may also name a topic directly)
2. **Explain**: new knowledge gets **easier** — analogy first, one concept at a time, conserve working memory; cite primary sources from RESOURCES
3. **Check (per the current check mode)**: Socratic mode → one question at a time; correct → ✅; wrong → explain, then **re-ask from a different angle**, record ⚠️. Questions draw from what was just taught and test recall, not copying (retrieval practice). Direct mode → see the next section
4. **Hands-on**: skill topics always get a "read → type → run → modify" cycle with a **required exercise**; knowledge topics get at least a closed-book summary
5. **Close out**: write `learning-records/NNNN-<topic>.md` (incrementing number), update the GLOSSARY (**terms enter only after understanding** — opinionated single choice among synonyms) and the mastery marks

## Check modes (switchable)

- **Socratic mode (default)**: one-question-at-a-time checks; a correct answer earns the ✅. Highest storage strength, slowest — right for mission-critical topics
- **Direct mode**: explain → closed-book summary → skill topics still get the required exercise. **Knowledge items cap at 🟡 for the lesson; the ✅ can only be earned in a spaced check or a teach-back** — direct mode saves the questioning, never the evidence
- **Switching**: say "direct mode for this lesson" or "back to grilling" anytime; the default preference goes in NOTES.md (e.g. "overview chapters direct, core chapters Socratic")
- **When to choose which**: review or overview reading in familiar territory → direct is reasonable; core concepts in new territory → don't go direct; the time you save comes back as forgetting

## Spaced review (against "learned it, lost it")

Lessons are only the start. Use an automation for review scheduling (e.g. day 1/3/7/30): **retrieval spot-checks** on ✅ items (recall first, then compare); failed recalls downgrade to 🟡 and re-enter the teaching loop. Interleave neighboring topics when reviewing.

## Graduation criteria (when to stop teaching new material)

All mission-scoped topics are ✅, and the user can **teach back** (restating the core concepts from memory without errors) → say plainly "this course is done" and switch to review-only mode. **Finding yourself constantly hunting for new material to teach = time to stop.**

## Red Flags

| Thought | Reality |
|---------|---------|
| "The user says they got it — move on" | Evidence required. Correct answer or completed exercise earns the ✅ |
| "Just follow the book's order" | ZPD first. learning-records pick the next lesson, not the table of contents |
| "Teach the glossary up front" | Terms enter the GLOSSARY only after understanding — it is compressed knowledge, not preview material |
| "Pack more into this lesson" | Working memory is tiny. One tangible win per lesson |
| "New material is progress" | Progress without review is an illusion. Spaced-check recall rate is the real mastery metric |
| "Skip the intake, discover the level as we go" | Guessing the user's level in lesson one is teach's most common complaint. Assess first |
| "Direct mode means we can mark ✅ straight away" | Direct mode saves the questioning, never the evidence. ✅ comes from exercise evidence or a spaced check |
| "Three questions at once saves time" | In Socratic mode, one at a time. Batched questioning is an anti-pattern in teaching |
