---
name: lean-team-en
description: Orchestration skill (user-invoked — start only on explicit user request). Execute an implementation plan with an agent team — the main session acts as controller (coordinate + adjudicate, never codes), dispatching implementer / reviewer subagents by S/M/L tier. Triggers: agent team, team execution, SDD, subagent development, run this plan with a team.
invocation: user
---

# Lean Team — Execute Plans with a Team

## Invocation tier

Orchestration skill (user-invoked): start only when the user brings a plan and explicitly asks for team execution. The controller (main session) **never writes or fixes code** — fixes are always dispatched to an implementer; controller fixes bypass review.

## Iron rules

1. **Artifacts travel as files; context holds only coordination** — writing files to disk is free; reading them into context is what costs
2. **Rulings, not stalls** — only four things stop for a human: irreversible operations, security-sensitive actions, side effects outside the worktree (merge/push), and a plan so broken every path forward is a guess. Everything else the controller rules on and ledgers
3. **Always specify the model when dispatching** — transcription → lite, integration judgment → default, architecture/final review → reasoning. Omitting it silently inherits the most expensive model. **Use lite only when all three hold: (1) the plan section contains complete code, (2) ≤2 files touched excluding lock/generated files, (3) no new public interface. The controller decides and writes it into the brief — a cheap model never self-assesses this.** When dispatching lite, use references/lite-implementer-prompt.md. Reviewers are not downgraded; they stay on default.

## Step 0: Execution tier (announce first; user can override)

- **S (1-2 mechanical tasks) → no team**: controller executes inline (lean-tdd-en + lean-review-en self-check), zero dispatches
- **M (3-8 tasks) → batch mode**: group by shape (same-kind small edits merge), **one implementer + one reviewer per batch**
- **L (8+ tasks or high-risk) → full loop**: per-task brief → implementer → two-stage review → fix loop

When in doubt, take the lighter tier; upgrade mid-flight if scope explodes.

## Step 1: Setup (M/L)

1. Isolate with lean-worktree-en (main/master requires user consent)
2. Workspace `.lean-team/<plan-name>/` (verify git-ignored): ledger `progress.md`, first line `# lean-team ledger — plan: <path>`
3. **The ledger is the recovery map**: tasks with a `Task N: complete` line are never re-dispatched (after compaction, trust the ledger + git log, not memory)
4. Read the plan once, one todo per task; L-tier runs a preflight conflict scan (task-vs-task and plan-vs-constraints), ruling each finding into the ledger

## Step 2: Task loop (L tier; M tier runs the same flow per batch, breaker at 3 rounds)

1. Record `BASE=$(git rev-parse HEAD)`; extract the task text into `task-N-brief.md` (**exact values live only in the brief — it is the single source of requirements**)
2. Dispatch the implementer (template `references/implementer-prompt.md`): brief path + upstream interfaces + global constraints + report path. **Never paste history**
3. Read only the first 3 lines of the receipt (`STATUS | commits | tests | findings`): DONE → review; others per contract
4. Build the diff package: `git diff -U3 --stat BASE HEAD` (**exclude lockfiles and generated code**); over the size threshold, send stat first and let the reviewer pick files
5. Dispatch the task-reviewer (default model, template `references/task-reviewer-prompt.md`): **both spec ✅ and quality ✅ required**
6. Fix loop (≤5 rounds): R1-3 resume the original implementer via SendMessage; R4-5 a fresh implementer on a stronger model; each round = one fix + one scoped re-review (`references/re-review-prompt.md`)
7. Still open after round 5 → adjudicate per finding: contestable or no downstream dependency → `parked — Ruling:`; **load-bearing** (downstream builds on it, or reveals a plan defect) → rule on the smallest unblocking change. Silent discards forbidden
8. After acceptance, ledger one line and **delete the task's brief/report/diff files** (git history is the record now)

## Step 3: Final review (M/L, mandatory)

`git diff -U3 $(git merge-base <base> HEAD) HEAD` for a whole-branch package, one dispatch on the **reasoning** model. Findings → **exactly one fix wave** (full list to one fixer, not one per finding) + one scoped re-review; residuals adjudicated per the breaker rules, load-bearing ones surfaced to the user.

## Step 4: Wrap up

Exhaustively list every ledger `Ruling:` entry (each with its cost-if-wrong) for the user — the only channel through which decisions made on their behalf reach them. Then lean-finish-en.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Faster to fix it myself — dispatching is overhead" | Controller fixes skip review. Dispatch an implementer |
| "The brief is long — let the subagent read the whole plan" | Exact values live only in the brief. Whole-plan reads are how a 42k-char dispatch happens |
| "One more round will converge" | Past the breaker, rounds don't converge — the failure is structural. Adjudicate |
| "This finding is obviously a false positive — drop it" | Adjudicate only at the breaker, and every ruling is a ledger entry |
| "Ledger bookkeeping is overhead" | Controllers without one have re-dispatched entire completed task sequences |
| "The implementer spawned its own reviewer — free assurance" | A duplicate seat. The task review is the only gate |
