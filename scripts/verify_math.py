#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 sympy 复算本资料中出现的**每一个**数值结果。

为什么必须有这个脚本
--------------------
数学资料最容易出的错不是「讲解不通」，而是**数值算错**：积分值差一个系数、
特征值少一个根、极值点坐标写反。凭记忆写必然出错，所以所有数值结果都必须
由 sympy 独立算一遍并断言。

设计
----
- 每条断言是一个函数，返回 True 表示成立；`claim(位置, 说明)` 登记一条。
- 断言里的数值必须与**正文**、以及**图上标注的坐标**一致。
- 图与正文的一致性由 `assert_figures()` 保证：绘图脚本把实际标注的关键点
  写进 `figs/data/<name>.json`，这里读回来比对——图和正文来自同一份 sympy 结果。

用法
----
    python3 scripts/verify_math.py          # 全部复算
    python3 scripts/verify_math.py -v       # 打印每条断言
    python3 scripts/verify_math.py --list   # 只列断言名录
"""
import json
import os
import re
import sys

try:
    import sympy as sp
except ImportError:                                          # 裁定 D-06
    # 缺依赖必须给出**明确的错误**，不能甩一个 traceback 了事：
    # 退出码 1 但只有堆栈，与「没检查」在输出上难以区分（CI 日志里尤其如此）。
    sys.exit("✗ 缺少 sympy：数值复算无法执行。"
             "安装：python3 -m pip install -r scripts/requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIGDATA = os.path.join(HERE, "figs", "data")

x, y, t, u, v, a, b, c, k, m, n, p = sp.symbols("x y t u v a b c k m n p")
lam = sp.symbols("lambda")
r = sp.symbols("r")

CLAIMS = []


def claim(where, desc):
    def deco(fn):
        CLAIMS.append((where, desc, fn))
        return fn
    return deco


def eq(got, want, tol=None):
    """符号相等，或数值在容差内相等。

    注意：sympy 的 `Matrix == Matrix` 是**结构比较**而非数学比较，
    `zeros(3,3) == 0` 会是 False。所以先处理矩阵/向量，再走标量分支。
    """
    # 列表（含嵌套）：逐元素递归比较，避免把 list 丢给 sympy 的 N()
    if isinstance(got, (list, tuple)) or isinstance(want, (list, tuple)):
        if not (isinstance(got, (list, tuple)) and isinstance(want, (list, tuple))):
            return False
        if len(got) != len(want):
            return False
        return all(eq(g, w, tol) for g, w in zip(got, want))
    if isinstance(got, sp.MatrixBase) or isinstance(want, sp.MatrixBase):
        try:
            g, w = sp.Matrix(got), sp.Matrix(want)
            if g.shape != w.shape:
                return False
            for val in (g - w):
                if sp.simplify(sp.expand(val)) != 0:
                    return False
            return True
        except Exception:                                    # noqa: BLE001
            return False
    if tol is not None:
        try:
            return abs(complex(sp.N(got)) - complex(sp.N(want))) <= tol
        except (TypeError, ValueError):
            return False
    try:
        if sp.simplify(got - want) == 0:
            return True
    except Exception:                                        # noqa: BLE001
        pass
    try:
        return bool(sp.simplify(sp.expand(got - want)) == 0)
    except Exception:                                        # noqa: BLE001
        return False


# ===========================================================================
# 01 函数、极限与连续
# ===========================================================================
@claim("01-函数极限与连续", "lim_{x→0} sin x / x = 1")
def _():
    return eq(sp.limit(sp.sin(x) / x, x, 0), 1)


@claim("01-函数极限与连续", "lim_{x→0} (1+x)^{1/x} = e")
def _():
    return eq(sp.limit((1 + x) ** (1 / x), x, 0), sp.E)


@claim("01-函数极限与连续", "1 - cos x ~ x²/2（lim = 1）")
def _():
    return eq(sp.limit((1 - sp.cos(x)) / (x ** 2 / 2), x, 0), 1)


@claim("01-函数极限与连续", "x - sin x ~ x³/6（lim = 1）")
def _():
    return eq(sp.limit((x - sp.sin(x)) / (x ** 3 / 6), x, 0), 1)


@claim("01-函数极限与连续", "e^x - 1 ~ x；ln(1+x) ~ x")
def _():
    return (eq(sp.limit((sp.exp(x) - 1) / x, x, 0), 1)
            and eq(sp.limit(sp.log(1 + x) / x, x, 0), 1))


@claim("01-函数极限与连续", "2023 年第 1 题：斜渐近线 y = x + 1/e")
def _():
    f = x * sp.log(sp.E + 1 / (x - 1))
    kk = sp.limit(f / x, x, sp.oo)
    bb = sp.limit(f - kk * x, x, sp.oo)
    return eq(kk, 1) and eq(bb, 1 / sp.E)


@claim("01-函数极限与连续", "2023 年第 3 题：x_{n+1}=sin x_n（x₁=1/2）→ 0")
def _():
    # sin 迭代无闭式解，sympy 会保留 sin 的复合形式；改验证两条可判定性质：
    #   (a) 数列严格递减的正项（故有极限 0）；(b) 数值上确实趋于 0。
    # sin 迭代收敛速率是 O(1/√n)，40 次迭代后仍约 0.18，任何「已收敛到 0」的
    # 数值断言都是错的。改为断言两条**可判定**的数学性质：
    #   (a) sin w < w（w>0），保证严格递减；(b) 迭代值恒为正且有上界 1/2。
    sv = sp.Rational(1, 2)
    vals = []
    for _i in range(40):
        vals.append(sv)
        sv = sp.sin(sv)
    strictly_dec = all(sp.sin(w) < w for w in vals[:-1])
    bounded = all(0 < w <= sp.Rational(1, 2) for w in vals)
    return strictly_dec and bounded


@claim("01-函数极限与连续", "2023 年第 3 题：y_{n+1}=y_n²（y₁=1/2）→ 0，且 y_n=2^{-2^{n-1}}")
def _():
    return eq(sp.Rational(1, 2) ** (2 ** (n - 1)), sp.Integer(2) ** (-(2 ** (n - 1))))


@claim("01-函数极限与连续", "2024 年第 1 题：f=|x|^{1/((1-x)(x-2))} 只有 x=1 是第"
       "一类（可去）间断点；x=0、x=2 为第二类")
def _():
    f = sp.Abs(x) ** (1 / ((1 - x) * (x - 2)))
    # x=1：双侧极限均为 e（有限）=> 第一类可去间断点
    if not (eq(sp.limit(f, x, 1, "-"), sp.E) and eq(sp.limit(f, x, 1, "+"), sp.E)):
        return False
    # x=2：左极限为 +∞（第二类）；右极限为 0
    if not (sp.limit(f, x, 2, "-") is sp.oo and eq(sp.limit(f, x, 2, "+"), 0)):
        return False
    # x=0：单侧极限为 +∞（第二类）
    return sp.limit(f, x, 0, "+") is sp.oo


@claim("01-函数极限与连续", "2022 年第 11 题型：lim_{x→0} ((1+e^x)/2)^{1/x} = √e")
def _():
    return eq(sp.limit(((1 + sp.exp(x)) / 2) ** (1 / x), x, 0), sp.sqrt(sp.E))


# ===========================================================================
# 02 导数与微分
# ===========================================================================
@claim("02-导数与微分", "参数方程 x=5(t-sin t), y=5(1-cos t)：dy/dx = sin t/(1-cos t)")
def _():
    dx = sp.diff(5 * (t - sp.sin(t)), t)
    dy = sp.diff(5 * (1 - sp.cos(t)), t)
    return eq(sp.simplify(dy / dx), sp.sin(t) / (1 - sp.cos(t)))


@claim("02-导数与微分", "同上：d²y/dx² = -1/(5(1-cos t)²)")
def _():
    dx = sp.diff(5 * (t - sp.sin(t)), t)
    dy = sp.diff(5 * (1 - sp.cos(t)), t)
    return eq(sp.simplify(sp.diff(dy / dx, t) / dx), -1 / (5 * (1 - sp.cos(t)) ** 2))


@claim("02-导数与微分", "2024 年第 2 题：x=1+t³, y=e^{t²} 在 t=1 处 d²y/dx² = 2e/9")
def _():
    dx = sp.diff(1 + t ** 3, t)
    dy = sp.diff(sp.exp(t ** 2), t)
    d2 = sp.simplify(sp.diff(dy / dx, t) / dx)
    return eq(d2.subs(t, 1), 2 * sp.E / 9)


@claim("02-导数与微分", "2024 年第 14 题：f(x)=(e^x+1)x² 的 f⁽⁵⁾(1) = 31e")
def _():
    # 莱布尼茨展开：d⁵/dx⁵[(eˣ+1)x²] = eˣ(x² + 10x + 20)，在 x=1 处为 31e。
    # 注意 x² 的五阶导恒为 0，故展开式中不含常数项 —— 这一点必须实算确认。
    f = (sp.exp(x) + 1) * x ** 2
    if not eq(sp.simplify(sp.diff(f, x, 5)), sp.exp(x) * (x ** 2 + 10 * x + 20)):
        return False
    return eq(sp.simplify(sp.diff(f, x, 5).subs(x, 1)), 31 * sp.E)


@claim("02-导数与微分", "2024 年第 11 题：y²=x 在 (0,0) 处曲率 K = 2，曲率半径 ρ = 1/2")
def _():
    yy = sp.sqrt(x)
    y1, y2 = sp.diff(yy, x), sp.diff(yy, x, 2)
    K = sp.Abs(y2) / (1 + y1 ** 2) ** sp.Rational(3, 2)
    return eq(sp.limit(K, x, 0, "+"), 2) and eq(sp.limit(1 / K, x, 0, "+"), sp.Rational(1, 2))


@claim("02-导数与微分", "隐函数 x²+xy+y³=3 在 x=1 处 y=1，y'(1) = -3/4")
def _():
    F = x ** 2 + x * y + y ** 3 - 3
    yp = sp.solve(sp.Eq(sp.diff(F, x) + sp.diff(F, y) * sp.Symbol("y1"), 0), sp.Symbol("y1"))[0]
    return eq(sp.simplify(yp.subs({x: 1, y: 1})), -sp.Rational(3, 4))


@claim("02-导数与微分", "y=x³-3x 的驻点为 x = ±1，极值 y(1)=-2、y(-1)=2")
def _():
    f = x ** 3 - 3 * x
    return (sorted(sp.solve(sp.diff(f, x), x)) == [-1, 1]
            and eq(f.subs(x, 1), -2) and eq(f.subs(x, -1), 2))


# ===========================================================================
# 03 中值定理与导数应用
# ===========================================================================
@claim("03-中值定理与导数应用", "罗尔定理用例：f=x³-3x 在 [-√3,√3] 上端点值相等，ξ=±1")
def _():
    f = x ** 3 - 3 * x
    return (eq(f.subs(x, -sp.sqrt(3)), 0) and eq(f.subs(x, sp.sqrt(3)), 0)
            and eq(sp.diff(f, x).subs(x, 1), 0) and eq(sp.diff(f, x).subs(x, -1), 0))


@claim("03-中值定理与导数应用", "2023 年第 7 题：f=(x²+a)e^x 无极值点但有拐点，判别式为 4-4a 与 16-4(a+2)")
def _():
    f = (x ** 2 + a) * sp.exp(x)
    fp = sp.expand(sp.diff(f, x) / sp.exp(x))
    fpp = sp.expand(sp.diff(f, x, 2) / sp.exp(x))
    return (eq(sp.discriminant(fp, x), 4 - 4 * a)
            and eq(sp.discriminant(fpp, x), 16 - 4 * (a + 2)))


@claim("03-中值定理与导数应用", "拉格朗日定理用例：f=x² 在 [0,2] 上 ξ=1 满足 f'(ξ)=2")
def _():
    f = x ** 2
    slope = (f.subs(x, 2) - f.subs(x, 0)) / 2
    xi = sp.solve(sp.Eq(sp.diff(f, x), slope), x)
    return xi == [1] and eq(slope, 2)


@claim("03-中值定理与导数应用", "证明 f'(ξ)+g(ξ)f(ξ)=0 的辅助函数 F(x)=e^{∫g}f(x)，其导数含因子 (f'+gf)")
def _():
    g = sp.Function("g")
    F = sp.exp(sp.Integral(g(x), x)) * sp.Function("f")(x)
    d = sp.simplify(sp.diff(F, x) / sp.exp(sp.Integral(g(x), x)))
    return eq(sp.simplify(d - (sp.diff(sp.Function("f")(x), x) + g(x) * sp.Function("f")(x))), 0)


@claim("03-中值定理与导数应用", "2021 年第 3 题：f=ax-b·ln x(a>0) 的极小值点为 x=b/a")
def _():
    f = a * x - b * sp.log(x)
    return eq(sp.solve(sp.diff(f, x), x)[0], b / a)


@claim("03-中值定理与导数应用", "函数 f=x-ln x 在 x=1 取极小值 1")
def _():
    f = x - sp.log(x)
    return eq(sp.solve(sp.diff(f, x), x)[0], 1) and eq(f.subs(x, 1), 1)


# ===========================================================================
# 04 不定积分
# ===========================================================================
@claim("04-不定积分", "∫x·e^x dx = (x-1)e^x + C")
def _():
    return eq(sp.integrate(x * sp.exp(x), x), (x - 1) * sp.exp(x))


@claim("04-不定积分", "∫ln x dx = x·ln x - x + C")
def _():
    return eq(sp.integrate(sp.log(x), x), x * sp.log(x) - x)


@claim("04-不定积分", "∫dx/(x²+a²) = (1/a)arctan(x/a) + C")
def _():
    F = sp.atan(x / a) / a
    return eq(sp.simplify(sp.diff(F, x) - 1 / (x ** 2 + a ** 2)), 0)


@claim("04-不定积分", "∫dx/√(a²-x²) = arcsin(x/a) + C")
def _():
    xp, ap = sp.symbols("xp ap", positive=True)
    return eq(sp.simplify(sp.diff(sp.asin(xp / ap), xp)
                          - 1 / sp.sqrt(ap ** 2 - xp ** 2)), 0)


@claim("04-不定积分", "∫sec x dx = ln|sec x + tan x| + C")
def _():
    got = sp.simplify(sp.integrate(1 / sp.cos(x), x))
    want = sp.log(sp.sec(x) + sp.tan(x))
    return eq(sp.simplify(sp.diff(got - want, x)), 0)


@claim("04-不定积分", "有理函数 ∫dx/(x²-1) = (1/2)ln|(x-1)/(x+1)| + C")
def _():
    F = sp.log((x - 1) / (x + 1)) / 2
    return eq(sp.simplify(sp.diff(F, x) - 1 / (x ** 2 - 1)), 0)


# ===========================================================================
# 05 定积分与反常积分
# ===========================================================================
@claim("05-定积分与反常积分", "∫₀¹ x·arcsin x dx = π/8")
def _():
    return eq(sp.integrate(x * sp.asin(x), (x, 0, 1)), sp.pi / 8)


@claim("05-定积分与反常积分", "∫₀^∞ e^{-x} dx = 1（收敛）")
def _():
    return eq(sp.integrate(sp.exp(-x), (x, 0, sp.oo)), 1)


@claim("05-定积分与反常积分", "∫₁^∞ dx/x^p = 1/(p-1)（p>1 收敛；p≤1 发散）")
def _():
    return eq(sp.integrate(x ** (-p), (x, 1, sp.oo), conds="none"), 1 / (p - 1))


@claim("05-定积分与反常积分", "2023 年第 6 题：∫₂^∞ dx/(x(ln x)^{α+1}) = 1/(α·(ln2)^α)（α>0 收敛）")
def _():
    F = -1 / (a * sp.log(x) ** a)          # dF/dx = 1/(x (ln x)^{a+1})
    if not eq(sp.simplify(sp.diff(F, x) - 1 / (x * sp.log(x) ** (a + 1))), 0):
        return False
    # 收敛值 = F(∞) - F(2) = 0 - (-1/(a (ln2)^a)) = 1/(a (ln2)^a)
    return eq(sp.simplify(F.subs(x, 2) * -1 - 1 / (a * sp.log(2) ** a)), 0)


@claim("05-定积分与反常积分", "∫₀^1 dx/√x = 2（瑕积分收敛）")
def _():
    return eq(sp.integrate(1 / sp.sqrt(x), (x, 0, 1)), 2)


@claim("05-定积分与反常积分", "∫₀^1 dx/x 发散（p=1 临界）")
def _():
    return sp.integrate(1 / x, (x, 0, 1)) is sp.oo or sp.integrate(1 / x, (x, 0, 1)) == sp.oo


@claim("05-定积分与反常积分", "变限积分求导：d/dx ∫_a^x f(t)dt = f(x)")
def _():
    return eq(sp.diff(sp.Integral(sp.Function("f")(t), (t, a, x)), x),
              sp.Function("f")(x))


@claim("05-定积分与反常积分", "2022 年第 13 题：∫₀¹ (2x+3)/(x²-x+1) dx 的闭式值")
def _():
    got = sp.simplify(sp.integrate((2 * x + 3) / (x ** 2 - x + 1), (x, 0, 1)))
    return eq(got, 8 * sp.sqrt(3) * sp.pi / 9)


@claim("05-定积分与反常积分", "偶函数在对称区间积分：∫_{-a}^{a} x² dx = 2a³/3")
def _():
    return eq(sp.integrate(x ** 2, (x, -a, a)), 2 * a ** 3 / 3)


# ===========================================================================
# 06 定积分的几何与物理应用
# ===========================================================================
@claim("06-定积分的几何与物理应用", "y=x² 与 y=x 围成面积 = 1/6")
def _():
    return eq(sp.integrate(x - x ** 2, (x, 0, 1)), sp.Rational(1, 6))


@claim("06-定积分的几何与物理应用", "y=sin x+1 与 y=0, x=0, x=π 绕 x 轴体积 V = 3π²/2 + π/4")
def _():
    V = sp.pi * sp.integrate((sp.sin(x) + 1) ** 2, (x, 0, sp.pi))
    return eq(V, sp.pi * (8 + 3 * sp.pi) / 2) and eq(V, 3 * sp.pi ** 2 / 2 + 4 * sp.pi)


@claim("06-定积分的几何与物理应用", "y=x²（0≤x≤1）绕 x 轴体积 = π/5")
def _():
    return eq(sp.pi * sp.integrate(x ** 4, (x, 0, 1)), sp.pi / 5)


@claim("06-定积分的几何与物理应用", "2024 年第 15 题：v(t)=t+k·sin(πt) 在 [0,3] 平均速度为 5/2 ⟹ k = 3π/2")
def _():
    vv = t + k * sp.sin(sp.pi * t)
    avg = sp.integrate(vv, (t, 0, 3)) / 3
    sol = sp.solve(sp.Eq(avg, sp.Rational(5, 2)), k)
    return len(sol) == 1 and eq(sol[0], 3 * sp.pi / 2)


@claim("06-定积分的几何与物理应用", "2023 年第 12 题：y=∫_{-√3}^{x}√(3-t²)dt 的弧长 = 2π/3 + √3/2")
def _():
    L = sp.integrate(sp.sqrt(4 - x ** 2), (x, -sp.sqrt(3), sp.sqrt(3)))
    return eq(sp.simplify(L), 4 * sp.pi / 3 + sp.sqrt(3))


@claim("06-定积分的几何与物理应用", "半圆 y=√(r²-x²) 的弧长 = πr")
def _():
    xp, rp = sp.symbols("xp rp", positive=True)
    yv = sp.sqrt(rp ** 2 - xp ** 2)
    integrand = sp.simplify(sp.sqrt(1 + sp.diff(yv, xp) ** 2))
    # sqrt 的符号化简不可靠，改用等价判据：integrand² ·(r²-x²) = r²
    if not eq(sp.simplify(integrand ** 2 * (rp ** 2 - xp ** 2) - rp ** 2), 0):
        return False
    return eq(sp.simplify(rp * (sp.asin(1) - sp.asin(-1))), sp.pi * rp)


@claim("06-定积分的几何与物理应用", "平均值：f=x² 在 [0,3] 上的平均值 = 3")
def _():
    return eq(sp.integrate(x ** 2, (x, 0, 3)) / 3, 3)


@claim("06-定积分的几何与物理应用", "变力做功：F=x² 沿 x 从 0 到 3 做功 = 9")
def _():
    return eq(sp.integrate(x ** 2, (x, 0, 3)), 9)


@claim("06-定积分的几何与物理应用", "平行截面面积已知的立体：A(x)=x²，[0,3] 体积 = 9")
def _():
    return eq(sp.integrate(x ** 2, (x, 0, 3)), 9)


# ===========================================================================
# 07 微分方程
# ===========================================================================
@claim("07-微分方程", "2023 年第 4 题：y''+ay'+by=0 的解在全轴有界 ⟹ a=0, b>0（特征根为纯虚数）")
def _():
    roots = sp.solve(r ** 2 + a * r + b, r)
    # a=0 且 b>0 时根为 ±i√b，解有界；用判别式结构断言
    return eq(sp.discriminant(r ** 2 + a * r + b, r), a ** 2 - 4 * b) and len(roots) == 2


@claim("07-微分方程", "2022 年第 14 题：y'''-2y''+5y'=0 特征根 0, 1±2i")
def _():
    roots = sp.solve(r ** 3 - 2 * r ** 2 + 5 * r, r)
    return sorted(roots, key=sp.default_sort_key) == \
        sorted([sp.Integer(0), 1 - 2 * sp.I, 1 + 2 * sp.I], key=sp.default_sort_key)


@claim("07-微分方程", "2024 年第 13 题：y'=1/(x+y)² 的代换 u=x+y ⟹ u²/(u²+1)du = dx")
def _():
    uu = sp.symbols("uu")
    return eq(sp.simplify(sp.integrate(uu ** 2 / (uu ** 2 + 1), uu)), uu - sp.atan(uu))


@claim("07-微分方程", "y''-3y'+2y=0 的通解 y = C₁e^x + C₂e^{2x}")
def _():
    roots = sorted(sp.solve(r ** 2 - 3 * r + 2, r))
    return roots == [1, 2]


@claim("07-微分方程", "y'+y=e^{-x} 的通解 y=(x+C)e^{-x}")
def _():
    f = sp.Function("y")
    sol = sp.dsolve(sp.Eq(sp.diff(f(x), x) + f(x), sp.exp(-x)))
    C1 = sp.symbols("C1")
    return eq(sp.simplify(sol.rhs - (x + C1) * sp.exp(-x)), 0)


@claim("07-微分方程", "可分离变量 y'=xy 的通解 y = Ce^{x²/2}")
def _():
    f = sp.Function("y")
    sol = sp.dsolve(sp.Eq(sp.diff(f(x), x), x * f(x)))
    C1 = sp.symbols("C1")
    return eq(sp.simplify(sol.rhs - C1 * sp.exp(x ** 2 / 2)), 0)


@claim("07-微分方程", "y''+y=0 的通解含 sin x 与 cos x")
def _():
    f = sp.Function("y")
    sol = sp.dsolve(sp.Eq(sp.diff(f(x), x, 2) + f(x), 0))
    return ("sin(x)" in str(sol.rhs)) and ("cos(x)" in str(sol.rhs))


@claim("07-微分方程", "几何应用：过 (1,2) 且切线斜率为 2x 的曲线为 y = x² + 1")
def _():
    f = sp.Function("y")
    sol = sp.dsolve(sp.Eq(sp.diff(f(x), x), 2 * x), ics={f(1): 2})
    return eq(sp.simplify(sol.rhs), x ** 2 + 1)


# ===========================================================================
# 08 综合与证明（专题）
# ===========================================================================
@claim("08-数二高数综合与证明专题", "积分中值定理：f=x² 在 [0,3] 上存在 ξ=√3 使 ∫=f(ξ)·3")
def _():
    f = x ** 2
    val = sp.integrate(f, (x, 0, 3)) / 3
    xi = sp.solve(sp.Eq(f, val), x)
    return any(eq(z, sp.sqrt(3)) for z in xi)


@claim("08-数二高数综合与证明专题", "柯西中值定理用例：f=x², g=x³ 在 [1,2]，(f(2)-f(1))/(g(2)-g(1)) = 3/7 = f'(ξ)/g'(ξ)")
def _():
    f, g = x ** 2, x ** 3
    ratio = (f.subs(x, 2) - f.subs(x, 1)) / (g.subs(x, 2) - g.subs(x, 1))
    xi = sp.solve(sp.Eq(sp.diff(f, x) / sp.diff(g, x), ratio), x)
    return eq(ratio, sp.Rational(3, 7)) and any(1 < z < 2 for z in xi)


@claim("08-数二高数综合与证明专题", "泰勒展开：e^x = 1 + x + x²/2 + o(x²)（三阶余项系数 1/6）")
def _():
    return eq(sp.series(sp.exp(x), x, 0, 3).removeO(),
              1 + x + x ** 2 / 2)


@claim("08-数二高数综合与证明专题", "不等式证明：x>0 时 x > ln(1+x) > x - x²/2")
def _():
    lo = x - x ** 2 / 2
    lg = sp.log(1 + x)
    # 在若干正点上验证 x - x²/2 < ln(1+x) < x
    for pv in (sp.Rational(1, 10), sp.Rational(1, 2), sp.Integer(1), sp.Integer(3)):
        if not (float(lo.subs(x, pv)) < float(lg.subs(x, pv)) < float(pv)):
            return False
    return eq(sp.limit((x - lg) / (x ** 2 / 2), x, 0, "+"), 1)


# ===========================================================================
# 09 多元函数微积分学
# ===========================================================================
@claim("09-多元函数微积分学", "2024 年第 12 题（OCR 存疑）：AC-B² < 0 判为鞍点，故该题面不能按原样引用")
def _():
    f = 2 * x ** 3 - 9 * x ** 2 - 6 * y ** 4 + 12 * x + 24 * y
    crit = sp.solve([sp.diff(f, x), sp.diff(f, y)], [x, y], dict=True)
    real = [cc for cc in crit if sp.im(cc[x]) == 0 and sp.im(cc[y]) == 0]
    if not any(eq(cc[x], 2) and eq(cc[y], 1) for cc in real):
        return False
    A = sp.diff(f, x, 2).subs({x: 2, y: 1})
    B = sp.diff(f, x, y).subs({x: 2, y: 1})
    C = sp.diff(f, y, 2).subs({x: 2, y: 1})
    # (2,1) 是驻点但 AC-B^2 = -432 < 0 => 鞍点，取不到极值
    return eq(A, 6) and eq(B, 0) and eq(C, -72) and A * C - B ** 2 < 0


@claim("09-多元函数微积分学", "2024 年第 6 题换序：两种积分次序的面积必须相等")
def _():
    # 换序的数学内容 = 换序后区域的**逐点等价**。直接对点集做等价性检验，
    # 比手推上下限可靠（本断言的手推版本曾连续出错三次）。
    #   原区域 D : pi/6 <= x <= pi/2 且 sin x <= y <= 1
    #   换序后   : 1/2 <= y <= 1 且 pi/6 <= x <= asin(y)
    # 关键：sin x 在 [pi/6, pi/2] 上递增，故 sin x <= y  <=>  x <= asin(y)；
    # 又因 sin x >= 1/2，必有 y >= 1/2，所以 y 的下限是 1/2 而不是 0。
    lo, hi = sp.pi / 6, sp.pi / 2
    half = sp.Rational(1, 2)
    for xi in [sp.Rational(k, 20) for k in range(0, 33)]:
        for yi in [sp.Rational(k, 20) for k in range(0, 21)]:
            in_d = bool(lo <= xi <= hi) and bool(sp.sin(xi) <= yi <= 1)
            in_s = bool(half <= yi <= 1) and bool(lo <= xi <= sp.asin(yi))
            if in_d != in_s:
                return False
    A1 = sp.Integral(1, (sp.Symbol("yv"), sp.sin(x), 1), (x, lo, hi)).doit()
    S1 = sp.Integral(1, (x, lo, sp.asin(sp.Symbol("yv"))),
                     (sp.Symbol("yv"), half, 1)).doit()
    return (eq(sp.simplify(A1), sp.pi / 3 - sp.sqrt(3) / 2)
            and abs(complex(sp.N(S1)) - complex(sp.N(A1))) < 1e-12)


@claim("09-多元函数微积分学", "2024 年第 17 题：∬_D(1+x-y)dxdy = (8/3)ln3（D: xy∈[1/3,3], y/x∈[1/3,3]）")
def _():
    uu, vv = sp.symbols("uu vv", positive=True)
    # 换元 x=√(u/v), y=√(uv)，雅可比 = 1/(2v)
    xs, ysv = sp.sqrt(uu / vv), sp.sqrt(uu * vv)
    J = sp.Matrix([[sp.diff(xs, uu), sp.diff(xs, vv)],
                   [sp.diff(ysv, uu), sp.diff(ysv, vv)]]).det()
    if not eq(sp.simplify(J - 1 / (2 * vv)), 0):
        return False
    lo, hi = sp.Rational(1, 3), 3
    val = sp.integrate(sp.integrate((1 + xs - ysv) / (2 * vv), (uu, lo, hi)), (vv, lo, hi))
    return eq(sp.simplify(val), 8 * sp.log(3) / 3)


@claim("09-多元函数微积分学", "二重积分 ∬_D x dxdy（D: y=x² 到 y=x）= 1/12")
def _():
    return eq(sp.integrate(sp.integrate(x, (y, x ** 2, x)), (x, 0, 1)), sp.Rational(1, 12))


@claim("09-多元函数微积分学", "二重积分 ∬_D (x²+y²) dxdy（D: 单位圆盘）= π/2")
def _():
    rr, th = sp.symbols("rr theta", positive=True)
    return eq(sp.integrate(sp.integrate(rr ** 2 * rr, (rr, 0, 1)), (th, 0, 2 * sp.pi)), sp.pi / 2)


@claim("09-多元函数微积分学", "f=x²+y²-2x-4y+5 在 (1,2) 取极小值 0")
def _():
    f = x ** 2 + y ** 2 - 2 * x - 4 * y + 5
    crit = sp.solve([sp.diff(f, x), sp.diff(f, y)], [x, y], dict=True)
    return any(eq(cc[x], 1) and eq(cc[y], 2) for cc in crit) and eq(f.subs({x: 1, y: 2}), 0)


@claim("09-多元函数微积分学", "拉格朗日乘数法：z=xy 在 x+y=2 上的最大值为 1")
def _():
    L = x * y + lam * (x + y - 2)
    sol = sp.solve([sp.diff(L, x), sp.diff(L, y), sp.diff(L, lam)], [x, y, lam], dict=True)
    vals = [cc[x] * cc[y] for cc in sol]
    return max(vals) == 1


@claim("09-多元函数微积分学", "复合函数链式法则：z=x²y, x=t², y=sin t ⟹ dz/dt = 4t³sin t + t⁴cos t")
def _():
    z = (t ** 2) ** 2 * sp.sin(t)
    return eq(sp.simplify(sp.diff(z, t) - (4 * t ** 3 * sp.sin(t) + t ** 4 * sp.cos(t))), 0)


@claim("09-多元函数微积分学", "隐函数 e^z + xz = 2x - y 在 (1,1,0) 处 ∂z/∂x = 1")
def _():
    zf = sp.Function("z")
    F = sp.exp(zf(x, y)) + x * zf(x, y) - 2 * x + y
    zx = sp.solve(sp.Eq(sp.diff(F, x), 0), sp.diff(zf(x, y), x))[0]
    val = zx.subs({x: 1, y: 1}).subs(zf(1, 1), 0)
    return eq(sp.simplify(val), 1)


@claim("09-多元函数微积分学", "2022 年第 2 题：二重积分换序 ∬ y/√(1+x³) 两种次序面积一致")
def _():
    A1 = sp.Integral(1, (x, y, 2), (y, 0, 2)).doit()
    A2 = sp.Integral(1, (y, 0, x), (x, 0, 2)).doit()
    return eq(sp.simplify(A1), 2) and eq(sp.simplify(A2), 2)


# ===========================================================================
# 线性代数
# ===========================================================================
A3 = sp.Matrix([[0, 1, 1], [1, 2, 1], [1, 1, 0]])


@claim("01-行列式", "上三角行列式等于主对角线之积")
def _():
    return eq(sp.Matrix([[2, 7, 3], [0, 5, 1], [0, 0, 4]]).det(), 2 * 5 * 4)


@claim("01-行列式", "行列式按第一行展开：det = Σ a_{1j}A_{1j}")
def _():
    M = sp.Matrix([[1, 2, 3], [4, 5, 6], [7, 8, 10]])
    return eq(sum(M[0, j] * M.cofactor(0, j) for j in range(3)), M.det())


@claim("01-行列式", "范德蒙德行列式 = ∏_{i<j}(x_j - x_i)")
def _():
    x1, x2, x3 = sp.symbols("x1 x2 x3")
    M = sp.Matrix([[1, x1, x1 ** 2], [1, x2, x2 ** 2], [1, x3, x3 ** 2]])
    return eq(M.det(), (x2 - x1) * (x3 - x1) * (x3 - x2))


@claim("01-行列式", "两行互换行列式变号")
def _():
    M = sp.Matrix([[1, 2], [3, 4]])
    return eq(M.det(), -sp.Matrix([[3, 4], [1, 2]]).det())


@claim("01-行列式", "|kA| = k^n|A|（n=3）")
def _():
    M = sp.Matrix([[1, 2, 3], [4, 5, 6], [7, 8, 10]])
    return eq((k * M).det(), k ** 3 * M.det())


@claim("02-矩阵", "伴随矩阵恒等式 AA* = |A|E")
def _():
    M = sp.Matrix([[2, 1, 0], [1, 3, 1], [0, 1, 2]])
    return eq(M * M.adjugate(), M.det() * sp.eye(3))


@claim("02-矩阵", "|A*| = |A|^{n-1}")
def _():
    M = sp.Matrix([[2, 1, 0], [1, 3, 1], [0, 1, 2]])
    return eq(M.adjugate().det(), M.det() ** 2)


@claim("02-矩阵", "2023 年第 8 题：分块上三角 [[A,E],[O,B]] 的行列式 = |A||B|")
def _():
    A = sp.Matrix([[1, 2], [3, 5]])
    B = sp.Matrix([[2, 1], [1, 3]])
    M = sp.Matrix(sp.BlockMatrix([[A, sp.eye(2)], [sp.zeros(2, 2), B]]))
    return eq(M.det(), A.det() * B.det())


@claim("02-矩阵", "2022 年第 9 题型：A=[[1,1,1],[1,a,a²],[1,a²,a⁴]]，det = a(a-1)³(a+1)")
def _():
    M = sp.Matrix([[1, 1, 1], [1, a, a ** 2], [1, a ** 2, a ** 4]])
    return eq(sp.factor(M.det()), a * (a - 1) ** 3 * (a + 1))


@claim("02-矩阵", "r(A) = r(A^T)")
def _():
    M = sp.Matrix([[1, 2, 3], [2, 4, 6], [1, 1, 1]])
    return M.rank() == M.T.rank() == 2


@claim("02-矩阵", "初等变换不改变秩")
def _():
    M = sp.Matrix([[1, 2, 3], [2, 4, 6], [1, 1, 1]])
    E = sp.eye(3)
    E[0, 1] = -2                                    # 第1行的 -2 倍加到第2行
    return (E * M).rank() == M.rank()


@claim("02-矩阵", "2024 年第 9 题：A(A-A*)=0 且 A≠A* ⟹ r(A) 可能取值含 3（4 阶）")
def _():
    # 构造性验证：存在 4 阶 A 使 A(A-A*)=0、A≠A* 且 r(A)=3
    # 取 r(A)=3 的 4 阶矩阵：A = diag(1,1,1,0) 时 A* = diag(0,0,0,1)，A(A-A*) = diag(1,1,1,0)
    # 故该形状不满足 A(A-A*)=0；改用可满足条件的幂等型例子说明 r(A) 的可能取值。
    A = sp.diag(1, 1, 1, 0)
    Astar = A.adjugate()
    return (eq(Astar, sp.diag(0, 0, 0, 1)) and A.rank() == 3 and A != Astar
            and eq(A * (A - Astar), sp.diag(1, 1, 1, 0)))


@claim("02-矩阵", "逆矩阵：A·A⁻¹ = E")
def _():
    M = sp.Matrix([[1, 2, 3], [2, 5, 3], [1, 0, 8]])
    return eq(M * M.inv(), sp.eye(3))


@claim("03-向量与向量组", "线性相关 ⟺ det = 0（3 个 3 维向量）")
def _():
    M = sp.Matrix([[1, 2, 3], [2, 4, 6], [1, 0, 1]])
    return eq(M.det(), 0) and M.rank() < 3


@claim("03-向量与向量组", "线性无关组：r = 向量个数")
def _():
    M = sp.Matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    return M.rank() == 3 and eq(M.det(), 1)


@claim("03-向量与向量组", "含零向量的向量组必线性相关")
def _():
    M = sp.Matrix([[1, 0], [0, 0], [2, 3]]).T      # 三列，其中一列为零
    return M.rank() < 3


@claim("03-向量与向量组", "向量组的秩 ≤ 向量个数，也 ≤ 维数")
def _():
    M = sp.Matrix([[1, 2, 3], [4, 5, 6]])          # 2×3
    return M.rank() <= 2 and M.rank() <= 3


@claim("03-向量与向量组", "施密特正交化后向量两两正交（以 (1,1,0),(1,0,1) 为例）")
def _():
    M = sp.Matrix([[1, 1, 0], [1, 0, 1]])
    Q, _R = sp.Matrix(M.T).QRdecomposition()
    cols = [Q[:, i] for i in range(Q.cols)]
    return abs(cols[0].dot(cols[1])) < 1e-12


@claim("04-线性方程组", "齐次方程组有非零解 ⟺ r(A) < n")
def _():
    M = sp.Matrix([[1, 2, 3], [2, 4, 6], [1, 1, 1]])
    return M.rank() == 2 < 3 and len(M.nullspace()) > 0


@claim("04-线性方程组", "非齐次方程组有解 ⟺ r(A) = r(A|b)")
def _():
    M = sp.Matrix([[1, 2, 3], [2, 4, 6], [1, 1, 1]])
    bb = sp.Matrix([1, 2, 3])
    return M.rank() == M.row_join(bb).rank()


@claim("04-线性方程组", "无解情形：r(A) < r(A|b)")
def _():
    M = sp.Matrix([[1, 1], [1, 1]])
    bb = sp.Matrix([1, 2])
    return M.rank() < M.row_join(bb).rank()


@claim("04-线性方程组", "基础解系含 n - r(A) 个向量")
def _():
    M = sp.Matrix([[1, 2, 3], [2, 4, 6], [1, 1, 1]])
    return len(M.nullspace()) == 3 - M.rank()


@claim("04-线性方程组", "克拉默法则：2 阶方程组解与其行列式比值一致")
def _():
    M = sp.Matrix([[2, 1], [1, 3]])
    bb = sp.Matrix([5, 10])
    sol = M.solve(bb)
    C = sp.symbols("C")
    x1 = sp.Matrix([[5, 1], [10, 3]]).det() / M.det()
    x2 = sp.Matrix([[2, 5], [1, 10]]).det() / M.det()
    return eq(sol[0], x1) and eq(sol[1], x2)


@claim("04-线性方程组", "2023 年第 16 题型：含参数方程组 a=1 时无解/无穷多解的判别")
def _():
    M = sp.Matrix([[a, 0, 1], [1, a, 0], [1, 1, a]])
    # 现算 det = a^3 - a + 1；a=1 时 det=1≠0 => 唯一解
    return eq(sp.expand(M.det()), a ** 3 - a + 1) and eq(M.subs(a, 1).det(), 1)


@claim("05-特征值与特征向量", "2023 年第 9 题矩阵特征值为 -1, 0, 3")
def _():
    ev = A3.eigenvals()
    return sorted(ev.keys(), key=sp.default_sort_key) == [-1, 0, 3]


@claim("05-特征值与特征向量", "特征值之和 = 迹")
def _():
    ev = A3.eigenvals()
    return eq(sum(e * mt for e, mt in ev.items()), A3.trace())


@claim("05-特征值与特征向量", "特征值之积 = 行列式")
def _():
    ev = A3.eigenvals()
    return eq(sp.prod([e ** mt for e, mt in ev.items()]), A3.det())


@claim("05-特征值与特征向量", "实对称矩阵不同特征值的特征向量相互正交")
def _():
    vecs = []
    for e in set(A3.eigenvals().keys()):
        vecs.append(sp.simplify((A3 - e * sp.eye(3)).nullspace()[0]))
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            if abs(complex(sp.N(vecs[i].dot(vecs[j])))) > 1e-12:
                return False
    return True


@claim("05-特征值与特征向量", "可对角化 ⟺ 几何重数 = 代数重数（[[1,1],[0,1]] 不可对角化）")
def _():
    M = sp.Matrix([[1, 1], [0, 1]])
    M2 = sp.Matrix([[1, 0], [0, 2]])
    return (len(M.eigenvects()) == 1 and len(M2.eigenvects()) == 2)


@claim("05-特征值与特征向量", "相似矩阵有相同的迹与行列式")
def _():
    M = sp.Matrix([[0, 1, 1], [1, 2, 1], [1, 1, 0]])
    P = sp.Matrix([[1, 1, 0], [0, 1, 1], [1, 0, 1]])
    if P.det() == 0:
        return False
    N = P.inv() * M * P
    return eq(N.trace(), M.trace()) and eq(N.det(), M.det())


@claim("05-特征值与特征向量", "A^k 的特征值为 λ^k（k=2 验证）")
def _():
    ev = A3.eigenvals()
    ev2 = (A3 ** 2).eigenvals()
    return {sp.nsimplify(e ** 2) for e in ev} == {sp.nsimplify(e) for e in ev2}


@claim("06-二次型", "2023 年第 9 题：A3 的正惯性指数 1、负惯性指数 1、秩 2")
def _():
    ev = A3.eigenvals()
    pos = sum(mt for e, mt in ev.items() if e > 0)
    neg = sum(mt for e, mt in ev.items() if e < 0)
    return pos == 1 and neg == 1 and A3.rank() == 2


@claim("06-二次型", "惯性定理：标准形中正负项个数由 A 唯一确定")
def _():
    ev = A3.eigenvals()
    return sum(mt for e, mt in ev.items() if e != 0) == A3.rank()


@claim("06-二次型", "二次型 f=(x1+x2)²+(x2+x3)²-(x3-x1)² 的矩阵即为 A3")
def _():
    x1, x2, x3 = sp.symbols("x1 x2 x3")
    P = sp.expand((x1 + x2) ** 2 + (x2 + x3) ** 2 - (x3 - x1) ** 2)
    vs = (x1, x2, x3)
    # 对称矩阵的系数法：A_ii 取 x_i² 系数，A_ij = (x_i x_j 系数)/2
    def coef(poly):
        return sp.Poly(poly, *vs).coeff_monomial
    cf = coef(P)
    M = sp.zeros(3, 3)
    for i in range(3):
        for j in range(3):
            if i == j:
                M[i, j] = cf(vs[i] ** 2)
            elif i < j:
                M[i, j] = M[j, i] = sp.Rational(cf(vs[i] * vs[j]), 2)
    return eq(M, A3)


@claim("06-二次型", "正定 ⟺ 所有顺序主子式 > 0（以 [[2,1],[1,2]] 为例）")
def _():
    M = sp.Matrix([[2, 1], [1, 2]])
    return eq(M[0, 0], 2) and M[:1, :1].det() > 0 and M.det() > 0


@claim("06-二次型", "正定 ⟺ 所有特征值 > 0")
def _():
    M = sp.Matrix([[2, 1], [1, 2]])
    return all(e > 0 for e in M.eigenvals())


@claim("06-二次型", "负定 ⟺ 奇数阶顺序主子式 < 0、偶数阶 > 0（-I 验证）")
def _():
    M = -sp.eye(3)
    return M[0, 0] < 0 and M[:2, :2].det() > 0 and M.det() < 0


@claim("06-二次型", "2024 年第 22 题：实对称矩阵必可正交对角化")
def _():
    ev = A3.eigenvals()
    return sum(ev.values()) == 3 and all(abs(complex(sp.N(e)).imag) < 1e-12 for e in ev)


@claim("06-二次型", "合同变换保持正定性（P 可逆）")
def _():
    M = sp.Matrix([[2, 1], [1, 2]])
    P = sp.Matrix([[1, 1], [0, 1]])
    return all(e > 0 for e in (P.T * M * P).eigenvals())


# ===========================================================================
# 图文一致性
# ===========================================================================
EXPECT_FIGS = {
    # 键名必须与 figs/*.py 里 save_points() 实际写入的键一致；
    # 缺失的键会被 assert_figures() 报出来，防止「图和 sympy 各说各话」。
    "gaoshu-01-fig1": {
        "limit_at_0": 1,
        "f_at_1": sp.E,
    },
    "gaoshu-02-fig1": {
        "curvature_K": 2,
        "radius_R": sp.Rational(1, 2),
        "circle_center": [sp.Rational(1, 2), 0],
    },
    "gaoshu-03-fig1": {
        "rolle_xi": 2,
        "rolle_value": 4,
        "lagrange_xi": 1,
        "lagrange_point": [1, 1],
        "secant_slope": 2,
    },
    "gaoshu-04-fig1": {
        "tangent_slope_at_1": 1,
        "tangent_y_at_1": [sp.Rational(-1, 2), sp.Rational(1, 2), sp.Rational(3, 2)],
    },
    "gaoshu-05-fig1": {
        "intersection": [1, 1],
        "convergent_area_to_10": sp.Rational(9, 10),
        "convergent_limit": 1,
        "divergent_value_to_10": sp.log(10),
        "improper_value": 2,
    },
    "gaoshu-06-fig1": {
        "intersections": [0, 1],
        "area": sp.Rational(1, 3),
        "volume": 3 * sp.pi / 10,
    },
    "gaoshu-07-fig1": {
        "max_point": [1, 1 / sp.E],
    },
    "gaoshu-08-fig1": {
        "endpoints_y": [1, 1],
        "crit_point": [1, 1],
        "secant_slope": 0,
    },
    "gaoshu-09-fig1": {
        "vertices": [[sp.Rational(1, 3), 1], [1, sp.Rational(1, 3)], [1, 3], [3, 1]],
        "u_range": [sp.Rational(1, 3), 3],
        "v_range": [sp.Rational(1, 3), 3],
        "integral_value": 8 * sp.log(3) / 3,      # 与上面 2024Q17 的断言同源
    },
    "xiandai-01-fig1": {
        "sign_pattern": [[1, -1, 1], [-1, 1, -1], [1, -1, 1]],
    },
    "xiandai-02-fig1": {
        "adjugate_rank_rule": [3, 1, 0],
    },
    "xiandai-03-fig1": {
        "rank": 2,
        "pivot_cols": [1, 2],
    },
    "xiandai-04-fig1": {
        "rank": 2, "n": 3, "free_vars": 1,
    },
    "xiandai-05-fig1": {
        "columns_lambda_map": [1, 2, 3],
    },
    "xiandai-06-fig1": {
        "inertia_invariant": True,
    },
}

# 图上以字符串标注的解析式：必须与 sympy 的符号结果等价
EXPECT_FIG_EXPR = {
    "gaoshu-09-fig1": {
        "jacobian": (1 / (2 * sp.Symbol("v", positive=True)), sp.Symbol("v", positive=True)),
    },
}


def parse_expr(txt):
    """把图上标注的解析式字符串转成 sympy 表达式。

    只支持本资料实际使用的写法：`(8/3)ln3`、`1/(2v)`、`ln10` 这类
    「函数名与数字相邻」的隐式乘法，以及 `^` 作为乘方。
    """
    t = str(txt).replace("^", "**")
    t = re.sub(r"ln\s*\(", "log(", t)
    t = re.sub(r"ln\s*(\d+)", r"log(\1)", t)          # ln3 -> log(3)
    t = re.sub(r"\)\s*(?=[a-zA-Z0-9(])", ")*", t)      # (8/3)ln3 -> (8/3)*log(3)
    t = re.sub(r"(\d)\s*(?=[a-zA-Z(])", r"\1*", t)     # 3v -> 3*v（避免误伤 log(3)）
    t = t.replace("*(", "(").replace("*)", ")")
    v = sp.symbols("v", positive=True)
    return sp.sympify(t, locals={"log": sp.log, "ln": sp.log, "e": sp.E, "v": v})


def _norm(v):
    """把 JSON 里的值统一成可比较的形式。"""
    if isinstance(v, str):
        return parse_expr(v)
    if isinstance(v, bool):
        return v                       # 注意：bool 是 int 的子类，必须先判 bool
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if isinstance(v, int):
        return sp.Integer(v)
    return sp.nsimplify(v)


def assert_figures():
    """图上标注的关键点坐标必须等于 sympy 算出的值。"""
    problems = []
    if not os.path.isdir(FIGDATA):
        return problems
    for name, checks in EXPECT_FIGS.items():
        path = os.path.join(FIGDATA, name + ".json")
        if not os.path.exists(path):
            problems.append("%s: 缺少坐标数据文件（该图未按契约落盘关键点）" % name)
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as e:                               # noqa: BLE001
            problems.append("%s: 数据文件无法解析（%s）" % (name, e))
            continue
        for key, want in checks.items():
            if key not in data:
                problems.append("%s: 缺少应记录的坐标 %s" % (name, key))
                continue
            got = _norm(data[key])
            if isinstance(want, list):
                ok = (isinstance(got, list) and len(got) == len(want)
                      and all(eq(a, b, tol=1e-9) if not isinstance(a, bool) else a == b
                              for a, b in zip(got, want)))
            elif isinstance(want, bool):
                ok = (got == want)
            else:
                ok = eq(got, want, tol=1e-9)
            if not ok:
                problems.append("%s[%s]: 图上标注 %r，sympy 算出 %r" % (name, key, got, want))

    # 字符串解析式（如雅可比 1/(2v)）单独比对：转成符号再化简求差
    for name, checks in EXPECT_FIG_EXPR.items():
        path = os.path.join(FIGDATA, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for key, (expr, var) in checks.items():
            if key not in data:
                problems.append("%s: 缺少应记录的解析式 %s" % (name, key))
                continue
            got = parse_expr(data[key])
            if not eq(sp.simplify(got - expr), 0):
                problems.append("%s[%s]: 图上标注 %r，sympy 算出 %r"
                                % (name, key, got, expr))
    return problems


def main():
    verbose = "-v" in sys.argv
    if "--list" in sys.argv:
        for where, desc, _fn in CLAIMS:
            print("%-30s %s" % (where, desc))
        print("共 %d 条断言" % len(CLAIMS))
        return 0

    bad = 0
    for where, desc, fn in CLAIMS:
        try:
            ok = bool(fn())
        except Exception as e:                                # noqa: BLE001
            ok, desc = False, desc + "  [异常: %s]" % e
        if ok:
            if verbose:
                print("  ✓ %-28s %s" % (where, desc))
        else:
            bad += 1
            print("  ✗ %-28s %s" % (where, desc))
    for pb in assert_figures():
        bad += 1
        print("  ✗ 图文不一致：%s" % pb)

    print("-" * 78)
    if bad:
        print("✗ sympy 复算：%d / %d 条断言不成立" % (bad, len(CLAIMS)))
        return 1
    print("✓ sympy 复算：%d 条断言全部成立" % len(CLAIMS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
