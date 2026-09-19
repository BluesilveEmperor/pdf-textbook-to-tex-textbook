#!/usr/bin/env python3
"""fix_fullwidth.py — 把 LaTeX 项目中所有 .tex 文件的全角符号替换为半角符号。

用法：
    python fix_fullwidth.py [项目根目录]    # 默认当前目录

扫描范围：递归搜索 .tex 文件，排除 tmp_work/、build_work/、build/、.git/ 目录。
替换规则：见下方 FULLWIDTH_MAP（安全替换 + 需转义替换）。
"""
import os, sys, collections

# === 全角→半角映射表 ===

# 安全替换：中文标点，替换后不影响 LaTeX 代码
SAFE_MAP = {
    '\uff0c': ',',   # ，全角逗号
    '\u3002': '.',   # 。全角句号
    '\uff1a': ':',   # ：全角冒号
    '\uff1b': ';',   # ；全角分号
    '\uff1f': '?',   # ？全角问号
    '\uff01': '!',   # ！全角叹号
    '\uff08': '(',   # （全角左括号
    '\uff09': ')',   # ）全角右括号
    '\u201c': '"',   # "左双引号
    '\u201d': '"',   # "右双引号
    '\u2018': "'",   # '左单引号
    '\u2019': "'",   # '右单引号
    '\u3001': ',',   # 、顿号
    '\u2014': '--',  # —破折号
    '\u2026': '...', # …省略号
    '\u3000': ' ',   # 　 全角空格
    '\uff3b': '[',   # ［
    '\uff3d': ']',   # ］
    '\uff1c': '<',   # ＜
    '\uff1e': '>',   # ＞
    '\uff1d': '=',   # ＝
    '\uff0b': '+',   # ＋
    '\uff0d': '-',   # －
    '\uff0a': '*',   # ＊
    '\uff0f': '/',   # ／
    '\uff5c': '|',   # ｜
    '\uff20': '@',   # ＠
}

# 需转义的替换：LaTeX 特殊字符，在文本模式中需转义
ESCAPE_MAP = {
    '\uff05': '\\%',   # ％
    '\uff03': '\\#',   # ＃
    '\uff06': '\\&',   # ＆
    '\uff3f': '\\_',   # ＿
    '\uff3c': '\\textbackslash',  # ＼
    '\uff5b': '\\{',   # ｛
    '\uff5d': '\\}',   # ｝
    '\uff5e': '\\textasciitilde{}',  # ～
    '\uff3e': '\\textasciicircum{}', # ＾
}

ALL_MAP = {}
ALL_MAP.update(SAFE_MAP)
ALL_MAP.update(ESCAPE_MAP)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    root = os.path.abspath(root)

    # 收集 .tex 文件
    tex_files = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ('tmp_work', 'build_work', 'build', '.git')]
        for f in files:
            if f.endswith('.tex'):
                tex_files.append(os.path.join(dirpath, f))

    # 扫描 + 替换
    all_counts = collections.Counter()
    total_replaced = 0
    for filepath in sorted(tex_files):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        original = content
        for full, half in ALL_MAP.items():
            content = content.replace(full, half)
        if content != original:
            n = sum(original.count(k) for k in ALL_MAP)
            total_replaced += n
            all_counts.update({k: original.count(k) for k in ALL_MAP if original.count(k) > 0})
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            rel = os.path.relpath(filepath, root)
            print(f'  {rel}: {n}')

    # 汇总
    print(f'\n共 {len(tex_files)} 个 .tex 文件，替换 {total_replaced} 个全角符号')
    if all_counts:
        print('明细：')
        for ch, count in sorted(all_counts.items(), key=lambda x: -x[1]):
            print(f'  {ch!r} ({ord(ch):04X}) -> {ALL_MAP[ch]!r}  x{count}')


if __name__ == '__main__':
    main()