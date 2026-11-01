---
name: copy-tutor
description: Teach how an existing program is built by walking a learner through rebuilding one business flow step by step - what each step must achieve, which needs and constraints lead to the design, which method implements it, and why earlier functions are revisited. Produces a shareable HTML lecture whose code excerpts are exact lines from Code Review Kit's source snapshot, with questions and notes bound to lecture revisions. Use when the user wants to learn or reproduce how a project or feature was built ("带我复现", "逐步讲解这个项目怎么搭的", "copy-tutor", "tutor next / retell / ask / note").
metadata:
  runtime: Python 3.11+; the bundled Code Review Kit tool extracts facts (first setup needs pip access) and renders lectures.
---

# copy-tutor

带用户沿“逐步搭建”的路线理解一项业务：每一步要做成什么，哪些需求、约束和代价导致了这样的设计，用什么方法实现，以及为什么之后要回到前面的函数补代码。

复现对象永远是一份固定版本的源码。各步骤只是逐步展开这份源码，讲解可以重讲。你只负责选择代码行和撰写讲解，**不写、不改学习项目的代码**。

下面的命令都相对于本 skill 目录（`python3` 也可以）。讲义格式见 [references/lecture-format.md](references/lecture-format.md)，样例见仓库里的 `examples/document-pipeline/lecture.zh.json`。

## 流程

1. **确认范围**
   - 确认学习项目路径和一项业务。
   - 要求学习项目处于**干净的固定提交**：工作区有未提交改动时，先请用户提交或暂存。
   - 讲义目录放在学习项目之外，例如 `<笔记根目录>/<项目>/<业务>/`。

2. **取事实**
   - 第一次使用前运行 `python scripts/review.py doctor`；缺少依赖时运行 `python scripts/setup.py`。
   - 提取事实：
     - 单个函数：`python scripts/review.py function --repo REPO --symbol SYMBOL --file FILE --out <讲义目录>/kit`
     - 跨模块业务：用业务清单 `business --manifest …`，在清单里直接列出课程必须包含的节点。
   - 这一步只读源码，不运行项目。
   - 只读需要的事实字段：节点的 `id`、`line`/`end_line`、`calls`、`branches`、`errors`、`returns`、`imports`，以及 `source`。不要通读整个仓库或整份 facts。
   - `lecture` 命令发现讲义需要的节点不在事实里时会报错，并说明有没有节点因上限被截断。

3. **排大纲，经用户确认后才写正文**。先回答三个问题，再决定函数的展示顺序：
   - 拿哪个**具体请求**贯穿整门课？
   - 用户会**观察到**什么变化？
   - 哪些**状态或约束**必须始终成立？

   “主路径骨架 → 数据结构 → 错误路径 → 边界 → 抽象与性能”只是遗漏检查清单和步骤标签，不是固定课序。不同类型的项目可以这样调整：
   - 事件驱动：先讲一个事件怎样改变状态；
   - UI：先讲用户动作 → 状态变化 → 界面结果；
   - 配置密集的系统：先讲配置来源和覆盖顺序；
   - 事务、并发、资源管理：先讲必须守住的约束和失败后的恢复。

   其他要求：
   - 每步以一个主要节点（函数或类型）为中心，类型、配置等可以单独作为准备步骤。
   - 把大纲以表格形式给用户确认，用户可以调整阅读路线。

4. **逐步写讲义**
   - 每次只写一步，写进 `lecture.json`，然后运行：
     `python scripts/review.py lecture --lecture <讲义目录>/lecture.json --facts <讲义目录>/kit/facts.json --discussion <讲义目录>/discussion.jsonl --accept-new`
   - `--accept-new` 只给尚未绑定的步骤写入当前证据摘要。
   - 报错就修改数据，不要绕过校验。
   - 把 HTML 路径告诉用户，然后停下，等用户说“下一步”或“重讲”。
   - 给别人看的公开版讲义，省略 `--discussion` 再渲染一次。

5. **响应命令**。用户在页面上点按钮复制命令，或直接输入。`<讲义id>/sN.rK` 表示讲义里第 N 步的第 K 次讲解。
   - `tutor next`：写下一步。
   - `tutor retell <讲义id>/sN`：原位重讲。
     1. 把当前讲解的 goal、reasons、method、decisions、change/consider，连同重讲原因，移进 `earlier`；
     2. `r` 加 1，换讲法或例子重写；
     3. 不自动推进到下一步。

     步骤 id 永不改变或复用，重排步骤也不改 id。
   - `tutor ask <讲义id>/sN.rK "引文" 问题`：只读这一步的代码行和讲解来回答，不推进主线。回答后运行：
     `python scripts/review.py discuss --lecture … --discussion … --step sN --revision K --kind ask --quote "引文" --question "…" --answer-file <回答文件>`
     然后重新渲染。
   - `tutor note <讲义id>/sN.rK "引文" 理解`：用 `discuss … --kind note --text "…"` 原样记录用户的话。
   - 讨论记录只能追加。只有用户明确要求时才可以删除；整理时不能用摘要替换原始记录。

## 讲解规则

- **目标**：直接说明这一步要做成什么、为什么需要它。这是导览，不向用户出题。
- **理由要连起来**：写出需求、必须满足的正确性要求、当前的选择、付出的代价。每条理由包含：
  - `kind`：`recorded`（作者明确记录过）、`inferred`（根据结果推断）或 `teaching`（为了教学给出的解释）；
  - `support`：支持这条理由的具体源码行、注释或实验；
  - `limits`：还有什么无法确定。

  实验只能支持“行为是这样”，不能单独证明作者的动机；注释说明的是作者的说法，不自动证明说法正确。能确认行为、但无法确定选择理由时，就照实写出来。
- **实现方法**：讲到方法和关键工具、参数为止，例如“用 ffmpeg 的 -vn 去掉视频流”。语法、参数含义、概念细节留给用户提问。可以按本次对话的提问调整详略，但不要据此建立能力画像：提问少不等于水平高。
- **代码节选**：
  - 每步约 20 行，只是软预算。多行表达式保持完整；新手可以少看几行。
  - 节点里的其余行都要折叠，并写明去向。
  - 与课程无关的大段代码标上 `out: true`，页面会把它们合并成一条“本课程不涉及”，不让读者逐条看去向说明。
- **关键决策**：只写真正存在取舍的地方，最多 3 处，没有就不写。不要为了凑数编一个明显更差的替代方案。
- **行为变化**：写“之前 / 现在”。错误路径步骤改写成“考虑到……所以……”的列表（`consider`）。
- **放在哪里**：写明文件、排在哪个函数前后、需要的 import（从事实的 `imports` 里取），让读者能自行复现。

## 运行学习项目

只有当实测能帮助理解行为时才运行，而且**每次都要先征得用户确认**：

- 说明具体命令、在哪个目录运行、想观察什么结果；
- 在临时副本或隔离环境中运行，不往学习项目里写东西；
- 结果作为理由的 `support`，写明命令和关键输出。

用户不同意就不运行，只说明“可以运行某条命令来观察”。

## 首版不做

学习者画像、自动判断每行代码的教学角色、普通聊天用的教学包、讲义共享库、编辑器插件。

页面上的“复制为对话消息”可以把选中的原文、步骤目标和源码位置交给任意聊天模型提问；但这些问答不会自动存回讨论记录。
