# 踩坑经验汇总（十二条）

> 本文档解决什么问题：把这条流水线上**真实踩过**的十二个坑逐条展开——每个坑给出【现象】【根因】【修复】【预防】，让下一个人不用重走一遍。

阅读顺序建议：**陷阱 1、2、3、4、5、11 是"一犯就大范围报废"的，优先记住**（其中 11 是唯一"不报错"的静默缺陷）；6–8 是转换阶段的高频问题；9、10 是"排错方法论"级别的坑，错了会浪费大量时间；12 是排版一致性的后处理步骤。

---

## 陷阱 1：aux 损坏导致满屏连锁报错

**【现象】**
日志里出现大量互相矛盾的错误，典型关键词：

```
\@newl@bel
\@@BOOKMARK
Text line contains an invalid character
```

而且报错行号看起来指向源码里明明没问题的位置，逐条排查永远排不完。

**【根因】**
`build/` 下的 `main.aux`（以及 `main.out` / `main.toc`）是**上一次编译**写下的，记录了当时的标签、页面参数、书签结构。源码改动后，旧 aux 与当前源码不匹配，LaTeX 在下一趟读取旧 aux 时就产生了大量虚假报错。常见触发：改过 `\documentclass` 选项、`geometry`、`\newtheorem`、增删章节。

**【修复】**
**先清空 `build/`，再干净重编译**，然后只看剩下什么错：

```powershell
Remove-Item build\* -Recurse -Force
xelatex -interaction=nonstopmode -output-directory=build main.tex
```

清完之后，原来的"几十条错误"通常只剩 1–2 条**真实**错误。

**【预防】**
- 把"清 build"作为**排错第一步**，而不是最后一步；
- 改动任何全局参数（文档类 / geometry / preamble / 章结构）后，**必须**清 build 重建 aux；
- 交付归档时若保留 aux，需与源码版本一致。

---

## 陷阱 2：零错误 ≠ 结构正确（漏 `\chapter` 退化"第 0 章"）

**【现象】**
编译 **0 错误、0 警告、0 undefined**，但：

- 目录里出现"第 0 章"，或章标题缺失；
- 定理与小节编号变成 `0.1`、`0.2`…；
- 后续所有按章编号的定理/图表编号全部错位。

**【根因】**
`main.tex` 中**漏写 `\chapter{章名}`**。章文件 `chNN.tex` 里只有 `\section` 及以下层级，本应由 `main.tex` 声明章。缺了 `\chapter` 之后，`\section` 直接挂在 chapter 计数器为 0 的位置上——LaTeX 不会为"没有章"报警，因为语法完全合法。

本项目实测：点集拓扑 10 个章文件仅含 `\section`，`main.tex` 未声明 `\chapter`，导致全书内容落在"第 0 章"、编号变 `0.x`。补上 10 个 `\chapter{章名}` 后编号恢复正常（1.1、1.2…），目录完整。

**【修复】**
在 `main.tex` 中为每章补一对结构：

```latex
\chapter{章名}
\input{chapters/chNN}
```

**【预防】**
- **约定：章标题只写在 `main.tex`**，章文件内禁止出现 `\chapter`；
- 验收时机械核对三个数：`main.toc` 的 chapter 条目数 = `main.tex` 的 `\chapter` 数 = `chapters/ch*.tex` 文件数；
- 抽查 aux 中的标签编号首位不为 `0`。

---

## 陷阱 3：前置页多出空白页（`openright` 强制右页起排）

**【现象】**
PDF 中标题页与目录页之间、以及各章之间，出现整页空白。

**【根因】**
`book` / `ctexbook` 文档类**默认 `openright`**：章、目录等大块结构强制从**奇数页（右页）**开始排版。如果上一部分结束在右页，就会插入一个空白页凑到下一个右页。

**【修复】**
给文档类加 `openany`：

```latex
\documentclass[UTF8,a4paper,zihao=-4,fontset=windows,openany]{ctexbook}
```

**【预防】**
- 模板默认就带 `openany`，不要删；
- 只有在**确实想做双面印刷、且接受留白**时才移除它；
- 改完文档类选项后必须清 build 重编（aux 记录了页面结构）。

---

## 陷阱 4：封面多出一行"作者"

**【现象】**
封面上标题下方多出一行文字，内容不是作者名（往往是书名的一部分或某段说明）。

**【根因】**
`\bookinfo{书名}{作者}` 的**第二参数是作者名**，`\maketitle` 会把它排在标题下方。只要书名的场景下，如果第二参数漏写或写成了别的文字，就会原样印到封面上。

**【修复】**
只要书名时**第二参数留空**：

```latex
\bookinfo{《点集拓扑讲义》}{}
```

**【预防】**
- `\bookinfo` 固定按"书名 + 作者"两个参数使用，作者未知就写空花括号；
- 核验封面时把"标题下方是否有多余文字"列为固定检查项。

---

## 陷阱 5：preamble 缺宏包 → `Undefined control sequence`

**【现象】**
编译报 `! Undefined control sequence.`，报错命令多样：`\mathscr`、`\textcolor`、`\pandocbounded`。

**【根因】**
三种典型缺失（都会在**第一次遇到该命令**时才报错，容易被误以为是"某章写错了"）：

| 缺失 | 命令 | 触发源 |
|---|---|---|
| `mathrsfs` | `\mathscr` | MinerU 把花体字母识别成 `\mathscr`（拓扑符号常见） |
| `xcolor` | `\textcolor` | ① 缺图占位 `\textcolor{red}{[缺图 …]}` ② OCR 严重损坏公式的人工标记 |
| `\providecommand{\pandocbounded}[1]{#1}` | `\pandocbounded` | pandoc 3.x 自动给图片套的包裹命令 |

**【修复】**
在 preamble 中补齐：

```latex
\usepackage{mathrsfs}
\usepackage{xcolor}
\providecommand{\pandocbounded}[1]{#1}
```

**【预防】**
- 把这三项作为模板的**固定组成**，不做删减；
- `\pandocbounded` 一律用 `\providecommand`（而非 `\newcommand`），以免与 pandoc 未来版本的自动定义冲突；
- 冒烟测试必须覆盖 `\mathscr`、`\textcolor`、一张图片，把缺失暴露在模板阶段而不是逐章阶段。

---

## 陷阱 6：环境嵌套断裂

**【现象】**
报错形如：

```
! LaTeX Error: \begin{remark} on input line N ended by \end{document}.
```

一处断裂，后面可能出现几十条连锁错误。

**【根因】**
某个 `\begin{theorem}` / `\begin{proof}` / `\begin{corollary}` / `\begin{remark}` **缺对应 `\end`**。LaTeX 一直把后续内容当作该环境的内容，直到 `\end{document}` 也没等来闭合标签。

本项目实测：泛函分析第 4 章中 `\begin{theorem}` / `\begin{proof}` / `\begin{corollary}` / `\begin{remark}` 多处缺 `\end`，导致 `\begin{remark} … ended by \end{document}` 连锁错误。

**【修复】**
1. 用机械脚本定位：

```python
# check_env.py：比较每章 \begin{env} 与 \end{env} 的计数
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

2. **只补第一个真正缺失的 `\end`**——后面的报错往往自动消失；
3. 补完后重跑 `check_env.py` 确认为空。

**【预防】**
- 自动转换时的环境开合必须**成对生成**（开一个就记一个栈，收尾强制闭合），不要依赖"下一个标题会自然闭合"；
- 每次改完章文件先跑 `check_env.py`，比读编译日志快得多；
- 转换脚本里"闭合当前环境"应作为**遇到任何结构头（新标题 / 新定理头 / 习题区）时的强制动作**。

---

## 陷阱 7：OCR 公式错误

**【现象】**
公式与原文不符、编译报数学模式错误，或编译内存异常膨胀。

**【根因】**
扫描图像型 PDF 靠 OCR/VLM 识别，公式错误属**预期**。本项目实测高频类型：

| 类型 | 实例 |
|---|---|
| 花体字母退化为变量 | `\var D`（应为 `\mathcal{D}`） |
| 伪命令 | `\itOmega`、`\itmathbb` |
| 符号落进文本模式 | `\$`、`\_`、`\textgreater{}` 出现在正文 |
| 竖线被拆成文本命令 | `(\mathcal{X}, \textbar{} \cdot \textbar)` |
| `\boldsymbol` 过度嵌套 | `\boldsymbol{\boldsymbol{\boldsymbol{\boldsymbol{v}}}}` → 编译内存膨胀 |
| 重复公式编号 | `\tag{3.5.5}\tag{3.5.5}` |
| `array` 层级错乱 / 定界符错位 | 多层 `array` 包裹、`\$\mu \_ \{ j \} 0 ( j \$ \(\infty )\)` |

**【修复】**
- 逐处对照原书定点修复（精确字符串替换，脚本写成**幂等**的：找不到就 `[SKIP]` 打印）；
- 常见映射：`\var D`→`\mathcal{D}`；`\textbar{} \cdot \textbar`→`\|\cdot\|`；`\textgreater{}`→数学模式 `>`；
- **严重损坏、无法一次修好的公式**不要臆造，改为显式标记留待人工校对：
  ```latex
  % TODO: 公式 OCR 严重损坏, 待人工对照原书校对
  \textcolor{red}{\textbf{[此处公式 OCR 严重损坏, 待人工校对]}}
  ```
- 换过解析模型的分块要**重点校对**：本项目中被 `pipeline` 模型救回的某段（泛函分析 p162–218），其公式风格与其余章节有轻微差异。

**【预防】**
- 阶段 1 质检就抽查公式（积分号/上下标/多行对齐是高频出错点），把问题登记到待校对清单；
- 阶段 2 把"修复脚本"与"统计"分开：修复做精确替换，统计记录修复处数便于复核；
- 用 `\textcolor{red}{…}` 让**未处理的问题在 PDF 上显式可见**，验收时不会被漏掉。

---

## 陷阱 8：收窄边距引发 Overfull（量级分级判据）

**【现象】**
日志出现 `Overfull \hbox (Npt too wide) in paragraph at lines …` 或 `detected at line …`。

**【根因】**
数学模式内的长行内公式**不会自动换行**；页面文本区变窄（本项目边距收窄为左右 2.2cm）后，原本勉强放得下的公式就会顶出右边界。

**【修复/判定】**
**按溢出量级分级处理**：

| 溢出量 | 判定 | 处理 |
|---|---|---|
| **≤ 4pt**（如 `0.57944pt`） | 视觉不可见 | **可忽略** |
| **> 4pt 但小于页边距宽度** | 顶进边距，通常仍可读 | 建议优化（拆分长公式 / 用 `aligned`） |
| **超过页边距宽度（约 62pt = 2.2cm）** | **会被 PDF 裁切丢内容** | **必须**定位源头修复 |

全局第一道手段（preamble 已配置）：

```latex
\setlength{\emergencystretch}{3em}
```

它允许 LaTeX 在紧急时拉伸字间距，能消除大部分轻微 Overfull；它消除不了的才是需要定位的真问题。

定位方法：日志给出输入行号（注意该行号属于**当前处理的 `.tex` 文件**，可能是某个 `chNN.tex` 而非 `main.tex`）：

```
Overfull \hbox (12.11221pt too wide) detected at line 2360
```

**【预防】**
- 边距收窄与 `\emergencystretch` **成对配置**，不要只收边距；
- 验收时把 Overfull 列为独立检查项，**按量级分级**而不是"有就改 / 无就过"；
- 本项目实测：泛函分析 3 处 Overfull（`0.57944pt` / `12.11221pt` / `49.93639pt`），点集拓扑 0 处。

---

## 陷阱 9：编译日志误报（`not found` / `rerun` 不是错）

**【现象】**
用关键词扫日志时，扫出"疑似问题"：

```
Package pdftexcmds Info: \pdfdraftmode not found.
Package: rerunfilecheck 2025-06-21 v1.11 Rerun checks for auxiliary files (HO)
LaTeX Font Warning: Size substitutions with differences
```

**【根因】**
- `not found` 来自 `pdftexcmds` 包的**信息行**（它在探测某个引擎原语是否可用），不是"文件找不到"；
- `rerun` 匹配到了**包名** `rerunfilecheck`，不是真正的"需要重跑"提示；
- `Size substitutions` 是字体自动缩放替换的**汇总提示**，不影响正确性。

**【修复】**
不需要修复。真正的重跑提示是官方那两句：

```
LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.
Package rerunfilecheck Warning: File `main.out' has changed. Rerun to get outlines right.
```

**【预防】**
- 判断"是否有错"用三类硬信号，而不是 `grep Warning` 的计数：
  1. `! …` 开头的 TeX 错误；
  2. `LaTeX Warning: …undefined` / `Reference … undefined`；
  3. 日志末尾的 `Output written on build/main.pdf (N pages).`（有它才说明产出了 PDF）；
- 把这条误报清单写进团队的排错手册（即本文档），避免每个人重复被同一句话骗一次；
- 本项目实测：点集拓扑 20 条 `Missing character`、0 处 Overfull、13 处 Underfull；泛函分析 191 条 `Missing character`、3 处 Overfull、9 处 Underfull——**两份日志都没有 TeX 错误**，说明"告警多"与"编译失败"是两件事。

---

## 陷阱 10：视觉推断不可靠（空白页判定必须用文本提取）

**【现象】**
对 PDF 分批做视觉/OCR 检查后，不同批次给出**互相矛盾**的结论：某页在这一批里被判定"空白"，在另一批（或人工复看）里又明显有内容；甚至出现"没看过某页却判定它空白"。

**【根因】**
视觉分析是抽样、启发式、分批进行的，对"看起来像空白"的页面（只有页码、页眉，或只有一张浅色插图）判断不一致；分批处理还会丢失上下文。

**【修复】**
判定某页是否空白，**以该页的文本提取结果为准**：

```powershell
# pdftotext（若可用）
pdftotext -f 3 -l 5 -layout build\main.pdf -

# pypdf（本项目依赖）
python -c "from pypdf import PdfReader; r=PdfReader(r'build/main.pdf'); [print(i+1, repr((r.pages[i].extract_text() or '')[:80])) for i in range(2,5)]"
```

判据：提取文本**去掉空白后长度为 0** 才算空白页；非 0 即不是。

**【预防】**
- 把"空白页核查"写成确定性步骤（提取文本 + 长度判据），不依赖人的视觉印象；
- 视觉抽查仍要用，但只用于**内容正确性**（公式、缺字、图文错位），不用于**存在性判定**；
- 结论有冲突时，一律回到文本提取结果作为仲裁。

---

## 陷阱 11：共享计数器 + cleveref 类型名失效（静默缺陷）

**【现象】**
正文里 `\cref{def:1-3}` / `\cref{lem:2-1}` / `\cref{prop:3-2}` / `\cref{cor:4-1}` 全部渲染成**"定理 X"**：定义、引理、命题、推论都变成了"定理"。`\crefname{definition}{定义}{定义}` 等 4 条配置形同虚设。
而编译结果**0 错误、0 警告、0 undefined**——只有肉眼比对渲染结果才能发现。

**【根因】**
cleveref 判定引用类型时依据 label 绑定的**计数器名**，不是环境名。模板若按下面这种"共享计数器"写法定义环境：

```latex
\newtheorem{theorem}{定理}[chapter]
\newtheorem{definition}[theorem]{定义}     % ✗ 计数器名实际是 theorem
\newtheorem{lemma}[theorem]{引理}          % ✗ 同上
\newtheorem{proposition}[theorem]{命题}    % ✗ 同上
\newtheorem{corollary}[theorem]{推论}      % ✗ 同上
```

则这 4 个环境的计数器**全都叫 `theorem`**（`[theorem]` 的含义是"借用 theorem 这条计数器流水线"）。于是它们的 label 与 `theorem` 计数器绑定，cleveref 查 `\crefname` 时只能查到"定理"。
编号本身仍然是对的（定义 1.1、定理 1.2、引理 1.3……），所以从编号上看不出异常——这是一处**静默缺陷**。

**【修复】**
引入 `aliascnt`，让这 4 类**保留独立计数器名、只共享编号序列**：

```latex
\usepackage{aliascnt}                      % 加载顺序：amsthm 之后、\newaliascnt 之前
\newtheorem{theorem}{定理}[chapter]

\newaliascnt{definition}{theorem}          % 新建独立计数器名 definition，编号别名到 theorem
\newtheorem{definition}[definition]{定义}  % 环境使用 definition 计数器
\aliascntresetthe{definition}              % 随 theorem 一起按章重置

\newaliascnt{lemma}{theorem}
\newtheorem{lemma}[lemma]{引理}
\aliascntresetthe{lemma}
% proposition / corollary 同理
```

改完后必须**清空 `build/` 重新编译**（label 与计数器的绑定关系已变，旧 aux 会给出错误结果），再用 `\cref` 抽验 4 类各一处。

**【预防】**
- **模板约定**：凡是"共享编号序列"的定理族环境，一律用 `\aliascnt` + `\newtheorem{env}[env]{中文名}` + `\aliascntresetthe{env}` 三件套，**禁止**直接写 `\newtheorem{env}[theorem]{中文名}`；
- **加载顺序**：`aliascnt` 在 `amsthm` 之后、`\newaliascnt` 之前；所有 `\newaliascnt` / `\newtheorem` 都在 `cleveref` 之前（顺序错了 alias 建不起来，会悄悄退回"共用计数器名"的老毛病）；
- **冒烟测试**：模板阶段就分别 `\cref` 引用定义 / 引理 / 命题 / 推论各一处，确认类型名正确——不能只验收"是不是中文"；
- **验收兜底**：把"引用类型名 ≠ 一律定理"列为内容层固定检查项（这类缺陷不报错，只能靠检查发现）。

---

## 陷阱 12：全角符号残留

**【现象】**
从 MinerU Markdown 经 pandoc 转换得到的 `.tex` 正文中，大量中文全角标点与原书一致保留：全角逗号 `，`、句号 `。`、冒号 `：`、分号 `；`、括号 `（）`、引号 `""` `''`、顿号 `、`、破折号 `—`、省略号 `…`、问号 `？`、叹号 `！`、全角空格等。这些符号在 `ctexbook` 下能编译通过，但与半角标点混排时排版间距不统一，且不符合用户"全角符号全部替换为半角"的偏好。

**【根因】**
MinerU OCR 识别中文 PDF 时保留原书的全角标点；pandoc `-smart` 关闭后不会自动转换标点；`convert.py` 的后处理阶段也未覆盖全角→半角替换。因此全角符号会原样进入 `.tex` 正文。

**【修复】**
用 `scripts/fix_fullwidth.py` 批量替换：

```powershell
python scripts/fix_fullwidth.py <LaTeX项目根目录>
```

脚本会递归扫描所有 `.tex` 文件（排除 `tmp_work/`、`build_work/`、`build/`、`.git/`），按以下规则替换：

| 类别 | 全角 | 半角 | 示例 |
|---|---|---|---|
| 安全替换 | `，。：；？！（）""''、—…` 及全角空格 | `, . : ; ? ! ( ) " " ' ' , -- ...` 及半角空格 | 不影响 LaTeX 代码 |
| 需转义替换 | `％＃＆＿＼｛｝～＾` | `\% \# \& \_ \textbackslash \{ \} \textasciitilde{} \textasciicircum{}` | 防止触发 LaTeX 特殊语义 |

替换后须**清 `build/` 重编译**（改动涉及全部 `.tex` 文件，属全局变更）。

**【预防】**
- 在阶段 2.2（逐章转换）的最后一步、编译验证之前，统一执行 `fix_fullwidth.py`；
- 将"无全角符号残留"列为验收清单内容层检查项（见 `acceptance-checklist.md`）；
- 后续新增章节或手动编辑 `.tex` 文件后，重跑一次脚本即可。

**实测数据**（4 本书 33 个 `.tex` 文件）：共替换 5899 个全角符号，替换后 4 本书编译均 0 错误收敛。

---

## 陷阱 13：编译引擎不在 PATH + `-output-directory` 用中文绝对路径 → xelatex fatal 且日志无错

**现象**（2026-10-06 实测，TeX Live 2026 / Windows）

两个独立故障叠在一起，且**都不产生任何 `!` 错误行**：

1. 引擎不在 PATH。本机 TeX Live 装在 `D:\texlive\2026\bin\windows`，`where xelatex` 找不到。
   脚本化调用（`subprocess.run(["xelatex", ...])`）直接抛 `FileNotFoundError`；
   手工 `xelatex` 则 command not found。
2. 即便写全引擎绝对路径，若把 `-output-directory` 传成**含中文的绝对路径**：

   ```
   xelatex.exe -interaction=nonstopmode -output-directory=D:\...\研一数学\03-latex\裴礼文-数学分析\build main.tex
   ```

   会得到：

   ```
   xelatex.exe: fatal: putenv(TEXMF_OUTPUT_DIRECTORY=D:\...\研一数学\...\build)
   返回码 1
   ```

   而 `build/main.log` 末尾仍是 `Output written on build/main.pdf (10 pages).`，
   **一个 `!` 都没有**——只看日志会以为编译成功，只有返回码是 1。

**根因**

* TeX Live 2025+ 的 `xelatex` 会把 `-output-directory` 的值 `putenv` 成
  `TEXMF_OUTPUT_DIRECTORY`；Windows CRT 的 `putenv` 不接受含非 ASCII 字符的值。
* 相对路径 `build` 是纯 ASCII，putenv 立刻成功，后续由 kpathsea 自行解析成绝对路径——
  所以**同一个中文目录下，相对路径能编过，绝对路径编不过**。

**修复**（已合入 `templates/build.py`，复制到项目根即用）

1. `resolve_engine()`：`--engine` 同时接受引擎名与绝对路径；只给名字时按
   「PATH → 常见安装根目录（`C:\texlive` / `D:\texlive` / MiKTeX…）」自动定位，
   并把引擎所在目录**原地**并入 `os.environ['PATH']`（不要用 `env=` 传副本，
   见下），使同目录的辅助程序与 DLL 也能被找到。
2. `-output-directory` 固定写**相对路径** `build`（脚本本身固定 `cwd=项目根`，
   两者等价），从根上规避 putenv 问题。
3. 返回码非 0 但 `!` 计数为 0 时，脚本会打印日志尾部 + stderr 尾部 + stdout 尾部——
   否则这个故障会完全隐形。

**为什么不要 `env=dict(os.environ)` 传给 subprocess**

Windows 下 Python 复制出的环境块会丢掉 `=C:` 这类"各盘当前目录"伪变量，
子进程行为难以预测；原地修改 `os.environ` 让子进程自然继承是更稳的做法。

**排查口诀**：`返回码≠0 且日志 0 错误` → 先看 stderr，别信日志。

---

## 附：陷阱速查表

| # | 一句话 | 第一动作 |
|---|---|---|
| 1 | aux 损坏 | 清 `build/` 重编 |
| 2 | 零错误但第 0 章 | 查 `main.tex` 的 `\chapter` |
| 3 | 前置页空白页 | 文档类加 `openany` |
| 4 | 封面多一行作者 | `\bookinfo{书名}{}` |
| 5 | `Undefined control sequence` | 补 `mathrsfs` / `xcolor` / `\pandocbounded` |
| 6 | `ended by \end{document}` | 跑 `check_env.py`，补第一个缺失的 `\end` |
| 7 | OCR 公式错 | 对照原书定点修；修不了的用红色标记 |
| 8 | Overfull | 按量级分级：≤4pt 忽略；>62pt 必修 |
| 9 | 日志误报 | 认准 `!` / `undefined` / `Output written` 三类硬信号 |
| 10 | 空白页判定 | 用文本提取，不用视觉推断 |
| 11 | `\cref` 类型名一律"定理" | 用 `aliascnt` 建独立计数器名，勿直接共享 theorem 计数器 |
| 12 | 全角符号残留 | 编译前跑 `scripts/fix_fullwidth.py` |
| 13 | 返回码 1 但日志 0 错误 | 看 stderr；`-output-directory` 改相对路径，`--engine` 用自动定位 |
| 14 | 数学环境里的中文变乱码 | 换 vlm 模型重跑，勿用 pipeline 兜底 |
| 15 | 例题编号与单元练习撞号 | 按习题区排除"例 X.Y.Z"题干 |
| 16 | 标题整段漏分类 | 段落先 strip 再取首行（`\s*$` 只吞一个换行） |

---

## 陷阱 14：MinerU pipeline 模型把数学环境内的中文识别成乱码（2026-10-06 实测）

**现象**：`为既约分数` 进了 display 公式后，pipeline 输出
`\varkappa / \mathrm { B } \dag \Sigma \dag \Sigma \dag \Sigma`，vlm 输出 `\text {为既约分数,}`。
中文在数学环境内是本书常态（分段函数的条件、公式后的"其中…"），因此该差异是**系统性**的。

**对策**：优先 `vlm`；某块 vlm 反复失败时再降级 pipeline，并**记住降级段需要在精排时重点校对**。
判据：同一页分别用两个模型解析后对比即可，5 分钟定案，别凭经验猜。

**副作用提醒**：换模型重跑时务必确认续跑逻辑不会把已成功块整体覆盖
（本工具曾因此把 14 块 vlm 结果覆盖成 pipeline，日志上只表现为"换模型重试"）。

---

## 陷阱 15：习题书的「单元练习」编号与例题同形（撞号 + 假例头）

**现象**（裴礼文《数学分析中的典型问题与方法》第 3 版）：
* 单元练习的题目编号是 `1.1.1、1.1.2…`，与正文例题 `例 1.1.1` **同形**；
* MinerU 还会把题干直接写成 `例 1.1.1 求复合函数表达式：`。

后果：若不区分，会把习题包成 `example` 环境并与正文例题撞号（实测 7 处），
且 LaTeX 的自动编号会把后续所有例号整体推移。

**对策**：拆分后维护 `in_unit` 区标志——遇到 `\unitpractice` 置位、遇到 `\section` 复位；
区内的 `例 X.Y.Z` 一律视为题干，不建环境、不进 id_map。

---

## 陷阱 16：`re.MULTILINE` 下 `\s*$` 只吞一个换行 → 段落首行取空 → 标题整段漏分类

**现象**：`text.split('## 原文')` 之后的正文首段是 `'\n## 第一章 一元函数极限'`——
因为 `^## 原文\s*$` 的 `\s*$` 在 MULTILINE 下只吞掉一个换行（贪心回溯后停在行尾），
下一段便以 `\n` 开头。于是 `lines[0] == ''`、`first == ''`，`startswith('#')` 不成立，
**整段标题原样穿过**，被 pandoc 转成 `\subsection{第一章 …}` 混进正文（全书 7 处）。

**对策**：处理段落前先 `p = p.strip()`，再取首行。一行修复，但症状（"多出一个 1.0.1 节"）
与根因（换行计数）相距极远，靠肉眼极难定位。

**教训**：正文里出现"章号 + 0.x"编号时，先怀疑**段落切分**，而不是标题正则。

---

## 陷阱 17：引用句前缀排除法对「例」类固定形态头部是误杀源

参考实现的 `REF_PREFIX_RE` 用"结合/由/从/利用/根据…"等前缀排除引用句，这对
"定理 1.2 表明…"这类自由形态有效；但习题书的例头常以动词开头——
`例 6.3.7 从原点向单叶双曲面 …` 会被整条误杀（实测 60+ 处）。

**对策**：按书分治。例头形态固定（`例 + 三段编号 + 题干`）时，只保留"标点开头"排除 +
重复编号检测，停用前缀表；对「注」这类自由形态仍可用前缀表。
**判定依据是实测误杀数，不是直觉**——写完规则后必须跑一遍 `missing_refs` 清单逐条核对。

---

## 陷阱 18：Overfull 只有量级没有定位 → 修不动（工具补齐，2026-10-06 实测）

**现象**：`build/main.log` 里 110 条 `Overfull \hbox`，skill 只给了量级分级判据（≤4pt 忽略 /
>62pt 必修），但**不知道每条对应源文件哪一行**，逐条人肉翻根本不可行。

**对策**：`overfull.py` 类工具，从日志提取并做两级映射：
1. **页 → 章**：解析 `main.toc` 的 chapter 条目起始页（arabic 页码与日志 `[N]` 同一体系）。
   ⚠️ 两个解析坑：① `detected at line N` 与 `Overfull` 在**同一行**，别只往后找；
   ② `\numberline {第一章\hspace {.3em}}` 内含嵌套花括号，`[^}]*` 匹配不了，要用 `(.*)` 贪婪到 `}{页码}{chapter`。
2. **源行 → 源码**：`detected at line N` 的 N 是当前 `\input` 文件的行号，直接读该章 `.tex` 打出上下文。

有了「页 + pt + 源行 + 源码」四元组，才能派单给并行智能体逐条修。

**修 display 溢出的标准手法**：一行长链 `= A = B = C` 拆 `\begin{align*} 原式 &= A \\ &= B \end{align*}`，
在关系符号后断行；行内 `\left…\right` 是不可断盒子，改普通定界符才允许内部断行。

---

## 陷阱 19：MinerU 把练习题题干输出两遍（458 处，去重判定粒度是关键）

**现象**：习题书的单元练习区，几乎每道题都是
```
1.3.14 若 \(f(x)=\begin{cases}…\end{cases}\) 求 …（上海工业大学）
 \(f(x)=\begin{cases}…\end{cases}\) 求 …（上海工业大学）   ← 残句（去编号后与上一行同文）
```
两份都会排进 PDF，用户会看到成段的重复文字。

**判定规则的教训（先错后对）**：
* ❌ 第一版：「归一化后**互为包含**、不限相邻」→ 误删 69 条正常的多行题干
  （长题干的换行两段天然互相包含）。已从智能体 scratch 恢复。
* ✅ 正确粒度：**相邻两行**，且上一行以题号 `\d+(\.\d+)+\s` 开头，当前行是其去编号副本
  （包含关系即可，因为残句常比题干少一个前置动词「若/证/计算」）。
* 额外保险：排除 `\begin/\end/\[/\]/\phead/\item/\def` 开头的行（`\def\labelenumi` 会整批误报）。

**验收**：删完必须重编译（页数会下降）+ 渲染原报告页对照原书。

---

## 陷阱 20：「缺失图片 0」防不住字面残留的图片引用

`convert.py` 的缺图检查只认 pandoc 输出的 `\includegraphics{images/…}` 形式；
但个别 markdown 图片（夹在两个 `$$` 块之间）pandoc **没有转换**，以字面
`![](images/….jpg)` 原样穿过，被排进正文成为一长串不可断文本（必然 Overfull）。

**对策**：编译后扫一遍所有 `.tex` 里的字面 `![](` 计数，应为 0；
不为零时回 md 源找原因、把图片文件从 `00-MinerU原始分块/chunk-*/images/` 拷进项目并补 `\includegraphics`。
另：智能体修溢出时可能把**文件名**切断来强行断行（实测把 64 位哈希从中间插了 `\hfill\linebreak`），
复核时要专门检查图片引用的完整性。
