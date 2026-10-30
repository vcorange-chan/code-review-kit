# AI 调用协议

按代码块顺序解释，略过语法，写清进入数据、执行者、判断条件（两条分支）、结果和下一步。跨文件调用写明由谁调用谁、传什么、返回后从哪继续；不要只列源码链接或用“检查参数”等短句代替解释。AI 处理自然语言、工具处理命令和 AI 补解释要分清。steps 可用 actor/input/result/next；source_index 配合 offset/end_offset 为块级来源定位。用具体请求贯穿复杂流程，不虚构实际运行结果。

使用已安装的 `code-review`，或执行 `python review.py`。Skill 内使用其 `scripts/review.py`。不要为例行 review 重写页面、安装浏览器或建立新的运行实验。

输出语言先按用户明确指定，否则按用户自然语言提示词：中文 zh，英文 en；忽略提示中的代码/路径。所有生成、render、packet 命令传 --output-language zh|en。解释标记 output_language，按语言保存为 explanations.zh.json / explanations.en.json；翻译仅补 prose，保留证据摘要、源码、符号及已有语言版本。needs_translation 表示需要由 AI 补充目标语言解释，工具不会联网翻译。

1. 函数：`code-review function --repo REPO --symbol SYMBOL --file RELATIVE_FILE --out OUTPUT`。
2. 业务：优先复用已有清单，使用 `code-review business --manifest FLOW.json --repo REPO --out OUTPUT`。新流程才定位节点，Rust/Python/Dart 来源优先用 `file + symbol`；其他语言暂作上下文范围。默认 --language auto 按后缀分析，显式 --language rust|python|dart 可缩小工作量；跨语言交接必须由清单声明，不从同名函数猜测。
3. 先看简短结果中的 `html_reused`、`stale_cards` 和 `unresolved_calls`。有效解释直接复用；未解析标准库/外部调用不必逐个追查，除非它影响当前业务问题。
4. 首次解释或证据变化时，只读 `evidence-packet.json` 与 `explanations.seed.json`。证据不足才用 `packet --symbol ... --bytes ...` 补取单节点；不要默认把完整 facts.json 放进上下文。预算按 UTF-8 字节计算，不冒充 token 数。
5. 按用户的阅读语言填写解释 JSON：输入、实现方式、状态、正常输出、错误条件/返回/收尾、降级及返回位置。保留来源引用，未知就明确说明。不要把参数清单或语法注释当作业务解释。
6. 使用 `render --facts ... --explanations ... --html ...` 合成页面。默认内嵌源码可离线定位行号，分享无需本机盘符；只有用户需要时配置外部链接。

旧解释不得自动换绑新摘要。`pin-sources` 只迁移来源清单，不表示旧解释已重新核对。证据匹配和候选唯一均不是运行证明。

当前自动分析支持 Rust、Python、Dart。Python 使用运行环境的标准库 AST；Dart 复用现有 ast-grep，不需要 SDK，也不执行目标代码。动态调用、装饰器、继承、闭包和跨语言桥保留静态分析限制。语法与候选解析留在适配器，入口、解释格式与模板共用。详细边界见 `docs/languages.md`，格式见 Skill 的 `references/flow-format.md` 和 `docs/architecture.md`。
