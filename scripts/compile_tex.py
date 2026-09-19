#!/usr/bin/env python3
r"""compile_tex.py — 统一编译入口：产物只进 build/，根目录零残留。

修复两个已知漏洞：
  1. 手工敲 xelatex main.tex 忘加 -output-directory=build → 全套产物散落项目根；
  2. Windows 下 -output-directory 未完全隔离，根目录仍可能出现
     synctex / fdb_latexmk / fls 等零散残留。

做法：
  - 命令由本脚本拼装，-output-directory=build 固定带上（无法忘加）；
  - 每遍编译后自动扫描项目根，按清单清除 <jobname>.* 残留
    （aux/log/out/toc/pdf/synctex/fdb/fls），build/ 内同名文件不动；
  - 自动检测 "Rerun to get cross-references right" 并补跑，直到收敛
    或达到遍数上限；结尾输出页数与错误计数摘要。

用法：
    python compile_tex.py [项目根] [--engine xelatex|lualatex] [--passes N]
                          [--jobname main] [--clean-only]

默认：项目根 = 当前目录；引擎 = xelatex；最多 3 遍。
"""
import argparse, os, re, subprocess, sys

# 根目录残留清理清单：<jobname> 后缀（不含扩展名分隔符）
RESIDUAL_EXTS = [
    '.aux', '.log', '.out', '.toc', '.pdf', '.fls',
    '.synctex', '.synctex.gz', '.fdb_latexmk', '.xdv', '.blg', '.bbl',
]

# 真实的"需要再跑一遍"信号（官方提示，非包名误报）
RERUN_RE = re.compile(
    r'Rerun to get cross-references right|Label\(s\) may have changed|'
    r'Rerun to get outlines right')
# 页数摘要
PAGES_RE = re.compile(r'Output written on \S+ \((\d+) pages?')


def clean_root(root, jobname):
    """清除项目根的 <jobname>.<ext> 残留，返回删除数。build/ 不动。"""
    removed = 0
    for ext in RESIDUAL_EXTS:
        p = os.path.join(root, jobname + ext)
        if os.path.isfile(p):
            try:
                os.remove(p)
                removed += 1
            except OSError as e:
                print(f'  [WARN] 无法删除 {p}: {e}')
    return removed


def read_log(build_dir, jobname):
    log = os.path.join(build_dir, jobname + '.log')
    if not os.path.isfile(log):
        return ''
    with open(log, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default='.', help='项目根（main.tex 所在目录）')
    ap.add_argument('--engine', default='xelatex', choices=['xelatex', 'lualatex'])
    ap.add_argument('--passes', type=int, default=3, help='最大编译遍数（默认 3）')
    ap.add_argument('--jobname', default='main')
    ap.add_argument('--clean-only', action='store_true', help='只清扫根目录残留，不编译')
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    main_tex = os.path.join(root, args.jobname + '.tex')
    build_dir = os.path.join(root, 'build')

    if not os.path.isfile(main_tex):
        sys.exit(f'[FAIL] 找不到 {main_tex}')

    # 编译前先清扫一次（处理上一次的残留）
    n = clean_root(root, args.jobname)
    if n:
        print(f'编译前清扫项目根残留 {n} 个文件')

    if args.clean_only:
        print('[OK] 清扫完成')
        return

    os.makedirs(build_dir, exist_ok=True)
    cmd = [args.engine, '-interaction=nonstopmode',
           f'-output-directory={build_dir}', args.jobname + '.tex']

    for i in range(1, args.passes + 1):
        print(f'=== 第 {i}/{args.passes} 遍（{args.engine}）===')
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        # 每遍之后立即清扫本遍可能落在根目录的残留（漏洞 2）
        n = clean_root(root, args.jobname)
        if n:
            print(f'  清扫根目录残留 {n} 个文件')

        log = read_log(build_dir, args.jobname)
        n_err = sum(1 for ln in log.split('\n')
                    if ln.strip().startswith('!') and len(ln.strip()) > 1)
        m = PAGES_RE.search(log)
        pages = m.group(1) if m else '?'
        rerun = bool(RERUN_RE.search(log))

        if r.returncode != 0:
            print(f'  [FAIL] 编译返回码 {r.returncode}，错误 {n_err} 个')
            sys.exit(r.returncode)
        print(f'  页数 {pages}，错误 {n_err}，需重跑: {rerun}')

        if not rerun:
            print('=== 收敛，编译完成 ===')
            break
        if i == args.passes:
            print(f'  [WARN] 已达 {args.passes} 遍仍有重跑提示，请人工检查')
    else:
        return

    # 摘要
    final_log = read_log(build_dir, args.jobname)
    n_err = sum(1 for ln in final_log.split('\n')
                if ln.strip().startswith('!') and len(ln.strip()) > 1)
    n_undef = len(re.findall(r'There were undefined references', final_log))
    print(f'\n摘要：页数 {PAGES_RE.search(final_log).group(1) if PAGES_RE.search(final_log) else "?"} | '
          f'错误 {n_err} | undefined引用 {n_undef} | 产物位于 build/，根目录零残留')


if __name__ == '__main__':
    main()