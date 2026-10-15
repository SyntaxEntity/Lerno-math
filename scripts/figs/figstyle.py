#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""绘图公共模块：中文字体、统一的输出目录、关键点落盘。

为什么需要它
------------
1. **中文字体**：matplotlib 默认字体不含中文，图里会出现方框。本模块在
   `setup()` 里显式挑选一个可用的 CJK 字体，找不到就**明确报错**而不是静默画方框。
2. **关键点落盘**：`verify_math.py` 要求「图上标注的关键点坐标必须等于 sympy
   算出的值」。本模块的 `save_points()` 把实际标注的坐标写进 `figs/data/<name>.json`，
   由 `verify_math.py` 读回来与符号计算比对——图和正文来自同一份数值。

所有绘图脚本都以 `import figstyle as S` 开头，并调用 `S.setup()`。
"""
import json
import os

import matplotlib

matplotlib.use("Agg")                     # 无显示环境，必须用 Agg
import matplotlib.pyplot as plt           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE = <repo>/scripts/figs；资产目录在 <repo>/数学二/assets（脚本上移到仓库根后要多经一层）
ASSETS = os.path.normpath(os.path.join(HERE, "..", "..", "数学二", "assets"))
DATA = os.path.join(HERE, "data")

# 候选 CJK 字体（按优先级）。本机实测存在 Noto Sans CJK SC。
CJK_CANDIDATES = [
    "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK TC",
    "Noto Sans Mono CJK SC", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
    "Source Han Sans SC", "SimHei", "Microsoft YaHei", "Droid Sans Fallback",
]


def setup():
    """配置中文字体与全局样式；返回选中的字体名。找不到中文字体则抛错。"""
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = None
    for name in CJK_CANDIDATES:
        if name in available:
            chosen = name
            break
    if chosen is None:
        raise SystemExit(
            "找不到可用的中文字体（候选：%s）。\n"
            "图里会画出方框，故直接失败而不是静默产出废图。\n"
            "请安装 fonts-noto-cjk 之类的中文字体后重试。"
            % "、".join(CJK_CANDIDATES))
    plt.rcParams["font.sans-serif"] = [chosen, "DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False      # 负号显示为正常减号
    plt.rcParams["figure.dpi"] = 110
    plt.rcParams["savefig.dpi"] = 150
    plt.rcParams["savefig.bbox"] = "tight"
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.25
    plt.rcParams["font.size"] = 11
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    return chosen


def save(fig, name):
    """把图保存到 数学二/assets/<name>.png，并关闭它。"""
    path = os.path.join(ASSETS, name + ".png")
    fig.savefig(path)
    plt.close(fig)
    size = os.path.getsize(path)
    print("  %-26s %7.1f KB" % (name + ".png", size / 1024.0))
    return path


def save_points(name, points):
    """把图上标注的关键点落盘，供 verify_math.py 复核（图-文一致性）。

    points: {标签: 数值 或 [数值,...]}；数值须可被 json 序列化（用 float/int/str）。
    """
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(points, f, ensure_ascii=False, indent=1, sort_keys=True)


def label_xy(ax, x, y, text, dx=6, dy=8, color="#c0392b", **kw):
    """在 (x, y) 处画一个点并加注释。"""
    ax.plot([x], [y], "o", ms=5, color=color, zorder=5)
    ax.annotate(text, (x, y), textcoords="offset points", xytext=(dx, dy),
                color=color, fontsize=10, **kw)
