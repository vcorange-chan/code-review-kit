# Code Review Kit

把源码证据和业务解释生成可折叠、可追溯的 HTML 地图。默认不调用模型 API；以缓存、精简证据包和固定模板减少重复工作。

- 小方框：输入与正常输出；大方框：功能、实现、状态与源码链接。
- 绿色直线主脉：成功顺序；红色侧分支：错误／中止；金色虚线：降级并回到指定节点。
- 一个业务节点可关联多个函数及其他语言的源码上下文，不必把业务节点等同于函数。
- 当前自动提取 Rust。未知动态分派、未展开宏、图外依赖保留为限制，不冒充完整程序分析或运行证明。

## 安装

Python 3.10+；支持 Windows、macOS、Linux。原生解析依赖按执行环境安装，不随 Skill 打包。

```sh
git clone https://github.com/vcorange-chan/code-review-kit.git
cd code-review-kit
python -m pip install .
code-review doctor
```

也可使用独立目录安装：Windows 运行 `install.ps1`，或在任意平台运行 `python skills/code-review-kit/scripts/setup.py`，随后使用 `python review.py`。`rg` 可加速文件枚举，未安装时使用 Python 遍历。

Pi：

```sh
pi install git:github.com/vcorange-chan/code-review-kit@v0.2.0
```

使用 `/skill:code-review-kit`。Cowork：从 GitHub Release 下载 `code-review-kit-skill.zip`，在 Customize → Skills 上传；需要启用代码执行。上传包是自包含的，首次提取时在实际执行环境安装依赖。它不假定可访问宿主机的盘符。详见 [安装说明](skills/code-review-kit/references/install.md)。

## 指定函数

```sh
code-review function --repo /path/to/repository --symbol some_function --file src/lib.rs --out ./review
```

打开 `review/index.html`。重名时要求补充文件或完整符号。默认向下追踪 2 层、最多 16 个节点，可调整 `--depth` 和 `--max-nodes`。

## 指定业务

首次由人或 AI 定位节点并保存业务清单，以后复用清单：

```sh
code-review business --manifest examples/document-pipeline/business.json --explanations examples/document-pipeline/explanations.json --out ./review --depth 0 --max-nodes 64
```

公开示例是一个可移植的合成文档流程：14 个阶段，包含 5 个降级返回。它不是来自私有项目的源码快照。清单可使用 `--repo` 覆盖路径，适合另一台机器或 Cowork 挂载目录。

节点关联多个 `sources`；`success` 边连接直线主脉，`resume` 边指定某个降级分支回到哪个节点的 input/output。格式见 [流程说明](skills/code-review-kit/references/flow-format.md)。没有解释时仍可生成基础卡片，未知含义明确标注。

## AI 只补解释，不重写页面

| 输出文件 | 用途 |
| --- | --- |
| index.html | 自包含、离线可看的交互报告 |
| facts.json | 自动事实、源码快照、调用候选与证据摘要；通常留在本地 |
| evidence-packet.json | 供 AI 阅读的小包，默认不超过 24000 UTF-8 字节（不是 token 数） |
| explanations.seed.json | 当前证据对应的解释骨架 |
| explanations.json | 独立的中文业务解释；重建时保留 |
| build-stats.json | 耗时、缓存复用、待复核卡片等简短结果 |

```sh
code-review render --facts review/facts.json --explanations review/explanations.json --html review/index.html
code-review packet --facts review/facts.json --symbol some_function --out packet.json --bytes 10000
```

已绑定的解释可继续复用。相关函数、来源或图结构改变时标为待复核；纯行号移动不影响普通函数解释。不能为了消除提示直接给旧解释换新摘要。CLI 和所有 AI 入口调用同一核心与模板。

源码、解释、清单和模板均未变时直接复用 HTML，不把完整报告再交给模型。其他时候按文件摘要复用语法索引。源码只读；默认不执行目标项目，不创建运行实验。

## 边界与开发

解析为有范围限制的语法候选分析，宏、trait/泛型、运行时路由和条件编译未做完整求解。非 Rust 引用作为上下文保留，不代表支持其自动调用分析。模型解释也不因摘要匹配就自动正确。

`reviewkit/rust.py` 提供语言适配器；`reviewkit/business.py` 处理多来源业务视图；`reviewkit/templates/` 是唯一模板源。模型/API 入口只读写同一种解释 JSON。

```sh
python -m unittest discover -s tests -v
node --check reviewkit/templates/review.js
python scripts/build_dist.py
python scripts/smoke_skill.py
```

CI 在 Windows/macOS/Linux 和 Python 3.10/3.12 上测试工具及实际 ZIP 安装路径，并检查 Pi 包安装。Skill 可被发现与可执行，不等于在某个用户的 Cowork 账号里已完成实际任务。

MIT License。发布内容不含本地缓存、原生依赖、私有项目的流程数据或生成报告。
