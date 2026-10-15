#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线性代数 6 章插图（矩阵结构 / 判定流程）。

线代的「结构图」用矩阵示意图比折线图更贴切：把符号棋盘、分块矩阵、行阶梯形、
增广矩阵行最简形、特征向量排列、二次型三种形态画成带格子的示意矩阵。

产出：
  xiandai-01-fig1.png  代数余子式符号棋盘 + 分块三角行列式降阶
  xiandai-02-fig1.png  矩阵等价标准形 + 伴随矩阵按秩三段
  xiandai-03-fig1.png  向量按列拼阵 → 行阶梯形 → 主元列取极大无关组
  xiandai-04-fig1.png  增广矩阵 → 行最简形 → 自由未知量个数 n-r
  xiandai-05-fig1.png  相似对角化 P^{-1}AP=Lambda 的列对应关系
  xiandai-06-fig1.png  二次型三种形态与正交变换 A=QLambdaQ^T

运行： scripts/figs/fig_xiandai.py
"""
import os
import sys

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figstyle as S          # noqa: E402


def matrix_grid(ax, x0, y0, rows, cols, cell=0.42, texts=None, color="#eef5ff",
                ec="#3b6ea5", title=None, title_dy=0.30, fs=None, tcolor="#1f2328"):
    """在 (x0, y0) 处画一个 rows×cols 的矩阵格子，返回格子中心坐标表。"""
    fs = fs or min(11, 190 * cell / max(rows, cols) / 10 + 8)
    centers = []
    for i in range(rows):
        row = []
        for j in range(cols):
            cx, cy = x0 + j * cell, y0 - i * cell
            ax.add_patch(Rectangle((cx, cy), cell, cell, fc=color, ec=ec, lw=0.9,
                                   zorder=2))
            row.append((cx + cell / 2, cy + cell / 2))
        centers.append(row)
    if texts:
        for i in range(rows):
            for j in range(cols):
                t = texts[i][j] if i < len(texts) and j < len(texts[i]) else ""
                if t:
                    cx, cy = centers[i][j]
                    ax.text(cx, cy, t, ha="center", va="center", fontsize=fs,
                            zorder=3, color=tcolor)
    if title:
        ax.text(x0 + cols * cell / 2, y0 + title_dy, title, ha="center",
                va="bottom", fontsize=10.5, color="#1f2328")
    return centers


def arrow(ax, p, q, text=None, color="#c0392b"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=14,
                                 lw=1.4, color=color, zorder=4))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + 0.16, text, ha="center",
                va="bottom", fontsize=9, color=color)


def fig_01():
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.8))

    # ---- 左：符号棋盘 ----
    ax = axes[0]
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("代数余子式的符号棋盘 $(-1)^{i+j}$")
    signs = [["+", "-", "+"], ["-", "+", "-"], ["+", "-", "+"]]
    matrix_grid(ax, 1.2, 6.4, 3, 3, cell=0.95, texts=signs,
                color="#fff8e1", ec="#b8912f",
                title="展开时正负号按行、列标之和的奇偶交替")
    ax.text(1.2, 2.5, "例：按第 1 行展开\n"
                      "$D=a_{11}A_{11}-a_{12}A_{12}+a_{13}A_{13}$\n"
                      "（不是全部相加！）", fontsize=10, va="top", color="#c0392b",
            bbox=dict(fc="#fdeeee", ec="#d8a3a3", alpha=0.95))

    # ---- 右：分块三角 ----
    ax = axes[1]
    ax.set_xlim(0, 9.6)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("分块三角行列式：左下块为 $O$ 时 $|M|=|A|\\cdot|B|$")
    # 画 4x4 分块：左上 A(2x2) 右上 C(2x2) 左下 O 右下 B(2x2)
    mat = [[["a"], ["a"], ["c"], ["c"]],
           [["a"], ["a"], ["c"], ["c"]],
           [["0"], ["0"], ["b"], ["b"]],
           [["0"], ["0"], ["b"], ["b"]]]
    cols = ["#eaf7ea", "#eaf7ea", "#fdeeee", "#fdeeee"]
    ecs = ["#3f8f43", "#3f8f43", "#a54b4b", "#a54b4b"]
    for i in range(4):
        for j in range(4):
            ax.add_patch(Rectangle((1.4 + j * 0.78, 6.5 - i * 0.78), 0.78, 0.78,
                                   fc=cols[j], ec=ecs[j], lw=1.0, zorder=2))
            t = mat[i][j][0]
            ax.text(1.4 + j * 0.78 + 0.39, 6.5 - i * 0.78 + 0.39, t,
                    ha="center", va="center", fontsize=11, zorder=3)
    ax.text(2.18, 7.05, "$A$", ha="center", fontsize=12, color="#1a7a3c")
    ax.text(3.74, 7.05, "$C$", ha="center", fontsize=12, color="#a54b4b")
    ax.text(2.18, 5.05, "$O$", ha="center", fontsize=12, color="#666")
    ax.text(3.74, 5.05, "$B$", ha="center", fontsize=12, color="#a54b4b")
    ax.text(1.4, 2.6, "左下角整块为 $O$ 时，行列式等于两个对角块的乘积：\n"
                      "$|M|=|A|\\cdot|B|$（不必展开 4 阶）\n"
                      "同理：上三角、下三角、对角块都适用。",
            fontsize=10, va="top", color="#1a7a3c",
            bbox=dict(fc="#eaf7ea", ec="#a8cbaa", alpha=0.95))

    S.save_points("xiandai-01-fig1", {"sign_pattern": [[1, -1, 1], [-1, 1, -1], [1, -1, 1]]})
    S.save(fig, "xiandai-01-fig1")


def fig_02():
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.9))

    # ---- 左：等价标准形 ----
    ax = axes[0]
    ax.set_xlim(0, 9.4)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("初等变换把 $A$ 化为等价标准形（秩 $r$）")
    std = [["1", "0", "0"], ["0", "1", "0"], ["0", "0", "0"]]
    matrix_grid(ax, 1.0, 6.3, 3, 3, cell=0.85, texts=std, color="#eef5ff", ec="#3b6ea5")
    ax.text(1.0, 2.9, "行变换 $\nRightarrow$ 改变秩\n"
                      "$r(A)=$ 非零行数 $=$ 主元个数\n"
                      "初等矩阵可逆 $\\Rightarrow$ 等价不改变秩",
            fontsize=10, va="top", color="#3b6ea5",
            bbox=dict(fc="#eef5ff", ec="#9bb8d8", alpha=0.95))

    # ---- 右：伴随矩阵按秩三段 ----
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("伴随矩阵的秩：按 $r(A)$ 分三段（$A$ 为 $n$ 阶）")
    rows = [("$r(A)=n$", "$|A|\\neq0$", "$r(A^{*})=n$", "#eaf7ea", "#3f8f43"),
            ("$r(A)=n-1$", "$|A|=0$ 但存在 $n-1$ 阶非零子式", "$r(A^{*})=1$",
             "#fff8e1", "#b8912f"),
            ("$r(A)\\leq n-2$", "所有 $n-1$ 阶子式全为 $0$", "$r(A^{*})=0$",
             "#fdeeee", "#a54b4b")]
    y = 6.4
    for a, b, c, fc, ec in rows:
        ax.add_patch(Rectangle((0.3, y - 0.42), 9.4, 0.95, fc=fc, ec=ec, lw=1.1))
        ax.text(0.55, y, a, fontsize=10.5, va="center")
        ax.text(2.5, y, b, fontsize=9.5, va="center", color="#444")
        ax.text(7.6, y, c, fontsize=10.5, va="center", color=ec)
        y -= 1.55
    ax.text(0.3, 1.5, "核心恒等式：$AA^{*}=A^{*}A=|A|E$\n"
                      "由此推 $|A^{*}|=|A|^{n-1}$，且 $A$ 可逆时 $A^{*}=|A|A^{-1}$",
            fontsize=10, va="top", color="#333",
            bbox=dict(fc="#f2eefb", ec="#b8a8dc", alpha=0.95))

    S.save_points("xiandai-02-fig1", {"adjugate_rank_rule": [3, 1, 0]})
    S.save(fig, "xiandai-02-fig1")


def fig_03():
    fig, ax = plt.subplots(figsize=(10.6, 4.6))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("向量组按列拼成矩阵 → 行阶梯形 → 主元列即极大无关组")

    A = [["1", "2", "3", "4"], ["2", "4", "6", "8"], ["1", "1", "1", "1"]]
    c1 = matrix_grid(ax, 0.8, 6.3, 3, 4, cell=0.78, texts=A,
                     color="#eef5ff", ec="#3b6ea5", title="以 $\\alpha_1,\\dots,\\alpha_4$ 为列")
    R = [["1", "2", "3", "4"], ["0", "2", "4", "8"], ["0", "0", "0", "0"]]
    c2 = matrix_grid(ax, 8.2, 6.3, 3, 4, cell=0.78, texts=R,
                     color="#eaf7ea", ec="#3f8f43", title="行阶梯形（非零行 2 行）")
    arrow(ax, (4.2, 5.6), (8.0, 5.6), "初等行变换")
    # 标出主元列
    for j in (0, 1):
        cx, cy = c2[0][j]
        ax.add_patch(Rectangle((cx - 0.39, cy - 1.17), 0.78, 2.34, fc="none",
                               ec="#c0392b", lw=2.0, zorder=5))
    ax.text(8.2, 2.4, "主元在第 1、2 列\n$\\Rightarrow$ $r=2$，$\\alpha_1,\\alpha_2$ 是极大无关组\n"
                      "$\\alpha_3,\\alpha_4$ 可由它们线性表示",
            fontsize=10, va="top", color="#c0392b",
            bbox=dict(fc="#fdeeee", ec="#d8a3a3", alpha=0.95))
    ax.text(13.6, 6.0, "要点：\n"
                       "① 只能做**行**变换，列变换会改变列向量组\n"
                       "② 主元所在**列**对应原向量组的极大无关组\n"
                       "③ $r(A)=$ 行秩 $=$ 列秩",
            fontsize=10, va="top", color="#3b6ea5",
            bbox=dict(fc="#eef5ff", ec="#9bb8d8", alpha=0.95))

    S.save_points("xiandai-03-fig1", {"rank": 2, "pivot_cols": [1, 2]})
    S.save(fig, "xiandai-03-fig1")


def fig_04():
    fig, ax = plt.subplots(figsize=(10.8, 4.6))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("增广矩阵 $(A\\mid b)$ → 行最简形 → 读出解的结构")

    M = [["1", "2", "3", "1"], ["2", "4", "6", "2"], ["1", "1", "1", "1"]]
    matrix_grid(ax, 0.7, 6.3, 3, 4, cell=0.78, texts=M,
                color="#eef5ff", ec="#3b6ea5", title="增广矩阵 $(A\\mid b)$")
    R = [["1", "0", "-1", "1"], ["0", "1", "2", "0"], ["0", "0", "0", "0"]]
    c2 = matrix_grid(ax, 7.9, 6.3, 3, 4, cell=0.78, texts=R,
                     color="#eaf7ea", ec="#3f8f43", title="行最简形")
    arrow(ax, (3.9, 5.6), (7.6, 5.6), "初等行变换")
    for j in (0, 1):
        cx, cy = c2[0][j]
        ax.add_patch(Rectangle((cx - 0.39, cy - 1.17), 0.78, 2.34, fc="none",
                               ec="#c0392b", lw=2.0, zorder=5))
    ax.add_patch(Rectangle((c2[0][2][0] - 0.39, c2[0][2][1] - 1.17), 0.78, 2.34,
                           fc="none", ec="#b8912f", lw=2.0, ls="--", zorder=5))
    ax.text(7.9, 2.3, "主元列 1、2；第 3 列无主元 $\\Rightarrow$ 自由未知量个数 "
                      "$n-r=3-2=1$\n"
                      "令 $x_3=t$，得 $x_1=1+t$，$x_2=-2t$\n"
                      "通解 $=(1,0,0)^{T}+t(1,-2,1)^{T}$",
            fontsize=10, va="top", color="#c0392b",
            bbox=dict(fc="#fdeeee", ec="#d8a3a3", alpha=0.95))
    ax.text(14.2, 6.1, "判别：\n"
                       "$r(A)=r(A\\mid b)=n$ → 唯一解\n"
                       "$r(A)=r(A\\mid b)<n$ → 无穷多解\n"
                       "$r(A)<r(A\\mid b)$ → 无解",
            fontsize=10, va="top", color="#3b6ea5",
            bbox=dict(fc="#eef5ff", ec="#9bb8d8", alpha=0.95))

    S.save_points("xiandai-04-fig1", {"free_vars": 1, "rank": 2, "n": 3})
    S.save(fig, "xiandai-04-fig1")


def fig_05():
    fig, ax = plt.subplots(figsize=(11.0, 5.2))
    ax.set_xlim(0, 23)
    ax.set_ylim(0, 9)
    ax.axis("off")
    ax.set_title("相似对角化：$P^{-1}AP=\\Lambda$ —— 列与特征值一一对应")

    P = [["$p_{11}$", "$p_{12}$", "$p_{13}$"],
         ["$p_{21}$", "$p_{22}$", "$p_{23}$"],
         ["$p_{31}$", "$p_{32}$", "$p_{33}$"]]
    cP = matrix_grid(ax, 1.0, 7.2, 3, 3, cell=0.85, texts=P,
                     color="#eef5ff", ec="#3b6ea5")
    ax.text(2.275, 8.75, "$P$：列 = 特征向量", ha="center", fontsize=10.5, color="#3b6ea5")
    L = [["$\\lambda_1$", "0", "0"],
         ["0", "$\\lambda_2$", "0"],
         ["0", "0", "$\\lambda_3$"]]
    cL = matrix_grid(ax, 9.2, 7.2, 3, 3, cell=0.85, texts=L,
                     color="#eaf7ea", ec="#3f8f43")
    ax.text(10.475, 8.75, "$\\Lambda$：对角 = 特征值", ha="center", fontsize=10.5,
            color="#3f8f43")
    arrow(ax, (3.8, 5.8), (9.0, 5.8), "$P^{-1}AP$")

    # 列与特征量的对应：在矩阵正下方画同列号的直线箭头（不交叉）
    for j in range(3):
        px = 1.0 + j * 0.85 + 0.425
        qx = 9.2 + j * 0.85 + 0.425
        ax.plot([px, px], [4.55, 3.55], lw=1.0, color="#c0392b", ls=":")
        ax.plot([qx, qx], [4.55, 3.55], lw=1.0, color="#c0392b", ls=":")
        ax.annotate("", xy=(qx, 3.55), xytext=(px, 3.55),
                    arrowprops=dict(arrowstyle="-|>", color="#c0392b", lw=1.2,
                                    linestyle="--",
                                    connectionstyle="bar,fraction=0.0"))
        ax.text(px, 3.35, "$\\lambda_%d$" % (j + 1), ha="center", va="top",
                fontsize=9.5, color="#c0392b")
    ax.text(5.6, 3.45, "同列号 ↔ 同特征值", ha="center", va="top",
            fontsize=9.5, color="#c0392b")

    ax.text(14.4, 8.2, "一一对应：$P$ 第 $j$ 列 $\\leftrightarrow$ $\\Lambda$ 第 $j$ 个对角元\n"
                       "列的顺序必须与特征值顺序一致",
            fontsize=9.5, va="top", color="#3b6ea5",
            bbox=dict(fc="#eef5ff", ec="#9bb8d8", alpha=0.95))
    ax.text(14.4, 6.0, "可对角化 $\\Leftrightarrow$ 每个特征值的\n"
                       "几何重数 $=$ 代数重数\n"
                       "$\\Leftrightarrow$ 有 $n$ 个线性无关特征向量",
            fontsize=9.5, va="top", color="#6b4fa0",
            bbox=dict(fc="#f2eefb", ec="#b8a8dc", alpha=0.95))
    ax.text(1.0, 2.6, "实对称矩阵总有正交矩阵 $Q$ 使 $Q^{-1}AQ=Q^{T}AQ=\\Lambda$；\n"
                      "不同特征值的特征向量必正交，重根内部再做施密特正交化。",
            fontsize=9.5, va="top", color="#1a7a3c",
            bbox=dict(fc="#eaf7ea", ec="#a8cbaa", alpha=0.95))

    S.save_points("xiandai-05-fig1", {"columns_lambda_map": [1, 2, 3]})
    S.save(fig, "xiandai-05-fig1")


def fig_06():
    fig, ax = plt.subplots(figsize=(12.0, 4.4))
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 7.4)
    ax.axis("off")
    ax.set_title("二次型的三种形态：一般型 →（合同/正交变换）→ 标准形 → 规范形")

    def block(x, title, lines, fc, ec):
        ax.add_patch(Rectangle((x, 1.0), 7.6, 4.6, fc=fc, ec=ec, lw=1.4, zorder=2))
        ax.text(x + 3.8, 5.15, title, ha="center", fontsize=10.5, color=ec, zorder=3)
        ax.text(x + 0.35, 4.6, lines, fontsize=9.5, va="top", zorder=3)

    block(0.4, "一般型 $f=x^{T}Ax$",
          "$f=\\sum_{i,j}a_{ij}x_ix_j$\n$a_{ij}=a_{ji}$（取对称矩阵）\n"
          "交叉项存在\n秩 $=r(A)$，正负惯性指数由 $A$ 定",
          "#eef5ff", "#3b6ea5")
    block(10.4, "标准形（只含平方项）",
          "$f=d_1y_1^2+\\dots+d_ny_n^2$\n"
          "正交变换：$x=Qy$，$Q^{T}AQ=\\Lambda$\n"
          "配方法：$x=Cy$，$C$ 可逆\n"
          "系数即特征值（正交变换时）",
          "#eaf7ea", "#3f8f43")
    block(20.4, "规范形（系数为 $\\pm1$）",
          "$f=z_1^2+\\dots+z_p^2-z_{p+1}^2-\\dots-z_r^2$\n"
          "惯性定理：正项个数 $p$、负项个数 $q$\n"
          "由 $A$ 唯一确定，与变换无关\n"
          "正定 $\\Leftrightarrow p=n$（$q=0$）",
          "#f2eefb", "#6b4fa0")
    arrow(ax, (8.1, 3.3), (10.2, 3.3), "合同变换")
    arrow(ax, (18.1, 3.3), (20.2, 3.3), "再标准化")

    S.save_points("xiandai-06-fig1", {"inertia_invariant": True})
    S.save(fig, "xiandai-06-fig1")


def main():
    chosen = S.setup()
    print("中文字体：%s" % chosen)
    fig_01()
    fig_02()
    fig_03()
    fig_04()
    fig_05()
    fig_06()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
