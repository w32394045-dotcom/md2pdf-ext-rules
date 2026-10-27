# md2pdf-ext-rules — 教 AI 写对 md2pdf 的扩展 JSON

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/type-agent%20skill-9cf)](SKILL.md)

[English](README.md) · **简体中文**

一个 **Skill**（给 AI 读的说明书 + 自检脚本），只解决一件事：
[md2pdf](https://github.com/w32394045-dotcom/md2pdf) 里那段**扩展 JSON** 怎么写。
就是「⚙️ 设置 → 智能扩展 → 自定义扩展」里粘进去的那段。

那段 JSON 不用改工具，就能做到：

| JSON 字段 | 得到什么 |
|---|---|
| `preProcess` | 解析前对全文做正则替换 |
| `customSyntax` · `type:"inline"` | 自定义行内语法（`[[t:重点]]` → 一个彩色小标签） |
| `customSyntax` · `type:"block"` | 自定义围栏（```` ```tip ```` → 一张样式卡片） |
| `cssInjection` | 文档样式，预览 / 打印 / 导出 HTML 三处共用 |
| `uiInjection` | 顶栏按钮，在光标处插入一段文字 |

> 没有这个 Skill，模型写出来的 JSON 往往「看着没毛病」，然后：**一处字段错就整份禁用**；
> 围栏名撞上内置语言（`html`、`js`、`note` 之外的 `text`…）被**静默跳过**；
> `$content` 落进标签里直接被拒；`\d` 只写一个反斜杠，JSON 本身就不合法；
> 替换串里的 `$` 把整篇文档复制了一遍；`cssInjection` 写了 `body{…}`，把工具界面改花；
> 或者键名打成 `customsyntax`，安安静静什么都没发生。

**懒得装？** 下面「安装 → 方式一」有一段现成的提示词，整段复制给你的 AI agent
（Claude Code / Codex / DSH / Cursor 都行），它自己下载、放好位置、装完还会自检。

## 目录结构

```text
SKILL.md                                 主文档：字段硬规范、四类规则写法、配方、故障对照表、交付前清单
references/schema-reference.md           每个字段的类型/上限/校验顺序/错误码，静默行为，80 个保留围栏名
references/patterns-and-replacements.md  两套 `$` 语义、正则约束、实测配方、反例
references/css-and-security.md           样式层位置、工具变量、打印要点、HTML/CSS 净化边界、样式配方
scripts/check_ext.py                     交付前自检脚本（纯标准库，零依赖）
scripts/selftest.py                      拿 examples/ 跑一遍自检，断言每个反例都被逮住
examples/ok-*.json                       三个正面例子（最小 / 完整 / 标点排版）
examples/bad-*.json                      十六个故意的错误，各自有明确结果
examples/demo-teaching-pack.md           配合「完整例子」使用的演示文档
examples/expect.json                     每个例子的期望结果
```

> 示例文件故意用中文写：它们同时是中文 README 的配图；自检规则本身与语言无关。

## 安装

先说清楚：**这个仓库是 Skill**——给 AI 的规则 + 一个检查脚本；干活的是
[md2pdf](https://github.com/w32394045-dotcom/md2pdf)（一个 HTML 文件）。
装 Skill 只是让 AI 知道那段 JSON 的规矩。三种方式，挑顺手的。

### 方式一 — 把这段丢给你的 AI agent（最省事）

支持 Skill 的客户端都行：Claude Code、Codex、DeepSeek Harness、Cursor、Gemini CLI……
**整段复制下面这块**，它会下载仓库、放到正确位置、装完自检。

```text
请帮我安装一个 skill：md2pdf-ext-rules。

来源仓库：https://github.com/w32394045-dotcom/md2pdf-ext-rules
它是什么：给 AI agent 读的说明书（SKILL.md）+ 参考资料（references/ 下三个 markdown）
+ 自检脚本（scripts/check_ext.py）。它教 AI 写 md2pdf 的扩展 JSON——就是「设置 → 智能扩展 →
自定义扩展」里粘贴的那段：preProcess、customSyntax（inline/block）、cssInjection、uiInjection。

请按顺序做：

1. 把仓库下载到本机，目录名保持 md2pdf-ext-rules，确认里面有 SKILL.md。
   建议命令：git clone --depth 1 https://github.com/w32394045-dotcom/md2pdf-ext-rules.git
   （没有 git 就下载 zip 解压，目录名别改。）

2. 把整个目录放进我的 skills 根目录（按你的客户端选一个）：
   - DeepSeek Harness / 通用：~/.dsh/skills/md2pdf-ext-rules/
   - Claude Code 风格：~/.claude/skills/md2pdf-ext-rules/
   - 只给当前项目用：<项目根>/.dsh/skills/md2pdf-ext-rules/
   有 skill_install / skill 工具就优先用它——但 references/、scripts/、examples/ 要和
   SKILL.md 一起装过去。不要只装成一个单文件 markdown。

3. 装完验证三件事并汇报：
   a) md2pdf-ext-rules 出现在 skill 列表里且校验通过；
   b) 目录里有 SKILL.md、references/（三个 .md）、scripts/check_ext.py、examples/；
   c) 运行 `python scripts/check_ext.py examples/ok-teaching-pack.json` 有报告
      （应为 0 error、退出码 0）；再运行 examples/bad-content-in-attr.json，应报 error（退出码 1）。

4. 任何一步失败，告诉我卡在哪：路径不存在、没有权限、客户端不支持 Skill、还是只能单文件安装——
   并给我退路（至少允许我把 SKILL.md 当系统提示词粘进去）。

约束：不要改 SKILL.md；不要改自检脚本的逻辑；不要把这些文件混进我别的 skill 目录。
```

### 方式二 — 自己动手（一条命令）

```bash
git clone --depth 1 https://github.com/w32394045-dotcom/md2pdf-ext-rules.git
cp -r md2pdf-ext-rules ~/.dsh/skills/        # DeepSeek Harness（用户级）
cp -r md2pdf-ext-rules ~/.claude/skills/     # Claude Code 风格
cp -r md2pdf-ext-rules ./.dsh/skills/        # 只给当前项目
```

有 skill 安装工具的话：

```text
skill_install source=<这个仓库的路径> scope=user
```

> ⚠️ 两个坑：**别只拷 SKILL.md**（会丢 `references/` 和 `scripts/`），
> **别装成一个平铺的 .md 文件**（`skills/md2pdf-ext-rules.md` 一样会丢）。
> SKILL.md 里的路径都是相对 skill 目录的。

### 方式三 — 你的 AI 没有 Skill 机制（网页版 ChatGPT / Kimi / 豆包 / 通义…）

那就别装，直接把内容交给它。

**3.1 把文件丢进去**——附件发 `SKILL.md`（或整个 zip），然后说：

```text
这是一份给 AI 看的写作规范（Skill）。读里面的 SKILL.md。
以后凡是写或修 md2pdf 的扩展 JSON（preProcess / customSyntax / cssInjection / uiInjection），
严格照它来：JSON 必须合法；$content 只能放标签外；$N 只能放标签外或引号属性里；
围栏名不能撞内置；CSS 只写命名空间类；交付前按它的清单自查。
```

**3.2 把内容粘进去**——把 `SKILL.md` 整段贴进对话，或存到「自定义指令 / 项目知识」里。
遇到正则或样式问题时，再把对应的参考文件贴进来：

| 文件 | 管什么 |
|---|---|
| `references/schema-reference.md` | 每个字段、上限、错误码、静默行为 |
| `references/patterns-and-replacements.md` | 正则写法、两套 `$` 语义、反例 |
| `references/css-and-security.md` | 样式层、打印规则、哪些会被过滤 |

**3.3 一句话版**

```text
写 md2pdf 扩展 JSON 时：任何一个字段错都会导致整份扩展禁用，所以结构必须精确
（meta / preProcess / customSyntax / uiInjection / cssInjection）；block 围栏的 $content 必须
在标签外；inline 模板的 $1…$9 只能在标签外或引号属性里；围栏名不能撞内置语言（svg、html、js、
json、text、math…）；preProcess 的替换串是 JS 的 $ 语义（字面 $ 要写 $$，绝不能写 $` 或 $'）；
CSS 是整页生效的，必须用 .ext-* 命名空间；交付前一定先校验。
```

大概能拿到 **80–90%** 的效果。代价：不会自动触发（要提醒它，或者明说「按 md2pdf 扩展规范写」）、
吃上下文（SKILL.md 约 26 KB）、长附件可能被截断或只进索引。

### 验证真的能用

```bash
# 1. 文件在不在
ls ~/.dsh/skills/md2pdf-ext-rules/
#    应有：SKILL.md  references/  scripts/  examples/

# 2. 自检脚本能跑
python ~/.dsh/skills/md2pdf-ext-rules/scripts/check_ext.py \
       ~/.dsh/skills/md2pdf-ext-rules/examples/ok-teaching-pack.json
#    应为 0 error、退出码 0

# 3. 所有示例跑一遍（每个 bad-*.json 都应该被逮住）
python ~/.dsh/skills/md2pdf-ext-rules/scripts/selftest.py

# 4. 问 AI 一个测试问题——答对了说明规范加载成功：
#    「写一个 md2pdf 扩展，加一个 ```tip 块和一个 [[tag:…]] 行内标记」
#    好答案的特征：围栏名带前缀（tb-tip）、$content 在标签外、CSS 用 .ext-*，
#                  并且告诉你点「应用扩展」后看状态行
```

### 更新 / 卸载

```bash
cd md2pdf-ext-rules && git pull          # 更新
rm -rf ~/.dsh/skills/md2pdf-ext-rules    # 卸载（删目录即可）
```

## 自检脚本

```bash
python scripts/check_ext.py 规则.json             # 一个文件
python scripts/check_ext.py examples/*.json       # 多个
python scripts/check_ext.py --strict 规则.json    # warn 也算失败（接 CI）
python scripts/check_ext.py --json 规则.json      # 机器可读，便于脚本断言
```

退出码：`0` 干净或只有告警；`1` 有 error（`--strict` 下有 warn 也算）；`2` 用法错误。

它会查：

- JSON 是否合法、顶层是不是对象、是否超过 20 万字符
- 每个字段的类型/上限/非法值，报错路径和工具一致（`customSyntax[0].fence`、`preProcess[0].flags`…）
- 正则能否编译；模板里的每个 `$N` 是否超出捕获组数
- `$content` 是否缺失、是否落进任何标签
- `$N` 是否裸插进标签（没在引号属性里）
- 围栏名是否撞 80 个内置名、是否重名、是否合法
- `preProcess` 替换串里的 `$` 陷阱（`` $` ``、`$'`、越界 `$N`）
- 是否漏了 `g`（只替换第一处）
- 样式里的整页选择器（`body`、`html`、`*`、`.toolbar`…）和会被吃掉的写法
  （`@import`、外链 `url()`、`expression()`、`behavior`）
- 模板里的 `on*`、`<script>`/`<svg>`/`<iframe>`、`javascript:`
- 静默截断（name>60、version>20、label>40、text>500）、未知键、按钮超过 6 个
- 灾难性回溯的嵌套量词、能匹配空串的规则

分级是诚实的：**error** = md2pdf 会整份禁用；**warn** = 能加载但会被静默跳过/截断/生成错；
**hint** = 风格建议。

`examples/bad-content-in-attr.json` 的真实输出（退出码 1 —— 这一条会让整份扩展被禁用）：

```text
========================================================================
扩展规则：examples/bad-content-in-attr.json
  [error] unsafeTemplate     customSyntax[0].replacement 模板里的 $content 落在 HTML 标签里（哪怕在引号属性值里也不行），正文 HTML 会破坏标签结构 → 整份禁用
------------------------------------------------------------------------
小计：1 error, 0 warn, 0 hint

合计 1 个文件：1 error, 0 warn, 0 hint
[FAIL] 有 1 处 error：md2pdf 会整份禁用扩展，先修完再用。
```

`examples/bad-truncate.json`（退出码 0 —— 能加载，但四个字段被静默截断）：

```text
扩展规则：examples/bad-truncate.json
  [warn ] truncate           meta.name            meta.name 有 64 个字符（64 个 UTF-16 码元），超过 60 会被静默截断
  [warn ] truncate           meta.version         meta.version 有 33 个字符，超过 20 会被静默截断
  [warn ] truncate           uiInjection[0].label label 有 44 个字符，超过 40 会被静默截断
  [warn ] truncate           uiInjection[0].text  text 有 520 个字符，超过 500 会被静默截断（插入内容会缺尾巴）
------------------------------------------------------------------------
小计：0 error, 4 warn, 0 hint
[OK] 没有 error。
```

可选的进阶用法——抓「规则合法但根本不会触发」：

```bash
python scripts/check_ext.py --doc 讲义.md 规则.json
```

给了 `--doc`，脚本会拿这篇样本文档去跑每一条 `preProcess` / 行内 `pattern`，并在文档里找每个
定义过的围栏。一次都没命中就报 `pattern-unmatched` / `fence-unused`——这是工具自己发现不了的一类错。

> 脚本是照着工具里的校验器复刻的，但**工具里的那份才是权威**。万一不一致，以 md2pdf 的状态行为准——
> 脚本的提示里会明确区分「一定失败」和「能加载但会变形」。

## 示例

| 文件 | 演示什么 |
|---|---|
| `examples/ok-minimal-tip.json` | 最小可用扩展：一个围栏 + 一条样式 |
| `examples/ok-teaching-pack.json` | 全套：预处理 + 2 条行内 + 3 种卡片围栏 + 顶栏按钮 + 主题色样式 |
| `examples/ok-typography.json` | 全局标点整理 + 行内颜色标签 + 题号徽章 |
| `examples/bad-json-syntax.json` | 尾逗号 → `JSON 格式不对` |
| `examples/bad-null-field.json` | `"cssInjection": null` → `扩展字段不对` |
| `examples/bad-content-missing.json` | 围栏模板没有 `$content` → `contentMissing` |
| `examples/bad-content-in-attr.json` | `$content` 写进 `class="…"` → `unsafeTemplate` |
| `examples/bad-inline-bare-attr.json` | `$1` 当裸属性 → `unsafeTemplate` |
| `examples/bad-fence-duplicate.json` | 两个规则用同一个围栏 → `field` |
| `examples/bad-ui-action.json` | `action:"insert"` → `field` |
| `examples/bad-fence-reserved.json` | 围栏名 `html` → 能加载，但这条被跳过（告警） |
| `examples/bad-backtrack.json` | `(a+)+` → 灾难性回溯告警 |
| `examples/bad-css-global.json` | `body`/`html`/`*` 选择器、`@import`、外链 `url()` |
| `examples/bad-dollar-traps.json` | 替换串里的 `` $` `` / `$'`（会插入整篇前后文） |
| `examples/bad-no-g.json` | `preProcess` 没写 `g` → 只替换第一处 |
| `examples/bad-inline-dollar-group.json` | 只有 1 个捕获组却写 `$2` → 输出空 |
| `examples/bad-truncate.json` | name/label/text 过长 → 静默截断 |
| `examples/bad-unknown-field.json` | `customsyntax` 拼错 → 静默忽略 |

一次跑完：`python scripts/selftest.py`。

## 扩展做不到的事

| 想要 | 现实 |
|---|---|
| 给围栏传参（比如 tip title="x"） | info 串只取第一个词，后面的丢弃——定义另一个围栏 |
| 行内规则输出块级结构 | 行内规则在段落内部，块级请用围栏 |
| 顶栏按钮执行操作（调函数、开弹窗） | 只支持 `insertText` |
| 模板/样式里跑脚本、加载远程资源 | 会被净化掉；工具刻意离线 |
| 规则跟着 `.md` 走（每个文档一套） | JSON 存在工具的本地设置里，要带走就发 `.json` 文件 |
| 用扩展改纸张/边距/字体 | 那是设置里的东西；扩展只加标记、样式、按钮 |

## 工具那边怎么用（简版）

1. 「⚙️ → 智能扩展 → 自定义扩展」粘 JSON → **应用扩展**。
2. 状态行成功显示 `已启用：名称（1.0）`；失败显示 `扩展加载失败：…（已整体禁用）` 并指出字段；
   被跳过的围栏、可疑正则作为告警接在后面。
3. JSON 存在浏览器本地数据库（`kv → extJson`），刷新还在，换浏览器/清站点数据会丢；
   要留存用「数据与字体 → 导出设置」，或自己存 `.json`。
4. 预览、打印/PDF、导出 HTML 三处用的是同一套规则和同一样式层。

## 怎么确认它靠谱

- **自检脚本 vs 工具内置校验器**：用 199 份规则文件（合法的 + 各种畸形的：坏 JSON、类型错、`null` 字段、
  非法/重名/撞内置的围栏、`$content` 进标签、裸 `$N`、超长 JSON、坏 flags、按钮超限、会被吃掉的 CSS、
  各种怪正则……）分别跑 md2pdf 自己的 `extValidate()`（从 `md2pdf.html` 里切出来在 Node 里跑）和
  `check_ext.py`。结果：**0 处不一致**——判定一致、错误码一致、字段路径一致，工具会报的告警
  （跳过围栏 / 回溯 / 忽略注入位置）也都有。
- **示例**：`scripts/selftest.py` 要求每个 `examples/bad-*.json` 都报出和真实校验器**完全相同的错误码**，
  每个 `ok-*.json` 都能干净加载：**18/18**。
- **文档不撒谎**：`SKILL.md` 和 `references/schema-reference.md` 里贴出的完整 JSON 片段，本身也会过一遍
  `extValidate()`。
- **说明书做过盲测**：只给一个 agent `SKILL.md` + `references/`（不给 examples、不给 scripts、禁止读工具源码），
  让它写四份扩展——行内标记 + 卡片围栏、自定义定界符的行内「小卡片」、顶栏按钮 + 标签（文档里还有 js 代码块）、
  修一个 `unsafeTemplate` 报错。四份全部通过真实校验器且**零告警**；渲染出来卡片和标签都在，代码块没被动。
- **机器测不到的**：浏览器里的点击路径、打印对话框、背景打印、纸上实际效果——这些得人点一遍。
  这也是 SKILL.md 里一直强调「点『应用扩展』后看状态行」的原因。

对拍脚本是开发期工具（需要 `md2pdf.html`），不随这个仓库发布。

## 相关项目

- **[md2pdf](https://github.com/w32394045-dotcom/md2pdf)** — 工具本体（单文件、离线、LaTeX/MathML、
  渲染型围栏）。主站：https://md2pdf.xszx.cc.cd
- **[md2pdf-authoring](https://github.com/w32394045-dotcom/md2pdf-authoring)** — 配套 Skill，
  教 AI 正确**使用**这个工具、写出「渲染正确、打印不出血」的 Markdown。

## 许可

[MIT](LICENSE) © 2026 w32394045-dotcom

随便用、随便改、随便转，保留版权声明即可。不提供任何担保。
