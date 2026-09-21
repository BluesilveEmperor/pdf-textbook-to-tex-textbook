#!/usr/bin/env python3
r"""fix_figure_rows.py — 连续图片并行排布（无文字间隔的图按数量动态并排）。

排版规范：若遇到连续多张图片，且两两图片之间没有任何文字内容，
则将该部分图片尽量并行排布（根据连续图片数量决定每行张数，而非
固定一行两张），避免逐张独占一行造成大片纵向留白。

匹配对象（pandoc/convert.py 产出的图片段落，按空行分块后逐块判定）：
    \pandocbounded{\includegraphics[width=…]{哈希}}
    \includegraphics[width=…]{哈希} 图 21-1        ← 尾随短图题视为图片一部分
    \pandocbounded{\includegraphics[…]{…}} (a) x型区域

改写规则：
    * 连续 N 个纯图片块 → 按 N 动态决定每行张数：
        - 无图题：一行 N 张，各 width=0.95/N\textwidth，\hfill 连接；
        - 有图题：一行 N 张，各 minipage[t]{0.95/N\textwidth}（图 0.9\linewidth，
          图题 \\ 后 \small 居中），minipage 间 \hfill。
      覆盖原 width（原 0.3/0.4 并排多张会溢出版心）。
    * 与文字相隔（非连续）的图片一律不动。
    * 幂等：改写后的并排行是"一行多图"，不再构成"连续空行分隔的
      纯图片块"，重跑无变化。

用法：
    python fix_figure_rows.py [项目根目录]    # 默认当前目录
"""
import os, re, sys

# 单个图片段落（整块只含一张图 + 可选尾随图题）
FIG_RE = re.compile(
    r'^(\\pandocbounded\{)?\\includegraphics(\[[^\]]*\])\{([^}]+)\}(?(1)\})\s*(.*)$'
)
# 图题上限：超过则视为正文段落而非图题（该块不算纯图片块）
CAPTION_MAX = 40


def parse_figure(block):
    """解析纯图片块，返回 (原始文本, 参数组, 文件名, 图题或 None)；非图片块返回 None。"""
    text = block.strip()
    if '\n' in text:
        return None
    m = FIG_RE.match(text)
    if not m:
        return None
    opt, fname, rest = m.group(2), m.group(3), m.group(4).strip()
    caption = rest if rest and len(rest) <= CAPTION_MAX else None
    if rest and caption is None:
        return None  # 尾随长文字 => 正文段落
    return (text, opt, fname, caption)


def set_width(opt, width):
    return re.sub(r'width=[^,\]]+', lambda m: f'width={width}', opt)


def build_row(figs):
    """N 张图合成一行 LaTeX。figs: [(text, opt, fname, caption), ...]"""
    n = len(figs)
    # 每张图分到的版心宽度（含 \hfill 间隙，0.95 是版心占比）
    frac = f'0.95/{n}'
    cells = []
    for _, opt, fname, caption in figs:
        if caption:
            opt2 = set_width(opt, r'0.9\linewidth')
            cells.append(
                '\\begin{minipage}[t]{' + frac + r'\textwidth}\n\\centering\n'
                f'\\pandocbounded{{\\includegraphics{opt2}{{{fname}}}}}\\\\\n'
                f'{{\\small {caption}}}\n'
                '\\end{minipage}'
            )
        else:
            opt2 = set_width(opt, frac + r'\textwidth')
            cells.append(f'\\pandocbounded{{\\includegraphics{opt2}{{{fname}}}}}')
    return '\\hfill\n'.join(cells)


def fix(text):
    """按空行分块，把连续 ≥2 的纯图片块按数量动态并排。返回 (新文本, 改写行数)。"""
    blocks = text.split('\n\n')
    out, n_rows, i = [], 0, 0
    while i < len(blocks):
        info = parse_figure(blocks[i])
        if info is None:
            out.append(blocks[i]); i += 1; continue
        # 收集连续纯图片块
        run = [info]
        j = i + 1
        while j < len(blocks):
            nxt = parse_figure(blocks[j])
            if nxt is None:
                break
            run.append(nxt); j += 1
        if len(run) >= 2:
            out.append(build_row(run)); n_rows += 1
        else:
            out.append(run[0][0])
        i = j
    return '\n\n'.join(out), n_rows


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
            print(f'  {os.path.relpath(fp, root)}: 并排 {n} 行')
        total += n

    print(f'\n共 {len(tex_files)} 个 .tex 文件，并排 {total} 行（按连续图片数量动态并排）')
    print('（非连续图不动；改写后须重编译验证）')


if __name__ == '__main__':
    main()
