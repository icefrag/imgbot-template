# -*- coding: utf-8 -*-
"""auto_farm 中控台入口(多开同款): 复用脚手架 icefrag.console_ui, 项目目录指向本目录。"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE.parents[1]
os.environ["IMGBOT_TEMPLATE_ROOT"] = str(HERE)
sys.path.insert(0, str(SCAFFOLD))
sys.path.insert(0, str(HERE))

import business  # noqa: E402
from icefrag.console_ui import Console  # noqa: E402

if __name__ == "__main__":
    Console(business).run()
