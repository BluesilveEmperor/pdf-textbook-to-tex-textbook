# 阶段 2.2 详解：逐章转换（定理头识别 · 引用句排除 · 两遍流程）

> 本文档解决什么问题：把"一章 Markdown 怎么变成一章可编译的 LaTeX"讲清楚——pandoc 初转、定理头正则、怎么把"引用定理的句子"与"定理本身"分开、为什么要两遍、证明环境与图片怎么处理、OCR 公式错误怎么修。

参考实现：`scripts/convert.py`（两遍流程范式）、`templates/` 配套的章文件产物 `chapters/chNN.tex`。本文所有规则都来自这两个真实实现。

## 1. 总览：一条章的多步流水线

```
01-原文解析.md
   │
   ├─[pass1] prep_md  剥离元信息 / 章标题 / 索引区；标题层级归一
   │         pandoc   初转 raw.tex
   │
   ├─[scan]  全书扫描所有 raw.tex 的定理头 -> 全局 id_map
   │         （编号 -> label 的唯一映射表，全书唯一真相）
   │
   └─[pass2] post_tex 用全局 id_map 生成 \label 与 \cref
             定理族环境 / proof 环境 / 图片复制 / OCR 修复
             -> chapters/chNN.tex
```

`pass1` 与 `scan` 对**全书**执行，`pass2` 逐章输出。顺序不可颠倒：没有全局 id_map 就无法在 pass2 中生成正确的 `\cref`。

## 2. pandoc 初转

### 2.1 预处理 `prep_md`（pass1）

原始 `01-原文解析.md` 需要先做几处"外科手术"，否则 pandoc 会把元信息、章标题、索引区一起搬进 tex：

| 处理 | 规则 |
|---|---|
| 剥 YAML 头 | 删除开头的 `---\n…\n---\n` |
| 定位正文 | 删除 `## 原文` 标题行之前的全部内容 |
| 去章标题 | 删除正文首个 `## 第X章…`（章标题由 `main.tex` 的 `\chapter` 提供，章文件内不得重复） |
| 截断索引 | 遇到 `### 索引` 即截断（章末索引区不进正文） |
| 标题还原 | `### 例 X` / `### 证…` / `### $公式` 去掉 `###` 前缀还原为普通段落 |
| 层级归一 | `### 1.2.3 标题` → `#`/`##`（按点号个数定深度）；`### 习题` → `# 习题`；其余 `### ` → `## ` |

### 2.2 转换命令

```powershell
pandoc -f markdown+tex_math_dollars-smart-auto_identifiers `
       -t latex-smart --wrap=none `
       prep_01.md -o ch01_raw.tex
```

关键参数：

| 参数 | 作用 |
|---|---|
| `+tex_math_dollars` | 让 `$...$` / `$$...$$` 直接映射为数学模式 |
| `-smart` | 关闭智能标点（不要在这里替换引号/连字符，交给后续处理） |
| `-auto_identifiers` | 关闭标题自动 id（避免 pandoc 生成一堆无用的 `\label`） |
| `--wrap=none` | 不按列宽折行（保证"一个段落=一块行"，便于后续按块处理） |

> pandoc 3.x 会把插图包成 `\pandocbounded{\includegraphics...}`，因此 preamble 必须有 `\providecommand{\pandocbounded}[1]{#1}` 透传（见 `stage2-latex-template.md` §4.3）。

## 3. 定理头识别：`HEAD_RE`

### 3.1 正则

```python
TYPE_RE = "(定义|定理|引理|命题|推论|例|注)"
HEAD_RE = re.compile(
    r"^" + TYPE_RE + r"\s*(\d+(?:\.\d+)+)\s*"
    r"(?:[（(]([^（）()]{1,60})[）)])?"
)
```

三个捕获组：**类型**、**编号**、**可选名称**。要点：

- `\s*` 允许"定义1.4.2"（OCR 常省略空格）与"定义 1.7.1"两种写法；
- 编号要求 `\d+(\.\d+)+`，即**至少两段**（`1.7`、`1.7.1` 都行，孤立的 `1` 不算），这条规则天然过滤掉了"例 1"这类列举；
- 名称括号最长 60 字符，且内部不再嵌套括号。

### 3.2 判定函数 `match_head` 的完整决策树

```
一行以"定理/定义/…"+编号开头
   │
   ├─ 抓到了 (名称) 括号？
   │     ├─ 名称是"纯数字"或"单个字母"   -> 不是名称，是列举 -> 继续往下判
   │     └─ 有真实名称                   -> ★ 定理头（名称进 \begin{env}[名称]）
   │
   ├─ 类型是"例"？                       -> ★ 定理头（例的标题常直接就是名称短语，如"例 2.2.5 可数补空间."）
   │
   ├─ 编号后有剩余文本 rest？
   │     ├─ rest 为空                    -> 不是定理头
   │     ├─ rest 首字符是标点            -> 不是定理头（是上句的续写）
   │     └─ rest 命中 REF_PREFIX_RE      -> 不是定理头（是引用句）
   │
   └─ 否则                              -> ★ 定理头
```

### 3.3 为什么必须有"引用句排除"

教材正文里大量出现形如"**定理 1.2.3 表明……**""**定理 1.2.3 是……的推广**"的句子。它们与真正的定理头在**字符层面几乎完全同形**——都是"类型 + 编号 + 文本"。如果只按 `HEAD_RE` 匹配，这些句子会被误判成新定理头，后果是：

- 正文里凭空多出一个 `\begin{theorem}` 环境（编号错乱）；
- 真正的定理环境被这个假环境"吃掉"后续段落（环境嵌套断裂）；
- 同编号被 `id_map` 记成重复（`dups`）。

### 3.4 `REF_PREFIX_RE` 与判定策略

实现采用**三路合取**的排除策略：

```python
# 1) 标点开头 —— 一定是上句的续写
PUNCT_START = set("，。、；：！？,.;:!?）)】》°")

# 2) 引用句特征前缀黑名单（节选，完整词表见 scripts/convert.py）
REF_PREFIX_RE = re.compile(
    r"^(结合|可|告|能|得|的|中|可见|可知|即|所述|表明|指出|说明|蕴含|推出|给出|概括|"
    r"便是|就是|此即|亦即|从而|于是|故|所以|因此|由|根据|从|应用|利用|使用|借助|…"
    r"|是.{0,30}的(推广|特例|证明|陈述|例子|应用|情形|推论|说明|解释|意义|版本)|…)"
)

# 3) 无名称括号 + 上面任一命中 -> 不是定理头
```

> 上面代码块中的 `REF_PREFIX_RE` 是**节选**（为便于阅读做了省略与截断）：完整词表还包含 `便是 / 就是 / 此即 / 亦即 / 上述 / 下面 / 如下 / 称为 / 叫做 / 是…的推广|特例|证明… / 有…解释|应用|意义…` 等 20 余个词条与两条句式规则。**以 `scripts/convert.py` 的实现为准**，本节示例只保留与下文案例直接相关的部分。

辅助探索脚本 `check_wl.py` 用的是**反向的白名单**思路（首字须落在 `设令对如称是有则假当定记若在任每存` 或数学起始符 `\( $ \pmb \mathbb \mathcal \text` 中才算定理头），说明"首字策略"有黑白名单两种做法：

- **黑名单（当前实现）**：只要命中引用特征就排除 → 召回高，但会把"正文恰好以这些字开头"的真定理头误杀；
- **白名单**：只认"教材定理正文惯用首字" → 精确高，但新书/新文风需要不断补词。

### 3.5 真实误判案例（重要）

本项目实测：黑名单策略造成 **5 处真定理头被漏识别**，最终记录在 `tmp_work/missing_refs_all.txt`：

| 原文（`prep_NN.md`） | rest 首字命中 | 后果 |
|---|---|---|
| `定理 1.7.1 可数集的任何子集都是可数集.` | `可` | 未被识别为环境 → 无 label → 正文引用"定理1.7.1"无法解析 |
| `推论 5.2.5 可分度量空间的每一个子空间都是可分空间.` | `可` | 同上（`推论5.2.5`） |
| `定理7.2.8 从紧致空间到Hausdorff空间的任何一个连续映射都是闭映射.` | `从` | 同上（`定理7.2.8`） |
| `推论 7.2.9 从紧致空间到 Hausdorff 空间的任何一个既单且满的(即一一的)连续映射都是同胚.` | `从` | 同上（`推论7.2.9`） |
| `定理10.3.5 从拓扑空间 $X$ 到拓扑空间 $Y$ 的一个连续映射 …` | `从` | 同上（`定理10.3.5`） |

而下面这些是**正确排除**的引用句（黑名单命中了本该命中的）：

| 原文 | 命中 | 说明 |
|---|---|---|
| `定理 2.3.2 概括了邻域系的基本性质.` | `概括` | 引用句 |
| `定理 4.2.6 可以得到进一步的改进. (参见本节习题 4.)` | `可` | 引用句 |
| `定理4.2.7给出了利用拓扑不变性质判定两个空间不同胚的第一个实例.` | `给出` | 引用句 |
| `定理 5.1.6 告诉我们，满足第二(或第一)可数性公理的性质是有限可积的拓扑性质。` | `告` | 引用句 |
| `推论7.2.2结合定理7.1.5可见：` | `结合` | 引用句 |

**结论与对策**：黑名单的"可 / 从 / 能 / 得 / 告"等单字过于宽泛。生产实践中应至少做以下之一：

1. **收紧单字条目**：把"可/能/得/从"改为更具体的前缀（如"可以"、"可得"、"能够"、"从而/从…出发"），或要求其后紧跟标点/连接词；
2. **加结构性判据**：true 定理头之后通常紧跟"设/若/令/对/则"等正文起笔，或其后**没有**"了/可见/表明"等尾缀；
3. **以 `missing_refs` 收敛**：pass2 结束后按 `missing_refs_all.txt` 逐条回查原文——**只要出现"某编号被引用却查无 label"，就回原文确认它到底是引用句还是漏识别的定理头**。这是最低成本、最可靠的兜底。

> 说明：上述 5 处在最终章文件中仍是**裸文本段落**（既没变成定理环境，也没有 label），属**已知残留缺陷**，应在人工校对阶段补齐；它们不影响编译（0 错误），但会让对应引用退化为纯文本。

## 4. 两遍流程与全局 `id_map`

### 4.1 为什么要两遍

教材中**跨章引用**极其频繁。实测点集拓扑 `ch07.tex` 中引用了：

```
\cref{cor:1-2}  \cref{thm:1-26} \cref{def:3-8}
\cref{thm:4-28} \cref{thm:4-9}  \cref{thm:5-8}
\cref{thm:6-14} \cref{thm:6-17} \cref{thm:6-20} …
```

处理第 7 章时，必须已经知道第 1~6 章每个定理的 label。若"边读边编号"（单遍逐章），处理 ch07 时 ch01 的映射已经丢失，跨章引用只能退化为纯文本。

因此：**先全书扫一遍建表，再用表做后处理。**

### 4.2 pass1：prep + pandoc → `chNN_raw.tex`

### 4.3 scan：全书扫描构建 `id_map`

```python
def scan_heads(raws):
    id_map, counts, dups = {}, {}, []
    for ch in sorted(raws):
        tex = read(raws[ch])                        # ★ 先读入该章 raw.tex（实现中此处还做"习题/标题编号"归一）
        for para in split_paragraphs(tex):          # 按空行切块，只看块首行
            if 块首是 \section/\subsection/\begin{...}: continue   # 结构行跳过
            h = match_head(first)
            if not h: continue
            typ, num, name, rest = h
            key = (typ, num)                        # 书内编号作键
            if key in id_map:                       # 重复编号
                dups.append(...); continue          # 只记首现，不覆盖
            order = counts.get((ch, typ), 0) + 1
            counts[(ch, typ)] = order
            id_map[key] = {"label": f"{pfx}:{ch}-{order}", "ch": ch, "order": order}
    return id_map, dups
```

关键设计：

| 设计 | 说明 |
|---|---|
| 键 = `(类型, 书内编号)` | 如 `("定理", "1.7.1")`，直接对应正文里"定理 1.7.1"的写法 |
| 值 = `label` + 首现章 + 章内序数 | `label` 形如 `thm:1-26`、`def:3-8`、`cor:1-2` |
| 扫描前先归一 | 把 `\section{习题}` 改成 `\subsection*{习题}`，并去掉标题里的编号（避免把标题误当定理头） |
| 跳过结构行 | 以 `\section` / `\subsection` / `\begin{` 开头的块不参与识别 |
| 重复编号只记首现 | 同名编号第二次出现进入 `dups` 列表并打印，**不覆盖**已有映射 |

**label 命名约定**：`<abbr>:<章>-<章内序数>`。abbr 见 `TYPE_MAP`：

```python
TYPE_MAP = {
    "定义": ("definition", "def"), "定理": ("theorem", "thm"),
    "引理": ("lemma", "lem"),      "命题": ("proposition", "prop"),
    "推论": ("corollary", "cor"),  "例": ("example", "ex"),
    "注": ("remark", "rem"),
}
```

⚠️ **label 中的数字不是书内编号的后段**。例如 `thm:7-8` 表示"第 7 章第 8 个 theorem 环境"，它可能是书里的"定理 7.2.10"。这是刻意设计——因为 LaTeX 计数器与书内原始编号体系未必一一对应（见 §4.5），而交叉引用只要求"id_map 两侧一致"。

### 4.4 pass2：用全局 map 生成 `\label` 与 `\cref`

**生成 `\label`**：

```python
info = id_map.get(key)
if info is None:                                  # scan 未收录（保险分支）
    label, add_label = f"{pfx}:{ch}-?{num}", True
else:
    label = info["label"]
    add_label = (info["ch"] == ch and key not in local_seen)
if key in local_seen:
    stats["dup_ids"].append(f"{typ}{num}")         # 章内重复编号告警
local_seen.add(key)
head_line = f"\\begin{{{env}}}" + (f"[{name}]" if name else "")
if add_label:
    head_line += f"\\label{{{label}}}"
```

即：**同一个编号只在其"首现章"加一次 `\label`**；跨章重复或章内重复都只记告警、不再加 label（避免 LaTeX "multiply defined labels" 与引用指错）。

**生成 `\cref`**：

```python
CREF_RE = re.compile(TYPE_RE + r"\s*(\d+(?:\.\d+)+)")

def cref_repl(m):
    typ, num = m.group(1), m.group(2)
    info = id_map.get((typ, num))
    if info is None:
        stats["missing_refs"].append(f"{typ}{num}")   # 记入缺失清单
        return m.group(0)                             # 原样保留
    stats["n_cref"] += 1
    return f"\\cref{{{info['label']}}}"
```

于是正文中的"见定理 1.2.3"变成 `见\cref{thm:1-2}`；`\cref` 会按 `\crefname` 自动渲染成**中文**"定理 1.2"。

**缺失引用是重要信号**：`missing_refs` + `dups` 就是 pass2 的质量指标。收尾时输出 `missing_refs_all.txt`，逐条回查（见 §3.5）。

### 4.5 与单遍实现的对比（泛函分析版脚本）

另一本书的脚本采用**单遍 + 环境体延续词白名单**：

- 在 `convert_one()` 内维护 `label_map`（章内映射）与 `stats["seq"]`（各环境序号）；
- 环境体何时结束，用**启发式**判断：遇到结构头（标题 / 下一定理头 / 注 / 证 / 图 / 三位编号条目）即闭合；否则用 `CONT_WORDS`（`于是/因此/所以/从而/设/令/取/…`）白名单判断后续段落是否仍属于环境体；
- 好处是能处理"定理正文跨多个自然段"的情况；代价是**章内映射无法支撑跨章引用**（处理 ch07 时已无 ch01 的映射）。

**推荐范式**：以两遍流程（点集版）为准；若某章需要更强的"环境体边界"判断，可把 `CONT_WORDS` 白名单作为 pass2 内部的环境体闭合辅助，两者不冲突。

## 5. 证明环境识别

```python
PROOF_START_RE = re.compile(r"^证\s*(?:[（(]|\s|$)|^证明[:：]\s*")
PROOF_CONT_RE  = re.compile(
    r"^([（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨⑩]|反之|再证|先证|…|若|当|设|则|…|证毕|…)"
)
```

规则：

1. 段落以"证"或"证明："开头（且不在习题区）→ 开 `\begin{proof}`，并把"证"/"证明："前缀从正文中剥掉（`proofname` 已汉化为"证"，由环境自己排）。
2. 处于 proof 内时，后续段落**若命中 `PROOF_CONT_RE` 白名单**则视为证明的续段；否则**闭合证明**并把该段落排到证明外。
3. 遇到结构头（新标题 / 新定理头）时**强制闭合**当前环境——这是防止环境嵌套断裂的关键。
4. 习题区（`\subsection*{习题}` 之后）不识别证明，避免把习题解答误包装成 `proof`。

一个容易被忽略的细节：

```python
tex = tex.replace("\\section{习题}", "\\subsection*{习题}")
```

习题区用**星号章节**（不编号、不进目录），并且作为"环境收尾边界"。

## 6. 图片处理

```python
IMG_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{images/([^}]+)\}")
```

处理步骤：

1. 从 `\includegraphics{images/<哈希名>}` 提取文件名；
2. **三级查找源文件**（`find_image`）：章文件夹 `images/` → 书根 `images/` → `00-MinerU原始分块/*/images/`；
3. 复制到 LaTeX 项目的 `images/`（已存在则跳过）；
4. 替换为统一宽度，并**去掉 `images/` 前缀**（`\graphicspath` 已指向该目录）：

```latex
\includegraphics[width=0.8\textwidth]{<哈希名>}
```

5. **找不到源文件时不静默跳过**，而是插入醒目的占位标记：

```latex
\textcolor{red}{[缺图 <哈希名>]}
```

这样"缺图"会显式出现在 PDF 上，验收时一眼可见（这也是 preamble 必须加载 `xcolor` 的原因之一）。

## 7. OCR 公式修复

扫描版教材的公式错误属**预期**，逐处对照原书修正。本项目实测的高频错误与修法（`fix_formulas.py`）：

| 现象 | 示例 | 修法 |
|---|---|---|
| 花体字母被识别成普通变量 | `\var D` | `\mathcal{D}` |
| 伪命令（OCR 把 `\mathcal` 认成 `\itmath…`） | `\itOmega`、`\itmathbb` | `\Omega`、`\mathbb` |
| 数学符号落进纯文本 | `\$`、`\_`、`\textgreater{}` | 改为数学模式 `\( … > … \)` |
| 竖线被拆成文本命令 | `(\mathcal{X}, \textbar{} \cdot \textbar)` | `(\mathcal{X}, \|\cdot\|)` |
| `\boldsymbol` 过度嵌套 | `\boldsymbol{\boldsymbol{\boldsymbol{\boldsymbol{v}}}}` | 单层 `\boldsymbol{v}`（嵌套会显著膨胀编译内存） |
| 重复公式编号 | `\tag{3.5.5}\tag{3.5.5}` | 保留最后一个 `\tag` |
| `array` 嵌套层级错乱 | 多层 `\begin{array}` 包裹一行公式 | 展平为单层 `array`（如 `\left\{ \begin{array}{cccc} … \end{array} \right.`） |
| 定界符/上下标错位 | `\$\mu \_ \{ j \} 0 ( j \$ \(\infty )\)` | `\(\mu_{j} \to 0 \ (j \to \infty)\)` |

**严重损坏、无法一次修好的公式**：不要硬编造，改为显式标记，留给人工对照原书：

```latex
% TODO: 公式 OCR 严重损坏, 待人工对照原书校对
\textcolor{red}{\textbf{[此处公式 OCR 严重损坏, 待人工校对]}}
```

修复脚本应写成**可重复执行**（幂等）：

- 精确字符串替换前先 `if old in s`，找不到就打印 `[SKIP]` 而不是报错；
- 每处替换打印实际改动，便于回看；
- 用 `newline="\n"` 写文件，避免 Windows 换行污染 diff。

## 7.5 全角符号 → 半角符号替换

**时机**：在 OCR 公式修复（§7）之后、编译验证（§8）之前执行。这是逐章转换的最后一步后处理。

**原因**：MinerU OCR 识别中文 PDF 时保留原书的全角标点（`，。：；？！（）` 等），pandoc `-smart` 关闭后不会自动转换，`convert.py` 后处理也未覆盖。全角符号虽能编译通过，但与半角混排时间距不统一，且不符合排版一致性要求。

**工具**：`scripts/fix_fullwidth.py`

```powershell
python scripts/fix_fullwidth.py <LaTeX项目根目录>
```

**替换规则**：

| 类别 | 全角符号 | 半角替换 | 说明 |
|---|---|---|---|
| 安全替换 | `，→,` `。→.` `：→:` `；→;` `？→?` `！→!` `（→(` `）→)` | 直接替换 | 不影响 LaTeX 代码 |
| 安全替换 | `"→" "→"` `'→' '→'` `、→,` `—→--` `…→...` | 直接替换 | 中文引号/顿号/破折号/省略号 |
| 安全替换 | 全角空格 `　`→半角空格 | 直接替换 | |
| 需转义替换 | `％→\%` `＃→\#` `＆→\&` `＿→\_` | 转义后替换 | 防止触发 LaTeX 注释/参数/表格/下标语义 |
| 需转义替换 | `＼→\textbackslash` `｛→\{` `｝→\}` | 转义后替换 | |
| 需转义替换 | `～→\textasciitilde{}` `＾→\textasciicircum{}` | 转义后替换 | |

**注意**：替换后须清 `build/` 重编译（改动涉及全部 `.tex` 文件，属全局变更，见陷阱 1）。

**实测**（4 本书 33 个 `.tex` 文件）：共替换 5899 个全角符号，替换后 4 本书编译均 0 错误收敛。

## 8. 章文件产出与统计

pass2 每章输出 `chapters/chNN.tex`，同时写 `stats_NN.json`，字段即质量指标：

```jsonc
{
  "env": { "theorem": 28, "definition": 25, "corollary": 4, "lemma": 1 },
  "labels": [ "thm:1-1", "thm:1-2", "def:1-1", … ],
  "proofs": 27,
  "missing_refs": [ "定理1.7.1" ],
  "dup_ids": [],
  "images": [], "missing_imgs": [],
  "n_cref": 30,
  "n_lines_tex": 1918, "n_lines_md": 1372,
  "dup_ids_global": []
}
```

（上为点集拓扑第 1 章的真实统计。）收尾时汇总全书：环境计数、证明数、图片数、`\cref` 数、缺失引用清单。

**章文件头部**应注明来源，便于追溯：

```latex
%% ---- 第1章 (由 convert.py 自动生成, 源: 01-第一章 朴素集合论/01-原文解析.md) ----
```

## 9. 本阶段完成标准

- [ ] 每章 `chNN.tex` 生成，行数/环境数/证明数已记录；
- [ ] `missing_refs` 逐条回查（区分"引用句"与"漏识别定理头"）；
- [ ] `dup_ids` / `dups` 为空（或有明确、已记录的原因）；
- [ ] `missing_imgs` 为空（有缺图则补齐源文件后重跑）；
- [ ] 章文件内**不出现** `\chapter`（章标题只在 `main.tex`）；
- [ ] 进入 `compilation-and-troubleshooting.md` 的编译流程。
