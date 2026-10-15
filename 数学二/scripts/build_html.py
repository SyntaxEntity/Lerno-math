#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `数学二/` 下的 Markdown 渲染成可离线阅读的 HTML 站点。

产出
----
  数学二/<部分>/<章节>.html      每章一页（带侧栏）
  数学二/<部分>/index.html       部分首页（章节索引）
  数学二/index.html              全科单页合集（高数 + 线代全部内容）
  数学二/README.html             总览

要点
----
- **图片正确引用**：正文里的 `assets/xxx.png` 在子目录页面要变成 `../assets/xxx.png`，
  在根页面保持 `assets/xxx.png`。层级数一律用 `os.path.relpath` 现算，不手写 `../`。
- **Mermaid 离线可用**：把 `mermaid.min.js` 复制到 `数学二/`，页面用相对路径引入；
  浏览器端渲染。若运行时缺失，页面会**明确提示**并回退为源码，不静默留白。
- **缺失资源要提示**：渲染前先检查每个 md 引用的图片是否存在，缺失则在页面顶部
  列出警告框（`<p class="warn">`），而不是留白。
- **不把大文件内联进每个页面**：CSS/JS 各自只有一份（内联一份小 CSS，mermaid 用外部文件）。

用法： python3 数学二/scripts/build_html.py
"""
import html
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import meta as T          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
CONTENT = os.path.join(ROOT, "数学二")
MERMAID_SRC = os.path.join(ROOT, ".tools", "node_modules", "mermaid", "dist", "mermaid.min.js")
KATEX_DIR = os.path.join(ROOT, ".tools", "node_modules", "katex", "dist")
KATEX_DST = os.path.join(CONTENT, "katex")

try:
    import markdown
except ImportError:
    sys.exit("需要 python-markdown：%s -m pip install markdown" % sys.executable)

CSS = """
:root{
 --bg:#f7f7f5; --paper:#ffffff; --fg:#1f2328; --fg2:#3d444d; --mut:#6b7280;
 --line:#e3e6ea; --line2:#eef1f4; --acc:#1d4ed8; --acc2:#0b3d91;
 --codebg:#f5f7fa; --hi:#fff6d6; --warnbg:#fff8ec; --warnbd:#f0d9a8;
 --realbg:#f1f8f2; --realbd:#bcdcc2; --chip:#eef2f7;
 --sh:0 1px 2px rgba(16,24,40,.04),0 4px 16px rgba(16,24,40,.05);
 --serif:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",Georgia,"Times New Roman",serif;
 --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;
}
html[data-theme="dark"]{
 --bg:#0d1117; --paper:#161b22; --fg:#e6edf3; --fg2:#c9d1d9; --mut:#8b949e;
 --line:#2b3138; --line2:#22272e; --acc:#6ea8fe; --acc2:#9ec5fe;
 --codebg:#1b2129; --hi:#3a2f10; --warnbg:#2c2415; --warnbd:#5c4a1e;
 --realbg:#14251a; --realbd:#2f5c3c; --chip:#1f2630;
 --sh:0 1px 2px rgba(0,0,0,.3),0 4px 16px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--sans);
 font-size:16.5px;line-height:1.82;-webkit-font-smoothing:antialiased}
#wrap{display:flex;min-height:100vh}

/* ---------- 侧栏 ---------- */
nav{width:302px;flex:0 0 302px;background:var(--paper);border-right:1px solid var(--line);
 position:sticky;top:0;height:100vh;overflow:auto;padding:18px 14px 40px}
nav .navhead{display:flex;align-items:center;justify-content:space-between;
 gap:8px;margin:0 6px 12px}
nav .navhead h1{font-size:14.5px;margin:0;font-weight:700;letter-spacing:.02em}
nav .sitehome{font-size:12px;color:var(--acc);text-decoration:none;
 border:1px solid var(--line);border-radius:999px;padding:2px 9px;white-space:nowrap}
nav .sitehome:hover{border-color:var(--acc)}
nav input{width:100%;padding:8px 11px;border:1px solid var(--line);border-radius:9px;
 background:var(--bg);color:var(--fg);margin-bottom:12px;font-size:13px;font-family:var(--sans)}
nav input:focus{outline:2px solid var(--acc);outline-offset:-1px;border-color:transparent}
nav a{display:block;padding:6px 10px;color:var(--fg2);text-decoration:none;
 font-size:13.5px;border-radius:8px;line-height:1.5}
nav a:hover{background:var(--codebg);color:var(--fg)}
nav .grp{margin:16px 6px 6px;font-size:11.5px;color:var(--mut);
 font-weight:700;letter-spacing:.06em;text-transform:uppercase}
nav a.cur{background:var(--chip);color:var(--acc);font-weight:700}
nav .tocbox{margin:2px 0 10px 16px;padding-left:10px;border-left:2px solid var(--line)}
nav .tocbox a{font-size:12.5px;color:var(--mut);padding:3px 8px}
nav .tocbox a.cur{color:var(--acc);font-weight:600;background:none}

/* ---------- 主区 ---------- */
main{flex:1;min-width:0;padding:0 0 100px}
.inner{max-width:880px;margin:0 auto;padding:0 46px}
.chapterbar{position:sticky;top:0;z-index:20;background:var(--paper);
 border-bottom:1px solid var(--line);
 padding:12px 46px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
@supports (backdrop-filter:blur(1px)){
 .chapterbar{background:color-mix(in srgb,var(--paper) 86%,transparent);
  backdrop-filter:saturate(1.6) blur(10px)}
}
.chapterbar .cb-title{font-weight:750;font-size:15px;font-family:var(--serif)}
.chapterbar .cb-sub{color:var(--mut);font-size:12.5px}
.chapterbar .cb-spacer{flex:1}
.chapterbar a.cb-btn{display:inline-flex;align-items:center;gap:5px;font-size:12.5px;
 padding:6px 13px;border:1px solid var(--line);border-radius:999px;background:var(--paper);
 color:var(--fg2);text-decoration:none;white-space:nowrap;transition:.15s}
.chapterbar a.cb-btn:hover{border-color:var(--acc);color:var(--acc);transform:translateY(-1px)}
.chapterbar a.cb-btn.off{opacity:.32;pointer-events:none}
#progress{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--acc),#7c3aed);
 width:0;z-index:50;transition:width .1s linear}
#totop{position:fixed;right:22px;bottom:24px;z-index:30;display:none;
 padding:9px 15px;border:1px solid var(--line);border-radius:999px;background:var(--paper);
 color:var(--fg2);cursor:pointer;font-size:12.5px;box-shadow:var(--sh);font-family:var(--sans)}
#totop:hover{border-color:var(--acc);color:var(--acc)}
#themetoggle{position:fixed;right:22px;bottom:70px;z-index:30;
 padding:9px 13px;border:1px solid var(--line);border-radius:999px;background:var(--paper);
 color:var(--fg2);cursor:pointer;font-size:12.5px;box-shadow:var(--sh);font-family:var(--sans)}

/* ---------- 标题 ---------- */
h1{font-family:var(--serif);font-size:30px;line-height:1.35;font-weight:700;
 margin:34px 0 18px;letter-spacing:.01em}
h2{font-family:var(--serif);font-size:25px;margin:42px 0 8px;font-weight:700;
 line-height:1.4;scroll-margin-top:80px}
h3{font-size:18px;margin:26px 0 10px;font-weight:700}
p{margin:1em 0}
strong{font-weight:700}

/* ---------- 章节头（知识点标题 + 高频标签） ---------- */
.chaphead{margin:10px 0 26px;padding-bottom:16px;border-bottom:2px solid var(--line)}
h2.bookmark{margin:60px 0 0;padding:14px 18px;font-size:24px;font-weight:800;
 color:#fff;background:linear-gradient(100deg,var(--acc2),var(--acc));
 border-radius:12px;box-shadow:var(--sh);letter-spacing:.01em}
h2.bookmark .badge{background:rgba(255,255,255,.22);color:#fff;border-color:transparent;
 font-weight:700;margin-left:8px;vertical-align:3px}
h2.bookmark + .sec, h2.bookmark ~ .sec:first-of-type{margin-top:18px}
.bookhead{margin:34px 0 10px;padding-bottom:14px;border-bottom:2px solid var(--line)}
.bookhead h1{margin:0 0 8px}
.bookhead .lede{margin:0;color:var(--mut);font-size:14.5px;line-height:1.7}
/* ===== 第 1 层：部分（高等数学 / 线性代数）===== */
h2.parthead{margin:64px 0 10px;padding:18px 24px;font-size:29px;font-weight:800;
 color:#fff;letter-spacing:.02em;border-radius:14px;box-shadow:var(--sh);
 background:linear-gradient(100deg,#111827,#374151)}
html[data-theme="dark"] h2.parthead{background:linear-gradient(100deg,#1f2937,#374151)}
h2.parthead .tag{background:rgba(255,255,255,.18);color:#fff;border-color:transparent;
 font-weight:700;font-size:13px;margin-left:10px;vertical-align:4px}
h2.parthead:first-of-type{margin-top:26px}
.partoverview{margin:0 0 8px;padding:2px 0 2px 20px;color:var(--fg2)}
.partoverview h3{font-size:17px;margin:22px 0 8px;border:0;color:var(--mut);
 font-family:var(--sans);font-weight:700;letter-spacing:.02em}
.partoverview table{max-width:100%}
.anchor{scroll-margin-top:16px}
.backtop{margin:22px 0 0;font-size:13px}
.backtop a{color:var(--mut);text-decoration:none}
.backtop a:hover{color:var(--acc)}
.chapterbar .cb-home{font-weight:700;font-size:14px;color:var(--acc);
 text-decoration:none;font-family:var(--serif)}
.chaphead h2{margin:0 0 10px;border:0}
.badges{display:flex;gap:8px;flex-wrap:wrap}
.badge{font-size:12px;padding:3px 11px;border-radius:999px;background:var(--chip);
 color:var(--fg2);border:1px solid var(--line)}
.badge.hot{background:linear-gradient(135deg,#fff1c9,#ffe0a3);color:#7a4b00;
 border-color:#f0cf8a;font-weight:700}
html[data-theme="dark"] .badge.hot{background:#3a2f10;color:#ffd479;border-color:#5c4a1e}

/* ---------- 模板六段式 ---------- */
.sec{margin:30px 0}
/* ===== 字段层级：整块卡片 + 明显的标题条 ===== */
.sec{margin:34px 0;background:var(--paper);border:1px solid var(--line);
 border-radius:14px;box-shadow:var(--sh);overflow:hidden}
.sec > .sec-h{display:flex;align-items:center;gap:11px;margin:0;
 padding:13px 20px;background:linear-gradient(90deg,var(--codebg),transparent);
 border-bottom:1px solid var(--line);border-left:5px solid var(--acc)}
.sec > .sec-h .ic{width:30px;height:30px;flex:0 0 30px;border-radius:9px;
 display:grid;place-items:center;font-size:16px;background:var(--chip)}
.sec > .sec-h .tt{font-family:var(--serif);font-size:20px;font-weight:800;
 margin:0;padding:0;border:0;line-height:1.35;color:var(--fg)}
.sec > .sec-h .hint{font-size:12.5px;color:var(--mut);margin-left:auto;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sec > .box{padding:18px 22px}
/* 每个字段给一条自己的主色，帮助扫读时快速定位 */
.sec-freq > .sec-h{border-left-color:#0ea5e9}
.sec-core > .sec-h{border-left-color:var(--acc)}
.sec-key  > .sec-h{border-left-color:#7c3aed}
.sec-fig  > .sec-h{border-left-color:#0891b2}
.sec-err  > .sec-h{border-left-color:#d97706}
.sec-real > .sec-h{border-left-color:#16a34a}

.sec-freq .box{font-size:15.5px;font-weight:600}
.sec-freq .box blockquote{margin:0 0 4px;background:var(--codebg);border-left:3px solid var(--acc);
 border-radius:0 8px 8px 0;padding:9px 13px;font-size:14.6px;color:var(--fg2)}
.sec-freq .box > p:first-child{margin-top:0}
/* ===== 模块层级：核心讲解里的 【模块名】 ===== */
.sec-core .box h3, .sec-core .box h4, .sec-core .box h5{
 margin:30px 0 12px;padding:9px 0 9px 15px;font-size:18.5px;font-weight:800;
 font-family:var(--serif);color:var(--acc2);letter-spacing:.01em;
 border-left:6px solid var(--acc);border-radius:0 8px 8px 0;
 background:linear-gradient(90deg,var(--codebg),transparent)}
.sec-core .box > h3:first-child, .sec-core .box > h4:first-child,
.sec-core .box > h5:first-child{margin-top:2px}
.sec-core .box h4{font-size:17px;border-left-width:4px}
/* 【核心公式】【适用条件】这类次级标记 */
.sec-core .box p > strong:only-child{color:var(--acc);letter-spacing:.02em}
.sec-core .box{font-size:16.8px;line-height:1.95}
.sec-core .box p{margin:1.05em 0}
.sec-core .box p:first-child{margin-top:0}
.sec-core .box p:first-child::first-letter{font-size:1.02em}

/* 关键结论速记：卡片网格 */
.sec-key .box{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.sec-key ul{display:contents;margin:0;padding:0;list-style:none}
.sec-key li{margin:0;background:var(--bg);border:1px solid var(--line);
 border-radius:12px;padding:13px 15px;font-size:14.8px;line-height:1.72;
 position:relative;overflow:hidden}
.sec-key li::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
 background:linear-gradient(180deg,var(--acc),#7c3aed);opacity:.85}
.sec-key li strong:first-child,.sec-key li em:first-child{color:var(--acc2)}

/* 示意图 */
.sec-fig .box{background:var(--bg);border-radius:10px}
.sec-fig img{display:block;width:100%;height:auto;margin:12px 0;border-radius:10px;
 border:1px solid var(--line2);background:#fff}
.sec-fig .mermaid{margin:14px 0;padding:14px;background:var(--bg);border:1px solid var(--line);
 border-radius:12px;overflow:auto;text-align:center}
.sec-fig details{margin:6px 0 0}
.sec-fig .ascii{background:var(--bg);border:1px solid var(--line);border-radius:10px;
 font-size:12.5px;line-height:1.5}

/* 易错点：警示样式 */
.sec-err .box{background:var(--warnbg)}
.sec-err ul{margin:10px 0 0;padding:0;list-style:none}
.sec-err li{margin:12px 0;padding-left:30px;position:relative;font-size:15.6px;line-height:1.85}
.sec-err li::before{content:"⚠";position:absolute;left:0;top:0;color:#d97706;font-size:15px}
.sec-err li strong:first-child{color:#b45309}
html[data-theme="dark"] .sec-err li strong:first-child{color:#fbbf24}

/* 真题示例 */
.sec-real .box{background:var(--realbg)}
.sec-real .box > p:first-child{font-weight:700;color:#166534;font-size:16px;margin-top:0}
html[data-theme="dark"] .sec-real .box > p:first-child{color:#86efac}
.sec-real blockquote{margin:14px 0 6px;padding:12px 16px;background:var(--paper);
 border-left:4px solid var(--realbd);border-radius:0 10px 10px 0;font-size:15.4px}
.sec-real blockquote p{margin:.55em 0}
.sec-real blockquote ol,.sec-real blockquote ul{margin:.5em 0;padding-left:1.35em}

/* ---------- 通用元素 ---------- */
blockquote{margin:1.1em 0;padding:12px 16px;background:var(--codebg);
 border-left:4px solid var(--acc);border-radius:0 10px 10px 0;color:var(--fg2)}
code{background:var(--codebg);padding:.16em .42em;border-radius:6px;
 font:13.6px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;
 border:1px solid var(--line2)}
pre{background:var(--codebg);padding:14px 16px;border-radius:12px;overflow:auto;
 border:1px solid var(--line)}
pre code{background:none;padding:0;border:0;font-size:12.8px;line-height:1.62}
img{max-width:100%;height:auto}
hr{border:0;border-top:1px solid var(--line);margin:36px 0}
ul,ol{padding-left:1.5em}
li{margin:.34em 0}
table{border-collapse:separate;border-spacing:0;margin:16px 0;width:100%;
 display:block;overflow:auto;max-width:100%;font-size:14.6px;
 background:var(--paper);border:1px solid var(--line);border-radius:12px}
th,td{border-bottom:1px solid var(--line2);padding:9px 14px;text-align:left}
th{background:var(--codebg);font-weight:700;font-size:13.6px;color:var(--fg2);
 position:sticky;top:0}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--codebg)}
td:first-child,th:first-child{padding-left:16px}
.katex{font-size:1.04em}
.katex-display{margin:1.1em 0;overflow-x:auto;overflow-y:hidden;padding:2px 0}
.warn,.missing{background:var(--warnbg);border:1px solid var(--warnbd);padding:11px 15px;
 border-radius:10px;font-size:14px;margin:14px 0}
.missing{background:#fdecec;border-color:#f0b4b4}
html[data-theme="dark"] .missing{background:#2c1616;border-color:#6b2b2b}
#navtoggle{position:fixed;left:12px;top:12px;z-index:40;display:none;
 padding:8px 13px;border:1px solid var(--line);border-radius:9px;background:var(--paper);
 color:var(--fg);cursor:pointer;font-size:13.5px;box-shadow:var(--sh);font-family:var(--sans)}
.tag{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:999px;
 background:var(--hi);border:1px solid var(--line);margin-left:6px;vertical-align:2px}

@media (max-width:1080px){ .sec-key .box{grid-template-columns:1fr} }
@media (max-width:860px){
 #navtoggle{display:block}
 nav{position:fixed;left:0;top:0;z-index:35;transform:translateX(-102%);
  transition:transform .22s ease;box-shadow:2px 0 18px rgba(0,0,0,.16);width:86vw;max-width:320px;
  flex-basis:auto}
 body.navopen nav{transform:none}
 .inner{padding:0 18px}
 .chapterbar{padding:10px 18px}
 h1{font-size:25px} h2{font-size:21px} .sec-core .box{font-size:16px}
}
@media print{
 nav,#navtoggle,#totop,#themetoggle,#progress,.chapterbar{display:none!important}
 main{padding:0} .inner{max-width:none;padding:0}
 .sec,.sec > .box{box-shadow:none;break-inside:avoid}
 a{color:inherit;text-decoration:none}
}
"""

JS_FILTER = """
document.getElementById('q')?.addEventListener('input',e=>{
  const v=e.target.value.trim().toLowerCase();
  document.querySelectorAll('nav a').forEach(a=>{
    a.style.display = !v || a.textContent.toLowerCase().includes(v) ? '' : 'none';});
});
"""

KATEX_INIT = """
(function () {
  if (!window.renderMathInElement) {
    // 公式渲染器没加载到：明确提示，而不是留一堆 $...$ 让读者困惑
    var has = /\\$[^$]+\\$/.test(document.body.innerText || '');
    if (has) {
      var p = document.createElement('p');
      p.className = 'missing';
      p.textContent = '未加载到公式渲染器（katex/），页面里的 LaTeX 公式以源码显示。'
        + '请确认 数学二/katex/ 目录存在。';
      document.querySelector('main').insertBefore(p, document.querySelector('main').firstChild);
    }
    return;
  }
  renderMathInElement(document.body, {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '$', right: '$', display: false }
    ],
    throwOnError: false,
    ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
  });
})();
"""


NAV_JS = """
(function () {
  var main = document.querySelector('main');
  // 1) 侧栏高亮当前小节（滚动位置驱动）
  var links = [].slice.call(document.querySelectorAll('nav a.toclink'));
  var targets = links.map(function (a) {
    var id = a.getAttribute('href').slice(1);
    return document.getElementById(id);
  });
  function sync() {
    var y = window.scrollY + 120, best = -1;
    targets.forEach(function (t, i) { if (t && t.offsetTop <= y) best = i; });
    links.forEach(function (a, i) { a.classList.toggle('cur', i === best); });
  }
  if (links.length) {
    window.addEventListener('scroll', sync, { passive: true });
    window.addEventListener('resize', sync);
    sync();
  }
  // 2) 键盘：j/k 或 ←/→ 翻章
  var prev = document.body.getAttribute('data-prev');
  var next = document.body.getAttribute('data-next');
  document.addEventListener('keydown', function (e) {
    if (e.target.matches('input, textarea')) return;
    if (e.key === 'ArrowLeft' || e.key === 'k') { if (prev) location.href = prev; }
    if (e.key === 'ArrowRight' || e.key === 'j') { if (next) location.href = next; }
  });
  // 3) 移动端侧栏抽屉 + 回到顶部
  var t = document.getElementById('navtoggle');
  if (t) t.addEventListener('click', function () { document.body.classList.toggle('navopen'); });
  // 4) 阅读进度条
  var bar = document.getElementById('progress');
  if (bar) {
    var upd = function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = (h > 0 ? (window.scrollY / h) * 100 : 0) + '%';
    };
    window.addEventListener('scroll', upd, { passive: true });
    window.addEventListener('resize', upd); upd();
  }
  // 5) 主题切换（记忆到 localStorage）
  var tb = document.getElementById('themetoggle');
  if (tb) tb.addEventListener('click', function () {
    var cur = document.documentElement.dataset.theme;
    if (cur === 'auto') cur = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var nx = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = nx;
    try { localStorage.setItem('dsh-theme', nx); } catch (e) {}
  });
  var top = document.getElementById('totop');
  if (top) {
    top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    window.addEventListener('scroll', function () {
      top.style.display = window.scrollY > 500 ? 'block' : 'none';
    }, { passive: true });
  }
})();
"""


MERMAID_INIT = """
(function () {
  var nodes = document.querySelectorAll('.mermaid');
  if (!nodes.length) return;
  if (!window.mermaid) {
    nodes.forEach(function (el) {
      el.insertAdjacentHTML('beforebegin',
        '<p class="missing">未加载到 mermaid 运行时（mermaid.min.js 不在预期位置），' +
        '下图暂以源码显示，可复制到任意 mermaid 编辑器查看。</p>');
      var pre = document.createElement('pre');
      var code = document.createElement('code');
      code.textContent = el.textContent;
      pre.appendChild(code); el.innerHTML = ''; el.appendChild(pre);
    });
    return;
  }
  mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'neutral',
    flowchart: { useMaxWidth: true }, state: { useMaxWidth: true } });
  nodes.forEach(function (el, i) {
    mermaid.render('mmd-' + i, el.textContent.trim()).then(function (r) {
      el.innerHTML = r.svg;
    }).catch(function (e) {
      el.innerHTML = '<p class="missing">该图渲染失败：' + e.message + '</p>';
    });
  });
})();
"""


def protect_math(text):
    """把数学区间替换成占位符，避免 Markdown 把公式里的 * _ ^ 吃成强调标签。

    为什么必须做：Python-Markdown 会把 `$AA^{*}=A^{*}A$` 渲染成
    `$AA^{<em>}=A^{</em>}A$` —— 两个 `*` 被当成强调标记，公式彻底损坏。
    KaTeX 拿到的必须是原样的 `*`，所以要在 Markdown 处理前把公式整段藏起来。

    返回 (被保护的文本, 还原函数)。
    """
    store = []
    # 先 $$...$$（含跨行），再 $...$（不跨行、非空）
    text = re.sub(r"\$\$.*?\$\$",
                  lambda m: _stash(store, m.group(0)), text, flags=re.S)
    text = re.sub(r"\$[^$\n]+?\$",
                  lambda m: _stash(store, m.group(0)), text)
    return text, lambda h: _restore(h, store)


# 占位符必须是「Markdown 不会动它」的纯可见 ASCII：
# 实测 \x01…\x02 里的 \x02 会被 Python-Markdown 直接丢掉（C0 控制字符），
# 导致占位符只剩前半截、还原失败。改用 @@MATH0@@ 这种形态。
PLACEHOLDER = "@@MATH%d@@"


def _stash(store, chunk):
    store.append(chunk)
    return PLACEHOLDER % (len(store) - 1)


def _restore(html_text, store):
    """把占位符换回数学源码。

    用正则而不是 str.replace：Markdown 会在占位符两侧插入换行/空白
    （例如把块级公式包成 <p>\n占位符\n</p>），逐字替换会整片漏掉，
    之前就是这样导致 81 处公式只剩 \x01M… 控制字符。
    """
    def put(m):
        k = int(m.group(1))
        return store[k] if 0 <= k < len(store) else m.group(0)
    return re.sub(r"@@MATH(\d+)@@", put, html_text)


def md_to_html(text, depth, missing):
    """Markdown → HTML。depth 为当前页面相对 `数学二/` 的层级（0 或 1）。

    `assets/xxx.png` 与 `mermaid.min.js` 的相对前缀按 depth 现算。
    """
    prefix = "../" * depth
    blocks = []

    def stash(m):
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        if lang == "mermaid":
            blocks.append(
                '<div class="mermaid">%s</div>'
                '<details><summary>查看该图源码</summary><pre><code>%s</code></pre></details>'
                % (html.escape(code), html.escape(code)))
        else:
            cls = ' class="ascii"' if lang == "text" else ""
            blocks.append("<pre%s><code>%s</code></pre>" % (cls, html.escape(code)))
        return "\x00B%d\x00" % (len(blocks) - 1)

    text = re.sub(r"```(\w*)\n(.*?)```", stash, text, flags=re.S)

    # 保护数学区间，防止 Markdown 把公式里的 * _ ^ 当强调标记吃掉
    text, unprotect = protect_math(text)

    # 图片路径：正文按「相对 数学二/」书写；本页在 数学二/ 下则去掉前缀，
    # 在 数学二/<部分>/ 下则加 "../"。层级数由 depth 现算，不手写。
    def fix_img(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http", "data:")):
            return m.group(0)
        rel_src = src if not prefix else os.path.normpath(os.path.join(prefix, src))
        return "![%s](%s)" % (alt, rel_src.replace(os.sep, "/"))

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", fix_img, text)

    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = unprotect(body)
    for i, b in enumerate(blocks):
        body = body.replace("<p>\x00B%d\x00</p>" % i, b)
        body = body.replace("\x00B%d\x00" % i, b)
    return body


def page(title, sidebar_html, body, depth, extra_warn="", chapterbar="",
         data_prev="", data_next="", with_progress=True):
    prefix = "../" * depth
    return """<!DOCTYPE html>
<html lang="zh-CN" data-theme="auto"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title><style>%s</style>
<link rel="stylesheet" href="%skatex/katex.min.css">
<script src="%skatex/katex.min.js"></script>
<script src="%skatex/contrib/auto-render.min.js"></script>
<script src="%smermaid.min.js"></script>
<script>try{var t=localStorage.getItem('dsh-theme');if(t)document.documentElement.dataset.theme=t;}catch(e){}</script>
</head>
<body data-prev="%s" data-next="%s">
%s<button id="navtoggle" type="button">☰ 目录</button>
<div id="wrap"><nav>%s</nav><main>%s<div class="inner">%s%s</div></main></div>
<button id="totop" type="button">↑ 回到当前小节</button>
<button id="themetoggle" type="button" title="切换深色/浅色">◐ 主题</button>
<script>%s</script>
<script>%s</script>
<script>%s</script>
<script>%s</script></body></html>""" % (
        html.escape(title), CSS,
        prefix, prefix, prefix, prefix,
        html.escape(data_prev), html.escape(data_next),
        '<div id="progress"></div>' if with_progress else "",
        sidebar_html, chapterbar, extra_warn, body,
        JS_FILTER, NAV_JS, KATEX_INIT, MERMAID_INIT)


def sidebar(depth, current=None, single_page=False, toc=None):
    """左侧导航。

    toc: 当前章节的 [(锚点, 小节名)]，用于在侧栏展开「本章小节」跳转列表。
         小节 = 模板六个字段（考频统计/核心讲解/…），由 build() 生成。
    """
    prefix = "../" * depth
    home = ('<a class="sitehome" href="#top">回到顶部</a>' if single_page
            else '<a class="sitehome" href="%sindex.html">全科合集</a>' % prefix)
    out = ['<div class="navhead"><h1>数学二速成资料</h1>%s</div>' % home]
    out.append('<input id="q" placeholder="筛选章节（输入即过滤）">')
    if single_page:
        out.append('<a href="#top">↑ 回到顶部</a>')
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        out.append('<div class="grp">%s（约 %d 分 · %s）</div>'
                   % (sub["name"], sub["score"], sub["ratio"]))
        for t in T.TOPICS[k]:
            if single_page:
                href = "#%s-%s" % (k, t[6])
            else:
                href = "%s%s/%s.html" % (prefix, sub["dir"], t[6])
            cls = []
            if current == t[6]:
                cls.append("cur")
            out.append('<a class="%s" href="%s">%s%s</a>'
                       % (" ".join(cls), href, t[0],
                          ' <span class="tag">高频</span>' if t[5] else ""))
            # 当前章节展开小节跳转
            if toc and current == t[6] and not single_page:
                box = "".join('<a class="toclink" href="#%s">%s</a>'
                              % (aid, name) for aid, name, _ic, _h in toc)
                out.append('<div class="tocbox">%s</div>' % box)
    return "\n".join(out)


def chapterbar(subject_key, slug, depth, prev_href, next_href,
               prev_title, next_title):
    """章节页顶部固定条：当前章 + 上一章/下一章 + 键盘提示。"""
    t = next(x for x in T.TOPICS[subject_key] if x[6] == slug)
    name, times, years, pts, qtype, hot, _slug = t
    prev_cls = "cb-btn" + ("" if prev_href else " off")
    next_cls = "cb-btn" + ("" if next_href else " off")
    # 这里**不放章名**：章名在正文的章节头里已经出现，重复显示会很刺眼。
    # 顶部条只承担"我在哪一部分 + 怎么翻页"。
    return (
        '<div class="chapterbar">'
        '<a class="cb-home" href="%sindex.html">%s</a>'
        '<span class="cb-sub">第 %s 章 · %s 分 · %s</span>'
        '<span class="cb-spacer"></span>'
        '<a class="%s" href="%s" title="键盘 ← 或 k">← %s</a>'
        '<a class="%s" href="%s" title="键盘 → 或 j">%s →</a>'
        '</div>' % (
            "../" * depth,
            html.escape(T.SUBJECTS[subject_key]["name"]),
            html.escape(name),
            pts,
            "高频" if hot else "常规",
            prev_cls, prev_href or "#", html.escape(prev_title or "已是第一章"),
            next_cls, next_href or "#", html.escape(next_title or "已是最后一章")))


def section_anchors():
    """模板六字段 → 章节内锚点 / 图标 / 副标题。"""
    return [("sec-freq", "考频统计", "📊", "历年命题分布"),
            ("sec-core", "核心讲解", "📖", "定义 · 公式 · 适用条件"),
            ("sec-key", "关键结论速记", "⚡", "考前最后扫一眼"),
            ("sec-fig", "示意图", "📐", "几何直观与判定流程"),
            ("sec-err", "易错点", "⚠️", "错在哪 · 正确是什么"),
            ("sec-real", "真题示例", "🎯", "题干 · 解析")]


def structure_sections(body, base=2):
    """把六个模板字段包成带样式的区块，提升可读性。

    Markdown 渲染后，六个字段各是一个 <p>（如 `<p><strong>核心讲解</strong>：</p>`）。
    做法：先给这些 <p> 打上 id，再按它们的位置把正文切成 6 段，
    每段外面套 `<section class="sec sec-xxx">` 并生成小标题栏。

    注意切片必须覆盖**整个** <p>…</p>（含闭合标签），否则段落会残缺——
    之前只匹配到开标签，导致每页多出三个未闭合的 <p>。
    """
    def strip_label(html_text):
        """删掉字段段落开头的「**字段名**：」标签。

        字段名已经在区块标题栏里显示，正文再出现一次就是"同一行字看两遍"。
        只删第一个 <p> 里的那一个 <strong>。
        """
        return re.sub(r"^(\s*)<p[^>]*>\s*<strong>[^<]+</strong>：?\s*",
                      r"\1<p>", html_text, count=1)

    def demote(html_text):
        """把字段内的 ##/### 降级到 base 之下，保持文档大纲正确。

        正文里的 `##` 是「模块」、`###` 是「子模块」；字段标题本身占一级，
        所以模块应落在 base+1、子模块 base+2。
        """
        # ## → base+1（模块），### → base+2（子模块）；
        # 注意是 base+1 而不是 base：模块必须比字段标题**深一级**，
        # 早先写成 base-1+1 导致章节页里模块与字段标题同为 h2、层级压平。
        html_text = re.sub(r"<h([23])>", lambda m: "<h%d>" % (int(m.group(1)) + base - 1),
                           html_text)
        html_text = re.sub(r"</h([23])>", lambda m: "</h%d>" % (int(m.group(1)) + base - 1),
                           html_text)
        return html_text

    marks = []
    for aid, name, _ic, _hint in section_anchors():
        pat = r'<p>(<strong>%s</strong>.*?)</p>' % re.escape(name)
        m = re.search(pat, body, re.S)
        if not m:
            continue
        marks.append((m.start(), m.end(), aid, name))
        body = body[:m.start()] + '<p id="%s">%s</p>' % (aid, m.group(1)) + body[m.end():]
    if not marks:
        return body

    # 打上 id 后重新定位（字符串长度变了，但位置按新串重新求）
    spans = []
    for aid, name, _ic, _hint in section_anchors():
        m = re.search(r'<p id="%s">.*?</p>' % aid, body, re.S)
        if m:
            spans.append((m.start(), m.end(), aid, name))

    out, cursor = [], 0
    for idx, (st, en, aid, name) in enumerate(spans):
        out.append(body[cursor:st])
        end = spans[idx + 1][0] if idx + 1 < len(spans) else len(body)
        ic, hint = next((i, h) for a2, _n, i, h in section_anchors() if a2 == aid)
        # 区间必须从**字段标签段落本身**开始（st），不能从它之后（en）开始：
        # 从 en 开始会把「**考频统计**：…」这一整段丢在 section 外面，
        # 于是页面上「考频统计」只剩标题、内容整段消失（实测过的严重 bug）。
        out.append(
            '<section class="sec sec-%s" id="%s">'
            '<div class="sec-h"><span class="ic">%s</span>'
            '<h%d class="tt">%s</h%d><span class="hint">%s</span></div>'
            '<div class="box">%s</div></section>'
            % (aid.replace("sec-", ""), aid, ic, base, name, base, hint,
               demote(strip_label(body[st:end]))))
        cursor = end
    out.append(body[cursor:])
    return "".join(out)


def chapter_head(body, name, hot, pts, sub_name):
    """把 `## 名称 [高频]` 换成带头部徽章的章节大标题。"""
    m = re.search(r'<h2>(.*?)</h2>', body, re.S)
    if not m:
        return body, name
    raw = re.sub(r"<[^>]+>", "", m.group(1))
    title = raw.replace("[高频]", "").strip()
    tag = ('<span class="badge hot">高频考点</span>' if hot
           else '<span class="badge">常规考点</span>')
    head = ('<header class="chaphead"><h1>%s</h1><div class="badges">'
            '%s<span class="badge">%s</span><span class="badge">建议 %d 分</span>'
            '</div></header>' % (title, tag, sub_name, pts))
    return body[:m.start()] + head + body[m.end():], title


def collect_missing():
    """检查成品 md 引用的图片是否存在，返回缺失文件名的集合。

    解析基准固定为 `数学二/`（不是 md 文件所在目录）：正文里的 `assets/xxx.png`
    是**相对交付根**写的，HTML 渲染时统一改写成带 `../` 前缀的路径。
    """
    missing = set()
    for f in glob_md():
        text = open(f, encoding="utf-8").read()
        for m in re.finditer(r"!\[[^\]]*\]\((assets/[^)\s]+)\)", text):
            p = os.path.normpath(os.path.join(CONTENT, m.group(1)))
            if not os.path.exists(p):
                missing.add(os.path.basename(m.group(1)))
    return missing


def glob_md():
    out = []
    for k in T.ORDER:
        d = os.path.join(CONTENT, T.SUBJECTS[k]["dir"])
        out.extend(sorted(f for f in __import__("glob").glob(os.path.join(d, "*.md"))))
    return out


def copy_mermaid_runtime():
    if not os.path.exists(MERMAID_SRC):
        print("! 未找到 %s，页面将回退为源码并提示" % os.path.relpath(MERMAID_SRC, ROOT))
        return False
    dst = os.path.join(CONTENT, "mermaid.min.js")
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(MERMAID_SRC):
        shutil.copyfile(MERMAID_SRC, dst)
    print("  已复制 mermaid 运行时 %.1f MB → 数学二/mermaid.min.js"
          % (os.path.getsize(dst) / 1048576.0))
    return True


def copy_katex():
    """把 KaTeX（含字体）复制到 数学二/katex/，让公式渲染完全离线可用。"""
    if not os.path.isdir(KATEX_DIR):
        print("! 未找到 %s，公式将以 LaTeX 源码显示" % os.path.relpath(KATEX_DIR, ROOT))
        return False
    os.makedirs(os.path.join(KATEX_DST, "contrib"), exist_ok=True)
    os.makedirs(os.path.join(KATEX_DST, "fonts"), exist_ok=True)
    for f in ("katex.min.css", "katex.min.js"):
        src = os.path.join(KATEX_DIR, f)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(KATEX_DST, f))
    src = os.path.join(KATEX_DIR, "contrib", "auto-render.min.js")
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(KATEX_DST, "contrib", "auto-render.min.js"))
    n = 0
    fdir = os.path.join(KATEX_DIR, "fonts")
    if os.path.isdir(fdir):
        for f in os.listdir(fdir):
            if f.endswith((".woff2", ".woff", ".ttf")):
                shutil.copyfile(os.path.join(fdir, f),
                                os.path.join(KATEX_DST, "fonts", f))
                n += 1
    print("  已复制 KaTeX 运行时（%d 个字体文件）→ 数学二/katex/" % n)
    return True


def warn_block(missing):
    if not missing:
        return ""
    return ('<p class="missing"><b>资源缺失提示：</b>本页引用了 %d 个不存在的图片文件：%s。'
            '这些位置会显示为空白，请先运行 <code>数学二/scripts/figs/</code> 下的绘图脚本。'
            '</p>' % (len(missing), "、".join(sorted(missing))))


def build():
    missing = collect_missing()
    if missing:
        print("! 有 %d 个被引用的图片不存在：%s"
              % (len(missing), "、".join(sorted(missing))))
    chapters, overviews, n = {}, {}, 0

    # 全局章节顺序（跨部分），用于「上一章 / 下一章」与键盘翻章
    order = [(k, t[6], t[0]) for k in T.ORDER for t in T.TOPICS[k]]

    def href_of(i, k):
        """第 i 章相对当前部分目录的链接（同部分用文件名，跨部分用 ../部分/文件）。"""
        if not (0 <= i < len(order)):
            return ""
        k2, slug2, _ = order[i]
        if k2 == k:
            return slug2 + ".html"
        return "../%s/%s.html" % (T.SUBJECTS[k2]["dir"], slug2)

    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        d = os.path.join(CONTENT, sub["dir"])
        ov = open(os.path.join(d, "00-科目总览.md"), encoding="utf-8").read()
        # 同一个 md 要按两种相对层级各渲染一次：章节页在 数学二/<部分>/ 下（depth=1），
        # 单页合集在 数学二/ 下（depth=0）。**不要复用同一个结果**——复用会让图片路径
        # 在另一种层级下全部失效，而页面照样生成，属于静默错误。
        overviews[(k, 1)] = md_to_html(ov, 1, missing)
        overviews[(k, 0)] = md_to_html(ov, 0, missing)
        for t in T.TOPICS[k]:
            slug = t[6]
            src = open(os.path.join(d, slug + ".md"), encoding="utf-8").read()
            body_chapter, chap_title = chapter_head(
                structure_sections(md_to_html(src, 1, missing)),
                t[0], t[5], t[3], sub["name"])
            body_chapter = re.sub(r"<h1>.*?</h1>", "", body_chapter, count=1, flags=re.S)
            chapters[(k, slug)] = structure_sections(md_to_html(src, 0, missing), base=4)
            i = next(j for j, (kk, ss, _) in enumerate(order) if kk == k and ss == slug)
            prev_href = href_of(i - 1, k)
            next_href = href_of(i + 1, k)
            bar = chapterbar(k, slug, 1, prev_href, next_href,
                             order[i - 1][2] if i > 0 else "",
                             order[i + 1][2] if i + 1 < len(order) else "")
            with open(os.path.join(d, slug + ".html"), "w", encoding="utf-8") as f:
                f.write(page("%s · %s" % (sub["name"], t[0]),
                             sidebar(1, slug, toc=section_anchors()),
                             body_chapter, 1, warn_block(missing), bar,
                             prev_href, next_href))
            n += 1
        ov_body = re.sub(r"<h1>.*?</h1>", "", overviews[(k, 1)], count=1, flags=re.S)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(page("%s · 考研数学二" % sub["name"], sidebar(1, None),
                         '<header class="bookhead"><h1>%s</h1>'
                         '<p class="lede">%s · 约 %d 分（%s）· %d 章</p></header>%s'
                         % (sub["name"], sub["name"], sub["score"], sub["ratio"],
                            len(T.TOPICS[k]), ov_body),
                         1, warn_block(missing)))

    # ---- 全科单页合集 ----
    # 标题层级刻意只保留两级，避免"重复标题"：
    #   h1  —— 全站标题（只出现一次）
    #   h2  —— 部分标题（去掉各 md 自带的那一级，由本函数统一生成）
    #   h3  —— 章节标题（章节正文里的 ## 已被 chapter_head 提升级别后放入）
    parts = ['<a id="top"></a>',
             '<header class="bookhead"><h1>考研数学二 · 全科速成复习资料</h1>'
             '<p class="lede">高等数学 9 章 + 线性代数 6 章，共 150 分。'
             '左侧可筛选章节，Ctrl+F 全文检索；键盘 ←/→ 在章节页间翻动。</p></header>',
             warn_block(missing)]
    for k in T.ORDER:
        sub = T.SUBJECTS[k]
        parts.append('<h2 class="parthead" id="part-%s">%s'
                     ' <span class="tag">约 %d 分 · %s</span></h2>'
                     % (k, sub["name"], sub["score"], sub["ratio"]))
        # 单页合集里，科目总览只保留「本章怎么复习」这类**独有**内容：
        #   - 「章节索引」表与左侧导航重复，删掉；
        #   - 「本科目在整卷中的位置」两个科目文字几乎相同，删掉（章节页里保留）。
        # 否则单页里会出现两条一模一样的标题（F21 就是这么抓出来的）。
        body_ov = re.sub(r"<h1>.*?</h1>", "", overviews[(k, 0)], count=1, flags=re.S)
        body_ov = re.sub(
            r"<h2>本科目章节索引</h2>.*?(?=<h2>|\Z)", "", body_ov, flags=re.S)
        body_ov = re.sub(
            r"<h2>本科目在整卷中的位置</h2>.*?(?=<h2>|\Z)", "", body_ov, flags=re.S)
        body_ov = re.sub(r"<h2>", "<h3>", body_ov)
        body_ov = re.sub(r"</h2>", "</h3>", body_ov)
        parts.append('<div class="partoverview">%s</div>' % body_ov)
        for t in T.TOPICS[k]:
            parts.append('<div id="%s-%s" class="anchor"></div>' % (k, t[6]))
            parts.append('<h3 class="bookmark">%s%s</h3>'
                         % (t[0], ' <span class="badge hot">高频</span>' if t[5]
                            else ' <span class="badge">常规</span>'))
            # 去掉章节正文自带的 h1 与 h2：章名已由上面的 h3.bookmark 给出，
            # 重复渲染会让读者看到"同一标题连着出现两次"。
            chap_body = re.sub(r"<h1>.*?</h1>", "", chapters[(k, t[6])],
                               count=1, flags=re.S)
            chap_body = re.sub(r"<h2>.*?</h2>", "", chap_body,
                               count=1, flags=re.S)
            parts.append(chap_body)
            parts.append('<p class="backtop"><a href="#top">↑ 回到顶部</a></p>')
    with open(os.path.join(CONTENT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("考研数学二 · 全科速成复习资料",
                     sidebar(0, None, single_page=True),
                     "\n".join(parts), 0, ""))

    # ---- README.html ----
    rp = os.path.join(CONTENT, "README.md")
    if os.path.exists(rp):
        body = md_to_html(open(rp, encoding="utf-8").read(), 0, missing)
        with open(os.path.join(CONTENT, "README.html"), "w", encoding="utf-8") as f:
            f.write(page("数学二 · 总览与数据口径", sidebar(0, None), body, 0,
                         warn_block(missing)))
    return n


def main():
    T.check()
    copy_mermaid_runtime()
    copy_katex()
    n = build()
    print("已生成 %d 个章节页 + %d 个部分首页 + 1 个全科单页 + README.html"
          % (n, len(T.ORDER)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
