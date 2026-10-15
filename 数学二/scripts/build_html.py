#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `数学二/` 下的 Markdown 渲染成可离线阅读的 HTML 站点。

产出
----
  数学二/<部分>/<章节>.html      每章一页（带侧栏）
  数学二/<部分>/index.html       部分首页（章节索引）
  数学二/index.html              全科单页合集（高数 + 线代全部内容）
  数学二/README.html             总览

要点
----
- **图片正确引用**：正文里的 `assets/xxx.png` 在子目录页面要变成 `../assets/xxx.png`，
  在根页面保持 `assets/xxx.png`。层级数一律用 `os.path.relpath` 现算，不手写 `../`。
- **Mermaid 离线可用**：把 `mermaid.min.js` 复制到 `数学二/`，页面用相对路径引入；
  浏览器端渲染。若运行时缺失，页面会**明确提示**并回退为源码，不静默留白。
- **缺失资源要提示**：渲染前先检查每个 md 引用的图片是否存在，缺失则在页面顶部
  列出警告框（`<p class="warn">`），而不是留白。
- **不把大文件内联进每个页面**：CSS/JS 各自只有一份（内联一份小 CSS，mermaid 用外部文件）。

用法： python3 数学二/scripts/build_html.py
"""
import html
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import meta as T          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
CONTENT = os.path.join(ROOT, "数学二")
MERMAID_SRC = os.path.join(ROOT, ".tools", "node_modules", "mermaid", "dist", "mermaid.min.js")
KATEX_DIR = os.path.join(ROOT, ".tools", "node_modules", "katex", "dist")
KATEX_DST = os.path.join(CONTENT, "katex")

try:
    import markdown
except ImportError:
    sys.exit("需要 python-markdown：%s -m pip install markdown" % sys.executable)

# 样式与脚本**外置**：两者都在 数学二/assets/ 下，随 pack_site.py 的 assets 目录一起发布。
# 类名与 DOM 结构是与 408 项目共用的契约（PLAN-对齐与改版 §2.4）；
# 行为脚本 assets/site.js 由两个项目共用同一份，改动它必须同步通知另一个项目。
SITE_CSS = "assets/site.css"
SITE_JS = "assets/site.js"
SITE_NAME = "考研数学二速成资料"



def protect_math(text):
    """把数学区间替换成占位符，避免 Markdown 把公式里的 * _ ^ 吃成强调标签。

    为什么必须做：Python-Markdown 会把 `$AA^{*}=A^{*}A$` 渲染成
    `$AA^{<em>}=A^{</em>}A$` —— 两个 `*` 被当成强调标记，公式彻底损坏。
    KaTeX 拿到的必须是原样的 `*`，所以要在 Markdown 处理前把公式整段藏起来。

    返回 (被保护的文本, 还原函数)。
    """
    store = []
    # 先 $$...$$（含跨行），再 $...$（不跨行、非空）
    text = re.sub(r"\$\$.*?\$\$",
                  lambda m: _stash(store, m.group(0)), text, flags=re.S)
    text = re.sub(r"\$[^$\n]+?\$",
                  lambda m: _stash(store, m.group(0)), text)
    return text, lambda h: _restore(h, store)


# 占位符必须是「Markdown 不会动它」的纯可见 ASCII：
# 实测 \x01…\x02 里的 \x02 会被 Python-Markdown 直接丢掉（C0 控制字符），
# 导致占位符只剩前半截、还原失败。改用 @@MATH0@@ 这种形态。
PLACEHOLDER = "@@MATH%d@@"


def _stash(store, chunk):
    store.append(chunk)
    return PLACEHOLDER % (len(store) - 1)


def _restore(html_text, store):
    """把占位符换回数学源码。

    用正则而不是 str.replace：Markdown 会在占位符两侧插入换行/空白
    （例如把块级公式包成 <p>\n占位符\n</p>），逐字替换会整片漏掉，
    之前就是这样导致 81 处公式只剩 \x01M… 控制字符。
    """
    def put(m):
        k = int(m.group(1))
        return store[k] if 0 <= k < len(store) else m.group(0)
    return re.sub(r"@@MATH(\d+)@@", put, html_text)


def md_to_html(text, depth, missing):
    """Markdown → HTML。depth 为当前页面相对 `数学二/` 的层级（0 或 1）。

    `assets/xxx.png` 与 `mermaid.min.js` 的相对前缀按 depth 现算。
    """
    prefix = "../" * depth
    blocks = []

    def stash(m):
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        if lang == "mermaid":
            blocks.append(
                '<div class="mermaid">%s</div>'
                '<details><summary>查看该图源码</summary><pre><code>%s</code></pre></details>'
                % (html.escape(code), html.escape(code)))
        else:
            cls = ' class="ascii"' if lang == "text" else ""
            blocks.append("<pre%s><code>%s</code></pre>" % (cls, html.escape(code)))
        return "\x00B%d\x00" % (len(blocks) - 1)

    text = re.sub(r"```(\w*)\n(.*?)```", stash, text, flags=re.S)

    # 保护数学区间，防止 Markdown 把公式里的 * _ ^ 当强调标记吃掉
    text, unprotect = protect_math(text)

    # 图片路径：正文按「相对 数学二/」书写；本页在 数学二/ 下则去掉前缀，
    # 在 数学二/<部分>/ 下则加 "../"。层级数由 depth 现算，不手写。
    def fix_img(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http", "data:")):
            return m.group(0)
        rel_src = src if not prefix else os.path.normpath(os.path.join(prefix, src))
        return "![%s](%s)" % (alt, rel_src.replace(os.sep, "/"))

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", fix_img, text)

    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = unprotect(body)
    for i, b in enumerate(blocks):
        body = body.replace("<p>\x00B%d\x00</p>" % i, b)
        body = body.replace("\x00B%d\x00" % i, b)
    return body


def crumbs_html(trail):
    """面包屑：[(文字, href 或 None), …]；最后一项是当前页（无链接、带 aria-current）。"""
    out = ['<nav class="tb-crumbs" aria-label="面包屑">']
    for i, (text, href) in enumerate(trail):
        if i:
            out.append('<span class="tb-sep">›</span>')
        if href:
            out.append('<a href="%s">%s</a>' % (html.escape(href), html.escape(text)))
        else:
            out.append('<span aria-current="page">%s</span>' % html.escape(text))
    out.append('</nav>')
    return "".join(out)


def topbar(brand, brand_href, trail):
    """顶栏（契约 .site-topbar / .tb-brand / .tb-crumbs / .tb-sep / .tb-search）。

    `.tb-search` 在 P2 是"聚焦侧栏筛选框"的入口（见 assets/site.js），不是死按钮；
    P3 的离线全文检索落地后换成检索面板，类名不变。
    """
    return ('<header class="site-topbar">'
            '<a class="tb-brand" href="%s">%s</a>%s'
            '<button class="tb-search" type="button" aria-label="搜索">搜索</button>'
            '</header>' % (html.escape(brand_href), html.escape(brand),
                           crumbs_html(trail)))


def footer_html(depth):
    """页脚（契约 .site-footer）：许可、数据口径、返回顶部。"""
    prefix = "../" * depth
    return (
        '<footer class="site-footer"><div class="sf-inner">'
        '<p><strong>%s</strong> · 文字与插图 CC BY-NC-SA 4.0（禁止商业使用）· 代码 MIT'
        ' · 第三方组件见 <a href="%sTHIRD-PARTY.md">THIRD-PARTY.md</a></p>'
        '<p>考频数据基于 2023—2024 年数二真题逐题统计，样本量小，'
        '仅用于区分必考主线与偶发考点；无法核实的一律标注「考频待补充」，'
        '口径见 <a href="%sREADME.html">总览</a>。</p>'
        '<p>完全离线静态页：公式由本地 KaTeX 渲染，图由本地 mermaid 渲染，断网可用。'
        ' · <a href="#top">↑ 返回顶部</a></p>'
        '</div></footer>' % (SITE_NAME, prefix, prefix))


def chapter_nav(prev_href, next_href, prev_title, next_title):
    """章节页正文底部的上一章/下一章（契约 .chapter-nav / .cn-prev / .cn-next）。"""
    prev_cls = "cn-prev" + ("" if prev_href else " off")
    next_cls = "cn-next" + ("" if next_href else " off")
    return ('<nav class="chapter-nav">'
            '<a class="%s" href="%s" title="键盘 ← 或 k">← %s</a>'
            '<a class="%s" href="%s" title="键盘 → 或 j">%s →</a>'
            '</nav>' % (prev_cls, html.escape(prev_href or "#"),
                        html.escape(prev_title or "已是第一章"),
                        next_cls, html.escape(next_href or "#"),
                        html.escape(next_title or "已是最后一章")))


def page(title, sidebar_html, body, depth, extra_warn="", topbar_html="",
         data_prev="", data_next="", with_progress=True):
    """整页外壳（契约 §2.3）：顶栏 → .site-body（侧栏 + main）→ 页脚。

    样式与脚本一律**外置**（assets/site.css / assets/site.js），相对前缀按 depth 现算；
    site.js 在 <head> 里**同步**引入——主题类要在首屏绘制前定下来，否则会闪白。
    """
    prefix = "../" * depth
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<link rel="stylesheet" href="%s%s">
<link rel="stylesheet" href="%skatex/katex.min.css">
<script src="%s%s"></script>
<script src="%skatex/katex.min.js"></script>
<script src="%skatex/contrib/auto-render.min.js"></script>
<script src="%smermaid.min.js"></script>
</head>
<body data-prev="%s" data-next="%s">
<a id="top"></a>
%s<button class="nav-toggle" type="button">☰ 目录</button>
%s<div class="site-body"><nav class="site-sidebar">%s</nav><main><div class="inner">%s%s</div></main></div>
%s<button class="to-top" type="button">↑ 回到顶部</button>
<button class="theme-toggle" type="button" title="切换深色/浅色">◐ 主题</button>
</body></html>""" % (
        html.escape(title),
        prefix, SITE_CSS, prefix,
        prefix, SITE_JS, prefix, prefix, prefix,
        html.escape(data_prev), html.escape(data_next),
        '<div class="read-progress"></div>' if with_progress else "",
        topbar_html, sidebar_html, extra_warn, body, footer_html(depth))


def sidebar(depth, current=None, single_page=False, toc=None):
    """左侧导航（契约 .site-sidebar / .sb-head / .sb-filter / .sb-group / .sb-chap / .toclink）。

    toc: 当前章节的 [(锚点, 小节名)]，用于在侧栏展开「本章小节」跳转列表。
         小节 = 模板六个字段（考频统计/核心讲解/…），由 build() 生成。
    """
    prefix = "../" * depth
    home = ('<a class="sb-home" href="#top">回到顶部</a>' if single_page
            else '<a class="sb-home" href="%sindex.html">全科合集</a>' % prefix)
    out = ['<div class="sb-head"><span class="sb-title">%s</span>%s</div>'
           % (html.escape(SITE_NAME), home)]
    out.append('<input class="sb-filter" type="search" placeholder="筛选章节（输入即过滤）" '
               'aria-label="筛选章节">')
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        grp = ['<div class="sb-group"><div class="sb-group-t">%s（约 %d 分 · %s）</div>'
               % (html.escape(sub["name"]), sub["score"], sub["ratio"])]
        for t in T.TOPICS[k]:
            if single_page:
                href = "#%s-%s" % (k, t[6])
            else:
                href = "%s%s/%s.html" % (prefix, sub["dir"], t[6])
            cls = "sb-chap" + (" cur" if current == t[6] else "")
            grp.append('<a class="%s" href="%s">%s%s</a>'
                       % (cls, href, html.escape(t[0]),
                          ' <span class="tag">高频</span>' if t[5] else ""))
            # 当前章节展开小节跳转
            if toc and current == t[6] and not single_page:
                box = "".join('<a class="toclink" href="#%s">%s</a>'
                              % (aid, html.escape(name))
                              for aid, name, _ic, _h in toc)
                grp.append('<div class="tocbox">%s</div>' % box)
        grp.append('</div>')
        out.append("".join(grp))
    return "\n".join(out)


def home_subjects(depth=0):
    """首页的科目卡片入口（契约 .home-subjects / .hs-card / .hs-name / .hs-meta）。

    以前首页指向科目目录的链接是 **0 条**：读者从单页合集跳不到分科首页。
    """
    prefix = "../" * depth
    cards = ['<nav class="home-subjects" aria-label="分科入口">']
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        cards.append(
            '<a class="hs-card" href="%s%s/index.html">'
            '<span class="hs-name">%s</span>'
            '<span class="hs-meta">%d 章 · 约 %d 分 · %s</span></a>'
            % (prefix, sub["dir"], html.escape(sub["name"]),
               len(T.TOPICS[k]), sub["score"], sub["ratio"]))
    cards.append('</nav>')
    return "".join(cards)



def section_anchors():
    """模板六字段 → 章节内锚点 / 图标 / 副标题。"""
    return [("sec-freq", "考频统计", "📊", "历年命题分布"),
            ("sec-core", "核心讲解", "📖", "定义 · 公式 · 适用条件"),
            ("sec-key", "关键结论速记", "⚡", "考前最后扫一眼"),
            ("sec-fig", "示意图", "📐", "几何直观与判定流程"),
            ("sec-err", "易错点", "⚠️", "错在哪 · 正确是什么"),
            ("sec-real", "真题示例", "🎯", "题干 · 解析")]


def structure_sections(body, base=2):
    """把六个模板字段包成带样式的区块，提升可读性。

    Markdown 渲染后，六个字段各是一个 <p>（如 `<p><strong>核心讲解</strong>：</p>`）。
    做法：先给这些 <p> 打上 id，再按它们的位置把正文切成 6 段，
    每段外面套 `<section class="sec sec-xxx">` 并生成小标题栏。

    注意切片必须覆盖**整个** <p>…</p>（含闭合标签），否则段落会残缺——
    之前只匹配到开标签，导致每页多出三个未闭合的 <p>。
    """
    def strip_label(html_text):
        """删掉字段段落开头的「**字段名**：」标签。

        字段名已经在区块标题栏里显示，正文再出现一次就是"同一行字看两遍"。
        只删第一个 <p> 里的那一个 <strong>。
        """
        return re.sub(r"^(\s*)<p[^>]*>\s*<strong>[^<]+</strong>：?\s*",
                      r"\1<p>", html_text, count=1)

    def demote(html_text):
        """把字段内的 ##/### 降级到 base 之下，保持文档大纲正确。

        正文里的 `##` 是「模块」、`###` 是「子模块」；字段标题本身占一级，
        所以模块应落在 base+1、子模块 base+2。
        """
        # ## → base+1（模块），### → base+2（子模块）；
        # 注意是 base+1 而不是 base：模块必须比字段标题**深一级**，
        # 早先写成 base-1+1 导致章节页里模块与字段标题同为 h2、层级压平。
        html_text = re.sub(r"<h([23])>", lambda m: "<h%d>" % (int(m.group(1)) + base - 1),
                           html_text)
        html_text = re.sub(r"</h([23])>", lambda m: "</h%d>" % (int(m.group(1)) + base - 1),
                           html_text)
        return html_text

    marks = []
    for aid, name, _ic, _hint in section_anchors():
        pat = r'<p>(<strong>%s</strong>.*?)</p>' % re.escape(name)
        m = re.search(pat, body, re.S)
        if not m:
            continue
        marks.append((m.start(), m.end(), aid, name))
        body = body[:m.start()] + '<p id="%s">%s</p>' % (aid, m.group(1)) + body[m.end():]
    if not marks:
        return body

    # 打上 id 后重新定位（字符串长度变了，但位置按新串重新求）
    spans = []
    for aid, name, _ic, _hint in section_anchors():
        m = re.search(r'<p id="%s">.*?</p>' % aid, body, re.S)
        if m:
            spans.append((m.start(), m.end(), aid, name))

    out, cursor = [], 0
    for idx, (st, en, aid, name) in enumerate(spans):
        out.append(body[cursor:st])
        end = spans[idx + 1][0] if idx + 1 < len(spans) else len(body)
        ic, hint = next((i, h) for a2, _n, i, h in section_anchors() if a2 == aid)
        # 区间必须从**字段标签段落本身**开始（st），不能从它之后（en）开始：
        # 从 en 开始会把「**考频统计**：…」这一整段丢在 section 外面，
        # 于是页面上「考频统计」只剩标题、内容整段消失（实测过的严重 bug）。
        out.append(
            '<section class="sec sec-%s" id="%s">'
            '<div class="sec-h"><span class="ic">%s</span>'
            '<h%d class="tt">%s</h%d><span class="hint">%s</span></div>'
            '<div class="box">%s</div></section>'
            % (aid.replace("sec-", ""), aid, ic, base, name, base, hint,
               demote(strip_label(body[st:end]))))
        cursor = end
    out.append(body[cursor:])
    return "".join(out)


def chapter_head(body, name, hot, pts, sub_name):
    """把 `## 名称 [高频]` 换成带头部徽章的章节大标题。"""
    m = re.search(r'<h2>(.*?)</h2>', body, re.S)
    if not m:
        return body, name
    raw = re.sub(r"<[^>]+>", "", m.group(1))
    title = raw.replace("[高频]", "").strip()
    tag = ('<span class="badge hot">高频考点</span>' if hot
           else '<span class="badge">常规考点</span>')
    head = ('<header class="chaphead"><h1>%s</h1><div class="badges">'
            '%s<span class="badge">%s</span><span class="badge">建议 %d 分</span>'
            '</div></header>' % (title, tag, sub_name, pts))
    return body[:m.start()] + head + body[m.end():], title


def collect_missing():
    """检查成品 md 引用的图片是否存在，返回缺失文件名的集合。

    解析基准固定为 `数学二/`（不是 md 文件所在目录）：正文里的 `assets/xxx.png`
    是**相对交付根**写的，HTML 渲染时统一改写成带 `../` 前缀的路径。
    """
    missing = set()
    for f in glob_md():
        text = open(f, encoding="utf-8").read()
        for m in re.finditer(r"!\[[^\]]*\]\((assets/[^)\s]+)\)", text):
            p = os.path.normpath(os.path.join(CONTENT, m.group(1)))
            if not os.path.exists(p):
                missing.add(os.path.basename(m.group(1)))
    return missing


def glob_md():
    out = []
    for k in T.ORDER:
        d = os.path.join(CONTENT, T.SUBJECTS[k]["dir"])
        out.extend(sorted(f for f in __import__("glob").glob(os.path.join(d, "*.md"))))
    return out


def copy_mermaid_runtime():
    if not os.path.exists(MERMAID_SRC):
        print("! 未找到 %s，页面将回退为源码并提示" % os.path.relpath(MERMAID_SRC, ROOT))
        return False
    dst = os.path.join(CONTENT, "mermaid.min.js")
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(MERMAID_SRC):
        shutil.copyfile(MERMAID_SRC, dst)
    print("  已复制 mermaid 运行时 %.1f MB → 数学二/mermaid.min.js"
          % (os.path.getsize(dst) / 1048576.0))
    return True


def copy_katex():
    """把 KaTeX（含字体）复制到 数学二/katex/，让公式渲染完全离线可用。"""
    if not os.path.isdir(KATEX_DIR):
        print("! 未找到 %s，公式将以 LaTeX 源码显示" % os.path.relpath(KATEX_DIR, ROOT))
        return False
    os.makedirs(os.path.join(KATEX_DST, "contrib"), exist_ok=True)
    os.makedirs(os.path.join(KATEX_DST, "fonts"), exist_ok=True)
    for f in ("katex.min.css", "katex.min.js"):
        src = os.path.join(KATEX_DIR, f)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(KATEX_DST, f))
    src = os.path.join(KATEX_DIR, "contrib", "auto-render.min.js")
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(KATEX_DST, "contrib", "auto-render.min.js"))
    n = 0
    fdir = os.path.join(KATEX_DIR, "fonts")
    if os.path.isdir(fdir):
        for f in os.listdir(fdir):
            if f.endswith((".woff2", ".woff", ".ttf")):
                shutil.copyfile(os.path.join(fdir, f),
                                os.path.join(KATEX_DST, "fonts", f))
                n += 1
    print("  已复制 KaTeX 运行时（%d 个字体文件）→ 数学二/katex/" % n)
    return True


def warn_block(missing):
    if not missing:
        return ""
    return ('<p class="missing"><b>资源缺失提示：</b>本页引用了 %d 个不存在的图片文件：%s。'
            '这些位置会显示为空白，请先运行 <code>数学二/scripts/figs/</code> 下的绘图脚本。'
            '</p>' % (len(missing), "、".join(sorted(missing))))


def build():
    missing = collect_missing()
    if missing:
        print("! 有 %d 个被引用的图片不存在：%s"
              % (len(missing), "、".join(sorted(missing))))
    chapters, overviews, n = {}, {}, 0

    # 全局章节顺序（跨部分），用于「上一章 / 下一章」与键盘翻章
    order = [(k, t[6], t[0]) for k in T.ORDER for t in T.TOPICS[k]]

    def href_of(i, k):
        """第 i 章相对当前部分目录的链接（同部分用文件名，跨部分用 ../部分/文件）。"""
        if not (0 <= i < len(order)):
            return ""
        k2, slug2, _ = order[i]
        if k2 == k:
            return slug2 + ".html"
        return "../%s/%s.html" % (T.SUBJECTS[k2]["dir"], slug2)

    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        d = os.path.join(CONTENT, sub["dir"])
        ov = open(os.path.join(d, "00-科目总览.md"), encoding="utf-8").read()
        # 同一个 md 要按两种相对层级各渲染一次：章节页在 数学二/<部分>/ 下（depth=1），
        # 单页合集在 数学二/ 下（depth=0）。**不要复用同一个结果**——复用会让图片路径
        # 在另一种层级下全部失效，而页面照样生成，属于静默错误。
        overviews[(k, 1)] = md_to_html(ov, 1, missing)
        overviews[(k, 0)] = md_to_html(ov, 0, missing)
        for t in T.TOPICS[k]:
            slug = t[6]
            src = open(os.path.join(d, slug + ".md"), encoding="utf-8").read()
            body_chapter, chap_title = chapter_head(
                structure_sections(md_to_html(src, 1, missing)),
                t[0], t[5], t[3], sub["name"])
            body_chapter = re.sub(r"<h1>.*?</h1>", "", body_chapter, count=1, flags=re.S)
            chapters[(k, slug)] = structure_sections(md_to_html(src, 0, missing), base=4)
            i = next(j for j, (kk, ss, _) in enumerate(order) if kk == k and ss == slug)
            prev_href = href_of(i - 1, k)
            next_href = href_of(i + 1, k)
            prev_title = order[i - 1][2] if i > 0 else ""
            next_title = order[i + 1][2] if i + 1 < len(order) else ""
            bar = topbar(sub["name"], "../index.html",
                         [("首页", "../index.html"), (sub["name"], "./index.html"),
                          (t[0], None)])
            body_chapter += chapter_nav(prev_href, next_href, prev_title, next_title)
            with open(os.path.join(d, slug + ".html"), "w", encoding="utf-8") as f:
                f.write(page("%s · %s" % (sub["name"], t[0]),
                             sidebar(1, slug, toc=section_anchors()),
                             body_chapter, 1, warn_block(missing), bar,
                             prev_href, next_href))
            n += 1
        ov_body = re.sub(r"<h1>.*?</h1>", "", overviews[(k, 1)], count=1, flags=re.S)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(page("%s · 考研数学二" % sub["name"], sidebar(1, None),
                         '<header class="bookhead"><h1>%s</h1>'
                         '<p class="lede">%s · 约 %d 分（%s）· %d 章</p></header>%s'
                         % (sub["name"], sub["name"], sub["score"], sub["ratio"],
                            len(T.TOPICS[k]), ov_body),
                         1, warn_block(missing),
                         topbar(sub["name"], "../index.html",
                                [("首页", "../index.html"), (sub["name"], None)])))

    # ---- 全科单页合集 ----
    # 标题层级刻意只保留两级，避免"重复标题"：
    #   h1  —— 全站标题（只出现一次）
    #   h2  —— 部分标题（去掉各 md 自带的那一级，由本函数统一生成）
    #   h3  —— 章节标题（章节正文里的 ## 已被 chapter_head 提升级别后放入）
    parts = ['<header class="bookhead"><h1>考研数学二 · 全科速成复习资料</h1>'
             '<p class="lede">高等数学 9 章 + 线性代数 6 章，共 150 分。'
             '左侧可筛选章节，Ctrl+F 全文检索；键盘 ←/→ 在章节页间翻动。</p></header>',
             home_subjects(0),          # 科目卡片入口（契约 §2.5.1）
             warn_block(missing)]
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        parts.append('<h2 class="parthead" id="part-%s">%s'
                     ' <span class="tag">约 %d 分 · %s</span></h2>'
                     % (k, sub["name"], sub["score"], sub["ratio"]))
        # 单页合集里，科目总览只保留「本章怎么复习」这类**独有**内容：
        #   - 「章节索引」表与左侧导航重复，删掉；
        #   - 「本科目在整卷中的位置」两个科目文字几乎相同，删掉（章节页里保留）。
        # 否则单页里会出现两条一模一样的标题（F21 就是这么抓出来的）。
        body_ov = re.sub(r"<h1>.*?</h1>", "", overviews[(k, 0)], count=1, flags=re.S)
        body_ov = re.sub(
            r"<h2>本科目章节索引</h2>.*?(?=<h2>|\Z)", "", body_ov, flags=re.S)
        body_ov = re.sub(
            r"<h2>本科目在整卷中的位置</h2>.*?(?=<h2>|\Z)", "", body_ov, flags=re.S)
        body_ov = re.sub(r"<h2>", "<h3>", body_ov)
        body_ov = re.sub(r"</h2>", "</h3>", body_ov)
        parts.append('<div class="partoverview">%s</div>' % body_ov)
        for t in T.TOPICS[k]:
            parts.append('<div id="%s-%s" class="anchor"></div>' % (k, t[6]))
            parts.append('<h3 class="bookmark">%s%s</h3>'
                         % (t[0], ' <span class="badge hot">高频</span>' if t[5]
                            else ' <span class="badge">常规</span>'))
            # 去掉章节正文自带的 h1 与 h2：章名已由上面的 h3.bookmark 给出，
            # 重复渲染会让读者看到"同一标题连着出现两次"。
            chap_body = re.sub(r"<h1>.*?</h1>", "", chapters[(k, t[6])],
                               count=1, flags=re.S)
            chap_body = re.sub(r"<h2>.*?</h2>", "", chap_body,
                               count=1, flags=re.S)
            parts.append(chap_body)
            parts.append('<p class="backtop"><a href="#top">↑ 回到顶部</a></p>')
    with open(os.path.join(CONTENT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("考研数学二 · 全科速成复习资料",
                     sidebar(0, None, single_page=True),
                     "\n".join(parts), 0, "",
                     topbar(SITE_NAME, "index.html", [("首页", None)])))

    # ---- README.html ----
    rp = os.path.join(CONTENT, "README.md")
    if os.path.exists(rp):
        body = md_to_html(open(rp, encoding="utf-8").read(), 0, missing)
        with open(os.path.join(CONTENT, "README.html"), "w", encoding="utf-8") as f:
            f.write(page("数学二 · 总览与数据口径", sidebar(0, None), body, 0,
                         warn_block(missing),
                         topbar(SITE_NAME, "index.html",
                                [("首页", "index.html"), ("总览与数据口径", None)])))
    return n


def main():
    T.check()
    copy_mermaid_runtime()
    copy_katex()
    n = build()
    print("已生成 %d 个章节页 + %d 个部分首页 + 1 个全科单页 + README.html"
          % (n, len(T.ORDER)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
