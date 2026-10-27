#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2pdf 扩展 JSON 规则自检：先看它会不会被工具整份禁用，再看会不会静默失效。

用法:
    python check_ext.py 规则.json [更多.json ...]
    python check_ext.py --strict 规则.json        # warn 也算失败（接流水线用）
    python check_ext.py --json 规则.json          # 只输出一行机器可读 JSON（CI / 对拍用）
    python check_ext.py --doc 样本文档.md 规则.json
                                                 # 额外检查 pattern / 自定义围栏在样例里是否真的用上
    python check_ext.py --help

退出码:
    0 = 没有 error（--strict 下还要求没有 warn）
    1 = 有 error，或 --strict 下有 warn
    2 = 用法错误 / 没给文件 / 文件读不了

判据来自 md2pdf.html 里 MD-PARSER-START / MD-PARSER-END 之间的 extValidate()
与 cssSanitize()（JS 源码是唯一权威）。本脚本只做静态检查：不联网、不写文件、
纯标准库，Python 3.8+。

分级说明:
    error  md2pdf 会整份禁用扩展（size/json/root/field/regex/contentMissing/
           unsafeTemplate），或者 checker 能确定的结构错误
    warn   能加载，但会静默失效 / 静默变形 / 污染工具界面
    hint   风格建议，不影响加载
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------- 与 JS 对齐的常量

EXT_MAX_JSON = 200000      # JSON 文本上限（JS 字符串长度 = UTF-16 码元数）
EXT_MAX_PATTERN = 2000     # 单条正则上限
EXT_MAX_TPL = 4000         # 单条替换模板上限
EXT_MAX_UI = 6             # 顶栏最多注入几个按钮

# RENDER_LANGS（渲染型围栏）
RENDER_LANGS = ('svg', 'css', 'html', 'render',
                'render-svg', 'render-css', 'render-html')

# HL_ALIAS 的全部键（高亮语言别名）
HL_ALIAS_KEYS = (
    'js', 'javascript', 'jsx', 'mjs', 'cjs', 'node',
    'ts', 'typescript', 'tsx',
    'c', 'h', 'cpp', 'c++', 'cc', 'hpp', 'cs', 'csharp',
    'java', 'kotlin', 'kt', 'swift', 'go', 'golang',
    'rust', 'rs', 'dart', 'scala', 'groovy', 'gradle',
    'py', 'python', 'python3',
    'sh', 'bash', 'shell', 'zsh', 'console', 'fish', 'ksh',
    'html', 'htm', 'xml', 'svg', 'vue', 'xhtml',
    'css', 'scss', 'less', 'sass', 'styl',
    'json', 'jsonc', 'json5',
    'yaml', 'yml',
    'sql', 'mysql', 'postgres', 'postgresql', 'sqlite',
    'diff', 'patch',
    'ini', 'toml', 'conf', 'cfg', 'properties', 'env',
)

# 内置固定名 + 上面两类；'constructor' 是 JS 里 EXT_RESERVED 的原型链误伤：
# EXT_RESERVED['constructor'] 取到 Object 构造函数（真值），所以这个围栏名也会被跳过。
RESERVED_FENCES = (set(RENDER_LANGS) | set(HL_ALIAS_KEYS)
                   | set('text plain txt text-plain math latex md markdown'.split())
                   | {'constructor'})

TOP_KEYS = ('meta', 'preProcess', 'customSyntax', 'uiInjection', 'cssInjection')
META_KEYS = ('name', 'version')
PRE_KEYS = ('pattern', 'flags', 'replacement')
INLINE_KEYS = ('type', 'pattern', 'replacement', 'flags')
BLOCK_KEYS = ('type', 'fence', 'replacement')
UI_KEYS = ('location', 'action', 'label', 'text')

# 很常见的围栏名：现在没撞内置，以后工具加语言就可能撞，建议加前缀
COMMON_FENCES = set(
    'tip note warning warn info danger callout card box grid columns '
    'figure timeline steps details spoiler quote sample demo'.split()
)

ATTRIBUTION = '（JS 权威：md2pdf.html 的 extValidate）'

BAD_QUANT_RE = re.compile(r'\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)\s*[+*{]')
FLAGS_RE = re.compile(r'^[gimsuy]*$')
FENCE_RE = re.compile(r'^[a-z][a-z0-9_-]{0,30}$')

# sanitizeHtml 会处理的标签（第一个正则整段删，第二个删孤立标签）
SANITIZE_TAGS = ('script', 'style', 'iframe', 'object', 'embed', 'link', 'meta',
                 'base', 'form', 'input', 'button', 'textarea', 'select', 'svg', 'math')
SANITIZE_STRAY = tuple(t for t in SANITIZE_TAGS if t not in ('svg', 'math'))

TPL_TAG_PAIR_RE = re.compile(
    r'<\s*(%s)\b[^>]*>[\s\S]*?<\s*/\s*\1\s*>' % '|'.join(SANITIZE_TAGS), re.I)
TPL_TAG_STRAY_RE = re.compile(
    r'<\s*/?\s*(%s)\b[^>]*>' % '|'.join(SANITIZE_STRAY), re.I)
TPL_ON_RE = re.compile(r'\son[a-z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', re.I)
TPL_PROTO_RE = re.compile(
    r'\b(href|src|xlink:href)\s*=\s*("|\')?\s*(?:javascript|vbscript)\s*:', re.I)
TPL_DATAHTML_RE = re.compile(
    r'\b(href|src|xlink:href)\s*=\s*("|\')?\s*data:text/html\s*[:;]', re.I)
TPL_STYLE_RE = re.compile(r'(\sstyle\s*=\s*)("|\')([\s\S]*?)\2', re.I)
TPL_STYLE_BARE_RE = re.compile(r'(\sstyle\s*=\s*)([^\s"\'>][^\s>]*)', re.I)

CSS_URL_RE = re.compile(r'url\(\s*([\'"]?)([^\'")]*)\1\s*\)', re.I)

# 会污染工具界面（而不是文档内容）的全局选择器
GLOBAL_HEADS = ('body', 'html', ':root', '*')
UI_SELECTORS = ('.toolbar', '.btn', '.toast', '.modal', '.dialog', '.settings',
                '.sidebar', '.menu', '.dropdown', '.topbar', '.tabs', '.tab',
                '.editor', '#editor', '#preview', '.app', '.wrap')

# Python 不认、但 JS 认的正则写法（用于降级提示，不当作 error）
JS_ONLY_FEATURES = (
    (re.compile(r'\\[pP]\{'), r'\p{...} / \P{...} Unicode 属性'),
    (re.compile(r'\\u\{'), r'\u{...} 码点转义'),
    (re.compile(r'\(\?<[A-Za-z_$]'), '命名捕获组 (?<name>…)'),
    (re.compile(r'\\k<'), r'命名反向引用 \k<name>'),
    (re.compile(r'\(\?<=|\(\?<!'), '变长 lookbehind'),
)

# JS 里当字面字符、Python 里是特殊语法的转义（语义会悄悄不同）
JS_LITERAL_ESCAPES = re.compile(r'\\([AZzQEGR XKN])'.replace(' ', ''))

# JS 的空白字符集合（String.prototype.trim 用）
JS_WS = ('\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006'
         '\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff')

LEVEL_ORDER = {'error': 0, 'warn': 1, 'hint': 2}


# ================================================================ 输出

class Report(object):
    """一个规则文件的检查结果。items 顺序 = 发现顺序（同级之间保序）。"""

    def __init__(self, path):
        self.path = path
        self.items = []
        self._seen = set()

    def add(self, level, code, path, msg):
        key = (level, code, path, msg)
        if key in self._seen:
            return
        self._seen.add(key)
        self.items.append({'level': level, 'code': code,
                           'path': path or '', 'msg': msg})

    def error(self, code, path, msg):
        self.add('error', code, path, msg)

    def warn(self, code, path, msg):
        self.add('warn', code, path, msg)

    def hint(self, code, path, msg):
        self.add('hint', code, path, msg)

    def count(self, level):
        return sum(1 for it in self.items if it['level'] == level)

    @property
    def errors(self):
        return self.count('error')

    @property
    def warns(self):
        return self.count('warn')

    @property
    def hints(self):
        return self.count('hint')

    def ordered(self):
        # 稳定排序：error 在前，同级别保持发现顺序
        return sorted(self.items, key=lambda it: LEVEL_ORDER[it['level']])

    def to_json(self):
        return {
            'path': self.path,
            'ok': self.errors == 0,
            'errors': self.errors,
            'warns': self.warns,
            'hints': self.hints,
            'items': [{'level': it['level'], 'code': it['code'],
                       'path': it['path'], 'msg': it['msg']}
                      for it in self.ordered()],
        }


def _setup_stdout():
    """Windows 控制台默认 GBK，中文/符号会 UnicodeEncodeError：能改就改 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            try:
                stream.reconfigure(errors='replace')
            except Exception:
                pass


def read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


# ================================================================ JS 语义小工具

def js_trim(s):
    return s.strip(JS_WS)


def utf16_len(s):
    """JS 的 String.length：UTF-16 码元数（emoji 算 2）。"""
    return len(s.encode('utf-16-le', 'surrogatepass')) // 2


def js_num_str(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if v != v:
        return 'NaN'
    if v == float('inf'):
        return 'Infinity'
    if v == float('-inf'):
        return '-Infinity'
    if v == int(v) and abs(v) < 1e21:
        return str(int(v))
    return repr(v)


def js_str(v):
    """JS 的 String(v)，只覆盖 JSON 能出现的类型。"""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return js_num_str(v)
    if isinstance(v, list):
        return ','.join(js_str(x) for x in v)
    return '[object Object]'


def js_truthy(v):
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return False
    if isinstance(v, str) and v == '':
        return False
    return True


def short(s, n=48):
    s = str(s).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return s if len(s) <= n else s[:n] + '…'


def _type_name(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return '布尔'
    if isinstance(v, str):
        return '字符串'
    if isinstance(v, (int, float)):
        return '数字'
    if isinstance(v, list):
        return '数组'
    return '对象'


# ================================================================ JS 正则的结构检查

def _valid_group_name(name):
    if not name:
        return False
    first = name[0]
    if first not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$' \
            and ord(first) < 128:
        return False
    for ch in name[1:]:
        if ch in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$':
            continue
        if ord(ch) >= 128:
            continue
        return False
    return True


def js_group_count(pattern):
    """数捕获组（JS 语义）：(?: (?= (?! (?<= (?<! (?flags: 不算，(?<name> 算。"""
    n = 0
    i = 0
    length = len(pattern)
    in_class = False
    while i < length:
        c = pattern[i]
        if c == '\\':
            i += 2
            continue
        if in_class:
            if c == ']':
                in_class = False
            i += 1
            continue
        if c == '[':
            in_class = True
            i += 1
            continue
        if c == '(':
            if (pattern.startswith('(?:', i) or pattern.startswith('(?=', i)
                    or pattern.startswith('(?!', i)
                    or pattern.startswith('(?<=', i) or pattern.startswith('(?<!', i)
                    or re.match(r'\(\?[ims]*(?:-[ims]+)?:', pattern[i:])):
                pass
            elif pattern.startswith('(?<', i):
                n += 1
            elif pattern.startswith('(?', i):
                pass                      # 非法分组，交给 js_regex_problem
            else:
                n += 1
        i += 1
    return n


def js_regex_problem(pattern, flags=''):
    """返回 JS RegExp 一定会抛 SyntaxError 的原因；能编译就返回 None。

    只查「确定错」的写法（括号/字符类/量词/分组语法/类范围/u 模式反向引用），
    拿不准的一律放过——宁可漏报，也不要把合法正则判成 error。
    """
    if len(set(flags)) != len(flags):
        return 'flags 里有重复标志（如 gg），new RegExp 会直接抛错'

    unicode_mode = 'u' in flags
    n = len(pattern)
    i = 0
    stack = []            # 'capture' / 'noncapture' / 'lookahead' / 'lookbehind' / 'named'
    prev = 'none'         # none | atom | assert | quant | lazy
    in_class = False
    class_last = None     # ('lit', ch) 或 ('esc', kind)
    names = []
    backrefs = []

    while i < n:
        c = pattern[i]

        if in_class:
            if c == '\\':
                if i + 1 >= n:
                    return '字符类里的反斜杠在结尾'
                class_last = ('esc', pattern[i + 1])
                i += 2
                continue
            if c == ']':
                in_class = False
                prev = 'atom'
                i += 1
                continue
            if c == '-' and class_last is not None and i + 1 < n \
                    and pattern[i + 1] != ']':
                if pattern[i + 1] == '\\':
                    nxt = pattern[i + 2] if i + 2 < n else ''
                    if unicode_mode and nxt in 'dDsSwWpP':
                        return 'u 标志下字符类范围的终点不能是 \\%s' % nxt
                    class_last = ('esc', nxt)
                    i += 3
                    continue
                end = pattern[i + 1]
                if class_last[0] == 'lit' and ord(class_last[1]) > ord(end):
                    return '字符类范围反了：%s-%s' % (class_last[1], end)
                class_last = ('lit', end)
                i += 2
                continue
            class_last = ('lit', c)
            i += 1
            continue

        if c == '\\':
            if i + 1 >= n:
                return '\\ 在结尾，转义没写完'
            e = pattern[i + 1]
            if e in 'bB':
                prev = 'assert'
                i += 2
                continue
            if e in 'dDsSwW':
                prev = 'atom'
                i += 2
                continue
            if e in 'pP':
                if unicode_mode:
                    if i + 2 >= n or pattern[i + 2] != '{':
                        return 'u 标志下 \\%s 后面必须跟 {属性}' % e
                    close = pattern.find('}', i + 3)
                    if close < 0:
                        return '\\%s{...} 的大括号没闭合' % e
                    i = close + 1
                    prev = 'atom'
                    continue
                prev = 'atom'
                i += 2
                continue
            if e == 'u':
                if unicode_mode:
                    if i + 2 < n and pattern[i + 2] == '{':
                        close = pattern.find('}', i + 3)
                        if close < 0:
                            return '\\u{...} 的大括号没闭合'
                        hexs = pattern[i + 3:close]
                        if not re.match(r'^[0-9a-fA-F]{1,6}$', hexs):
                            return '\\u{...} 里不是合法十六进制'
                        if int(hexs, 16) > 0x10FFFF:
                            return '\\u{...} 超过 0x10FFFF'
                        i = close + 1
                        prev = 'atom'
                        continue
                    if not re.match(r'^[0-9a-fA-F]{4}$', pattern[i + 2:i + 6]):
                        return 'u 标志下 \\u 后面必须是 4 位十六进制'
                    i += 6
                    prev = 'atom'
                    continue
                i += 2
                prev = 'atom'
                continue
            if e == 'x':
                if unicode_mode and not re.match(
                        r'^[0-9a-fA-F]{2}$', pattern[i + 2:i + 4]):
                    return 'u 标志下 \\x 后面必须是 2 位十六进制'
                i += 4 if unicode_mode else 2
                prev = 'atom'
                continue
            if e == 'c':
                if unicode_mode:
                    if i + 2 >= n or not pattern[i + 2].isalpha():
                        return 'u 标志下 \\c 后面必须是字母'
                    i += 3
                else:
                    i += 2
                prev = 'atom'
                continue
            if e == 'k':
                if names:
                    m = re.match(r'\\k<([^>]*)>', pattern[i:])
                    if not m:
                        return '\\k 后面缺少 <name>'
                    if m.group(1) not in names:
                        return '\\k<%s> 找不到对应命名组' % m.group(1)
                    i += m.end()
                    prev = 'atom'
                    continue
                if unicode_mode:
                    return 'u 标志下 \\k 不能当字面转义'
                i += 2
                prev = 'atom'
                continue
            if e.isdigit():
                if unicode_mode and e == '0' and i + 2 < n and pattern[i + 2].isdigit():
                    return 'u 标志下 \\00 / \\01× 这种八进制转义非法'
                m = re.match(r'\\([0-9]+)', pattern[i:])
                num = int(m.group(1))
                if num > 0:
                    backrefs.append(num)
                i += m.end()
                prev = 'atom'
                continue
            if unicode_mode and e.isalpha() and e.isascii() and e not in 'nrtfv':
                return 'u 标志下 \\%s 是非法转义' % e
            i += 2
            prev = 'atom'
            continue

        if c == '(':
            if pattern.startswith('(?', i):
                if i + 2 >= n:
                    return '分组语法不完整（结尾的 "(?"）'
                g = pattern[i + 2]
                if g == ':':
                    stack.append('noncapture')
                    i += 3
                    prev = 'none'
                    continue
                if g in '=!':
                    stack.append('lookahead')
                    i += 3
                    prev = 'none'
                    continue
                if g == '<':
                    if i + 3 >= n:
                        return '分组语法不完整（(?<）'
                    if pattern[i + 3] in '=!':
                        stack.append('lookbehind')
                        i += 4
                        prev = 'none'
                        continue
                    m = re.match(r'\(\?<([^>]*)>', pattern[i:])
                    if not m:
                        return '命名捕获组缺少 >'
                    name = m.group(1)
                    if not _valid_group_name(name):
                        return '命名组名字不合法：%s' % (name or '(空)')
                    if name in names and '|' not in pattern:
                        return '命名组名字重复：%s' % name
                    names.append(name)
                    stack.append('named')
                    i += m.end()
                    prev = 'none'
                    continue
                m = re.match(r'\(\?([ims]*)(?:-([ims]+))?:', pattern[i:])
                if m:
                    fl = m.group(1) + (m.group(2) or '')
                    if len(set(fl)) != len(fl):
                        return '修饰符组里同一个标志重复了'
                    stack.append('noncapture')
                    i += m.end()
                    prev = 'none'
                    continue
                return '分组语法不合法："%s"' % pattern[i:i + 4]
            stack.append('capture')
            i += 1
            prev = 'none'
            continue

        if c == ')':
            if not stack:
                return '多了一个 )'
            kind = stack.pop()
            prev = 'assert' if kind == 'lookbehind' else 'atom'
            i += 1
            continue

        if c == '|':
            prev = 'none'
            i += 1
            continue

        if c in '^$':
            prev = 'assert'
            i += 1
            continue

        if c in '*+?':
            if prev == 'quant' and c == '?':
                prev = 'lazy'
                i += 1
                continue
            if prev != 'atom':
                return '量词 %s 前面没有可重复的内容' % c
            prev = 'quant'
            i += 1
            continue

        if c == '{':
            m = re.match(r'\{(\d+)(?:,(\d*))?\}', pattern[i:])
            if m:
                lo = int(m.group(1))
                hi = m.group(2)
                if hi:
                    if int(hi) < lo:
                        return '量词数字顺序反了：{%d,%s}' % (lo, hi)
                if prev != 'atom':
                    return '量词 {%s} 前面没有可重复的内容' % m.group(0)[1:-1]
                prev = 'quant'
                i += m.end()
                continue
            prev = 'atom'      # 不构成量词的 { 在 JS 里是字面量
            i += 1
            continue

        if c == '[':
            in_class = True
            class_last = None
            i += 1
            continue

        prev = 'atom'
        i += 1

    if in_class:
        return '字符类 [ 没有闭合'
    if stack:
        return '分组 ( 没有闭合'
    if unicode_mode and backrefs and max(backrefs) > js_group_count(pattern):
        return 'u 标志下反向引用数超过捕获组数'
    return None


def analyze_regex(pattern, flags, rep, path):
    """编译检查 + 分级。

    返回 (ok, groups)。ok=False 表示已经记了 error，调用方跳过后续检查。
    策略：JS 结构检查是硬判据；Python 编译失败只降级成 hint，不误报。
    """
    problem = js_regex_problem(pattern, flags)
    if problem:
        rep.error('regex', path,
                  '正则不是合法 JS 正则（%s）→ md2pdf 会整份禁用%s；pattern：%s'
                  % (problem, ATTRIBUTION, short(pattern)))
        return False, 0

    py_flags = 0
    for f in flags:
        if f == 'i':
            py_flags |= re.I
        elif f == 'm':
            py_flags |= re.M
        elif f == 's':
            py_flags |= re.S
        elif f == 'u':
            py_flags |= re.U
    py_err = ''
    try:
        re.compile(pattern, py_flags)
    except re.error as exc:
        py_err = str(exc)

    if py_err:
        label = ''
        for rx, name in JS_ONLY_FEATURES:
            if rx.search(pattern):
                label = name
                break
        if label:
            rep.hint('js-regex', path,
                     '这条正则用了 Python 不支持的 JS 写法（%s），已降级为结构检查；'
                     '以 md2pdf 实际校验为准' % label)
        else:
            rep.hint('js-regex', path,
                     'Python 的 re 编译不了它（%s），但 JS 正则仍可能合法；'
                     '以 md2pdf 实际校验为准' % short(py_err, 40))

    if JS_LITERAL_ESCAPES.search(pattern) and 'u' not in flags:
        rep.hint('regex-dialect', path,
                 r'正则里有 \A / \Z / \Q 这类转义：JS 把它们当字面字符，'
                 r'和 Python 的解释不同，以 md2pdf 为准')

    if BAD_QUANT_RE.search(pattern):
        rep.warn('backtrack', path,
                 '有嵌套量词（如 (a+)+），全文替换时可能灾难性回溯、卡住页面：%s'
                 % short(pattern, 40))

    return True, js_group_count(pattern)


# ================================================================ 模板占位符扫描（extTplMarks 移植）

def tpl_marks(tpl, is_token):
    """返回 [(位置, 是否在标签内, 是否在引号属性值里), ...]。

    标签识别规则与 extTplMarks 完全一致：`<` 后跟字母 / `/` / `!` 进标签；
    标签里遇引号进引号态；不在引号态遇 `>` 出标签。
    """
    marks = []
    in_tag = False
    quote = ''
    n = len(tpl)
    for i in range(n):
        c = tpl[i]
        if not in_tag:
            if c == '<' and i + 1 < n and re.match(r'[a-zA-Z/!]', tpl[i + 1]):
                in_tag = True
        elif quote:
            if c == quote:
                quote = ''
        elif c in '"\'':
            quote = c
        elif c == '>':
            in_tag = False
        if is_token(tpl, i):
            marks.append((i, in_tag, bool(quote)))
    return marks


def is_content_token(tpl, i):
    return tpl[i:i + 8] == '$content'


def is_inline_token(tpl, i):
    if tpl[i] != '$':
        return False
    n = tpl[i + 1] if i + 1 < len(tpl) else ''
    return n == '$' or n == '&' or ('0' <= n <= '9')


def unsafe_placeholder(tpl, is_content):
    """返回第一个「裸插进标签」的占位符（没有就返回空串）。"""
    marks = tpl_marks(tpl, is_content_token if is_content else is_inline_token)
    for at, in_tag, quoted in marks:
        if not in_tag:
            continue
        if is_content:
            return '$content'
        if not quoted:
            return tpl[at:at + 2]
    return ''


# ================================================================ CSS（cssSanitize 移植 + 诊断）

def css_sanitize(css):
    s = re.sub(r'@import[\s\S]*?;', '', css, flags=re.I)
    s = re.sub(r'expression\s*\(', 'none(', s, flags=re.I)
    s = re.sub(r'(?:behavior|-moz-binding)\s*:[^;}]*', '', s, flags=re.I)
    s = re.sub(r'(?:java|vb)script\s*:', '', s, flags=re.I)

    def _url(m):
        target = m.group(2).strip()
        if not target or target[0] == '#' or re.match(r'data:image/', target, re.I):
            return m.group(0)
        return 'none'

    return CSS_URL_RE.sub(_url, s)


def css_selectors(css):
    """粗切选择器（去掉注释、跳过 @ 规则的前奏），只为警告全局选择器。"""
    clean = re.sub(r'/\*[\s\S]*?\*/', '', css)
    out = []
    for m in re.finditer(r'([^{}]*)\{', clean):
        prelude = m.group(1).strip()
        if not prelude:
            continue
        if prelude.startswith('@'):
            # @import x; body {…} 这种，选择器在最后一条 ; 之后
            tail = prelude.rsplit(';', 1)[-1].strip()
            if not tail or tail.startswith('@'):
                continue
            prelude = tail
        for sel in prelude.split(','):
            sel = sel.strip()
            if sel:
                out.append(sel)
    return out


def is_global_selector(sel):
    low = sel.strip().lower()
    for head in GLOBAL_HEADS:
        if low == head:
            return True
        if low.startswith(head) and len(low) > len(head) \
                and not (low[len(head)].isalnum() or low[len(head)] in '_-'):
            return True
    for cls in UI_SELECTORS:
        if re.search(re.escape(cls) + r'(?![\w-])', low):
            return True
    return False


def check_css(css, rep):
    path = 'cssInjection'

    if re.search(r'@import[\s\S]*?;', css, re.I):
        rep.warn('css-stripped', path,
                 '@import … ; 整条会被 cssSanitize 删掉（外部样式不会生效）')
    elif '@import' in css.lower():
        rep.warn('css-stripped', path,
                 '@import 后面没有分号：删不掉，但外部样式仍然加载不了，建议直接删')

    if re.search(r'expression\s*\(', css, re.I):
        rep.warn('css-stripped', path,
                 'expression( 会被替换成 none(（IE 时代的脚本表达式一律禁用）')

    if re.search(r'(?:behavior|-moz-binding)\s*:', css, re.I):
        rep.warn('css-stripped', path,
                 'behavior / -moz-binding 声明会被整条删掉')

    if re.search(r'(?:java|vb)script\s*:', css, re.I):
        rep.warn('css-stripped', path,
                 'javascript: / vbscript: 会被删掉（写在 CSS 里也没法执行）')

    ext_urls = []
    # 按 cssSanitize 的顺序先去掉 @import，免得把 import 里的 url 再报一遍
    after_import = re.sub(r'@import[\s\S]*?;', '', css, flags=re.I)
    for m in CSS_URL_RE.finditer(after_import):
        target = m.group(2).strip()
        if not target or target[0] == '#' or re.match(r'data:image/', target, re.I):
            continue
        ext_urls.append(short(target, 40))
    if ext_urls:
        rep.warn('css-stripped', path,
                 '外部 url() 会被换成 none（离线优先，只允许 #id 和 data:image/）：%s'
                 % '、'.join(ext_urls[:3]))

    seen = []
    for sel in css_selectors(css):
        if is_global_selector(sel) and sel not in seen:
            seen.append(sel)
    for sel in seen[:4]:
        rep.warn('css-global', path,
                 '选择器 %s 会作用到工具界面本身（不只是文档内容），建议收进 .ext- 之类的前缀里'
                 % short(sel, 40))

    if css.strip() and not css_sanitize(css).strip():
        rep.hint('css-empty-after-sanitize', path,
                 '净化后这段 CSS 什么都不剩了，等于没写')


# ================================================================ 模板诊断

def check_template(tpl, root, rep, block):
    """模板骨架里会被 sanitizeHtml 吃掉的东西 + inline style 里的 CSS 陷阱。"""
    for m in TPL_TAG_PAIR_RE.finditer(tpl):
        rep.warn('sanitized-away', root,
                 '模板里的 <%s>…</%s> 会被 sanitizeHtml 整段删掉（骨架只允许普通排版标签）；'
                 '样式请放 cssInjection，图形请放正文'
                 % (m.group(1).lower(), m.group(1).lower()))
    paired = set(m.group(1).lower() for m in TPL_TAG_PAIR_RE.finditer(tpl))
    for m in TPL_TAG_STRAY_RE.finditer(tpl):
        tag = m.group(1).lower()
        if tag in paired:
            continue
        rep.warn('sanitized-away', root,
                 '模板里的 <%s> 标签会被 sanitizeHtml 删掉' % tag)

    if TPL_ON_RE.search(tpl):
        rep.warn('sanitized-away', root,
                 '模板里的 on*= 事件属性会被 sanitizeHtml 删掉（写模板时不要带事件）')

    if TPL_PROTO_RE.search(tpl):
        rep.warn('sanitized-away', root,
                 '模板里的 javascript:/vbscript: 链接会被换成 href="#"，点了不会执行')

    if TPL_DATAHTML_RE.search(tpl):
        rep.warn('sanitized-away', root,
                 '模板里的 data:text/html 链接会被换成 href="#"')

    style_chunks = [m.group(3) for m in TPL_STYLE_RE.finditer(tpl)]
    style_chunks += [m.group(2) for m in TPL_STYLE_BARE_RE.finditer(tpl)]
    for chunk in style_chunks:
        low = chunk.lower()
        if '@import' in low or re.search(r'url\(\s*[\'"]?(?!data:|#)', low, re.I) \
                or 'expression(' in low or 'javascript:' in low:
            rep.warn('css-stripped', root,
                     '模板里 style="…" 的内联样式会被 cssSanitize 过滤（外链 url / @import / expression 会没）')
            break

    if block and '$contentX' in tpl:
        rep.hint('content-suffix', root,
                 '$contentX 会被当成 $content 后跟一个 X（正文后面多出个 X），'
                 '想紧挨正文写字请把 X 移出模板或加空格')


# ================================================================ 逐字段检查

class ExtChecker(object):
    def __init__(self, rep, doc_text=None):
        self.rep = rep
        self.doc = doc_text
        self.effective = 0       # 真正生效的条目数
        self.meta_name = ''
        self.meta_name_hinted = False

    # ---------------- meta ----------------
    def check_meta(self, data):
        if 'meta' not in data:
            return
        meta = data['meta']
        if not js_truthy(meta) or not isinstance(meta, dict):
            if isinstance(meta, list):
                self.rep.hint('meta-ignored', 'meta',
                              'meta 是数组，工具只认对象，name/version 会被忽略')
            elif meta is not None:
                self.rep.hint('meta-ignored', 'meta',
                              'meta 不是对象（%s），name/version 会被忽略' % _type_name(meta))
            return
        if not meta:
            self.rep.hint('meta-name', 'meta',
                          'meta 是空对象：建议写 name/version，状态行会显示「已启用：名字（版本）」')
            self.meta_name_hinted = True
            return

        raw_name = meta.get('name')
        name = js_trim(js_str(raw_name))
        if utf16_len(name) > 60:
            self.rep.warn('truncate', 'meta.name',
                          'meta.name 有 %d 个字符（%d 个 UTF-16 码元），超过 60 会被静默截断'
                          % (len(name), utf16_len(name)))
        elif raw_name is not None and isinstance(raw_name, str) \
                and raw_name != raw_name.strip():
            self.rep.hint('trimmed', 'meta.name',
                          'meta.name 首尾空白会被静默 trim 掉')
        self.meta_name = name

        raw_ver = meta.get('version')
        ver = js_trim(js_str(raw_ver))
        if utf16_len(ver) > 20:
            self.rep.warn('truncate', 'meta.version',
                          'meta.version 有 %d 个字符，超过 20 会被静默截断' % len(ver))
        elif raw_ver is not None and isinstance(raw_ver, str) \
                and raw_ver != raw_ver.strip():
            self.rep.hint('trimmed', 'meta.version',
                          'meta.version 首尾空白会被静默 trim 掉')

        for key in meta:
            if key not in META_KEYS:
                self.rep.warn('unknown-key', 'meta.' + key,
                              'meta 里不认识 %r，会被静默忽略（只有 name/version 有用）' % key)

    # ---------------- preProcess ----------------
    def check_pre_process(self, data):
        if 'preProcess' not in data:
            return
        val = data['preProcess']
        if not isinstance(val, list):
            self.rep.error('field', 'preProcess',
                           'preProcess 必须是数组（现在是 %s）→ 整份禁用'
                           % _type_name(val))
            return
        for i, item in enumerate(val):
            path = 'preProcess[%d]' % i
            if not isinstance(item, dict):
                self.rep.error('field', path,
                               '%s 必须是对象（现在是 %s）→ 整份禁用'
                               % (path, _type_name(item)))
                continue
            self._check_pre_item(i, item, path)

    def _check_pre_item(self, i, item, path):
        rep = self.rep
        pattern = item.get('pattern')
        p_ok = True
        if not isinstance(pattern, str) or not pattern:
            rep.error('field', path + '.pattern',
                      'pattern 必须是非空字符串 → 整份禁用')
            p_ok = False
        elif utf16_len(pattern) > EXT_MAX_PATTERN:
            rep.error('field', path + '.pattern',
                      'pattern 长度 %d 超过 %d（UTF-16 码元）→ 整份禁用'
                      % (utf16_len(pattern), EXT_MAX_PATTERN))
            p_ok = False

        flags = ''
        f_ok = True
        if 'flags' in item:
            raw_flags = item['flags']
            if not isinstance(raw_flags, str) or not FLAGS_RE.match(raw_flags):
                rep.error('field', path + '.flags',
                          'flags 必须是 ^[gimsuy]*$ 的字符串（现在是 %s）→ 整份禁用'
                          % (short(js_str(raw_flags), 20) if not isinstance(raw_flags, str)
                             else short(raw_flags, 20)))
                f_ok = False
            else:
                flags = raw_flags
        if 'flags' in item and f_ok and 'y' in flags:
            rep.hint('sticky-flag', path + '.flags',
                     'y（sticky）会从 lastIndex 锚定匹配，全文替换几乎只命中开头；'
                     '一般想要的是 g')

        replacement = item.get('replacement')
        r_ok = isinstance(replacement, str)
        if not r_ok:
            rep.error('field', path + '.replacement',
                      'replacement 必须是字符串（可以是空串）→ 整份禁用')

        for key in item:
            if key not in PRE_KEYS:
                rep.warn('unknown-key', path + '.' + key,
                         '%s 里的 %r 工具不认识，会被静默忽略（是不是拼错了？）'
                         % (path, key))

        if not (p_ok and f_ok):
            return

        ok, groups = analyze_regex(pattern, flags, rep, path + '.pattern')
        if not ok:
            return

        if r_ok:
            if 'g' not in flags:
                rep.warn('no-g-flag', path + '.flags',
                         '没写 g：String.replace 只替换第一处（要全文替换必须 flags:"g"）')
            self._check_pre_replacement(replacement, groups, pattern, path)
            if self.doc is not None:
                self._check_hit(pattern, flags, path)

        self.effective += 1

    def _check_pre_replacement(self, tpl, groups, pattern, path):
        """String.replace 的 $ 语义：$& 整个匹配、$` 前缀、$' 后缀、$n 捕获组、$$ 字面 $。"""
        rep = self.rep
        rpath = path + '.replacement'
        named = re.findall(r'\(\?<([A-Za-z_$][A-Za-z0-9_$]*)>', pattern)

        for m in re.finditer(r'\$(&|`|\'|<[^>]*>|\d{1,2}|\$)', tpl):
            tok = m.group(0)
            if tok == '$$':
                rep.hint('dollar-semantics', rpath,
                         'replacement 里的 $$ 会输出一个字面 $（想写 $1 字面量要写 $$1）')
            elif tok == '$&':
                rep.hint('dollar-semantics', rpath,
                         '$& 是「整个匹配」，会原样再插一份；确认这是你要的')
            elif tok in ('$`', "$'"):
                rep.warn('dollar-replacement', rpath,
                         '%s 是「匹配前/后的全文」，会把整份文档复制进来；'
                         '要字面量请写 $$' % tok)
            elif tok.startswith('$<'):
                name = tok[2:-1]
                if name and name not in named:
                    rep.warn('dollar-replacement', rpath,
                             '$<%s> 找不到同名命名组，会原样输出；'
                             '要字面量请写 $$' % name)
            else:
                digits = tok[1:]
                num = int(digits)
                if num == 0:
                    rep.warn('dollar-replacement', rpath,
                             '$0 在 preProcess 里不是「整个匹配」（要写 $&），'
                             '它会被原样输出')
                elif num > groups:
                    if len(digits) == 2 and 1 <= int(digits[0]) <= groups:
                        rep.warn('dollar-replacement', rpath,
                                 '$%s 超出捕获组数（%d 个），会展开成「第 %s 组 + 字面数字 %s」；'
                                 '要字面量请写 $$%s'
                                 % (digits, groups, digits[0], digits[1], digits))
                    else:
                        rep.warn('dollar-replacement', rpath,
                                 '$%s 超出捕获组数（%d 个），会原样输出；'
                                 '要字面量请写 $$%s' % (digits, groups, digits))

        if re.search(r'\\[nrtbf1-9$]', tpl):
            rep.hint('literal-escape', rpath,
                     'replacement 里有字面反斜杠序列（JSON 的 "\\\\n" 会得到反斜杠+n，'
                     '不会换行）；要真换行得在 JSON 里写 "\\n"')

    def _check_fence_used(self, fence, path):
        """--doc 里有没有真的用到这个围栏（名字写错是最常见的「写了没反应」）。"""
        if not self.doc:
            return
        try:
            rx = re.compile(r'^ {0,3}(?:`{3,}|~{3,})[ \t]*' + re.escape(fence)
                            + r'(?:[ \t].*)?$', re.I | re.M)
        except re.error:
            return
        if rx.search(self.doc) is None:
            self.rep.warn('fence-unused', path + '.fence',
                          '围栏 %s 定义了，但 --doc 样本文档里没出现 ```%s'
                          '（名字写错 / 大小写不一致 / 文档还没用上）' % (fence, fence))

    def _check_hit(self, pattern, flags, path):
        py_flags = 0
        for f in flags:
            if f == 'i':
                py_flags |= re.I
            elif f == 'm':
                py_flags |= re.M
            elif f == 's':
                py_flags |= re.S
        try:
            rx = re.compile(pattern, py_flags)
            hit = rx.search(self.doc) is not None
        except re.error:
            return
        if not hit:
            self.rep.warn('pattern-unmatched', path + '.pattern',
                          '在你给的 --doc 样本文档里一次都没命中，检查转义/字符类是不是写错了')

    # ---------------- customSyntax ----------------
    def check_custom_syntax(self, data):
        if 'customSyntax' not in data:
            return
        val = data['customSyntax']
        if not isinstance(val, list):
            self.rep.error('field', 'customSyntax',
                           'customSyntax 必须是数组（现在是 %s）→ 整份禁用'
                           % _type_name(val))
            return
        fences = set()
        for i, item in enumerate(val):
            path = 'customSyntax[%d]' % i
            if not isinstance(item, dict):
                self.rep.error('field', path,
                               '%s 必须是对象（现在是 %s）→ 整份禁用'
                               % (path, _type_name(item)))
                continue
            if item.get('type') not in ('inline', 'block'):
                self.rep.error('field', path + '.type',
                               'type 只能是 "inline" 或 "block"（现在是 %s）→ 整份禁用'
                               % short(js_str(item.get('type')), 20))
                continue
            replacement = item.get('replacement')
            if not isinstance(replacement, str) or not replacement:
                self.rep.error('field', path + '.replacement',
                               'replacement 必须是非空字符串 → 整份禁用')
                continue
            if utf16_len(replacement) > EXT_MAX_TPL:
                self.rep.error('field', path + '.replacement',
                               'replacement 长度 %d 超过 %d（UTF-16 码元）→ 整份禁用'
                               % (utf16_len(replacement), EXT_MAX_TPL))
                continue

            if item['type'] == 'inline':
                self._check_inline(i, item, path, replacement)
            else:
                if not self._check_block(i, item, path, replacement, fences):
                    continue

    def _check_inline(self, i, item, path, replacement):
        rep = self.rep
        pattern = item.get('pattern')
        if not isinstance(pattern, str) or not pattern:
            rep.error('field', path + '.pattern',
                      'inline 条目必须有非空的 pattern → 整份禁用')
            return
        if utf16_len(pattern) > EXT_MAX_PATTERN:
            rep.error('field', path + '.pattern',
                      'pattern 长度 %d 超过 %d → 整份禁用'
                      % (utf16_len(pattern), EXT_MAX_PATTERN))
            return

        for key in item:
            if key not in INLINE_KEYS:
                rep.warn('unknown-key', path + '.' + key,
                         '%s 里的 %r 工具不认识，会被静默忽略（是不是拼错了？）'
                         % (path, key))

        if 'flags' in item and item['flags'] != 'g':
            rep.warn('inline-flags', path + '.flags',
                     'inline 条目的 flags 会被忽略：工具固定用 g，且没有 i/m/s 可用；'
                     '想不区分大小写只能在 pattern 里写 (?i:…)（修饰符组要 Chrome 125+）')

        ok, groups = analyze_regex(pattern, 'g', rep, path + '.pattern')
        if not ok:
            return

        unsafe = unsafe_placeholder(replacement, False)
        if unsafe:
            rep.error('unsafeTemplate', path + '.replacement',
                      '行内占位符 %s 裸插进了 HTML 标签（不在引号属性值里），'
                      '捕获内容能逃逸出标签 → 整份禁用' % short(unsafe, 4))
            return

        if '$content' in replacement:
            rep.warn('content-in-inline', path + '.replacement',
                     '行内模板里的 $content 不是占位符，会原样输出（$content 只属于 block 围栏）')

        if re.search(r'\$\d\d', replacement):
            rep.hint('two-digit-group', path + '.replacement',
                     '行内只认一位数字：$12 等于 $1 后跟字面 "2"，不是第 12 组')

        if '$<' in replacement:
            rep.hint('named-group-inline', path + '.replacement',
                     '行内模板不支持 $<name>，会原样输出；只能用 $0…$9 / $& / $$')

        for m in re.finditer(r'\$(&|\d)', replacement):
            tok = m.group(0)
            num = 0 if tok == '$&' else int(tok[1])
            if num > groups:
                rep.warn('dollar-replacement', path + '.replacement',
                         '%s 超出捕获组数（%d 个）：行内替换会变成空串（不是原样保留）'
                         % (tok, groups))

        check_template(replacement, path + '.replacement', rep, block=False)
        if self.doc is not None:
            self._check_hit(pattern, 'g', path)
        self.effective += 1

    def _check_block(self, i, item, path, replacement, fences):
        rep = self.rep
        fence_value = item.get('fence')
        fence = js_str(fence_value).strip().lower() if fence_value is not None else ''
        if not FENCE_RE.match(fence):
            rep.error('field', path + '.fence',
                      'fence 必须是 ^[a-z][a-z0-9_-]{0,30}$（会先 trim 再转小写；现在是 %s）'
                      '→ 整份禁用' % short(js_str(fence_value), 30))
            return False
        if fence in RESERVED_FENCES:
            rep.warn('fenceConflict', path + '.fence',
                     '围栏名 %s 撞了内置语言名：这条会被跳过（不报错，但也不会生效）'
                     % fence)
            return False
        if fence in fences:
            rep.error('field', path + '.fence',
                      '围栏名 %s 重复（大小写不敏感）→ 整份禁用' % fence)
            return False
        fences.add(fence)

        if '$content' not in replacement:
            rep.error('contentMissing', path + '.replacement',
                      'block 模板里没有 $content（围栏名为 %s）→ 整份禁用' % fence)
            return False
        unsafe = unsafe_placeholder(replacement, True)
        if unsafe:
            rep.error('unsafeTemplate', path + '.replacement',
                      '模板里的 $content 落在 HTML 标签里（哪怕在引号属性值里也不行），'
                      '正文 HTML 会破坏标签结构 → 整份禁用')
            return False

        for key in item:
            if key not in BLOCK_KEYS:
                rep.warn('unknown-key', path + '.' + key,
                         '%s 里的 %r 工具不认识，会被静默忽略（block 只用 type/fence/replacement）'
                         % (path, key))

        if fence in COMMON_FENCES:
            rep.hint('fence-prefix', path + '.fence',
                     '围栏名 %s 很常见，建议加项目前缀（如 ext-%s），'
                     '以免以后工具内置同名语言把它顶掉' % (fence, fence))
        if fence_value is not None and isinstance(fence_value, str) \
                and fence_value != fence:
            rep.hint('fence-normalized', path + '.fence',
                     '围栏名会被静默 trim + 转小写：%r → %r'
                     % (fence_value, fence))

        check_template(replacement, path + '.replacement', rep, block=True)
        if self.doc is not None:
            self._check_fence_used(fence, path)
        self.effective += 1
        return True

    # ---------------- uiInjection ----------------
    def check_ui(self, data):
        if 'uiInjection' not in data:
            return
        val = data['uiInjection']
        if not isinstance(val, list):
            self.rep.error('field', 'uiInjection',
                           'uiInjection 必须是数组（现在是 %s）→ 整份禁用'
                           % _type_name(val))
            return
        accepted = 0
        for i, item in enumerate(val):
            path = 'uiInjection[%d]' % i
            if not isinstance(item, dict):
                self.rep.error('field', path,
                               '%s 必须是对象（现在是 %s）→ 整份禁用'
                               % (path, _type_name(item)))
                continue
            if 'location' in item and js_str(item['location']) != 'toolbar':
                self.rep.warn('uiLocation', path + '.location',
                              '只支持 location:"toolbar"；这条会被跳过（现在是 %s）'
                              % short(js_str(item['location']), 20))
                continue
            if js_str(item.get('action')) != 'insertText':
                self.rep.error('field', path + '.action',
                               'action 必须是字面量 "insertText"（现在是 %s）→ 整份禁用'
                               % short(js_str(item.get('action')), 20))
                continue
            label = item.get('label')
            if not isinstance(label, str) or not js_trim(label):
                self.rep.error('field', path + '.label',
                               'label 必须是非空（trim 后）字符串 → 整份禁用')
                continue
            text = item.get('text')
            if not isinstance(text, str):
                self.rep.error('field', path + '.text',
                               'text 必须是字符串 → 整份禁用')
                continue

            for key in item:
                if key not in UI_KEYS:
                    self.rep.warn('unknown-key', path + '.' + key,
                                  '%s 里的 %r 工具不认识，会被静默忽略' % (path, key))

            if accepted >= EXT_MAX_UI:
                self.rep.error('field', path,
                               '顶栏最多注入 %d 个按钮，第 %d 个起会报错 → 整份禁用'
                               % (EXT_MAX_UI, accepted + 1))
                continue
            accepted += 1
            self.effective += 1

            label_len = utf16_len(js_trim(label))
            if label_len > 40:
                self.rep.warn('truncate', path + '.label',
                              'label 有 %d 个字符，超过 40 会被静默截断' % label_len)
            if label != js_trim(label):
                self.rep.hint('trimmed', path + '.label',
                              'label 首尾空白会被静默 trim 掉')
            if utf16_len(text) > 500:
                self.rep.warn('truncate', path + '.text',
                              'text 有 %d 个字符，超过 500 会被静默截断（插入内容会缺尾巴）'
                              % utf16_len(text))

    # ---------------- cssInjection ----------------
    def check_css_injection(self, data):
        if 'cssInjection' not in data:
            return
        val = data['cssInjection']
        if not isinstance(val, str):
            self.rep.error('field', 'cssInjection',
                           'cssInjection 必须是字符串（现在是 %s）→ 整份禁用'
                           % _type_name(val))
            return
        if not val.strip():
            self.rep.hint('empty-css', 'cssInjection', 'cssInjection 是空字符串，等于没写')
            return
        check_css(val, self.rep)
        self.effective += 1

    # ---------------- 顶层未知键 ----------------
    def check_unknown_top(self, data):
        for key in data:
            if key in TOP_KEYS:
                continue
            extra = ''
            if key == 'version':
                extra = '（版本号应写在 meta.version）'
            elif key == 'name':
                extra = '（名字应写在 meta.name）'
            elif key in ('preprocess', 'preProcesses', 'preProc'):
                extra = '（正确键名是 preProcess）'
            elif key in ('customsyntax', 'custom'):
                extra = '（正确键名是 customSyntax）'
            elif key in ('uiinjection', 'ui'):
                extra = '（正确键名是 uiInjection）'
            elif key in ('cssinjection', 'css'):
                extra = '（正确键名是 cssInjection）'
            self.rep.warn('unknown-key', key,
                          '顶层键 %r 工具不认识，会被静默忽略%s' % (key, extra))


def check_extension(raw, path, doc_text=None):
    """按 extValidate 的顺序检查一份扩展 JSON 文本。"""
    rep = Report(path)
    src = js_trim(js_str(raw))

    if not src:
        rep.hint('empty-ext', '',
                 '文件是空的：md2pdf 会当成「没有扩展」（ok，但什么都不会生效）')
        return rep

    if utf16_len(src) > EXT_MAX_JSON:
        rep.error('size', '',
                  'JSON 文本有 %d 个 UTF-16 码元，超过上限 %d → md2pdf 会整份禁用'
                  % (utf16_len(src), EXT_MAX_JSON))
        return rep

    try:
        data = json.loads(src, parse_constant=_reject_json_constant)
    except ValueError as exc:
        rep.error('json', '',
                  'JSON 解析失败：%s → md2pdf 会整份禁用' % short(exc, 80))
        return rep

    if not isinstance(data, dict):
        rep.error('root', '',
                  '顶层必须是 JSON 对象（现在是 %s）→ md2pdf 会整份禁用'
                  % _type_name(data))
        return rep

    checker = ExtChecker(rep, doc_text=doc_text)
    checker.check_meta(data)
    checker.check_pre_process(data)
    checker.check_custom_syntax(data)
    checker.check_ui(data)
    checker.check_css_injection(data)
    checker.check_unknown_top(data)

    if checker.effective == 0 and rep.errors == 0:
        rep.hint('empty-ext', '',
                 '没有任何生效的条目（preProcess / customSyntax / uiInjection / '
                 'cssInjection 都空着）：扩展能加载，但等于没开')
    if rep.errors == 0 and checker.effective > 0 and not checker.meta_name \
            and not checker.meta_name_hinted:
        rep.hint('meta-name', 'meta.name',
                 '建议写 meta.name：工具状态行会显示「已启用：名字（版本）」，'
                 '按钮提示也更清楚')
    if rep.errors == 0 and doc_text is None and _has_pattern_rules(data):
        rep.hint('no-doc', '',
                 '没给 --doc 样本文档：checker 无法验证 pattern 是否真的命中，'
                 '建议拿一篇实际文档跑一遍')
    return rep


def _has_pattern_rules(data):
    for item in data.get('preProcess') or []:
        if isinstance(item, dict):
            return True
    for item in data.get('customSyntax') or []:
        if isinstance(item, dict) and item.get('type') == 'inline':
            return True
    return False


def _reject_json_constant(name):
    raise ValueError('JSON 里不允许 %s' % name)


# ================================================================ 输出与 CLI

def print_report(rep):
    print('=' * 72)
    print('扩展规则：%s' % rep.path)
    if not rep.items:
        print('  [OK] 没发现问题。')
    width = max([len(it['path']) for it in rep.items] + [6])
    width = min(width, 34)
    for it in rep.ordered():
        where = it['path'] or '-'
        print('  [%-5s] %-18s %-*s %s'
              % (it['level'], it['code'], width, where, it['msg']))
    print('-' * 72)
    print('小计：%d error, %d warn, %d hint'
          % (rep.errors, rep.warns, rep.hints))


def main(argv):
    _setup_stdout()
    strict = False
    as_json = False
    doc_path = None
    files = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ('-h', '--help'):
            print(__doc__)
            return 0
        if a in ('-s', '--strict'):
            strict = True
            i += 1
            continue
        if a == '--json':
            as_json = True
            i += 1
            continue
        if a == '--doc':
            i += 1
            if i >= len(argv):
                sys.stderr.write('--doc 后面要跟一个文档路径\n')
                return 2
            doc_path = argv[i]
            i += 1
            continue
        if a.startswith('--doc='):
            doc_path = a[len('--doc='):]
            i += 1
            continue
        if a.startswith('-') and a != '-':
            sys.stderr.write('未知选项：%s\n\n' % a)
            sys.stderr.write(__doc__)
            return 2
        files.append(a)
        i += 1

    if not files:
        sys.stderr.write('没给规则文件。用法：python check_ext.py 规则.json [更多.json ...]\n\n')
        sys.stderr.write(__doc__)
        return 2

    doc_text = None
    if doc_path is not None:
        if not os.path.isfile(doc_path):
            sys.stderr.write('找不到 --doc 文档：%s\n' % doc_path)
            return 2
        doc_text = read_text(doc_path)

    reports = []
    for p in files:
        if not os.path.isfile(p):
            sys.stderr.write('找不到文件：%s\n' % p)
            return 2
        try:
            raw = read_text(p)
        except OSError as exc:
            sys.stderr.write('读不了文件：%s（%s）\n' % (p, exc))
            return 2
        reports.append(check_extension(raw, p, doc_text=doc_text))

    if as_json:
        payload = {
            'files': [rep.to_json() for rep in reports],
            'errors': sum(rep.errors for rep in reports),
            'warns': sum(rep.warns for rep in reports),
            'hints': sum(rep.hints for rep in reports),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False,
                                    separators=(',', ':')) + '\n')
        if payload['errors']:
            return 1
        if strict and payload['warns']:
            return 1
        return 0

    for rep in reports:
        print_report(rep)
        print('')
    total_e = sum(rep.errors for rep in reports)
    total_w = sum(rep.warns for rep in reports)
    total_h = sum(rep.hints for rep in reports)
    print('合计 %d 个文件：%d error, %d warn, %d hint'
          % (len(reports), total_e, total_w, total_h))
    if total_e:
        print('[FAIL] 有 %d 处 error：md2pdf 会整份禁用扩展，先修完再用。' % total_e)
        return 1
    if strict and total_w:
        print('[FAIL] --strict 模式下 %d 处 warn 也算失败。' % total_w)
        return 1
    print('[OK] 没有 error。')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
