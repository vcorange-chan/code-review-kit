# 给 AI 的调用协议

用户指定函数时：

1. 使用 `review.cmd function --repo ... --symbol ... --file ... --out ...`。不要默认安装组件、运行程序、编写测试或重新写页面。
2. 命令只输出简短 JSON。先检查 `explained`、`stale_cards`、`index`。解释有效且用户没有要求重新解释时，直接交付 index.html，不读源码包。
3. 首次解释或证据变化时，只读输出目录的 `evidence-packet.json` 和 `explanations.seed.json`。默认包上限 24000 UTF-8 字节，并非实测 token 数。完整 facts.json 留在本地，只有定位问题才读取。
4. 证据缺失时使用 `packet --facts ... --symbol ... --out ... --bytes ...`。如果函数未进入 facts，另运行 function 入口（限制深度/节点数）。不要猜测缺失下游或真实运行行为。
5. 把解释填写到 explanations.json，保留 seed 中的 evidence_hash。输入、实现步骤、正常输出、错误条件/返回/收尾使用中文。说明实现方式与状态，不讲细节语法，不抄 FFmpeg 实际参数。源码位置用 reference 的符号 ID，渲染时自动绑定行号。
6. `render --facts ... --explanations ... --html ...`，不重新编写 HTML。检查返回的 stale_cards 与 source_changed；源文件变化先重新 function/business，旧解释待复核后才能更新 hash。

用户指定业务时：先读取已有业务清单；若没有，定向定位关键节点，参照 `examples/document-pipeline/business.json` 和 Skill 的 references/flow-format.md，再调用 business。一个节点可引用多处源码。成功主脉顺序是业务解释，不能从函数引用图直接推断；降级分支的返回目标使用 resume 边明确指定。

不得自动把旧解释绑定到新 hash 以消除待复核标记。只有核对实际变化后，才从新的 explanations.seed.json 取对应 hash。默认不调用外部模型 API，不发送源码到网络，不建立新运行实验。

JSON 接口由 CLI 与 Python 核心共用；未来的模型/API 入口只生产同一种解释 JSON，不能另实现一套提取和渲染。
