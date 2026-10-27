#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""examples/ 的完整自检：把 check_ext.py 跑在每个示例文件上，按 expect.json 断言。

用法:
    python selftest.py            # 全部跑一遍
    python selftest.py -v         # 顺带打印每个文件的检查输出

断言内容:
    1. examples/ 里每个 .json 都在 expect.json 里有条目（不漏测）；
    2. expect.json 里写的 md2pdf 真实结论（ok / error+code）与 linter 的判定一致；
    3. expect.json 里写明的 checker 告警码确实出现。

退出码: 0 = 全部通过；1 = 有失败。

注意: expect.json 里 md2pdf 那一栏是用工具内置校验器实测出来的期望值，
      所以这个脚本同时也是「linter 有没有偏离工具」的回归测试。
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXAMPLES = os.path.join(ROOT, 'examples')
CHECKER = os.path.join(HERE, 'check_ext.py')
EXPECT = os.path.join(EXAMPLES, 'expect.json')


def _setup_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            try:
                stream.reconfigure(errors='replace')
            except Exception:
                pass


def run_checker(path):
    """返回 (exit_code, parsed_json_or_None, raw_stdout, raw_stderr)。"""
    proc = subprocess.run(
        [sys.executable, CHECKER, '--json', path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=ROOT,
    )
    out = proc.stdout.decode('utf-8', 'replace')
    err = proc.stderr.decode('utf-8', 'replace')
    data = None
    stripped = out.strip()
    if stripped:
        try:
            data = json.loads(stripped)
        except ValueError:
            data = None
    return proc.returncode, data, out, err


def codes_of(data, levels=('error', 'warn', 'hint')):
    if not data:
        return []
    out = []
    for f in data.get('files', []):
        for it in f.get('items', []):
            if it.get('level') in levels:
                out.append((it.get('level'), it.get('code'), it.get('path')))
    return out


def main(argv):
    _setup_stdout()
    verbose = '-v' in argv or '--verbose' in argv

    if not os.path.isfile(CHECKER):
        print('找不到 check_ext.py：%s' % CHECKER)
        return 2
    if not os.path.isfile(EXPECT):
        print('找不到 examples/expect.json')
        return 2

    with open(EXPECT, 'r', encoding='utf-8') as f:
        expect = json.load(f)
    files = expect.get('files', {})

    # ---- 覆盖检查：examples 里的 json 都要有期望值 ----
    on_disk = sorted(n for n in os.listdir(EXAMPLES) if n.endswith('.json') and n != 'expect.json')
    missing = [n for n in on_disk if n not in files]
    extra = [n for n in files if n not in on_disk]
    fails = []
    if missing:
        fails.append('expect.json 缺这些文件的期望值：%s' % ', '.join(missing))
    if extra:
        fails.append('expect.json 里有不存在的文件：%s' % ', '.join(extra))

    print('=' * 66)
    print('示例自检：%d 个文件' % len(on_disk))
    checked = 0
    for name in on_disk:
        spec = files.get(name, {})
        path = os.path.join(EXAMPLES, name)
        rc, data, out, err = run_checker(path)
        problems = []

        if data is None:
            problems.append('--json 没有输出可解析的 JSON（stdout=%r, stderr=%r）' % (out[:120], err[:120]))
        else:
            top = data.get('files') or [{}]
            errors = top[0].get('errors', 0)
            warns = top[0].get('warns', 0)
            truth = spec.get('md2pdf', {})

            # 1) 退出码
            want_rc = 1 if truth.get('ok') is False else 0
            if rc != want_rc:
                problems.append('退出码 %d，期望 %d' % (rc, want_rc))

            # 2) 与 md2pdf 真实结论一致
            if truth.get('ok') is False:
                if errors < 1:
                    problems.append('md2pdf 会整份禁用，但 linter 没报 error')
                want_code = truth.get('code')
                got_codes = [c for lv, c, _ in codes_of(data, ('error',)) if c]
                if want_code and want_code not in got_codes:
                    problems.append('期望错误码 %s，实际 %s' % (want_code, got_codes or '无'))
            else:
                if errors:
                    bad = [c for lv, c, _ in codes_of(data, ('error',))]
                    problems.append('md2pdf 能加载，但 linter 报了 error：%s' % bad)

            # 3) 声明的 checker 告警码要真的出现
            want_warns = (spec.get('checker') or {}).get('warns') or []
            plain_codes = [c for _, c, _ in codes_of(data, ('warn', 'hint'))]
            for w in want_warns:
                if w not in plain_codes:
                    problems.append('期望告警 %s（可能有多个），实际 %s' % (w, plain_codes or '无'))
            if verbose:
                print('  warn/hint: %s' % (plain_codes or '-'))

        checked += 1
        if problems:
            print('  FAIL  %-32s %s' % (name, '；'.join(problems)))
            fails.append(name + ' :: ' + '；'.join(problems))
        else:
            print('  ok    %-32s (exit %d)' % (name, rc))

    print('-' * 66)
    print('汇总：%d 个文件，%d 个失败' % (checked, len(fails)))
    if fails:
        print('[FAIL] 自检没通过：')
        for x in fails:
            print('  - ' + x)
        return 1
    print('[OK] 全部符合预期（linter 的 error 码与 md2pdf 内置校验器一致）。')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
