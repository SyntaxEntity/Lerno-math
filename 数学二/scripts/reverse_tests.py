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
    python3 数学二/scripts/reverse_tests.py            # 跑全部反向测试
    python3 数学二/scripts/reverse_tests.py -v         # 打印每条反例的细节

设计
----
每个用例是 `Case(code, 名字, 目标文件, 变换函数, 期望出现的错误码)`。
- 变换函数接收原文、返回改坏后的文本；用「读原文 → 写坏文 → 跑校验 → 恢复」保证
  无论成败原始内容都会还原。
- 校验器以子进程运行（`--no-mermaid` 加速），只关心是否出现期望的错误码与关键字。
- 任何一条用例没有触发预期错误，就计为**失败**——这才是「校验器不是摆设」的证据。
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
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
G08 = os.path.join(PARTS, "gaoshu", "08-数二高数综合与证明专题.md")

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

    直接往 <body> 后插一个占位符即可，不依赖正文的具体结构
    （正文结构改版过一次，早期版本依赖 <p id="sec-core"> 导致用例失效）。
    """
    return t.replace("<body", "<body", 1).replace(
        '<div id="wrap">', '<div id="wrap"><p>@@MATH7@@</p>', 1)


def _html_em_in_math(t):
    """公式区间里出现 <em>（* 被 Markdown 吃掉）。"""
    return t.replace("<p>", "<p>$A^{<em>}=A^{</em>}A$ ", 1)


def _html_bad_nav(t):
    """上一章链接指向不存在的文件。"""
    return t.replace('class="cb-btn" href="', 'class="cb-btn" href="nope-', 1)


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
case("F20", "上一章链接不可达", D01H, _html_bad_nav, mode="full")
case("F20", "字段区块内容为空（内容被切到区块外）", D01H, _empty_section, mode="full")
case("F20", "区块内重复字段名", D01H, _dup_field_label, mode="full")
case("F21", "正文标题重复", D01H, _dup_heading, mode="full")
case("F21", "正文出现第二个 h1", D01H, _two_h1, mode="full")
case("F17", "行间公式 $ 不成对（成品）", D05, _odd_dollar_full, mode="full")
case("F3", "mermaid 标签含圆括号未加引号（真实解析器层·成品）", D05, _bad_mermaid_syntax,
     mode="full", mermaid=True)
case("F3", "mermaid 标签含圆括号未加引号（真实解析器层·内容源）", G05, _bad_mermaid_syntax,
     mode="parts", mermaid=True)


def run_validate(mode, allow_mermaid=False):
    cmd = [PY, VALIDATE] + (["--parts"] if mode == "parts" else [])
    if not allow_mermaid:
        cmd.append("--no-mermaid")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
    return r.stdout + r.stderr


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
            broken = mutate(original)
            if broken == original:
                print("  ? %-5s %-42s 跳过（反例未改变内容，用例失效）" % (code, name))
                failed += 1
                continue
            with open(target, "w", encoding="utf-8") as f:
                f.write(broken)
            out = run_validate(mode, allow_mermaid=mermaid)
            hit = ("[%s]" % code) in out
            if hit:
                passed += 1
                print("  ✓ %-5s %-42s 已报错" % (code, name))
                if verbose:
                    for ln in out.split("\n"):
                        if "[%s]" % code in ln:
                            print("        " + ln.strip()[:140])
                            break
            else:
                failed += 1
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
