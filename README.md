# pdf-textbook-to-tex-textbook

> 把授权的数学/理工教材 PDF 转成**可编译的 LaTeX 精排项目**并产出 PDF 的 Agent Skill。

## 这是什么

一个 **Agent Skill**：当用户提出「把 PDF 教材/讲义转成 LaTeX 重排版」「生成带定理环境的 tex 项目」「按章拆分成 tex 并编译成 PDF」时触发，指导 Agent 走完从 PDF 到成品 PDF 的完整流程。

适用于**数学/理工类**教材（含大量定理、定义、证明、公式与插图），尤其是**扫描图像型 PDF**（OCR/VLM 识别，公式存在少量误差属预期，精排阶段需对照原书校正）。

## 两阶段流水线

```
教材 PDF
   │
   ├─ 阶段 1：PDF → Markdown      （调用配套工具 mineru-textbook-to-md）
   │        产出：full.md + 按章文件夹 + 本地图片 + 质量报告
   │
   ├─ 阶段 2：Markdown → LaTeX    （pandoc 初转 + 定理环境规范化 + 公式修复 + 编译）
   │        产出：ctexbook 项目 + 成品 PDF
   │
   └─ 阶段 3：验收与交付           （编译层 / 结构层 / 内容层 三层核验）
```

## 目录结构

```
pdf-textbook-to-tex-textbook/
├── SKILL.md                                核心入口：工作流、决策默认值、常见陷阱
├── references/                             详细参考文档（7 篇）
│   ├── pipeline-overview.md                全流程总览与产物清单
│   ├── stage1-markdown-conversion.md       阶段 1：工具用法、书签缺陷、断点重试
│   ├── stage2-latex-template.md            阶段 2：模板设计与 preamble 逐项详解
│   ├── stage2-chapter-conversion.md        阶段 2：定理头识别、引用句排除、两遍流程
│   ├── compilation-and-troubleshooting.md  编译流程与排错手册
│   ├── acceptance-checklist.md             验收清单（可执行判据）
│   └── pitfalls.md                         踩坑经验（11 条，含现象/根因/修复/预防）
├── templates/                              可直接复用的 LaTeX 模板
│   ├── preamble.tex                        导言区（宏包、定理族环境、交叉引用）
│   └── main.tex                            主文件骨架
└── scripts/
    └── convert.py                          参考转换脚本（两遍流程：全局 id_map + 后处理）
```

## 使用方式

本 Skill 由 Agent 在匹配到触发场景时加载 `SKILL.md`。若需人工参考：

1. **读入口**：`SKILL.md` —— 了解全流程、关键决策默认值与必读陷阱。
2. **复用模板**：把 `templates/preamble.tex` + `main.tex` 复制到目标项目根，建 `chapters/`、`images/`、`build/`。
3. **参考转换脚本**：`scripts/convert.py` 的转换逻辑（定理头识别、两遍流程、`id_map`）可按目标项目调整后复用；顶部集中了需替换的路径配置。
4. **按参考文档执行**：阶段 1 见 `references/stage1-markdown-conversion.md`，阶段 2 见 `stage2-*.md`。

### 前置依赖

| 依赖 | 用途 |
|---|---|
| `mineru-textbook-to-md` | 阶段 1：PDF → Markdown（配套工具），需 `MINERU_OFFICIAL_API_TOKEN` |
| Python 3.10+ | 运行转换脚本 |
| TeX Live（`xelatex`） | 阶段 2：编译（实测 `fontset=windows` 可用） |
| `pandoc` 3.x | Markdown → LaTeX 初转 |

> **安全与授权**：上传 PDF 到 MinerU 前必须确认用户已授权；产出仅限个人学习使用。Token 只从环境变量读取，禁止打印或落盘。

## 关键经验（均由真实教材项目验证）

- **定理族共享编号序列 ≠ 共享计数器**：cleveref 按 label 绑定的**计数器名**判定类型，直接共享计数器会让 definition/lemma/proposition/corollary 的 `\cref` 一律渲染成「定理 X」且 `\crefname` 静默失效（不报错）。须用 `aliascnt` 为各环境建独立计数器名。
- **零编译错误 ≠ 结构正确**：`main.tex` 漏写 `\chapter{}` 会让全书退化到「第0章」、编号变 `0.x`，且不产生任何报警。验收必须查目录与编号。
- **aux 产物损坏**会引发上百条连锁假错误（`\@newl@bel` / `@@BOOKMARK` / 无效字符）——先清 `build/` 重编译，勿逐条排查源码。
- **前置页空白页**：book 类默认 `openright` 强制右页起排，会在标题页与目录间插入空白页 → 用 `openany`。
- **封面多余文字**：`\bookinfo{书名}{作者}` 第二参数是作者名，只要书名时留空。
- **收窄边距后的溢出分级**：`≤ 4pt` 可忽略；超过页边距宽度（约 62pt = 2.2cm）会被 PDF 裁切，必须定位修复；全局 `\emergencystretch` 可消除大部分。
- **编译日志误报**：`not found` 可能来自 `pdftexcmds` 信息行、`rerun` 可能匹配包名 `rerunfilecheck`；但结构变更后的官方 `Rerun to get` 提示为真。
- **页面核查用文本提取**：视觉/OCR 分批分析可能自相矛盾，判断某页是否空白应提取该页文本。

## 已知限制

- 扫描图像型 PDF 的公式存在少量 OCR 误差，须对照原书校正；个别长公式可能结构损坏，需人工确认。
- 引用句排除正则按前缀词排除时可能**误杀**以这些词开头的真定理头（如「可」「从」），须与 `missing_refs` 清单逐条交叉核对。
- 阶段 1 依赖 MinerU 云端服务，受网络与服务状态影响（服务端临时故障表现为 `please try again later`）。
- 编译产物中的排版类告警（`Overfull` / `Underfull` / `Missing character` / 字体替换）通常无法归零，须按量级分级登记而非追求「0 警告」。

## 配套项目

- **[mineru-textbook-to-md](../mineru-textbook-to-md)** —— 阶段 1 的 PDF → Markdown 工具（本 Skill 的上游依赖）。
- **[xsls-exam-skill](../xsls-exam-skill)** —— 同目录下的试卷 LaTeX 排版 Skill（结构范例）。

## 许可

个人学习与研究用途。