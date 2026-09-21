---
name: lean-finish
description: 纪律类 skill（model-invoked，实现完成且测试全绿、需要决定如何整合时自动生效）。分支收尾流程：验证测试 → 检测环境 → 确认基分支 → 呈现选项 → 执行选择 → 清理。触发词：收尾、完成了、merge、合并分支、create PR。
invocation: model
---

# Lean Finish — 分支收尾

**核心流程：验证 → 检测 → 确认基分支 → 呈现菜单 → 执行 → 清理。整合决定永远属于用户。**
**开场声明**："我正在用 lean-finish 收尾这项工作。"

## 第 1 步：验证测试（在要整合的这颗树上重跑）

跑项目全量测试。**红 → 报告失败并停下，菜单只在全绿后出现**。"本session早些时候跑过"不算数——绿只证明跑过的那颗树。

## 第 2 步：检测环境

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
WORKTREE_PATH=$(git rev-parse --show-toplevel)   # 趁还在工作区内先存好
```

`GIT_DIR == GIT_COMMON` → 普通仓库；不等 → worktree；detached HEAD → 外部管理的工作区（菜单减配，不动它）。

## 第 3 步：确认基分支

基分支 = 本工作从哪儿分叉的（计划/对话/上游分支里有）。不确定就问："这分支是从 <最佳猜测> 分出来的，对吗？"——**合错基分支的代价远大于多问一句**。

## 第 4 步：呈现菜单（原文呈现，等用户选）

普通仓库 / 命名分支 worktree，恰好三个选项：

```
实现完成。接下来怎么处理？

1. 本地合并回 <base-branch>
2. 推送并创建 Pull Request
3. 保留分支现状（我稍后自己处理）
```

detached HEAD 只有两项（去掉合并，推送改为 `HEAD:refs/heads/<新分支>`）。**丢弃工作永远不在菜单里**——只有用户明确说丢弃时才走丢弃路径。

## 第 5 步：执行选择

- **合并**：回主仓库根 → `git checkout <base> && git pull && git merge <branch>` → **对合并结果重跑测试**。合并后红：停下，分支和 worktree 原样保留，排查（未推送，可恢复）。全绿后才清理 + `git branch -d`
- **PR**：`git push -u origin <branch>`，用 forge 工具建 PR（遵循仓库 PR 模板），报告 URL。**保留 worktree**——PR 反馈在那里迭代。push 前按用户惯例显式确认
- **保留**：报告"保留分支 <名>，worktree 在 <路径>"

**丢弃路径（仅用户明确要求时）**：先列出将永久删除的分支、提交清单、worktree 路径，要求用户**输入 discard 确认**。"嗯，删了吧"不算确认。确认后清理 + `git branch -D`。

## 第 6 步：清理 worktree（仅选项 1 和已确认的丢弃）

- 普通仓库 → 无事可做
- worktree 在 `.worktrees/` 或 `worktrees/` 下 → `git worktree remove "$WORKTREE_PATH" && git worktree prune`
- **remove 被拒（有未提交/未跟踪文件）→ 绝不主动 --force**。先 `git status --porcelain -uall` 亮出风险，给用户三个选择：提交到分支 / 移到主仓库 / 删除（不可恢复）。执行后再删
- 其他位置的 worktree → 属于宿主环境，原样保留

## Red Flags

| 念头 | 现实 |
|------|------|
| "他们显然想合并" | 整合是用户的决定。呈现菜单，等待 |
| "这个功能他们做完了，顺手问下要不要丢弃" | 菜单就三项。丢弃只在用户明确说时发生 |
| "PR 都建了，worktree 没用了" | PR 反馈要在那里面改。工作落地前它都在 |
| "remove 被拒，--force 一下就完事" | 被拒 = 有文件只存在于那个 worktree。--force 是永久销毁。亮出来问 |
| "基分支显然是 main" | 确认分叉点或问。合错基分支很贵 |
| "push 被拒，force-push 就行" | 被拒 = 远程动了。先排查；force-push 只在用户明确要求时 |
