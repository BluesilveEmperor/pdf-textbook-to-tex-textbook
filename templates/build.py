# -*- coding: utf-8 -*-
r"""build.py — 自包含一键编译：复制到任何 LaTeX 项目根，python build.py 即可。

取代 compile.bat（硬编码 SKILL_DIR，换机器即坏）与 scripts/compile_tex.py
（依赖 skill 仓库存在、只支持单个 main.tex）。零路径配置、零外部依赖（仅
标准库），两者能力全部内化：

  - 智能文档发现：有 main.tex → 单文档模式（教材场景）；无 main.tex →
    批量编译根目录所有 .tex（不递归，天然排除 chapters/ 子目录），并排除
    被 main.tex input 的 preamble.tex（试卷场景：多份独立试卷）；
  - build/ 隔离：产物只进 build/，根目录零残留；
  - 收敛检测：识别 "Rerun to get cross-references right" 等提示，需要则
    补跑，直到收敛或达到遍数上限（每文档独立循环）；
  - 残留清扫：编译前 + 每遍编译后，按清单清除根目录 <jobname>.* 残留；
  - 引擎定位：显式路径 → PATH → 常见安装根目录（TeX Live/MiKTeX）→ WSL
    候选，找到后把引擎目录原地并入 PATH；
  - 日志诊断：统计 "!" 错误行、页数、undefined 引用；返回码非 0 且日志
    0 错误时，打印日志/stderr/stdout 尾部（putenv 类故障唯一暴露渠道）。

用法：
    python build.py                    # 零参数：自动发现文档 + xelatex + 最多 3 遍
    python build.py --engine lualatex  # 换引擎
    python build.py --passes 5         # 最多 5 遍
    python build.py --clean-only       # 只清扫根目录残留，不编译
    python build.py D:\path\to\proj    # 指定项目根（默认脚本所在目录）

项目根默认 = 本脚本所在目录（双击、从任意 cwd 调用都指向正确目录），可用
位置参数改指他处。退出码：全部 OK=0；任一失败/异常=1（单文档模式失败
立即退出，退出码=引擎返回码）。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

# 项目根默认值：本脚本所在目录
HERE = os.path.dirname(os.path.abspath(__file__))
# 引擎自动定位：常见安装根目录（跨盘、跨发行版）
ENGINE_ROOT_CANDIDATES = [
    r'C:\texlive', r'D:\texlive', r'E:\texlive', r'F:\texlive',
    r'C:\Program Files\MiKTeX', r'D:\Program Files\MiKTeX',
    os.path.expanduser(r'~\AppData\Local\Programs\MiKTeX')]
# TeX Live 年份目录下的 bin 子目录名
TL_BIN_SUBDIRS = ['windows', 'win32', 'x86_64-windows']
# WSL 候选目录（赣州版经验：脚本跑在 WSL/Linux 内，或经 /mnt 访问）
WSL_BIN_CANDIDATES = ['/mnt/d/texlive/2026/bin/windows',
                      '/usr/local/bin', '/usr/bin']
# 根目录残留清理清单：<jobname> 后缀（build/ 内同名文件不动）
RESIDUAL_EXTS = ['.aux', '.log', '.out', '.toc', '.pdf', '.fls', '.synctex',
                 '.synctex.gz', '.fdb_latexmk', '.xdv', '.blg', '.bbl']
# 真实的"需要再跑一遍"信号（官方提示，非包名误报）
RERUN_RE = re.compile(r'Rerun to get cross-references right|'
                      r'Label\(s\) may have changed|Rerun to get outlines right')
# 页数摘要
PAGES_RE = re.compile(r'Output written on \S+ \((\d+) pages?')
# undefined 引用计数
UNDEF_RE = re.compile(r'There were undefined references')


def resolve_engine(name):
    """把引擎名或路径解析为可执行文件的绝对路径。返回 (exe, bin_dir)。"""
    # 1) 显式路径（含分隔符），找不到时补 .exe 再试
    if os.path.sep in name or '/' in name:
        exe = os.path.abspath(name)
        for cand in (exe, exe + '.exe'):
            if os.path.isfile(cand):
                return cand, os.path.dirname(cand)
        sys.exit(f'[FAIL] 找不到引擎：{name}')
    # 2) PATH
    found = shutil.which(name)
    if found:
        return found, os.path.dirname(found)
    # 3) 常见安装根目录（TeX Live 可能不在 PATH，如 D:\texlive\2026\bin\windows）
    for root in ENGINE_ROOT_CANDIDATES:
        if not os.path.isdir(root):
            continue
        # MiKTeX 布局：<root>\miktex\bin\x64\<engine>.exe
        for sub in [r'miktex\bin\x64', r'miktex\bin', 'bin'] + \
                   [os.path.join(y, b) for y in ('2025', '2026', '2024')
                    for b in TL_BIN_SUBDIRS]:
            cand = os.path.join(root, sub, name + '.exe')
            if os.path.isfile(cand):
                return cand, os.path.dirname(cand)
        # TeX Live 布局：<root>\<year>\bin\<bin-subdir>\<engine>.exe（年份逆序）
        for y in sorted(os.listdir(root), reverse=True):
            for b in TL_BIN_SUBDIRS:
                cand = os.path.join(root, y, 'bin', b, name + '.exe')
                if os.path.isfile(cand):
                    return cand, os.path.dirname(cand)
    # 4) WSL 候选（/mnt 下为 Windows 版引擎带 .exe；/usr 下为 Linux 版）
    for d in WSL_BIN_CANDIDATES:
        for cand in (os.path.join(d, name), os.path.join(d, name + '.exe')):
            if os.path.isfile(cand):
                return cand, os.path.dirname(cand)
    sys.exit(f'[FAIL] 未在 PATH 与常见安装目录中找到 {name}，'
             f'请用 --engine <绝对路径> 指定')


def discover_docs(root):
    """发现待编译文档。返回 (jobname 列表, 是否单文档模式)。

    有 main.tex → 单文档模式；无 → 批量模式：根目录所有 .tex
    （os.listdir 不递归，天然排除 chapters/ 等子目录），但排除
    preamble.tex——被 main.tex input 的导言文件，单独编译必失败。
    """
    texs = sorted(f for f in os.listdir(root) if f.endswith('.tex'))
    main_name = next((f for f in texs if f.lower() == 'main.tex'), None)
    if main_name:
        return [main_name[:-4]], True
    return [f[:-4] for f in texs if f[:-4].lower() != 'preamble'], False


def clean_root(root, jobname):
    """清除项目根的 <jobname>.<ext> 残留，返回删除数。build/ 内不动。"""
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
    """读取 build/<jobname>.log 全文；不存在返回空串。"""
    log = os.path.join(build_dir, jobname + '.log')
    if not os.path.isfile(log):
        return ''
    with open(log, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def count_errors(log):
    """统计日志中 "!" 开头的错误行数（len>1 排除孤立的 "!"）。"""
    return sum(1 for ln in log.split('\n')
               if ln.strip().startswith('!') and len(ln.strip()) > 1)


def _result(ok, pages, errors, log, returncode):
    """组装 compile_one 的结果 dict（undef 从最终日志统计）。"""
    return {'ok': ok, 'pages': pages, 'errors': errors,
            'undef': len(UNDEF_RE.findall(log)), 'returncode': returncode}


def compile_one(exe, root, jobname, max_passes):
    """编译单个文档至收敛（最多 max_passes 遍）。

    返回 dict：ok / pages / errors / undef / returncode。
    """
    build_dir = os.path.join(root, 'build')
    os.makedirs(build_dir, exist_ok=True)
    # 编译前先清扫一次（处理上一次运行的残留）
    n = clean_root(root, jobname)
    if n:
        print(f'  编译前清扫根目录残留 {n} 个文件')

    # ⚠️ `-output-directory` 必须用**相对路径** `build`，不能用绝对路径。
    # TeX Live 2025+ 会把该值 putenv 成 TEXMF_OUTPUT_DIRECTORY，而 Windows
    # CRT 的 putenv 不接受含中文的绝对路径 → fatal + 返回码 1，且 .log 里
    # 没有任何 "!" 错误行（日志看起来还是成功的），极易误判。本脚本固定
    # cwd=项目根，相对路径与绝对路径等价，且天然规避该问题。
    cmd = [exe, '-interaction=nonstopmode',
           '-output-directory=build', jobname + '.tex']

    ok = False
    for i in range(1, max_passes + 1):
        print(f'=== {jobname}：第 {i}/{max_passes} 遍 ===')
        # capture_output 保留排错信息（putenv 类故障的唯一线索在 stderr，
        # 不能像 DEVNULL 那样丢弃）
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        # 每遍之后立即清扫根目录残留（Windows 下 -output-directory 未完全隔离）
        n = clean_root(root, jobname)
        if n:
            print(f'  清扫根目录残留 {n} 个文件')

        log = read_log(build_dir, jobname)
        n_err = count_errors(log)
        m = PAGES_RE.search(log)
        pages = m.group(1) if m else '?'
        rerun = bool(RERUN_RE.search(log))

        if r.returncode != 0:
            # 排查口诀：返回码≠0 且日志 0 错误 → 先看 stderr，别信日志。
            # 这是 putenv 类故障唯一的暴露渠道。
            print(f'  [FAIL] 编译返回码 {r.returncode}，错误 {n_err} 个')
            if n_err == 0:
                print('  --- 日志尾部 ---\n' +
                      '\n'.join(log.split('\n')[-15:]))
                print('  --- stderr 尾部 ---\n' + (r.stderr or '')[-1000:])
                print('  --- stdout 尾部 ---\n' + (r.stdout or '')[-1000:])
            return _result(False, pages, n_err, log, r.returncode)

        print(f'  页数 {pages}，错误 {n_err}，需重跑: {"是" if rerun else "否"}')
        if not rerun:
            ok = True
            break
        if i == max_passes:
            # 返回码与错误数均正常，仅交叉引用未完全收敛，不算失败
            print(f'  [WARN] 已达 {max_passes} 遍仍有重跑提示，请人工检查')
            ok = True

    # 安全网：错误行非 0 或 PDF 未生成，都不算成功
    if n_err > 0 or not os.path.isfile(os.path.join(build_dir, jobname + '.pdf')):
        ok = False
    return _result(ok, pages, n_err, log, r.returncode)


def main():
    ap = argparse.ArgumentParser(
        description='自包含一键编译：自动发现 .tex，产物只进 build/，根目录零残留')
    ap.add_argument('root', nargs='?', default=None,
                    help='项目根（默认：本脚本所在目录）')
    ap.add_argument('--engine', default='xelatex',
                    help='引擎名（xelatex/lualatex）或其可执行文件绝对路径')
    ap.add_argument('--passes', type=int, default=3,
                    help='每个文档最大编译遍数（默认 3）')
    ap.add_argument('--clean-only', action='store_true',
                    help='只清扫根目录残留，不编译')
    args = ap.parse_args()

    root = os.path.abspath(args.root) if args.root else HERE
    if not os.path.isdir(root):
        print(f'[FAIL] 项目根不存在：{root}')
        return 1

    if args.clean_only:
        # 对根目录所有 .tex 的 jobname 逐一清扫（含 preamble.tex——
        # 它若曾被误编译，同样会在根目录留下残留）
        texs = sorted(f for f in os.listdir(root) if f.endswith('.tex'))
        total = sum(clean_root(root, f[:-4]) for f in texs)
        print(f'[OK] 清扫完成，删除根目录残留 {total} 个文件')
        return 0

    if args.passes < 1:
        print('[FAIL] --passes 至少为 1')
        return 1

    docs, single = discover_docs(root)
    if not docs:
        print(f'[FAIL] {root} 下没有可编译的 .tex 文件'
              '（批量模式排除 preamble.tex；子目录不参与发现）')
        return 1

    exe, bin_dir = resolve_engine(args.engine)
    # 把引擎所在目录**原地**并入 os.environ['PATH']（TeX Live 的 DLL 与
    # 辅助程序同目录）。
    # ⚠️ 不要用 subprocess(env=...) 传环境副本：Windows 下 Python 复制的
    # 环境块会丢失 "=C:" 伪变量，破坏子进程的驱动器级相对路径解析
    # （pitfalls.md 陷阱 13 的教训）。
    os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')

    print(f'共 {len(docs)} 个文档，引擎：{exe}')

    results = []
    for jobname in docs:
        res = compile_one(exe, root, jobname, args.passes)
        if res['ok']:
            extra = f'，undefined引用 {res["undef"]}' if res['undef'] else ''
            line = (f'{jobname}: OK (errors={res["errors"]}, '
                    f'pages={res["pages"]}{extra})')
        else:
            line = f'{jobname}: FAIL (errors={res["errors"]})'
        print(f'  {line}')
        results.append((jobname, res))
        if not res['ok'] and single:
            # 单文档模式：失败立即退出，退出码 = 引擎返回码
            sys.exit(res['returncode'] or 1)

    print('\n=== 摘要 ===')
    print(' | '.join(f'{n}: OK' if r['ok'] else f'{n}: FAIL (errors={r["errors"]})'
                     for n, r in results))
    fails = [n for n, r in results if not r['ok']]
    if fails:
        print(f'失败 {len(fails)} 个：{"、".join(fails)}')
        return 1
    print('全部编译成功')
    return 0


if __name__ == '__main__':
    sys.exit(main())