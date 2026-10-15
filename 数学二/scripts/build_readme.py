#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 `数学二/README.md`：总览 + 考频总表 + 数据口径与可信度说明。

为什么由脚本生成：README 里的考频总表、原题/改编题清单、章节数都必须与
`meta.py` 和正文**逐字一致**。手写第二遍必然漂移（408 的教训：正文说 24 次、
总表说 22 次）。校验器 F2 / F12 会回比这些数字。

原题清单是**从内容源实扫出来的**，不是手抄的：`scan_citations()` 遍历
`parts/*/*.md`，把形如 `**2024 年数二第 12 题（…）**` 的行收集起来。
所以 README 的声明清单与正文标注天然一致（F12 双向校验）。

用法： python3 数学二/scripts/build_readme.py
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import meta as T          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
CONTENT = os.path.join(ROOT, "数学二")
PARTS = os.path.join(ROOT, "parts")

ORIG_RE = re.compile(r"^\*\*((?:19|20)\d{2})\s*年数二第\s*(\d+)\s*题（([^）]*)）\*\*")
ADAPT_RE = re.compile(r"^\*\*((?:19|20)\d{2})\s*年真题改编（([^）]*)）\*\*")

# 题型顺序，用于把清单排得好看
QTYPE_ORDER = ["选择题", "填空题", "解答题", "证明题"]


def scan_citations():
    """扫描内容源，返回 (原题清单, 改编清单)。

    原题：[(年, 题号, 题型, 知识点名)]；改编：[(年, 题型, 知识点名)]
    """
    orig, adapt = [], []
    for k in T.ORDER:
        for t in T.TOPICS[k]:
            p = os.path.join(PARTS, k, t[6] + ".md")
            if not os.path.exists(p):
                continue
            in_tr = False
            for ln in open(p, encoding="utf-8"):
                s = ln.strip()
                if s == "# 真题示例":
                    in_tr = True
                    continue
                if in_tr and s.startswith("# "):
                    break
                if not in_tr:
                    continue
                m = ORIG_RE.match(s)
                if m:
                    orig.append((m.group(1), m.group(2), m.group(3), t[0]))
                    continue
                m = ADAPT_RE.match(s)
                if m:
                    adapt.append((m.group(1), m.group(2), t[0]))
    return orig, adapt


def freq_table():
    rows = ["| 部分 | 知识点 | 考察次数 | 涉及年份 | 分值（建议权重） | 占比 | 高频 |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        for name, times, years, pts, qtype, hot, slug in T.TOPICS[k]:
            rows.append("| %s | [%s](数学二/%s/%s.md) | %s | %s | %d 分 | %s | %s |"
                        % (sub["name"], name, sub["dir"], slug,
                           T.PENDING if times == T.PENDING else "%d 次" % times,
                           years if times == T.PENDING else
                           "%s（%s）" % (years, T.SAMPLE_NOTE),
                           pts, T.ratio_of(k, slug), "**是**" if hot else "否"))
    return "\n".join(rows)


def subject_table():
    rows = ["| 部分 | 分值 | 占全卷 | 章节数 | 本次资料章节 |",
            "| --- | --- | --- | --- | --- |"]
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        links = "、".join("[%s](数学二/%s/%s.md)" % (t[0], sub["dir"], t[6])
                          for t in T.TOPICS[k])
        rows.append("| **%s** | %d 分 | %s | %d | %s |"
                    % (sub["name"], sub["score"], sub["ratio"], len(T.TOPICS[k]), links))
    rows.append("| **合计** | **%d 分** | 100%% | **%d** | —— |"
                % (sum(T.SUBJECTS[k]["score"] for k in T.ORDER),
                   sum(len(T.TOPICS[k]) for k in T.ORDER)))
    return "\n".join(rows)


# 依赖表里每个组件的用途说明（版本不在这里，版本从声明文件读）
DEP_USE = {
    "mermaid": "站点内置图运行时 + F3 真实解析校验",
    "katex": "站点内置公式运行时（含 60 个字体）",
    "jsdom": "给 mermaid 的 `parse()` 提供最小 DOM",
    "sympy": "全部数值复算（含图上坐标）",
    "matplotlib": "生成 `assets/*.png`",
    "Markdown": "Markdown → HTML",
}


def dep_table():
    """从 requirements*.txt 与 tools-package.json **读**出依赖表（不手写版本号）。

    为什么要生成而不是手写：这张表以前是手抄的，一旦依赖升级就会与实际
    装的东西对不上——而"文档里的版本 ≠ 实际装的版本"正是最难查的一类偏差
    （PLAN-对齐与改版 §1.2 要求版本只有一个数据源）。
    """
    rows = ["| 组件 | 锁定版本 | 来源文件 | 谁需要 | 用途 |",
            "| --- | --- | --- | --- | --- |"]
    items = []
    for fn, who in (("requirements.txt", "CI 门禁 + 校验"),
                    ("requirements-dev.txt", "本地生成链路")):
        path = os.path.join(HERE, fn)
        try:
            with open(path, encoding="utf-8") as f:
                for ln in f:
                    if ln.lstrip().startswith(("-r ", "#")):
                        continue
                    m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*==\s*([^\s#]+)", ln)
                    if m:
                        items.append((m.group(1), m.group(2), "`%s`" % fn, who))
        except Exception as e:                               # noqa: BLE001
            print("! 读不到 %s：%s" % (fn, e))
    try:
        with open(os.path.join(HERE, "tools-package.json"), encoding="utf-8") as f:
            for n, v in (json.load(f).get("dependencies") or {}).items():
                items.append((n, v, "`tools-package.json`", "CI 门禁 + 校验"))
    except Exception as e:                                   # noqa: BLE001
        print("! 读不到 tools-package.json：%s" % e)
    if not items:
        return "（依赖表生成失败：声明文件都读不到）"
    for n, v, src, who in items:
        rows.append("| %s | `%s` | %s | %s | %s |"
                    % (n, v, src, who,
                       DEP_USE.get(n) or DEP_USE.get(n.lower()) or "——"))
    return "\n".join(rows)


def main():
    T.check()
    orig, adapt = scan_citations()
    deps_tbl = dep_table()

    # ---- 原题清单（按年份倒序、题号升序）----
    if orig:
        orows = ["| 年份 | 题号 | 题型 | 所属知识点 |", "| --- | --- | --- | --- |"]
        for y, n, qt, topic in sorted(orig, key=lambda r: (-int(r[0]), int(r[1]))):
            orows.append("| `%s` | 第 `%s` 题 | %s | %s |" % (y, n, qt, topic))
        otbl = "\n".join(orows)
    else:
        otbl = "（无：本次交付未使用可逐字核对的原题）"

    if adapt:
        arows = ["| 年份 | 题型 | 所属知识点 |", "| --- | --- | --- |"]
        for y, qt, topic in sorted(adapt, key=lambda r: (-int(r[0]), r[2])):
            arows.append("| `%s` | %s | %s |" % (y, qt, topic))
        atbl = "\n".join(arows)
    else:
        atbl = "（无）"

    n_distinct = len({(a, b) for a, b, _c, _d in orig})
    doc = f"""# 考研数学二 · 速成复习资料

> 面向**已经系统学过数学二、需要快速过一遍**的考生。每章固定六段式：
> 考频统计 → 核心讲解 → 关键结论速记 → 示意图 → 易错点 → 真题示例。
> 本资料由脚本生成（`数学二/scripts/`），**不要手工编辑 `数学二/` 下的 .md**。

---

## 一、考试结构（已核实）

| 项目 | 内容 |
| --- | --- |
| 满分 / 时长 | **150 分 / 180 分钟** |
| 单项选择题 | {T.EXAM['choice']} |
| 填空题 | {T.EXAM['blank']} |
| 解答题（含证明题） | {T.EXAM['answer']} |
| 考查模块 | {T.EXAM['modules']} |

### ⚠️ 试卷结构沿革（这条很重要，能解释市面上互相矛盾的说法）

网上流传的两套「题型分值」说法**都曾经是对的**，因为它们对应不同年份：

| 时期 | 单选 | 填空 | 解答 | 合计 |
| --- | --- | --- | --- | --- |
| 2020 年及以前 | 8 题 × 4 分 = 32 分 | 6 题 × 4 分 = 24 分 | 9 题 = 94 分 | 150 分 |
| **2021 年起（现行）** | **10 题 × 5 分 = 50 分** | **6 题 × 5 分 = 30 分** | **6 题 = 70 分** | **150 分** |

**核实方式**：直接读真题原件的卷首说明（本地真题语料，见第六节）：

- 2020 年数二：「一、选择题(1～8 小题，每小题 4 分，共 32 分)」
- 2022 年数二：「一、选择题（1~10 小题，每小题 5 分，共 50 分）」
  「二、填空题（11~16 小题，每小题 5 分，共 30 分）」「三、解答题（17~22 小题，共 70 分）」
- 2023 年数二：同 2022
- 2024 年数二：选择题 1～10（每题 5 分，共 50 分）；解答题 17～22

**备考一律以现行结构（2021 年起）为准。** 本资料的题型标注均按现行结构。

### 范围边界（据数二考试大纲）

- **考**：函数、极限与连续；一元函数微分学；一元函数积分学（含反常积分）；
  **多元函数微积分学**（含二重积分）；常微分方程；线性代数六章。
- **不考**：概率论与数理统计；无穷级数；向量代数与空间解析几何；
  三重积分、曲线积分与曲面积分；线性代数中的向量空间（数一内容）。

> **一处需要你确认的差异**：任务书中原本把「多元函数微积分学」列为**不考**。
> 但核实大纲与真题后发现**它是要考的**：2025 年数二大纲原文列有
> 「四、多元函数微积分学」（二元函数极限与连续、偏导数与全微分、多元复合与
> 隐函数求导、多元极值与条件极值、二重积分）；真题层面，2024 年第 5、6、12、20 题、
> 2023 年第 13 题、2022 年第 2 题均涉及多元函数或二重积分。
> 因此本资料按大纲**增列了「09-多元函数微积分学」一章**（高等数学共 9 章）。

---

## 一点五、怎么用这份资料（建议从 HTML 开始）

**`数学二/index.html` 是主要学习界面**，建议直接用浏览器打开它：

| 你想做的事 | 怎么操作 |
| --- | --- |
| 一页看完全部内容 | 打开 `数学二/index.html`（高数 + 线代 15 章合并，约 170 KB） |
| 只看某一章 | 用左侧输入框筛选章节名，或点章节直接跳转 |
| 在章节内跳段 | 章节页左侧会自动展开「考频统计 / 核心讲解 / 速记 / 示意图 / 易错点 / 真题示例」 |
| 快速翻章 | 键盘 `←`/`k` 上一章、`→`/`j` 下一章；或点顶部的上一章/下一章 |
| 全文检索 | `Ctrl+F`（单页合集里直接搜） |
| 护眼/夜间 | 右下角「◐ 主题」切换，选择会被记住 |
| 打印或存 PDF | `Ctrl+P`，已做打印样式（自动隐藏导航、避免区块跨页断开） |

页面特征：**顶栏**（品牌 / 面包屑 / 搜索）、**左侧目录**（可筛选 + 当前章六段锚点 + 滚动高亮）、
**正文底部翻页**、**页脚**（许可与数据口径）；首页有**两张科目卡片**可直接进分科首页。
公式用**本地 KaTeX** 渲染、图用**本地 mermaid** 渲染，**完全离线可用**；
每章的六个字段各有独立区块与配色（速记是卡片网格、易错点是警示样式、真题是绿色区块），
滚动时顶部有阅读进度条，右下角有一键回到当前小节。

**核心讲解的阅读结构**：每章的核心讲解都按「【模块名】+【核心公式】+【适用条件】+【易错提醒】」
组织，用 `##` 分模块、列表拆解、公式单独成行、易混淆内容用表格对比
（如反常积分两类、微分方程特征根三种情形），关键条件加粗显示。
在 HTML 里这些模块会渲染成 `h3/h4` 层级，可直接用浏览器的文档大纲跳转。

**真题示例的解析**：一律「一步一段 + 关键公式独立成行」——大公式单独占一行的
`$$…$$`，短符号留在句子里。这样在手机上也能一眼看清每一步在算什么；
格式由校验项 F25 强制（任一段行内公式 ≤3 个、纯文字 ≤200 字）。

**Markdown 的定位**：`数学二/**/*.md` 是**由 `parts/` 生成的中间产物**，
用途是版本管理与二次加工，阅读体验不如 HTML。二者都由脚本生成，
改内容请改 `parts/` 后重跑 `run_all.py`。

---

## 二、交付物结构

```
数学二/
├── README.md              本文件
├── index.html             全科单页合集（高数 + 线代全部内容，可筛选、可 Ctrl+F）
├── 高等数学/
│   ├── 00-科目总览.md / .html
│   ├── 01-函数极限与连续.md / .html
│   ├── 02-导数与微分.md / .html
│   ├── 03-中值定理与导数应用.md / .html
│   ├── 04-不定积分.md / .html
│   ├── 05-定积分与反常积分.md / .html
│   ├── 06-定积分的几何与物理应用.md / .html
│   ├── 07-微分方程.md / .html
│   ├── 08-数二高数综合与证明专题.md / .html
│   └── 09-多元函数微积分学.md / .html
├── 线性代数/
│   ├── 00-科目总览.md / .html
│   └── 01-行列式.md … 06-二次型.md / .html
├── assets/                matplotlib 生成的 PNG + 外置样式与脚本
│                          （site.css / site.js，类名契约见 PLAN-对齐与改版 §2.4）
└── scripts/               生成与校验工具链
    ├── meta.py            单一数据源：全部统计数字只在这里写一次
    ├── build.py           组装成品（注入考频统计行 + 模板骨架 + 空行规范化）
    ├── normalize_md.py    幂等空行规范化器
    ├── validate.py        形式校验器（范围由它自己输出；每条都有反向测试，
    │                      F26 元校验保证两者集合相等）
    ├── verify_math.py     sympy 复算全部数值结果
    ├── extract_papers.py  从真题语料抽取题面，供逐字核对
    ├── build_readme.py    生成本文件
    ├── build_html.py      生成 HTML 站点
    ├── run_all.py         一键跑通全流水线
    ├── reverse_tests.py   反向测试：每条校验规则注入反例，确认它真会报错
    ├── check_mermaid.mjs  F3 的真实解析器层：node + 官方 mermaid parse()
    ├── test_site_js.mjs   F22 的行为层：jsdom 真跑 assets/site.js（12 条断言）
    ├── diff_math.py       公式不变量审阅：改排版前后，公式正文必须逐字一致
    ├── requirements.txt   Python 依赖：CI 与校验所需的全部（锁定版本）
    ├── requirements-dev.txt  本地生成链路额外所需（含 matplotlib）
    ├── tools-package.json Node 侧依赖清单（与站点运行时同版本）
    ├── REVERSE_TESTS.md   反向测试记录（含当场抓出的 7 个校验器缺陷）
    ├── PARTS_FORMAT.md    内容源写作契约
    └── figs/*.py          绘图代码（先代码后图形）+ figs/data/*.json 关键点坐标
```

内容源在同级的 `parts/gaoshu/`、`parts/xiandai/` 下。

---

## 三、考频数据口径与可信度（**请务必先读这一节**）

### 3.1 数据来源与置信度

| 数据 | 来源 | 置信度 |
| --- | --- | --- |
| 试卷结构（题型、题量、分值） | 真题原件卷首说明 | **高**（逐字核对） |
| 各部分分值占比（高数约 78%、线代约 22%） | 大纲与公开统计口径 | **中高** |
| 各章「考察次数」 | 本资料对真题逐题定章自行统计 | **中**（见 3.2 的局限） |
| 各章「分值（建议权重）」 | 本资料给出的**复习权重建议** | **中**（非官方数据） |
| 考试范围边界 | 数二考试大纲 | **高** |

### 3.2 「考察次数」的口径与已知局限

- **样本**：{T.SAMPLE_NOTE}，共 {len(T.SAMPLE_YEARS)} 套（44 道题）。
  **样本量小，请勿把「次数」当作长期占比来用**——它的用途是区分「必考主线」
  与「偶发考点」，而不是精确估计分值。
- **计数单位**：一题计 1 次；解答题串联多个考点时，计入其**主要**考查的那一章。
- **为什么只用这两年**：2021 年才改为现行结构；且本地语料中 **2021、2022 两年的
  OCR 文本存在题面缺失或答案与题干交错**，无法逐题定章。把抽不到的年份算作
  「没考」会系统性低估，因此**不计入**。
- **不确定度**：定章依「主要考查内容」判断，边界题（如「变限积分 + 极限」）
  可能归入相邻章节，存在 **±1 次**的不确定度。
- **「考频待补充」**：官方从不公布逐知识点考频，任何具体次数都来自第三方统计、
  口径不一。凡本资料无法核实的条目一律标注**考频待补充**，**绝不编造次数**。

### 3.3 与市面考频表的预期差异

市面辅导书（李永乐 / 张宇 / 武忠祥系列）公布的考频表多覆盖 10—15 年，且统计口径
（按题次 / 按分值 / 按知识点拆分粒度）各不相同，与本资料的两年样本**不可直接比较**。
本资料的做法是：**只给能自证的数字**，其余标注待补充，并在正文里给出该章的实际
命题方式（题型、常见考法），供你按题型判断优先级。

---

## 四、考频总表

### 4.1 两部分分值结构

{subject_table()}

### 4.2 逐知识点考频

{freq_table()}

---

## 五、图形与数值的可验证性

- **图形一律「先代码后图形」**：所有精确图像由 `数学二/scripts/figs/*.py`
  用 matplotlib 生成到 `数学二/assets/`，正文以相对路径引用。
  **不手写 SVG，不用 ASCII 硬凑函数图像。**
- **数值一律 sympy 复算**：`数学二/scripts/verify_math.py` 会复算资料中出现的
  极限值、导数、积分、反常积分敛散性、微分方程通解/特解、行列式值、秩、逆矩阵、
  方程组的解、特征值与特征向量、二次型标准形与正定性，以及几何应用中的
  面积、体积、弧长。
- **图上标注的关键点坐标必须等于 sympy 算出的值**：这是硬性要求，
  `verify_math.py` 会断言失败即报错。
- **mermaid 图用官方解析器真实 `parse()`**：静态正则查不出「标签含圆括号未加
  引号」这类直接解析失败的写法，所以校验器调用
  `数学二/scripts/check_mermaid.mjs`（node + 官方 mermaid）逐图真解析；
  扫描根跟着模式走——`--parts` 扫内容源 `parts/`，成品模式扫 `数学二/`，
  这样在「改 parts → `validate.py --parts`」的内层循环里也能立刻看到写坏的图。
  **解析器不在、node 不在、返回码非 0、一块图都没扫到——这四种情况都会让校验
  直接失败**，而不是打一句「跳过真实解析」然后照样全绿。确实要离线跳过时，
  必须显式写 `python3 数学二/scripts/validate.py --no-mermaid`。

---

## 六、真题引用规范与核对方式

### 6.1 两级标注

| 标注 | 含义 |
| --- | --- |
| `**20XX 年数二第 N 题（题型，X 分）**` | 题面已用真题原件**逐字核对** |
| `**20XX 年真题改编（题型，X 分）**` | 考点与考法保留，**题面数据为改写**，或年份/题号无法确证 |

**绝不把改编题伪装成原题。** 凡无法确证的，一律降级为「改编」。

### 6.2 核对方式（可复核）

本地真题语料位于 `.tools/kmath2/`（GitHub: `TsekaLuk/Kaoyan-Math2-Papers`，
考研数学二真题 1987—2024，含 OCR 文本与 PDF 原件）。抽取任意一题比对：

```bash
python3 数学二/scripts/extract_papers.py --year 2024 --n 12   # 打印 2024 年第 12 题原文
python3 数学二/scripts/extract_papers.py --search 二重积分     # 全语料检索
```

### 6.3 已逐条核对的原题清单（共 {len({(a, b) for a, b, _c, _d in orig})} 道，正文标注 {len(orig)} 处）

> 说明：标题里的「{n_distinct} 道」是**题目去重**后的数量；下表有
> **{len(orig)} 行**，因为同一道题被两章各引用一次时会登记两行（例如
> 2024 年第 22 题同时作为「线性方程组」与「二次型」的示例）。
> 校验器 F12 会双向核对：表中出现的每一对 (年份, 题号) 都必须能在正文找到对应标注，
> 正文的每一处原题标注也必须在表中有行。

{otbl}

### 6.4 改编题清单（共 {len(adapt)} 道）

{atbl}

> 校验器 F12 会把上面的清单与正文标注**双向比对**：README 声明了但正文没有、
> 或正文标了但 README 没声明，都会报错。

---

## 七、工具链用法

### 7.1 依赖：按用途分两个文件，版本只写一次

**分工规则**（PLAN-对齐与改版 §1.2.1）：版本只写在声明文件里，工作流与脚本一律读它。

| 文件 | 含义 | 谁用 |
| --- | --- | --- |
| `requirements.txt` | **CI 与校验**所需的全部 | `.github/workflows/pages.yml`、`validate.py`、`verify_math.py` |
| `requirements-dev.txt` | 本地**生成链路**额外所需（`-r requirements.txt` + 增量） | `run_all.py`（绘图 / 复算 / 组装 / HTML） |

```bash
# CI 与校验（= 工作流装的那一套；不含 matplotlib）
python3 -m venv .tools/venv
.tools/venv/bin/python -m pip install -r 数学二/scripts/requirements.txt

# 本地生成链路（要重跑绘图/组装时用这个；它会把上面那套一并带入）
.tools/venv/bin/python -m pip install -r 数学二/scripts/requirements-dev.txt

# Node 侧（mermaid 真实解析校验 + 站点内置运行时）—— 版本锁在 tools-package.json
# 先把清单拷进 .tools/ 再让 npm 按清单装：与 CI（.github/workflows/pages.yml）
# 走的是同一条路径，因此本地和线上不可能装出两个版本。
mkdir -p .tools && cp 数学二/scripts/tools-package.json .tools/package.json
npm install --prefix .tools --cache /tmp/npm-cache --no-audit --no-fund
```

> **为什么 CI 不装 matplotlib**：图（`assets/*.png`）与 HTML 都已入库，CI 只做
> 「校验 + 打包」，**不重绘、不重生成产物**。matplotlib 只在本地重跑
> `数学二/scripts/figs/*.py` 时才需要，所以它在 `requirements-dev.txt` 里。
> 这样 `requirements.txt` 就是「CI 与校验所需」的**准确描述**，而不是一个被本地
> 需求撑大的清单。

> 这里**不再写版本号**：版本只在上面三个声明文件里各写一次，
> 工作流、校验器与本文档都从它们读。下面这张表**由构建时读取那些文件生成**，
> 因此永远不会和实际装的依赖跑偏。

{deps_tbl}

> **为什么要锁版本**：站点里内置的 `mermaid.min.js` / `katex/` 就是上面这两个版本，
> 而 F3 用同一个 mermaid 做解析校验——版本漂移会造出「校验过了但页面渲染不出来」
> 这种最难查的情况。`run_all.py` 开跑前会**比对实际安装版本**，不一致直接报出来。
>
> `.tools/` 是 gitignore 的**本地依赖目录**，可以随时删掉重建；
> `check_mermaid.mjs` 则放在受版本管理的 `数学二/scripts/` 下——
> 校验逻辑必须进仓库，否则「删掉 node_modules」就等于悄悄关掉了 F3。

### 7.2 跑流水线

```bash
# 一键跑通全流水线（绘图 → 复算 → 组装 → 校验 → 反向测试 → HTML）
python3 数学二/scripts/run_all.py

# 或分步执行
python3 数学二/scripts/verify_math.py            # sympy 复算全部数值 + 图文一致性
python3 数学二/scripts/normalize_md.py --check   # 检查内容源空行
python3 数学二/scripts/validate.py --parts       # 校验内容源
python3 数学二/scripts/build.py                  # 组装成品 Markdown
python3 数学二/scripts/build_readme.py           # 生成本 README
python3 数学二/scripts/validate.py               # 校验成品（形式）
python3 数学二/scripts/reverse_tests.py          # 反向测试：每条规则注入反例（CI 门禁②）
python3 数学二/scripts/build_html.py             # 生成 HTML 站点
node 数学二/scripts/check_mermaid.mjs --strict   # 单独跑 mermaid 真实解析

# 打包成待发布的站点目录（仓库内，已 gitignore；注意会先清空输出目录）
python3 数学二/scripts/pack_site.py math2-site
```

> **站点不入库、由 CI 现打包**：仓库跟踪的是源码、内容源、生成物与工具链；
> `math2-site/` 是 `pack_site.py` 的产物，随 `.gitignore` 排除。
> 发布走 `.github/workflows/pages.yml`：
> 推 `main` → 装依赖 → **门禁 ①** `validate.py`（形式，含 F26 元校验）
> → **门禁 ②** `reverse_tests.py`（反向测试：规则本身必须能被反例触发）
> → **门禁 ③** `verify_math.py`（数值：sympy 断言）
> → `pack_site.py math2-site` → 上传 artifact。
> 任何一道门禁不过就不部署。本地要看站点，自己跑一次打包即可
> （或直接打开 `数学二/index.html`，那同样是离线可用的站点）。

> `run_all.py` 会自动挑一个同时具备 sympy / matplotlib / markdown 的解释器
> （优先用 `.tools/venv/`，对应 `requirements-dev.txt`），并把 `MPLCONFIGDIR`
> 指到 `.tools/mplcache`——本机 `$HOME/.config` 是只读的，不设它每次都会退到
> 随机临时目录重建字体缓存。Node 依赖缺失时它会在开跑前明确报出来，
> 而不是等 F3 静默跳过。

### 校验项一览（每条都做过反向测试）

| 项 | 内容 |
| --- | --- |
| F1 | 模板字段齐全**且顺序正确**（按字段名定位，不按位置下标） |
| F2 | 正文统计行与 `meta.py` 逐字一致 |
| F3 | 围栏闭合、语言标签合法；mermaid 交**真实解析器** `parse()`（解析器缺失即报错，不许静默跳过） |
| F4 | 禁止占位符（TODO / 待补充讲解 / XXX …） |
| F5 | ASCII 图内不得出现全角字符（破坏等宽对齐） |
| F6 | 真题年份落在合理区间，且标注格式规范 |
| F7 | `[高频]` 标记与 `meta.py` 一致 |
| F8 | 每知识点 ≥1 张示意图 + ≥1 张流程图 |
| F9 | 核心讲解**结构化**：≥2 个 `## 【模块】`、独立成行 `$$` 公式块、`⚠️` 提醒、`【核心公式】`/`【适用条件】`、列表 ≥5 条、关键条件加粗 |
| F10 / F11 | 易错点 2—4 条、速记 3—8 条 |
| F12 | README 声明清单与正文标注**双向一致** |
| F13 | 块级元素之间有空行（**排除代码块内部**） |
| F14 | **渲染验证**：真实 Markdown 渲染器确认字段各自独立成段 |
| F15 | 所有相对链接可从仓库根解析；图片真实存在 |
| F16 | 交付物完整性（不静默缺失）+ 不含绝对路径 |
| F17 | LaTeX `$` 成对（数学科目特有） |
| F18 | 每张引用的图都有对应生成脚本（先代码后图形） |
| F19 | LaTeX 必须在 `$...$` 内，不得被反引号包裹（否则不渲染、且 `_` `^` 会被吃掉） |
| F20 | HTML：无占位符残留、公式区间无 `<em>` 污染、`$$` 块**与内容源等量**、上一章/下一章链接可达 |
| F21 | HTML：每页正文仅 1 个 `h1`；同一章节内不得有重复标题 |
| F22 | 外壳骨架：每页顶栏/面包屑/页脚/侧栏齐全，章节页有正文底部翻页与六段锚点，首页科目卡片数 = 科目数；**并用 jsdom 真跑 assets/site.js**（缺 node/jsdom 即报错） |
| F23 | 外置资源：assets/site.css / site.js 真的外置且处处可达；出现内联 `<style>`/`<script>` 即报错 |
| F24 | 渲染残留：正文里不得出现字面 `**`（加粗定界符没能闭合时页面会直接显示星号）；成品与内容源两种模式都查 |
| F25 | 解析排版：真题示例的解析必须一步一段、关键公式独立成行——任一段的行内公式 ≤3 个、纯文字 ≤200 字 |
| F26 | **元校验**：规则集合 ≡ 反向测试覆盖集合（缺覆盖即报错）；扫描型规则的受检对象数必须 > 0；文档与 CI 里不得硬编码 F 范围（范围只由校验器输出） |

> 反向测试记录见 `数学二/scripts/REVERSE_TESTS.md`。

---

## 八、我无法自验的部分（请你确认）

1. **HTML 中的 mermaid 渲染效果**：本环境无浏览器。我能验证的是——
   15 块 mermaid 源码**全部通过了官方解析器的 `parse()`**（解析器版本与站内运行时
   同源，见 7.1 的依赖表与 `tools-package.json`）、容器数量、脚本可达、锚点齐全、
   无绝对路径。
   **实际渲染出的图形请你在浏览器里打开 `数学二/index.html` 看一眼。**
   若解析器或 node 依赖缺失，校验会直接失败并告诉你装什么，不会静默跳过。
2. **考频次数的绝对值**：见第三节，只有 2023—2024 两年样本，存在 ±1 次不确定度。
   若你手上有更完整的考频表，改 `数学二/scripts/meta.py` 一个文件后重跑
   `build.py` 即可全局同步，无需改正文。
3. **真题题面的 OCR 准确性**：语料来自第三方 OCR。标注为「原题」的题目我已逐字
   比对语料，但若语料本身识别有误，题面可能仍有偏差。建议你对照纸质真题复核
   第六节 6.3 的清单。
4. **数学结论的表述风格**：定义、定理条件已按同济《高等数学》《线性代数》口径
   撰写并做条件完整性检查，但「是否讲得够清楚」需你按自身基础判断。
5. **考频次数的代表性**：样本只有 {len(T.SAMPLE_YEARS)} 套（共 44 题）。
   「考察次数 7 次」这类数字是**该样本内**的计数，不是长期占比。
   若你手上有更完整的考频表，只需改 `数学二/scripts/meta.py` 一处，
   重跑 `run_all.py` 即可让正文、总表、HTML 三处同步更新。
6. **HTML 的公式与图形渲染效果**：公式用**打包在本地的 KaTeX**（`数学二/katex/`，
   含 60 个字体文件）在浏览器端渲染，mermaid 用本地 `mermaid.min.js` 渲染，均**离线可用**。
   我能验证的是：文件已复制、`<script>`/`<link>` 引用可达、mermaid 源码能被官方解析器
   `parse()` 通过、页面无绝对路径——**但本环境没有浏览器，无法替你确认最终排版观感**。
   请打开 `数学二/index.html` 看一眼公式与图；若某处渲染异常，页面会显示明确的
   「未加载到公式渲染器 / 该图渲染失败」提示，而不会静默留白。
"""
    dst = os.path.join(CONTENT, "README.md")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(doc.rstrip("\n") + "\n")
    print("生成: %s" % os.path.relpath(dst, ROOT))
    print("  原题 %d 道 | 改编 %d 道 | 知识点 %d 个"
          % (len(orig), len(adapt), sum(len(v) for v in T.TOPICS.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
