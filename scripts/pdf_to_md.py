"""阶段 1 入口：PDF -> Markdown（MinerU 云端 API + 本地书签语义分块）。

自带完整实现（scripts/mineru_textbook_to_md/），不依赖任何外部 skill，
可在任意工作目录下运行。

用法：
    python scripts/pdf_to_md.py --pdf <pdf> --base-name <书名> --output <工作根>
    python scripts/pdf_to_md.py --help
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把 scripts/ 目录并入 sys.path，使 vendored 包可直接导入
SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from mineru_textbook_to_md.cli import run  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run())
