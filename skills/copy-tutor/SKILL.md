---
name: copy-tutor
description: Teach one business flow from fixed Rust/Python/Dart source, explaining needs, design choices, methods and code excerpts in a collapsible HTML lecture. Use for copy-tutor, 带我复现, step-by-step construction guides, and tutor next/retell/ask/note. Uses Code Review Kit evidence; never writes the learning project's code.
metadata:
  runtime: Python 3.11+; bundled offline Code Review Kit; first setup may need pip access.
---

# copy-tutor

帮助用户理解项目为什么这样设计、每段代码有什么意义。沿可能的书写路线逐步展开一份**固定版本的真实源码**，可以回到前面的函数展示更多行。用户不必复制、粘贴、运行或接受测验。Tutor 选择行与写讲解，不生成或修改学习项目代码。

命令使用本 Skill 的 `python scripts/review.py`（也可 python3）。CLI、Codex、Claude Code、Pi/Cowork 共用这套核心，不自行写解析器或 HTML。展示语言按用户明确指定，否则按提示词语言，提取/渲染时传 `--output-language zh|en`。

## 开始一项业务

1. 确认项目、业务和固定提交；已确认的不重复问。Git 项目提取加 `--source-ref COMMIT`，只读 Git 对象，无需用户提交、暂存或切换工作区。非 Git 项目固定工作区快照，不能冒充提交。
2. 初次检查 `doctor`，缺依赖才运行 `scripts/setup.py`。用 Kit 的 `function --repo … --symbol … --file … --source-ref … --out …` 或 `business --manifest …` 提取；业务清单明确列出必需节点。讲义、讨论和状态放在学习项目之外。
3. 从有预算的 Kit 证据包确定具体请求、可观察结果和必须保持的约束，再排大纲请用户确认。不要默认读整份 facts/仓库。“主路径、数据、错误、边界、性能”是检查清单，不是强制课序；事件/UI 先看动作与状态，事务先看约束与恢复。
4. 按[数据格式](references/lecture-format.md)创建 schema_version:2 的短讲义骨架：稳定 id、scenario/observable/invariants、outline 与空 steps。outline 可包含节点与计划展示范围，先不写全部正文。

## 每次只推进一块

- 先取材料：`tutor packet --lecture … --facts … --step ID --out step-packet.json --bytes 12000`。支持尚未讲到的 outline 节点、旧修订和可选讨论。证据不足才补特定节点；不重读完整仓库。可用 --explanations 复用有效 Review 行为解释，不能当作动机证据。
- 每步以一个函数或类型为中心；约 20 行是软预算，保持多行表达式完整。只写这一步的数据草稿，然后用 `tutor add --lecture … --facts … --step ID --replacement draft.json` 追加，不重写全讲义。
- 只给 show；工具计算折叠补集和其他步骤去向。必要时用 defer/remainder，未知保留待安排。被调函数写 `{node, ref}`，工具提取真实签名。
- 每步讲目标、理由、实现方法、代码含义与位置。理由包含性质 kind、依据 support、必要局限 limits。实验支持行为，注释代表作者说法；都不独自证明设计动机。不能确认的动机照实说明。
- 区分 progress（前面看过/本次展开/接下来）、behavior（固定代码在何种条件下产生什么结果）、decisions[].otherwise（明确的反事实比较）。不写“原来没有处理，现在加入处理”的源码演变故事。
- 关键决策最多 3 个，没有就不凑；讲到实现方法即可，语法概念留给用户提问。可以调整详略，但提问少不代表水平高，不建立能力画像。
- 运行 `lecture --lecture … --facts … --discussion …` 生成 HTML，告知路径，等待用户选下一步/重讲。工具只维护阅读位置，不宣布用户掌握。

## 响应用户动作

页面复制的是**对话消息，不是待执行的 shell**。含讲义/步骤/修订身份；处理前核对身份，过期时读当前状态，不猜编号。

- **下一步**：`tutor next --lecture … --step ID --expected-revision K` 记录用户选择的位置。下一步已有有效正文就直接定位，尚未撰写才取包写草稿。只说“继续”时用 `tutor status --lecture …` 恢复位置。中途明确跳转用 resume；展示链接附加 #步骤id。到大纲末尾说明路线已结束，不等同于已经学会。
- **重讲**：写新解释 replacement.json，运行 `tutor retell --lecture … --facts … --step ID --expected-revision K --replacement … --reason …`。工具保存完整旧视图并增修订；不手工编辑 earlier/r。渲染后停留本步。
- **提问/旁注**：页面给出 `{target, quote}`。仅取目标修订的必要材料作答，不推进主线。完整选文、问题、回答或用户旁注写入本地 JSON，经 `discuss --lecture … --discussion … --record-file …` 追加，然后重渲染。不得截断原记录、用摘要替换或自动删除；只有用户明确要求才能删除。

具体命令、预算/缓存、状态和结构化讨论见[机械操作](references/operations.md)，按当前动作读取。重讲与讨论更新由工具负责；AI 专注解释、路线和不确定性。

## 运行与共享

默认只读分析。确需运行学习项目时，逐次说明命令、目录、观察目标并先征得用户确认，在临时副本/隔离环境执行；没运行就不标实测。

公开讲义渲染时省略 --discussion，且不分享个人 discussion/state 文件。页面不调用模型。“复制为对话消息”可给普通 Chat，但问答需自行保存。首版不做模型 API、画像、共享库、编辑器插件或普通 Chat 完整教学包。
