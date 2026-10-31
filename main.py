# -*- coding: utf-8 -*-
"""单开入口(薄): 裸跑一个目标, Ctrl+C 全局停止。多开用 console.py。

用法: uv run main.py
"""
import os
from pathlib import Path

os.environ.setdefault("IMGBOT_TEMPLATE_ROOT", str(Path(__file__).resolve().parent))

import business  # noqa: E402
from icefrag.bootstrap import run_single  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_single(business))
