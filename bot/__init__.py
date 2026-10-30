# -*- coding: utf-8 -*-
"""imgbot-template 框架包(拷走不改): worker/backends/hotkeys/settings/store/console_ui。

ROOT = 项目根(scaffold.toml/templates/logs 所在)。默认 = 本包的上级目录;
子项目(如 test/auto_farm)复用框架包时, 在 import bot 之前设环境变量
IMGBOT_TEMPLATE_ROOT 指向自己的项目根即可。
"""
import os
from pathlib import Path

ROOT = Path(os.environ.get(
    "IMGBOT_TEMPLATE_ROOT",
    Path(__file__).resolve().parents[1]))
