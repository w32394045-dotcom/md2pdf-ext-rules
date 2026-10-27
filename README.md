# md2pdf-ext-rules — teach an AI to write md2pdf extension JSON

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/type-agent%20skill-9cf)](SKILL.md)

**English** · [简体中文](README.zh-CN.md)

A **Skill** — instructions for an AI agent, plus a linter — that solves one narrow thing:
writing the **extension JSON** of [md2pdf](https://github.com/w32394045-dotcom/md2pdf),
the block you paste under *⚙️ Settings → Smart extensions → Custom extension*.

That JSON can, without touching the tool:

| JSON field | You get |
|---|---|
| `preProcess` | regex replacement over the whole document before parsing |
| `customSyntax` · `type:"inline"` | your own inline syntax (`[[tag:重点]]` → a coloured tag) |
| `customSyntax` · `type:"block"` | your own fenced block (```` ```tip ```` → a styled card) |
| `cssInjection` | document CSS, shared by preview / print / exported HTML |
| `uiInjection` | a toolbar button that inserts a text snippet at the cursor |

> Without this Skill, models write JSON that *looks* fine and then one of these happens:
> the whole extension is disabled because a single field is wrong; the fence is silently skipped
> because it collides with a built-in language name; `$content` lands inside a tag and is rejected;
> `\d` was written with one backslash and the JSON is invalid; a literal `$` in a `preProcess`
> replacement duplicates the entire document; `body{…}` in `cssInjection` wrecks the tool's own UI;
> or the rule was simply misspelled (`customsyntax`) and silently ignored.

**Can't be bothered to install it?** Option 1 under *Install* has a prompt you can paste
straight into your agent (Claude Code / Codex / DSH / Cursor). It downloads, installs and
verifies itself.

## What's inside

```text
SKILL.md                                 main instructions: field rules, hard constraints, recipes,
                                         troubleshooting table, pre-delivery checklist
references/schema-reference.md           every field: type, limit, validation order, error code,
                                         silent behaviours, the 80 reserved fence names
references/patterns-and-replacements.md  the two different `$` semantics, regex constraints,
                                         tested patterns, anti-patterns
references/css-and-security.md           where the CSS layer sits, tool CSS variables, print rules,
                                         what the HTML/CSS sanitizers strip, safe styling recipes
scripts/check_ext.py                     pre-delivery linter (stdlib only, no dependencies)
scripts/selftest.py                      runs the linter over examples/ and checks expectations
examples/ok-*.json                       three positive examples (minimal / full / typography)
examples/bad-*.json                      sixteen deliberate mistakes, each with a known outcome
examples/demo-teaching-pack.md           a Markdown file that uses the full example's syntax
examples/expect.json                     expected verdict of every example file
```

The examples are kept in Chinese on purpose (they double as fixtures for the Chinese README);
the linter's rules are language-agnostic.

## Install

First, a clarification: **this repo is a Skill** — instructions for an AI, plus a checker script.
The thing that does the work is [md2pdf](https://github.com/w32394045-dotcom/md2pdf) (one HTML file).
Installing the skill just tells the AI the rules of that JSON. Three routes; pick whatever fits.

### Option 1 — paste this into your AI agent (easiest)

Works with any agent that supports skills: Claude Code, Codex, DeepSeek Harness, Cursor, Gemini CLI…
**Copy the whole block below.** It downloads the repo, puts it in the right place, and verifies the result.

```text
Please install a skill for me: md2pdf-ext-rules.

Source repository: https://github.com/w32394045-dotcom/md2pdf-ext-rules
What it is: an instruction file for AI agents (SKILL.md) + references (three markdown files in
references/) + a linter (scripts/check_ext.py). It teaches an AI to write the extension JSON of
md2pdf (the JSON pasted under Settings → Smart extensions → Custom extension: preProcess,
customSyntax inline/block, cssInjection, uiInjection).

Please do the following, in order:

1. Download the repository to this machine, keeping the directory name md2pdf-ext-rules, and make
   sure SKILL.md exists inside it.
   Suggested command: git clone --depth 1 https://github.com/w32394045-dotcom/md2pdf-ext-rules.git
   (If git is unavailable, download the zip and extract it — keep the directory name.)

2. Move that whole directory into my skills root, choosing the one that matches your client:
   - DeepSeek Harness / generic: ~/.dsh/skills/md2pdf-ext-rules/
   - Claude Code style: ~/.claude/skills/md2pdf-ext-rules/
   - This project only: <project root>/.dsh/skills/md2pdf-ext-rules/
   If you have a skill_install / skill tool, prefer it — but copy references/, scripts/ and
   examples/ along with SKILL.md. Do not install it as a single flat markdown file.

3. After installing, verify three things and report the results to me:
   a) md2pdf-ext-rules shows up in your skill list and is valid;
   b) the directory contains SKILL.md, references/ (three .md files), scripts/check_ext.py and
      examples/;
   c) running `python scripts/check_ext.py examples/ok-teaching-pack.json` prints a report
      (expect 0 errors, exit 0), and running it on examples/bad-content-in-attr.json reports
      an error (exit 1).

4. If any step fails, tell me exactly where: path missing, permission denied, client doesn't
   support skills, or only single-file install works — and give me the fallback (at minimum,
   let me paste SKILL.md as a system prompt).

Constraints: do not edit SKILL.md; do not change the linter's logic; do not mix these files into
my other skill directories.
```

### Option 2 — do it manually (one command)

```bash
git clone --depth 1 https://github.com/w32394045-dotcom/md2pdf-ext-rules.git
cp -r md2pdf-ext-rules ~/.dsh/skills/        # DeepSeek Harness (user scope)
cp -r md2pdf-ext-rules ~/.claude/skills/     # Claude Code style
cp -r md2pdf-ext-rules ./.dsh/skills/        # this project only
```

With a skill installer tool:

```text
skill_install source=<path to this repo> scope=user
```

> ⚠️ Two traps: **don't copy only SKILL.md** (lose `references/` and `scripts/`), and **don't
> install it as a flat file** (`skills/md2pdf-ext-rules.md` loses the same things). Paths inside
> SKILL.md are relative to the skill directory.

### Option 3 — your AI has no skill mechanism (web ChatGPT / Kimi / Doubao / Tongyi …)

Don't install anything; hand the content over:

**3.1 Send the file** — attach `SKILL.md` (or the whole zip) and say:

```text
This is a writing spec for AI (a Skill). Read the SKILL.md inside.
From now on, whenever you write or fix md2pdf extension JSON (preProcess / customSyntax /
cssInjection / uiInjection), follow it strictly: JSON must stay valid, `$content` only outside
tags, `$N` only outside tags or inside quoted attributes, fence names must not collide with
built-ins, CSS only namespaced classes, and run the checklist before handing anything back.
```

**3.2 Paste the content** — copy `SKILL.md` into the chat or into *custom instructions /
project knowledge*. When you hit regex or CSS problems, paste the matching reference too:

| File | Covers |
|---|---|
| `references/schema-reference.md` | every field, limit, error code, silent behaviour |
| `references/patterns-and-replacements.md` | regex patterns, the two `$` semantics, anti-patterns |
| `references/css-and-security.md` | CSS layer, print rules, what gets sanitized |

**3.3 One-line version**

```text
When writing md2pdf extension JSON: a single field error disables the whole extension, so keep the
structure exact (meta / preProcess / customSyntax / uiInjection / cssInjection); block fences need
`$content` outside any tag; inline templates may use $1…$9 only outside tags or inside quoted
attributes; fence names must not collide with built-in languages (svg, html, js, json, text, math…);
preProcess replacements use JS `$` syntax (write $$ for a literal $, never $` or $'); CSS must be
namespaced (.ext-*) because it is page-wide; and always validate before delivering.
```

Expect **80–90% of the benefit**. The cost: it does not trigger automatically, it eats context
(SKILL.md ≈ 26 KB), and long attachments may be truncated.

### Verify it actually works

```bash
# 1. files are there
ls ~/.dsh/skills/md2pdf-ext-rules/
#    expect: SKILL.md  references/  scripts/  examples/

# 2. the linter runs
python ~/.dsh/skills/md2pdf-ext-rules/scripts/check_ext.py \
       ~/.dsh/skills/md2pdf-ext-rules/examples/ok-teaching-pack.json
#    expect: 0 errors, exit 0

# 3. self-test over all examples (expects every bad-*.json to be caught)
python ~/.dsh/skills/md2pdf-ext-rules/scripts/selftest.py

# 4. ask the AI a test question — a correct answer shows the spec loaded:
#    "Write an md2pdf extension that adds a ```tip block and a [[tag:…]] inline marker"
#    good sign: fence name namespaced (tb-tip), $content outside tags, .ext-* CSS,
#               and it tells you to press "应用扩展" and watch the status line
```

### Update / uninstall

```bash
cd md2pdf-ext-rules && git pull          # update
rm -rf ~/.dsh/skills/md2pdf-ext-rules    # uninstall (just delete the directory)
```

## The linter

```bash
python scripts/check_ext.py rules.json             # one file
python scripts/check_ext.py examples/*.json        # several
python scripts/check_ext.py --strict rules.json    # warnings count as failures (CI-friendly)
python scripts/check_ext.py --json rules.json      # machine-readable, one JSON object
```

Exit codes: `0` clean / warnings only, `1` errors (or warnings under `--strict`), `2` usage.

It checks:

- JSON validity, root type, the 200 000-character budget
- every field's type, limit and illegal value, reported with the same field path the tool uses
  (`customSyntax[0].fence`, `preProcess[0].flags`, …)
- regex compilation, and whether every `$N` in a template stays within the pattern's capture groups
- `$content` missing, or placed inside any tag
- `$N` interpolations placed inside a tag but not inside a quoted attribute
- fence names colliding with the 80 reserved names, duplicate fences, illegal fence names
- `$` traps in `preProcess` replacements (`` $` ``, `$'`, out-of-range `$N`)
- a missing `g` flag (only the first match gets replaced)
- page-wide CSS selectors (`body`, `html`, `*`, `.toolbar` …) and CSS that gets stripped
  (`@import`, external `url()`, `expression()`, `behavior`)
- `on*` attributes, `<script>`/`<svg>`/`<iframe>` and `javascript:` in templates
- silent truncation (name > 60, version > 20, label > 40, text > 500), unknown keys, > 6 buttons
- catastrophic-backtracking patterns and rules that match the empty string

Severity is split honestly: **error** = md2pdf will disable the whole extension;
**warn** = it loads but something is silently skipped, truncated or generated wrongly;
**hint** = style advice.

Real output for `examples/bad-content-in-attr.json` (exit 1 — the whole extension would be disabled):

```text
========================================================================
扩展规则：examples/bad-content-in-attr.json
  [error] unsafeTemplate     customSyntax[0].replacement 模板里的 $content 落在 HTML 标签里（哪怕在引号属性值里也不行），正文 HTML 会破坏标签结构 → 整份禁用
------------------------------------------------------------------------
小计：1 error, 0 warn, 0 hint

合计 1 个文件：1 error, 0 warn, 0 hint
[FAIL] 有 1 处 error：md2pdf 会整份禁用扩展，先修完再用。
```

And `examples/bad-truncate.json` (exit 0 — it loads fine, but four fields are silently cut):

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

(The report text is Chinese, like the tool's own UI; `--json` gives the same data as one JSON object.)

Optional extra — catch "valid but never triggers":

```bash
python scripts/check_ext.py --doc lecture.md rules.json
```

With `--doc`, every `preProcess`/inline `pattern` is run against that sample document, and every
defined fence is looked up in it. A rule that never matches is reported as
`pattern-unmatched` / `fence-unused` — the one class of mistake the tool itself cannot tell you about.

> The linter is a faithful re-implementation, but the validator **inside** md2pdf is the authority.
> If they ever disagree, the tool's status line wins — and the linter's messages say which of the
> two situations you are in.

## Examples

| File | Shows |
|---|---|
| `examples/ok-minimal-tip.json` | the smallest useful extension: one fence + one CSS rule |
| `examples/ok-teaching-pack.json` | full set: preProcess, 2 inline rules, 3 card fences, toolbar button, themed CSS |
| `examples/ok-typography.json` | global punctuation cleanup + inline colour tag + question-number badge |
| `examples/bad-json-syntax.json` | trailing comma → `JSON 格式不对` |
| `examples/bad-null-field.json` | `"cssInjection": null` → `扩展字段不对` |
| `examples/bad-content-missing.json` | block template without `$content` → `contentMissing` |
| `examples/bad-content-in-attr.json` | `$content` inside `class="…"` → `unsafeTemplate` |
| `examples/bad-inline-bare-attr.json` | `$1` as an unquoted attribute → `unsafeTemplate` |
| `examples/bad-fence-duplicate.json` | two rules with the same fence → `field` |
| `examples/bad-ui-action.json` | `action:"insert"` → `field` |
| `examples/bad-fence-reserved.json` | fence named `html` → loads, but that rule is skipped (warning) |
| `examples/bad-backtrack.json` | `(a+)+` → catastrophic-backtracking warning |
| `examples/bad-css-global.json` | `body`/`html`/`*` selectors, `@import`, external `url()` |
| `examples/bad-dollar-traps.json` | `` $` `` and `$'` in a replacement (prefix/suffix of the document) |
| `examples/bad-no-g.json` | `preProcess` without `g` → only the first match is replaced |
| `examples/bad-inline-dollar-group.json` | `$2` with a single capture group → empty output |
| `examples/bad-truncate.json` | over-long name/label/text → silently truncated |
| `examples/bad-unknown-field.json` | `customsyntax` typo → silently ignored |

Run `python scripts/selftest.py` to check all of them at once.

## What extensions cannot do

| Wanted | Reality |
|---|---|
| Pass parameters into a fence (e.g. `tip title="x"`) | The info string after the first word is discarded — define another fence instead |
| Custom syntax that produces block-level markup | Inline rules live inside a paragraph; use a block fence |
| Toolbar buttons that do something (call a function, open a dialog) | Only `insertText` |
| Scripts, event handlers, remote resources in templates/CSS | Stripped by the sanitizers; the tool is deliberately offline |
| Per-document rules (travel with the `.md`) | The JSON lives in the tool's local settings; ship it as a `.json` file |
| Override paper size / margins / fonts from the extension | Use the tool's settings; the extension only adds markup, styles and buttons |

## How the tool side works (short)

1. Paste the JSON under *⚙️ → Smart extensions → Custom extension* → **Apply extension**.
2. The status line says `已启用：name (1.0)` on success, or `扩展加载失败：…（已整体禁用）` with the
   offending field on failure. Warnings (skipped fence, backtracking regex) are appended.
3. The JSON is stored in the browser's local database (`kv → extJson`), so it survives reloads but
   not a different browser or cleared site data. Export it via *Data & fonts → Export settings*, or
   keep a `.json` file.
4. Preview, print/PDF and exported HTML all use the same rules and CSS layer.

## How it was verified

- **Linter vs the real validator.** 199 generated rule files — valid ones plus malformed ones (bad JSON, wrong
  types, `null` fields, illegal / duplicate / reserved fences, `$content` inside tags, bare `$N`, oversize
  JSON, bad `flags`, UI limits, CSS that gets stripped, weird regexes) — were run through both md2pdf's own
  `extValidate()` (in Node, sliced out of `md2pdf.html`) and `check_ext.py`. Result: **0 mismatches** — same
  pass/fail verdict, same error code, same field path, and every warning the tool emits (skipped fence,
  backtracking regex, ignored UI location) is also emitted.
- **Examples.** `scripts/selftest.py` asserts that every `examples/bad-*.json` fails with exactly the error code
  the real validator gives, and every `examples/ok-*.json` loads clean: **18/18**.
- **Docs don't lie.** The complete JSON snippets embedded in `SKILL.md` and `references/schema-reference.md` are
  themselves fed through `extValidate()`.
- **The instructions were tested blind.** An agent that had *only* `SKILL.md` + `references/` (no examples, no
  scripts, and forbidden from reading the tool source) was asked for four extensions: an inline tag plus a card
  fence, an inline "card" behind a custom delimiter, a toolbar button plus a tag in a document that contains a
  `js` code block, and a fix for an `unsafeTemplate` error. All four loaded in the real validator with **zero
  warnings**; rendering produced the cards and tags and left the code block untouched.
- **Not covered by machine:** the browser click path, the print dialog, background printing, and how it looks on
  paper — those need human eyes. That is also why SKILL.md keeps repeating "check the status line after Apply".

The parity harness is a development artifact (it needs `md2pdf.html`), so it is not shipped in this repo.

## Related

- **[md2pdf](https://github.com/w32394045-dotcom/md2pdf)** — the tool itself (single file, offline,
  LaTeX/MathML, render fences). Primary site: https://md2pdf.xszx.cc.cd
- **[md2pdf-authoring](https://github.com/w32394045-dotcom/md2pdf-authoring)** — the companion Skill
  that teaches an AI to *use* the tool and to write Markdown that survives rendering/printing.

## Licence

[MIT](LICENSE) © 2026 w32394045-dotcom

Use it, change it, redistribute it — keep the copyright notice. No warranty.
