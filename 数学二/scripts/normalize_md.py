#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown 空行规范化器（幂等）。

为什么需要它
------------
Markdown 中**单换行不产生换行**。块级元素（标题、代码围栏、行间公式 `$$`、
引用块、表格、列表）与相邻段落之间若只隔一个换行，渲染时会粘连成一整段。
408 资料初版就因此把「核心讲解 / 关键结论速记 / 示意图 / 易错点 / 真题示例」
五个模板字段渲染成一整坨。

数学二比 408 多一类块级元素：**行间公式 `$$ ... $$`**。它同样必须独立成块，
否则会与前后正文粘在一行、KaTeX/MathJax 不渲染。

本脚本做两件事，且**幂等**（重复运行结果不变）：
  1. 在块级元素前后保证恰好一个空行；
  2. 折叠连续空行（代码围栏与 `$$` 块内部一律不动）。

用法
----
    python3 数学二/scripts/normalize_md.py            # 规范化 parts/（内容源）
    python3 数学二/scripts/normalize_md.py --check    # 只报告需要改动的位置
    python3 数学二/scripts/normalize_md.py <dir>      # 规范化指定目录下的 *.md（递归）
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARTS = os.path.join(ROOT, "parts")

TABLE_SEP = re.compile(r"^\|?[\s:\-|]+\|[\s:\-|]*$")
LIST_RE = re.compile(r"^([-*+]|\d+\.)\s")
HEAD_RE = re.compile(r"^#{1,6} ")


def is_table_line(s):
    return s.startswith("|") or bool(TABLE_SEP.match(s) and "-" in s)


def split_blocks(lines):
    """把文档切成块。

    一个「块」是：整个代码围栏 / 整个 `$$` 行间公式 / 连续表格行 /
    连续列表行 / 连续引用行 / 连续正文行 / 单个标题行。
    """
    blocks, i, n = [], 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s.startswith("```"):
            buf = [lines[i]]
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            if i < n:
                buf.append(lines[i])      # 闭合围栏
                i += 1
            blocks.append(("fence", buf))
            continue
        if not s:
            i += 1                        # 空行不产生块，后面统一补
            continue
        if s.startswith("$$"):
            # 行间公式：`$$...$$` 可能一行写完，也可能跨多行到下一个 `$$`
            buf = [lines[i]]
            done = s.count("$$") >= 2
            i += 1
            while i < n and not done:
                buf.append(lines[i])
                if "$$" in lines[i]:
                    done = True
                i += 1
            blocks.append(("math", buf))
            continue
        if is_table_line(s):
            kind = "table"
        elif s.startswith(">"):
            kind = "quote"
        elif HEAD_RE.match(s):
            kind = "head"
        elif LIST_RE.match(s):
            kind = "list"
        else:
            kind = "text"
        buf = [lines[i]]
        i += 1
        while i < n:
            t = lines[i].strip()
            if not t:
                break
            same = (
                (kind == "table" and is_table_line(t)) or
                (kind == "quote" and t.startswith(">")) or
                (kind == "list" and LIST_RE.match(t)) or
                (kind == "text" and not is_table_line(t) and not t.startswith(">")
                 and not t.startswith("$$") and not t.startswith("```")
                 and not HEAD_RE.match(t) and not LIST_RE.match(t))
            )
            if not same:
                break
            buf.append(lines[i])
            i += 1
        blocks.append((kind, buf))
    return blocks


def normalize(text):
    lines = text.split("\n")
    blocks = split_blocks(lines)
    out = []
    for _kind, buf in blocks:
        if out:
            out.append("")                # 块间恰好一个空行
        out.extend(buf)
    return "\n".join(out).rstrip("\n") + "\n"


def target_files(argv):
    dirs = [a for a in argv if not a.startswith("-")]
    if not dirs:
        return sorted(glob.glob(os.path.join(PARTS, "*", "*.md")))
    files = []
    for d in dirs:
        p = d if os.path.isabs(d) else os.path.join(ROOT, d)
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "**", "*.md"), recursive=True)))
        else:
            files.append(p)
    return files


def main():
    check = "--check" in sys.argv
    files = target_files(sys.argv[1:])
    if not files:
        print("没有找到可规范化的 Markdown 文件")
        return 0
    changed = 0
    for f in files:
        src = open(f, encoding="utf-8").read()
        dst = normalize(src)
        if src != dst:
            changed += 1
            rel = os.path.relpath(f, ROOT)
            if check:
                print("需规范化:", rel)
            else:
                open(f, "w", encoding="utf-8").write(dst)
                print("已规范化:", rel)
    print(("需要规范化 %d 个文件" if check else "已规范化 %d 个文件") % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
