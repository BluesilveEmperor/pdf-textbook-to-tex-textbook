# 验收清单

> 本文档解决什么问题：给出"这份 LaTeX 精排项目算不算做完了"的可执行判据——分编译层 / 结构层 / 内容层三层检查，每一条都配可运行的核验方法，并规定收尾时哪些文件要清理、哪些必须保留。

**核心原则：不能只看编译错误数。** 本项目实测过"编译 0 错误、0 警告，但全书落在第 0 章"的情况——编译层全绿，结构层全错。

## 第 0 层：前置确认

- [ ] 工作目录 = 项目根（`main.tex` 所在处）；
- [ ] `build/` 是**本次**编译的产物（而非上次残留）；
- [ ] 结构 / preamble 有过任何改动的话，已先清 `build/` 再连跑 2–3 遍。

```powershell
Remove-Item build\* -Recurse -Force    # 仅在上一条成立时执行
xelatex -interaction=nonstopmode -output-directory=build main.tex
xelatex -interaction=nonstopmode -output-directory=build main.tex
xelatex -interaction=nonstopmode -output-directory=build main.tex
```

## 第 1 层：编译层

| # | 检查项 | 目标 | 核验方法 |
|---|---|---|---|
| 1.1 | TeX 错误 | **0** | `findstr /C:"! " build\main.log`（无输出即通过） |
| 1.2 | undefined 引用 | **0** | `findstr /I "undefined" build\main.log` |
| 1.3 | 未收敛提示 | 无 | 日志中不应再出现 `Rerun to get cross-references right` |
| 1.4 | 确实产出 PDF | 有 | `findstr /C:"Output written on" build\main.log`（形如 `Output written on build/main.pdf (N pages).`） |

**关于"0 警告"**：需要区分两类：

- **必须处理的告警**：`undefined reference`、`multiply defined labels`、`\begin{…} ended by \end{document}`、`Undefined control sequence`、`Missing $ inserted`；
- **可接受的排版告警**：`Underfull \hbox/\vbox`、`Overfull \hbox`（按 `compilation-and-troubleshooting.md` §6 分级：≤4pt 可忽略）、字体形状替换（`U/rsfs/m/n not available`、`Size substitutions`）、`Missing character`（属待人工校对项）。

收尾时**逐条列出**可接受的告警并说明为什么不处理，不要用一句"0 警告"掩盖。

## 第 2 层：结构层

这一层是**编译不报警但结果会错**的部分，必须机械核验。

### 2.1 目录章数 = 实际章数

```powershell
# 目录里的 chapter 条目数
findstr /C:"\contentsline {chapter}" build\main.toc | find /C "chapter"
# 源码里的 \chapter 数
findstr /R /C:"^\\chapter{" main.tex | find /C "chapter"
# chapters/ 下的章文件数
dir /B chapters\ch*.tex | find /C ".tex"
```

三个数字必须**完全一致**。

### 2.2 编号按章递增（不是 0.x）

```powershell
# 抽查：aux 中的标签是否带章号（形如 {1}{1} 而非 {0}{1}）
findstr /C:"\newlabel{thm:" build\main.aux
```

判据：

- 标签编号第一个数字是**章号**（`1`、`2`…），**不得出现 `0`**；
- 目录里不得出现"第 0 章"；
- `定理 1.1、1.2、1.3…` 与 `定理 2.1、2.2…` 按章重新起算。

> 这一条是为了捕获"`main.tex` 漏写 `\chapter{}`"这一类**零报错**故障：10 个章文件只含 `\section`，`main.tex` 不声明 `\chapter`，全书就落到第 0 章、编号变 `0.x`——编译完全不报错。

### 2.3 章文件内不出现 `\chapter`

```powershell
findstr /S /C:"\chapter{" chapters\*.tex
```

无输出（章标题只写在 `main.tex`）才算通过。

### 2.4 环境配对

运行 `check_env.py`（见 `compilation-and-troubleshooting.md` §7），每章 `\begin{env}` 与 `\end{env}` 计数相等；输出应为空。

### 2.5 图片无缺失

```powershell
# 正文中被引用的图（去重后）
findstr /S /C:"\includegraphics" chapters\*.tex
# images/ 实际文件数
dir /B images | find /C "."
```

判据：

- `images/` 文件数 **≥** 被引用的**唯一**文件名数；
- 全书**不存在** `\textcolor{red}{[缺图 …]}` 占位（转换阶段自动插入的缺图标记）：
  ```powershell
  findstr /S /C:"[缺图" chapters\*.tex
  ```
  无输出才通过。
- 无 `\textcolor{red}{\textbf{[此处公式 OCR 严重损坏` 类未处理标记（如果保留，必须已在待校对清单中登记）。

### 2.6 定理族计数与统计一致

抽若干章，用 `audit_env.py` 列出每个带 label 的环境，与 `stats_NN.json` 的 `env` 字段比对；全书合计应与总计划记录的规模量级一致（本项目：**`theorem` 环境**数泛函 101 / 点集 233；含 definition / lemma / proposition / corollary / example / remark 在内的定理族环境合计泛函 426 / 点集 452）。

## 第 3 层：内容层（渲染抽查）

编译与结构都对，还要**看**成品。抽取封面、目录、每章首尾页、公式密集页、图表页渲染成图逐页核验。

| # | 检查项 | 判据 |
|---|---|---|
| 3.1 | 封面 | 只有书名（**没有**多余的作者行/日期行）；无乱码 |
| 3.2 | 目录 | 三级结构完整（章 / 节 / 小节）；页码与正文对得上；无"第 0 章" |
| 3.3 | 正文中文 | 无缺字、无方框、无乱码（`fontset=windows` 生效） |
| 3.4 | 公式 | 希腊字母 / 花体 / 积分号 / 上下标 / 集合符号渲染正确；无截断 |
| 3.5 | 定理环境 | `定理 1.2`、`定义 1.1`、`例 1.3` 编号连续；`\cref` 渲染成中文引用名；**随机各取一个 `\cref{def:…}` / `\cref{lem:…}` / `\cref{prop:…}` / `\cref{cor:…}`，确认分别渲染为「定义 / 引理 / 命题 / 推论」，而不是一律「定理」** |
| 3.6 | 证明环境 | 标题为"证"，末尾有 QED 方块 |
| 3.7 | 插图 | 图片位置正确、不超出页面、图注可见 |
| 3.8 | 文字溢出 | 长公式未顶破右边距（对照第 2 层的 Overfull 分级） |

本项目实测：抽两书封面、目录、正文共 8 页转图核验——中文无缺字、数学公式（希腊字母/花体/积分号/上下标/集合符号）全部正确渲染、目录三级结构完整、定理环境编号规范、无文字溢出或图文错位。

### 3.9 页面规范核对

| 检查项 | 判据 |
|---|---|
| 页边距生效 | 正文不应有大片留白；左右 2.2cm / 上下 2.5cm 已生效（改过 geometry 的话必须清 build 重编后才可信） |
| 前置页无空白页 | 标题页与目录页之间**不应有空白页**——`openany` 生效的标志 |
| 章间无空白页 | 各章之间不应插入空白页 |
| 封面无冗余文字 | `\bookinfo{书名}{作者}` 的第二参数为作者名；只要书名时必须写 `\bookinfo{书名}{}` |
| 页眉/页码正常 | `headsep=0.6cm` / `footskip=0.9cm` 下无重叠、无越界 |

### 3.10 空白页判定：用文本提取，不要靠"看图"

**视觉/OCR 分批分析可能给出互相矛盾的结论**（例如未看某页却判定其空白）。判断某页是否空白，**必须以该页文本提取结果为准**：

```powershell
# 方案 A：pdftotext（poppler，若已安装）
pdftotext -f 3 -l 5 -layout build\main.pdf -

# 方案 B：pypdf（本项目依赖，推荐）
python -c "from pypdf import PdfReader; r=PdfReader(r'build/main.pdf'); [print(i+1, repr((r.pages[i].extract_text() or '')[:80])) for i in range(2,5)]"
```

判据：某页提取出的文本**去空白后长度为 0**，才判定为空白页。若长度非 0，即便视觉上像空白（例如只有页码或页眉），也不是需要处理的空白页。

### 3.11 全角符号已替换为半角

教材正文中的全角标点（`，。：；？！（）""''、—…` 等）应全部替换为半角。检查方法：

```python
# 扫描所有 .tex 文件中是否仍有全角符号残留
import os
fullwidth = set('，。：；？！（）""''、—…　％＃＆＿＼｛｝～＾＜＞＝＋－＊／｜＠［］')
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('tmp_work', 'build_work', 'build', '.git')]
    for f in files:
        if f.endswith('.tex'):
            with open(os.path.join(root, f), encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    found = fullwidth & set(line)
                    if found:
                        print(f'{os.path.join(root, f)}:{i} {found}')
```

判据：无输出即通过。若仍有残留，重跑 `python scripts/fix_fullwidth.py` 后清 `build/` 重编译。

### 3.12 公式定界符统一为美元符号

编码规范：行内公式只能用 `$...$`、行间公式只能用 `$$...$$`，**不得残留** pandoc 改写出的 `\(...\)` / `\[...\]`。检查方法：

```powershell
findstr /S /C:"\\(" chapters\*.tex main.tex
findstr /S /C:"\\)" chapters\*.tex main.tex
findstr /S /R /C:"\\[" chapters\*.tex main.tex
findstr /S /R /C:"\\]" chapters\*.tex main.tex
```

判据：无输出即通过。注意排除误报——`\\[2pt]` 类"换行+可选参数"不是 `\[` 定界符；若 findstr 语义不够精确，用 Python 正则 `(?<!\\)\\[\(\)\[\]]` 逐行扫描（与 `scripts/fix_math_delimiters.py` 同一判据）。若有残留，重跑 `python scripts/fix_math_delimiters.py` 后重编译。

## 第 4 层：收尾与归档

### 4.1 清理项目根目录的误输出残留

**应然状态**（项目根只包含）：`main.tex`、`preamble.tex`、`chapters/`、`images/`、`build/`、工作区（`build_work/` 或 `tmp_work/`）。实际项目可能偏离这个清单，收尾时按下述判据清理。

**两类常见残留**：

1. **编译产物**：若编译时忘加 `-output-directory=build`（或手工跑过 `xelatex main.tex`），项目根会散落 `main.aux`、`main.log`、`main.pdf`、`main.toc`、`main.out`；**Windows 下即使带了参数**，根目录仍可能漏出 `main.synctex.gz`、`main.fdb_latexmk`、`main.fls` 等零散残留。判据：干净构建下这些文件只应出现在 `build/`，出现在项目根即为残留 → 删除（`build/` 内的同名文件保留）。
   - **优先用统一编译入口** `python scripts/compile_tex.py`——脚本固定带输出目录参数、每遍编译后自动按清单清扫根目录残留（清单含 `.aux/.log/.out/.toc/.pdf/.synctex/.synctex.gz/.fdb_latexmk/.fls/.xdv/.blg/.bbl`）；
   - 手工编译后用 `python scripts/compile_tex.py <项目根> --clean-only` 补扫一次；
   - 收尾核对：项目根 `main.*` 应只剩 `main.tex` 源文件。

2. **脚本副本**：项目根若出现 `convert.py`、`fix_formulas.py` 等工作脚本，确认它是否只是工作区脚本的误放副本（例如根目录有一份 `convert.py`、而 `build_work/` 里才是实际执行的版本）。若是副本 → 删除，保留工作区那一份。删除前先确认内容/行数差异，不要凭文件名判断。

### 4.2 保留工作区与原始缓存

**必须保留**：

| 目录 | 为什么保留 |
|---|---|
| `<LaTeX项目>/build_work/` 或 `tmp_work/` | 含 `convert.py`、`prep_NN.md`、`chNN_raw.tex`、`stats_NN.json`、辅助校验脚本——重跑/复现转换的唯一依据 |
| `<书名>/00-MinerU原始分块/` | 每个分块的原始结果——断点重试与回溯边界的依据 |

> 上表列的是工作区产物的**理想集合**，实际项目常有缺项，**不影响流程正确性**：
>
> - 泛函项目的 `build_work/` 实测只含 `convert.py`、`chNN_raw.tex` 与辅助校验脚本，**没有** `prep_NN.md` / `stats_NN.json`——那两样是点集项目 `tmp_work/` 的形态，因为两本书的转换脚本实现不同（前者单遍、后者两遍流程，见 `stage2-chapter-conversion.md` §4.5）；
> - 因此收尾时**不要**仅因"少了一个中间文件"就判定产物不完整：保留实际存在的脚本、中间产物与原始分块缓存即可。

**可以清理**：`build/` 中的中间产物（`aux` / `toc` / `out` / `log`）在归档时可保留 `main.pdf`，其余按需删除；但**下次编译前若动过结构必须清空**。

### 4.3 归档与登记

- [ ] 成品 PDF：`build/main.pdf` 存在且页数正确（以 `Output written on build/main.pdf (N pages).` 为准；本项目最终版实测：泛函 257 页、点集 245 页。注意 `00-总计划.md` 中记录的 319/318 页为**页边距优化（geometry 2.2cm）前**的历史值，勿以其为准）；
- [ ] Markdown 包 + LaTeX 源码 + 编译 PDF 均留在同一工作根下；
- [ ] 把本阶段的真实统计与**已知残留问题**写回总计划文档：
  - 章数 / **`theorem` 环境数** / 定理族环境合计 / `\label` 数 / `\cref` 数 / 图片数；
  - 未识别定理头（如本项目点集拓扑的 `定理1.7.1`、`定理7.2.8`、`定理10.3.5`、`推论5.2.5`、`推论7.2.9` 五处仍为裸文本）；
  - 待人工校对的 OCR 疑点（如目录中人名拼写"Tuley"应为"Tukey"）；
  - 可接受告警清单及理由。
- [ ] 版权约束复核：产物仅个人学习使用，不上传公开网络。

## 验收结论模板

```
编译层：0 错误 / 0 undefined / 已连跑 N 遍收敛        [通过 / 不通过]
结构层：chapter 数 = toc 条目数 = 章文件数 (a=b=c)    [通过 / 不通过]
        编号按章递增，无第 0 章                        [通过 / 不通过]
        环境配对无差异 / 图片缺失 0                    [通过 / 不通过]
内容层：封面·目录·正文抽检 x 页，无缺字/无截断/公式正确 [通过 / 不通过]
        引用类型名正确（定义/引理/命题/推论 ≠ 一律"定理"）[通过 / 不通过]
        前置页无空白页（openany 生效）                 [通过 / 不通过]
收尾  ：根目录无编译产物/脚本残留 / 工作区与原始缓存已保留 [通过 / 不通过]
残留  ：<未识别定理头 5 处 / OCR 疑点 n 处，已登记>    [已登记]
```
