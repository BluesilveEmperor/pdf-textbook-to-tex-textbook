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
    python compile_tex.py [项目根] [--engine xelatex|lualatex|绝对路径] [--passes N]
                          [--jobname main] [--clean-only]

默认：项目根 = 当前目录；引擎 = xelatex；最多 3 遍。

引擎定位（重要）
----------------
本机实测：TeX Live 可能**不在 PATH**（如装在 D:\texlive\2026\bin\windows）。
因此 `--engine` 既接受引擎名，也接受引擎可执行文件的绝对路径；
若只给名字，脚本按「PATH -> 常见安装根目录」顺序自动定位，
并把引擎所在目录注入子进程 PATH（TeX Live 的 DLL 与辅助程序同目录）。
"""
import argparse, os, re, shutil, subprocess, sys

# 引擎自动定位的候选根目录（跨盘、跨发行版）
ENGINE_ROOT_CANDIDATES = [
    r'C:\texlive', r'D:\texlive', r'E:\texlive', r'F:\texlive',
    r'C:\Program Files\MiKTeX', r'D:\Program Files\MiKTeX',
    os.path.expanduser(r'~\AppData\Local\Programs\MiKTeX'),
]
# TeX Live 年份目录下的 bin 子目录名
TL_BIN_SUBDIRS = ['windows', 'win32', 'x86_64-windows']


def resolve_engine(name):
    """把引擎名或路径解析为可执行文件的绝对路径。返回 (exe, bin_dir)。"""
    # 1) 已给绝对/相对路径
    if os.path.sep in name or '/' in name:
        exe = os.path.abspath(name)
        if os.path.isfile(exe):
            return exe, os.path.dirname(exe)
        if os.path.isfile(exe + '.exe'):
            return exe + '.exe', os.path.dirname(exe)
        sys.exit(f'[FAIL] 找不到引擎：{name}')

    # 2) PATH
    found = shutil.which(name)
    if found:
        return found, os.path.dirname(found)

    # 3) 常见安装根目录
    for root in ENGINE_ROOT_CANDIDATES:
        if not os.path.isdir(root):
            continue
        # MiKTeX 布局：<root>\miktex\bin\x64\<engine>.exe
        for sub in [r'miktex\bin\x64', r'miktex\bin', r'bin'] + \
                   [os.path.join(y, b) for y in ('2025', '2026', '2024')
                    for b in TL_BIN_SUBDIRS]:
            cand = os.path.join(root, sub, name + '.exe')
            if os.path.isfile(cand):
                return cand, os.path.dirname(cand)
        # TeX Live 布局：<root>\<year>\bin\<bin-subdir>\<engine>.exe
        for y in sorted(os.listdir(root), reverse=True):
            for b in TL_BIN_SUBDIRS:
                cand = os.path.join(root, y, 'bin', b, name + '.exe')
                if os.path.isfile(cand):
                    return cand, os.path.dirname(cand)

    sys.exit(f'[FAIL] 未在 PATH 与常见安装目录中找到 {name}，请用 --engine <绝对路径> 指定')

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
    ap.add_argument('--engine', default='xelatex',
                    help='引擎名（xelatex/lualatex）或其可执行文件绝对路径')
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
    exe, bin_dir = resolve_engine(args.engine)
    os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')
    print(f'引擎：{exe}')
    # ⚠️ `-output-directory` 必须用**相对路径** `build`，不能用绝对路径。
    # TeX Live 2026 的 xelatex 会把该值 putenv 成 TEXMF_OUTPUT_DIRECTORY，
    # 而 Windows CRT 的 putenv 无法接受含中文的绝对路径 —— 表现为
    #   xelatex.exe: fatal: putenv(TEXMF_OUTPUT_DIRECTORY=D:\...\研一数学\...\build)
    # 返回码 1，且 .log 里**没有任何 "!" 错误行**（日志看起来还是成功的），
    # 极易误判。因为本脚本固定 cwd=项目根，相对路径与绝对路径等价，且天然规避该问题。
    cmd = [exe, '-interaction=nonstopmode',
           '-output-directory=build', args.jobname + '.tex']

    for i in range(1, args.passes + 1):
        print(f'=== 第 {i}/{args.passes} 遍（{os.path.basename(exe)}）===')
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
            # 返回码非 0 但日志里没有 "!" 错误行时，多半是引擎自身的 shell 层问题
            # （编码/管道/权限），把 stdout/stderr 尾部与日志尾部一起打出来定位。
            print(f'  [FAIL] 编译返回码 {r.returncode}，错误 {n_err} 个')
            if n_err == 0:
                tail = '\n'.join(log.split('\n')[-15:])
                print('  --- 日志尾部 ---\n' + tail)
                print('  --- stderr 尾部 ---\n' + (r.stderr or '')[-1000:])
                print('  --- stdout 尾部 ---\n' + (r.stdout or '')[-1000:])
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