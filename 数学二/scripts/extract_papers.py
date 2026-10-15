#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真题 OCR 语料中抽取题面，供撰写「真题示例」时逐条核对。

语料来源
--------
`.tools/kmath2/Kaoyan-Math2-Papers-main/`（GitHub: TsekaLuk/Kaoyan-Math2-Papers，
考研数学二真题 1987—2024，含 OCR 文本与 PDF 原件）。该目录只作为**核对用**
的本地语料，不进入交付物。

用法
----
    python3 数学二/scripts/extract_papers.py --list
    python3 数学二/scripts/extract_papers.py --year 2024        # 打印该年题面
    python3 数学二/scripts/extract_papers.py --year 2024 --n 5  # 只打印第 5 题
    python3 数学二/scripts/extract_papers.py --search 二重积分   # 全语料检索

注意
----
OCR 文本有个别识别错误（例如 2024 年第 16 题之后填空题标题缺失）。**引用题面
到成品前，必须以 `--n` 抽出的原文人工比对**，不得凭记忆填写。凡 OCR 残缺、
无法确证题面的，在正文中一律写成「真题改编」。
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, ".tools", "kmath2", "Kaoyan-Math2-Papers-main", "solutions")

# 年份 -> 语料文件（相对 CORPUS）
FILES = {
    1987: "math2_1987-2019/math2_1987-2019.md",   # 该文件含 1987—2019 全部年份
    2020: "2020/math2_2020/math2_2020.md",
    2021: "2021/math2_2021/math2_2021.md",
    2022: "2022/math2_2022/math2_2022.md",
    2023: "2023/math2_2023/math2_2023.md",
    2024: "2024/math2_2024.md",
}
BULK = "math2_1987-2019/math2_1987-2019.md"

CN_DIGIT = "〇一二三四五六七八九"
CN_YEAR_RE = re.compile(r"^#\s*([〇一二三四五六七八九]{4})年")


def cn_year_to_int(s):
    """'二〇二四' -> 2024。"""
    val = 0
    for ch in s:
        val = val * 10 + CN_DIGIT.index(ch)
    return val


def read(year):
    """返回指定年份的题面文本。1987—2019 从合集里按年份标题切分。"""
    if year in (1987,) or 1987 <= year <= 2019:
        path = os.path.join(CORPUS, BULK)
        if not os.path.exists(path):
            sys.exit("找不到语料：%s（请先下载真题库到 .tools/kmath2/）" % path)
        text = open(path, encoding="utf-8").read()
        parts = re.split(r"(?m)^(?=#\s*[〇一二三四五六七八九]{4}年)", text)
        for p in parts:
            m = CN_YEAR_RE.match(p)
            if m and cn_year_to_int(m.group(1)) == year:
                return p
        return None
    rel = FILES.get(year)
    if rel is None:
        return None
    path = os.path.join(CORPUS, rel)
    if not os.path.exists(path):
        sys.exit("找不到语料：%s" % path)
    return open(path, encoding="utf-8").read()


def section(text):
    """按题号切分，返回 [(题号, 该题文本)]。题号形如 （1） / (1) / 1. 。"""
    lines = text.split("\n")
    out, cur_no, buf = [], None, []
    for ln in lines:
        m = re.match(r"^\s*[（(]?(\d{1,2})[）)]?\s*[.、]?\s*(?=\S)", ln)
        m2 = re.match(r"^\s*(\d{1,2})\.\s+\S", ln)
        no = None
        if m2:
            no = int(m2.group(1))
        elif m and int(m.group(1)) <= 23:
            no = int(m.group(1))
        if no is not None and (cur_no is None or no == cur_no + 1):
            if cur_no is not None:
                out.append((cur_no, "\n".join(buf).strip()))
            cur_no, buf = no, [ln]
        elif cur_no is not None:
            buf.append(ln)
    if cur_no is not None:
        out.append((cur_no, "\n".join(buf).strip()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出语料覆盖的年份")
    ap.add_argument("--year", type=int, help="打印指定年份题面")
    ap.add_argument("--n", type=int, help="与 --year 连用，只打印第 n 题")
    ap.add_argument("--search", help="在全部语料中检索关键词")
    a = ap.parse_args()

    if a.list:
        print("可用年份：", ", ".join(str(y) for y in sorted(FILES)))
        for y in (2020, 2021, 2022, 2023, 2024):
            t = read(y) or ""
            print("  %d：%d 字，%d 个题号" % (y, len(t), len(section(t))))
        return 0

    if a.search:
        for y in sorted(FILES):
            t = read(y) or ""
            for i, ln in enumerate(t.split("\n"), 1):
                if a.search in ln:
                    print("%d:%d: %s" % (y, i, ln.strip()[:110]))
        return 0

    if not a.year:
        ap.print_help()
        return 1
    t = read(a.year)
    if not t:
        sys.exit("语料中没有 %d 年" % a.year)
    if a.n:
        for no, body in section(t):
            if no == a.n:
                print(body)
                return 0
        sys.exit("未找到第 %d 题" % a.n)
    print(t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
