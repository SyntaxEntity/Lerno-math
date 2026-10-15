#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公式不变量审阅器：对比两个版本的 `parts/`，确认**数学内容一个字都没改**。

为什么需要它
------------
改解析排版（把行内公式提成独立成行的 `$$…$$`、把一大段拆成几步）时，
最容易发生的错误不是排版，而是**顺手把公式改了**：少个负号、系数写错、
括号换了层级。这类错误肉眼审 diff 很容易滑过去，而站点的 sympy 复算
（`verify_math.py`）只覆盖资料里**断言过**的那些数值，覆盖不到全部公式。

所以这条工具把"我只动了排版"变成**机器可验证的断言**。

判据分两级（这是有意区分的）
----------------------------
1. **硬失败**：公式**内容**变了。判据是把两边的公式正文按顺序拼接、去掉空白与
   纯间距宏后逐字比对——少一个负号、多一个逗号都会被抓出来。
2. **提示放行**：序列不同但拼接内容相同，即"把两个公式合并成一行"或反过来拆开。
   这属于排版选择（例如把两个导数等式并排写成一行 `$$A=1\qquad B=1$$`），
   不算改内容，因此只打印一条 `·` 提示、不失败。
   ⚠️ 注意：合并时**只能用间距宏**（`\\qquad`/`\\quad`/`\\;`），一旦顺手加个逗号
   或顿号，拼接就不再相同，会被判成内容改动——这正是它该有的严格程度。

用法
----
    python3 scripts/diff_math.py HEAD        # 工作区 vs HEAD
    python3 scripts/diff_math.py HEAD~1      # 工作区 vs 上一个提交

退出码：0 = 公式内容一致（可能含合并/拆分提示）；1 = 有文件公式内容被改动。
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARTS = os.path.join(ROOT, "parts")

# 只算「纯间距」的宏：它们不承载数学含义，允许在合并/拆分行内公式时增减
SPACING = re.compile(r"\\(?:qquad|quad|,|;|:|!)|\s+")
MATH = re.compile(r"\$\$(.+?)\$\$|\$([^$\n]+?)\$", re.S)


def formulas(text):
    """按出现顺序取出所有公式正文（`$$…$$` 与 `$…$` 一视同仁）。"""
    out = []
    for m in MATH.finditer(text):
        body = m.group(1) if m.group(1) is not None else m.group(2)
        out.append(SPACING.sub("", body))
    return out


def as_text(rev, path):
    r = subprocess.run(["git", "show", "%s:%s" % (rev, path)],
                       cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rev = sys.argv[1]
    changed, regrouped, checked = [], [], 0
    for dirpath, _d, files in os.walk(PARTS):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            old = as_text(rev, rel)
            if old is None:
                print("  ? %s：%s 里没有这个文件（新增？跳过）" % (rel, rev))
                continue
            checked += 1
            new = open(full, encoding="utf-8").read()
            a, b = formulas(old), formulas(new)
            if a == b:
                continue
            # 公式**序列**不同但**拼接内容**相同 = 只是把两个公式合并成了一行
            # （或反过来拆开）。这属于排版，不是内容改动：允许，但要显式提示，
            # 免得"看起来什么都没变"地把公式搬来搬去。
            if "".join(a) == "".join(b):
                regrouped.append((rel, len(a), len(b)))
            else:
                changed.append((rel, a, b))
    print("=" * 74)
    print("公式不变量审阅：%s → 工作区，共比对 %d 个内容源文件" % (rev, checked))
    for rel, na, nb in regrouped:
        print("  · %s：公式被合并/拆分（%d 个 → %d 个），拼接内容一致" % (rel, na, nb))
    if not changed:
        print("  ✓ 全部文件的公式**内容**逐字一致（本次改动只动了排版）")
        return 0
    for rel, a, b in changed:
        print("  ✗ %s：公式内容有改动（旧 %d 个 / 新 %d 个）" % (rel, len(a), len(b)))
        sa, sb = set(a), set(b)
        for x in a:
            if x not in sb:
                print("      删/改：%s" % x[:90])
        for x in b:
            if x not in sa:
                print("      新增/改：%s" % x[:90])
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print("      第 %d 个：\n        旧 %s\n        新 %s"
                      % (i + 1, x[:90], y[:90]))
                break
    print("-" * 74)
    print("  ✗ 有 %d 个文件的公式**内容**被改动：请逐条确认是有意修改，"
          "否则改回原样（本工具的用途就是拦住「顺手改公式」）" % len(changed))
    return 1


if __name__ == "__main__":
    sys.exit(main())
