---
name: pdf-textbook-to-tex-textbook
description: 把授权的数学/理工教材 PDF（含扫描图像型）转成可编译的 LaTeX 精排项目并产出 PDF。当用户提出"把 PDF 教材/讲义转成 LaTeX 重排版""生成带定理环境的 tex 项目""按章拆分成 tex 并编译成 PDF""PDF 教材转 tex"时触发。两阶段流程：先用 mineru-textbook-to-md 把 PDF 转 Markdown，再逐章转 LaTeX（ctexbook + amsthm 定理族 + cleveref 交叉引用）并编译验证；内置定理编号惯例、定理环境规范化、编译排错与验收清单。
---

# PDF 教材 → LaTeX 精排项目

## 概述

把一本（或多本）授权的教材 PDF 转成**可编译、可编辑、排版规范**的 LaTeX 项目，最终产出 PDF。分两个阶段：

1. **阶段 1（PDF → Markdown）**：调用同目录工具 `mineru-textbook-to-md`（MinerU 云端 API + PDF 书签语义分块），产出按篇/章组织的 Markdown 文档包（`full.md` + 章文件夹 + 本地图片 + 质量报告）。
2. **阶段 2（Markdown → LaTeX）**：pandoc 初转 + 定理环境规范化 + 公式修复 + 逐章编译，产出 ctexbook 项目与成品 PDF。

适用教材特征：数学/理工类，含大量定理/定义/证明/公式与插图，通常为**扫描图像型 PDF**（每页为一张位图，靠 OCR/VLM 识别，公式有少量误差属预期，精排阶段需对照原书修正）。

## Use This Skill When

- 用户要把教材/讲义 PDF 转成 LaTeX 重排版，或"转 tex 并编译成 PDF"
- 用户要生成带定理族环境（定理/定义/引理/命题/推论/例/注/证明）与交叉引用的 tex 项目
- 用户已用 MinerU 转出了 Markdown，要接着做 LaTeX 精排
- 用户提到 `ctexbook`、`amsthm`、定理环境、交叉引用（`\cref`）、扫描版教材、按章拆分成 tex

**不适用**：单个公式/单页的转换；论文、报告等非教材文档（可能更适合直接排版而非拆分章环境）。

## 前置条件

| 依赖 | 用途 | 备注 |
|---|---|---|
| Python 3.10+ | 转换脚本 | |
| MinerU Token | 阶段 1 上传解析 | 环境变量 `MINERU_OFFICIAL_API_TOKEN`，**勿写入任何文件** |
| TeX Live（`xelatex`） | 阶段 2 编译 | 实测 `fontset=windows` 可用；字体异常时可改 `fandol` |
| `pandoc` | Markdown → LaTeX 初转 | 3.x 会引入 `\pandocbounded`（见陷阱 5） |
| `mineru-textbook-to-md` | 阶段 1 工具 | 用法见 `references/stage1-markdown-conversion.md` |

**安全与授权**：上传 PDF 到 MinerU 前必须确认用户已授权；产出仅限个人学习使用，不对外分发。Token 只从环境变量读取，禁止打印或落盘。

## 工作流

### 阶段 0：准备与决策

1. 确认输入 PDF、输出目录、书名、最终交付物（Markdown 包 + LaTeX 源码 + 编译 PDF）。
2. 核查环境（Python / Token / TeX Live / pandoc）。
3. 多本书时建议建一个总计划文档（含进度跟踪表），后续接续工作以它为准，避免重复已确认决策。

### 阶段 1：PDF → Markdown

详见 `references/stage1-markdown-conversion.md`。要点：

1. **先本地预览分块**：用 `--plan-only` 生成分块计划（纯本地书签解析，不上传、不需 Token），人工审核边界是否落在书签起始页上。
2. **正式上传**：工具按书签语义分块，大文件自动切多块并按序合并；失败可**断点重试**（已完成分块的缓存会被复用，只重传缺失页段）。
3. **书签缺陷处理**：若原 PDF 书签缺失/错误导致拆章不全，改用 `--from-full-md --split-by chapter`（走正文标题路径，不依赖书签）重拆。
4. **质检**：章数与书签树一致、图片引用全部有效、抽查公式渲染质量。

### 阶段 2：Markdown → LaTeX

详见 `references/stage2-latex-template.md` 与 `references/stage2-chapter-conversion.md`。三步：

**2.1 模板设计**（先做，阻塞后续步骤）

- 从 `templates/` 复制 `preamble.tex` + `main.tex` 作为骨架，建 `chapters/`、`images/`、`build/`。
- 文档类 `ctexbook` + **`openany`**（避免空白页，见陷阱 3）+ `fontset=windows`。
- 定理族用 `amsthm`；**计数器惯例**：definition/lemma/proposition/corollary 与 theorem 共享同一编号序列（同章内连续编号），example/remark 用独立计数器。
- 交叉引用用 `hyperref` + `cleveref`。**关键细节**：cleveref 按 label 绑定的**计数器名**判定引用类型，因此共享编号序列的这 4 类环境必须用 **`aliascnt`** 各自建立独立计数器名，否则它们的 `\cref` 会**全部渲染成「定理 X」**（`\crefname` 形同虚设、且编译不报错）。`templates/preamble.tex` 已按此配置，详见 `references/stage2-latex-template.md`。
- 用一份样例内容通过编译**冒烟测试**后，再进入 2.2。

**2.2 逐章转换**

- 用 `pandoc` 将各章 Markdown 初转为 `.tex`。
- 正则识别定理头（如 `**定理 1.2.3**（名称）` → `\begin{theorem}[名称]\label{thm:<章>-<章内序数>}`），并**排除引用句**（"定理 1.2.3 表明…"是引用而非定理头）。**label 编码**为 `<前缀>:<章号>-<章内序数>`（如 `thm:7-8` 表示"第 7 章第 8 个 theorem 环境"），**不是**把书内编号连字符化。参考实现见 `scripts/convert.py`，label 约定详见 `references/stage2-chapter-conversion.md`。
- 采用**两遍流程**：先扫描全书定理头建立「编号 → label」全局映射，再做后处理生成 `\label` 与 `\cref`，确保跨章交叉引用正确。
- 修复 MinerU OCR 公式误差（对照原书；见陷阱 7）。
- **全角符号 → 半角符号**：用 `scripts/fix_fullwidth.py` 把所有 `.tex` 文件中的全角标点（，。：；？！（）等）替换为半角，适用于全部教材（见陷阱 12）。
- **公式定界符统一**：pandoc 会把 Markdown 的 `$…$` / `$$…$$` 转成 `\(...\)` / `\[...\]`；用 `scripts/fix_math_delimiters.py` 回替换为美元符号形式——**行内公式只能用单美元 `$...$`、行间公式只能用双美元 `$$...$$`**（编码规范，详见 `references/stage2-chapter-conversion.md` §7.6）。
- 图片复制到 `images/`，正文 `\includegraphics` 直接用文件名（`\graphicspath` 已指向 `images/`）。

**2.3 编译验证**

- **统一编译入口**：`python scripts/compile_tex.py [项目根] [--engine xelatex|lualatex]`——脚本固定带 `-output-directory=build`（杜绝忘加参数导致产物散落根目录），每遍后自动清扫根目录残留（Windows 下 `-output-directory` 未完全隔离，会漏出 synctex/fdb/fls 等），自动检测 `Rerun` 提示并补跑至收敛（≤3 遍），结尾输出页数/错误/undefined 摘要。手工编译仍须遵守：`xelatex -interaction=nonstopmode -output-directory=build main.tex` **连跑 2–3 遍**，收尾按 `acceptance-checklist.md` §4.1 清根目录残留。
- 本阶段目标：**0 错误、0 undefined**（交叉引用全收敛）。排版类告警（`Overfull`/`Underfull`/`Missing character`/字体替换）通常**无法归零**，须按 `references/compilation-and-troubleshooting.md` 分级评估：量级可忽略的登记即可，**超出页边距（约 2.2cm）的溢出必须修**（见陷阱 8）。

### 阶段 3：验收与交付

详见 `references/acceptance-checklist.md`。**不能只看编译错误数**——必须同时核验：

1. 目录（`main.toc`）中 `chapter` 条目数 = 实际章数；
2. 定理/小节编号按章递增（不是 `0.x`）；
3. 图片引用无缺失（`images/` 文件数 ≥ 被引用数）；
4. 渲染抽查（封面、目录、正文）中文无缺字、公式正确、无截断。

## 关键决策与默认值

| 决策 | 默认值 | 理由 |
|---|---|---|
| 文档类 | `ctexbook` + `openany` | 中文书籍；`openany` 消除强制右页起排产生的空白页 |
| 字号/字体 | `zihao=-4`、`fontset=windows` | 正文小四；Windows 系统字体（异常时改 `fandol`） |
| 页边距 | `geometry` 左右 2.2cm / 上下 2.5cm | 紧凑版面，避免整页大片留白 |
| 溢出容忍 | `\emergencystretch=3em` | 全局缓解长公式 `Overfull \hbox` |
| 定理计数器 | theorem 主计数器 + 4 类共享编号序列（用 `aliascnt` 各建独立计数器名）；example/remark 独立 | 国内教材连续编号惯例；`aliascnt` 让 cleveref 能区分类型名 |
| 交叉引用 | `\cref` + 中文 `\crefname` + `aliascnt` | 共享编号序列下仍渲染正确类型名（定义/引理/命题/推论） |
| 章文件 | `chapters/chNN.tex`；`main.tex` 挂 `\chapter{}` + `\input{}` | 章标题只写在 main.tex，章文件内不重复写 `\chapter` |
| 标签格式 | `def:` / `thm:` / `lem:` / `prop:` / `cor:` / `ex:` / `rem:` | 便于检索与引用 |
| 公式定界符 | 行内 `$...$`、行间 `$$...$$`；**禁用** `\(...\)` / `\[...\]` | 编码规范；pandoc 输出需经 `scripts/fix_math_delimiters.py` 回替换；amsmath 环境（equation/align）不受约束 |
| 编译 | `scripts/compile_tex.py`（固定 `-output-directory=build` + 自动清根目录残留 + 自动补跑收敛）；手工编译 `xelatex` 连跑 2–3 遍，产物只进 `build/` | 封装命令杜绝漏参数；Windows 下 `-output-directory` 未完全隔离须主动清扫 |

## 常见陷阱（必读）

完整版见 `references/pitfalls.md`，最关键的十二条：

1. **aux 损坏**：报大量连锁错误（含 `\@newl@bel`、`\@@BOOKMARK`、`Text line contains an invalid character`）时，**先清空 `build/` 目录重编译**，再判断真实错误，勿逐条排查源码。改动 `\documentclass` / `geometry` / preamble 等**全局参数后必须清 build 重建 aux**。
2. **零错误 ≠ 结构正确**：`main.tex` 漏写 `\chapter{}` 会让全书退化到"第0章"、编号变 `0.x`，且**不产生任何编译报警**。验收必须查目录与编号。
3. **前置页空白页**：book 类默认 `openright` 强制章/目录从奇数页起排，会在标题页与目录页之间插入一页空白 → `\documentclass` 加 `openany`。
4. **封面多余文字**：`\bookinfo{书名}{作者}` 的**第二参数是作者名**，`\maketitle` 会排在标题下方；只要书名时留空（`\bookinfo{书名}{}`）。
5. **preamble 必备宏包**：`mathrsfs`（`\mathscr`）、`xcolor`（`\textcolor`）、`\providecommand{\pandocbounded}[1]{#1}`（pandoc 3.x 图片命令透传）。缺任一都会报 `Undefined control sequence`。
6. **环境嵌套断裂**：`\begin{theorem}` / `\begin{proof}` 等缺对应 `\end`，会引发 `\begin{...} ended by \end{document}` 连锁错误，须补齐闭合标签。
7. **OCR 公式错误**：高频错误包括 `\var D`（应为 `\mathcal{D}`）、`\$` / `\_` / `\textgreater{}` 误入数学模式、`\boldsymbol` 过度嵌套导致内存膨胀。
8. **收窄边距 → 溢出**：长行内公式在数学模式内**不自动换行**，文本区变窄会顶出边界。按量级分级：**≤ 4pt** 属可忽略；溢出量超过页边距宽度（约 62pt = 2.2cm）会被 PDF 裁切丢内容，**必须**定位源头修复。全局 `\emergencystretch` 可消除大部分。
9. **编译日志误报**：`not found` 可能来自 `pdftexcmds` 包信息行，`rerun` 可能匹配到包名 `rerunfilecheck`——均非真问题。但改动结构后官方提示 `Rerun to get cross-references right` 为**真**，须补跑收敛。
10. **页面核查用文本提取**：分批视觉/OCR 分析可能给出互相矛盾的结论（例如未看某页却判定其空白）；判断某页是否空白应以该页**文本提取**结果为准。
11. **共享计数器 + cleveref 类型名失效**：definition/lemma/proposition/corollary 与 theorem 共享计数器时，cleveref 无法区分类型，指向这几类的 `\cref` 会**一律渲染成「定理 X」**（`\crefname` 无效，且编译不报错）。必须用 `aliascnt` 为各环境建立独立计数器名；验收时须实测各类 `\cref` 的实际类型名——与陷阱 2 同属"静默错误"，只看编译结果发现不了。
12. **全角符号残留**：OCR/Markdown 转换会在 `.tex` 正文中混入全角标点（，。：；？！（）""''、—…等），影响排版一致性。用 `scripts/fix_fullwidth.py` 在编译前批量替换为半角；LaTeX 特殊字符的全角版本（％＃＆＿^\~等）自动转义为 `\%` `\#` `\&` `\_` 等。

## 参考文档

- `references/pipeline-overview.md` — 全流程总览与产物清单
- `references/stage1-markdown-conversion.md` — 阶段 1 详解（工具用法、书签缺陷、断点重试、服务端故障识别）
- `references/stage2-latex-template.md` — 模板设计与 preamble 逐项详解
- `references/stage2-chapter-conversion.md` — 逐章转换、定理头识别与引用句排除、两遍流程
- `references/compilation-and-troubleshooting.md` — 编译流程与排错手册
- `references/acceptance-checklist.md` — 验收清单
- `references/pitfalls.md` — 踩坑经验汇总
- `templates/preamble.tex`、`templates/main.tex` — 可直接复用的模板
- `scripts/convert.py` — 参考转换脚本（两遍流程：扫描全局 id_map + 后处理）
- `scripts/compile_tex.py` — 统一编译入口（固定 `-output-directory=build`、自动清根目录残留、自动补跑收敛）
- `scripts/fix_fullwidth.py` — 全角符号→半角符号批量替换脚本
- `scripts/fix_math_delimiters.py` — 公式定界符统一脚本（`\(...\)`/`\[...\]` → `$…$`/`$$…$$`）
