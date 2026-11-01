# -*- coding: utf-8 -*-
"""唯一入口(薄): ttkbootstrap 中控台(热键收编/表格启停/日志面板/双 Tab 设置)。

用法: uv run console.py   (单开多开都是它: 收编几个目标就跑几个)
"""
import os
from pathlib import Path

os.environ.setdefault("IMGBOT_TEMPLATE_ROOT", str(Path(__file__).resolve().parent))

import business  # noqa: E402
from icefrag.console_ui import Console  # noqa: E402

if __name__ == "__main__":
    Console(business).run()
