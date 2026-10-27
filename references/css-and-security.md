# 样式层与安全边界（cssInjection / 模板 HTML 会被怎样处理）

扩展能改的是**文档的呈现**，不是工具的功能。这份文件说明样式放在哪、什么会被过滤、怎么写出「预览=打印=导出」都一致的卡片。

---

## 1. 样式层的位置与优先级

页面里和文档有关的 `<style>` 顺序（从上到下，越靠后同特异性越赢）：

```text
docCss       工具自带的文档样式（预览 / 打印 / 导出共用同一份）
extCss       ← 你的 cssInjection 在这里，紧跟在 docCss 后面
accentPrintCss  @media print 的强调色换算（只改 --doc-* 变量，带 !important）
```

三条推论：

1. **你的选择器和工具自带的冲突时，你赢**（同特异性、后写）。
2. **带 `!important` 的工具规则你压不住**（例如打印时 `.markdown-body{background:#fff !important}`），别硬刚——那是为了纸面能看。
3. 样式同时作用于**预览、打印、导出 HTML**——不用为导出单独写一套。

> ⚠️ 但 `extCss` 物理上是**整页**的样式表，不是 iframe。所以写 `body`/`*`/`.toolbar` 这类选择器会改到工具界面，而且改完可能连设置面板都点不开（只能清浏览器数据恢复）。**永远只用 `.ext-*` 这样的命名空间类，并用 `.markdown-body` 兜底限定。**

```css
.markdown-body .ext-tip{ … }   /* 双保险：只在文档正文里生效 */
```

---

## 2. 可以用的工具变量

扩展样式里直接用这些变量，就会跟着用户的主题色 / 字号 / 打印换算走：

| 变量 | 含义 | 打印时 |
|---|---|---|
| `--doc-accent` | 主题强调色（链接、引用竖线、目录高亮） | 自动换成深一点的「打印安全色」 |
| `--doc-quote` | 引用块/表头底色 | 同主题色系 |
| `--doc-line` | 标题下划线、表格边框、分隔线 | 同主题色系 |
| `--doc-mark` / `--doc-mark-ink` | `==高亮==` 底色 / 上面该用的字色 | 各自换算 |
| `--doc-size` | 正文基准字号 | 有配套的 `--doc-print-size` |
| `--doc-font` / `--doc-mono` | 正文 / 等宽字体栈 | — |
| `--doc-surface` | 表格、代码块、引用块那层「内容底色」 | — |

```css
.ext-tip .ext-tip-h{ color: var(--doc-accent); border-bottom:1px solid var(--doc-line); }
```

**注意**：这些变量是工具**内联**设置在根元素上的，你在 `:root{…}` 里重写它们**不会生效**（内联优先），只会制造困惑——别写 `:root`。

---

## 3. 打印要点（写样式时就要想到 A4）

| 要点 | 做法 |
|---|---|
| 底色/背景图不一定印 | 浏览器默认不印背景色。要印需用户在打印界面勾「背景图形」。**关键信息别只靠底色区分** |
| 卡片被切两页 | 给卡片加 `break-inside: avoid;`（旧写法 `page-break-inside: avoid;`） |
| 颜色太浅印不出来 | 扩展里写死的颜色**不会**走工具的黑白安全色换算；自己选深色；或用 `var(--doc-accent)` |
| 不想打印某些块（内部备注/提示） | 模板上加 `class="no-print"`——工具自带 `@media print{.no-print{display:none !important}}` |
| 只在打印出现的内容 | `cssInjection` 里写 `.ext-print-only{display:none} @media print{.ext-print-only{display:block}}` |
| 卡片跨页位置怪异 | 别用 `position:fixed`（打印会重复/错位），别用 `min-height:100vh`，别用 `float` |
| 双栏 | `display:flex` / `grid` 能打印，但**跨页容易断**；短块可以，长内容建议单栏 |
| 页面尺寸 | 是工具设置（A4/Letter/A5 + 边距），扩展不负责；`@page` 写了也压不过工具的页规则 |

---

## 4. 选择器白/黑名单

**可以写**（作用域都在正文容器里）：

```css
.ext-tip{…}                 /* 推荐：命名空间类 */
.markdown-body .ext-tip{…}  /* 更稳，连工具自带的同名类都不会误伤 */
.ext-tip > p:last-child{margin-bottom:0}
.ext-tip .ext-tip-h{…}
```

**不要写**：

```text
body  html  *  :root  ::selection
.toolbar  .tabs  .tab  .panes  .pane  .btn  .settings  .toast  .modal-mask
#editor  #previewScroll  #btnSettings  #docCss  #extCss
```

这些是工具界面（工具栏 / 设置面板 / 编辑区），改它们轻则界面错位，重则按钮点不到。还有：**不要写 `!important` 去压工具样式**，会破坏打印转换。

---

## 5. CSS 会被怎样净化（cssInjection 和模板里的 `style=` 都过这一层）

| 写法 | 结果 |
|---|---|
| `@import url(...);` | **整条删除** |
| `url(https://…)` / `url(//…)` / `url(x.png)` | 换成 `none`（离线原则） |
| `url(#grad)` | 保留（页内引用） |
| `url(data:image/png;base64,…)` | 保留（内嵌图片） |
| `expression(…)`（老 IE） | 改写成 `none(…)`（失效） |
| `behavior:` / `-moz-binding:` 声明 | 整条删除 |
| `javascript:` / `vbscript:` | 删除 |

**所以**：扩展引不到外部字体、外部背景图、CDN 图标。需要图片就 `data:` 内嵌（长，谨慎）或用 CSS 画（渐变、边框、`::before` 字符）。

---

## 6. 模板 HTML 会被怎样净化（三层信任模型）

| 层 | 内容 | 处理 |
|---|---|---|
| **骨架** | `replacement` 里除插值之外的 HTML | 每次渲染都过 `sanitizeHtml`（见下表） |
| **插值** | `$1…$9` / `$&`（行内捕获） | 一律当数据：文本位 HTML 转义、引号属性位属性转义 → 逃不出属性、变不成标签 |
| **`$content`** | 自定义围栏里的正文 | 是解析层自己的产物（正文里手写的 HTML 已被过滤过），**不再二次过滤**（否则 MathML/SVG 会被误杀） |

骨架 `sanitizeHtml` 明细：

| 处理 | 对象 |
|---|---|
| **连内容整段删** | `<script>` `<style>` `<iframe>` `<object>` `<embed>` `<link>` `<meta>` `<base>` `<form>` `<input>` `<button>` `<textarea>` `<select>` `<svg>` `<math>` |
| **删标签** | 上面这些标签的单独出现/自闭合形式 |
| **删属性** | `on*`（`onclick`、`onerror`…全部） |
| **链接改写为 `#`** | `href`/`src`/`xlink:href` 里的 `javascript:`、`vbscript:`、`data:text/html` |
| **过滤内联样式** | `style="…"` 过一遍第 5 节的 CSS 净化 |

**推论**：

- 不能在模板里放 `<style>`——样式统一写 `cssInjection`。
- 不能在模板里画 `<svg>`——图放正文（`$content` 里写 ` ```svg ` 围栏）。见 §8 示例。
- 不能靠 `onclick` 做交互——预览不是应用，且会被删。
- 模板允许：`div` `span` `p` `table` `ul/ol/li` `hr` `br` `b/strong` `i/em` `mark` `abbr` `sup/sub` `figure` `a` `img` 等常规标签。

> 安全模型的前提是「`.md` 可能是别人给的」。**不要设计绕过方案**（编码变形、CSS 注入、data 协议……），设计上就不支持，试出来的多半是「工具里看着能跑、导出/打印坏掉」。

---

## 7. 可以直接抄的样式配方

```css
/* 卡片：提示 / 易错 / 答案 三色系（都走主题色，打印自动变深） */
.ext-card{border-radius:10px;padding:.65em 1em;margin:.9em 0;break-inside:avoid;
  background:var(--doc-surface);border:1px solid var(--doc-line);border-left:4px solid var(--doc-accent)}
.ext-card-h{font-weight:700;margin-bottom:.3em;color:var(--doc-accent)}
.ext-card.ext-warn{border-left-color:#d64545}
.ext-card.ext-warn .ext-card-h{color:#b91c1c}
.ext-card.ext-ans{border-left-color:#16a34a}
.ext-card.ext-ans .ext-card-h{color:#15803d}
.ext-card > :last-child{margin-bottom:0}

/* 行内小标签 */
.ext-tag{display:inline-block;padding:0 .4em;margin:0 .1em;border-radius:4px;
  background:var(--doc-quote);color:var(--doc-accent);font-size:.92em;font-weight:600;
  border:1px solid var(--doc-line)}

/* 行内高亮（替换 ==…== 之外的另一种） */
.ext-hl{background:var(--doc-mark);color:var(--doc-mark-ink);padding:0 .18em;border-radius:3px}

/* 题号徽章 */
.ext-qno{display:inline-block;min-width:1.9em;padding:.05em .45em;border-radius:999px;
  background:var(--doc-accent);color:#fff;font-weight:700;font-size:.86em;text-align:center}

/* 缩写/术语（打印时 title 不显示，别把关键信息放这里） */
.ext-abbr{border-bottom:1px dotted var(--doc-line);cursor:help}

/* 表格里的紧凑段落（围栏内容常带 <p>） */
.ext-card p{margin:.35em 0}
```

---

## 8. 「要画图」的正确姿势

图**不能**写在围栏模板里（会被删）。写在正文里，用工具自带的渲染围栏：

````markdown
```tb-tip
下面这张图是**正文内容**，所以能画：

~~~svg
<svg width="320" height="90" viewBox="0 0 320 90" xmlns="http://www.w3.org/2000/svg">
  <rect x="1" y="1" width="318" height="88" rx="10" fill="#eef3ff" stroke="#2f6fed" stroke-width="2"/>
  <text x="160" y="52" font-size="16" text-anchor="middle" fill="#1d4ed8">$content 里可以嵌 SVG</text>
</svg>
~~~
```
````

（嵌套围栏要换标记：外层用 ` ``` `、内层用 `~~~` 或更长的反引号。）

`$content` 里的公式、图片、SVG、表格都按正常 Markdown 走，不会被扩展的过滤器二次处理。

---

## 9. 调试样式：为什么我的 CSS 没生效

| 症状 | 先查 |
|---|---|
| 完全没样式 | `cssInjection` 是不是字符串？类名和模板 `class` 是否**逐字**一致（大小写、连字符）？规则里是不是有语法错误导致整份禁用（看状态行） |
| 颜色不对 | 用了 `body`/`:root` 想覆盖工具变量？变量是内联的，改不动；改用自己的类 + `var(--doc-accent)` |
| 背景打印没了 | 正常：打印界面没勾「背景图形」 |
| 打印颜色变浅/变黑 | 扩展颜色不走打印安全色；确认用的是深色，或改用工具变量 |
| 样式在导出的 HTML 里丢了 | 导出会带 `extCss`；如果丢了，多半是规则本身没生效（导出时用的是同一份） |
| 界面被改花了 | 有全局选择器；改成 `.markdown-body .ext-xxx`，或直接清空扩展再排查 |
