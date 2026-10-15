#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键跑通全流水线：绘图 → 复算 → 组装 → 校验 → 反向测试 → HTML。

顺序是有讲究的：
  1. `figs/*.py` 先跑，把 assets/*.png 与 figs/data/*.json 落盘 ——
     后续 verify_math 的「图-文一致」检查依赖这些数据文件；
  2. `verify_math.py` 复算全部数值（含图上坐标）；
  3. `normalize_md.py` 规范化内容源空行；
  4. `build.py` 组装成品；`build_readme.py` 生成 README；
  5. `validate.py` 校验成品；
  6. `reverse_tests.py` 反向测试（确认校验器不是摆设）；
  7. `build_html.py` 最后生成站点，再用 validate 复校一次 HTML。

用法
----
    python3 数学二/scripts/run_all.py            # 全部跑一遍
    python3 数学二/scripts/run_all.py --quick    # 跳过反向测试与绘图（只重建+校验）

解释器：绘图与复算需要 matplotlib/sympy。若当前解释器缺少依赖，本脚本会自动
改用仓库内的 `.tools/venv/bin/python`（存在时）。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENV = os.path.join(ROOT, ".tools", "venv", "bin", "python")

# matplotlib 需要一个**可写**的配置缓存目录：本机 $HOME/.config 是只读的，
# 不设它每次都会退到随机临时目录并重建字体缓存（慢且刷警告）。
# 默认放在仓库内 .tools/（已 gitignore），可用环境变量覆盖。
os.environ.setdefault("MPLCONFIGDIR", os.path.join(ROOT, ".tools", "mplcache"))
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

# Node 依赖的版本**只写在 tools-package.json 里**（PLAN-对齐与改版 §1.2 单一数据源）。
# 这里读它、不抄它：CI 装的是同一份清单，所以本地与线上不可能装出两个版本。
TOOLS_MANIFEST = os.path.join(HERE, "tools-package.json")
INSTALL_HINT = ("mkdir -p .tools && cp 数学二/scripts/tools-package.json .tools/package.json\n"
                "    npm install --prefix .tools --cache /tmp/npm-cache --no-audit --no-fund")


def _pkg_version(name):
    p = os.path.join(ROOT, ".tools", "node_modules", name, "package.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("version")
    except Exception:                                        # noqa: BLE001
        return None


def node_deps():
    """从 tools-package.json 读出 Node 依赖清单；读不到返回 None。"""
    try:
        with open(TOOLS_MANIFEST, encoding="utf-8") as f:
            return json.load(f).get("dependencies") or {}
    except Exception as e:                                   # noqa: BLE001
        print("! 读不到依赖清单 %s：%s"
              % (os.path.relpath(TOOLS_MANIFEST, ROOT), e))
        return None


def check_node_deps():
    """检查 .tools/node_modules 里的前端依赖是否就位、版本是否与清单一致。

    版本漂移必须**在开跑前**报出来：F3 用 `mermaid` 解析、`build_html.py` 用
    `mermaid/dist/mermaid.min.js` 和 `katex/dist` 生成站点运行时——两者版本不同，
    就会出现「校验通过但页面渲染不出来」这种最难查的情况。
    """
    want_all = node_deps()
    if want_all is None:
        return False
    problems = []
    for name, want in want_all.items():
        got = _pkg_version(name)
        if got is None:
            problems.append("缺少 %s" % name)
        elif got != want:
            problems.append("%s 版本不符：装的是 %s，清单要求 %s" % (name, got, want))
    if not problems:
        return True
    print("! Node 依赖有问题：%s" % "；".join(problems))
    print("  重装（版本以 数学二/scripts/tools-package.json 为准）：")
    print("    %s" % INSTALL_HINT)
    return False


def need_deps():
    """返回一个能 import matplotlib 与 sympy 的解释器路径。"""
    for cand in (sys.executable, VENV):
        if not os.path.exists(cand):
            continue
        r = subprocess.run([cand, "-c", "import matplotlib, sympy, markdown"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return cand
    print("! 找不到同时具备 matplotlib / sympy / markdown 的解释器。")
    print("  先运行：python3 -m venv .tools/venv && "
          ".tools/venv/bin/python -m pip install sympy matplotlib markdown")
    sys.exit(1)


def run(title, args, cwd=ROOT):
    print("\n" + "=" * 78)
    print("▶ " + title)
    print("=" * 78)
    r = subprocess.run(args, cwd=cwd, text=True)
    return r.returncode


def main():
    quick = "--quick" in sys.argv
    PY = need_deps()
    print("使用解释器：%s" % PY)
    deps_ok = check_node_deps()
    fails = []

    if not quick:
        for f in sorted(os.listdir(os.path.join(HERE, "figs"))):
            if f.startswith("fig_") and f.endswith(".py"):
                if run("绘图 %s" % f, [PY, os.path.join(HERE, "figs", f)]) != 0:
                    fails.append("绘图 " + f)

    if run("sympy 复算全部数值（含图上坐标一致性）",
           [PY, os.path.join(HERE, "verify_math.py")]) != 0:
        fails.append("verify_math")
    if run("规范化内容源空行", [PY, os.path.join(HERE, "normalize_md.py")]) != 0:
        fails.append("normalize_md")
    if run("组装成品 Markdown", [PY, os.path.join(HERE, "build.py")]) != 0:
        fails.append("build")
    if run("生成 README", [PY, os.path.join(HERE, "build_readme.py")]) != 0:
        fails.append("build_readme")
    if run("校验成品（F1—F21）", [PY, os.path.join(HERE, "validate.py")]) != 0:
        fails.append("validate")
    if not quick:
        if run("反向测试（每条校验规则注入反例）",
               [PY, os.path.join(HERE, "reverse_tests.py")]) != 0:
            fails.append("reverse_tests")
    if run("生成 HTML 站点", [PY, os.path.join(HERE, "build_html.py")]) != 0:
        fails.append("build_html")
    if run("校验（含 HTML 产物）", [PY, os.path.join(HERE, "validate.py")]) != 0:
        fails.append("validate(html)")

    print("\n" + "=" * 78)
    if not deps_ok:
        fails.append("node 依赖缺失")
    if fails:
        print("✗ 流水线有 %d 步失败：%s" % (len(fails), "、".join(fails)))
        return 1
    print("✓ 流水线全部通过")
    print("  成品入口：数学二/index.html（全科单页）、数学二/README.md（总览与数据口径）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
