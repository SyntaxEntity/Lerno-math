#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 parts/<部分>/<slug>.md 的内容源组装为 `数学二/` 下的成品 Markdown。

职责划分（保证全局一致性）
--------------------------
  - 模板骨架（`## 知识点名 [高频]`、六个字段标签）由本脚本生成；
  - 考频数据来自 `meta.py`（唯一数据源），**内容源里不写任何统计数字**；
  - 作者只写 parts 文件，格式见 `PARTS_FORMAT.md`。

产出
----
    数学二/高等数学/00-科目总览.md      + 01..09 章
    数学二/线性代数/00-科目总览.md      + 01..06 章
    （每个知识点的 .md 不含 README，README 由 build_readme() 生成）

用法
----
    python3 scripts/build.py            # 全部生成
    python3 scripts/build.py gaoshu     # 只生成高等数学
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import meta as T          # noqa: E402
import normalize_md as NM  # noqa: E402

ROOT = os.path.dirname(HERE)      # 仓库根（parts/ 所在）
CONTENT = os.path.join(ROOT, "数学二")              # 成品根
PARTS = os.path.join(ROOT, "parts")

# 内容源里合法的段落名（顺序固定，不可增删）
SEGMENTS = ["核心讲解", "关键结论速记", "示意图", "易错点", "真题示例"]

# 注入成品、但不在内容源里手写的字段标签
FIELDS = [("核心讲解", "**核心讲解**："),
          ("关键结论速记", "**关键结论速记**："),
          ("示意图", "**示意图**："),
          ("易错点", "**易错点**："),
          ("真题示例", "**真题示例**：")]

BANNER = (
    "> 本资料为**速成复习**用途，面向已经系统学过数学二、需要快速过一遍的考生。\n"
    "> 考频数据来自真题逐题统计，口径与来源见 `数学二/README.md`；\n"
    "> 未核实条目一律标注「考频待补充」，不作估算。\n")


def parse_partial(path):
    """解析内容源：按 `# 段落名` 切段，返回 {段落名: 正文}。

    只认 `# 名称` 一级标题；`##` 及更深标题视为正文的一部分（本资料不使用）。
    """
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    segs, cur = {}, None
    for ln in lines:
        m = re.match(r"^# (\S.*?)\s*$", ln)
        if m and not ln.startswith("## "):
            cur = m.group(1).strip()
            segs.setdefault(cur, [])
            continue
        if cur is not None:
            segs[cur].append(ln)
    return {k: "\n".join(v).strip() for k, v in segs.items()}


def build_topic(subject_key, topic, partial):
    """生成单个知识点的成品 Markdown（含标题与考频统计行）。"""
    name, times, years, pts, qtype, hot, slug = topic

    missing = [s for s in SEGMENTS if s not in partial or not partial[s]]
    if missing:
        raise SystemExit("[%s/%s] 内容源缺少段落：%s"
                         % (subject_key, slug, "、".join(missing)))
    extra = [k for k in partial if k not in SEGMENTS]
    if extra:
        raise SystemExit("[%s/%s] 内容源含非法段落名：%s（合法值只有 %s）"
                         % (subject_key, slug, "、".join(extra), "、".join(SEGMENTS)))

    title = ("## %s %s" % (name, "[高频]" if hot else "")).strip()
    # 字段之间用空行分隔：Markdown 中单换行不换行，不留空行六段会糊成一整段
    out = [title, "", T.freq_line(subject_key, name), ""]

    note = T.NOTES.get(slug)
    if note:
        out += ["> **考频说明**：%s" % note, ""]

    for key, label in FIELDS:
        out += [label, "", partial[key], ""]

    out += ["---", ""]
    return "\n".join(out)


def subject_overview(subject_key, topics):
    """科目总览：章节索引表 + 本科目分值结构 + 应试提示。"""
    sub = T.SUBJECTS[subject_key]
    rows = ["| # | 知识点 | 考察次数 | 分值（建议权重） | 占比 | 高频 |",
            "| --- | --- | --- | --- | --- | --- |"]
    for i, (name, times, years, pts, qtype, hot, slug) in enumerate(topics, 1):
        # 链接统一用「从仓库根算起」的相对路径：无论在仓库根还是数学二/ 下都能点开
        rows.append("| %d | [%s](数学二/%s/%s.md) | %s | %d 分 | %s | %s |"
                    % (i, name, sub["dir"], slug,
                       T.PENDING if times == T.PENDING else "%d 次" % times,
                       pts, T.ratio_of(subject_key, slug),
                       "**是**" if hot else "否"))
    idx = "\n".join(rows)

    if subject_key == "gaoshu":
        focus = ("**复习优先级**：定积分与反常积分 → 函数、极限与连续 → 导数与微分 "
                 "→ 多元函数微积分学 → 中值定理与导数应用 → 定积分的几何与物理应用 "
                 "→ 微分方程 → 不定积分。\n\n"
                 "高数占全卷约 **117 分**，是绝对主体。其中**一元函数微积分**"
                 "（极限/导数/中值定理/积分）合计约 76 分，**多元函数微积分学**"
                 "（偏导、全微分、极值、二重积分）约 16 分，且近两年稳定出选择 + 解答。")
        scope = ("**范围边界（据 2025 年数二大纲）**：考函数、极限与连续，一元函数微分学，"
                 "一元函数积分学（含反常积分），**多元函数微积分学**（含二重积分），"
                 "常微分方程。**不考**无穷级数、向量代数与空间解析几何、三重积分、"
                 "曲线积分与曲面积分。")
    else:
        focus = ("**复习优先级**：矩阵 → 特征值与特征向量 → 二次型 → 线性方程组 "
                 "→ 向量与向量组 → 行列式。\n\n"
                 "线代占全卷约 **33 分**（约 22%），通常为 1—2 道选择/填空 + 1 道解答题。"
                 "命题**重基本运算**，跨章节综合证明少于数学一；"
                 "但「秩」这一概念贯穿全科，是解题的总钥匙。")
        scope = ("**范围边界（据 2025 年数二大纲）**：考行列式、矩阵、向量、线性方程组、"
                 "矩阵的特征值与特征向量、二次型。**不考**向量空间（数一内容）。")

    return "\n".join([
        "# %s · 考研数学二速成复习资料" % sub["name"],
        "",
        "**本科目分值**：约 %d 分 / 150 分（%s）　|　**章节数**：%d　|　**考频样本**：%s"
        % (sub["score"], sub["ratio"], len(topics), T.SAMPLE_NOTE),
        "",
        "## 本科目章节索引",
        "",
        idx,
        "",
        "## 本科目在整卷中的位置",
        "",
        focus,
        "",
        scope,
        "",
        BANNER,
    ])


def build_subject(subject_key):
    sub = T.SUBJECTS[subject_key]
    topics = T.TOPICS[subject_key]
    outdir = os.path.join(CONTENT, sub["dir"])
    os.makedirs(outdir, exist_ok=True)
    written = []

    # 章节文件
    for t in topics:
        slug = t[6]
        src = os.path.join(PARTS, subject_key, slug + ".md")
        if not os.path.exists(src):
            raise SystemExit("缺少内容源：%s" % os.path.relpath(src, ROOT))
        body = "# %s · %s\n\n" % (sub["name"], t[0]) + build_topic(
            subject_key, t, parse_partial(src))
        dst = os.path.join(outdir, slug + ".md")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(NM.normalize(body))
        written.append(dst)

    # 科目总览
    # subject_overview() 自身已包含一级标题，不能再前置一次——
    # 否则成品 md / HTML 里会出现两行一模一样的标题（读者一眼可见的重复）。
    head = subject_overview(subject_key, topics)
    dst = os.path.join(outdir, "00-科目总览.md")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(NM.normalize(head))
    written.append(dst)
    return written


def main():
    T.check()
    keys = [a for a in sys.argv[1:] if not a.startswith("-")] or T.ORDER
    n = 0
    for k in keys:
        if k not in T.SUBJECTS:
            raise SystemExit("未知科目 %r（合法值：%s）" % (k, "、".join(T.ORDER)))
        for p in build_subject(k):
            print("生成:", os.path.relpath(p, ROOT))
            n += 1
    print("共生成 %d 个 Markdown 文件" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
