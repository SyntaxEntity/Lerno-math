#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高等数学 01—03 章插图。

产出（数学二/assets/）：
  gaoshu-01-fig1.png  y=sin x/x 趋于 1；f(x)=|x|^{1/((1-x)(x-2))} 的间断点
  gaoshu-01-fig2.png  极限方法选择与间断点分类判定流程（图形式）
  gaoshu-02-fig1.png  y²=x 与其在原点处的曲率圆（圆心 (1/2,0)，半径 1/2）
  gaoshu-02-fig2.png  可导性判定与求导方法选择流程
  gaoshu-03-fig1.png  罗尔定理（y=4x-x²，ξ=2）与拉格朗日定理（y=x²，ξ=1）
  gaoshu-03-fig2.png  中值定理选择与辅助函数构造流程

图中所有关键点坐标由 numpy/sympy 计算得出后标注，并落盘供 verify_math.py 复核。
运行： 数学二/scripts/figs/fig_gaoshu_01.py
"""
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as S          # noqa: E402


def fig_01_1():
    """左：sin x / x 的补定义曲线；右：含可去与无穷间断点的函数。"""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    # ---- 左 ----
    ax = axes[0]
    xs = np.linspace(-12, 12, 2000)
    xs = xs[np.abs(xs) > 1e-6]
    ax.plot(xs, np.sin(xs) / xs, lw=1.8, label=r"$y=\frac{\sin x}{x}$")
    ax.axhline(0, color="#888", lw=0.8)
    ax.axvline(0, color="#888", lw=0.8, ls="--")
    ax.plot([0], [1.0], "o", color="#c0392b", ms=6, zorder=5)
    ax.annotate("补定义 $f(0)=1$\n$\\lim_{x\\to0}\\frac{\\sin x}{x}=1$",
                (0, 1.0), textcoords="offset points", xytext=(16, -30),
                color="#c0392b", fontsize=10)
    ax.set_ylim(-0.35, 1.25)
    ax.set_xlim(-12, 12)
    ax.set_title("重要极限：$\\sin x/x \\to 1$（$x\\to 0$）")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper right", fontsize=9)

    # ---- 右 ----
    ax = axes[1]
    x = np.linspace(-2.6, 2.6, 4000)
    x = x[(np.abs(x - 1) > 1e-3) & (np.abs(x - 2) > 1e-3) & (np.abs(x) > 1e-3)]
    y = np.abs(x) ** (1.0 / ((1 - x) * (x - 2)))
    y = np.where(np.isfinite(y), y, np.nan)
    ax.plot(x, y, lw=1.5, color="#2c7fb8")
    ax.set_ylim(0, 5.5)
    ax.set_xlim(-2.6, 2.6)
    for xv, txt in ((0, "$x=0$\n第二类"), (1, "$x=1$：可去\n（第一类）"),
                    (2, "$x=2$\n第二类")):
        ax.axvline(xv, color="#c0392b", ls=":", lw=1.0)
    ax.plot([1], [np.e], "o", color="#c0392b", ms=6, zorder=5)
    ax.annotate("$(1,\\,e)$", (1, np.e), textcoords="offset points",
                xytext=(-30, 12), color="#c0392b", fontsize=10)
    ax.text(0.02, 0.97, "$x=0,\\,x=2$ 处为无穷间断点（第二类）\n"
                        "$x=1$ 处极限为 $e$，是可去间断点（第一类）",
            transform=ax.transAxes, va="top", fontsize=9.5,
            bbox=dict(fc="#fffbe6", ec="#d8c98a", alpha=0.95))
    ax.set_title("$f(x)=|x|^{\\frac{1}{(1-x)(x-2)}}$ 的间断点")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")

    S.save_points("gaoshu-01-fig1", {
        "limit_at_0": 1.0,
        "f_at_1": float(np.e),
        "jump_points": [0.0, 2.0],
        "removable_point": 1.0,
    })
    S.save(fig, "gaoshu-01-fig1")


def fig_01_2():
    """极限方法选择 + 间断点分类的判定流程图（用图形方式表达分支）。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))

    def box(ax, x, y, w, h, text, fc="#eef5ff", ec="#3b6ea5"):
        ax.add_patch(plt.Rectangle((x - w / 2, y - h / 2), w, h,
                                   fc=fc, ec=ec, lw=1.2, zorder=2))
        ax.text(x, y, text, ha="center", va="center", fontsize=9, zorder=3)

    def arrow(ax, p, q, label=None):
        ax.annotate("", xy=q, xytext=p,
                    arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.2))
        if label:
            ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, label,
                    ha="center", va="center", fontsize=8.5, color="#c0392b",
                    bbox=dict(fc="white", ec="none", alpha=0.9))

    # ---- 左：求极限方法选择 ----
    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("求极限：方法选择")
    box(ax, 5, 9, 6.4, 1.1, "先判类型：$0/0$、$\\infty/\\infty$、$1^{\\infty}$、$\\infty-\\infty$")
    box(ax, 2.6, 6.9, 4.4, 1.5, "能用等价无穷小替换\n（乘除因子可直接换）", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 7.6, 6.9, 4.2, 1.5, "不能替换\n（加减项、幂指型）", fc="#fdeeee", ec="#a54b4b")
    box(ax, 2.6, 4.4, 4.4, 1.4, "化简后直接代入\n或约去零因子", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 8.6, 4.6, 2.6, 1.2, "洛必达\n（验前提）", fc="#fff8e1", ec="#b8912f")
    box(ax, 5.6, 4.6, 3.0, 1.2, "$1^{\\infty}$：取对数\n或 $e^{\\lim f(g-1)}$", fc="#fff8e1", ec="#b8912f")
    box(ax, 5, 1.9, 6.6, 1.5,
        "仍算不出：泰勒展开到足够阶\n（分母阶数决定展开阶数）", fc="#f2eefb", ec="#6b4fa0")
    arrow(ax, (5, 8.45), (2.6, 7.65))
    arrow(ax, (5, 8.45), (7.6, 7.65))
    arrow(ax, (2.6, 6.15), (2.6, 5.1))
    arrow(ax, (7.6, 6.15), (8.6, 5.2))
    arrow(ax, (7.6, 6.15), (5.6, 5.2))
    arrow(ax, (2.6, 3.7), (5, 2.65), "仍为未定式")
    arrow(ax, (8.6, 4.0), (5, 2.65), "仍为未定式")
    arrow(ax, (5.6, 4.0), (5, 2.65), "仍为未定式")

    # ---- 右：间断点分类 ----
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("间断点分类（先看左右极限是否存在）")
    box(ax, 5, 9, 7.2, 1.1, "$x_0$ 处 $f$ 无定义或 $\\lim f\\ne f(x_0)$：考察 $f(x_0^-)$、$f(x_0^+)$")
    box(ax, 2.7, 6.6, 4.6, 1.5, "两侧极限都存在\n（有限）→ 第一类", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 7.6, 6.6, 4.2, 1.5, "至少一侧不存在\n或为 $\\infty$ → 第二类", fc="#fdeeee", ec="#a54b4b")
    box(ax, 1.5, 3.9, 2.6, 1.4, "两者相等\n可去间断点", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 4.4, 3.9, 2.6, 1.4, "两者不等\n跳跃间断点", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 7.6, 3.9, 3.6, 1.4, "无穷间断点 / 振荡间断点", fc="#fdeeee", ec="#a54b4b")
    arrow(ax, (5, 8.45), (2.7, 7.35))
    arrow(ax, (5, 8.45), (7.6, 7.35))
    arrow(ax, (2.7, 5.85), (1.5, 4.6))
    arrow(ax, (2.7, 5.85), (4.4, 4.6))
    arrow(ax, (7.6, 5.85), (7.6, 4.6))

    S.save(fig, "gaoshu-01-fig2")


def fig_02_1():
    """y²=x 与它在原点的曲率圆：圆心 (1/2,0)、半径 1/2、原点处竖直切线。"""
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    ys = np.linspace(-1.05, 1.05, 800)
    ax.plot(ys ** 2, ys, lw=2.0, color="#2c7fb8", label=r"$y^2=x$")

    th = np.linspace(-np.pi, np.pi, 500)
    ax.plot(0.5 + 0.5 * np.cos(th), 0.5 * np.sin(th), lw=1.6, ls="--",
            color="#c0392b", label=r"曲率圆 $(x-\frac{1}{2})^2+y^2=\frac{1}{4}$")

    ax.plot([0], [0], "o", color="#1a7a3c", ms=7, zorder=6)
    ax.annotate("原点 $(0,0)$\n竖直切线 $x=0$", (0, 0), textcoords="offset points",
                xytext=(16, -44), color="#1a7a3c", fontsize=10)
    ax.plot([0.5], [0], "o", color="#c0392b", ms=7, zorder=6)
    ax.annotate("圆心 $(\\frac{1}{2},0)$", (0.5, 0), textcoords="offset points",
                xytext=(10, 16), color="#c0392b", fontsize=10)
    ax.plot([0, 0.5], [0, 0], lw=1.2, color="#c0392b")
    ax.text(0.25, 0.035, r"$R=\frac{1}{2}$", color="#c0392b", fontsize=10, ha="center")
    ax.axvline(0, color="#666", lw=1.1, ls=":")
    ax.axhline(0, color="#666", lw=0.8)
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal")
    ax.set_title("$y^2=x$ 在原点处：曲率 $K=2$，曲率半径 $R=1/2$")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="lower right", fontsize=9)

    S.save_points("gaoshu-02-fig1", {
        "curvature_K": 2.0,
        "radius_R": 0.5,
        "circle_center": [0.5, 0.0],
        "tangent_point": [0.0, 0.0],
    })
    S.save(fig, "gaoshu-02-fig1")


def fig_02_2():
    """可导性判定 + 求导方法选择的流程。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))

    def box(ax, x, y, w, h, text, fc="#eef5ff", ec="#3b6ea5"):
        ax.add_patch(plt.Rectangle((x - w / 2, y - h / 2), w, h,
                                   fc=fc, ec=ec, lw=1.2, zorder=2))
        ax.text(x, y, text, ha="center", va="center", fontsize=9, zorder=3)

    def arrow(ax, p, q, label=None):
        ax.annotate("", xy=q, xytext=p,
                    arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.2))
        if label:
            ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, label, ha="center",
                    va="center", fontsize=8.5, color="#c0392b",
                    bbox=dict(fc="white", ec="none", alpha=0.9))

    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("一点处可导性判定")
    box(ax, 5, 8.9, 6.8, 1.1, "先看连续性：不连续 $\\Rightarrow$ 必不可导")
    box(ax, 5, 6.9, 7.4, 1.3, "求差商极限 $\\lim_{x\\to x_0}\\frac{f(x)-f(x_0)}{x-x_0}$\n"
                              "或分别求左右导数")
    box(ax, 2.5, 4.3, 4.0, 1.4, "左导数 $=$ 右导数\n$\\Rightarrow$ 可导，值即导数", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 7.5, 4.3, 4.0, 1.4, "不相等或不存在\n$\\Rightarrow$ 不可导", fc="#fdeeee", ec="#a54b4b")
    box(ax, 5, 1.9, 7.0, 1.3, "分段点必须用定义求；\n含绝对值处按零点分区间讨论", fc="#fff8e1", ec="#b8912f")
    arrow(ax, (5, 8.35), (5, 7.55))
    arrow(ax, (5, 6.25), (2.5, 5.0))
    arrow(ax, (5, 6.25), (7.5, 5.0))
    arrow(ax, (2.5, 3.6), (5, 2.55))
    arrow(ax, (7.5, 3.6), (5, 2.55))

    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("求导方法选择")
    box(ax, 5, 9.1, 6.4, 1.0, "看函数以什么形式给出")
    box(ax, 1.7, 6.9, 3.0, 1.5, "显函数\n$y=f(x)$", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 4.9, 6.9, 3.0, 1.5, "隐函数\n$F(x,y)=0$", fc="#eef5ff", ec="#3b6ea5")
    box(ax, 8.1, 6.9, 3.2, 1.5, "参数方程\n$x=x(t),y=y(t)$", fc="#f2eefb", ec="#6b4fa0")
    box(ax, 1.7, 4.2, 3.4, 1.4, "四则 + 复合\n链式法则", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 4.9, 4.2, 3.4, 1.4, "两边对 $x$ 求导，\n$y$ 视为 $x$ 的函数", fc="#eef5ff", ec="#3b6ea5")
    box(ax, 8.1, 4.2, 3.6, 1.4, "$\\frac{dy}{dx}=\\frac{y'(t)}{x'(t)}$\n"
                              "$\\frac{d^2y}{dx^2}=\\frac{1}{x'(t)}\\cdot\\frac{d}{dt}\\left(\\frac{dy}{dx}\\right)$",
        fc="#f2eefb", ec="#6b4fa0")
    box(ax, 5, 1.7, 7.6, 1.3, "幂指函数 $u(x)^{v(x)}$：取对数或写成 $e^{v\\ln u}$",
        fc="#fff8e1", ec="#b8912f")
    arrow(ax, (5, 8.6), (1.7, 7.65))
    arrow(ax, (5, 8.6), (4.9, 7.65))
    arrow(ax, (5, 8.6), (8.1, 7.65))
    for x0 in (1.7, 4.9, 8.1):
        arrow(ax, (x0, 6.15), (x0, 4.9))
    arrow(ax, (1.7, 3.5), (5, 2.35))
    arrow(ax, (4.9, 3.5), (5, 2.35))
    arrow(ax, (8.1, 3.5), (5, 2.35))

    S.save(fig, "gaoshu-02-fig2")


def fig_03_1():
    """左：罗尔定理（y=4x-x²，[0,4]，ξ=2）；右：拉格朗日（y=x²，[0,2]，ξ=1）。"""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    # ---- 左：罗尔 ----
    ax = axes[0]
    x = np.linspace(-0.25, 4.25, 400)
    ax.plot(x, 4 * x - x ** 2, lw=1.9, color="#2c7fb8", label="$y=4x-x^2$")
    ax.plot([0, 4], [0, 0], lw=1.4, color="#1a7a3c", ls="-")
    ax.text(0.5, -1.15, "水平割线 $y=0$，$f(0)=f(4)=0$", color="#1a7a3c",
            fontsize=9.5, ha="left")
    ax.plot([2, 2], [0, 4], lw=1.3, ls="--", color="#c0392b")
    ax.plot([1.2, 2.8], [4, 4], lw=1.4, color="#c0392b", label="切线 $y=4$（水平）")
    ax.plot([2], [4], "o", color="#c0392b", ms=6.5, zorder=5)
    ax.annotate("$\\xi=2$，$f(2)=4$", (2, 4), textcoords="offset points",
                xytext=(8, 8), color="#c0392b", fontsize=10)
    ax.set_ylim(-1.4, 5.4)
    ax.set_xlim(-0.4, 4.4)
    ax.set_title("罗尔定理：$f(0)=f(4)$，$\\exists\\xi=2,\\ f'(\\xi)=0$")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper right", fontsize=9)

    # ---- 右：拉格朗日 ----
    ax = axes[1]
    x = np.linspace(-0.2, 2.3, 400)
    ax.plot(x, x ** 2, lw=1.9, color="#2c7fb8", label="$y=x^2$")
    ax.plot([0, 2], [0, 4], lw=1.4, color="#1a7a3c", label="割线 $y=2x$")
    xa = np.linspace(-0.1, 1.9, 100)
    ax.plot(xa, 2 * xa - 1, lw=1.4, ls="--", color="#c0392b",
            label="切线 $y=2x-1$")
    ax.plot([1], [1], "o", color="#c0392b", ms=6.5, zorder=5)
    ax.plot([0, 2], [0, 4], "o", color="#1a7a3c", ms=5, zorder=5)
    ax.annotate("$\\xi=1$，切点 $(1,1)$", (1, 1), textcoords="offset points",
                xytext=(-6, -34), color="#c0392b", fontsize=10)
    ax.set_ylim(-0.6, 4.8)
    ax.set_xlim(-0.35, 2.35)
    ax.set_title("拉格朗日：$\\frac{f(2)-f(0)}{2}=2=f'(1)$")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper left", fontsize=9)

    S.save_points("gaoshu-03-fig1", {
        "rolle_xi": 2.0,
        "rolle_value": 4.0,
        "lagrange_xi": 1.0,
        "lagrange_point": [1.0, 1.0],
        "secant_slope": 2.0,
    })
    S.save(fig, "gaoshu-03-fig1")


def fig_03_2():
    """中值定理选择与辅助函数构造的判定流程。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))

    def box(ax, x, y, w, h, text, fc="#eef5ff", ec="#3b6ea5"):
        ax.add_patch(plt.Rectangle((x - w / 2, y - h / 2), w, h,
                                   fc=fc, ec=ec, lw=1.2, zorder=2))
        ax.text(x, y, text, ha="center", va="center", fontsize=9, zorder=3)

    def arrow(ax, p, q, label=None):
        ax.annotate("", xy=q, xytext=p,
                    arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.2))
        if label:
            ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, label, ha="center",
                    va="center", fontsize=8.5, color="#c0392b",
                    bbox=dict(fc="white", ec="none", alpha=0.9))

    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("按结论形式选定理")
    box(ax, 5, 9.1, 7.0, 1.0, "看要证的结论里出现什么")
    box(ax, 2.2, 6.9, 4.0, 1.6, "只含 $f'(\\xi)=0$\n或 $f(a)=f(b)$", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 6.4, 6.9, 4.2, 1.6, "含 $\\frac{f(b)-f(a)}{b-a}=f'(\\xi)$",
        fc="#eef5ff", ec="#3b6ea5")
    box(ax, 9.0, 6.9, 1.8, 1.6, "含两个\n函数之比", fc="#fdeeee", ec="#a54b4b")
    box(ax, 2.2, 4.3, 3.6, 1.4, "罗尔定理", fc="#eaf7ea", ec="#3f8f43")
    box(ax, 6.4, 4.3, 3.6, 1.4, "拉格朗日定理", fc="#eef5ff", ec="#3b6ea5")
    box(ax, 9.0, 4.3, 1.9, 1.4, "柯西\n定理", fc="#fdeeee", ec="#a54b4b")
    box(ax, 5, 1.8, 8.4, 1.6,
        "高阶导数或需估计误差 $\\Rightarrow$ 泰勒公式\n"
        "（在展开点与端点间用拉格朗日余项）", fc="#f2eefb", ec="#6b4fa0")
    arrow(ax, (5, 8.6), (2.2, 7.7))
    arrow(ax, (5, 8.6), (6.4, 7.7))
    arrow(ax, (5, 8.6), (9.0, 7.7))
    for x0 in (2.2, 6.4, 9.0):
        arrow(ax, (x0, 6.1), (x0, 5.0))
    arrow(ax, (2.2, 3.6), (5, 2.6))
    arrow(ax, (6.4, 3.6), (5, 2.6))
    arrow(ax, (9.0, 3.6), (5, 2.6))

    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("构造辅助函数 $F(x)$ 的常用套路")
    box(ax, 5, 9.1, 6.6, 1.0, "把结论中的 $\\xi$ 换成 $x$，移项成 $=0$")
    box(ax, 5, 7.3, 7.6, 1.3, "若可整理成 $f'(x)+g(x)f(x)=0$",
        fc="#eaf7ea", ec="#3f8f43")
    box(ax, 5, 5.3, 7.6, 1.4, "取 $F(x)=e^{\\int g(x)\\,dx}f(x)$\n"
                              "（$g$ 为常数时即 $e^{kx}f(x)$）", fc="#eef5ff", ec="#3b6ea5")
    box(ax, 2.6, 3.0, 4.4, 1.5, "若含 $f(b)-f(a)$\n用拉格朗日/柯西", fc="#fff8e1", ec="#b8912f")
    box(ax, 7.4, 3.0, 4.6, 1.5, "若含两个中值点\n分区间用两次定理", fc="#f2eefb", ec="#6b4fa0")
    box(ax, 5, 0.9, 7.4, 1.1, "验证 $F$ 满足定理条件后套用结论", fc="#eef5ff", ec="#3b6ea5")
    arrow(ax, (5, 8.6), (5, 7.95))
    arrow(ax, (5, 6.65), (5, 6.0))
    arrow(ax, (5, 4.6), (2.6, 3.75))
    arrow(ax, (5, 4.6), (7.4, 3.75))
    arrow(ax, (2.6, 2.25), (5, 1.45))
    arrow(ax, (7.4, 2.25), (5, 1.45))

    S.save(fig, "gaoshu-03-fig2")


def main():
    chosen = S.setup()
    print("中文字体：%s" % chosen)
    fig_01_1()
    fig_01_2()
    fig_02_1()
    fig_02_2()
    fig_03_1()
    fig_03_2()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
