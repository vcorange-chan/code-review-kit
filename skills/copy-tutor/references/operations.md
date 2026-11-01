# Tutor 机械操作

下列命令都通过同一 `scripts/review.py` 核心运行。HTML 复制的是发给对话的消息，不要把选文拼成 shell 命令执行。

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
