---
name: lean-finish-en
description: Discipline skill (model-invoked — applies when implementation is complete, tests pass, and the integration decision comes up). Branch completion workflow: verify tests → detect environment → confirm base branch → present options → execute choice → clean up. Triggers: wrap up, merge, finish branch, create PR, integrate this work.
invocation: model
---

# Lean Finish — Completing a Branch

**Core flow: verify → detect → confirm base → present menu → execute → clean up. The integration decision always belongs to the user.**
**Opening line**: "I'm completing this work with lean-finish."

## Step 1: Verify tests (fresh run on the tree being integrated)

Run the project's full test suite. **Red → report failures and stop; the menu appears only after a green suite.** "It passed earlier this session" doesn't count — a green run only proves the tree it ran on.

## Step 2: Detect environment

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
WORKTREE_PATH=$(git rev-parse --show-toplevel)   # capture now, while still inside the workspace
```

`GIT_DIR == GIT_COMMON` → normal repo; otherwise → worktree; detached HEAD → externally managed workspace (reduced menu, leave it alone).

## Step 3: Confirm the base branch

The base is whatever this work forked from (named in the plan, conversation, or the branch's upstream). If unsure, ask: "This branch split from <best guess> — correct?" **Merging into the wrong base is far more expensive than one question.**

## Step 4: Present the menu (verbatim, then wait)

Normal repo / named-branch worktree — exactly three options:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
```

Detached HEAD gets two (no merge; push becomes `HEAD:refs/heads/<new-branch>`). **Discard is never in the menu** — it happens only when the user explicitly asks.

## Step 5: Execute the choice

- **Merge**: back to main repo root → `git checkout <base> && git pull && git merge <branch>` → **re-run tests on the merged result**. Red after merge: stop, leave branch and worktree in place, investigate (nothing pushed, recoverable). Only after green: clean up + `git branch -d`
- **PR**: `git push -u origin <branch>`, create the PR with forge tooling (follow the repo's PR template), report the URL. **Keep the worktree** — PR feedback gets iterated there. Confirm explicitly before pushing, per user convention
- **Keep**: report "Keeping branch <name>. Worktree preserved at <path>."

**Discard path (only on explicit user request)**: list what will be permanently deleted — branch, commit list, worktree path — and require the user to **type `discard` to confirm**. "Yeah, get rid of it" is not confirmation. After confirmation: clean up + `git branch -D`.

## Step 6: Clean up the worktree (Option 1 and confirmed discards only)

- Normal repo → nothing to do
- Worktree under `.worktrees/` or `worktrees/` → `git worktree remove "$WORKTREE_PATH" && git worktree prune`
- **Removal refused (modified/untracked files) → never `--force` on your own initiative.** Show what's at stake with `git status --porcelain -uall` and offer three choices: commit to the branch / move into the main repo / delete (unrecoverable). Carry out the choice, then remove
- Worktrees anywhere else → owned by the host environment, leave in place

## Red Flags

| Thought | Reality |
|---------|---------|
| "They obviously want it merged" | Integration is the user's decision. Present the menu and wait |
| "They're done with this feature — I'll offer to discard" | The menu is three items. Discard happens only when the user asks in so many words |
| "The PR is up, the worktree is clutter" | PR feedback gets fixed there. It stays until the work lands |
| "Removal refused — `--force` finishes the job" | Refused means files exist only in that worktree. `--force` destroys them permanently. Show and ask |
| "The base is obviously main" | Confirm the fork point or ask. Wrong-base merges are expensive |
| "Push rejected — force-push will fix it" | Rejected means the remote moved. Investigate; force-push only on explicit user request |
