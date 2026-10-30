# Review Kit

先读 DECISIONS.md 和 AI-WORKFLOW.md。当前仅支持 Rust；CLI/AI 共用核心，解释为独立 JSON。未来语言通过适配器添加，不提前实现。

- 使用现成 CLI 生成 review，不重新编写页面。解释存 JSON，自动事实存 facts.json，模板在 reviewkit/templates/。
- 默认不运行目标源码、不建立新媒体模拟实验、不调用模型 API。
- 只向 AI 提供有字节预算的证据包；缓存有效的解释不重新生成。未知分派、宏和图外依赖须保留限制。
- 改核心缓存、选择和证据规则时跑相应 unittest；改页面时跑 JS 语法检查和一次实际交互检查。
- 新语言只加适配器，不在入口、渲染和业务清单各写一套语言判断。
