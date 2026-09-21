---
name: lean-team
description: 编排类 skill（user-invoked，仅用户明确要求时启动）。用 agent 团队执行实施计划：主会话做 controller（协调+裁决，不写码），按 S/M/L 分级派遣 implementer / reviewer subagent。触发词：agent team、团队执行、SDD、用团队做、subagent 开发。
invocation: user
---

# Lean Team — 团队执行计划

## 调用层级

编排类（user-invoked）：只在用户拿着计划明确要求团队执行时启动。controller（主会话）**不写码、不修码**——修复一律派 implementer，controller 修复会跳过评审。

## 铁律

1. **产物文件交接，上下文只留协调**——文件写盘免费，读进上下文才花钱
2. **Rulings, not stalls**——只有四件事停下问人：不可逆操作、安全敏感、worktree 外副作用（merge/push）、计划坏到每条路都是猜。其余 controller 裁决并记 ledger
3. **派遣时显式指定模型**——转录级 → lite，集成判断 → default，架构/终审 → reasoning。不指定 = 默认继承最贵模型

## 第 0 步：执行分级（先宣布，可否决）

- **S（1-2 个机械任务）→ 不起团队**：controller 内联执行（lean-tdd + lean-review 自检），零派遣
- **M（3-8 个任务）→ 批量模式**：按形状分组（同类小改动合并），**一批一个 implementer + 一个 reviewer**
- **L（8+ 任务或高风险）→ 完整循环**：每任务 brief → implementer → 双阶段评审 → fix loop

拿不准取轻的一档；中途规模失控可升档。

## 第 1 步：Setup（M/L）

1. lean-worktree 建隔离（main 上开工须用户同意）
2. 工作区 `.lean-team/<plan 名>/`（确认 git-ignored）：ledger `progress.md` 首行 `# lean-team ledger — plan: <路径>`
3. **ledger 是恢复地图**：有 `Task N: complete` 行的任务绝不重派（会话压缩后信 ledger + git log，不信记忆）
4. 读 plan 一次，todo 每任务；L 级做 preflight 冲突扫描（任务间矛盾、plan 与约束矛盾），发现即裁决记入 ledger

## 第 2 步：任务循环（L 级；M 级按批执行同流程，熔断降为 3 轮）

1. 记 `BASE=$(git rev-parse HEAD)`；把任务全文抽成 `task-N-brief.md`（**精确值只进 brief，是唯一需求源**）
2. 派 implementer（模板 `references/implementer-prompt.md`）：给 brief 路径 + 前置任务接口 + 全局约束 + report 路径。**绝不粘贴历史**
3. 回执只读头 3 行（`STATUS | commits | tests | findings`）：DONE → 评审；其余按约处理
4. 生成 diff package：`git diff -U3 --stat BASE HEAD`（**排除 lock/生成文件**），超阈值先给 stat 让 reviewer 点名
5. 派 task-reviewer（default 模型，模板 `references/task-reviewer-prompt.md`）：**spec ✅ + 质量 ✅ 双过才算过**
6. Fix loop（≤5 轮）：R1-3 用 SendMessage resume 原 implementer；R4-5 换更强模型的新鲜 implementer；每轮 = 一次 fix + 一次 scoped re-review（`references/re-review-prompt.md`）
7. 5 轮未收敛 → controller 逐项裁决：可争议/无下游依赖 → `parked — Ruling:`；**承重**（下游要建在上面/暴露 plan 缺陷）→ 裁决最小解锁改动。静默丢弃禁止
8. 验收后 ledger 记一行，**删除该任务的 brief/report/diff 三文件**（git 历史已是记录）

## 第 3 步：终审（M/L 必做）

`git diff -U3 $(git merge-base <base> HEAD) HEAD` 生成全分支 package，**reasoning 模型**一次派遣。有 findings → **只派一波 fix**（完整清单给一个 fixer，不是一个 finding 一个）+ 一次 scoped 复审；残余按熔断规则裁决，承重的留给用户。

## 第 4 步：收尾

穷举 ledger 里所有 `Ruling:` 条目（每条带"错了的代价"）列给用户——这是代做的决定到达用户的唯一通道。然后进 lean-finish。

## Red Flags

| 念头 | 现实 |
|------|------|
| "我自己改快，派遣是开销" | controller 修复跳过评审。派 implementer |
| "brief 太长，让 subagent 读整个 plan" | 精确值只进 brief。读全 plan 是 42k 字符事故的根源 |
| "再修一轮就会收敛" | 过熔断不收敛 = 结构性失败。裁决 |
| "这个小问题明显是误报，扔掉" | 只在熔断处裁决，且每条都是 ledger 条目 |
| "ledger 记账是开销" | 没有 ledger 的 controller 把已完成任务整个重派过 |
| "implementer 自己派了个评审，白赚的" | 重复评审席位。任务评审是唯一的门 |
