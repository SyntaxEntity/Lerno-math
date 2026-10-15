#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高等数学 07—09 章插图。

产出：
  gaoshu-07-fig1.png  一阶线性方程 y'+y=e^{-x} 的解曲线族（含特解 y=xe^{-x}）
  gaoshu-07-fig2.png  微分方程类型判定与解法选择流程
  gaoshu-08-fig1.png  拉格朗日中值定理的弦与平行切线（综合证明的几何原型）
  gaoshu-08-fig2.png  证明题：结论形式 → 辅助函数 → 定理选择
  gaoshu-09-fig1.png  二重积分区域（xy=1/3、xy=3、y=x/3、y=3x 围成）与双曲线变换
  gaoshu-09-fig2.png  多元极值判定与二重积分计算路线

运行： 数学二/scripts/figs/fig_gaoshu_07.py
"""
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as S          # noqa: E402


def flow(ax, title, nodes, edges, w=6.6, h=1.2, xs=(0, 10), ys=(0, 10),
         pal_extra=None):
    ax.set_xlim(*xs)
    ax.set_ylim(*ys)
    ax.axis("off")
    ax.set_title(title, fontsize=11)
    pal = {"g": ("#eaf7ea", "#3f8f43"), "b": ("#eef5ff", "#3b6ea5"),
           "y": ("#fff8e1", "#b8912f"), "p": ("#f2eefb", "#6b4fa0"),
           "r": ("#fdeeee", "#a54b4b")}
    if pal_extra:
        pal.update(pal_extra)
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
            ax.text((p[0] + q[0]) / 2 + 1.6, (p[1] + q[1]) / 2, lab, fontsize=8.5,
                    color="#c0392b", ha="left", va="center",
                    bbox=dict(fc="white", ec="none", alpha=0.9))


def fig_07_1():
    """y' + y = e^{-x} 的解曲线族 y=(x+C)e^{-x}，标注特解与极大值点。"""
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    xs = np.linspace(-1.6, 4.2, 600)
    for C, col, lw in ((-2, "#9bb8d8", 1.3), (-1, "#6b9dc9", 1.3),
                       (0, "#c0392b", 2.2), (1, "#6b9dc9", 1.3), (2, "#9bb8d8", 1.3)):
        ax.plot(xs, (xs + C) * np.exp(-xs), lw=lw, color=col,
                label=("特解 $C=0$：$y=xe^{-x}$" if C == 0 else "$C=%d$" % C))
    # 特解极大值点：y'=e^{-x}(1-x)=0 -> x=1, y=1/e
    ax.plot([1], [1 / np.e], "o", color="#1a7a3c", ms=7, zorder=6)
    ax.annotate("极大值点 $(1,\\ \\frac{1}{e})$", (1, 1 / np.e),
                textcoords="offset points", xytext=(12, 12),
                color="#1a7a3c", fontsize=10)
    ax.axhline(0, color="#888", lw=0.8)
    ax.axvline(0, color="#888", lw=0.8)
    ax.set_xlim(-1.6, 4.2)
    ax.set_ylim(-1.4, 2.2)
    ax.set_title("一阶线性方程 $y'+y=e^{-x}$ 的解曲线族 $y=(x+C)e^{-x}$\n"
                 "任两条曲线不相交；$C$ 由初始条件定出")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper left", fontsize=8.5)

    S.save_points("gaoshu-07-fig1", {
        "max_point": [1.0, 1.0 / float(np.e)],
        "particular_solution": "y=(x)e^{-x}",
    })
    S.save(fig, "gaoshu-07-fig1")


def fig_07_2():
    """微分方程类型判定与解法选择。"""
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    flow(ax, "微分方程：先判阶数与类型，再选解法",
         [(5, 9.3, "① 定阶数与是否线性", "b"),
          (2.4, 7.3, "一阶\n$y'=f(x)g(y)$ 可分离", "g"),
          (5, 7.3, "一阶线性\n$y'+P(x)y=Q(x)$", "y"),
          (7.6, 7.3, "可降阶高阶\n$y''=f(x)$、$y''=f(x,y')$、$y''=f(y,y')$", "p"),
          (2.4, 5.0, "分离变量后两边积分\n得隐式通解", "g"),
          (5, 5.0, "通解 $y=e^{-\\int P dx}\\left(\\int Qe^{\\int P dx}dx+C\\right)$", "y"),
          (7.6, 5.0, "逐次积分或令 $p=y'$ 降为一阶", "p"),
          (5, 2.8, "二阶常系数：写特征方程 $r^2+pr+q=0$\n"
                   "两不等实根 / 重根 / 共轭复根 三种通解形式", "r"),
          (5, 1.0, "非齐次：通解 = 齐次通解 + 一个特解；"
                   "自由项为 $P_m(x)e^{\\alpha x}$ 型用待定系数法", "b")],
         [(0, 1, None), (0, 2, None), (0, 3, None),
          (1, 4, None), (2, 5, None), (3, 6, None),
          (4, 7, None), (5, 7, None), (6, 7, None), (7, 8, None)],
         w=6.6, h=1.15)
    S.save(fig, "gaoshu-07-fig2")


def fig_08_1():
    """拉格朗日中值定理的几何原型（综合证明题的常用工具）。"""
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    xs = np.linspace(-0.35, 2.15, 400)
    f = xs ** 3 - 3 * xs ** 2 + 2 * xs + 1
    ax.plot(xs, f, lw=2.0, color="#2c7fb8", label="$y=f(x)$")
    a, b = 0.0, 2.0
    fa, fb = 1.0, 1.0
    ax.plot([a, b], [fa, fb], lw=1.5, color="#1a7a3c", label="弦（割线）")
    ax.plot([a, b], [fa, fb], "o", color="#1a7a3c", ms=6, zorder=5)
    ax.annotate("$(a,f(a))$", (a, fa), textcoords="offset points",
                xytext=(6, -18), color="#1a7a3c", fontsize=9.5)
    ax.annotate("$(b,f(b))$", (b, fb), textcoords="offset points",
                xytext=(-46, 10), color="#1a7a3c", fontsize=9.5)
    ax.annotate("此处 $f(a)=f(b)$：\n弦水平 $\\Rightarrow$ 退化为罗尔定理",
                (1.0, 1.0), textcoords="offset points", xytext=(-30, -60),
                color="#c0392b", fontsize=9.5,
                bbox=dict(fc="#fdeeee", ec="#d8a3a3", alpha=0.95))
    ax.set_xlim(-0.35, 2.15)
    ax.set_ylim(-0.2, 2.4)
    ax.set_title("拉格朗日中值定理：弦的斜率 $=\\frac{f(b)-f(a)}{b-a}=f'(\\xi)$\n"
                 "（本题 $f(a)=f(b)=1$，弦水平，$\\xi=1$）")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper center", fontsize=9)

    S.save_points("gaoshu-08-fig1", {
        "endpoints_y": [1.0, 1.0],
        "crit_point": [1.0, 1.0],
        "secant_slope": 0.0,
    })
    S.save(fig, "gaoshu-08-fig1")


def fig_08_2():
    """证明题：结论形式 → 辅助函数 → 定理选择。"""
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    flow(ax, "中值定理证明题：从结论反推辅助函数",
         [(5, 9.3, "把结论中的 $\\xi$ 换成 $x$，全部移到一边记为 $=0$", "b"),
          (2.4, 7.2, "形如 $f'(x)=0$", "g"),
          (5, 7.2, "形如 $f'(x)+g(x)f(x)=0$", "y"),
          (7.6, 7.2, "含 $f(b)-f(a)$\n或两个中值点", "p"),
          (2.4, 5.0, "取 $F(x)=f(x)$\n（罗尔定理）", "g"),
          (5, 5.0, "取 $F(x)=e^{\\int g\\,dx}f(x)$\n（$g$ 为常数即 $e^{kx}f(x)$）", "y"),
          (7.6, 5.0, "分区间用两次\n拉格朗日 / 柯西定理", "p"),
          (5, 2.7, "验证 $F$ 在 $[a,b]$ 连续、在 $(a,b)$ 可导（**条件必须写全**）", "r"),
          (5, 1.0, "由罗尔定理得 $F'(\\xi)=0$，再化回原结论", "b")],
         [(0, 1, None), (0, 2, None), (0, 3, None),
          (1, 4, None), (2, 5, None), (3, 6, None),
          (4, 7, None), (5, 7, None), (6, 7, None), (7, 8, None)],
         w=6.8, h=1.15)
    S.save(fig, "gaoshu-08-fig2")


def fig_09_1():
    """2024 年第 17 题的积分区域 D 与 (u,v)=(xy, y/x) 坐标变换。

    D 由 xy=1/3、xy=3、y=x/3、y=3x 在第一象限围成，四个顶点为
    (1/3,1)、(1,1/3)、(1,3)、(3,1)；变换后 u∈[1/3,3]、v∈[1/3,3] 是矩形，
    雅可比 |∂(x,y)/∂(u,v)| = 1/(2v)。
    """
    from matplotlib.patches import Polygon
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.9))

    V = [(1 / 3, 1), (1, 1 / 3), (1, 3), (3, 1)]

    # ---- 左：原坐标下的区域 ----
    ax = axes[0]
    ax.add_patch(Polygon([(1 / 3, 1), (1, 3), (3, 1), (1, 1 / 3)],
                         closed=True, fc="#1a7a3c", ec="#1a7a3c", alpha=0.18, lw=1.4))
    xs1 = np.linspace(1 / 3, 1, 300)
    ax.plot(xs1, 1 / (3 * xs1), lw=1.9, color="#2c7fb8", label="$xy=\\frac{1}{3}$")
    xs2 = np.linspace(1, 3, 300)
    ax.plot(xs2, 3 / xs2, lw=1.9, color="#c0392b", label="$xy=3$")
    xs3 = np.linspace(1 / 3, 1, 300)
    ax.plot(xs3, xs3 / 3, lw=1.9, color="#1a7a3c", label="$y=\\frac{x}{3}$")
    xs4 = np.linspace(1, 3, 300)
    ax.plot(xs4, 3 * xs4, lw=1.9, color="#6b4fa0", label="$y=3x$")
    for (vx, vy), name in zip(V, ["$(\\frac{1}{3},1)$", "$(1,\\frac{1}{3})$",
                                  "$(1,3)$", "$(3,1)$"]):
        ax.plot([vx], [vy], "o", color="#111", ms=5.5, zorder=6)
        ax.annotate(name, (vx, vy), textcoords="offset points",
                    xytext=(7, -13 if vy < 1 else 7), fontsize=9, color="#111")
    ax.annotate("$D$：$\\frac{1}{3}\\leq xy\\leq 3$，$\\frac{1}{3}\\leq\\frac{y}{x}\\leq 3$",
                (0.95, 1.05), fontsize=10, ha="center",
                bbox=dict(fc="#fffbe6", ec="#d8c98a", alpha=0.95))
    ax.set_xlim(0.1, 3.5)
    ax.set_ylim(0.1, 3.6)
    ax.set_title("积分区域 $D$（2024 第 17 题）")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.legend(loc="upper right", fontsize=8.5)

    # ---- 右：u-v 平面上的矩形 ----
    ax = axes[1]
    ax.add_patch(plt.Rectangle((1 / 3, 1 / 3), 3 - 1 / 3, 3 - 1 / 3,
                               fc="#eef5ff", ec="#3b6ea5", lw=1.8, zorder=2))
    ax.text(5 / 3, 1.67,
            "变换后是矩形\n$u\\in[\\frac{1}{3},3],\\ v\\in[\\frac{1}{3},3]$\n"
            "$\\left|\\frac{\\partial(x,y)}{\\partial(u,v)}\\right|=\\frac{1}{2v}$\n"
            "$\\iint_D(1+x-y)\\,dxdy=\\frac{8}{3}\\ln 3$",
            ha="center", va="center", fontsize=10, color="#3b6ea5")
    for vx, lab in ((1 / 3, "$\\frac{1}{3}$"), (3, "$3$")):
        ax.axvline(vx, color="#888", lw=0.9, ls=":")
        ax.axhline(vx, color="#888", lw=0.9, ls=":")
    ax.set_xlim(0, 3.6)
    ax.set_ylim(0, 3.6)
    ax.set_title("换元 $u=xy,\\ v=\\frac{y}{x}$：曲边区域拉直成矩形")
    ax.set_xlabel("$u$")
    ax.set_ylabel("$v$")
    ax.set_aspect("equal")

    S.save_points("gaoshu-09-fig1", {
        "vertices": [[1 / 3, 1], [1, 1 / 3], [1, 3], [3, 1]],
        "u_range": [1 / 3, 3],
        "v_range": [1 / 3, 3],
        "jacobian": "1/(2v)",
        "integral_value": "(8/3)ln3",
    })
    S.save(fig, "gaoshu-09-fig1")


def fig_09_2():
    """多元极值判定 + 二重积分计算路线。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.8))

    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("二元函数极值判定")
    pal = {"g": ("#eaf7ea", "#3f8f43"), "b": ("#eef5ff", "#3b6ea5"),
           "y": ("#fff8e1", "#b8912f"), "r": ("#fdeeee", "#a54b4b"),
           "p": ("#f2eefb", "#6b4fa0")}

    def box(a, x, y, w, h, t, k):
        fc, ec = pal[k]
        a.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=fc, ec=ec, lw=1.2))
        a.text(x, y, t, ha="center", va="center", fontsize=9)

    def arr(a, p, q):
        a.annotate("", xy=q, xytext=p,
                   arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.2))
    box(ax, 5, 9.0, 8.0, 1.1, "求驻点：解 $f_x=0$ 且 $f_y=0$", "b")
    box(ax, 5, 7.2, 8.4, 1.2, "记 $A=f_{xx}$、$B=f_{xy}$、$C=f_{yy}$（在驻点取值）", "y")
    box(ax, 2.6, 4.9, 4.4, 1.5, "$AC-B^2>0$：是极值点\n$A<0$ 极大，$A>0$ 极小", "g")
    box(ax, 7.4, 4.9, 4.6, 1.5, "$AC-B^2<0$：不是极值点\n$AC-B^2=0$：判别法失效", "r")
    box(ax, 5, 2.3, 8.6, 1.4, "有界闭区域最值：内部驻点值 与 边界最值 一起比较", "b")
    box(ax, 5, 0.8, 8.6, 1.0, "带约束用拉格朗日乘数法 $L=f+\\lambda\\varphi$，候选点需比较", "y")
    arr(ax, (5, 8.45), (5, 7.8))
    arr(ax, (5, 6.6), (2.6, 5.65))
    arr(ax, (5, 6.6), (7.4, 5.65))
    arr(ax, (2.6, 4.15), (5, 3.0))
    arr(ax, (7.4, 4.15), (5, 3.0))
    arr(ax, (5, 1.6), (5, 1.3))

    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("二重积分计算路线")
    box(ax, 5, 9.0, 8.2, 1.1, "① 画区域图，写出不等式描述", "b")
    box(ax, 2.7, 7.0, 4.6, 1.4, "② 选坐标系\n圆/扇形/圆环 或含 $x^2+y^2$ → 极坐标", "y")
    box(ax, 7.5, 7.0, 4.4, 1.4, "直角坐标：X 型 或 Y 型\n定限口诀：外常数、内函数", "g")
    box(ax, 2.7, 4.6, 4.6, 1.4, "$dxdy=r\\,drd\\theta$\n**不要漏掉因子 $r$**", "r")
    box(ax, 7.5, 4.6, 4.4, 1.4, "算不出就交换次序：\n重新用不等式描述同一区域", "p")
    box(ax, 5, 2.2, 8.4, 1.3, "③ 用对称性简化：关于 $x$ 轴/直线 $y=x$ 的对称", "b")
    box(ax, 5, 0.8, 8.4, 1.0, "④ 先算内层（上限减下限），再算外层", "g")
    arr(ax, (5, 8.45), (2.7, 7.75))
    arr(ax, (5, 8.45), (7.5, 7.75))
    arr(ax, (2.7, 6.3), (2.7, 5.35))
    arr(ax, (7.5, 6.3), (7.5, 5.35))
    arr(ax, (2.7, 3.9), (5, 2.9))
    arr(ax, (7.5, 3.9), (5, 2.9))
    arr(ax, (5, 1.55), (5, 1.3))

    S.save(fig, "gaoshu-09-fig2")


def main():
    chosen = S.setup()
    print("中文字体：%s" % chosen)
    fig_07_1()
    fig_07_2()
    fig_08_1()
    fig_08_2()
    fig_09_1()
    fig_09_2()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
