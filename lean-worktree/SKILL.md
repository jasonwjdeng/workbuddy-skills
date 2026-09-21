---
name: lean-worktree
description: 纪律类 skill（model-invoked）。开始需要隔离的功能开发或执行实施计划前使用：先检测是否已在隔离环境，再用原生工具或 git worktree 创建隔离工作区，跑通基线测试后才开工。触发词：worktree、隔离工作区、新分支开发。
invocation: model
---

# Lean Worktree — 隔离开工

**核心原则：先检测，再原生，最后 git。绝不和 harness 对着干。**
**开场声明**："我正在用 lean-worktree 建立隔离工作区。"

## 第 0 步：检测现有隔离（必做，不许目测）

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
git rev-parse --show-superproject-working-tree 2>/dev/null   # 有输出 = 在 submodule 里，按普通仓库处理
```

- `GIT_DIR != GIT_COMMON` 且非 submodule → **已在 worktree 中**，跳到第 2 步，绝不嵌套创建
- 普通仓库 → 用户没声明过偏好的话，先问一句再建：
  > "要我建一个隔离 worktree 吗？可以保护当前分支不被改动。"
  用户拒绝 → 原地工作，跳到第 2 步

## 第 1 步：创建（按此顺序）

1. **原生工具优先**：harness 提供 worktree 工具（`EnterWorktree`、`/worktree` 命令等）就用它——它管目录、分支和清理。绕过它用 `git worktree add` 会产生 harness 看不见的幽灵状态
2. **git 兜底**（无原生工具时）：
   - 目录：用户声明 > 已有 `.worktrees/` 或 `worktrees/`（两个都有用 `.worktrees/`）> 默认新建 `.worktrees/`
   - **必须验证被 gitignore**：`git check-ignore -q .worktrees`；没忽略就先加进 .gitignore 并提交（否则整个 worktree 会被提交进仓库）
   - `git worktree add .worktrees/<branch> -b <branch> && cd .worktrees/<branch>`
   - 权限被拒（沙箱）→ 告知用户，原地工作

## 第 2 步：项目初始化 + 基线测试

按项目类型装依赖（package.json → npm install；pyproject/requirements → pip；pom.xml → Maven 跳过依赖检查直接编测试）。然后**跑全量测试确认基线干净**：

- 绿 → 报告：`工作区就绪 <路径>，测试全过（N 个），可以开工 <功能名>`
- 红 → 报告失败，问用户：继续还是先把基线修绿。**脏基线上开工，之后每个失败都无法归因**

## Red Flags

| 念头 | 现实 |
|------|------|
| "明显不在 worktree 里，不用查" | 跑第 0 步。harness 建的隔离和 submodule 都能骗过目测 |
| "git worktree add 比找原生工具快" | 绕过原生工具是头号错误——它产生的状态 harness 无法管理 |
| "目录肯定已经被忽略了" | 跑 git check-ignore。没忽略 = 整个目录进仓库 |
| "工作区是新的，基线测试可以等等" | 脏基线让后续所有失败无法归因。现在就跑 |
