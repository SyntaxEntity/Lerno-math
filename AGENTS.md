# website/math2-kaoyan —— 考研数学二速成复习资料

本目录是一个**独立 git 仓库**（分支 `main`）。上游工作区说明见
[`../../AGENTS.md`](../../AGENTS.md)（若你的项目根是本目录，该文件不会被自动加载，
故要点在此复述）。

📋 **跨项目的对齐与改版规格见 [`../PLAN-对齐与改版.md`](../PLAN-对齐与改版.md)**——
它同时约束本仓库与 `../408-kaoyan/`，涉及外壳结构、类名、分期与验收。
发现规格有问题请回报管理会话改那份文件，**不要在本仓库里自行发明例外**。

## 一、路径提醒（2026-10-15 工作区重组）

| 旧路径（已失效） | 现在的实际位置 |
| --- | --- |
| `UCAS/408-new/` | **`UCAS/website/math2-kaoyan/`**（就是本目录） |
| `UCAS/408-kaoyan/` | `UCAS/website/408-kaoyan/`（408 项目，与本项目无关） |

⚠️ `408-new/` 这个目录名**已废弃且极具误导性**：它原本是 **408 项目**的仓库，
408 内容搬走后被**数学二**接管。历史会话记录里 `408-new/数学二/…` 就是本目录的
`数学二/…`。**不要把 `408-new` 当成 408 资料的位置。**

另：`math2-site/` 早年的独立 git 仓库历史已移到
`../.archive/math2-site-git-history/`（5 个提交，`git --git-dir=… log` 可读）。

## 二、目录职责

```
website/math2-kaoyan/
├── .github/workflows/pages.yml  Pages 工作流：两道门禁（validate + verify_math）→ pack_site → 上传 math2-site
├── 数学二/                      ★ 生成物 + 站点资源
│   ├── index.html               全科单页合集（高数 9 章 + 线代 6 章，主学习界面）
│   ├── README.md / README.html  说明（README.md 由 build_readme.py 生成）
│   ├── 高等数学/ 线性代数/        各章 .md 与 .html
│   ├── assets/                  matplotlib 生成的 PNG
│   ├── assets/site.css site.js  外置样式与外壳脚本（类名契约见 PLAN §2.4）
│   ├── katex/  mermaid.min.js   离线运行时
│   └── scripts/                 生成与校验工具链
├── parts/gaoshu/  parts/xiandai/   ★ 内容源，只写这里
├── math2-site/                  ★ 站点构建产物（.gitignore，不入库）
├── PLAYBOOK-速成资料工程化.md
├── PROMPT-数学二速成资料.md
└── .git-old-408-history/        归档：本目录早年 408 项目的 git 历史（勿使用）
```

## 三、再生成与校验（在 `数学二/` 目录下执行）

```bash
python3 scripts/run_all.py         # 一键全流程：绘图→复算→组装→校验→反向测试→HTML
python3 scripts/run_all.py --quick # 跳过反向测试与绘图，只重建 + 校验
python3 scripts/verify_math.py     # sympy 复算全部数值（含图上坐标）
python3 scripts/validate.py        # 校验 F1—F25（含 F22 外壳/行为层、F24 渲染残留、F25 解析排版）
python3 scripts/reverse_tests.py   # 反向测试：每条规则注入反例，确认它真会报错
node scripts/test_site_js.mjs      # 单独跑外壳脚本行为测试（jsdom，12 条）
python3 scripts/diff_math.py HEAD  # 改解析排版后：证明公式正文一字未改
```

Python 依赖按用途分两个文件（PLAN §1.2.1）：`数学二/scripts/requirements.txt`
= **CI 与校验**所需的全部（Markdown + sympy）；`requirements-dev.txt` = 本地生成链路
额外所需（`-r requirements.txt` + matplotlib）。Node 侧锁在 `tools-package.json`。
**CI 只跑校验与打包**（`validate.py` 形式 + `verify_math.py` 数值），
不重绘、不重生成产物，所以不装 matplotlib。

## 四、发布

`math2-site/` 是**构建产物，不入库**。发布走 `.github/workflows/pages.yml`：
推 `main` → 装依赖 → 两道门禁（`validate.py` 形式校验 F1—F25 / `verify_math.py` 数值复算）
→ `pack_site.py math2-site` → 上传。任一门禁不过即中止部署。

本地预览：`python3 数学二/scripts/pack_site.py math2-site`，
或直接打开 `数学二/index.html`（同样是离线可用的站点）。

⚠️ `pack_site.py` 的输出目录若已有 `.git`/`.github` 会**拒绝执行**（防止删掉历史与工作流）。
本仓库常态下不会触发（`math2-site/` 已 gitignore 且不含 VCS 元数据）。

## 五、硬性约定

- **改内容只改 `parts/`**，然后重跑脚本。`数学二/` 下的 `.md`/`.html` 都是生成物，
  手工改会在下次生成时被覆盖。
- `scripts/meta.py` 是**统计数字的唯一数据源**，正文数字由 `build.py` 注入。
- 考频/真题数据凡不能核实的，标注「考频待补充」或「真题改编」，**不许编造**。
  数据口径与可信度分级见 `数学二/README.md` 第三节。
- 站点是完全离线的纯静态页，改完直接用浏览器打开 `index.html` 验证，无需起服务器。
- **真题示例的解析一律「一步一段 + 关键公式独立成行」**（F25 强制）；
  引用块内相邻 `>` 行会并成同一段，所以每个段落之间**必须写空 `>` 行**。
- **加粗的闭合记号后面不能紧跟汉字**（`**…。**汉字` 不闭合，页面会露出 `**`，F24 会报）。
- 临时依赖放 `.tools/`（已 gitignore，约 478 MB），不要提交 `__pycache__/`。
