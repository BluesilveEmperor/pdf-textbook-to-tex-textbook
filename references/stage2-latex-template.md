# 阶段 2.1 详解：LaTeX 模板设计（ctexbook + 定理族环境）

> 本文档解决什么问题：把 `main.tex` / `preamble.tex` 里每一行配置"为什么这么写"讲清楚——尤其是文档类选项、定理族计数器设计、宏包加载顺序这三处一动就出问题的地方，并给出模板落地后的冒烟测试流程。

模板文件：`templates/preamble.tex`、`templates/main.tex`。**先建模板并编译通过，再开始逐章转换**——模板是阻塞后续全部步骤的前置条件。

## 1. 项目骨架

```
<书名>/
├── main.tex          ← 文档类 + 结构 + \chapter
├── preamble.tex      ← 宏包与配置（本文档主角）
├── chapters/chNN.tex ← 逐章内容（章节转换产物）
├── images/           ← 正文插图
└── build/            ← 编译产物（PDF / aux / toc / out / log）
```

建目录、复制模板：

```powershell
mkdir <书名>\chapters, <书名>\images, <书名>\build
copy templates\preamble.tex <书名>\
copy templates\main.tex     <书名>\
```

## 2. 文档类：`ctexbook` 及选项

```latex
\documentclass[UTF8,a4paper,zihao=-4,fontset=windows,openany]{ctexbook}
```

| 选项 | 作用 | 为什么需要 |
|---|---|---|
| `UTF8` | 声明 UTF-8 编码 | 全文（含 LaTeX 源码、Markdown 产物）均为 UTF-8；显式声明避免按系统代码页误判 |
| `a4paper` | A4 纸张 | 教材常规开本 |
| `zihao=-4` | 正文字号**小四** | 中文排版惯例；`-4` 是 ctex 的负号字号写法 |
| `fontset=windows` | 使用 Windows 系统字体（中易宋体/黑体） | 实测可用；**若编译环境字体异常，去掉该选项改用 `fandol`**（TeX Live 自带中文字体） |
| **`openany`** | 允许章/目录从**任意页**开始 | `book` 类默认 `openright` 强制"右页起排"，会在标题页与目录页之间、以及各章之间插入**空白页**；`openany` 消除这些空白页（见 pitfalls 陷阱 3） |

> `ctexbook`（而非 `ctexart` / `article`）是必需的：本书需要 `\chapter`、`\frontmatter` / `\mainmatter`、按章编号的定理计数器——这些只有 book 类层级才提供。

## 3. `main.tex` 的结构骨架

```latex
\documentclass[UTF8,a4paper,zihao=-4,fontset=windows,openany]{ctexbook}

\input{preamble}

\begin{document}

% ---- 前置部分：标题页与目录 ----
\frontmatter
\bookinfo{《点集拓扑讲义》}{}   % 第二参数是作者名；只要书名时留空
\maketitle
\tableofcontents

% ---- 正文部分 ----
\mainmatter

\chapter{朴素集合论}
\input{chapters/ch01}

\chapter{拓扑空间与连续映射}
\input{chapters/ch02}

% … 每章一对 \chapter + \input

\end{document}
```

三条硬约定：

1. **`\bookinfo{书名}{作者}`**：第二参数是**作者名**，`\maketitle` 会把它排在标题下方；只要书名时**必须留空**（`\bookinfo{《点集拓扑讲义》}{}`），否则封面上会多出一行不是作者的"作者"（见 pitfalls 陷阱 4）。
2. **章标题只写在 `main.tex`**：`\chapter{章名}` 在最外层，章文件 `chNN.tex` 内**只含 `\section` 及以下**。漏写 `\chapter` 会让全书退化到"第 0 章"且**不报任何编译错误**（见 pitfalls 陷阱 2）。
3. **`\input` 不带 `.tex` 后缀**：`\input{chapters/ch01}`。

全项目编码规范（正文编写与转换产物统一遵守）：

4. **公式定界符**：行内公式只能用单美元 `$...$`、行间公式只能用双美元 `$$...$$`；**禁用** `\(...\)` 与 `\[...\]`（pandoc 的改写输出须用 `scripts/fix_math_delimiters.py` 回替换，详见 `stage2-chapter-conversion.md` §7.6）。带编号/多行对齐的 amsmath 环境（`equation`/`align` 等）不受此约束。

## 4. `preamble.tex` 逐节解释

### 4.1 页面设置（〇）

```latex
\usepackage{geometry}
\geometry{
  a4paper,
  left=2.2cm, right=2.2cm,   % 左右边距
  top=2.5cm, bottom=2.5cm,   % 上下边距
  headsep=0.6cm,             % 页眉与正文的距离
  footskip=0.9cm,            % 页码与正文底部的距离
}
\setlength{\emergencystretch}{3em}
```

- **为什么收窄边距**：`ctexbook` 默认页边距偏大、版面留白过多，收窄为左右 2.2cm / 上下 2.5cm 提升版面利用率。`headsep` / `footskip` 同步收紧，避免页眉页码占位过大。
- **代价**：文本区变窄 → 长行内公式更容易 `Overfull \hbox`（数学模式内不自动换行）。`\emergencystretch=3em` 允许 LaTeX 在紧急情况下拉伸字间距，是缓解 Overfull 的**第一道全局手段**（量级分级判据见 pitfalls 陷阱 8）。
- **改动后必须清 build 重建**（aux 中记录了页面参数）。

### 4.2 数学宏包（一）

```latex
\usepackage{amsmath}     % 数学环境基础（equation、align 等）
\usepackage{amssymb}     % 数学符号（\varnothing、\lesssim 等）
\usepackage{amsthm}      % 定理环境与证明环境
\usepackage{mathtools}   % amsmath 增强（\coloneqq、dcases 等）
\usepackage{bm}          % 粗体数学符号（\bm）
\usepackage{mathrsfs}    % 花写字母 \mathscr（OCR 识别的拓扑符号）
\usepackage{xcolor}      % 文本颜色(\textcolor)—— 标记 OCR 损坏公式待校对
\allowdisplaybreaks[1]   % 长公式允许适度跨页
```

**四个"看起来可选、实际必需"的宏包**（缺任一都会报 `Undefined control sequence`）：

| 宏包 | 提供 | 触发场景 |
|---|---|---|
| `mathrsfs` | `\mathscr` | MinerU 把花体字母识别成 `\mathscr` |
| `xcolor` | `\textcolor` | ① 缺图占位标记 `\textcolor{red}{[缺图 …]}`；② OCR 严重损坏公式的人工标记 |
| （`amsmath` 系） | `\text{}` 等 | 数学模式内的中文/文本 |
| `\pandocbounded` | 见 4.3 | pandoc 3.x 自动插图包裹命令 |

### 4.3 图形（二）

```latex
\usepackage{graphicx}
\graphicspath{{images/}}                 % 插图统一存放在项目 images/
\providecommand{\pandocbounded}[1]{#1}   % pandoc 3.x 图片包裹命令透传
```

- **`\graphicspath{{images/}}`**：正文一律写 `\includegraphics{<哈希名>}`，**不写 `images/` 前缀**。
- **`\providecommand{\pandocbounded}[1]{#1}`**：pandoc 3.x 会把图片包成 `\pandocbounded{\includegraphics[...]{...}}`。模板不需要它的溢出保护语义，只需让它"透传"内部内容，否则报 `Undefined control sequence`。用 `\providecommand`（而非 `\newcommand`）是为了兼容将来 pandoc 版本可能自带定义的情况。

### 4.4 列表（三）

```latex
\usepackage{enumitem}
\setlist{itemsep=2pt, topsep=4pt, parsep=0pt}
```

压紧列表项间距，贴合教材版式，避免"枚举列表占半页"。

### 4.5 定理族环境（四）—— 计数器设计

```latex
% ---- 4.0 aliascnt：让"共享编号序列"与"独立计数器名"兼得 ----
% 必须在 \newaliascnt 之前、amsthm 之后加载
\usepackage{aliascnt}

% ---- 4.1 主计数器（plain 风格：编号体斜体）----
\newtheorem{theorem}{定理}[chapter]

% ---- 4.2 共享「编号序列」，但保留各自独立的「计数器名」----
% 正例（本模板采用）：aliascnt 为 definition 建一个专属计数器名 definition，
% 其编号跟随 theorem；cleveref 于是能按计数器名区分类型。
\theoremstyle{definition}                % 正文直体
\newaliascnt{definition}{theorem}
\newtheorem{definition}[definition]{定义}
\aliascntresetthe{definition}

\theoremstyle{plain}                     % 正文斜体
\newaliascnt{lemma}{theorem}
\newtheorem{lemma}[lemma]{引理}
\aliascntresetthe{lemma}

\newaliascnt{proposition}{theorem}
\newtheorem{proposition}[proposition]{命题}
\aliascntresetthe{proposition}

\newaliascnt{corollary}{theorem}
\newtheorem{corollary}[corollary]{推论}
\aliascntresetthe{corollary}

% ✗ 反例（不要这样写）：直接共享 theorem 计数器
%   \newtheorem{lemma}[theorem]{引理}
%   编号是对的，但 label 绑定的计数器名变成 theorem，于是 \cref 对
%   定义/引理/命题/推论一律输出"定理"，四条 \crefname 永不生效（详见本节末尾的警示）。

% ---- 4.3 独立计数器的环境（无需 aliascnt）----
\theoremstyle{definition}
\newtheorem{example}{例}[chapter]
\theoremstyle{remark}
\newtheorem{remark}{注}[chapter]

% ---- 4.4 证明环境汉化 ----
\renewcommand{\proofname}{证}
```

**设计意图（国内教材编号惯例）**：

| 环境 | 计数器 | 效果 |
|---|---|---|
| `theorem` | **主计数器 `[chapter]`** | 按章编号，形如"定理 1.2" |
| `definition` / `lemma` / `proposition` / `corollary` | **共享 theorem 的编号序列**（计数器名各自独立，用 `aliascnt` 建立别名） | 与定理共用一条编号流水线：同一章内依次出现"定义 1.1、定理 1.2、引理 1.3、推论 1.4……" |
| `example` | 独立 `[chapter]` | "例 1.1、例 1.2…"单独计数 |
| `remark` | 独立 `[chapter]` | "注 1.1、注 1.2…"单独计数 |

为什么共享而不是每种环境各自编号：国内教材通常把定义/定理/引理/推论视作**同一个"结果序列"**，读者看到"引理 1.3"就知道它是本章第 3 个编号结果；若各环境独立编号，会出现"定义 1.1、定理 1.1、引理 1.1"并存的混乱。`example` / `remark` 属于举例与旁注性质，惯例上不占用主序列。

`\theoremstyle` 的作用：`plain`（斜体正文）用于定理类结果；`definition`（直体）用于定义、例；`remark` 用于注。

**交叉引用的中文名**（在 4.6 与 hyperref/cleveref 一起生效）：

```latex
\crefname{theorem}{定理}{定理}   \crefname{definition}{定义}{定义}
\crefname{lemma}{引理}{引理}      \crefname{proposition}{命题}{命题}
\crefname{corollary}{推论}{推论}  \crefname{example}{例}{例}
\crefname{remark}{注}{注}         \crefname{figure}{图}{图}
\crefname{equation}{式}{式}       \crefname{chapter}{章}{章}
```

单复数取同一形式（中文没有词的复数形态），保证"定理 1.2"/"定理 1.2 和 1.3"都渲染成自然中文。

> ⚠️ **陷阱：共享计数器会让 cleveref 分不清类型名**。
> cleveref 判定引用类型时依据的是 label 绑定的**计数器名**，不是环境名。若按上面"✗ 反例"的写法 `\newtheorem{lemma}[theorem]{引理}`，引理环境的计数器实际就是 `theorem`，于是：
>
> - `\cref` 对定义 / 引理 / 命题 / 推论**一律渲染为"定理"**（"引理 1.3"被写成"定理 1.3"）；
> - `\crefname{definition}` / `{lemma}` / `{proposition}` / `{corollary}` 这 4 条配置**永不生效**，而且**不报错、不告警**，只能靠肉眼比对渲染结果才能发现。
>
> **修复**：用 `aliascnt` 给这 4 类建立**独立计数器名**、只**共享编号序列**（配置见本节模板代码的 4.0 与 4.2 段）：
>
> ```latex
> \usepackage{aliascnt}              % 加载位置：amsthm 之后
> \newaliascnt{lemma}{theorem}       % 新建独立计数器名 lemma，并把编号别名到 theorem
> \newtheorem{lemma}[lemma]{引理}    % 环境使用 lemma 这个计数器（不再是 theorem）
> \aliascntresetthe{lemma}           % 让 lemma 与 theorem 一起按章重置
> ```
>
> 这样 label 绑定的是 `lemma` 计数器名，`\crefname{lemma}{引理}{引理}` 才真正生效。
> **结论：`\crefname` 只有在"计数器名可区分"时才生效**——它按计数器名查引用名，不按环境名。

### 4.6 超链接与交叉引用（五）

```latex
\usepackage{hyperref}    % 必须在 cleveref 之前
\hypersetup{
  hidelinks,             % 链接不加彩框、不变色
  bookmarksnumbered,     % PDF 书签带章节编号
}

\usepackage{cleveref}    % 必须在 hyperref 之后
\crefname{...}{...}{...}  % 见 4.5
```

- PDF 书签（`bookmarksnumbered`）与正文 `\cref` 都由这两个宏包提供。
- `hidelinks` 是刻意选择：印刷/阅读版不希望到处都是彩色方框。

### 4.7 书名元信息（六）

```latex
\newcommand{\bookinfo}[2]{%
  \title{#1}%
  \author{#2}%
  \date{}%
  \hypersetup{pdftitle={#1}, pdfauthor={#2}}%
}
```

把"书名 + 作者"一次性写入标题页与 PDF 元数据（`pdftitle` / `pdfauthor`）。`\date{}` 显式清空，避免标题页出现编译日期。

## 5. 加载顺序约束（最容易踩的坑）

preamble 必须满足下面这条**偏序关系**，任意两条颠倒都会导致"引用名失效"或"编译报错"：

```
ctexbook(documentclass)
   └─> geometry                     （页面参数，先于 hyperref 记忆页面尺寸）
   └─> amsmath / amssymb / amsthm   （定理机制基础）
   └─> aliascnt                     （★ 在 \newaliascnt 之前、amsthm 之后）
   └─> \newaliascnt × 4 + \newtheorem × 7   （★ 全部计数器与环境定义完毕）
   └─> hyperref                     （★ 在 cleveref 之前）
   └─> cleveref                     （★ 在 hyperref 之后）
   └─> \crefname{...} × 9           （★ 在 cleveref 之后）
```

四条硬规则：

1. **`amsthm` 必须在 `hyperref` 之前**加载。
2. **所有 `\newaliascnt` 与 `\newtheorem` 必须在 `cleveref` 之前完成**——否则 cleveref 收集不到环境/计数器类型，`\crefname` 报"未知环境类型"或引用名退化为英文/编号。
3. **`aliascnt` 必须在 `\newaliascnt` 之前、`amsthm` 之后**加载；顺序错了 alias 计数器建立不起来，会退回"共享同一计数器名"的老毛病（类型名失效）。
4. **`hyperref` 必须在 `cleveref` 之前**。

实践建议：**不要随意重排 preamble 的段落顺序**。模板是按上述顺序写好的，调整应追加在对应段落内。

## 6. 冒烟测试流程

模板建好后**不要等逐章转换完成才第一次编译**——先用一段样例内容验证模板本身：

1. 在 `chapters/` 下放一个极小的 `smoke.tex`（或直接在 `main.tex` 里临时写），内容要覆盖模板的**全部能力**：
   - 一个 `\chapter` + `\section` + `\subsection`（验证层级与编号）；
   - 每种定理族环境各一个（`theorem` / `definition` / `lemma` / `proposition` / `corollary` / `example` / `remark`）；
   - **分别 `\cref` 引用定义 / 引理 / 命题 / 推论各一处**，确认渲染为"定义 1.x / 引理 1.x / 命题 1.x / 推论 1.x"，**而不是一律"定理 1.x"**（共享计数器的典型症状，且不会报错）；
   - 一个带名称括号的定理（`\begin{theorem}[名称]`）；
   - 一个 `\begin{proof} … \end{proof}`（验证 `proofname` 显示为"证"、QED 方块自动出现）；
   - 两个互相 `\label` / `\cref` 的定理（验证交叉引用名是中文）；
   - 一个 `$行内公式$` 与一个 `\[ 行间公式 \]`；
   - 一个 `\includegraphics`（验证 `graphicspath` 生效）；
   - 一个中文长段落（验证 `fontset=windows` 无缺字）。
2. 编译两遍：

```powershell
xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
```

3. 通过标准：**0 错误、0 undefined reference**；目录出现章/节条目；`\cref` 渲染成中文引用名**且类型名正确**（定义 / 引理 / 命题 / 推论各就其位，不是一律"定理"）；证明末尾有 QED 方块。
4. 通过后再进入逐章转换（`stage2-chapter-conversion.md`）。冒烟测试失败时先修模板，**不要**在章文件里打补丁绕过。

## 7. 模板复用与微调

- 两本书**共用一套骨架**，各自的 `preamble.tex` 内容保持一致。
- 某本书需要单独微调（行距、页眉页脚等）时，**只改自己项目内的副本**，互不影响。
- 任何一次对 preamble 的改动（尤其是 `\documentclass` 选项、`geometry`、`\newtheorem`），都必须**清空 `build/` 重新编译**，否则会因 aux 与当前参数不一致而报连锁错误（见 `compilation-and-troubleshooting.md` 与 pitfalls 陷阱 1）。
