#!/usr/bin/env python3
r"""fix_math_delimiters.py — 统一公式定界符：行内 $...$、行间 $$...$$。

pandoc 把 Markdown 的 $...$ / $$...$$ 转成 LaTeX 的 \(...\) / \[...\]。
项目编码规范要求源码统一用美元符号定界，本脚本做回替换：
    \( ... \)  ->  $ ... $     （行内公式）
    \[ ... \]  ->  $$ ... $$   （行间公式）

关键细节：用负向后行断言 (?<!\\) 排除 \\[2pt]（换行命令 + 行距可选参数）
中第 2 个反斜杠被误当作 \[ 定界符的情况——这是此替换唯一的隐蔽坑。

amsmath 环境（equation / align / gather 等）不是"符号包裹"形式，
不受本规则约束，脚本不触碰。

用法：
    python fix_math_delimiters.py [项目根目录]    # 默认当前目录
"""
import os, re, sys

# 负向后行断言：定界符的反斜杠前不能紧跟另一个反斜杠
INLINE_OPEN  = re.compile(r'(?<!\\)\\\(')
INLINE_CLOSE = re.compile(r'(?<!\\)\\\)')
DISP_OPEN    = re.compile(r'(?<!\\)\\\[')
DISP_CLOSE   = re.compile(r'(?<!\\)\\\]')

# 已知会误替换的写法（pandoc 不会产出，但 OCR 源可能出现）：
# \left\[ / \right\] 中的字面 \[ \] 前是普通字母，断言无法排除
WARN_PATTERNS = [
    (re.compile(r'\\left\\\[|\\right\\\]'), r'\left\[ \right\]（应写 \left[ \right]）'),
]

def fix(text):
    text = INLINE_OPEN.sub('$', text)
    text = INLINE_CLOSE.sub('$', text)
    text = DISP_OPEN.sub('$$', text)
    text = DISP_CLOSE.sub('$$', text)
    return text

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    root = os.path.abspath(root)

    tex_files = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ('tmp_work', 'build_work', 'build', '.git')]
        for f in files:
            if f.endswith('.tex'):
                tex_files.append(os.path.join(dirpath, f))

    total_inline = total_disp = 0
    for fp in sorted(tex_files):
        with open(fp, 'r', encoding='utf-8') as fh:
            content = fh.read()

        n_inline = len(INLINE_OPEN.findall(content)) + len(INLINE_CLOSE.findall(content))
        n_disp = len(DISP_OPEN.findall(content)) + len(DISP_CLOSE.findall(content))

        # 预检查：已知会误替换的写法
        for pat, desc in WARN_PATTERNS:
            m = pat.findall(content)
            if m:
                print(f'  [WARN] {os.path.relpath(fp, root)}: 含 {len(m)} 处 {desc}，'
                      f'请先手工改写为 \\left[ / \\right] 再重跑')

        new = fix(content)
        if new != content:
            with open(fp, 'w', encoding='utf-8') as fh:
                fh.write(new)
            print(f'  {os.path.relpath(fp, root)}: 行内 {n_inline} 处, 行间 {n_disp} 处')
        total_inline += n_inline
        total_disp += n_disp

    print(f'\n共 {len(tex_files)} 个 .tex 文件，'
          f'替换行内 {total_inline} 处、行间 {total_disp} 处')
    print('（amsmath 环境 equation/align 等不在替换范围）')

if __name__ == '__main__':
    main()