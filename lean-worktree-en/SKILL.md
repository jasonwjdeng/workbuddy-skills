---
name: lean-worktree-en
description: Discipline skill (model-invoked). Use before starting feature work that needs isolation or before executing an implementation plan — detect existing isolation first, then native tools, then git worktree fallback, and verify a clean test baseline before starting. Triggers: worktree, isolated workspace, new branch for this feature.
invocation: model
---

# Lean Worktree — Isolate Before You Start

**Core principle: detect first, native second, git last. Never fight the harness.**
**Opening line**: "I'm setting up an isolated workspace with lean-worktree."

## Step 0: Detect existing isolation (mandatory — never eyeball it)

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
git rev-parse --show-superproject-working-tree 2>/dev/null   # output = submodule; treat as normal repo
```

- `GIT_DIR != GIT_COMMON` and not a submodule → **already in a worktree** — skip to Step 2, never nest another
- Normal repo → unless the user has already declared a preference, ask first:
  > "Want me to set up an isolated worktree? It protects your current branch from changes."
  If they decline → work in place, skip to Step 2

## Step 1: Create (in this order)

1. **Native tools first**: if the harness offers one (`EnterWorktree`, a `/worktree` command, etc.), use it — it owns placement, branching, and cleanup. Bypassing it with `git worktree add` creates phantom state the harness can't see or manage
2. **Git fallback** (no native tool):
   - Directory: user-declared > existing `.worktrees/` or `worktrees/` (if both, `.worktrees/` wins) > default new `.worktrees/`
   - **Must verify it's gitignored**: `git check-ignore -q .worktrees`; if not, add to .gitignore and commit first (otherwise the whole worktree gets committed into the repo)
   - `git worktree add .worktrees/<branch> -b <branch> && cd .worktrees/<branch>`
   - Permission denied (sandbox) → tell the user, work in place

## Step 2: Project setup + baseline tests

Install deps by project type (package.json → npm install; pyproject/requirements → pip; pom.xml → Maven). Then **run the full test suite to confirm a clean baseline**:

- Green → report: `Workspace ready at <path>, tests passing (N), ready to implement <feature>`
- Red → report failures and ask: proceed or fix the baseline first. **Starting on a dirty baseline makes every later failure unattributable**

## Red Flags

| Thought | Reality |
|---------|---------|
| "Obviously not in a worktree, skip the check" | Run Step 0. Harness-created isolation and submodules both fool eyeballing |
| "git worktree add is quicker than hunting for a native tool" | Bypassing the native tool is the #1 mistake — it creates state the harness can't manage |
| "The directory is surely ignored already" | Run git check-ignore. Unignored = the entire tree lands in the repo |
| "Fresh workspace, baseline tests can wait" | A dirty baseline makes every later failure ambiguous. Run them now |
