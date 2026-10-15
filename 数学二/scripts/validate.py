#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学二速成资料校验器。

校验项（与 PROMPT 第三节表格一一对应）
------------------------------------
  F1  模板字段齐全**且顺序正确**（按字段名定位，不按位置下标）
  F2  正文统计行与 scripts/meta.py 逐字一致
  F3  代码围栏成对闭合、语言标签合法；mermaid 交给**真实解析器**（失败即报错）
  F4  禁止占位符（TODO / 待补充讲解 / XXX / 此处省略 …）
  F5  ASCII(text) 图内不得出现全角字符或制表符（破坏等宽对齐）
  F6  真题年份落在 meta.YEAR_MIN—YEAR_MAX 区间
  F7  高频标记与 meta.py 一致
  F8  每个知识点 ≥1 张示意图（图片或 ASCII）+ ≥1 张 mermaid 流程图
  F9  核心讲解句数在 3—20 句
  F10 易错点 2—4 条
  F11 关键结论速记 3—8 条
  F12 README 声明清单与正文标注**双向一致**
  F13 块级元素（标题/围栏/表格/引用/列表/行间公式）之间有空行；**排除代码块内部**
  F14 渲染验证：模板字段各自独立成段（真实 Markdown 渲染器）
  F15 所有相对链接可从仓库根解析；图片资源真实存在
  F16 交付物完整性（不静默缺失）+ 不含绝对路径
  F17 LaTeX `$` 成对（数学科目特有）
  F18 每张被引用的图都有对应的 figs 生成脚本（图与代码对应）

用法
----
    python3 数学二/scripts/validate.py            # 校验成品 + HTML
    python3 数学二/scripts/validate.py --parts    # 校验内容源 parts/
    python3 数学二/scripts/validate.py --stats    # 只打印统计
    python3 数学二/scripts/validate.py --no-mermaid   # 跳过真实解析器（离线时用）
"""
import ast
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import meta as T          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))     # 仓库根
CONTENT = os.path.join(ROOT, "数学二")             # 成品根
PARTS = os.path.join(ROOT, "parts")
FIGDIR = os.path.join(CONTENT, "scripts", "figs")
ASSETS = os.path.join(CONTENT, "assets")
MERMAID_CHECKER = os.path.join(CONTENT, "scripts", "check_mermaid.mjs")

FIELD_ORDER = ["**考频统计**", "**核心讲解**", "**关键结论速记**",
               "**示意图**", "**易错点**", "**真题示例**"]
SEGMENTS = ["核心讲解", "关键结论速记", "示意图", "易错点", "真题示例"]
# 外壳契约里**逐字一致**的六段锚点 id（PLAN-对齐与改版 §2.4）。
# 这里再写一份是有意的：校验器要能独立于生成器判断"契约有没有被遵守"，
# 同时用 check_shell() 里的自比对防止两边悄悄分叉。
SHELL_ANCHORS = ["sec-freq", "sec-core", "sec-key", "sec-fig", "sec-err", "sec-real"]
FENCE_LANGS = ("text", "mermaid")
ALLOWED_BOX = set("─│┌┐└┘├┤┬┴┼▲▼→←↑↓")
PLACEHOLDER = re.compile(r"TODO|FIXME|待补充讲解|此处省略|\bTBD\b|XXX|待填写|占位符")
YEAR_RE = re.compile(r"((?:19|20)\d{2})\s*年")
# 原题标注：**2024 年数二第 12 题（填空题，5 分）**
ORIG_RE = re.compile(r"^\*\*((?:19|20)\d{2})\s*年数二第\s*(\d+)\s*题")
# 改编标注：**2023 年真题改编（解答题，12 分）**
ADAPT_RE = re.compile(r"^\*\*((?:19|20)\d{2})\s*年真题改编")

errors, warnings, stats = [], [], defaultdict(int)
per_file = {}


def err(path, line, code, msg):
    errors.append("%s:%s [%s] %s" % (path, line, code, msg))


def warn(path, line, code, msg):
    warnings.append("%s:%s [%s] %s" % (path, line, code, msg))


def rel(p):
    return os.path.relpath(p, ROOT)


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def is_fence(l):
    return l.strip().startswith("```")


def is_head(l):
    return bool(re.match(r"^#{1,6} ", l.strip()))


def is_quote(l):
    return l.strip().startswith(">")


def is_math_fence(l):
    return l.strip().startswith("$$")


def is_table_row(l):
    s = l.strip()
    if s.startswith("|") and s.count("|") >= 2:
        return True
    # 分隔行：仅由 - | : 空格组成且含 -
    return bool(s) and set(s) <= set("-|: ") and "-" in s


def math_delim_only(line):
    """该行是否「只有 `$$` 定界符」（允许行尾空白）。

    用精确匹配而不是 `"$$" in line`：公式正文里也会出现 `$$`（如前半段以 `$$` 结尾），
    若把它当成闭合定界符，会与真正的定界符错配。
    """
    return re.fullmatch(r"\s*\$\$\s*", line) is not None


def inner_mask(lines):
    """标出「代码围栏内部」与「`$$` 行间公式块内部」的行号集合。

    为什么必须排除：代码块里的 `|<--- length --->|` 会被误判成 Markdown 表格，
    产生大量误报（408 踩过这个坑）。

    实现要点（都是踩过的坑）：
    1. 围栏开/闭必须成对匹配，用显式的 in_fence 状态，而不是「找到下一个 ``` 」。
    2. `$$` 块按**定界符个数**配对：一块里出现的 `$$` 计入计数，累计到偶数即闭合。
    3. **遇到未闭合的块要停下来**，绝不能用「一直找到文件尾」的循环 —— 那样一个
       漏写的 `$` 会把后面几十行正文全标记成块内部，导致后续所有检查静默失效
       （实测：一个 `$$` 被写成 `$` 后，inner 从 17 行暴涨到 67 行，F17 因此完全失效）。
    """
    inner = set()
    i, n = 0, len(lines)
    in_fence = False
    fence_start = 0
    open_math = None            # 行间公式块的起始行号
    while i < n:
        raw = lines[i]
        st = raw.strip()
        if in_fence:
            inner.add(i)
            if st.startswith("```"):
                in_fence = False
            i += 1
            continue
        if st.startswith("```"):
            in_fence = True
            fence_start = i
            inner.add(i)
            i += 1
            continue
        if open_math is not None:
            inner.add(i)
            if math_delim_only(raw):
                open_math = None
            i += 1
            continue
        if st.startswith("$$"):
            # 只有「独占一行的 `$$` 定界符」开启块状态；块内才加入 inner。
            # 注意：**含公式的单行 `$$...$$` 不加 inner** —— 若把这一行也屏蔽掉，
            # 一个被写坏的定界符就会连同证据一起被排除，F17 的奇偶校验永远看不到它
            # （实测踩过：inner 把坏行吞掉后，全文 `$$` 计数恒为 0，规则形同虚设）。
            if math_delim_only(raw):
                inner.add(i)
                open_math = i
            i += 1
            continue
        i += 1
    # 未闭合的围栏/公式块：把它们之后的标记保持原样（宁可多查，不可漏查）
    return inner


def char_width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


# ---------------------------------------------------------------------------
# 图相关
# ---------------------------------------------------------------------------
def check_ascii_block(path, lineno, block):
    """F5：ASCII 图不得含全角字符/制表符。"""
    for i, ln in enumerate(block, start=lineno):
        if "\t" in ln:
            err(path, i, "F5", "ASCII 图含制表符，会破坏等宽对齐")
            continue
        for ch in ln:
            if ord(ch) < 128 or ch in ALLOWED_BOX:
                continue
            if unicodedata.east_asian_width(ch) in ("W", "F"):
                err(path, i, "F5",
                    "ASCII 图含全角字符 %r（破坏对齐），中文说明请外移到正文" % ch)
                break
        if len(ln) > 100:
            err(path, i, "F5", "ASCII 图行宽 %d > 100" % len(ln))


def scan_fences(path, lines, mermaid_blocks):
    """扫描围栏：校验语言标签、闭合、ASCII 对齐；收集 mermaid 源码。"""
    n_text = n_mermaid = 0
    in_fence = False
    lang = ""
    start = 0
    buf = []
    for i, ln in enumerate(lines, start=1):
        m = re.match(r"^\s*```(\w*)\s*$", ln)
        if m and not in_fence:
            in_fence, lang, start, buf = True, m.group(1), i, []
            if lang not in FENCE_LANGS:
                err(path, i, "F3",
                    "代码块语言标签非法（%r）；仅允许 text / mermaid" % lang)
        elif ln.strip() == "```" and in_fence:
            in_fence = False
            if lang == "text":
                n_text += 1
                check_ascii_block(path, start + 1, buf)
            elif lang == "mermaid":
                n_mermaid += 1
                mermaid_blocks.append((path, start + 1, "\n".join(buf)))
        elif in_fence:
            buf.append(ln)
    if in_fence:
        err(path, start, "F3", "代码围栏未闭合（起始第 %s 行，语言 %r）" % (start, lang))
    return n_text, n_mermaid


def run_mermaid_parser(scan_dir):
    """F3 的真实解析器层：调用 node + 官方 mermaid parse()。

    这里的**每一条失败路径都必须是 error 而不是 warning**：解析器不在、装不起来、
    返回码非 0、一块图都没扫到——这四种情况都会让 F3 退化成「永远通过」，
    而页面上的图会静默变空白。宁可整个校验失败，也不许它假装检查过了。
    真要离线跳过，必须显式加 `--no-mermaid`（命令行会留下痕迹）。

    `scan_dir` 必须跟着模式走：`--parts` 时扫内容源 `parts/`，成品模式扫 `数学二/`。
    否则写手在「改 parts → validate --parts」这个内层循环里**看不到自己刚写坏的
    mermaid**，要等 build 之后才会暴露——那就等于内层循环没有图形校验。
    """
    # 提示里**不写版本号**：版本只在 tools-package.json 里写一次
    # （PLAN-对齐与改版 §1.2），这里给的是"怎么按清单装"的命令。
    hint = ("（装依赖：mkdir -p .tools && "
            "cp 数学二/scripts/tools-package.json .tools/package.json && "
            "npm install --prefix .tools --cache /tmp/npm-cache --no-audit --no-fund；"
            "实在离线就加 --no-mermaid 显式跳过）")
    if not os.path.exists(MERMAID_CHECKER):
        err("数学二/scripts", 0, "F3", "找不到 mermaid 解析器脚本 %s%s"
            % (rel(MERMAID_CHECKER), hint))
        return
    if shutil.which("node") is None:
        err("mermaid", 0, "F3", "找不到 node 可执行文件，无法做真实解析%s" % hint)
        return
    try:
        r = subprocess.run(["node", MERMAID_CHECKER, "--content", scan_dir], cwd=ROOT,
                           capture_output=True, text=True, timeout=900)
    except Exception as e:                                   # noqa: BLE001
        err("mermaid", 0, "F3", "调用 mermaid 解析器失败：%s" % e)
        return
    try:
        data = json.loads(r.stdout)
    except Exception:                                        # noqa: BLE001
        err("mermaid", 0, "F3",
            "mermaid 解析器未产出 JSON（返回码 %d）：%s%s"
            % (r.returncode, (r.stderr or r.stdout or "")[-200:], hint))
        return
    if r.returncode != 0:
        err("mermaid", 0, "F3", "mermaid 解析器返回码 %d：%s"
            % (r.returncode, str(data.get("error") or r.stderr or "")[:200]))
        return
    stats["mermaid_parsed"] = data.get("ok", 0)
    stats["mermaid_blocks"] = data.get("total", 0)
    for f in data.get("failed", []):
        p = rel(f["file"])
        err(p, f.get("line", 0), "F3",
            "mermaid 真实解析器拒绝：%s" % str(f.get("error", ""))[:200])
    if data.get("total", 0) == 0:
        err("mermaid", 0, "F3",
            "在 %s 下没有任何 mermaid 图被解析——扫描范围为空，等于 F3 没生效"
            % rel(scan_dir))


def check_latex(path, lines, inner):
    """F17：`$` 必须成对（排除代码块内部）。"""
    for i, ln in enumerate(lines, start=1):
        if (i - 1) in inner:
            continue
        s = ln.strip()
        if s.startswith("$$"):
            continue
        # 去掉转义美元与行内代码
        t = re.sub(r"\\\$", "", re.sub(r"`[^`]*`", "", ln))
        if t.count("$") % 2 == 1:
            err(path, i, "F17", "行内公式 `$` 不成对：%s" % ln.strip()[:60])

    # 行间公式 `$$` 必须整体成对：全文（排除代码块与转义）里 `$$` 的个数应为偶数。
    # 只做逐行检查会漏掉「一个 $$ 被写成单个 $」这类错误——它落在独占一行的
    # 公式定界符上，逐行看永远「不成对的是行内 $」而被跳过。
    joined = "\n".join(ln for k, ln in enumerate(lines) if k not in inner)
    joined = re.sub(r"`[^`]*`", "", joined)
    if joined.count("$$") % 2 == 1:
        err(path, 0, "F17", "行间公式定界符 `$$` 个数为奇数（有一处未闭合）")


# ---------------------------------------------------------------------------
# 成品校验
# ---------------------------------------------------------------------------
def validate_file(path, subject_key, is_overview=False, mermaid_blocks=None):
    rp = rel(path)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")

    if not text.strip():
        err(rp, 1, "F0", "文件为空")
        return

    inner = inner_mask(lines)
    check_latex(rp, lines, inner)
    check_math_markup(rp, lines, inner)

    all_h2 = [(i, m.group(1).strip())
              for i, ln in enumerate(lines)
              if (m := re.match(r"^## (?!#)(.*)$", ln))]
    if not all_h2:
        err(rp, 1, "F0", "未找到任何 '## 知识点' 小节")
        return

    # 知识点小节 vs 模块小节：核心讲解内部也用 `## 【模块名】` 分块，
    # 它们**不是**知识点，不能按六字段模板去要求。判据：含「**考频统计**」的
    # `##` 才是知识点小节；其余 `##` 视为其所属知识点的正文延续。
    kp_idx = [k for k, (i, _t) in enumerate(all_h2)
              if any(ln.startswith("**考频统计**")
                     for ln in lines[i:(all_h2[k + 1][0] if k + 1 < len(all_h2)
                                           else len(lines))])]
    if not kp_idx:
        # 总览类是元文件，本来就没有知识点小节
        if not is_overview:
            err(rp, 1, "F0", "未找到含「考频统计」的知识点小节")
        return
    stats["sections"] += len(kp_idx)

    for n, k in enumerate(kp_idx):
        start, title = all_h2[k]
        # 该知识点的范围一直延伸到「下一个知识点小节」之前（模块小节含在内）
        nxt = kp_idx[n + 1] if n + 1 < len(kp_idx) else len(all_h2)
        end = all_h2[nxt][0] if nxt < len(all_h2) else len(lines)
        body = lines[start:end]

        if is_overview:
            continue

        # [高频] 标记必须与 meta.py 一致（见下方 F7），此处只检查字段结构，
        # 不再无条件要求标题以 [高频] 结尾——那会把 meta 里非高频的章节误判为错误。

        # ---- F1 字段齐全且顺序正确（按字段名定位）----
        pos = {}
        for fld in FIELD_ORDER:
            hits = [k for k, ln in enumerate(body) if ln.startswith(fld)]
            if not hits:
                err(rp, start + 1, "F1", "小节《%s》缺少字段 %s" % (title, fld))
            else:
                pos[fld] = hits[0]
        order = [pos[f] for f in FIELD_ORDER if f in pos]
        if order != sorted(order):
            err(rp, start + 1, "F1", "小节《%s》字段顺序错误，应为 %s"
                % (title, " → ".join(FIELD_ORDER)))

        def seg(fld):
            if fld not in pos:
                return []
            i = pos[fld]
            ends = [v for v in pos.values() if v > i]
            return body[i:(min(ends) if ends else len(body))]

        # ---- F2 考频统计与 meta.py 逐字一致 ----
        freq = [ln for ln in body if ln.startswith("**考频统计**")]
        if freq:
            match = None
            for t in T.TOPICS.get(subject_key, []):
                if t[0] in title:
                    match = t[0]
                    break
            if match is None:
                err(rp, start + 1, "F2", "小节《%s》无法在 meta.py 中匹配到知识点" % title)
            else:
                expect = T.freq_line(subject_key, match)
                if freq[0].strip() != expect:
                    err(rp, start + 1, "F2",
                        "考频统计与 meta.py 不一致\n      实际: %s\n      期望: %s"
                        % (freq[0].strip(), expect))

        # ---- F4 占位符 ----
        for k, ln in enumerate(body):
            if (start + k) in inner:
                continue
            if PLACEHOLDER.search(ln):
                err(rp, start + 1 + k, "F4", "疑似占位符：%s" % ln.strip()[:60])

        # ---- F6 真题年份 ----
        ti = pos.get("**真题示例**")
        if ti is not None:
            blk = body[ti:]
            years = [int(m.group(1)) for ln in blk for m in YEAR_RE.finditer(ln)]
            if not years:
                err(rp, start + ti + 1, "F6", "真题示例未标注年份")
            for y in years:
                if not (T.YEAR_MIN <= y <= T.YEAR_MAX):
                    err(rp, start + ti + 1, "F6",
                        "真题年份 %d 超出 %d—%d" % (y, T.YEAR_MIN, T.YEAR_MAX))
            if not any(ORIG_RE.match(ln.strip()) or ADAPT_RE.match(ln.strip()) for ln in blk):
                err(rp, start + ti + 1, "F6",
                    "真题示例未按规范标注（应写「**20XX 年数二第 N 题（…）」"
                    "或「**20XX 年真题改编（…）」）")

        # ---- F7 高频标记与 meta.py 一致 ----
        hot_meta = None
        for t in T.TOPICS.get(subject_key, []):
            if t[0] in title:
                hot_meta = t[5]
        if hot_meta is not None:
            has = "[高频]" in title
            if hot_meta and not has:
                err(rp, start + 1, "F7", "meta.py 标记为高频，但标题缺 [高频]")
            if not hot_meta and has:
                err(rp, start + 1, "F7", "meta.py 未标记高频，但标题有 [高频]")

        # ---- F9 核心讲解自然段数（判据与 parts 版一致，见 validate_partial）----
        ci = pos.get("**核心讲解**")
        if ci is not None:
            body_lines = seg("**核心讲解**")[1:]        # 去掉字段标签行本身
            cp = "\n".join(body_lines)
            for msg in check_core_structure(cp):
                err(rp, start + ci + 1, "F9", msg)
            stats["sent"] += len([s for s in re.split(r"[。；;！？]", cp)
                                  if len(s.strip()) >= 4])

        # ---- F10 易错点条数 ----
        ei = pos.get("**易错点**")
        if ei is not None:
            b = [ln for ln in seg("**易错点**") if re.match(r"^\s*[-*·]\s+\S", ln)]
            if not (2 <= len(b) <= 4):
                err(rp, start + ei + 1, "F10", "易错点应 2—4 条，实为 %d 条" % len(b))

        # ---- F11 速记条数 ----
        ki = pos.get("**关键结论速记**")
        if ki is not None:
            b = [ln for ln in seg("**关键结论速记**") if re.match(r"^\s*[-*·]\s+\S", ln)]
            if not (3 <= len(b) <= 8):
                err(rp, start + ki + 1, "F11", "关键结论速记应 3—8 条，实为 %d 条" % len(b))

        # ---- F8 每知识点 ≥1 图 + ≥1 流程图（在本文件层面统计）----
        # 实际按文件合计判定，见 validate_file 尾部

    # ---- lint + 渲染 ----
    lint_markdown(rp, lines, inner)
    if not is_overview:
        render_check(rp, text)

    n_text, n_mermaid = scan_fences(rp, lines, mermaid_blocks if mermaid_blocks is not None else [])
    imgs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", text)
    stats["img"] += len(imgs)

    # ---- F8：≥1 张示意图 + ≥1 张流程图（总览等元文件不参与）----
    if not is_overview:
        if n_text == 0 and not imgs:
            err(rp, 1, "F8", "没有任何示意图（既无图片也无 ASCII 图）")
        if n_mermaid == 0:
            err(rp, 1, "F8", "没有 mermaid 流程图（每章至少 1 张判定/流程类图）")

    # ---- F15 图片资源真实存在 ----
    # 基准是交付根 `数学二/`，不是 md 文件所在目录：正文里统一写 `assets/xxx.png`，
    # 由 build_html.py 在生成子目录页面时加 `../` 前缀。这个「单一基准」是刻意的，
    # 否则每个子目录的 md 都要写不同层级的 `../`，手写必错。
    for src in imgs:
        if src.startswith(("http", "/")):
            err(rp, 0, "F15", "图片必须用相对路径：%s" % src)
            continue
        if not os.path.exists(os.path.normpath(os.path.join(CONTENT, src))):
            err(rp, 0, "F15", "图片不存在：%s" % src)

    # ---- F16 不含绝对路径 ----
    for i, ln in enumerate(lines, start=1):
        if (i - 1) in inner:
            continue
        if re.search(r"(?<![\w.])/(?:home|Users|root|mnt|media)/", ln):
            err(rp, i, "F16", "正文含绝对路径（换机器即失效）：%s" % ln.strip()[:60])

    per_file[rp] = {"sections": len(kp_idx), "text": n_text,
                    "mermaid": n_mermaid, "img": len(imgs), "chars": len(text)}
    stats["text_figs"] += n_text
    stats["mermaid"] += n_mermaid
    stats["chars"] += len(text)


def check_core_structure(cp):
    """F9：核心讲解必须按「模块化」结构写，不能是一大段文字。

    判据（对应 PARTS_FORMAT 的固定结构）：
      1. 至少 2 个 `## 【模块名】` 标题 —— 建立层级；
      2. 至少 1 个独立成行的 `$$...$$` 公式块；
      3. 至少 1 处 `> ⚠️` 提醒（易错点 / 秒杀技）；
      4. 至少 1 个 `**【核心公式】**` 或 `【适用条件】` 标记块；
      5. 列表条目（`-` / `1.`）不少于 5 条 —— 拆解知识点；
      6. 同时含 `**加粗**` 的关键条件。
    返回错误信息列表（空列表表示通过）。
    """
    msgs = []
    if not cp.strip():
        return ["核心讲解为空"]
    heads = re.findall(r"^##\s*【[^】]+】", cp, re.M)
    if len(heads) < 2:
        msgs.append("核心讲解需至少 2 个 `## 【模块名】` 标题（实为 %d 个）"
                    "—— 不要写成一大段文字" % len(heads))
    if not re.search(r"^\s*\$\$", cp, re.M):
        msgs.append("核心讲解缺独立成行的 `$$…$$` 公式块")
    if "⚠️" not in cp:
        msgs.append("核心讲解缺 `> ⚠️ **易错点/秒杀技**：` 提醒")
    if not re.search(r"【(核心公式|适用条件)】", cp):
        msgs.append("核心讲解缺 `【核心公式】`/`【适用条件】` 标记块")
    if not re.search(r"\*\*[^*\n]{2,}\*\*", cp):
        msgs.append("核心讲解缺 `**加粗**` 的关键条件")
    items = len(re.findall(r"^\s*(?:[-*]|\d+\.)\s+\S", cp, re.M))
    if items < 5:
        msgs.append("核心讲解列表条目仅 %d 条（应 ≥5）—— 请用列表拆解知识点" % items)
    # 易混淆内容必须用表格对比（如反常积分两类、微分方程特征根三种情形）
    if not re.search(r"^\s*\|.*\|\s*$", cp, re.M):
        msgs.append("核心讲解缺 Markdown 对比表格 —— 易混淆内容（分类、判别、情形对照）"
                    "必须用表格呈现")
    else:
        # 表格每一行的列数必须一致。公式里的裸 `|`（如 $|f''(x)|$）会被 Markdown
        # 当成列分隔符，把 4 列撑成 6 列、表格直接散架；应写成 \lvert \rvert。
        for ti, tm in enumerate(re.finditer(r"((?:^\s*\|.*\|\s*$\n?)+)", cp, re.M), 1):
            rows = [r for r in tm.group(1).strip().split("\n") if r.strip()]
            if len(rows) < 2:
                continue
            cols = {r.count("|") for r in rows}
            if len(cols) != 1:
                msgs.append("第 %d 张对比表格列数不一致（%s）—— 单元格里的裸 `|` "
                            "需写成 `\\lvert`/`\\rvert`" % (ti, sorted(cols)))
    return msgs


def lint_markdown(rp, lines, inner):
    """F13：块级元素之间必须有空行（严格排除代码块/行间公式内部）。

    为什么重要：Markdown 中单换行不产生换行，字段之间只隔一个换行会糊成一整段。
    围栏规则要区分「开」与「闭」：关闭围栏前不要求空行（那会把空行塞进代码块），
    开启围栏后也不要求空行（紧跟的是代码内容）。
    """
    is_fence_line = lambda l: l.strip().startswith("```")          # noqa: E731
    is_math_line = lambda l: l.strip().startswith("$$")            # noqa: E731
    need = {}
    for i, l in enumerate(lines):
        if i in inner:
            continue
        s = l.strip()
        if not s:
            continue
        if is_fence_line(l):
            # 该围栏是开还是闭？向上数同类型行数
            before = sum(1 for k in range(i) if is_fence_line(lines[k]))
            role = "open" if before % 2 == 0 else "close"
            if role == "open":
                need[i] = ("before", "代码围栏开始")
            else:
                need[i] = ("after", "代码围栏结束")
            continue
        if is_math_line(l):
            # `$$...$$` 单行写完时前后都要空行；多行块由 inner 排除内部
            if l.strip().count("$$") >= 2 and len(s) > 2:
                need[i] = ("both", "行间公式")
            else:
                before = sum(1 for k in range(i) if is_math_line(lines[k]))
                role = "open" if before % 2 == 0 else "close"
                need[i] = (("before", "行间公式开始") if role == "open"
                           else ("after", "行间公式结束"))
            continue
        if is_head(l):
            need[i] = ("both", "标题")
            continue
        # 模板字段标签（**核心讲解**：等）单独成段；若与上一段只隔一个换行，
        # 渲染时会被上一段吞并 —— 这正是 F14 要抓的「模板粘连」。
        if re.match(r"^\*\*(考频统计|核心讲解|关键结论速记|示意图|易错点|真题示例)\*\*", l):
            need[i] = ("both", "模板字段")
            continue
        if is_quote(l):
            prev_quote = i > 0 and is_quote(lines[i - 1])
            nxt_quote = i + 1 < len(lines) and is_quote(lines[i + 1])
            if not prev_quote:
                need.setdefault(i, ("before", "引用块开始"))
            if not nxt_quote:
                need[i] = ("after", "引用块结束")
                if i in need and need[i][0] == "before":
                    need[i] = ("both", "引用块")
            continue
        if is_table_row(l):
            prev_t = i > 0 and (i - 1) not in inner and is_table_row(lines[i - 1])
            nxt_t = i + 1 < len(lines) and (i + 1) not in inner and is_table_row(lines[i + 1])
            if not prev_t:
                need[i] = ("before", "表格开始")
            if not nxt_t:
                if i in need:
                    need[i] = ("both", "表格")
                else:
                    need[i] = ("after", "表格结束")
            continue
        if re.match(r"^\s*([-*+]|\d+\.)\s+\S", s):
            prev_l = i > 0 and (i - 1) not in inner and re.match(
                r"^\s*([-*+]|\d+\.)\s+\S", lines[i - 1].strip())
            if not prev_l:
                need.setdefault(i, ("before", "列表开始"))
            continue

    for i, (where, what) in need.items():
        if where in ("before", "both") and i > 0 and lines[i - 1].strip():
            err(rp, i + 1, "F13", "「%s」之前缺少空行（渲染时会与上一段粘连）"
                % lines[i].strip()[:40])
        if where in ("after", "both") and i + 1 < len(lines) and lines[i + 1].strip():
            err(rp, i + 1, "F13", "「%s」之后缺少空行" % lines[i].strip()[:40])

    for i in range(1, len(lines)):
        if i in inner or (i - 1) in inner:
            continue
        if not lines[i].strip() and not lines[i - 1].strip():
            err(rp, i + 1, "F13", "连续空行")


def render_check(rp, text):
    """F14：用真实 Markdown 渲染器确认模板字段各自独立成段。

    判据必须是「标记位于**段首**」——若只判「标记是否出现在该段」，
    字段粘连时标记位于段落中间，校验会永远报 0 条（408 实测过的失效判据）。
    """
    try:
        import markdown
    except ImportError:
        warn(rp, 0, "F14", "未安装 python-markdown，跳过渲染验证")
        return
    labels = ["考频统计", "核心讲解", "关键结论速记", "示意图", "易错点", "真题示例"]
    body = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)      # 公式块会干扰分段判定
    html = markdown.markdown(body, extensions=["tables", "fenced_code"])
    paras = re.findall(r"<p>(.*?)</p>", html, re.S)
    seen = {}
    for lab in labels:
        tag = "<strong>%s</strong>" % lab
        for i, p in enumerate(paras):
            head = p.strip()[:len(tag) + 8]
            if tag in head:                     # 必须位于段首
                seen.setdefault(lab, []).append(i)
                break
        else:
            where = [i for i, p in enumerate(paras) if tag in p]
            if where:
                err(rp, 0, "F14",
                    "字段 %s 被并入上一段（出现在第 %d 段中间）" % (lab, where[0]))
            else:
                err(rp, 0, "F14", "字段 %s 未渲染出来" % lab)
    idx = [seen[l][0] for l in labels if l in seen]
    dup = {k for k in idx if idx.count(k) > 1}
    if dup:
        bad = [l for l in labels if seen.get(l) and seen[l][0] in dup]
        err(rp, 0, "F14", "字段 %s 被渲染进同一段落（模板粘连）" % "、".join(bad))


# ---------------------------------------------------------------------------
# parts 内容源校验
# ---------------------------------------------------------------------------
def validate_partial(subject_key, topic, path, mermaid_blocks):
    rp = rel(path)
    name, times, years, pts, qtype, hot, slug = topic
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    inner = inner_mask(lines)
    check_latex(rp, lines, inner)
    check_math_markup(rp, lines, inner)

    segs, cur = {}, None
    for ln in lines:
        m = re.match(r"^# (\S.*?)\s*$", ln)
        if m and not ln.startswith("## "):
            cur = m.group(1).strip()
            segs.setdefault(cur, [])
            continue
        if cur is not None:
            segs[cur].append(ln)
    segs = {k: "\n".join(v).strip() for k, v in segs.items()}

    # F1 段落齐全与顺序
    for k in SEGMENTS:
        if k not in segs or not segs[k]:
            err(rp, 1, "F1", "缺少段落 # %s" % k)
    got = [k for k in segs if k in SEGMENTS]
    want = [k for k in SEGMENTS if k in segs]
    if got != want:
        err(rp, 1, "F1", "段落顺序错误：%s（应为 %s）" % (" / ".join(got), " / ".join(SEGMENTS)))
    for k in segs:
        if k not in SEGMENTS:
            err(rp, 1, "F1", "非法段落名 # %s（合法值只有 %s）" % (k, "、".join(SEGMENTS)))

    # 核心讲解内部的 `## 【模块名】` 属于正文，已随段内容一起解析，无需额外处理；
    # 这里显式确认「模块」不会污染一级段落名的判定（历史 bug：把模块名当段落名报错）。
    if "示意图" not in segs:
        return

    n_text, n_mermaid = scan_fences(rp, lines, mermaid_blocks)

    # F8
    imgs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", segs.get("示意图", ""))
    if n_text == 0 and not imgs:
        err(rp, 1, "F8", "示意图段既无图片也无 ASCII 图")
    if n_mermaid == 0:
        err(rp, 1, "F8", "缺少 mermaid 流程图")

    # F9/F10/F11
    # 注意：segs 的值是**字符串**，必须 .split("\n") 之后再逐行匹配。
    # 曾直接对字符串做列表推导 —— 那会逐字符迭代，正则永远不匹配，
    # 于是 F10/F11 恒报「0 条」，看起来像内容不合规，实际是校验器失效。
    #
    # F9 判据用**自然段数（2—5 段）**而不是句数：模板规定的是「拆成 2—5 个自然段」，
    # 而中文句数在数学文本里受公式内标点影响极大（同一段内容可数出 8 句或 24 句），
    # 用句数当硬判据会产生大量假警报。句数只作统计输出。
    cp = segs.get("核心讲解", "")
    errs9 = check_core_structure(cp)
    for msg in errs9:
        err(rp, 1, "F9", msg)
    stats["sent"] += len([x for x in re.split(r"[。；;！？]", cp) if len(x.strip()) >= 4])
    kb = [ln for ln in segs.get("关键结论速记", "").split("\n")
          if re.match(r"^\s*[-*·]\s+\S", ln)]
    if not (3 <= len(kb) <= 8):
        err(rp, 1, "F11", "关键结论速记应 3—8 条，实为 %d 条" % len(kb))
    ec = [ln for ln in segs.get("易错点", "").split("\n")
          if re.match(r"^\s*[-*·]\s+\S", ln)]
    if not (2 <= len(ec) <= 4):
        err(rp, 1, "F10", "易错点应 2—4 条，实为 %d 条" % len(ec))

    # F6 真题年份与标注规范
    tr = segs.get("真题示例", "")
    yrs = [int(m.group(1)) for m in YEAR_RE.finditer(tr)]
    if not yrs:
        err(rp, 1, "F6", "真题示例未标注年份")
    for y in yrs:
        if not (T.YEAR_MIN <= y <= T.YEAR_MAX):
            err(rp, 1, "F6", "真题年份 %d 超出 %d—%d" % (y, T.YEAR_MIN, T.YEAR_MAX))
    titled = [ln.strip() for ln in tr.split("\n")
              if ORIG_RE.match(ln.strip()) or ADAPT_RE.match(ln.strip())]
    if not titled:
        err(rp, 1, "F6", "真题示例标题未按规范标注（原题或改编）")
    if len(titled) != 1:
        err(rp, 1, "F6", "真题示例应恰好 1 道，实为 %d 道" % len(titled))

    # F4 占位符 / F2 不得自带统计数字
    for i, ln in enumerate(lines, start=1):
        if (i - 1) in inner:
            continue
        if PLACEHOLDER.search(ln):
            err(rp, i, "F4", "疑似占位符：%s" % ln.strip()[:60])
        if re.search(r"考察次数|分数占比|考频统计|考频待补充", ln):
            err(rp, i, "F2", "parts 内容源不得自带考频数字（由 build.py 注入）：%s"
                % ln.strip()[:50])
    # F16 绝对路径
    for i, ln in enumerate(lines, start=1):
        if (i - 1) in inner:
            continue
        if re.search(r"(?<![\w.])/(?:home|Users|root|mnt|media)/", ln):
            err(rp, i, "F16", "含绝对路径：%s" % ln.strip()[:60])

    stats["sections"] += 1
    stats["text_figs"] += n_text
    stats["mermaid"] += n_mermaid
    stats["chars"] += len("\n".join(lines))
    per_file[rp] = {"sections": 1, "text": n_text, "mermaid": n_mermaid,
                    "img": len(imgs), "chars": len("\n".join(lines))}


def check_math_markup(path, lines, inner):
    """F19：LaTeX 必须处于 `$...$` 或 `$$...$$` 内，且不得被反引号包住。

    为什么需要这条：``\frac{dy}{dx}`` 这类片段一旦没被 `$` 包裹、或被反引号包住，
    KaTeX 不会渲染它，读者看到的就是原始 LaTeX 源码；更糟的是其中的
    `_` 与 `^` 会被 Markdown 当成强调标记吃掉字符，公式直接损坏。
    实测：某章 6 条速记全部长这样，读者反馈"可读性太差"——所以必须机器拦住。
    """
    for i, ln in enumerate(lines, start=1):
        if (i - 1) in inner:
            continue
        st = ln.strip()
        if st.startswith("```"):
            continue
        # 1) 反引号里包着 LaTeX 命令
        for m in re.finditer(r"`([^`\n]*)`", ln):
            if re.search(r"\\[a-zA-Z]{2,}", m.group(1)):
                err(path, i, "F19",
                    "LaTeX 被反引号包裹（不会渲染，且 _ ^ 会被 Markdown 吃掉）：%s"
                    % m.group(1)[:50])
                break
        # 2) 数学模式之外的裸 LaTeX 命令（先剔除行内代码与已包裹的公式）
        t = re.sub(r"`[^`\n]*`", "", ln)
        t = re.sub(r"\$\$[^$]*\$\$", "", t)     # 单行 $$...$$
        t = re.sub(r"\$[^$]*\$", "", t)           # 行内 $...$
        t = t.lstrip(">").strip()                   # 引用块前缀
        if t.startswith("$$") or t.endswith("$$"):
            continue                                # 多行公式块的定界符行
        if re.search(r"\\[a-zA-Z]{2,}", t):
            err(path, i, "F19",
                "数学模式外的裸 LaTeX（请用 $...$ 包裹）：%s" % ln.strip()[:60])


# ---------------------------------------------------------------------------
# 全局校验
# ---------------------------------------------------------------------------
def our_parts():
    """本资料的内容源文件（按 meta.ORDER 限定，绝不扫到 408 的 parts/）。

    曾经写成 `glob(parts/*/*.md)`，结果把 408 四科的 28 个 parts 文件也扫进来，
    使 F12 的「原题/改编」计数完全失真。范围必须由 meta.py 决定。
    """
    out = []
    for k in T.ORDER:
        out.extend(sorted(glob.glob(os.path.join(PARTS, k, "*.md"))))
    return out

def check_readme_citations():
    """F12：README 声明清单与正文标注**双向一致**。"""
    actual = set()
    for f in our_parts():
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                m = ORIG_RE.match(ln.strip())
                if m:
                    actual.add((m.group(1), m.group(2)))
    rp = os.path.join(CONTENT, "README.md")
    if not os.path.exists(rp):
        err("数学二/README.md", 0, "F12", "缺少 README.md（先跑 build_readme）")
        return
    with open(rp, encoding="utf-8") as fh:
        readme = fh.read()
    declared = set(re.findall(r"\|\s*`(\d{4})`\s*\|\s*第\s*`(\d+)`\s*题\s*\|", readme))
    for item in sorted(declared - actual):
        err("数学二/README.md", 0, "F12",
            "声明为已核对原题但正文未标注：%s 年第 %s 题" % item)
    for item in sorted(actual - declared):
        err("数学二/README.md", 0, "F12",
            "正文标注为原题但未在 README 清单声明：%s 年第 %s 题" % item)
    # 同一道题可能被两章各引用一次（如 2024 年第 22 题），去重后才是「原题道数」
    stats["orig"] = len(actual)
    stats["orig_cites"] = sum(
        1 for f in our_parts() for ln in open(f, encoding="utf-8")
        if ORIG_RE.match(ln.strip()))

    # 改编题数量也要能对上（单向：README 声明的改编数 ≥ 正文实有数）
    n_adapt = 0
    for f in our_parts():
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                if ADAPT_RE.match(ln.strip()):
                    n_adapt += 1
    stats["adapt"] = n_adapt
    stat = re.search(r"改编题\s*(\d+)\s*道", readme)
    if stat and int(stat.group(1)) != n_adapt:
        err("数学二/README.md", 0, "F12",
            "README 声明改编题 %s 道，正文实为 %d 道" % (stat.group(1), n_adapt))


def strip_code(text):
    """去掉代码围栏与行内代码，避免把示例代码里的路径当成真实引用。"""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    return text


def check_links():
    """F15：文档链接必须能从**仓库根**解析；图片按其所在目录解析。

    两种口径的区别是有意的：
      - 文档间链接统一写成「从仓库根算起」（数学二/高等数学/01-….md），
        这样在仓库根、在子目录、在 HTML 里都能点开；
      - 图片写成 `assets/xxx.png`（**相对交付根 `数学二/`**），
        由 build_html.py 在生成子目录页面时统一加 `../` 前缀。
    """
    files = (glob.glob(os.path.join(CONTENT, "*", "*.md"))
             + [os.path.join(CONTENT, "README.md")])
    for f in files:
        if not os.path.exists(f):
            continue
        rp = rel(f)
        text = strip_code(open(f, encoding="utf-8").read())
        imgs = {m.group(1) for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)\)", text)}
        for m in re.finditer(r"\]\(([^)\s]+)\)", text):
            t = m.group(1)
            if t.startswith(("http", "#", "mailto:")):
                continue
            if t in imgs:
                # 图片：按约定「相对交付根 数学二/」解析（与 build_html.py 一致）
                if not os.path.exists(os.path.normpath(os.path.join(CONTENT, t))):
                    err(rp, 0, "F15", "图片不存在：%s" % t)
                continue
            if not os.path.exists(os.path.join(ROOT, t)):
                err(rp, 0, "F15", "相对链接无法从仓库根解析：%s" % t)


def check_figs():
    """F18：每张被引用的 assets 图片都应有对应的 figs 生成脚本（先代码后图形）。"""
    if not os.path.isdir(ASSETS):
        err("数学二/assets", 0, "F18", "缺少 assets 目录")
        return
    used = set()
    for f in (glob.glob(os.path.join(CONTENT, "*", "*.md"))
              + our_parts()):
        text = strip_code(open(f, encoding="utf-8").read())
        for m in re.finditer(r"!\[[^\]]*\]\(assets/([^)\s]+)\)", text):
            used.add(m.group(1))
    # 只统计图片：assets/ 里现在也放 site.css / site.js（P2 外置资源），
    # 它们不是"未被引用的图片"，不该在这里告警。
    have = {os.path.basename(p) for p in glob.glob(os.path.join(ASSETS, "*"))
            if os.path.splitext(p)[1].lower() in (".png", ".svg", ".jpg", ".jpeg", ".webp")}
    for u in sorted(used - have):
        err("数学二/assets", 0, "F18", "正文引用的图片不存在：assets/%s" % u)
    for u in sorted(have - used):
        warn("数学二/assets", 0, "F18", "assets 中存在未被引用的图片：%s" % u)
    stats["assets"] = len(have)
    # figs 目录存在且有脚本
    figs = sorted(glob.glob(os.path.join(FIGDIR, "*.py")))
    if not figs:
        err("数学二/scripts/figs", 0, "F18", "缺少绘图脚本（图形必须由代码生成）")
    stats["figs"] = len(figs)


def check_html():
    """F16：HTML 产物完整性 + 引用资源真实存在 + 无绝对路径。"""
    idx = os.path.join(CONTENT, "index.html")
    if not os.path.exists(idx):
        err("数学二/index.html", 0, "F16", "缺少全科单页合集（先跑 build_html.py）")
        return
    with open(idx, encoding="utf-8") as f:
        page = f.read()
    n_topics = 0
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        d = os.path.join(CONTENT, sub["dir"])
        if not os.path.exists(os.path.join(d, "index.html")):
            err("数学二/%s" % sub["dir"], 0, "F16", "缺少部分首页 index.html")
        for t in T.TOPICS[k]:
            n_topics += 1
            if not os.path.exists(os.path.join(d, t[6] + ".html")):
                err("数学二/%s" % sub["dir"], 0, "F16", "缺少章节 HTML：%s.html" % t[6])
            if 'id="%s-%s"' % (k, t[6]) not in page:
                err("数学二/index.html", 0, "F16", "合集缺少锚点 %s-%s" % (k, t[6]))
    stats["html_topics"] = n_topics
    if n_topics != 15:
        err("数学二/index.html", 0, "F16", "知识点数应为 15，实为 %d" % n_topics)
    if page.count('class="mermaid"') < n_topics:
        err("数学二/index.html", 0, "F16",
            "合集 mermaid 容器 %d 个 < 知识点 %d 个" % (page.count('class="mermaid"'), n_topics))
    # 每个 HTML 引用的本地脚本/图片必须存在
    for f in glob.glob(os.path.join(CONTENT, "*", "*.html")) + [idx]:
        rp = rel(f)
        d = os.path.dirname(f)
        with open(f, encoding="utf-8") as fh:
            body = fh.read()
        if re.search(r"(?<![\w.])/(?:home|Users|root|mnt|media)/", body):
            err(rp, 0, "F16", "HTML 含绝对路径（换机器即失效）")
        for r in re.findall(r'<script src="([^"]+)"', body):
            if not os.path.exists(os.path.normpath(os.path.join(d, r))):
                err(rp, 0, "F16", "引用的脚本不存在：%s" % r)
        for r in re.findall(r'<img[^>]+src="([^"]+)"', body):
            if r.startswith(("http", "data:")):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(d, r))):
                err(rp, 0, "F16", "引用的图片不存在：%s" % r)
    # mermaid 运行时
    if not os.path.exists(os.path.join(CONTENT, "mermaid.min.js")):
        warn("数学二/mermaid.min.js", 0, "F16", "缺少 mermaid 运行时，图将回退为源码")


def check_html_math_and_nav():
    """F20：HTML 里的公式必须完好，且站内导航链接必须可达。

    分三项：
      1. 不得残留 `@@MATHn@@` 占位符（占位符还原失败会让正文变成乱码）；
      2. `$...$` 区间内不得出现 `<em>`/`<strong>`（Markdown 会把公式里的
         `*`、`_` 当强调标记吃掉，实测 `$AA^{*}=A^{*}A$` 会坏成
         `$AA^{<em>}=A^{</em>}A$`）；
      3. 侧栏「上一章/下一章」与章节条链接必须指向真实存在的文件。
    """
    pages = glob.glob(os.path.join(CONTENT, "*", "*.html"))
    idx = os.path.join(CONTENT, "index.html")
    if os.path.exists(idx):
        pages.append(idx)
    n_math = 0
    for f in pages:
        rp = rel(f)
        body = open(f, encoding="utf-8").read()
        if "@@MATH" in body:
            err(rp, 0, "F20", "公式占位符 @@MATHn@@ 未还原（共 %d 处）" % body.count("@@MATH"))
        # 去掉代码块/脚本后再查公式区间
        stripped = re.sub(r"<pre.*?</pre>|<code.*?</code>|<script.*?</script>|<style.*?</style>",
                          "", body, flags=re.S)
        for m in re.finditer(r"\$[^$]{0,800}\$", stripped, re.S):
            n_math += 1
            if re.search(r"<(em|strong)>", m.group(0)):
                err(rp, 0, "F20",
                    "公式被 Markdown 强调标记污染（* 或 _ 被吃掉）：%s"
                    % m.group(0)[:70].replace("\n", " "))
                break
        # 导航链接可达性（契约类名 .cn-prev / .cn-next，见 PLAN §2.4）
        d = os.path.dirname(f)
        for attr in re.findall(r'class="cn-(?:prev|next)[^"]*" href="([^"]*)"', body):
            if attr in ("", "#"):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(d, attr))):
                err(rp, 0, "F20", "上一章/下一章链接不可达：%s" % attr)
        # 每个字段区块（.sec-xxx 的 .box）必须有实际内容：
        # 曾经因为切片起点取成"字段段落之后"，六段式的内容全部落到了
        # section 外面，页面上只剩「考频统计」标题、正文整段消失。
        for sm in re.finditer(
                r'<section class="sec (sec-[a-z]+)"[^>]*>.*?'
                r'<div class="box">(.*?)</div></section>', body, re.S):
            aid, inner = sm.group(1), sm.group(2)
            text = re.sub(r"<[^>]+>", "", inner)
            text = re.sub(r"\s+", "", text)
            if len(text) < 4:
                err(rp, 0, "F20", "字段区块 %s 内容为空（内容被切到了区块之外）" % aid)
        # 字段标签不得在区块内重复出现（标题栏已有名字，正文再写一次是"看两遍"）
        for sm in re.finditer(
                r'<section class="sec (sec-[a-z]+)"[^>]*>.*?'
                r'<div class="sec-h">.*?</div><div class="box">(.*?)</div></section>',
                body, re.S):
            aid, inner = sm.group(1), sm.group(2)
            if re.match(r"\s*<p[^>]*>\s*<strong>[^<]+</strong>：", inner):
                err(rp, 0, "F20",
                    "字段 %s 的区块内又重复了一遍字段名（标题栏已显示）" % aid)
        # 独立成行的 $$…$$ 必须**与内容源等量**存活。
        #
        # 这条原来写的是"正文里至少出现一次 $$"，看起来能用，其实是**假通过**：
        # 当时 KaTeX 的初始化配置（含 `'$$'` 字面量）内联在页面里、且位于 <main> 之后，
        # 于是「一个公式都没有的科目总览页」也照样满足判据。P2 把脚本外置后真相暴露：
        # 总览页的 $$ 数从 2 变成 0，而内容源本来就没有公式。
        # 正确判据是"HTML 里有多少 $$，内容源里就该有多少"——公式保护/还原失效时
        # 这个等量关系会破，而与页面是否恰好含公式无关。
        want_dollars = _source_dollar_count(rp)
        if want_dollars is not None and "<main>" in body:
            mainpart = body[body.find("<main>"):]
            got = mainpart.count("$$")
            if got < want_dollars:
                err(rp, 0, "F20",
                    "正文的 `$$…$$` 公式块少了：内容源 %d 处，页面只剩 %d 处"
                    "（公式保护/还原可能失效）" % (want_dollars, got))
        for attr in re.findall(r'data-(?:prev|next)="([^"]+)"', body):
            if not os.path.exists(os.path.normpath(os.path.join(d, attr))):
                err(rp, 0, "F20", "键盘翻章目标不可达：%s" % attr)
        # F24：渲染后不得残留字面 `**`
        check_render_leftovers(body, rp, "F24", "html")
        # F25：真题示例的解析必须一步一段、关键公式独立成行
        sec = re.search(r'<section class="sec sec-real".*?</section>', body, re.S)
        if sec:
            bq = re.search(r"<blockquote>(.*?)</blockquote>", sec.group(0), re.S)
            if bq:
                # 段落既可能是 <p>，也可能是 <ol><li>（"1. …" 这类有序步骤会被
                # Markdown 渲染成列表）。**只查 <p> 会漏掉列表里的整段**——
                # 而列表恰恰是最容易塞进一堆行内公式的地方。
                paras = [a or b for a, b in
                         re.findall(r"<p>(.*?)</p>|<li>(.*?)</li>", bq.group(1), re.S)]
                check_solution_layout(paras, rp, "F25")
    stats["html_math"] = n_math


def _source_dollar_count(html_rel):
    """该 HTML 对应的内容源里 `$$` 的个数（用于 F20 的等量比对）。

    映射：章节页 → 同名 .md；部分首页 → 00-科目总览.md；全科合集 → 全部 md 之和；
    README.html → README.md。找不到对应源文件时返回 None（不做这项判定）。
    """
    def count(p):
        if not os.path.exists(p):
            return None
        return strip_code(open(p, encoding="utf-8").read()).count("$$")

    if html_rel.endswith("README.html"):
        return count(os.path.join(CONTENT, "README.md"))
    if html_rel == "数学二/index.html":
        total, seen = 0, False
        for k in T.ORDER:
            d = os.path.join(CONTENT, T.SUBJECTS[k]["dir"])
            for name in ["00-科目总览.md"] + [t[6] + ".md" for t in T.TOPICS[k]]:
                c = count(os.path.join(d, name))
                if c is not None:
                    total += c
                    seen = True
        return total if seen else None
    if html_rel.endswith("/index.html"):
        d = os.path.dirname(os.path.join(ROOT, html_rel))
        return count(os.path.join(d, "00-科目总览.md"))
    return count(os.path.join(ROOT, html_rel[:-5] + ".md"))


# 模板六字段的纯文本名（用于 F21 排除"设计如此"的重复）
FIELD_PLAIN = {"考频统计", "核心讲解", "关键结论速记", "示意图", "易错点", "真题示例"}


def check_html_headings():
    """F21：每个页面正文只能有一个 h1；单页合集里不得有重复的章节标题。

    为什么需要：`build.py` 曾把科目总览标题前置一次、而 `subject_overview()`
    自身也含该标题，成品里就出现**两行一模一样的大标题**；单页合集也曾把部分名、
    章名各渲染两遍。这类问题肉眼一眼可见，却没有任何规则拦得住。

    注意判据的范围：模板六字段名（考频统计/核心讲解/…）在 15 个章节里**本来就会
    重复出现**，属于正常结构，不能算"标题重复"——所以这里只检查：
      (a) 正文 h1 数量；
      (b) 同一章节区块**内部**是否出现重复标题。
    """
    pages = glob.glob(os.path.join(CONTENT, "*", "*.html"))
    idx = os.path.join(CONTENT, "index.html")
    if os.path.exists(idx):
        pages.append(idx)
    for f in pages:
        rp = rel(f)
        body = open(f, encoding="utf-8").read()
        mi = body.find("<main>")
        main = body[mi:] if mi != -1 else body
        heads = [(m.group(1), re.sub(r"\s+", " ",
                                     re.sub(r"<[^>]+>", "", m.group(2))).strip())
                 for m in re.finditer(r"<h([1-3])[^>]*>(.*?)</h\1>", main, re.S)]
        n1 = sum(1 for lv, _ in heads if lv == "1")
        if n1 > 1:
            err(rp, 0, "F21", "正文出现 %d 个 h1（每页应只有 1 个）" % n1)
        # 按「章节标题」(class="bookmark") 切块，逐块查重。
        # 章节页没有 bookmark，此时把整篇正文当成一个块来查——
        # 早期实现只遍历 blocks[1:]，导致章节页（跨章复用的单页）根本不被检查，
        # 反向测试注入的重复标题因此没被发现。
        blocks = re.split(r'<h[1-3] class="bookmark"[^>]*>', main)
        chunks = blocks[1:] if len(blocks) > 1 else [main]
        for bi, blk in enumerate(chunks, 1):
            seen = {}          # 标题文本 -> 出现次数（用 dict 而非 set，见下）
            for m in re.finditer(r"<h([1-6])[^>]*>(.*?)</h\1>", blk, re.S):
                key = re.sub(r"\s*(高频|常规|约 \d+ 分.*)$", "",
                             re.sub(r"\s+", " ",
                                    re.sub(r"<[^>]+>", "", m.group(2))).strip())
                if not key:
                    continue
                # 模板六字段名在每个知识点里**本来就各出现一次**，属于设计如此：
                # 只统计出现次数，不超过 1 次就不算重复。直接 continue 会把
                # "同一字段渲染两遍"这种真重复一起放过（实测踩过）。
                if key in FIELD_PLAIN:
                    seen[key] = seen.get(key, 0) + 1
                    if seen[key] > 1:
                        err(rp, 0, "F21",
                            "第 %d 个章节区块内字段标题重复：%r" % (bi, key))
                    continue
                if key in seen:
                    err(rp, 0, "F21", "第 %d 个章节区块内标题重复：%r" % (bi, key[:36]))
                seen[key] = seen.get(key, 0) + 1


def check_shell():
    """F22：外壳骨架完整性（PLAN-对齐与改版 §2.3—§2.5.1 的契约）。

    分两层：
      (a) 形式层——每页必须齐备顶栏/面包屑/页脚/侧栏；章节页还要有
          正文底部的 .chapter-nav 与六段 .sec-* 锚点；首页要有科目卡片入口；
      (b) 行为层——把 assets/site.js 放进 jsdom 真跑一遍（scripts/test_site_js.mjs），
          确认契约钩子确实驱动得了行为。**缺 node/jsdom 是 error，不是跳过**——
          与 F3 同一条规矩：跑不起来的校验等于没有校验。
    """
    shell = {"topbar": '<header class="site-topbar">', "sidebar": '<nav class="site-sidebar">',
             "footer": '<footer class="site-footer">'}
    anchor_ids = list(SHELL_ANCHORS)
    # 自比对：生成器 build_html.section_anchors() 的清单必须与上面的契约常量一致，
    # 否则"校验器认的"和"生成器产出的"会各说各话（这类分叉肉眼看不出来）。
    try:
        import build_html as _BH
        gen = [a for a, _n, _i, _h in _BH.section_anchors()]
        if gen != anchor_ids:
            err("数学二/scripts", 0, "F22",
                "生成器与校验器的六段锚点清单不一致：%s vs %s" % (gen, anchor_ids))
    except ImportError:
        pass
    for f in sorted(glob.glob(os.path.join(CONTENT, "*", "*.html"))
                    + glob.glob(os.path.join(CONTENT, "*.html"))):
        rp = rel(f)
        body = open(f, encoding="utf-8").read()
        for what, needle in shell.items():
            if needle not in body:
                err(rp, 0, "F22", "外壳缺少 %s（契约类名 %s）" % (what, needle))
        if '<nav class="tb-crumbs"' not in body:
            err(rp, 0, "F22", "顶栏缺少面包屑 .tb-crumbs")
        if 'class="tb-brand"' not in body or 'class="tb-search"' not in body:
            err(rp, 0, "F22", "顶栏缺少 .tb-brand 或 .tb-search")
        for cls in re.findall(r'<nav class="tb-crumbs".*?</nav>', body, re.S):
            # 面包屑至少一项，最后一项必须是带 aria-current 的当前位置；
            # 多于一项时必须有 .tb-sep 分隔（首页只有"首页"一项，此时不需要分隔符）。
            n_items = len(re.findall(r"<a\b", cls)) + len(re.findall(r"aria-current=", cls))
            if n_items < 1:
                err(rp, 0, "F22", "面包屑是空的")
            if n_items > 1 and 'class="tb-sep"' not in cls:
                err(rp, 0, "F22", "面包屑多于一项却没有层级分隔符 .tb-sep")
            if "aria-current" not in cls:
                err(rp, 0, "F22", "面包屑最后一项缺少 aria-current（当前位置标记）")
        # 章节页：正文底部翻页 + 六段锚点
        stem = os.path.basename(f)[:-5]
        is_chapter = any(stem == t[6] for k in T.ORDER for t in T.TOPICS[k])
        if is_chapter:
            if '<nav class="chapter-nav">' not in body:
                err(rp, 0, "F22", "章节页缺少正文底部翻页 .chapter-nav")
            for cls in ("cn-prev", "cn-next"):
                if 'class="%s' % cls not in body:
                    err(rp, 0, "F22", "章节页翻页缺少 .%s" % cls)
            miss = [a for a in anchor_ids if 'id="%s"' % a not in body]
            if miss:
                err(rp, 0, "F22", "六段锚点缺失：%s（契约 id 必须逐字一致）" % "、".join(miss))
        # 首页：科目卡片入口，卡片数 = 科目数
        if rp == "数学二/index.html":
            if '<nav class="home-subjects"' not in body:
                err(rp, 0, "F22", "首页缺少科目卡片入口 .home-subjects")
            else:
                cards = re.findall(r'<a class="hs-card"[^>]*>(.*?)</a>', body, re.S)
                if len(cards) != len(T.ORDER):
                    err(rp, 0, "F22", "首页科目卡片 %d 张，应为 %d 张"
                        % (len(cards), len(T.ORDER)))
                for c in cards:
                    if 'class="hs-name"' not in c or 'class="hs-meta"' not in c:
                        err(rp, 0, "F22", "科目卡片缺少 .hs-name 或 .hs-meta")
    stats["shell_pages"] = (len(glob.glob(os.path.join(CONTENT, "*", "*.html")))
                            + len(glob.glob(os.path.join(CONTENT, "*.html"))))
    run_site_js_test()


def run_site_js_test():
    """F22 的行为层：node + jsdom 真跑 assets/site.js（scripts/test_site_js.mjs）。"""
    script = os.path.join(CONTENT, "scripts", "test_site_js.mjs")
    hint = ("（装依赖：mkdir -p .tools && "
            "cp 数学二/scripts/tools-package.json .tools/package.json && "
            "npm install --prefix .tools --cache /tmp/npm-cache --no-audit --no-fund）")
    if not os.path.exists(script):
        err("数学二/scripts", 0, "F22", "找不到外壳行为测试脚本 %s%s" % (rel(script), hint))
        return
    if shutil.which("node") is None:
        err("数学二/scripts", 0, "F22", "找不到 node，无法验证外壳行为%s" % hint)
        return
    try:
        r = subprocess.run(["node", script], cwd=ROOT, capture_output=True,
                           text=True, timeout=300)
    except Exception as e:                                   # noqa: BLE001
        err("数学二/assets/site.js", 0, "F22", "调用外壳行为测试失败：%s" % e)
        return
    try:
        data = json.loads(r.stdout)
    except Exception:                                        # noqa: BLE001
        err("数学二/assets/site.js", 0, "F22",
            "外壳行为测试未产出 JSON（返回码 %d）：%s%s"
            % (r.returncode, (r.stderr or r.stdout or "")[-200:], hint))
        return
    if r.returncode != 0:
        err("数学二/assets/site.js", 0, "F22", "外壳行为测试返回码 %d：%s"
            % (r.returncode, str(data.get("error") or r.stderr or "")[:200]))
        return
    stats["shell_js_ok"] = data.get("ok", 0)
    stats["shell_js_total"] = data.get("total", 0)
    for t in data.get("failed", []):
        err("数学二/assets/site.js", 0, "F22",
            "外壳行为测试失败：%s —— %s" % (t.get("name", "?"), str(t.get("error", ""))[:160]))
    if not data.get("total"):
        err("数学二/assets/site.js", 0, "F22",
            "外壳行为测试一条都没跑——等于 F22 的行为层没生效")


def check_external_assets():
    """F23：外置资源（assets/site.css + assets/site.js）真的外置、且处处可达。

    为什么要单独一条：P2 的主要收益就是"别把 13.6 KB CSS 内联进 19 个页面"。
    若谁哪天又把它内联回去，页面上看不出任何异常，但冗余会悄悄涨回来——
    这条规则就是那个"看不出异常"的守卫。
    """
    for name in ("site.css", "site.js"):
        p = os.path.join(ASSETS, name)
        if not os.path.exists(p):
            err("数学二/assets", 0, "F23", "缺少外置资源 %s" % name)
    for f in sorted(glob.glob(os.path.join(CONTENT, "*", "*.html"))
                    + glob.glob(os.path.join(CONTENT, "*.html"))):
        rp = rel(f)
        d = os.path.dirname(f)
        body = open(f, encoding="utf-8").read()
        for attr in re.findall(r'<link[^>]+href="([^"]+)"', body):
            if attr.startswith(("http", "data:")):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(d, attr))):
                err(rp, 0, "F23", "样式表链接不可达：%s" % attr)
        if "assets/site.css" not in body:
            err(rp, 0, "F23", "页面没有引用外置样式 assets/site.css（被内联回去了？）")
        if "assets/site.js" not in body:
            err(rp, 0, "F23", "页面没有引用外置脚本 assets/site.js")
        if "<style" in body:
            err(rp, 0, "F23", "页面出现内联 <style>：样式必须外置到 assets/site.css")
        inline_js = [s for s in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", body)]
        if inline_js:
            err(rp, 0, "F23", "页面出现 %d 段内联 <script>：脚本必须外置到 assets/site.js"
                % len(inline_js))



# ---------------------------------------------------------------------------
# F24 / F25：渲染可读性（用户实拍反馈暴露的两类缺陷）
# ---------------------------------------------------------------------------
INLINE_MATH = re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)")
DISPLAY_MATH = re.compile(r"\$\$.+?\$\$", re.S)
# 解析里单个段落的上限：行内公式 ≤3 个、纯文字 ≤200 字。超过就说明该把公式
# 提成独立成行的 `$$…$$`、或者该把一大段拆成几步（这正是用户截图里的问题）。
MAX_INLINE_PER_PARA = 3
MAX_PARA_TEXT = 200


def _strip_math(text):
    """去掉 `$$…$$` 与 `$…$`，用于统计"纯文字"长度。"""
    return INLINE_MATH.sub("", DISPLAY_MATH.sub("", text))


def _blockquote_paras(lines):
    """按 Markdown 规则把 `>` 行合并成段落：**相邻的非空 `>` 行属于同一段**。

    这正是 P2 之后暴露的那个缺陷的成因：`> 1. …` / `> 2. …` 不写空 `>` 行时，
    渲染出来是**一个** `<p>`，几十个公式连成一坨。所以在内容源阶段就按同一规则
    合并，才能让写手在 build 之前看到真实的分段结果。
    """
    paras, cur = [], []
    for ln in lines:
        if not ln.startswith(">"):
            if cur:
                paras.append(" ".join(cur)); cur = []
            continue
        body = ln[1:].strip()
        if body:
            cur.append(body)
        elif cur:
            paras.append(" ".join(cur)); cur = []
    if cur:
        paras.append(" ".join(cur))
    return paras


def check_render_leftovers(text, path, code, mode):
    """F24：渲染后不得残留字面 Markdown 记号（`**`）。

    为什么要有：`**错在…。**正确做法` 这种写法里，闭合定界符前面是句号、
    后面紧跟汉字，按 CommonMark 的侧翼规则**无法闭合**，于是页面上直接露出
    `**`（用户实拍截图发现，全库 14 处）。这类错误在源文件里看起来完全正常，
    只有渲染出来才看得见——所以既要在成品 HTML 上查，也要在内容源上查。
    """
    if mode == "html":
        body = re.sub(r"<pre.*?</pre>|<code.*?</code>|<script.*?</script>|<style.*?</style>",
                      "", text, flags=re.S)
        body = body[body.find("<main>"):] if "<main>" in body else body
    else:
        # 内容源：按真实流水线渲染一遍（先保护公式，再交给 Markdown）
        try:
            import markdown as _md
        except ImportError:
            return
        prot, _unprotect = protect_math_for_check(text)
        body = _md.markdown(prot, extensions=["tables", "fenced_code", "sane_lists"])
    body = DISPLAY_MATH.sub("", body)          # 公式区间里的 `*` 是合法的（如 A^{*}）
    body = INLINE_MATH.sub("", body)
    n = body.count("**")
    if n:
        err(path, 0, code, "渲染后残留字面 `**` %d 处（加粗定界符没能闭合，"
                           "页面上会直接显示星号）" % n)


def protect_math_for_check(text):
    """给 F24 的内容源检查用：把公式换成占位符（与 build_html 的做法一致）。"""
    store = []

    def stash(m):
        store.append(m.group(0))
        return "@@M%d@" % (len(store) - 1)

    text = re.sub(r"\$\$.*?\$\$", stash, text, flags=re.S)
    text = re.sub(r"\$[^$\n]+?\$", stash, text)
    return text, lambda h: h


def check_solution_layout(paras, path, code):
    """F25：真题示例的解析必须"一步一段 + 关键公式独立成行"。

    判据（对解析块里的每个段落）：
      (a) 行内公式 ≤ MAX_INLINE_PER_PARA 个——超了就该把大公式提出来；
      (b) 纯文字 ≤ MAX_PARA_TEXT 字——超了就该拆成几步。
    用户实拍的正是最坏情况：一整段 715 字、24 个行内公式，手机上没法读。
    """
    for i, para in enumerate(paras, 1):
        body = DISPLAY_MATH.sub("", para)
        n = len(INLINE_MATH.findall(body))
        txt = len(re.sub(r"\s+", "", _strip_math(body)))
        if n > MAX_INLINE_PER_PARA:
            err(path, 0, code, "解析第 %d 段有 %d 个行内公式（上限 %d）："
                               "请把大公式提成独立成行的 `$$…$$`"
                % (i, n, MAX_INLINE_PER_PARA))
        if txt > MAX_PARA_TEXT:
            err(path, 0, code, "解析第 %d 段纯文字 %d 字（上限 %d）："
                               "请拆成几步，每步一个 `>` 段落"
                % (i, txt, MAX_PARA_TEXT))
        # 「1. … 2. … 3. …」挤在同一段 = 步骤没有分行（用户实拍指出的正是这个）。
        # 判据放在这里而不是靠上面的字数上限：一段可以很短却仍塞着两个编号。
        # 注意别写成 `(?:^|\s)\d+\.`：中文里编号前面是「。」不是空格，
        # 那样写会漏掉「…定理。2. 下一步」这种真实写法（第一版就漏了）。
        steps = len(re.findall(r"(?<![\d.])\d+\.\s", _strip_math(body)))
        if steps >= 2:
            err(path, 0, code, "解析第 %d 段把 %d 个步骤编号挤在同一段："
                               "请一步一段（编号之间留空 `>` 行）" % (i, steps))


# ---------------------------------------------------------------------------
# F26：元校验（PLAN-对齐与改版 §4.4—§4.6）—— 让「假通过」不可能
#
# 为什么要有这一条：本项目已经踩过三次同一个坑——
#   ① F3 的解析器脚本丢了，校验却仍报「通过」（失败路径写成了 warn）；
#   ② F20 的 `$$` 判据一直是假通过（被内联脚本里的 '$$' 字面量满足）；
#   ③ 反向测试的判据「输出里出现 [Fxx]」在规则本身有既存报错时会蒙对。
# 三次的共同点是：**校验项看起来在跑，其实在自欺**。所以这条规则检查的不是内容，
# 而是"校验体系自己"：规则集合与反向测试覆盖集合是否相等、扫描型规则是否真看了东西、
# 文档与 CI 里有没有写死会漂移的规则范围。
# ---------------------------------------------------------------------------

# H3：扫描型规则 → 它报告的「受检对象数」统计键。这些数必须 > 0，否则规则在空转。
SCANNED_BOTH_MODES = [
    ("assets", "F18 扫到的图片资产"),
    ("figs", "F18 扫到的绘图脚本"),
]
SCANNED_FULL_ONLY = [
    ("html_math", "F20 扫到的公式区间"),
    ("shell_pages", "F22 扫到的外壳页"),
    ("shell_js_total", "F22 跑到的 site.js 行为断言"),
]
SCANNED_WITH_MERMAID = ("mermaid_blocks", "F3 扫到的 mermaid 图块")

# H4：这些文件里**不许**硬编码 F 范围（真实范围由本脚本输出）。
# 确需引用历史范围时，在那一行里写上「（历史）」即可豁免。
RANGE_DECL_FILES = [
    "AGENTS.md",
    ".github/workflows/pages.yml",
    "数学二/README.md",
    "数学二/scripts/PARTS_FORMAT.md",
    "数学二/scripts/REVERSE_TESTS.md",
    "数学二/scripts/build_readme.py",
]
RANGE_RE = re.compile(r"F(\d+)\s*[—\-~～]\s*F?(\d+)")





def _rules_with_error_path(src):
    """用 **AST** 判断每条规则是否存在 err(...) 路径（比文本启发式可靠）。

    为什么必须用 AST：第一版是文本启发式（"字面量前面最近一次调用是不是 err("），
    结果被**本函数自己的文档字符串**骗过——docstring 里写了示例
    `err(…, "F24", …)`，于是任何降级都判不出来。AST 只认真正的调用节点，
    注释与文档字符串天然被忽略。

    认三种写法：
      ① `err(…, "F24", …)`                    —— 直接形式
      ② `check_xxx(…, "F24", …)` 且该函数体里有 err(  —— 间接形式（F24/F25 是这种）
      ③ 辅助函数用变量 `code` 转发到 err(      —— 由 ② 覆盖
    返回 {规则码: True}。
    """
    tree = ast.parse(src)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    def call_name(c):
        f = c.func
        if isinstance(f, ast.Name):
            return f.id
        return f.attr if isinstance(f, ast.Attribute) else None

    def codes_of(c):
        return [a.value for a in c.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
                and re.fullmatch(r"F\d+", a.value)]

    func_has_err = {name: any(call_name(c) == "err"
                              for c in ast.walk(node) if isinstance(c, ast.Call))
                    for name, node in funcs.items()}
    out = {}
    for c in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        nm = call_name(c)
        for code in codes_of(c):
            if nm == "err" or (nm and nm != "warn" and func_has_err.get(nm)):
                out[code] = True
    return out

def check_meta(parts_mode, mermaid_skipped=False):
    """F26：H2 规则集合 ≡ 覆盖集合；H3 扫描型受检数 > 0；H4 不硬编码规则范围。"""
    # ---- H2：规则集合 vs 反向测试覆盖集合（用集合比较，不假设编号连续）----
    self_src = open(os.path.join(HERE, "validate.py"), encoding="utf-8").read()
    rules = set(re.findall(r'"F(\d+)"', self_src))
    rt = os.path.join(HERE, "reverse_tests.py")
    cover = set()
    if not os.path.exists(rt):
        err("数学二/scripts", 0, "F26",
            "找不到反向测试脚本 reverse_tests.py：门禁少了「规则本身有效」这一层")
    else:
        cover = set(re.findall(r'case\(\s*"F(\d+)"', open(rt, encoding="utf-8").read()))
    missing = sorted(rules - cover, key=int)
    if missing:
        err("数学二/scripts", 0, "F26",
            "有 %d 条校验规则没有被反向测试覆盖：%s"
            % (len(missing), "、".join("F" + x for x in missing)))
    extra = sorted(cover - rules, key=int)
    if extra:
        err("数学二/scripts", 0, "F26",
            "反向测试引用了不存在的规则：%s" % "、".join("F" + x for x in extra))
    # 每条规则在源码里至少要有一处 err(...)：只有 warn(...) 的"规则"永远拦不住发布，
    # 而它照样能被反向测试的旧判据（找 `[Fxx]` 字样）判成"已报错"。
    # 这是实测到的假通过：把 F24 的 err 改成 warn，61 条用例全绿、发布照走。
    # 静态检查比动态自测更可靠：不用构造场景，改坏就报。
    have_err = _rules_with_error_path(self_src)
    for code in sorted(rules, key=int):
        if ("F" + code) not in have_err:
            err("数学二/scripts", 0, "F26",
                "规则 F%s 在 validate.py 里没有 err(...) 调用——只 warn 拦不住发布，不算规则"
                % code)
    stats["rules_with_err"] = sum(1 for c in rules if ("F" + c) in have_err)
    stats["rules"] = len(rules)
    stats["rules_covered"] = len(rules & cover)
    if rules:
        stats["rule_min"] = min(rules, key=int)
        stats["rule_max"] = max(rules, key=int)

    # ---- H3：扫描型规则的受检对象数必须 > 0 ----
    keys = list(SCANNED_BOTH_MODES)
    if not parts_mode:
        keys += SCANNED_FULL_ONLY
    if not mermaid_skipped:
        keys.append(SCANNED_WITH_MERMAID)
    zero = ["%s（stat=%s）" % (label, k) for k, label in keys if stats.get(k, 0) <= 0]
    if zero:
        err("数学二/scripts", 0, "F26",
            "扫描型规则在空转（受检对象数为 0，等于什么都没查）：%s" % "；".join(zero))
    stats["scanned_checked"] = len(keys)

    # ---- H4：文档/CI 里不得硬编码 F 范围 ----
    lo, hi = stats.get("rule_min", "?"), stats.get("rule_max", "?")
    n_decl = 0
    for rel_p in RANGE_DECL_FILES:
        fp = os.path.join(ROOT, rel_p)
        if not os.path.exists(fp):
            err(rel_p, 0, "F26", "H4 清单里的文件不存在（清单本身过期了）")
            continue
        for i, ln in enumerate(open(fp, encoding="utf-8").read().split("\n"), 1):
            if "（历史）" in ln:          # 显式标注的历史引用，豁免
                continue
            m = RANGE_RE.search(ln)
            if m:
                n_decl += 1
                err(rel_p, i, "F26",
                    "文档/CI 里不得硬编码 F 范围（%s）：真实范围由 validate.py 输出为 "
                    "F%s—F%s；确需引用历史范围请在该行标注「（历史）」" % (m.group(0), lo, hi))
    stats["declared_ranges"] = n_decl


def check_completeness():
    """F16：交付物完整性——不得静默缺失。"""
    need = [os.path.join(CONTENT, "README.md"), os.path.join(CONTENT, "index.html")]
    for k in T.ORDER:
        need.append(os.path.join(CONTENT, T.SUBJECTS[k]["dir"], "00-科目总览.md"))
        for t in T.TOPICS[k]:
            need.append(os.path.join(CONTENT, T.SUBJECTS[k]["dir"], t[6] + ".md"))
    for p in need:
        if not os.path.exists(p):
            err(rel(p), 0, "F16", "交付物缺失")


# ---------------------------------------------------------------------------
def report(title):
    print("=" * 78)
    print(title)
    print("=" * 78)
    for k in sorted(per_file):
        v = per_file[k]
        print("  %-42s 节 %2d | ASCII %2d | mermaid %2d | 图 %2d | %6d 字"
              % (k, v["sections"], v["text"], v["mermaid"], v["img"], v["chars"]))
    print("-" * 78)
    print("  文件 %d | 知识点 %d | ASCII 图 %d | mermaid 图 %d | 图片 %d | 总 %d 字"
          % (len(per_file), stats["sections"], stats["text_figs"], stats["mermaid"],
             stats["img"], stats["chars"]))
    print("  HTML 公式区间 %d 个 | 高频 %d | 原题 %d 道（正文标注 %d 处，含跨章复用） | 改编 %d 道 | "
          "mermaid 真实解析通过 %d 块 | 绘图脚本 %d 个"
          % (stats.get("html_math", 0), stats["hot"],
             stats.get("orig", 0), stats.get("orig_cites", 0),
             stats.get("adapt", 0), stats.get("mermaid_parsed", 0), stats.get("figs", 0)))
    # 外壳行为测试跑了几条也要打出来：**"0 条"必须看得见**，否则 F22 的行为层
    # 会像 F3 曾经那样"静默没跑却显示全绿"。
    print("  外壳页 %d 个 | site.js 行为测试通过 %d/%d 条"
          % (stats.get("shell_pages", 0), stats.get("shell_js_ok", 0),
             stats.get("shell_js_total", 0)))
    # F26 的体检结果：规则范围、覆盖情况、扫描型受检数、文档里的范围声明数。
    # 「范围」只在这里输出——文档与 CI 一律不要手写（手写的必然漂移，已漂过一次）。
    print("  ★ 规则 F%s—F%s（%d 条，%d 条有 err 路径）｜反向测试覆盖 %d/%d"
          "｜扫描型受检数 %d 项｜文档/CI 范围声明 %d 处"
          % (stats.get("rule_min", "?"), stats.get("rule_max", "?"), stats.get("rules", 0),
             stats.get("rules_with_err", 0),
             stats.get("rules_covered", 0), stats.get("rules", 0),
             stats.get("scanned_checked", 0), stats.get("declared_ranges", 0)))
    print("-" * 78)
    if errors:
        print("  ✗ 错误 %d 条：" % len(errors))
        # 不截断错误列表：截断会让"某条规则是否报错"无法判断，
        # 反向测试也会因此误判成"校验器失效"（曾把上限设成 100 而踩到）。
        for e in errors:
            print("    " + e)
    else:
        print("  ✓ 全部强制校验项通过")
    if warnings:
        print("  ! 警告 %d 条：" % len(warnings))
        for w in warnings[:30]:
            print("    " + w)
    print("=" * 78)
    return 1 if errors else 0


def main():
    argv = sys.argv[1:]
    parts_mode = "--parts" in argv
    mermaid_blocks = []

    if not parts_mode:
        check_completeness()
        for k in T.ORDER:
            d = os.path.join(CONTENT, T.SUBJECTS[k]["dir"])
            if not os.path.isdir(d):
                err("数学二/%s" % T.SUBJECTS[k]["dir"], 0, "F0", "部分目录不存在")
                continue
            files = sorted(f for f in os.listdir(d) if f.endswith(".md"))
            got = {os.path.splitext(f)[0] for f in files}
            want = {t[6] for t in T.TOPICS[k]}
            for s in sorted(want - got):
                err("数学二/%s" % T.SUBJECTS[k]["dir"], 0, "F0", "缺少章节文件 %s.md" % s)
            for s in sorted(got - want - {"00-科目总览"}):
                warn("数学二/%s" % T.SUBJECTS[k]["dir"], 0, "F0", "未登记章节文件 %s.md" % s)
            for f in files:
                validate_file(os.path.join(d, f), k,
                              is_overview=f.startswith("00-"), mermaid_blocks=mermaid_blocks)
        stats["hot"] = sum(1 for _, t in T.all_topics() if t[5])
        check_readme_citations()
        check_links()
        check_html()
        check_html_math_and_nav()
        check_html_headings()
        check_shell()               # F22：外壳骨架（形式层 + site.js 行为层）
        check_external_assets()     # F23：外置样式/脚本真的外置且可达
    else:
        for k in T.ORDER:
            for t in T.TOPICS[k]:
                p = os.path.join(PARTS, k, t[6] + ".md")
                if not os.path.exists(p):
                    err("parts/%s" % k, 0, "F0", "缺少内容源 %s.md" % t[6])
                    continue
                validate_partial(k, t, p, mermaid_blocks)
                # F24 / F25 在内容源阶段就跑一遍：写手改完 parts 立刻能看到，
                # 不必等 build 之后才发现（与 F3 扫描根随模式走是同一个道理）。
                raw = open(p, encoding="utf-8").read()
                check_render_leftovers(raw, os.path.relpath(p, ROOT), "F24", "parts")
                m = re.search(r"(?m)^# 真题示例\s*$", raw)
                if m:
                    tail = raw[m.end():].split("\n")
                    # 真题示例必须给出 `> 解析：…` 引用块；没有的话下面的排版检查
                    # 会"无段落可查"而静默通过——静默通过比报错更危险。
                    if not any(ln.startswith(">") for ln in tail):
                        err(os.path.relpath(p, ROOT), 0, "F25",
                            "真题示例里没有 `> 解析：…` 引用块（模板要求逐条给解析）")
                    bq = []
                    started = False
                    for ln in tail:
                        if ln.startswith(">"):
                            started = True; bq.append(ln)
                        elif started and ln.strip():
                            break
                    check_solution_layout(_blockquote_paras(bq),
                                          os.path.relpath(p, ROOT), "F25")
        stats["hot"] = sum(1 for _, t in T.all_topics() if t[5])

    check_figs()                           # F18：两种模式都要跑

    mermaid_skipped = "--no-mermaid" in argv
    if not mermaid_skipped:
        run_mermaid_parser(PARTS if parts_mode else CONTENT)

    # F26 元校验放在最后：它要读前面各条规则报告的受检对象数
    check_meta(parts_mode, mermaid_skipped=mermaid_skipped)

    if "--json" in argv:
        # 机器可读输出：**errors 与 warnings 必须分开**。
        # 反向测试原来靠正则找 `[Fxx]` 字样，分不清这两者——把一条规则从 error
        # 降级成 warn（= 门禁不再拦它）时，用例照样"通过"。这就是 P4 要消灭的假通过。
        print(json.dumps({"errors": errors, "warnings": warnings,
                          "stats": dict(stats), "parts_mode": parts_mode},
                         ensure_ascii=False))
        return 1 if errors else 0

    if "--stats" in argv:
        for k, v in sorted(per_file.items()):
            print("%-44s %s" % (k, v))
        return 0
    return report("数学二速成资料校验报告（%s）" % ("内容源 parts/" if parts_mode else "成品"))


if __name__ == "__main__":
    sys.exit(main())
