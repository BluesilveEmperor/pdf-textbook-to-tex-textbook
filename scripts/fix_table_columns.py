#!/usr/bin/env python3
r"""fix_table_columns.py — 表格列格式 l → c（所有表格中的值居中）。

pandoc 初转的表格列格式默认左对齐（\begin{longtable}[]{@{}ll@{}}）。
项目编码规范：所有表格中的值一律居中，本脚本把列格式参数中的 l
替换为 c（r / p{...} 等其他列说明符保留不动）。

范围与安全性：
    * 只改 \begin{tabular} / \begin{longtable}（含 * 变体）的可选参数
      之后的列格式组（如 {@{}ll@{}}），正文与公式不受影响；
    * p{...} 列（宽度含 {} 嵌套）内部不替换，先保护再还原；
    * 幂等，可重复运行。

用法：
    python fix_table_columns.py [项目根目录]    # 默认当前目录
"""
import os, re, sys

# \begin{tabular/longtable} 行：可选参数 [] + 列格式组（允许 p{...} 一层嵌套）
BEGIN_RE = re.compile(
    r'(\\begin\{(?:longtable|tabular)\*?\}(?:\[[^\]]*\])?\{)'
    r'((?:[^{}]|\{[^{}]*\})*)'
    r'(\})'
)
# p 列保护：宽度参数内部不替换
PCOL_RE = re.compile(r'([pP]\{[^{}]*\})')


def fix_column_spec(spec):
    parts = PCOL_RE.split(spec)
    return ''.join(
        p if p.startswith(('p{', 'P{')) else p.replace('l', 'c')
        for p in parts
    )


def fix(text):
    n = 0

    def repl(m):
        nonlocal n
        new_spec = fix_column_spec(m.group(2))
        if new_spec != m.group(2):
            n += 1
        return m.group(1) + new_spec + m.group(3)

    return BEGIN_RE.sub(repl, text), n


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    root = os.path.abspath(root)

    tex_files = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ('tmp_work', 'build_work', 'build', '.git')]
        for f in files:
            if f.endswith('.tex'):
                tex_files.append(os.path.join(dirpath, f))

    total = 0
    for fp in sorted(tex_files):
        with open(fp, 'r', encoding='utf-8') as fh:
            content = fh.read()
        new, n = fix(content)
        if new != content:
            with open(fp, 'w', encoding='utf-8') as fh:
                fh.write(new)
            print(f'  {os.path.relpath(fp, root)}: 改写 {n} 个表格列格式')
        total += n

    print(f'\n共 {len(tex_files)} 个 .tex 文件，改写 {total} 个表格列格式（l -> c）')
    print('（r / p{...} 等其他列说明符保留；改写后须重编译验证）')


if __name__ == '__main__':
    main()