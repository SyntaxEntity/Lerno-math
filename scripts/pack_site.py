#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `数学二/` 打包成一个**可直接推送到静态托管平台**的独立站点目录。

产出内容（不含 parts/、scripts/、mermaid.min.js 之外的源文件）
--------------------------------------------------------------
    <输出目录>/
    ├── index.html            全科单页合集（入口）
    ├── README.html           数据口径说明
    ├── 高等数学/*.html
    ├── 线性代数/*.html
    ├── assets/*.png          24 张 matplotlib 生成的插图
    ├── katex/                公式渲染运行时（含 60 个字体，离线可用）
    ├── mermaid.min.js        图表渲染运行时（离线可用）
    ├── .nojekyll             关闭 Jekyll（否则下划线开头的目录会被静默跳过）
    ├── LICENSE               代码 MIT
    ├── LICENSE-CONTENT       文字与图片 CC BY-NC-SA 4.0
    ├── THIRD-PARTY.md        第三方组件许可与来源
    ├── .gitignore            站点仓库的忽略规则
    └── README.md             站点说明（面向访客）

用法
----
    python3 scripts/pack_site.py math2-site   # 仓库根的 math2-site/（发布用，CI 同款）
    python3 scripts/pack_site.py dist         # 仓库根的 dist/（临时预览）

    路径按**仓库根**（即本脚本往上两级）解析，所以从仓库根执行时写目录名即可。

⚠️ 输出目录会被**先清空再重建**。如果它已经是一个 git 仓库（里面有 `.git/`），
本脚本默认**拒绝执行**——否则会连本地提交历史和 `.github/workflows/` 一起删掉。
要保留这些元数据请加 `--keep-vcs`（打包前移出、打包后放回）；确实要推倒重来加 `--force`。
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "数学二")

# 「输出目录不是纯粹的生成物」时会被保留的元数据（--keep-vcs）
VCS_KEEP = [".git", ".github"]

# 体检用的密钥形态（裁定 D-06：报告里宣称的检查必须真的存在）。
# 只认高置信度形态，避免把正文/公式里的普通字符误报成密钥。
SECRET_PATTERNS = [
    ("私钥", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("口令赋值", re.compile(r"(?i)(?:password|passwd|api[_-]?key|secret[_-]?key)"
                          r"\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']")),
]

# 密钥扫描的反例表（裁定 D-06：新增门禁必须配反例）。
# 每条给出「样本 → 期望命中的标签集合」；空集合表示**必须不误报**。
# 用 `--self-test` 跑，报告打印「N/N 通过」——判断这条检查跑没跑，看数字即可。
SECRET_SELFTEST = [
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIE...", {"私钥"}),
    ("ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4", {"GitHub token"}),
    ("sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4O5P6", {"OpenAI key"}),
    ("AKIA" + "ABCDEFGHIJKLMNOP", {"AWS key"}),
    ('api_key = "a1b2c3d4e5f6g7h8"', {"口令赋值"}),
    # 正常内容：数学正文、普通代码、渠道名 —— 一条都不许命中
    ("设 $f(x)=x^2$，则 $f'(x)=2x$。", set()),
    ("sk-learn 与 sklearn 都是普通词，不是 key。", set()),
    ("const cacheKey = 'v1';  // 普通字符串", set()),
]


def run_selftest():
    """跑密钥扫描的反例：既要有命中，也要有不误报。"""
    ok = 0
    for sample, want in SECRET_SELFTEST:
        got = {label for label, pat in SECRET_PATTERNS if pat.search(sample)}
        hit = got == want
        ok += hit
        print("  %s 期望 %-12s 实得 %-12s %s"
              % ("✓" if hit else "✗", want or "（无）", got or "（无）",
                 sample.replace("\n", "\\n")[:40]))
    print("-" * 66)
    print("  密钥扫描自测：%d / %d 条通过" % (ok, len(SECRET_SELFTEST)))
    return 0 if ok == len(SECRET_SELFTEST) else 1

# 需要整目录拷贝的静态资源
COPY_DIRS = ["assets", "katex"]
# 需要单文件拷贝的运行库
COPY_FILES = ["mermaid.min.js"]

MIT = """MIT License

Copyright (c) {year} 考研数学二速成资料 contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

CONTENT_LICENSE = """# 文字与图片内容许可

本仓库的**复习资料正文（Markdown/HTML 文本）与插图（assets/*.png）**
采用 **Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International（CC BY-NC-SA 4.0）** 许可。

你可以自由地：

- **共享** —— 以任何媒介或格式复制、发行本作品
- **演绎** —— 修改、转换或以本作品为基础进行创作

但须遵守以下条件：

- **署名** —— 必须给出适当署名，并提供指向本许可协议的链接，同时标明是否
  作出了修改。
- **非商业性使用** —— 不得将本作品用于商业目的。
- **相同方式共享** —— 如果修改、转换或以本作品为基础进行创作，必须采用与
  本许可协议相同的许可协议分发你的贡献。

许可协议全文：https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.zh-Hans

---

## 使用到的第三方材料与出处

1. **考试大纲与试卷结构**
   依据教育部教育考试院发布的《全国硕士研究生招生考试数学（二）考试大纲》
   整理。大纲本身为官方公开文件。

2. **历年真题题面**
   少量真题题面为**解题示范**目的引用，来源为公开流传的历年真题（本地核对语料
   为第三方 OCR 整理，未随本仓库分发）。真题著作权归原命题机构所有，此处引用
   属合理使用；如权利人提出异议，将立即移除相关内容。

3. **知识体系口径**
   定义、定理与解法步骤按同济大学《高等数学》《线性代数》的通行口径撰写，
   表述为原创。

4. **插图**
   全部由本仓库作者编写的 matplotlib 脚本生成，非转载。
"""

THIRD_PARTY = """# 第三方组件

本站在浏览器端渲染公式与图表，相关运行库**已随站点分发**，因此完全离线可用。

| 组件 | 版本 | 许可 | 用途 | 来源 |
| --- | --- | --- | --- | --- |
{katex_row}
{mermaid_row}

两者的许可均为 MIT，允许随作品再分发；MIT 许可全文见各组件仓库内的 `LICENSE`。
版本取自 `scripts/tools-package.json`（唯一数据源），不在此处另写一份。

---

## 数据说明

本站的**考频统计**基于 2023—2024 两年数学二真题逐题定章自行统计，样本量小，
仅用于区分「必考主线」与「偶发考点」，不代表长期占比。官方从不公布逐知识点
考频，凡是无法核实的条目均标注「考频待补充」，未作估算。

详细口径见站内 `README.html`。
"""


def third_party_md():
    """按 tools-package.json 渲染 THIRD_PARTY.md（版本不在本文件里写死）。"""
    deps = {}
    try:
        with open(os.path.join(SRC, "scripts", "tools-package.json"), encoding="utf-8") as f:
            deps = json.load(f).get("dependencies", {})
    except Exception:                                        # noqa: BLE001
        pass

    def ver(name):
        return deps.get(name, "见 tools-package.json")

    return THIRD_PARTY.format(
        katex_row="| KaTeX | %s | MIT | 公式排版（含 60 个字体文件） | https://katex.org/ |"
                  % ver("katex"),
        mermaid_row="| mermaid | %s | MIT | 流程图渲染 | https://mermaid.js.org/ |"
                    % ver("mermaid"))

SITE_GITIGNORE = """# 系统与编辑器
.DS_Store
Thumbs.db
*.swp
.idea/
.vscode/

# 若在本地构建产物，忽略 Python 缓存
__pycache__/
*.pyc
"""

SITE_README = """# 考研数学二速成复习资料（网页版）

面向**已经系统学过数学二、需要快速过一遍**的考生。高等数学 9 章 + 线性代数 6 章。

## 直接看

打开 `index.html` 即可（本地双击也能用，**无需联网、无需服务器**）。

在线访问：`<部署后替换为你的网址>`

## 怎么用

| 想做的事 | 操作 |
| --- | --- |
| 一页看完全部 | `index.html`（15 章合并） |
| 只看某章 | 左侧输入框筛选，或点章节跳转 |
| 章内跳段 | 章节页左侧自动展开「考频统计 / 核心讲解 / 速记 / 示意图 / 易错点 / 真题示例」 |
| 快速翻章 | 键盘 `←`/`k` 上一章、`→`/`j` 下一章 |
| 全文检索 | `Ctrl+F` |
| 夜间模式 | 右下角「◐ 主题」 |
| 存 PDF | `Ctrl+P`（已做打印样式） |

## 特点

- **完全离线**：KaTeX 与 mermaid 运行库随包分发，断网也能正常看公式和图。
- **考频数据可追溯**：基于真题逐题统计，无法核实的一律标「考频待补充」，绝不编造。
- **数值全部机器复算**：108 条 sympy 断言，含「图上标注坐标 = 符号计算结果」。
- **真题标注分级**：区分「逐字核对的原题」与「改编题」，宁保守不冒充。

## 许可

- 代码：MIT（见 `LICENSE`）
- 文字与插图：CC BY-NC-SA 4.0（见 `LICENSE-CONTENT`，**禁止商业使用**）
- 第三方组件：见 `THIRD-PARTY.md`

## 免责声明

本资料为个人整理的复习辅助材料，**与任何命题、招生机构无关**，不构成命题预测。
请以官方考试大纲与正式教材为准。
"""


def iter_html(src):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in ("scripts", "assets", "katex", "__pycache__")]
        for fn in files:
            if fn.endswith(".html"):
                yield os.path.join(root, fn)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if "--self-test" in flags:
        return run_selftest()
    if not args:
        sys.exit(__doc__)
    keep_vcs = "--keep-vcs" in flags
    out = os.path.abspath(os.path.join(ROOT, args[0]))
    if out in (ROOT, os.path.dirname(ROOT), os.path.dirname(SRC), SRC):
        sys.exit("拒绝执行：输出目录 %s 是仓库/内容目录本身。" % out)

    # 0) 输出目录先清空再重建。若它是个 git 仓库，删掉就等于删提交历史，
    #    所以默认拒绝，而不是「按脚本设计的工作流」默默毁掉本地历史。
    stash = None
    if os.path.exists(out):
        present = [n for n in VCS_KEEP if os.path.exists(os.path.join(out, n))]
        if present and not (keep_vcs or "--force" in flags):
            sys.exit(
                "拒绝执行：%s 里已有 %s。\n"
                "  本脚本会先 rmtree 输出目录，直接跑会把本地提交历史与 GitHub Actions\n"
                "  工作流一起删掉。请二选一：\n"
                "    --keep-vcs  打包前把 %s 移出、打包后放回（保留历史，推荐）\n"
                "    --force     确实要推倒重来（历史会丢）"
                % (out, "、".join(present), "、".join(present)))
        if present and keep_vcs:
            stash = out + "__vcs_stash"
            if os.path.exists(stash):
                shutil.rmtree(stash)
            os.makedirs(stash)
            for n in present:
                shutil.move(os.path.join(out, n), os.path.join(stash, n))
            print("◇ 已暂存 %s，打包后放回" % "、".join(present))
        shutil.rmtree(out)
    os.makedirs(out)

    # 1) 静态资源
    for d in COPY_DIRS:
        s = os.path.join(SRC, d)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(out, d))
    for f in COPY_FILES:
        s = os.path.join(SRC, f)
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(out, f))

    # 2) HTML（保持目录结构）
    n_html = 0
    for p in iter_html(SRC):
        rel = os.path.relpath(p, SRC)
        tgt = os.path.join(out, rel)
        os.makedirs(os.path.dirname(tgt), exist_ok=True)
        shutil.copyfile(p, tgt)
        n_html += 1

    # 2.4) 站点必备文件——**必须在修链接之前写**：
    #      否则页脚里指向 THIRD-PARTY.md / README.md 的链接会因为目标尚不存在
    #      而被判成死链去掉（实测 19 个页面各丢一条）。
    # 3) 站点必备文件
    open(os.path.join(out, ".nojekyll"), "w").close()
    with open(os.path.join(out, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(MIT.format(year="2026"))
    for name, body in (("LICENSE-CONTENT", CONTENT_LICENSE),
                       ("THIRD-PARTY.md", third_party_md()),
                       ("README.md", SITE_README),
                       (".gitignore", SITE_GITIGNORE)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(body)

    # 2.5) 修正站内链接。
    #
    # 源文件里的 href 有**两种口径**混用，必须都认：
    #   (a) 仓库根口径：`数学二/高等数学/01-xxx.md`（README、部分首页的章节卡片）
    #   (b) 当前文件口径：`../高等数学/01-xxx.html`、`02-导数与微分.html`（侧栏、翻页）
    # 早期实现只在「当前文件目录」下解析 (a)，路径里白多了一层目录名，于是
    # **部分首页正文里的 15 个章节链接全部解析失败、被当成死链去掉**（侧栏还在，
    # 所以肉眼很难发现）。现在两种基准都试，命中后一律用 os.path.relpath 现算回
    # 相对路径——不手写层级。
    #
    # 站点包里既没有 .md、也少一层目录，所以 .md 先换成同名 .html；
    # 真找不到目标才去掉 <a> 只留文字，绝不留死链。
    fixed = dropped = 0
    dead_links = []
    for root, _d, files in os.walk(out):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            fp = os.path.join(root, fn)
            here = os.path.dirname(fp)
            body = open(fp, encoding="utf-8").read()

            def repl(m, here=here, fp=fp):
                nonlocal fixed, dropped
                href = m.group(1)
                if href.startswith(("http", "#", "mailto:", "data:")):
                    return m.group(0)
                c = href[len("数学二/"):] if href.startswith("数学二/") else href
                alts = [c, href]
                if c.endswith(".md"):
                    alts.insert(0, c[:-3] + ".html")
                tgt = None
                for x in alts:
                    for base in (out, here):          # (a) 根口径 → (b) 当前文件口径
                        p = os.path.normpath(os.path.join(base, x))
                        if p.startswith(out + os.sep) and os.path.exists(p):
                            tgt = p
                            break
                    if tgt:
                        break
                if tgt:
                    fixed += 1
                    return 'href="%s"' % os.path.relpath(tgt, here).replace(os.sep, "/")
                dropped += 1
                dead_links.append((os.path.relpath(fp, out), href))
                return 'href="#" data-dead="1"'

            body = re.sub(r'href="([^"]+)"', repl, body)
            # 被标记为死链的 <a>，把标签去掉只保留文字，避免点进去没反应
            body = re.sub(r'<a\b[^>]*data-dead="1"[^>]*>(.*?)</a>', r"\1", body, flags=re.S)
            open(fp, "w", encoding="utf-8").write(body)

    # 3.5) 放回暂存的 VCS 元数据
    if stash:
        for n in os.listdir(stash):
            shutil.move(os.path.join(stash, n), os.path.join(out, n))
        shutil.rmtree(stash)
        print("◇ 已放回 %s" % "、".join(VCS_KEEP))

    # 4) 体检：不放行任何绝对路径 / 密钥痕迹
    # 裁定 D-06：报告里宣称的检查必须真的存在。旧版成功行写着「无密钥痕迹」，
    # 但代码里**根本没有密钥扫描**——「没检查」与「检查通过」在输出上完全一样，
    # 属于明令禁止的形态。现在补上真扫描，并把实际扫描的文件数打进报告。
    bad = []

    def ship_files():
        """只统计**真正要发布**的文件：把 .git/.github 排除掉。

        否则同一份站点在提交几次之后「文件数」和「体积」会自己变大，
        看起来像内容膨胀了——报告里的数字必须是发布物的数字。
        """
        for r, dirs, fs in os.walk(out):
            dirs[:] = [d for d in dirs if d not in VCS_KEEP]
            for f in fs:
                yield r, f

    def secret_hits(t):
        """返回命中的密钥形态标签（空列表 = 没命中）。

        只认**高置信度**的形态：宁可漏一个不像密钥的，也不要把 minified JS 里
        的随机串误报成密钥（误报会让这条检查被当成噪音而关掉）。
        """
        hits = []
        for label, pat in SECRET_PATTERNS:
            if pat.search(t):
                hits.append(label)
        return hits

    n_text = 0
    for r, fn in ship_files():
        p = os.path.join(r, fn)
        if fn.endswith((".html", ".md", ".txt")):
            t = open(p, encoding="utf-8", errors="ignore").read()
            n_text += 1
            if re.search(r"(?<![\w.])/(?:home|Users|root|mnt|media)/", t):
                bad.append(("绝对路径", os.path.relpath(p, out)))
            for label in secret_hits(t):
                bad.append(("疑似%s" % label, os.path.relpath(p, out)))
    n_files = sum(1 for _ in ship_files())
    size = sum(os.path.getsize(os.path.join(r, f)) for r, f in ship_files())

    print("=" * 66)
    print("部署目录：%s" % out)
    print("  文件 %d 个（HTML %d 个）｜ 体积 %.1f MB" % (n_files, n_html, size / 1048576))
    print("  站内链接：改写 %d 处，去掉死链 %d 处" % (fixed, dropped))
    print("  体检：绝对路径 + 密钥形态，扫描了 %d 个文本文件" % n_text)
    if dead_links:
        # 死链必须**逐条列出来**：上一版只报了个总数「去掉死链 15 处」，
        # 于是「部分首页 15 个章节链接全丢了」这件事在报告里看起来像正常清理。
        print("  ! 被去掉的链接（确认这些目标本来就不该随包分发）：")
        for f, h in dead_links[:20]:
            print("      %s → %s" % (f, h))
        if len(dead_links) > 20:
            print("      …（共 %d 条）" % len(dead_links))
    print("  已生成：.nojekyll / LICENSE / LICENSE-CONTENT / THIRD-PARTY.md / README.md / .gitignore")
    if bad:
        print("  ✗ 体检发现问题：")
        for kind, rel in bad[:10]:
            print("      %s：%s" % (kind, rel))
        return 1
    print("  ✓ 体检通过：%d 个文本文件里无绝对路径、无密钥形态" % n_text)
    print("-" * 66)
    print("""下一步：
  本目录是**构建产物**，已由仓库根的 .gitignore 排除，不要单独提交或推送。
  发布走仓库根的工作流：.github/workflows/pages.yml
    push 到 main → 跑 validate.py → 跑本脚本 → 上传本目录到 GitHub Pages
  要本地预览，直接用浏览器打开 %s/index.html 即可（完全离线）。""" % (out,))
    return 0


if __name__ == "__main__":
    sys.exit(main())
