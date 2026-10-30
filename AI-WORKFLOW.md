# AI 调用协议

使用已安装的 `code-review`，或执行 `python review.py`。Skill 内使用其 `scripts/review.py`。不要为例行 review 重写页面、安装浏览器或建立新的运行实验。

1. 函数：`code-review function --repo REPO --symbol SYMBOL --file RELATIVE_FILE --out OUTPUT`。
2. 业务：优先复用已有清单，使用 `code-review business --manifest FLOW.json --repo REPO --out OUTPUT`。新流程才定位节点，Rust 来源优先用 `file + symbol`；其他语言暂作上下文范围。
3. 先看简短结果中的 `html_reused`、`stale_cards` 和 `unresolved_calls`。有效解释直接复用；未解析标准库/外部调用不必逐个追查，除非它影响当前业务问题。
4. 首次解释或证据变化时，只读 `evidence-packet.json` 与 `explanations.seed.json`。证据不足才用 `packet --symbol ... --bytes ...` 补取单节点；不要默认把完整 facts.json 放进上下文。预算按 UTF-8 字节计算，不冒充 token 数。
5. 按用户的阅读语言填写解释 JSON：输入、实现方式、状态、正常输出、错误条件/返回/收尾、降级及返回位置。保留来源引用，未知就明确说明。不要把参数清单或语法注释当作业务解释。
6. 使用 `render --facts ... --explanations ... --html ...` 合成页面。默认内嵌源码可离线定位行号，分享无需本机盘符；只有用户需要时配置外部链接。

旧解释不得自动换绑新摘要。`pin-sources` 只迁移来源清单，不表示旧解释已重新核对。证据匹配和候选唯一均不是运行证明。

当前自动分析只支持 Rust。新语言的语法与候选解析留在适配器，入口、解释格式与模板继续共用。详细格式见 Skill 的 `references/flow-format.md` 和 `docs/architecture.md`。
