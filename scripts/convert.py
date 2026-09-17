#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md -> LaTeX 逐章转换脚本（两遍流程，通用参考实现）
================================================================

用途
----
把 OCR/解析产物（每章一个目录，内含 `01-原文解析.md`）批量转换为
可直接被 ctexbook 项目 `\\input` 的 `chapters/chNN.tex`，并完成：

  * 定理族环境的识别与重建（定义/定理/引理/命题/推论/例/注）；
  * 证明环境的识别与包裹（`\\begin{proof} ... \\end{proof}`）；
  * 全局统一的 `\\label` 生成与正文中"定理 1.2"式引用的 `\\cref` 替换；
  * 插图复制到 `images/` 目录并改写为 `\\includegraphics`。

两遍流程原理
------------
第一遍（pass1 / prep + pandoc）
    `prep_md` 清洗 markdown（去 YAML front matter、去索引区、标题层级归一化、
    把"### 例 x.y"等降级为正文），再由 pandoc 转成未经后处理的 `raw.tex`。
    pandoc 输出此时只是"半成品"：定理仍是纯文本段落，没有环境与标签。

扫描（scan）
    `scan_heads` 遍历**全书**所有 `raw.tex`，按 (类型, 编号) 建立全局
    `id_map`，为每个定理分配唯一 `label`（前缀冒号格式，如 `thm:3-2`）。
    之所以必须先全书扫描，是因为交叉引用可能跨章出现：只有全书编号唯一，
    后处理生成的 `\\label` 才与 `\\cref` 一一对应。

第二遍（pass2 / post_tex）
    `post_tex` 依据全局 `id_map` 对单章 `raw.tex` 做后处理：
    包裹定理/证明环境、插入 `\\label`、把正文里的"定理 1.2"替换成 `\\cref`、
    搬迁并改写插图，最终写出 `chapters/chNN.tex` 与统计 JSON。

使用方法
--------
    python scripts/convert.py            # 转换全部章节
    python scripts/convert.py 3 4 5      # 只重转第 3、4、5 章

依赖：pandoc 需在 PATH 中可执行；本脚本使用 Python 3 标准库。

注意
----
**章节数、章名、路径均需按目标项目调整**，见下方「配置区」。
本脚本是参考实现：阅读它可了解两遍转换的设计，改造时只需改配置区，
不必改动下方函数逻辑。
"""
import re, subprocess, sys, os, json, shutil

# ======================================================================
# 配置区（需按实际项目修改）
# 下列路径为参考项目的真实值示例（迁移时整段替换即可）。
# 迁移到新项目时，只需修改本节中的常量，函数体无需改动。
# ======================================================================

# markdown 源根目录：其下每个子目录对应一章，目录名与 CHAPTERS 的值一致，
# 且每个章目录内需含 `01-原文解析.md`（以及可选的 `images/`）。
SRC_ROOT = r"D:\Documents\01_Study_Research\研一数学\点集拓扑讲义\99-未归类章节"

# 原始书籍资料根目录：用于兜底查找缺失插图（images/ 与 00-MinerU原始分块/）。
BOOK_ROOT = r"D:\Documents\01_Study_Research\研一数学\点集拓扑讲义"

# LaTeX 项目根目录：即 main.tex / preamble.tex 所在目录，
# 转换产物写入其下的 chapters/ 与 images/。
LATEX_ROOT = r"D:\Documents\01_Study_Research\研一数学\03-latex\点集拓扑"

# 中间产物目录：存放 prep_*.md、chNN_raw.tex、stats_*.json。
WORK = os.path.join(LATEX_ROOT, "tmp_work")

# 章号 -> 源章节目录名。键为整数章号，值为 SRC_ROOT 下的子目录名。
# 迁移到新项目时替换本字典（章数、章名均按目标项目调整）。
CHAPTERS = {
    1: "01-第一章 朴素集合论", 2: "02-第二章 拓扑空间与连续映射",
    3: "03-第三章 子空间，积空间，商空间", 4: "04-第四章 连通性",
    5: "05-第五章 有关可数性的公理", 6: "06-第六章 分离性公理",
    7: "07-第七章 紧致性", 8: "08-第八章 完备度量空间",
    9: "09-第九章 映射空间", 10: "10-第十章 基本群及其应用",
}

# ======================================================================
# 以下为转换逻辑，通常无需修改
# ======================================================================

# 中文类型名 -> (LaTeX 环境名, 标签前缀)。
# 标签前缀遵循「前缀冒号」约定：def:、thm:、lem:、prop:、cor:、ex:、rem:。
# 环境名须与 preamble.tex 中的 \newtheorem 定义严格一致。
TYPE_MAP = {
    "定义": ("definition", "def"), "定理": ("theorem", "thm"),
    "引理": ("lemma", "lem"), "命题": ("proposition", "prop"),
    "推论": ("corollary", "cor"), "例": ("example", "ex"),
    "注": ("remark", "rem"),
}
TYPE_RE = "(定义|定理|引理|命题|推论|例|注)"

# 定理头形如："定理 1.2（名称）" 或 "定义 3.1.4"。编号至少两段（x.y）。
HEAD_RE = re.compile(
    r"^" + TYPE_RE + r"\s*(\d+(?:\.\d+)+)\s*"
    r"(?:[（(]([^（）()]{1,60})[）)])?"
)
# 引用句特征前缀 (rest 以这些开头 => 不是定理头，而是正文对定理的引用)
REF_PREFIX_RE = re.compile(
    r"^(结合|可|告|能|得|的|中|可见|可知|即|所述|表明|指出|说明|蕴含|推出|给出|概括|"
    r"便是|就是|此即|亦即|从而|于是|故|所以|因此|由|根据|从|应用|利用|使用|借助|"
    r"表明了|说明了|指出了|推出了|蕴含了|给出了|概括了|同胚|等价|这个|这些|其|它|本|该|此|"
    r"上述|下面|如下|称为|叫做|"
    r"是.{0,30}的(推广|特例|证明|陈述|例子|应用|情形|推论|说明|解释|意义|版本)|"
    r"有(一个|几种|若干).{0,30}(解释|应用|意义|例子|情形|说明|改进|版本))"
)
# 标点开头必为引用/续句，而非定理头
PUNCT_START = set("，。、；：！？,.;:!?）)】》°")

# 证明起始：段首为"证"或"证明："。
PROOF_START_RE = re.compile(r"^证\s*(?:[（(]|\s|$)|^证明[:：]\s*")
# 证明续段特征：以下列词开头则视为同一证明的延续段落，不闭合 proof 环境。
PROOF_CONT_RE = re.compile(
    r"^([（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨⑩]|反之|再证|先证|又证|另证|充分性|必要性|"
    r"若|当|设|则|另外|再|又|而且|并且|于是|因此|所以|从而|首先|其次|最后|事实上|"
    r"显然|即|故|而|综上|这就是|由|充分|必要|根据|现在|此外|同时|另一方面|因为|由于|"
    r"为此|亦即|换句话说|证毕|对|无论|只要|注意|特别地|特别|一般地|一般|但|但是|"
    r"然而|也就是说|上述|剩下|余下|只须|只需|可得|可知|易见|易知|不难|仿照|于是有|"
    r"综合|归纳|既然|确切|更|并|如|凡|任|每|所有|任何)"
)

# pandoc 输出的插图：\includegraphics{images/xxx.png}
IMG_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{images/([^}]+)\}")
# 正文中的定理引用："定理 1.2" 形式，用于替换为 \cref。
CREF_RE = re.compile(TYPE_RE + r"\s*(\d+(?:\.\d+)+)")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)


def match_head(line):
    """判定一行是否定理头; 返回 (typ, num, name, rest) 或 None"""
    m = HEAD_RE.match(line)
    if not m:
        return None
    typ, num, name = m.group(1), m.group(2), m.group(3)
    rest = line[m.end():].lstrip()
    if name and re.fullmatch(r"\s*\d+\s*|\s*[A-Za-z]\s*", name):
        name = None  # 纯数字/单字母括号 => 列举, 非名称
    if typ == "例":
        return (typ, num, name, rest)
    if name:
        return (typ, num, name, rest)  # 有名称括号 => 定理头
    if not rest or rest[0] in PUNCT_START or REF_PREFIX_RE.match(rest):
        return None  # 无名称且 rest 为引用句/标点开头 => 非定理头
    return (typ, num, name, rest)


# ----------------------------------------------------------------------
# pass1: 预处理 markdown
# ----------------------------------------------------------------------
def prep_md(ch):
    """清洗单章 markdown，供 pandoc 转换。

    注意：本函数中的正则清洗规则（如"### 例 x.y"降级、章末索引区删除、
    "现回忆几个已知的事实"标题合并等）是针对本书 markdown 解析产物总结的，
    迁移到其他项目时应按目标 md 的实际结构增删这些规则。
    """
    src = os.path.join(SRC_ROOT, CHAPTERS[ch], "01-原文解析.md")
    text = read(src)
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    if m:
        text = text[m.end():]
    m = re.search(r"^## 原文\s*$", text, re.M)
    if m:
        text = text[m.end():]
    text = re.sub(r"^## 第.+?章.*$\n?", "", text, count=1, flags=re.M)
    m = re.search(r"^### 索引\s*$", text, re.M)
    if m:
        text = text[:m.start()]
        print(f"  [prep] 已删除章末索引区")
    text = re.sub(r"^### 现回忆几个已知的事实：\s*$", "现在回忆几个已知的事实：", text, flags=re.M)
    text = re.sub(r"^### (例\s*\d.*)$", r"\1", text, flags=re.M)
    text = re.sub(r"^###\s+(证.*)$", r"\1", text, flags=re.M)
    text = re.sub(r"^###\s+(\$)", r"\1", text, flags=re.M)

    def sect_repl(m):
        title = m.group(2).strip()
        depth = m.group(1).count(".") + 1
        return ("## " if depth >= 3 else "# ") + title

    text = re.sub(r"^###\s+(\d+(?:\.\d+)+)\s+(.+)$", sect_repl, text, flags=re.M)
    text = re.sub(r"^###\s+习题\s*$", "# 习题", text, flags=re.M)
    text = re.sub(r"^### ", "## ", text, flags=re.M)
    out = os.path.join(WORK, f"prep_{ch:02d}.md")
    write(out, text)
    return out


def pandoc_convert(prep_path, raw_path):
    cmd = ["pandoc", "-f", "markdown+tex_math_dollars-smart-auto_identifiers",
           "-t", "latex-smart", "--wrap=none", prep_path, "-o", raw_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("PANDOC STDERR:", r.stderr[:2000])
        raise RuntimeError("pandoc 转换失败")


# ----------------------------------------------------------------------
# scan: 全书扫描构建全局 id_map
# ----------------------------------------------------------------------
def split_paragraphs(tex):
    paras, cur = [], []
    for line in tex.split("\n"):
        if line.strip() == "":
            if cur:
                paras.append(cur); cur = []
        else:
            cur.append(line)
    if cur:
        paras.append(cur)
    return paras


def scan_heads(raws):
    """raws: {ch: raw_path}; 返回 id_map {(typ,num): {"label","ch","order"}} 和 counts"""
    id_map = {}
    counts = {}  # (ch, typ) -> order
    dups = []
    for ch in sorted(raws):
        tex = read(raws[ch])
        tex = tex.replace("\\section{习题}", "\\subsection*{习题}")
        tex = re.sub(r"(\\(?:sub)?section)\{\d+(?:\.\d+)+\s*", r"\1{", tex)
        for para in split_paragraphs(tex):
            first = para[0]
            if (first.startswith("\\section{") or
                    first.startswith("\\subsection") or
                    first.startswith("\\begin{")):
                continue
            h = match_head(first)
            if not h:
                continue
            typ, num, name, rest = h
            key = (typ, num)
            if key in id_map:
                dups.append(f"{typ}{num} (章{ch}, 首现于章{id_map[key]['ch']})")
                continue
            order = counts.get((ch, typ), 0) + 1
            counts[(ch, typ)] = order
            pfx = TYPE_MAP[typ][1]
            # 标签采用「前缀冒号」约定，并把章号编入名称以保证全书唯一
            id_map[key] = {"label": f"{pfx}:{ch}-{order}", "ch": ch, "order": order}
    return id_map, dups


# ----------------------------------------------------------------------
# pass2: 后处理生成 chNN.tex
# ----------------------------------------------------------------------
def post_tex(ch, raw_path, out_path, id_map):
    tex = read(raw_path)
    stats = {"env": {}, "labels": [], "proofs": 0, "missing_refs": [],
             "dup_ids": [], "images": [], "missing_imgs": [], "n_cref": 0}

    tex = tex.replace("\\section{习题}", "\\subsection*{习题}")
    tex = re.sub(r"(\\(?:sub)?section)\{\d+(?:\.\d+)+\s*", r"\1{", tex)

    paras = split_paragraphs(tex)
    out_lines = []
    in_proof = False
    exercise_zone = False
    local_seen = set()
    HEADER = ("\\providecommand{\\tightlist}{\\setlength{\\itemsep}{0pt}"
              "\\setlength{\\parskip}{0pt}}\n")
    out_lines.append(HEADER)

    def close_proof():
        nonlocal in_proof
        if in_proof:
            out_lines.append("\\end{proof}")
            in_proof = False

    for pi, para in enumerate(paras):
        first = para[0]
        if pi > 0 and out_lines and out_lines[-1].strip() != "":
            out_lines.append("")
        is_struct = (first.startswith("\\section{") or
                     first.startswith("\\subsection") or
                     first.startswith("\\begin{"))
        if first.startswith("\\subsection*{习题}"):
            exercise_zone = True
        elif first.startswith("\\section{"):
            exercise_zone = False

        # 定理头 -> 包裹为定理族环境 + \label
        h = match_head(first) if not is_struct else None
        if h:
            typ, num, name, rest = h
            env, pfx = TYPE_MAP[typ]
            key = (typ, num)
            info = id_map.get(key)
            if info is None:
                # scan 未收录 (理论上不会, 保险)
                label = f"{pfx}:{ch}-?{num}"
                add_label = True
            else:
                label = info["label"]
                add_label = (info["ch"] == ch and key not in local_seen)
            if key in local_seen:
                stats["dup_ids"].append(f"{typ}{num}")
            local_seen.add(key)
            head_line = f"\\begin{{{env}}}" + (f"[{name}]" if name else "")
            if add_label:
                head_line += f"\\label{{{label}}}"
                stats["labels"].append(label)
            out_lines.append(head_line)
            stats["env"][env] = stats["env"].get(env, 0) + 1
            if rest:
                out_lines.append(rest)
            out_lines.extend(para[1:])
            out_lines.append(f"\\end{{{env}}}")
            continue

        # 证明开始 -> 包裹 \begin{proof}
        if (not is_struct and not in_proof and not exercise_zone
                and PROOF_START_RE.match(first)):
            close_proof()
            out_lines.append("\\begin{proof}")
            in_proof = True
            stats["proofs"] += 1
            body0 = re.sub(r"^证明[:：]\s*|^证\s*", "", first, count=1)
            if body0.strip():
                out_lines.append(body0)
            out_lines.extend(para[1:])
            continue

        # 证明续段 -> 依据续段特征判断是否仍在证明内
        if in_proof:
            if is_struct:
                close_proof()
                out_lines.extend(para)
                continue
            if PROOF_CONT_RE.match(first):
                out_lines.extend(para)
                continue
            close_proof()
            out_lines.extend(para)
            continue

        out_lines.extend(para)

    close_proof()
    tex = "\n".join(out_lines) + "\n"

    # 交叉引用："定理 1.2" -> \cref{thm:1-2}（依赖全局 id_map）
    def cref_repl(m):
        typ, num = m.group(1), m.group(2)
        info = id_map.get((typ, num))
        if info is None:
            stats["missing_refs"].append(f"{typ}{num}")
            return m.group(0)
        stats["n_cref"] += 1
        return f"\\cref{{{info['label']}}}"

    tex = CREF_RE.sub(cref_repl, tex)

    # 图片：从源目录查找并复制到 LATEX_ROOT/images/，改写为 \includegraphics
    def img_repl(m):
        fname = m.group(1)
        base = os.path.splitext(fname)[0]
        stats["images"].append(fname)
        src = find_image(fname, ch)
        if src is None:
            stats["missing_imgs"].append(fname)
            return f"\\textcolor{{red}}{{[缺图 {fname}]}}"
        dst = os.path.join(LATEX_ROOT, "images", fname)
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        return f"\\includegraphics[width=0.8\\textwidth]{{{base}}}"

    tex = IMG_RE.sub(img_repl, tex)
    tex = tex.replace("[注]", "（注）")

    write(out_path, tex)
    stats["n_lines_tex"] = len(tex.split("\n"))
    return stats


def find_image(fname, ch):
    """按优先级在源工程中查找插图：章节 images/ -> 书根 images/ -> MinerU 分块。"""
    cands = [os.path.join(SRC_ROOT, CHAPTERS[ch], "images", fname),
             os.path.join(BOOK_ROOT, "images", fname)]
    chunks_dir = os.path.join(BOOK_ROOT, "00-MinerU原始分块")
    if os.path.isdir(chunks_dir):
        for d in sorted(os.listdir(chunks_dir)):
            cands.append(os.path.join(chunks_dir, d, "images", fname))
    for c in cands:
        if os.path.exists(c):
            return c
    return None


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def main():
    os.makedirs(WORK, exist_ok=True)
    chs = sorted(int(a) for a in sys.argv[1:]) or list(CHAPTERS)

    # pass1: 逐章预处理 + pandoc 转 raw.tex
    raws = {}
    for ch in chs:
        print(f"== pass1 第{ch}章 {CHAPTERS[ch]} ==")
        prep = prep_md(ch)
        raw = os.path.join(WORK, f"ch{ch:02d}_raw.tex")
        pandoc_convert(prep, raw)
        raws[ch] = raw

    # scan: 全书扫描，构建全局 id_map（保证跨章引用可解析）
    id_map, dups = scan_heads(raws)
    print(f"== scan: 全局 id_map {len(id_map)} 条, 重复编号 {len(dups)} 处 ==")
    for d in dups:
        print("   DUP:", d)

    # pass2: 逐章后处理，生成 chapters/chNN.tex
    all_stats = {}
    for ch in chs:
        out = os.path.join(LATEX_ROOT, "chapters", f"ch{ch:02d}.tex")
        s = post_tex(ch, raws[ch], out, id_map)
        src_md = os.path.join(SRC_ROOT, CHAPTERS[ch], "01-原文解析.md")
        s["n_lines_md"] = len(read(src_md).split("\n"))
        s["dup_ids_global"] = dups
        write(os.path.join(WORK, f"stats_{ch:02d}.json"),
              json.dumps(s, ensure_ascii=False, indent=1))
        all_stats[ch] = s
        print(f"== pass2 第{ch}章: md {s['n_lines_md']} -> tex {s['n_lines_tex']} 行, "
              f"环境 {s['env']}, 证明 {s['proofs']}, 图片 {len(s['images'])}, "
              f"cref {s['n_cref']}, 缺引用 {len(s['missing_refs'])} ==")

    # 全书统计汇总
    total_env = {}
    for s in all_stats.values():
        for k, v in s["env"].items():
            total_env[k] = total_env.get(k, 0) + v
    print("== 全书环境 ==", total_env)
    print("== 全书证明 ==", sum(s["proofs"] for s in all_stats.values()))
    print("== 全书图片 ==", sum(len(s["images"]) for s in all_stats.values()))
    print("== 全书 cref ==", sum(s["n_cref"] for s in all_stats.values()))
    miss = sorted(set(m for s in all_stats.values() for m in s["missing_refs"]))
    print(f"== 全书缺失引用 {len(miss)} 个 ==")
    for m in miss[:20]:
        print("   MISS:", m)
    write(os.path.join(WORK, "missing_refs_all.txt"), "\n".join(miss))


if __name__ == "__main__":
    main()
