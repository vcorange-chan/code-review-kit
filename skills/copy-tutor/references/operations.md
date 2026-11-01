# Tutor 机械操作

下列命令都通过同一 `scripts/review.py` 核心运行。HTML 复制的是发给对话的消息，不要把选文拼成 shell 命令执行。

## 单步追加与阅读位置

先创建含 id、schema_version:2、outline 和空 steps 的讲义骨架。每次只写一块 draft.json：

```sh
python scripts/review.py tutor add --lecture lecture.json --facts kit/facts.json --step s1 --replacement draft.json
python scripts/review.py lecture --lecture lecture.json --facts kit/facts.json --discussion discussion.jsonl
```

工具只追加一个未出现的步骤，检查大纲节点与证据，不要求 AI 重新输出整份讲义。旧讲义来源未锁定时，先用 lecture --accept-new 显式绑定；已有证据不匹配不能借此换绑。

页面消息例如 `tutor next lesson-id/s1.r2`。核对所属讲义后：

```sh
python scripts/review.py tutor next --lecture lecture.json --step s1 --expected-revision 2
python scripts/review.py tutor status --lecture lecture.json
python scripts/review.py tutor resume --lecture lecture.json --step s1 --expected-revision 2
```

状态默认存 lecture.state.json，可用 --state 覆盖。next 记录位置，返回下一节点；needs_authoring 表示该步在大纲里但还没有正文。status 只读；resume 用于用户明确选择返回某步。重复 next 不再次推进，过期修订被拒绝。阅读位置不是已读证明或掌握记录。侧问/旁注/重讲都不自动改变主线位置。

## 单步骤材料

```sh
python scripts/review.py tutor packet --lecture lecture.json --facts kit/facts.json --step s3 --discussion discussion.jsonl --out step-packet.json --bytes 12000
```

可加 `--revision 1` 取旧讲解，或 `--explanations kit/explanations.zh.json` 复用有效行为解释。输出含 packet_hash、当前证据状态和 omitted_counts；预算是 UTF-8 字节，不是 token。完整源码文件、无关函数体和全部讨论不放入包。包内容相同不重写。材料不足时提高预算或用 Kit 的 `packet --symbol` 单独取证，不能把遗漏说成代码不存在。

## 自动折叠与签名

步骤只需 show；省略 gaps 时，工具计算补集，优先查找同节点其他步骤的展示范围。可用 defer 提供某些段的去向，用 remainder 明确其余范围。没有依据时保留“待安排”，不自动归为课程外。

可单独预览，输出选区 JSON，不修改讲义：

```sh
python scripts/review.py tutor select --lecture lecture.json --facts kit/facts.json --step s1 --selection selection.json --out ranges.json
```

selection.json 示例：`{"show":[[12,18]],"remainder":{"label":"其他子命令","out":true}}`。真实行号必须来自当前快照。签名引用写 `{"node":"src/lib.rs::accept","ref":"s2"}`；工具查事实，找不到就报错。旧手填签名仅作未核验兼容数据。

## 原子重讲

```sh
python scripts/review.py tutor retell --lecture lecture.json --facts kit/facts.json --step s3 --expected-revision 1 --replacement replacement.json --reason "换一个例子"
```

replacement.json 只写本次变更的讲解字段，允许改变 show。身份字段、历史和源码摘要不可替换。工具保存旧视图、校验新视图、一次写入；校验失败不改原文，旧请求不会重复创建修订。遇到 .lock 表示另一次更新正在进行或上次异常退出，先检查现场，不能自动删除锁或绕过。之后重新运行 lecture 渲染。

## 完整讨论

把选文和全文写入本地 JSON，不经命令行转义：

```json
{"step":"s3","revision":1,"kind":"ask","quote":"完整原文，保留空白和换行","question":"完整问题","answer":"完整回答"}
```

```sh
python scripts/review.py discuss --lecture lecture.json --discussion discussion.jsonl --record-file question.json
```

旁注改用 `kind: note` 和 `text`。讲义、修订及源码身份由工具核对并派生；原记录只追加，用户主动删除除外。重新渲染后在步骤中折叠回看。共享页面省略 --discussion，不携带个人问答。普通 Chat 的问答需用户自行保存，页面不调用模型。
