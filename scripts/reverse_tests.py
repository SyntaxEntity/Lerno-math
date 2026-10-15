#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验器的反向测试：**每条规则都故意造一个反例，确认它真的会报错**。

为什么必须做
------------
不做反向测试的校验等于自我安慰。408 项目里就吃过亏：一条渲染校验因为判据写错
（检查标记「是否出现」而非「是否位于段首」），一直报 0 条、完全失效，直到造了
反例才发现。本脚本把这件事自动化：对每条规则注入一个最小反例，跑校验器，
断言「出现了该规则的错误」，然后恢复现场。

用法
----
    python3 scripts/reverse_tests.py            # 跑全部反向测试
    python3 scripts/reverse_tests.py -v         # 打印每条反例的细节

设计
----
每个用例是 `Case(code, 名字, 目标文件, 变换函数, 期望出现的错误码)`。
- 变换函数接收原文、返回改坏后的文本；用「读原文 → 写坏文 → 跑校验 → 恢复」保证
  无论成败原始内容都会还原。
- 校验器以子进程运行（`--no-mermaid` 加速），只关心是否出现期望的错误码与关键字。
- 任何一条用例没有触发预期错误，就计为**失败**——这才是「校验器不是摆设」的证据。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARTS = os.path.join(ROOT, "parts")
CONTENT = os.path.join(ROOT, "数学二")
# 必须用**带 markdown 等依赖的解释器**跑校验器：否则 F14 会静默跳过，
# 反向测试就会把「依赖缺失」误判成「规则失效」。优先用仓库自带 venv。
_VENV = os.path.join(ROOT, ".tools", "venv", "bin", "python")
PY = _VENV if os.path.exists(_VENV) else sys.executable
VALIDATE = os.path.join(HERE, "validate.py")

CASES = []


def case(code, name, target, mutate, expect_kw=None, mode="parts", mermaid=False):
    """mermaid=True 的用例会**不跳过**真实解析器跑校验（用于验 F3 的解析器层）。

    其余用例一律带 `--no-mermaid`：不是为了省事，而是因为若反例破坏了围栏闭合，
    解析器层的报错会**盖过**被测规则本来要报的那个错，反而看不出规则是否生效。
    """
    CASES.append((code, name, target, mutate, expect_kw, mode, mermaid))


# --- 内容源（parts）用例 -----------------------------------------------------
G01 = os.path.join(PARTS, "gaoshu", "01-函数极限与连续.md")
G05 = os.path.join(PARTS, "gaoshu", "05-定积分与反常积分.md")
X02 = os.path.join(PARTS, "xiandai", "02-矩阵.md")

# --- 成品（数学二/）用例 ------------------------------------------------------
D01 = os.path.join(CONTENT, "高等数学", "01-函数极限与连续.md")
D05 = os.path.join(CONTENT, "高等数学", "05-定积分与反常积分.md")
D01H = os.path.join(CONTENT, "高等数学", "01-函数极限与连续.html")
D05H = os.path.join(CONTENT, "高等数学", "05-定积分与反常积分.html")
G08 = os.path.join(PARTS, "gaoshu", "08-数二高数综合与证明专题.md")
HOMEH = os.path.join(CONTENT, "index.html")      # 全科单页合集（= 站点首页）
SITEJS = os.path.join(CONTENT, "assets", "site.js")
SITECSS = os.path.join(CONTENT, "assets", "site.css")
READMEmd = os.path.join(CONTENT, "README.md")          # 生成物，F12 比对的两端之一
VALIDATEpy = os.path.join(HERE, "validate.py")          # F26 读它的规则集合
SELFpy = os.path.join(HERE, "reverse_tests.py")         # F26 读它的覆盖集合
AGENTSmd = os.path.join(ROOT, "AGENTS.md")              # F26 的 H4 会扫它

FENCE = "```"
FIELD = "**核心讲解**"
FREQ = "**考频统计**"


def _del_blank_before_field(t):
    return re.sub(r"\n\n" + re.escape(FIELD), "\n" + FIELD, t, count=1)


def _rename_section(t):
    return t.replace("# 核心讲解", "# 核心说明", 1)


def _drop_errors_section(t):
    return re.sub(r"# 易错点.*?(?=# 真题示例)", "", t, flags=re.S)


def _swap_sections(t):
    return (t.replace("# 关键结论速记", "# @@TMP@@", 1)
             .replace("# 示意图", "# 关键结论速记", 1)
             .replace("# @@TMP@@", "# 示意图", 1))


def _insert_todo(t):
    return t.replace("函数", "TODO 函数", 1)


def _fullwidth_in_ascii(t):
    return re.sub(r"(" + FENCE + r"text\n)", r"\1　| 全角\n", t, count=1)


def _year_out_of_range(t):
    return re.sub(r"\*\*20\d\d 年", "**2088 年", t, count=1)


def _bad_citation_title(t):
    return re.sub(r"\*\*20\d\d 年[^\n]*\*\*", "**某年某题**", t, count=1)


def _one_paragraph(t):
    return re.sub(r"(# 核心讲解\n)(.*?)(\n# 关键结论速记)",
                  lambda m: m.group(1) + m.group(2).replace("\n\n", "\n") + m.group(3),
                  t, flags=re.S)


def _core_no_modules(t):
    """核心讲解里把 `## 【模块】` 标题全部删掉 -> 退回"一大段文字"。"""
    return re.sub(r"(?m)^##\s*【[^】]+】\s*$", "", t)


def _core_no_display_math(t):
    """删掉核心讲解里**所有**独立成行的 $$ 公式块。

    两种写法都要覆盖：单行 `$$ 公式 $$` 与跨行 `$$\n公式\n$$`。
    早期实现只处理跨行式，遇到 05 章改用单行式后删除不彻底，
    于是反例没触发 F9，被误判成"校验器失效"。
    """
    out = re.sub(r"(?m)^\s*\$\$.+?\$\$\s*$", "", t)      # 单行式
    out = re.sub(r"(?ms)^\s*\$\$\s*$.*?^\s*\$\$\s*$", "", out)  # 跨行式
    return out


def _core_no_warn(t):
    """核心讲解里删掉全部 ⚠️ 提醒。"""
    return re.sub(r"(?m)^>\s*⚠️.*$", "", t)


def _core_no_lists(t):
    """核心讲解里删掉所有列表条目。"""
    head = t.find("# 核心讲解")
    tail = t.find("# 关键结论速记")
    if head == -1 or tail == -1:
        return t
    blk = re.sub(r"(?m)^\s*(?:[-*]|\d+\.)\s+\S.*$", "", t[head:tail])
    return t[:head] + blk + t[tail:]


def _core_no_table(t):
    """核心讲解里删掉全部表格行。"""
    return re.sub(r"(?m)^\|.*\|\s*$", "", t)


def _core_broken_table(t):
    """表格单元格里放裸 `|`（如 $|f''(x)|$），把列数撑乱。"""
    return t.replace("| --- | --- | --- |", "| --- | --- | --- |", 1).replace(
        "| $f'+f=0$", "| $|f'(x)|$ 型", 1)


def _one_bullet_errors(t):
    return re.sub(r"(# 易错点\n)(.*?)(\n# 真题示例)",
                  lambda m: m.group(1) + m.group(2).strip().split("\n")[0] + "\n" + m.group(3),
                  t, flags=re.S)


def _two_bullets_key(t):
    return re.sub(r"(# 关键结论速记\n)(.*?)(\n# 示意图)",
                  lambda m: m.group(1) + "\n".join(m.group(2).strip().split("\n")[:2])
                  + "\n" + m.group(3), t, flags=re.S)


def _stats_in_source(t):
    return t.replace("# 核心讲解", "# 核心讲解\n\n考察次数 7 次，分数占比约 15%。", 1)


def _bad_mermaid_syntax(t):
    """把 mermaid 节点标签里的圆括号**去掉引号** —— 官方解析器实测直接 parse error。

    这是内容里最容易犯、而正则静态扫描**查不出来**的错：看图时是一整块空白，
    只有在真实解析器下才会暴露。所以这条用例必须关掉 `--no-mermaid`。
    """
    return t.replace('B{"区间是否为无穷区间"}', "B{区间是否为无穷区间(含瑕点)}", 1)


def _drop_mermaid(t):
    return re.sub(FENCE + r"mermaid.*?" + FENCE, "", t, flags=re.S)


def _abs_path(t):
    return t.replace("assets/", "/home/user/assets/", 1)


def _unclosed_fence(t):
    return re.sub(r"(" + FENCE + r"mermaid\n.*?)\n" + FENCE, r"\1", t, count=1, flags=re.S)


def _odd_dollar_parts(t):
    return t.replace("# 核心讲解\n\n", "# 核心讲解\n\n这里少了一个美元符号 $x^2\n\n", 1)


def _backtick_latex(t):
    """反引号里包 LaTeX —— KaTeX 不渲染，且 _ ^ 会被 Markdown 吃掉。"""
    return t.replace("# 关键结论速记\n\n", "# 关键结论速记\n\n- `\\frac{dy}{dx}=f(x)` —— 测试用。\n\n", 1)


def _bare_latex(t):
    """数学模式外的裸 LaTeX。"""
    return t.replace("# 关键结论速记\n\n", "# 关键结论速记\n\n- 裸公式 \\frac{dy}{dx}=f(x) 未加美元符号。\n\n", 1)


def _html_placeholder(t):
    """HTML 里残留公式占位符（还原失败）。

    直接往页面开头插一个占位符即可，不依赖正文的具体结构。
    早期版本依赖 `<p id="sec-core">`、后来又依赖 `<div id="wrap">`，两次都因为
    外壳改版而**悄悄变成空操作**（反向测试会报"反例未改变内容"）。现在挂在
    P2 契约的 `.site-body` 上——它是契约类名，不会随排版改版消失。
    """
    anchor = '<div class="site-body">'
    assert anchor in t, "锚点 %s 不在页面里：请同步更新这条反例" % anchor
    return t.replace(anchor, anchor + "<p>@@MATH7@@</p>", 1)


def _html_em_in_math(t):
    """公式区间里出现 <em>（* 被 Markdown 吃掉）。"""
    return t.replace("<p>", "<p>$A^{<em>}=A^{</em>}A$ ", 1)


def _html_bad_nav(t):
    """上一章链接指向不存在的文件（P2 起翻页类名是 .cn-prev / .cn-next）。

    目标必须是**中间章**：第一章的上一章是 `.cn-prev off` + `href="#"` 占位，
    对它做替换等于没改，反例会失效（实测被抓出来过）。
    """
    old = '<a class="cn-prev" href="'
    assert old in t, "目标页没有可用的上一章链接，请换一个中间章做反例"
    return t.replace(old, '<a class="cn-prev" href="nope-', 1)


def _html_drop_display_math(t):
    """把页面里的 `$$` 定界符删掉（模拟公式保护/还原失效）。

    这是 F20 在 P2 修掉的那个**假通过**：旧判据只要求"正文里出现过 $$"，
    而当时内联的 KaTeX 配置里正好有 `'$$'` 字面量，于是永远满足。
    现在判据改成"与内容源等量"，删掉定界符必须报错。
    """
    return t.replace("$$", "$")


def _html_drop_topbar(t):
    """删掉顶栏（F22 形式层：外壳四件之一）。"""
    return re.sub(r'<header class="site-topbar">.*?</header>', "", t, count=1, flags=re.S)


def _html_drop_footer(t):
    """删掉页脚。"""
    return re.sub(r'<footer class="site-footer">.*?</footer>', "", t, count=1, flags=re.S)


def _html_break_site_js(t):
    """把 site.js 的深色类名改错 —— F22 的**行为层**必须因此报错。

    这条反例验的是"第二层校验真的在跑"：形式层（HTML 里类名齐全）看不出任何问题，
    只有把脚本放进 jsdom 真跑一遍才会暴露。
    """
    return t.replace("root.classList.toggle('dark', t === 'dark')",
                     "root.classList.toggle('darkX', t === 'dark')", 1)


def _html_inline_style(t):
    """把外置样式内联回去（F23：P2 的主要收益不能被悄悄退回）。"""
    return t.replace("</head>", "<style>body{color:#000}</style></head>", 1)


def _html_break_css_ref(t):
    """把 site.css 的引用改坏（F23）。"""
    return t.replace("assets/site.css", "assets/nope.css", 1)


def _home_drop_card(t):
    """首页删掉一张科目卡片（F22：卡片数必须 = 科目数）。"""
    return re.sub(r'<a class="hs-card".*?</a>', "", t, count=1, flags=re.S)



def _bold_unclosable(t):
    """往内容源塞一条「**…。**汉字」的加粗：按 CommonMark 侧翼规则无法闭合，
    渲染后会露出字面 `**`（F24；用户实拍截图发现的那类缺陷）。"""
    return t.replace("# 易错点\n\n",
                     "# 易错点\n\n- **错在条件不足就下结论。**正确做法是先核对条件。\n", 1)


def _merge_solution_paras(t):
    """删掉「真题示例」解析里的空 `>` 行：渲染时所有步骤会并成**一个**段落（F25）。"""
    head, sep, tail = t.partition("# 真题示例")
    if not sep:
        return t
    return head + sep + re.sub(r"(?m)^>\s*$\n", "", tail)


def _html_leftover_stars(t):
    """成品 HTML 正文里出现字面 `**`（F24）。"""
    return t.replace("<main>", "<main><p>**字面星号**汉字</p>", 1)


def _html_cram_para(t):
    """往「真题示例」的解析里塞一个含 5 个行内公式的段落（F25）。"""
    return re.sub(r'(<section class="sec sec-real".*?<blockquote>)',
                  lambda m: m.group(1) + "<p>$a$ $b$ $c$ $d$ $e$</p>",
                  t, count=1, flags=re.S)



def _drop_solution_quote(t):
    """删掉真题示例里的整个 `> 解析` 引用块（F25 必须报"没有解析引用块"）。

    这条反例防的是**静默通过**：排版判据是逐段检查的，段落列表为空时它什么都不会报。
    """
    head, sep, tail = t.partition("# 真题示例")
    if not sep:
        return t
    return head + sep + re.sub(r"(?m)^>.*\n?", "", tail)



def _html_cram_li(t):
    """把 5 个行内公式塞进一个 `<ol><li>` 段落（F25 的 HTML 层必须也看列表）。

    这条反例针对的是"只查 `<p>`"的盲区：步骤被渲染成列表项时，
    段落内容不在 `<p>` 里，规则会看不到它。
    """
    return re.sub(r'(<section class="sec sec-real".*?<blockquote>)',
                  lambda m: m.group(1) + "<ol><li>$a$ $b$ $c$ $d$ $e$</li></ol>",
                  t, count=1, flags=re.S)



def _merge_step_numbers(t):
    """在解析的首个步骤段里再塞一个编号 —— 制造「1. … 2. … 挤在同一段」。

    这是用户实拍指出的写法（中文里编号前面是「。」不是空格，所以判据的正则
    不能写成 `(?:^|\\s)\\d+\\.`——第一版就因此漏判过）。
    """
    head, sep, tail = t.partition("# 真题示例")
    if not sep:
        return t
    return head + sep + re.sub(r"(?m)^(> \d+\.\s.*)$", r"\1 2. 另一步。", tail, count=1)



def _delete_file(_t):
    """返回 None：让 harness 把目标文件删掉 —— 用来触发 F0（结构完整性：文件缺失）。

    F0 查的是"该有的东西在不在"，内容层面的改写触发不了它，所以需要一个
    "文件不存在"的反例类型。harness 的 finally 会把原内容写回，文件必然还原。
    """
    return None


def _add_fake_orig_row(t):
    """在 README 的原题清单里加一行**正文并不存在**的原题 —— 触发 F12 的双向比对。

    （F12 是"README 声明清单 ↔ 正文标注"两个方向都要一致，这条走"声明多了"的方向。）
    """
    marker = "| --- | --- | --- | --- |"
    assert marker in t, "README 里没找到原题清单表头，反例需要更新"
    return t.replace(marker,
                     marker + "\n| `2024` | 第 `99` 题 | 选择题，5 分 | 函数、极限与连续 |", 1)


def _inject_fake_rule(t):
    """往 validate.py 里塞一条"永远为真、因而永远不会报错"的假规则 —— 触发 F26 的 H2。

    P4 验收项 2：注入假规则后元校验必须报 error，才说明元校验本身有效。
    """
    return t.replace("errors, warnings, stats = [], [], defaultdict(int)",
                     'errors, warnings, stats = [], [], defaultdict(int)\n'
                     '_FAKE_RULE = "F99"     # 假规则：声明了却没有任何反向测试覆盖',
                     1)


def _drop_one_reverse_case(t):
    """删掉某条规则的**全部**反向测试用例 —— 触发 F26 的 H2（覆盖集合 ≠ 规则集合）。

    第一版删的是 F1 的一条 case，结果用例没触发：**F1 有三条反例，删一条不影响覆盖**。
    所以要挑一条"只有单条反例"的规则，并断言确实只删到一条——
    将来若给它加了第二条反例，这里会立刻报错提醒换规则。
    """
    out, n = re.subn(r'(?m)^case\("F12",.*?\n', "", t)
    assert n == 1, "F12 的反例应恰好 1 条（现为 %d 条）：请改用一个只有单条反例的规则" % n
    return out


def _zero_one_scanned_stat(t):
    """把某个扫描型规则的受检对象数强行改成 0 —— 触发 F26 的 H3（空转通过）。

    P4 验收项 4：让受检数变 0 必须报错。这里用白盒方式直接改统计量，
    因为"让真实环境恰好扫到 0 个对象"没法在一条反例里稳定复现。
    """
    old = 'stats["assets"] = len(have)'
    assert old in t
    return t.replace(old, old + '\n    stats["assets"] = 0     # 反例：制造空转', 1)


def _hardcode_rule_range(t):
    """在文档里硬编码一个 F 范围 —— 触发 F26 的 H4（范围漂移）。"""
    return t + "\n<!-- 校验规则 F1—F99 -->\n"



def _downgrade_rule_to_warn(t):
    """把一条规则的 err(...) 降级成 warn(...) —— 门禁从此拦不住它。

    这是**实测出来的假通过**：旧判据只找 `[Fxx]` 字样，分不清 error 与 warning，
    所以把 F24 降级后 61 条用例照样全绿、发布照走。现在两层都会拦：
    动态层（本 harness 只认新出现的 **error**）、静态层（F26 用 AST 检查每条规则
    是否存在 err( 路径）。
    """
    old = 'err("数学二/README.md", 0, "F12"'
    assert old in t, "锚点没找到：F12 的 err( 调用变了"
    # 必须**全部**替换：F12 有多处 err(，只改一处时 AST 仍能看到 err 路径，
    # 判据就不会报错（第一版正是只替换了第一处，用例没触发）。
    out = t.replace(old, 'warn("数学二/README.md", 0, "F12"')
    assert out != t
    return out



def _break_style_token(t):
    """改掉 site.css 里的一个配色 token 值 —— 触发 F27（A 暖纸表是硬契约）。"""
    old = "--bg:#f5f2ea"
    assert old in t, "锚点没找到：site.css 的 --bg 亮色值变了"
    return t.replace(old, "--bg:#f7f7f5", 1)



def _mw_magic_calc(t):
    """把正文列的 max-width 改回带魔法数的 calc 形式 —— 触发 F27 的第二条判据。"""
    old = ".inner{max-width:var(--mw);"
    assert old in t, "锚点没找到：site.css 里 .inner 的 max-width 写法变了"
    return t.replace(old, ".inner{max-width:calc(var(--mw) + 92px);", 1)


def _dup_heading(t):
    """在**同一章节区块内**重复一个标题（F21 的判据范围）。

    早期版本把重复标题插在正文最前面，既不在任何章节区块内、文本也不是已有的，
    两种情况下规则都不该报错，却被当成"校验器失效"。现在按判据范围造例。
    """
    marker = '<section class="sec sec-core" id="sec-core">'
    if marker not in t:
        return t
    dup = ('<section class="sec sec-core"><div class="sec-h">'
           '<h2 class="tt">核心讲解</h2></div><div class="box"></div></section>')
    return t.replace(marker, marker + dup, 1)


def _two_h1(t):
    """正文里出现第二个 h1。"""
    return t.replace("<main>", "<main><h1>重复的一级标题</h1>", 1)


def _empty_section(t):
    """把某个字段区块的内容清空（模拟"内容被切到区块之外"）。"""
    return re.sub(r'(<section class="sec sec-freq"[^>]*>.*?<div class="box">).*?(</div>)',
                  r"\1\2", t, count=1, flags=re.S)


def _dup_field_label(t):
    """区块内又重复一遍字段名。"""
    return t.replace('<section class="sec sec-freq" id="sec-freq">'
                     '<div class="sec-h">',
                     '<section class="sec sec-freq" id="sec-freq">'
                     '<div class="sec-h">', 1).replace(
        '<div class="box">', '<div class="box"><p><strong>考频统计</strong>：重复</p>', 1)


def _bad_image_ref(t):
    return t.replace("assets/gaoshu-01-fig1.png", "assets/gaoshu-01-figX.png", 1)


def _dbl_blank(t):
    return t.replace("\n\n" + FIELD, "\n\n\n" + FIELD, 1)


def _fake_freq_number(t):
    return re.sub(r"考察次数 \d+ 次", "考察次数 99 次", t, count=1)


def _drop_hot(t):
    return t.replace(" [高频]\n", "\n", 1)


def _bad_doc_link(t):
    return t + "\n\n[不存在的章节](数学二/高等数学/99-不存在.md)\n"


def _join_field(t):
    """真正的模板粘连：删掉两个**字段标签之间**的空行，让 核心讲解 与
    关键结论速记 落进同一个 <p>。仅去掉标签后空行只会让标签与首段合并，
    那仍然是合法的一段（不算错误）。"""
    return re.sub(r"(" + re.escape(FIELD) + "：\n\n.*?)\n\n"
                  r"(?=\*\*关键结论速记\*\*)", r"\1\n", t, count=1, flags=re.S)


def _odd_dollar_full(t):
    """把行间公式的**闭合** `$$` 改成单个 `$`，使全文 `$$` 个数变成奇数。

    只替换行尾的定界符（`$$` 后紧跟换行），避免误改公式正文里的内容；
    若替换后个数仍为偶数说明没命中，直接返回原文让用例报「跳过」而不是误判。
    """
    out = re.sub(r"\$\$(\n)", r"$\1", t, count=1)
    return out if out.count("$$") % 2 == 1 else t


case("F1", "字段改名（核心讲解 → 核心说明）", G01, _rename_section)
case("F1", "删除「易错点」整段", G01, _drop_errors_section)
case("F1", "调换段落顺序（速记与示意图互换）", G01, _swap_sections)
case("F4", "插入占位符 TODO", G01, _insert_todo)
case("F5", "ASCII 图里混入全角字符", X02, _fullwidth_in_ascii)
case("F6", "真题年份越界（2088 年）", G01, _year_out_of_range)
case("F6", "真题标题不合规范（冒充实题）", G01, _bad_citation_title)
case("F9", "核心讲解缺 【模块】 标题（退回一段文字）", G05, _core_no_modules)
case("F9", "核心讲解缺独立成行的 $$ 公式块", G05, _core_no_display_math)
case("F9", "核心讲解缺 ⚠️ 提醒", G05, _core_no_warn)
case("F9", "核心讲解缺列表拆解", G05, _core_no_lists)
case("F9", "核心讲解缺对比表格", G05, _core_no_table)
case("F9", "对比表格列数被裸 | 撑乱", G08, _core_broken_table)
case("F10", "易错点只剩 1 条", G01, _one_bullet_errors)
case("F11", "速记只剩 2 条", G01, _two_bullets_key)
case("F2", "内容源自带考频数字", G01, _stats_in_source)
case("F8", "删掉全部 mermaid 代码块", G05, _drop_mermaid)
case("F16", "写入绝对路径 /home/user/", G01, _abs_path)
case("F3", "代码围栏不闭合", G05, _unclosed_fence)
case("F17", "行内公式 $ 不成对（内容源）", G01, _odd_dollar_parts)
case("F18", "内容源引用不存在的图片", G01, _bad_image_ref)
case("F19", "反引号包住 LaTeX（不渲染且吃掉 _ ^）", G01, _backtick_latex)
case("F19", "数学模式外的裸 LaTeX", G01, _bare_latex)

case("F13", "字段与上一段只隔单换行（渲染粘连）", D01, _del_blank_before_field, mode="full")
case("F13", "连续空行", D01, _dbl_blank, mode="full")
case("F2", "手改考频统计数字（与 meta.py 不符）", D01, _fake_freq_number, mode="full")
case("F7", "高频标记与 meta.py 不一致", D01, _drop_hot, mode="full")
case("F15", "文档链接指向不存在的文件", D01, _bad_doc_link, mode="full")
case("F16", "正文出现绝对路径", D01, _abs_path, mode="full")
case("F14", "字段标签被上一段吞并（模板粘连）", D01, _join_field, mode="full")
case("F18", "成品 md 引用不存在的图片", D01, _bad_image_ref, mode="full")
case("F20", "HTML 残留公式占位符", D01H, _html_placeholder, mode="full")
case("F20", "公式区间被 <em> 污染", D01H, _html_em_in_math, mode="full")
case("F20", "上一章链接不可达", D05H, _html_bad_nav, mode="full")
case("F20", "字段区块内容为空（内容被切到区块外）", D01H, _empty_section, mode="full")
case("F20", "区块内重复字段名", D01H, _dup_field_label, mode="full")
case("F21", "正文标题重复", D01H, _dup_heading, mode="full")
case("F21", "正文出现第二个 h1", D01H, _two_h1, mode="full")
case("F17", "行间公式 $ 不成对（成品）", D05, _odd_dollar_full, mode="full")
case("F20", "公式块 $$ 定界符丢失（与内容源不等量）", D01H, _html_drop_display_math, mode="full")
case("F22", "删掉顶栏（外壳形式层）", D01H, _html_drop_topbar, mode="full")
case("F22", "删掉页脚（外壳形式层）", D01H, _html_drop_footer, mode="full")
case("F22", "首页少一张科目卡片", HOMEH, _home_drop_card, mode="full")
case("F24", "内容源出现无法闭合的加粗（**…。**汉字）", G01, _bold_unclosable)
case("F24", "成品 HTML 正文残留字面 **", D01H, _html_leftover_stars, mode="full")
case("F25", "解析里的空 > 行被删（整段并成一段）", G05, _merge_solution_paras)
case("F25", "解析里塞进 5 个行内公式的段落", D01H, _html_cram_para, mode="full")
case("F25", "真题示例缺 `> 解析` 引用块（防静默通过）", G01, _drop_solution_quote)
case("F25", "解析的列表项里塞 5 个行内公式（HTML 层盲区）", D01H, _html_cram_li, mode="full")
case("F25", "两个步骤编号挤在同一段（1. … 2. …）", G05, _merge_step_numbers)
case("F0", "内容源缺少一个知识点文件（结构完整性）", G01, _delete_file)
case("F12", "README 声明了一道正文并不存在的原题", READMEmd, _add_fake_orig_row, mode="full")
case("F26", "注入一条永不为真的假规则（H2 元校验必须抓到）", VALIDATEpy, _inject_fake_rule, mode="full")
case("F26", "删掉一条反向测试用例（H2 覆盖集合不再相等）", SELFpy, _drop_one_reverse_case, mode="full")
case("F26", "把某个扫描型规则的受检数改成 0（H3 空转通过）", VALIDATEpy, _zero_one_scanned_stat, mode="full")
case("F26", "在文档里硬编码 F 范围（H4 漂移）", AGENTSmd, _hardcode_rule_range, mode="full")
case("F26", "把一条规则的 err 降级成 warn（只 warn 拦不住发布）", VALIDATEpy, _downgrade_rule_to_warn, mode="full")
case("F27", "把 site.css 的 --bg 改成表外的色值", SITECSS, _break_style_token)
case("F27", "正文列改回 calc(var(--mw) + 92px)（契约禁止魔法数）", SITECSS, _mw_magic_calc)
case("F22", "site.js 深色类名写错（行为层必须抓到）", SITEJS, _html_break_site_js, mode="full")
case("F23", "把外置样式内联回页面", D01H, _html_inline_style, mode="full")
case("F23", "样式表引用不可达", D01H, _html_break_css_ref, mode="full")
case("F3", "mermaid 标签含圆括号未加引号（真实解析器层·成品）", D05, _bad_mermaid_syntax,
     mode="full", mermaid=True)
case("F3", "mermaid 标签含圆括号未加引号（真实解析器层·内容源）", G05, _bad_mermaid_syntax,
     mode="parts", mermaid=True)


_BASELINE = {}
ERROR_LINE = re.compile(r"\[F\d+\]")


def baseline_errors(mode, allow_mermaid):
    """未注入反例时，该模式下已有的报错行集合。

    **为什么必须做基线差分**：早期判据是"跑完校验后输出里出现 `[Fxx]`"。
    一旦这条规则本来就有既存报错（比如正在返工的文件），反例即使完全没生效，
    用例也会"通过"——这正是"校验器是摆设"的另一种形态。
    现在只认**注入之后新出现**的报错行，用例就不可能蒙对。
    """
    key = (mode, allow_mermaid)
    if key not in _BASELINE:
        errs, _warns, _rc = run_validate(mode, allow_mermaid=allow_mermaid)
        _BASELINE[key] = {e.strip() for e in errs}
        print("  · 基线（%s%s）：已有 %d 条**错误**（warning 不计）"
              % (mode, "，含真实解析器" if allow_mermaid else "", len(_BASELINE[key])))
    return _BASELINE[key]


def run_validate(mode, allow_mermaid=False):
    """跑一次校验器，返回 (errors, warnings, 退出码)。

    **必须拿结构化的 errors 而不是"输出里有没有 `[Fxx]` 字样"**：
    后者分不清 error 与 warning，而把一条规则从 error 降级成 warn 就等于门禁不再拦它——
    实测过：把 F24 的 err 改成 warn，正则判据下 61 条用例照样全绿。
    这就是 P4 说的「假通过」，只不过这次假通过的是反向测试自己。
    """
    cmd = [PY, VALIDATE, "--json"] + (["--parts"] if mode == "parts" else [])
    if not allow_mermaid:
        cmd.append("--no-mermaid")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    try:
        data = json.loads(r.stdout)
    except Exception as e:                                   # noqa: BLE001
        # 两种情况都可能：校验器崩了，或**本脚本自己**出错（例如漏 import json）。
        # 把异常一并报出来，否则"harness 自身有 bug"会被伪装成"校验器没输出"。
        return ({"读不出校验器输出（%s: %s）：%s"
                 % (type(e).__name__, e, (r.stdout[-200:] + r.stderr[-200:]))}, set(),
                r.returncode)
    return set(data.get("errors", [])), set(data.get("warnings", [])), r.returncode


def main():
    verbose = "-v" in sys.argv
    print("=" * 78)
    print("校验器反向测试：每条规则注入一个反例，确认它真的会报错")
    print("=" * 78)
    passed = failed = 0
    for code, name, target, mutate, _kw, mode, mermaid in CASES:
        rel = os.path.relpath(target, ROOT)
        if not os.path.exists(target):
            print("  ? %-5s %-42s 跳过（目标文件不存在：%s）" % (code, name, rel))
            failed += 1
            continue
        original = open(target, encoding="utf-8").read()
        try:
            # ⚠️ 基线必须在**注入之前**取：早期版本写在注入之后，
            # 于是基线里已经含了本用例注入的那条报错，差集恒为空、
            # 所有用例都会显示"未报错"。顺序错了，整个判据就失效。
            base = baseline_errors(mode, mermaid)
            try:
                broken = mutate(original)
            except Exception as e:                           # noqa: BLE001
                print("  ✗ %-5s %-42s 反例函数报错：%s" % (code, name, e))
                failed += 1
                continue
            if broken is None:
                # None = 这个反例要求"目标文件不存在"（F0 那类查存在性的规则）。
                # finally 会把原内容写回，文件照样还原。
                os.remove(target)
            elif broken == original:
                print("  ? %-5s %-42s 跳过（反例未改变内容，用例失效）" % (code, name))
                failed += 1
                continue
            else:
                with open(target, "w", encoding="utf-8") as f:
                    f.write(broken)
            errs, warns, rc = run_validate(mode, allow_mermaid=mermaid)
            fresh = {e.strip() for e in errs} - base
            hit = any(("[%s]" % code) in ln for ln in fresh)
            only_warn = (not hit) and any(
                ("[%s]" % code) in w for w in warns)
            if hit and rc == 0:
                # 报了 error 但退出码是 0 —— 报告与退出码对不上，门禁就拦不住
                hit = False
                print("  ✗ %-5s %-42s 报了 error 但退出码为 0（门禁不会中止！）"
                      % (code, name))
                failed += 1
                continue
            if hit:
                passed += 1
                print("  ✓ %-5s %-42s 已报错" % (code, name))
                if verbose:
                    for ln in sorted(fresh):
                        if "[%s]" % code in ln:
                            print("        " + ln.strip()[:140])
                            break
            else:
                failed += 1
                if only_warn:
                    print("  ✗ %-5s %-42s **只报了 warning（门禁不会失败，属假通过！）**"
                          % (code, name))
                else:
                    print("  ✗ %-5s %-42s **未报错（校验器失效！）**" % (code, name))
        finally:
            with open(target, "w", encoding="utf-8") as f:
                f.write(original)
    print("-" * 78)
    print("  反向测试：%d 条通过 / %d 条用例，%d 条失败"
          % (passed, len(CASES), failed))
    print("=" * 78)
    if failed:
        print("✗ 有校验规则未能被反例触发——这些规则实际处于失效状态，必须修。")
        return 1
    print("✓ 每条规则都能被反例触发（校验器确实在工作）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
