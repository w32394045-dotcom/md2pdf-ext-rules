# 扩展 JSON 字段参考（对应 md2pdf 内置校验器 extValidate）

本文件是 md2pdf「自定义扩展」JSON 的**完整字段规格**，按工具真实校验顺序排列。
写规则时以本表为准；`scripts/check_ext.py` 是本表的可执行版本，工具里的校验器是最终权威。

---

## 1. 顶层

```json
{
  "meta":         { "name": "…", "version": "…" },
  "preProcess":   [ … ],
  "customSyntax": [ … ],
  "uiInjection":  [ … ],
  "cssInjection": "…"
}
```

- 最外层**必须是一个对象**（`{…}`）。数组 / 字符串 / 数字 / `null` 都报 `root`。
- 五个键**全部可选**；`{}` 合法（等于「启用了但没有规则」）。
- 未知键**静默忽略**，不告警、不生效 —— 拼错 `customSyntax` 是最常见的「写了没反应」。
- **不能写 `null`**：`"preProcess": null` 报 `field`（`preProcess`）。不用的键直接省略。空数组 / 空串合法。
- 整段 JSON 文本（`trim` 之后）超过 **200 000** 个字符 → 报 `size`，整份不生效。

---

## 2. `meta`

| 字段 | 类型 | 必填 | 上限 | 超限行为 |
|---|---|---|---|---|
| `name` | string | 否 | 60 | 静默截断 |
| `version` | string | 否 | 20 | 静默截断 |

- `meta` 不是对象（如字符串）→ **静默忽略**（不报错，`name`/`version` 为空）。
- 状态行显示：`已启用：<name>（<version>）`；没写时显示 `已启用：未命名扩展（1.0）`。
- 建议写：方便用户在多套规则之间认人。

---

## 3. `preProcess`（解析前全文替换）

必须是**数组**；每项是**对象**。校验顺序即报错优先级：

| 顺序 | 字段 | 规则 | 违反时报错 |
|---|---|---|---|
| 1 | 数组本身 | `Array.isArray` | `field` · `preProcess` |
| 2 | 项 | 必须是对象（数组也不行） | `field` · `preProcess[i]` |
| 3 | `pattern` | string、非空、≤ 2 000 | `field` · `preProcess[i].pattern` |
| 4 | `flags` | 可选；string；匹配 `^[gimsuy]*$` | `field` · `preProcess[i].flags` |
| 5 | `replacement` | string（**允许空串**） | `field` · `preProcess[i].replacement` |
| 6 | 正则可编译 | `new RegExp(pattern, flags \|\| '')` | `regex` · `<pattern>` |
| 7 | 嵌套量词检查 | `EXT_BAD_QUANT`（`(a+)+` 之类） | 只告警 `backtrack` |

- **不写 `g` = 只替换第一处**（不是默认全局）。
- 执行顺序：数组从前到后，后一条看到的是前一条替换后的文本。
- 替换串是 JS `String.replace` 语义，`$` 有特殊含义（见 `patterns-and-replacements.md`）。
- 作用范围：**整篇源码**，包括代码块、公式、链接、表格。

```json
"preProcess": [
  { "pattern": "\\.\\.\\.", "replacement": "…", "flags": "g" }
]
```

---

## 4. `customSyntax`（自定义语法：行内 / 围栏）

必须是**数组**；每项是**对象**。

| 顺序 | 字段 | 规则 | 违反时报错 |
|---|---|---|---|
| 1 | 数组本身 | `Array.isArray` | `field` · `customSyntax` |
| 2 | 项 | 必须是对象 | `field` · `customSyntax[i]` |
| 3 | `type` | 必须是 `"inline"` 或 `"block"` | `field` · `customSyntax[i].type` |
| 4 | `replacement` | string、非空、≤ 4 000 | `field` · `customSyntax[i].replacement` |

> 注意：`replacement` 的检查**排在 `pattern` / `fence` 之前**，所以模板为空时先报模板。

### 4.1 `type: "inline"`

| 字段 | 规则 |
|---|---|
| `pattern` | string、非空、≤ 2 000；以 `g` 编译（项里写 `flags` 会被忽略） |
| `replacement` | 模板字符串；占位符见下 |

- 编译失败 → `regex` · `<pattern>`。
- 占位符 **`$N` 裸插进标签**（标签内、又不在引号属性值里）→ `unsafeTemplate` · `$N`（detail 是两个字符，如 `$1`）。
- 允许的位置：标签外的文本位；**引号包住**的属性值里（`class="ext-$1"`、`title="$2"`）。
- 模板里写 `$content` **不会报错**，但也不替换——行内没有「正文」概念。
- `pattern` 里的 `\d` 之类反斜杠在 JSON 字符串里要写 `\\d`。

```json
{ "type": "inline",
  "pattern": "\\[\\[t:([^\\]]+)\\]\\]",
  "replacement": "<span class=\"ext-tag\">$1</span>" }
```

### 4.2 `type: "block"`

| 顺序 | 字段 | 规则 | 违反时报错 |
|---|---|---|---|
| 1 | `fence` | `trim()` + 小写后匹配 `^[a-z][a-z0-9_-]{0,30}$` | `field` · `customSyntax[i].fence` |
| 2 | 撞内置保留名 | 见 §7 | **只告警** `fenceConflict`，**跳过这一条**（整份其他规则仍生效） |
| 3 | 重名 | 同一份 JSON 里 fence 不能重复 | `field` · `customSyntax[i].fence` |
| 4 | `$content` 存在 | 模板里必须含字符串 `$content` | `contentMissing` · `<fence>` |
| 5 | `$content` 位置 | 不能出现在**任何** HTML 标签里（含引号属性值） | `unsafeTemplate` · `$content` |

- 不需要 `pattern`（block 是靠围栏名触发的）。
- 模板可以多次出现 `$content`（正文会插多次）。
- 模板里 `$contentX` 会渲染成「正文 + `X`」。
- `pattern` 字段如果写了会被忽略（不报错）。

```json
{ "type": "block", "fence": "tip",
  "replacement": "<div class=\"ext-tip\"><div class=\"ext-tip-h\">提示</div>$content</div>" }
```

---

## 5. `uiInjection`（顶栏按钮）

必须是**数组**；每项是**对象**。校验顺序：

| 顺序 | 字段 | 规则 | 违反时 |
|---|---|---|---|
| 1 | 数组本身 | `Array.isArray` | `field` · `uiInjection` |
| 2 | 项 | 必须是对象 | `field` · `uiInjection[i]` |
| 3 | `location` | 可选；只有 `"toolbar"` 有效 | 其他值 → 只告警 `uiLocation` 并**跳过该项** |
| 4 | `action` | 必须字面 `"insertText"` | `field` · `uiInjection[i].action` |
| 5 | `label` | string、`trim` 后非空 | `field` · `uiInjection[i].label` |
| 6 | `text` | string（允许空串） | `field` · `uiInjection[i].text` |
| 7 | 数量 | 最多 6 个 | 第 7 个报 `field` · `uiInjection[6]` |

- 生效时 `label` 截 40、`text` 截 500（静默截断）。
- 点击 = 在编辑区**光标处插入 `text` 原文**（Markdown 源码，可以是多行）。

```json
"uiInjection": [
  { "location": "toolbar", "action": "insertText", "label": "插入答案区", "text": "\n## 参考答案\n\n" }
]
```

---

## 6. `cssInjection`（文档样式）

| 规则 | 违反时 |
|---|---|
| 必须是 **string**（数组/数字/对象/`null` 都不行） | `field` · `cssInjection` |
| 内容经 CSS 净化（见 `css-and-security.md`） | 净化，不报错 |

- 样式写进页面里一个独立 `<style>`，排在文档自带样式**之后**（同特异性时后者赢）。
- 预览 / 打印 / 导出 HTML 三处都会带上。
- 没有自动作用域：**必须自己用类名命名空间**（`.ext-*`）。

```json
"cssInjection": ".ext-tip{border-left:4px solid #e0a300;background:#fff8e1;border-radius:8px;padding:.6em 1em;break-inside:avoid}"
```

---

## 7. 内置保留围栏名（80 个，撞了会被静默跳过）

`bash c c++ cc cfg cjs conf console cpp cs csharp css dart diff env fish go golang gradle groovy h hpp htm html ini java javascript js json json5 jsonc jsx kotlin ksh kt latex less markdown math md mjs mysql node patch plain postgres postgresql properties py python python3 render render-css render-html render-svg rs rust sass scala scss sh shell sql sqlite styl svg swift text text-plain toml ts tsx txt typescript vue xhtml xml yaml yml zsh`

记忆口径：

- 渲染型：`svg css html render render-svg render-css render-html`
- 显示型：`text plain txt text-plain math latex md markdown`
- 高亮语言 + 别名：其余全部（68 个）

**自己命名一律加前缀**：`tb-tip`、`lab-note`、`my-warn`、`x-faq`。

---

## 8. 静默行为总表（不报错，但和你以为的不一样）

| 行为 | 说明 |
|---|---|
| 未知键 | 忽略（顶层/子项都是） |
| `meta` 类型不对 | 忽略 |
| `name` > 60 / `version` > 20 | 截断 |
| `label` > 40 / `text` > 500 | 截断 |
| 按钮第 7 个开始 | **报错**（不是截断） |
| 围栏撞内置 | 告警 + 跳过该条 |
| `uiInjection.location` 非 toolbar | 告警 + 跳过该条 |
| inline 项里的 `flags` | 忽略（固定 `g`） |
| block 项里的 `pattern` | 忽略 |
| inline 模板里的 `$content` | 原样输出（不替换） |
| `$N` 超出捕获组数 | inline：空串；preProcess：按 JS 规则（`$1` 组不存在则原样保留） |
| CSS 里 `@import` / 外链 `url()` | 删除 / 换成 `none` |
| 模板骨架里的 `<script>` / `on*` / `<svg>` | 删除 |
| 围栏 info 的多余 token | 丢弃（只取第一个词） |

---

## 9. 错误码 → 状态行文案（中文界面）

| code | 状态行（已整体禁用） | detail |
|---|---|---|
| `json` | `扩展加载失败：JSON 格式不对：…` | `JSON.parse` 的报错原文 |
| `regex` | `扩展加载失败：正则无效：…` | 原始 pattern |
| `size` | `扩展加载失败：扩展 JSON 太大（最多 200000 字符）` | `200000` |
| `root` | `扩展加载失败：扩展 JSON 的最外层必须是一个对象` | — |
| `contentMissing` | `扩展加载失败：围栏 X 的模板里要写 $content（正文插在哪）` | fence 名 |
| `unsafeTemplate` | `扩展加载失败：模板里的 X 不能裸插进标签（要放在标签外，或引号包住的属性值里）` | `$content` 或 `$N` |
| `field` | `扩展加载失败：扩展字段不对：…` | 字段路径，如 `customSyntax[0].fence` |
| 其他 | `扩展加载失败：扩展结构不对：…` | — |

告警（状态行里 `已启用：… ·` 之后）：

| code | 文案 |
|---|---|
| `fenceConflict` | `语法名 X 与内置围栏冲突，已跳过` |
| `uiLocation` | `界面注入只支持 location:"toolbar"，已跳过` |
| `backtrack` | `这条正则可能有灾难性回溯，建议改写：…` |

> 接口语言有 7 种，文案会翻译；**错误码/字段路径不变**。用户贴来的是英文/日文报错时，按字段路径定位即可。

---

## 10. 最小合法样例

```json
{}
```

```json
{ "customSyntax": [ { "type": "block", "fence": "tip", "replacement": "<div class=\"ext-tip\">$content</div>" } ] }
```

```json
{ "meta": { "name": "空规则", "version": "1.0" }, "preProcess": [], "customSyntax": [], "uiInjection": [] }
```
