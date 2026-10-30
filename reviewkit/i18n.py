"""Output language is independent of source language; no network translation."""

import re

EN = {
    "执行者": "Executed by",
    "进入此步": "Input to this block",
    "本步结果": "Block result",
    "接下来": "Next",
    "补充说明与限制": "Notes and limitations",
    "<h3>错误输出</h3>": "<h3>Error output</h3>",
    '<span class="muted">此侧无已解释分支</span>': '<span class="muted">No explained branch on this side</span>',
    "? 传播点 · ": "? propagation sites · ",
    "代码位置与源码": "Code locations and source",
    "以下为语法提取；业务阶段和实际执行顺序仍需解释。": "Syntax extraction follows; business stages and execution order still need explanation.",
    "位置": "Location",
    "其他分支": "Other branches",
    "函数参数": "Function parameters",
    "分支 · ": "Branches · ",
    "功能实现": "Implementation",
    "名称": "Name",
    "含 else": "Has else",
    "无 else": "No else",
    "回到主流程": "Return to main flow",
    "宏（未展开）": "Macros (not expanded)",
    "实现边界": "Limitations",
    "引用上下文 · ": "Source context · ",
    "待补充错误条件与返回值。": "Error conditions and return values need explanation.",
    "接收者（语法）": "Receiver (syntax)",
    "收尾／下一步": "Cleanup / next step",
    "无宏调用。": "No macro invocations.",
    "旧式行号锚点：插入代码后可能定位到别处，建议使用 pin-sources 生成符号锚点。": "Legacy line anchor: inserted code may shift the target. Use pin-sources to create symbol anchors.",
    "旧解释 · 待复核": "Previous explanation · review required",
    "未提取到显式返回或命名错误构造；这不表示不会出错。": "No explicit return or named error construction extracted; this does not mean errors are impossible.",
    "条件": "Condition",
    "正常输出 · ": "Normal output · ",
    "源码": "Source",
    "源码解释 · 证据匹配（未运行验证）": "Source explanation · evidence matches (not runtime verified)",
    "组合调用": "Combinator calls",
    "自动提取 · 业务含义待补充": "Automatic extraction · business explanation needed",
    "自动证据": "Extracted evidence",
    "语法": "Syntax",
    "调用名称": "Call name",
    "调用表达式 · ": "Call expressions · ",
    "输入 · ": "Input · ",
    "返回与错误构造": "Returns and error construction",
    "返回值": "Return value",
    "返回相关类型 · ": "Related return type · ",
    "错误业务解释尚未补充。自动证据中的传播点和错误构造不代表完整错误路径。": "Business error handling has not been explained. Extracted propagation sites and error constructions are not complete error paths.",
    "错误返回与降级": "Errors and recovery",
    "错误／中止": "Error / stop",
    "降级后继续": "Fallback and continue",
    "上下文摘要保留可见导入、相关属性与宏。仍会对可见导入组等情况做保守判断。": "Context hashes retain visible imports, relevant attributes and macros. Visible import groups are still handled conservatively.",
    "代码流程 Review": "Code Flow Review",
    "依据（非类型检查）": "Basis (not type checking)",
    "候选目标": "Candidate targets",
    "函数／业务节点": "Function / business node",
    "宏内提及（未展开）": "Macro mentions (not expanded)",
    "当前源码与事实快照不同，请重新提取：": "Source differs from the facts snapshot. Extract again: ",
    "成功顺序来自业务清单。调用边是语法候选；未解析调用不等于没有调用。默认无运行验证。": "Success order comes from the business manifest. Call edges are syntax candidates; unresolved calls do not mean no calls exist. No runtime verification by default.",
    "按图索骥 · 查看顺序": "Reading order and code map",
    "接收者": "Receiver",
    "未解析原因": "Unresolved reason",
    "未解析调用仍保留在图中。可能是接收者类型未知、外部函数、泛型或变量被遮蔽；不会静默丢弃。": "Unresolved calls stay in the graph. Reasons include unknown receiver types, external functions, generics or shadowed bindings; calls are not silently dropped.",
    "未解析调用／接收者 · ": "Unresolved calls / receivers · ",
    "来源": "Origin",
    "测试": "Test",
    "源码位置": "Source location",
    "生产候选": "Production candidate",
    "生成信息与边界": "Build information and limitations",
    "相关类型与错误枚举": "Related types and error enums",
    "类别": "Kind",
    "解析错误文件：": "Files with parse errors: ",
    "解释状态": "Explanation status",
    "调用": "Call",
    "调用候选 · ": "Call candidates · ",
    "调用关系与未解析项": "Calls and unresolved entries",
    "调用者与宏内提及": "Callers and macro mentions",
    "调用者候选": "Caller candidates",
    "追踪深度：": "Traversal depth: ",
    "顺序": "Order",
    "；节点上限：": "; node limit: ",
    "；超限未纳入：": "; omitted by limit: ",
    '">复制位置</button>': '">Copy location</button>',
    '<section id="source-view" class="inventory" hidden><h2>源码快照</h2><button id="source-back">返回流程</button>': '<section id="source-view" class="inventory" hidden><h2>Source snapshots</h2><button id="source-back">Back to flow</button>',
    "link-mode 仅支持 embedded/relative/local": "link-mode supports embedded/relative/local only",
    "link-template 仅支持 path/absolute_path/line/end_line，无格式或属性表达式": "link-template supports path/absolute_path/line/end_line only, without format or attribute expressions",
    "link-template 使用了不支持的 URL 协议": "link-template uses an unsupported URL scheme",
    "只显示所选证据中的源码；行号为生成时快照。": "Only selected source evidence is shown; line numbers belong to this generated snapshot.",
    "源码和报告不在同一盘符，无法生成相对链接；请使用 embedded 或 link-template": "Source and report are on different drives. Use embedded or link-template instead of relative links.",
    "（此位置未纳入源码快照；可重新提取相关函数。）": "(This location is outside the source snapshot; extract the related function to include it.)",
    "代码流程 REVIEW · 本地生成": "CODE FLOW REVIEW · generated locally",
    "输入 → 功能与实现 → 正常输出": "Input → Function and implementation → Normal output",
    "绿色直线：成功主脉": "Green spine: success path",
    "红色分支：错误／中止": "Red branches: error / stop",
    "金色虚线：降级后回到主流程": "Gold dashed lines: fallback and resume",
    "展开功能实现": "Expand implementations",
    "全部折叠": "Collapse all",
    "跳转卡片": "Jump to card",
    " 张卡片": " cards",
    "如何阅读": "How to read",
    "每张卡片的功能实现、错误返回、输入输出均可展开。点击函数名直接展开代码位置。成功顺序与降级回到的位置由业务清单给出。语法调用关系在页面底部。": "Expand implementation, errors, inputs and outputs on each card. Click a function name to reveal its code locations. Success order and recovery destinations come from the business manifest. Syntax call relations are at the bottom.",
    "“证据匹配”表示解释绑定的源码未发生相关变化，不代表模型解释一定正确，也不代表运行验证通过。“自动提取”保留未知项。": "Evidence matches means no relevant change to the bound source was found. It does not prove the explanation correct or runtime verification successful. Automatic extraction preserves unknowns.",
    "成功主脉、错误分支与降级返回": "Success spine, error branches and recovery paths",
    "源码地图与提取证据": "Code map and extracted evidence",
    "生成时间 ": "Generated ",
    " · 自动提取＋独立解释 JSON＋固定模板 · 默认无运行验证": " · Extracted facts + separate explanation JSON + fixed template · No runtime verification by default",
    "已复制代码位置": "Code location copied",
    "代码位置": "Code location",
    "待补充业务说明": "Business explanation needed",
}


def normalize_language(value):
    aliases = {
        "zh-cn": "zh",
        "中文": "zh",
        "汉语": "zh",
        "chinese": "zh",
        "en-us": "en",
        "en-gb": "en",
        "英文": "en",
        "英语": "en",
        "english": "en",
    }
    value = str(value).strip().lower().replace("_", "-")
    value = aliases.get(value, value)
    if value not in {"zh", "en"}:
        raise ValueError("Output language must be zh or en (Chinese or English).")
    return value


def has_chinese(text):
    return bool(re.search(r"[\u3400-\u9fff]", text or ""))


def resolve_language(request="auto", prompt=None, fallback="zh"):
    if request != "auto":
        return normalize_language(request)
    if prompt and prompt.strip():
        # Common explicit requests; agents resolve more complex instructions before calling CLI.
        mentions = []
        for language, pattern in [
            (
                "en",
                r"(?:用|使用|输出|生成|回复).{0,5}(?:英文|英语)|\b(?:in|use|output|respond)\s+English\b",
            ),
            (
                "zh",
                r"(?:用|使用|输出|生成|回复).{0,5}(?:中文|汉语)|\b(?:in|use|output|respond)\s+Chinese\b",
            ),
        ]:
            mentions.extend((m.start(), language) for m in re.finditer(pattern, prompt, re.I))
        if mentions:
            return max(mentions)[1]
        if has_chinese(prompt):
            return "zh"
        if re.search("[A-Za-z]", prompt):
            return "en"
    return normalize_language(fallback)


def explanation_language(notes):
    return normalize_language((notes or {}).get("output_language", "zh"))


def has_explanations(notes):
    for card in notes.get("cards", {}).values():
        if any(
            card.get(k)
            for k in [
                "input",
                "inputs",
                "normal_output",
                "outputs",
                "steps",
                "errors",
                "branches",
                "notes",
                "scope",
                "state",
            ]
        ):
            return True
        if card.get("title") not in {None, "", "待补充业务说明", "Business explanation needed"}:
            return True
    return False


class Translator:
    def __init__(self, language="zh"):
        self.language = normalize_language(language)

    def __call__(self, text):
        return EN.get(text, text) if self.language == "en" else text

    def template(self, text):
        """Translate only fixed template resources, before inserting any source or prose."""
        if self.language == "zh":
            return text
        pattern = "|".join(re.escape(k) for k in sorted(EN, key=len, reverse=True))
        return re.sub(pattern, lambda m: EN[m.group()], text)
