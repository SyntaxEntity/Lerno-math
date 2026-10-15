// F3 的真实解析器层：用官方 mermaid 解析器逐块 parse() 全部 ```mermaid 代码块。
//
// 为什么必须「真解析」而不是正则扫：
//   mermaid 对「节点/边标签里含圆括号却没用双引号包裹」这类写法是**直接解析失败**的，
//   静态正则根本查不出来。而页面上一旦渲染失败，图就是一整块空白。
//
// 用法
// ----
//   node scripts/check_mermaid.mjs            # 输出 JSON（供 validate.py 消费）
//   node scripts/check_mermaid.mjs --strict   # 有解析失败时退出码 1
//   node scripts/check_mermaid.mjs --content <dir>   # 换扫描根（反向测试用）
//
// 依赖（版本必须与站点内置的运行时一致，否则校验的语法与线上渲染的不是同一个版本）：
//   mkdir -p .tools && cp scripts/tools-package.json .tools/package.json
//   npm install --prefix .tools --cache /tmp/npm-cache --no-audit --no-fund
//   ↑ 版本只在 tools-package.json 里写一次（PLAN-对齐与改版 §1.2），本文件不抄版本号。
//
// 退出码
// ------
//   0  扫描完成（有无解析失败都算完成，失败项写在 JSON 的 failed 里由 validate.py 报错）
//   1  --strict 模式下存在解析失败
//   2  环境缺少 mermaid / jsdom（**不是**「跳过」：validate.py 会因此直接报错）
//   3  内部错误
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));       // scripts
const ROOT = resolve(HERE, '..');                          // 仓库根（U2：脚本已在仓库根下）
const argv = process.argv.slice(2);
const ci = argv.indexOf('--content');
const CONTENT = ci >= 0 && argv[ci + 1] ? resolve(argv[ci + 1]) : join(ROOT, '数学二');  // 待扫描根
const TOOLS = join(ROOT, '.tools', 'node_modules');

const SKIP_DIRS = new Set(['scripts', 'assets', 'katex', 'node_modules', '.git', '.tools', '__pycache__']);

function fail(code, msg) {
  process.stdout.write(JSON.stringify({ total: 0, ok: 0, failed: [], error: msg }) + '\n');
  process.stderr.write('✗ ' + msg + '\n');
  process.exit(code);
}

// 装依赖的命令只有这一份说法：**版本不在本文件里写**，一律以 tools-package.json 为准
// （PLAN-对齐与改版 §1.2 的单一数据源要求；本地、CI、错误提示都指向同一个清单）。
const INSTALL = 'mkdir -p .tools && cp scripts/tools-package.json .tools/package.json && '
  + 'npm install --prefix .tools --cache /tmp/npm-cache --no-audit --no-fund';

if (!existsSync(join(TOOLS, 'mermaid'))) {
  fail(2, `未安装 mermaid 解析器（版本见 scripts/tools-package.json）。安装：\n  ${INSTALL}`);
}
if (!existsSync(join(TOOLS, 'jsdom'))) {
  fail(2, `未安装 jsdom（版本见 scripts/tools-package.json）。安装：\n  ${INSTALL}`);
}

// --- 给 mermaid 准备一个最小 DOM（mermaid 12 的 parse() 需要 DOM 才能初始化）---
const { JSDOM } = await import(join(TOOLS, 'jsdom', 'lib', 'api.js'));
const dom = new JSDOM('<!DOCTYPE html><body><div id="c"></div></body>', { pretendToBeVisual: true });
for (const k of ['window', 'document', 'DOMParser', 'Node', 'Element', 'SVGElement', 'HTMLElement', 'navigator', 'getComputedStyle']) {
  if (k === 'navigator' || k === 'getComputedStyle') continue;
  globalThis[k] = dom.window[k];
}
globalThis.window = dom.window;
globalThis.document = dom.window.document;

let mermaid;
try {
  mermaid = (await import(join(TOOLS, 'mermaid', 'dist', 'mermaid.esm.mjs'))).default;
  mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' });
} catch (e) {
  fail(3, '加载 mermaid 失败：' + String(e && e.message || e).split('\n')[0]);
}

// --- 收集待解析的 Markdown ---
function walk(dir, out = []) {
  let entries;
  try { entries = readdirSync(dir); } catch { return out; }
  for (const name of entries) {
    if (SKIP_DIRS.has(name)) continue;
    const p = join(dir, name);
    let st;
    try { st = statSync(p); } catch { continue; }
    if (st.isDirectory()) walk(p, out);
    else if (name.endsWith('.md')) out.push(p);
  }
  return out;
}

const files = walk(CONTENT).sort();
let total = 0, ok = 0;
const failed = [];

for (const f of files) {
  const lines = readFileSync(f, 'utf8').split('\n');
  let inBlock = false, buf = [], startLine = 0, lang = '';
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    const m = !inBlock && /^\s*```(\w*)\s*$/.exec(l);
    if (m) { inBlock = true; lang = m[1]; buf = []; startLine = i + 2; continue; }
    if (inBlock && l.trim() === '```') {
      inBlock = false;
      if (lang !== 'mermaid') continue;
      total++;
      const src = buf.join('\n');
      try {
        const r = await mermaid.parse(src);
        if (!r || !r.diagramType) {
          failed.push({ file: f, line: startLine, error: '解析未返回 diagramType（语法可能不被识别）' });
        } else {
          ok++;
        }
      } catch (e) {
        failed.push({ file: f, line: startLine, error: String((e && e.message) || e).split('\n')[0].slice(0, 300) });
      }
      continue;
    }
    if (inBlock) buf.push(l);
  }
  if (inBlock) failed.push({ file: f, line: startLine, error: 'mermaid 围栏未闭合' });
}

const rel = (p) => {
  const r = relative(ROOT, p);
  return (!r || r.startsWith('..')) ? p : r;   // 扫描根被 --content 换到仓库外时直接显示绝对路径
};
process.stdout.write(JSON.stringify({
  total, ok, failed,
  files: files.length,
  mermaidVersion: (await import(join(TOOLS, 'mermaid', 'package.json'), { with: { type: 'json' } })).default.version,
}) + '\n');

process.stderr.write(`mermaid 图 ${total} 块（${files.length} 个 md）｜真实解析通过 ${ok}｜失败 ${failed.length}\n`);
for (const x of failed) process.stderr.write(`  ✗ ${rel(x.file)}:${x.line} ${x.error}\n`);

if (process.argv.includes('--strict') && failed.length) process.exit(1);
process.exit(0);
