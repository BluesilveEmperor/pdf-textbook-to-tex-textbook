# 编译与排错手册

> 本文档解决什么问题：给出从"章文件都写好了"到"拿到成品 PDF"的编译流程，以及一套**有优先级顺序**的排错方法——遇到满屏报错时先做什么、哪些报错是假的、哪些现象必须清 build 重编。

## 1. 编译命令

**推荐：统一编译入口脚本**（自动补跑收敛 + 自动清扫根目录残留）：

```powershell
python scripts/compile_tex.py <项目根>                # xelatex，最多 3 遍
python scripts/compile_tex.py <项目根> --engine lualatex   # OCR 严重、xelatex 报字体内部错误的书
python scripts/compile_tex.py <项目根> --clean-only    # 只清扫根目录残留，不编译
```

脚本固定带 `-output-directory=build`（杜绝漏参数）、每遍后按清单清除根目录 `<jobname>.aux/.log/.out/.toc/.pdf/.synctex*/.fdb_latexmk/.fls` 残留、检测官方 `Rerun` 提示自动补跑，结尾输出页数/错误/undefined 摘要。

**手工编译**（无法用脚本时）——工作目录 = 项目根（`main.tex` 所在目录）：

```powershell
xelatex -interaction=nonstopmode -output-directory=build main.tex
```

| 参数 | 作用 |
|---|---|
| `xelatex` | 必须用 XeLaTeX（`ctexbook` + `fontset=windows` 走系统字体） |
| `-interaction=nonstopmode` | 遇错不中断，把全部日志打完（便于一次性看到所有问题） |
| `-output-directory=build` | 所有产物（pdf / aux / toc / out / log）只进 `build/`，项目根保持干净 |

排查单个疑难错误时，可临时加 `-halt-on-error` 只停在第一个错误：

```powershell
xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
```

⚠️ **"产物只进 build/"的两个已知漏洞**（脚本已内置修复，手工编译时须人工兜底）：

1. **忘加参数**：手工跑 `xelatex main.tex` 漏掉 `-output-directory=build`，全套产物散落项目根；
2. **未完全隔离**：Windows 下即使带参数，根目录仍可能出现 `synctex` / `fdb_latexmk` / `fls` 等零散残留。

根目录残留的陈旧 aux/log 会误导后续诊断（误读上次错误、引发 aux 连锁假报错，见陷阱 1）。手工编译后必须按 `acceptance-checklist.md` §4.1 清单核对清理。

## 2. 为什么要"连跑 2–3 遍"

LaTeX 是**多趟收敛**的排版系统：

| 趟次 | 写入/读取 |
|---|---|
| 第 1 遍 | 生成 `main.aux`（标签位置）与 `main.toc`（目录条目） |
| 第 2 遍 | 读回 aux/toc → 目录条目落位、`\cref` 解析成正确编号 |
| 第 3 遍 | 页码/条目长度变化可能再次影响目录 → 再收敛一次 |

**判据**：日志末尾若出现官方提示

```
LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.
```

或

```
Package rerunfilecheck Warning: File `main.out' has changed. Rerun to get outlines right.
```

就**必须再跑一遍**，直到提示消失、`undefined` 归零。

约定：**结构改动后固定连跑 2–3 遍**，别去数"到底要几遍"。

## 3. 排错优先级顺序（关键）

遇到满屏报错时，**不要从第一条开始逐条改源码**。按下面顺序处理，能消掉 80% 的"看起来很多"的错误：

```
① 先排除 aux 损坏  ── 清空 build/ 干净重编，看还剩什么错
        │           （aux 损坏会制造大量虚假连锁错误）
        ▼
② 再查结构        ── chapter 是否齐全？toc 章数对不对？编号是 0.x 吗？
        │           （这类问题零报错，但结果全错）
        ▼
③ 再查环境嵌套    ── \begin/\end 是否配对？（ended by \end{document} 类错误）
        ▼
④ 最后查公式 OCR  ── Missing $ / Bad math delimiter / 无效字符
```

理由：①②③④ 的错误会互相掩盖。aux 损坏导致的 `\@newl@bel` 报错会淹没真实的源码错误；结构错误（漏 `\chapter`）根本不报警，却让后面所有编号对不上；环境未闭合会让"第一个真实的公式错误"出现在几百行之后。

## 4. 常见错误 —— 现象 / 根因 / 对策

| 现象（日志关键词） | 根因 | 对策 |
|---|---|---|
| `\@newl@bel`、`\@@BOOKMARK`、`Text line contains an invalid character` 连锁报错 | `build/main.aux`（或 `.out`）来自**旧参数/旧结构**，与当前源码不匹配 | **清空 `build/` 目录**（或至少删 `main.aux`、`main.out`、`main.toc`）后干净重编 |
| `! LaTeX Error: \begin{xxx} on input line N ended by \end{document}.` | 某个 `\begin{theorem}` / `\begin{proof}` / `\begin{corollary}` / `\begin{remark}` 缺对应 `\end` | 用配对检查脚本定位（见 §7），补齐闭合标签。注意连锁：**只补第一个真正缺失的 `\end`**，后面的报错往往自动消失 |
| `! Undefined control sequence.` | ① 用了 preamble 没加载的宏包命令；② pandoc 3.x 的 `\pandocbounded` 未定义 | `mathrsfs`（`\mathscr`）、`xcolor`（`\textcolor`）、`\providecommand{\pandocbounded}[1]{#1}` 三件套是否齐全 |
| `! Missing $ inserted.` | 数学符号出现在文本模式（OCR 把 `$`、`_`、`>` 丢出数学环境） | 回原文把该片段包回 `\( … \)`；批量处理见 `stage2-chapter-conversion.md` §7 |
| `! LaTeX Error: Bad math environment delimiter.` | `$` 与 `\(` 混用、定界符不配对 | 统一改为 `\( … \)` / `\[ … \]`，检查该段落定界符配对 |
| `! Package inputenc Error: Unicode character … not set up`（XeLaTeX 下较少见） | 源码里有异常 Unicode 字符 | 定位该字符（多为 OCR 噪声），替换或删除 |
| `Overfull \hbox (…)` | 长行内公式不自动换行，文本区窄 | 按 §6 分级：可忽略 / 需修 |
| `LaTeX Font Warning: Font shape 'U/rsfs/m/n' … not available` | `mathrsfs` 在某些字号下无对应字模，自动替换 | 不影响正确性；同一字体家族会有 `Size substitutions` 汇总提示 |
| `Missing character: There is no ■ (U+25A0) in font [lmroman12-regular]` | OCR 把符号（■□∃λ∈⇒≠①②…）作为 **Unicode 字符**留在正文/数学模式，当前字体无此字形 | 换成 LaTeX 命令（`\blacksquare`、`\lambda`、`\exists`…）或用 `\text{}` + 支持该字形的字体；数量多时优先只修正文可见处 |

## 5. 日志误报识别（别被 grep 骗了）

日志里有些"看起来是问题"的行其实是**信息行或包名匹配**：

| 日志原文 | 真相 |
|---|---|
| `Package pdftexcmds Info: \pdfdraftmode not found.` | `pdftexcmds` 包的**信息行**，描述它探测某个引擎原语的结果——不是"文件找不到" |
| `Package: rerunfilecheck 2025-06-21 v1.11 Rerun checks for auxiliary files` | 包**加载记录**；用 `grep rerun` 会把包名 `rerunfilecheck` 也匹配进来 |
| `LaTeX Font Warning: Size substitutions with differences` | 字体自动缩放替换的**汇总提示**，不是错误 |

**真正需要响应的 rerun 提示**是官方那两句明确的：

```
LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.
Package rerunfilecheck Warning: File `main.out' has changed. Rerun to get outlines right.
```

**经验法则**：判断"是否有错"不要只看 `grep -c Warning` 的计数，而要看三类硬信号——

1. `! …` 开头的 TeX 错误；
2. `LaTeX Warning: …undefined` / `Reference … undefined`；
3. 日志末尾的 `Output written on build/main.pdf (N pages).`（有这行才说明产出了 PDF）。

本项目两份成品日志的真实分布（供对照，说明"有告警 ≠ 有错误"）：

| 类别 | 点集拓扑 | 泛函分析 |
|---|---|---|
| TeX 错误（`!`） | 0 | 0 |
| `Overfull \hbox` | 0 | 3 |
| `Underfull \hbox/\vbox` | 13 | 9 |
| `Missing character` | 20 | 191 |

（`Missing character` 偏多的那本，多为数学模式内残留的 Unicode 符号，属**待校对项**而非编译失败项。）

## 6. Overfull 的分级判据

`Overfull \hbox` 是收窄边距后最值得关注的告警。**按溢出量级分级**：

| 溢出量 | 判定 | 处理 |
|---|---|---|
| ≤ 4pt （如 `0.57944pt`、`2–4pt`） | 视觉不可见 | 可忽略，不必处理 |
| 明显超出但 < 页边距宽度 | 会顶进边距，通常仍可见 | 可接受，但建议在源公式处换行/断行优化 |
| **> 页边距宽度（左右 2.2cm ≈ 62pt）** | **内容会被裁切丢失** | **必须**定位到具体行修复（拆分长公式 / 用 `aligned` / `\allowdisplaybreaks`） |

本项目实例：泛函分析日志中有 3 处 Overfull，分别为 `0.57944pt`（可忽略）、`12.11221pt`（需优化）、`49.93639pt`（接近但仍小于 2.2cm 页边距宽度，须定位）。

定位方法：日志里 Overfull 行会给出**输入行号**，例如

```
Overfull \hbox (12.11221pt too wide) detected at line 2360
```

但注意行号是**当前正在处理的 `.tex` 文件**的行号——可能是 `chapters/chNN.tex` 而非 `main.tex`，要结合上下文确认所属章文件。

全局缓解手段：`\setlength{\emergencystretch}{3em}`（preamble 已配置）能消除大部分轻微 Overfull；它消除不了的才是真问题。

## 7. 结构与环境配对的机械核查

编译告警"0 错误"**不等于**结构正确。用两个小脚本做机械核查（真实可用的做法）：

**环境配对**（检查每章 `\begin`/`\end` 计数）：

```python
# check_env.py
import re, glob
from collections import Counter
for f in glob.glob('chapters/*.tex'):
    s = open(f, encoding='utf-8').read()
    b = Counter(re.findall(r'\\begin\{(\w+)\}', s))
    e = Counter(re.findall(r'\\end\{(\w+)\}', s))
    diffs = {k: b[k]-e[k] for k in set(b)|set(e) if b[k] != e[k]}
    if diffs:
        print(f, diffs)
```

**花括号平衡**（检查每个 `\( … \)` / `\[ … \]` 片段内部括号是否配对）：

```python
# check_braces.py（核心）
def brace_balance(s):
    s = re.sub(r"\\[{}]", "", s)      # 去掉转义括号 \{ \}
    return s.count("{") - s.count("}")
```

两条核查应在**每次改完章文件后**运行，比读编译日志快得多。

## 8. 必须清 `build/` 重编的场景清单

只要**改动影响 aux/toc/out 的内容或解释方式**，就必须清空 `build/` 重新编译。清单：

1. 修改 `\documentclass` 选项（含 `openany`、`zihao`、`fontset`）；
2. 修改 `geometry` 页面参数（边距、`headsep`、`footskip`）；
3. 修改 `\newtheorem` / 计数器设计 / `\theoremstyle`；
4. 增删 `\chapter`、调整章顺序、增删章文件；
5. 修改 `\crefname` / hyperref 设置 / `\bookinfo`；
6. 出现 `\@newl@bel`、`\@@BOOKMARK`、`Text line contains an invalid character` 类连锁错误时（先清再看）；
7. 换机器/换 TeX Live 版本后首次编译（aux 格式可能不兼容）。

清空方式（只清产物，不动源码）：

```powershell
Remove-Item build\* -Recurse -Force
```

> 注意：`build_work/` 或 `tmp_work/` **不要清**——那里放的是转换脚本、`prep_NN.md`、`chNN_raw.tex`、`stats_NN.json`，是重跑转换所需的工作区，不是编译产物。

## 9. 编译通过后的确认动作

```powershell
# 1) 无 TeX 错误
findstr /C:"! " build\main.log
# 2) 无 undefined
findstr /I "undefined" build\main.log
# 3) 确认真有产出
findstr /C:"Output written on" build\main.log
```

`Output written on build/main.pdf (N pages).` 是"确实生成了 PDF"的唯一硬证据。**不要用"PDF 文件存在"当作编译成功的证明**——它可能是上一次编译的残留。
