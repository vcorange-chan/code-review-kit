# 讲义格式

一份讲义对应一个 `lecture.json`。HTML 由 `review.py lecture` 生成，**不要手改 HTML**。

讲义里不写任何代码。代码行按行号，从事实快照中对应节点的 `source` 里切出来。

## 顶层字段

| 字段 | 说明 |
| --- | --- |
| `schema_version` | 固定为 `1` |
| `id` | 讲义身份，只用字母、数字、`_`、`-`，生成后不再更改。讨论记录靠它和讲义对应。 |
| `output_language` | `zh` 或 `en`，决定页面固定文字的语言 |
| `title`, `business` | 标题，以及这项业务的一句话描述 |
| `scenario` | 贯穿整门课的具体请求 |
| `observable` | 用户会观察到的变化 |
| `invariants` | 必须始终成立的状态或约束（数组） |
| `source` | 源码版本说明，例如仓库和 commit |
| `notice` | 页首说明，写这份讲义已知的局限 |
| `not_covered` | 本讲义不覆盖的范围（数组） |
| `steps` | 步骤数组，顺序就是教学顺序 |

## 步骤字段

| 字段 | 说明 |
| --- | --- |
| `id` | 例如 `s1`。永不更改，也不复用；重排步骤时 id 保持不变。 |
| `short`, `layer` | 目录里的短标题；标签，例如“主路径”“数据结构”“错误路径”“边界”“性能” |
| `node` | 事实里的节点 id，例如 `src/lib.rs::run`。类型节点用 `文件::type::名称`。 |
| `evidence_hash` | 写这一步时节点的哈希，由 `--accept-new` 填入。与当前事实不符时，页面标为“待复核”。 |
| `version` | 例如 `run · 第 2 次（回到第 1 步的函数）` |
| `r` | 当前是第几次讲解，默认 `1` |
| `goal` | 这一步要做成什么 |
| `reasons` | 数组，每项是 `{kind, text, support, limits?}`。`kind` 只能是 `recorded`、`inferred`、`teaching` 之一，`support` 必填。 |
| `method` | 字符串数组 |
| `show` | 显示的行段，如 `[[a, b], …]`，用文件中的绝对行号 |
| `gaps` | 折叠段，每项是 `{lines: [a, b], label, ref?, out?}`。`out: true` 表示与本课程无关，相邻的这类段会合并显示。 |
| `stubs` | 可选。本步只用签名的函数，每项是 `{name, where, ref}` |
| `decisions` | 可选，最多 3 项，每项是 `{line, text, otherwise?}`。`line` 必须是显示出来的行。 |
| `change` 或 `consider` | 可选，二选一。`change` 是 `{before, after}`；`consider` 是字符串数组 |
| `place` | 代码放在哪里，以及需要的 import |
| `earlier` | 旧的讲解，每项是 `{r, reason?, goal, reasons, method, decisions, change/consider}` |

**校验规则**：节点范围内的每一行，必须恰好属于 `show` 或某个 `gaps` 段，不能遗漏，也不能重复。超过 20 行只给出提示，不算失败。

## 讨论记录

讨论记录存放在 `discussion.jsonl`，每行一条，**只追加**。必须用 `review.py discuss` 写入，因为身份字段要从讲义中读取，不能手填。

| 字段 | 说明 |
| --- | --- |
| `lecture` | 讲义 id |
| `step`, `r` | 步骤 id，以及讨论针对的第几次讲解 |
| `evidence_hash` | 记录时该步骤绑定的源码证据 |
| `kind` | `ask` 或 `note` |
| `quote` | 用户所选的原文 |
| `question`, `answer` | 提问的完整问题和完整回答 |
| `text` | 旁注原文 |
| `time` | 记录时间（UTC） |

渲染时：

- 每一步显示自己的“提问 N · 旁注 M”，可以展开查看全部历史；
- 针对旧讲解的讨论会标明“针对第 K 次讲解”；
- 指向已不存在步骤的记录集中放在页面底部，不会丢弃；
- 省略 `--discussion` 时生成公开讲义，不含任何个人讨论。
