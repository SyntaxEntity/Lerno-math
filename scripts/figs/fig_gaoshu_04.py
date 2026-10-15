#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高等数学 04—06 章插图。

产出（数学二/assets/）：
  gaoshu-04-fig1.png  f(x)=x 的三条积分曲线与 x=1 处的平行切线（斜率均为 1）
  gaoshu-04-fig2.png  不定积分选路流程（图形式）
  gaoshu-05-fig1.png  左：1/x 与 1/x² 的尾部与积分面积；右：1/√x 的瑕积分
  gaoshu-05-fig2.png  反常积分敛散性判定流程
  gaoshu-06-fig1.png  y=√x 与 y=x² 围成的区域及其绕 x 轴的旋转体
  gaoshu-06-fig2.png  微元法流程

运行： scripts/figs/fig_gaoshu_04.py
"""
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as S          # noqa: E402


def flow(ax, title, nodes, edges, xs=(0, 10), ys=(0, 10), w=6.6, h=1.2):
    """画一张竖向流程图。nodes: [(x, y, 文本, 颜色键)]；edges: [(i, j, 标签)]。"""
    ax.set_xlim(*xs)
    ax.set_ylim(*ys)
    ax.axis("off")
    ax.set_title(title, fontsize=11)
    pal = {"g": ("#eaf7ea", "#3f8f43"), "b": ("#eef5ff", "#3b6ea5"),
           "y": ("#fff8e1", "#b8912f"), "p": ("#f2eefb", "#6b4fa0"),
           "r": ("#fdeeee", "#a54b4b")}
    boxes = []
    for (x, y, text, key) in nodes:
        fc, ec = pal[key]
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=fc, ec=ec,
                               lw=1.2, zorder=2))
        ax.text(x, y, text, ha="center", va="center", fontsize=9, zorder=3)
        boxes.append((x, y))
    for (i, j, lab) in edges:
        p, q = boxes[i], boxes[j]
        ax.annotate("", xy=(q[0], q[1] + h / 2), xytext=(p[0], p[1] - h / 2),
                    arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.2))
        if lab:
            ax.text((p[0] + q[0]) / 2 + 1.7, (p[1] + q[1]) / 2, lab, fontsize=8.5,
                    color="#c0392b", ha="left", va="center",
                    bbox=dict(fc="white", ec="none", alpha=0.9))


def fig_04_1():
    """三条积分曲线 y=x²/2+C（C=-1,0,1）与 x=1 处斜率均为 1 的平行切线。"""
    fig, ax = plt.subplots(figsize=(7.0, 5.4))
    xs = np.linspace(-2.2, 2.2, 400)
    colors = ["#2c7fb8", "#1a7a3c", "#c0392b"]
    labels = ["$C=-1$", "$C=0$", "$C=1$"]
    for C, col, lab in zip((-1, 0, 1), colors, labels):
        ax.plot(xs, xs ** 2 / 2 + C, lw=1.9, color=col,
                label="$y=\\frac{x^2}{2}%s$" % ("+" + str(C) if C >= 0 else str(C)))
        y1 = 0.5 + C                       # x=1 处函数值
        # 切线：y = 1·(x-1) + y1
        xt = np.linspace(0.25, 1.75, 20)
        ax.plot(xt, (xt - 1) + y1, lw=1.2, ls="--", color=col, alpha=0.85)
        ax.plot([1], [y1], "o", color=col, ms=6, zorder=5)
    ax.annotate("三条切线互相平行\n斜率均 $=f(1)=1$", (1, 0.5),
                textcoords="offset points", xytext=(12, 26),
                color="#333", fontsize=9.5,
                bbox=dict(fc="#fffbe6", ec="#d8c98a", alpha=0.95))
    ax.annotate("$x=1$ 处切点纵坐标\n$-\\frac{1}{2},\\ \\frac{1}{2},\\ \\frac{3}{2}$",
                (1, 0.5), textcoords="offset points", xytext=(14, -52),
                color="#333", fontsize=9.5)
    ax.axhline(0, color="#888", lw=0.8)
    ax.axvline(1, color="#666", lw=0.9, ls=":")
    ax.set_xlim(-2.2, 2.3)
    ax.set_ylim(-1.8, 3.4)
    ax.set_title("同一被积函数 $f(x)=x$ 的三条积分曲线\n"
                 "（任两条相差常数；同一 $x$ 处切线平行）")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper center", fontsize=9, ncol=3)

    S.save_points("gaoshu-04-fig1", {
        "tangent_slope_at_1": 1.0,
        "tangent_y_at_1": [-0.5, 0.5, 1.5],
        "curves_C": [-1, 0, 1],
    })
    S.save(fig, "gaoshu-04-fig1")


def fig_04_2():
    """不定积分的选路流程。"""
    fig, ax = plt.subplots(figsize=(8.4, 5.6))
    flow(ax, "不定积分：从基本积分表出发的选路",
         [(5, 9.2, "先对照基本积分表，能否直接套公式？", "b"),
          (2.4, 7.0, "含 $\\varphi'(x)\\,dx$ 形式\n$\\Rightarrow$ 第一类换元（凑微分）", "g"),
          (7.6, 7.0, "含 $\\sqrt{a^2-x^2}$、$\\sqrt{x^2\\pm a^2}$\n$\\Rightarrow$ 三角代换", "y"),
          (2.4, 4.6, "两类函数相乘\n$\\Rightarrow$ 分部积分 $\\int u\\,dv=uv-\\int v\\,du$", "p"),
          (7.6, 4.6, "有理函数\n$\\Rightarrow$ 部分分式分解", "r"),
          (5, 2.2, "回代还原变量，并补上任意常数 $C$\n（结果可求导验算）", "b")],
         [(0, 1, None), (0, 2, None), (1, 3, None), (2, 4, None),
          (3, 5, None), (4, 5, None)],
         w=5.4)
    S.save(fig, "gaoshu-04-fig2")


def fig_05_1():
    """左：1/x 与 1/x² 的尾部积分；右：1/√x 的瑕积分。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.3))

    # ---- 左 ----
    ax = axes[0]
    xs = np.linspace(1, 10, 600)
    ax.plot(xs, 1 / xs, lw=1.9, color="#c0392b", label="$y=1/x$")
    ax.plot(xs, 1 / xs ** 2, lw=1.9, color="#2c7fb8", label="$y=1/x^2$")
    ax.fill_between(xs, 1 / xs ** 2, color="#2c7fb8", alpha=0.25)
    ax.plot([1], [1], "o", color="#1a7a3c", ms=6, zorder=5)
    ax.annotate("交点 $(1,1)$", (1, 1), textcoords="offset points",
                xytext=(10, 8), color="#1a7a3c", fontsize=9.5)
    ax.annotate("$\\int_1^{10}\\frac{dx}{x^2}=1-\\frac{1}{10}=0.9$\n"
                "$\\to 1$（$b\\to\\infty$，收敛）",
                (4.0, 0.28), fontsize=9.5, color="#2c7fb8",
                bbox=dict(fc="#eef5ff", ec="#9bb8d8", alpha=0.95))
    ax.annotate("$\\int_1^{10}\\frac{dx}{x}=\\ln 10\\approx 2.303$\n"
                "$\\to\\infty$（发散）",
                (3.2, 0.62), fontsize=9.5, color="#c0392b",
                bbox=dict(fc="#fdeeee", ec="#d8a3a3", alpha=0.95))
    ax.set_xlim(0.9, 10.4)
    ax.set_ylim(0, 1.15)
    ax.set_title("无穷限反常积分：$\\int_1^{+\\infty}x^{-p}dx$\n"
                 "$p=2$ 收敛，$p=1$ 发散")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper right", fontsize=9)

    # ---- 右 ----
    ax = axes[1]
    xs = np.linspace(0.02, 1, 800)
    ax.plot(xs, 1 / np.sqrt(xs), lw=1.9, color="#6b4fa0", label="$y=1/\\sqrt{x}$")
    ax.fill_between(xs, 1 / np.sqrt(xs), color="#6b4fa0", alpha=0.22)
    ax.axvline(0, color="#c0392b", lw=1.2, ls=":")
    ax.annotate("$x=0$ 为瑕点\n（函数无界）", (0, 3.0), textcoords="offset points",
                xytext=(8, 6), color="#c0392b", fontsize=9.5)
    ax.annotate("$\\int_0^1\\frac{dx}{\\sqrt{x}}=2\\sqrt{x}\|_0^1=2$\n收敛",
                (0.30, 1.25), fontsize=10, color="#6b4fa0",
                bbox=dict(fc="#f2eefb", ec="#b8a8dc", alpha=0.95))
    ax.set_xlim(-0.04, 1.05)
    ax.set_ylim(0, 5.2)
    ax.set_title("瑕积分：$\\int_0^1 x^{-1/2}dx = 2$（收敛）")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper right", fontsize=9)

    S.save_points("gaoshu-05-fig1", {
        "intersection": [1.0, 1.0],
        "convergent_area_to_10": 0.9,
        "convergent_limit": 1.0,
        "divergent_value_to_10": float(np.log(10)),
        "improper_value": 2.0,
    })
    S.save(fig, "gaoshu-05-fig1")


def fig_05_2():
    """反常积分敛散性判定流程。"""
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    flow(ax, "反常积分：先辨类型，再用 p 积分作基准",
         [(5, 9.3, "识别类型：无穷限？瑕点（被积函数无界）？", "b"),
          (2.4, 7.2, "无穷限 $\\int_a^{+\\infty}$\n→ 取极限 $\\lim_{b\\to\\infty}\\int_a^b$", "g"),
          (7.6, 7.2, "瑕积分 $\\int_a^b$（$c$ 为瑕点）\n→ 拆成 $\\int_a^c+\\int_c^b$ 取极限", "y"),
          (5, 5.0, "与 p 积分比较：\n$\\int_1^{+\\infty}\\frac{dx}{x^p}$ 在 $p>1$ 收敛；"
                   "$\\int_0^1\\frac{dx}{x^p}$ 在 $p<1$ 收敛", "p"),
          (5, 2.9, "比较判别法：$0\\leq f\\leq g$ 时\n"
                   "$\\int g$ 收敛 $\\Rightarrow\\int f$ 收敛；$\\int f$ 发散 $\\Rightarrow\\int g$ 发散", "r"),
          (5, 1.0, "两段都收敛才算收敛；任一段发散即发散", "b")],
         [(0, 1, None), (0, 2, None), (1, 3, None), (2, 3, None), (3, 4, None), (4, 5, None)],
         w=7.4, h=1.3)
    S.save(fig, "gaoshu-05-fig2")


def fig_06_1():
    """y=√x 与 y=x² 围成的区域（面积 1/3）及其绕 x 轴旋转体（体积 3π/10）。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6))

    # ---- 左：区域 ----
    ax = axes[0]
    xs = np.linspace(0, 1.25, 500)
    ax.plot(xs, np.sqrt(xs), lw=1.9, color="#2c7fb8", label="$y=\\sqrt{x}$")
    ax.plot(xs, xs ** 2, lw=1.9, color="#c0392b", label="$y=x^2$")
    xf = np.linspace(0, 1, 300)
    ax.fill_between(xf, xf ** 2, np.sqrt(xf), color="#1a7a3c", alpha=0.22)
    ax.plot([0, 1], [0, 1], "o", color="#1a7a3c", ms=6, zorder=5)
    ax.annotate("$(0,0)$", (0, 0), textcoords="offset points", xytext=(8, -14),
                color="#1a7a3c", fontsize=9.5)
    ax.annotate("$(1,1)$", (1, 1), textcoords="offset points", xytext=(-34, 8),
                color="#1a7a3c", fontsize=9.5)
    ax.annotate("$S=\\int_0^1(\\sqrt{x}-x^2)dx=\\frac{1}{3}$",
                (0.22, 0.72), fontsize=10, color="#1a7a3c",
                bbox=dict(fc="#eaf7ea", ec="#a8cbaa", alpha=0.95))
    ax.set_xlim(-0.05, 1.3)
    ax.set_ylim(-0.05, 1.3)
    ax.set_title("围成区域：交点 $(0,0)$、$(1,1)$，面积 $=\\frac{1}{3}$")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper left", fontsize=9)

    # ---- 右：旋转体轮廓 ----
    ax = axes[1]
    xs = np.linspace(0, 1, 400)
    ax.plot(xs, np.sqrt(xs), lw=1.7, color="#2c7fb8", ls="--",
            label="外半径 $\\sqrt{x}$")
    ax.plot(xs, -np.sqrt(xs), lw=1.7, color="#2c7fb8", ls="--")
    ax.plot(xs, xs ** 2, lw=1.5, color="#c0392b", ls=":",
            label="内半径 $x^2$")
    ax.plot(xs, -xs ** 2, lw=1.5, color="#c0392b", ls=":")
    ax.fill_between(xs, np.sqrt(xs), xs ** 2, color="#6b4fa0", alpha=0.16)
    ax.fill_between(xs, -np.sqrt(xs), -xs ** 2, color="#6b4fa0", alpha=0.16)
    ax.annotate("$V=\\pi\\int_0^1(x-x^4)dx=\\frac{3\\pi}{10}\\approx0.9425$",
                (0.14, -1.42), fontsize=10, color="#6b4fa0",
                bbox=dict(fc="#f2eefb", ec="#b8a8dc", alpha=0.95))
    ax.set_xlim(-0.05, 1.3)
    ax.set_ylim(-1.75, 1.35)
    ax.set_title("绕 $x$ 轴旋转：环形体，体积 $=\\frac{3\\pi}{10}$")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper left", fontsize=8.5)
    ax.set_aspect("equal")

    S.save_points("gaoshu-06-fig1", {
        "intersections": [0.0, 1.0],
        "area": 1.0 / 3.0,
        "volume": 3 * float(np.pi) / 10,
    })
    S.save(fig, "gaoshu-06-fig1")


def fig_06_2():
    """微元法流程。"""
    fig, ax = plt.subplots(figsize=(8.2, 5.4))
    flow(ax, "定积分应用：微元法四步",
         [(5, 9.2, "① 画图定界：找出交点与积分区间 $[a,b]$", "b"),
          (5, 7.2, "② 取微元：在 $[x,x+dx]$ 上把所求量近似为 $dQ$", "g"),
          (2.4, 5.0, "几何量\n面积 $dS=(y_1-y_2)\\,dx$\n体积 $dV=\\pi(y_1^2-y_2^2)\\,dx$\n"
                     "（$y_1$ 上边界，$y_2$ 下边界）", "y"),
          (7.6, 5.0, "物理量\n功 $dW=F(x)dx$\n压力 $dP=\\rho g\\,h\\,dA$", "y"),
          (5, 2.8, "③ 定限：按实际范围写出 $\\int_a^b dQ$", "p"),
          (5, 1.0, "④ 计算并检查量纲/符号是否合理", "r")],
         [(0, 1, None), (1, 2, None), (1, 3, None), (2, 4, None), (3, 4, None), (4, 5, None)],
         w=6.4)
    S.save(fig, "gaoshu-06-fig2")


def main():
    chosen = S.setup()
    print("中文字体：%s" % chosen)
    fig_04_1()
    fig_04_2()
    fig_05_1()
    fig_05_2()
    fig_06_1()
    fig_06_2()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
