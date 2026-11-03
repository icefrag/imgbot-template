# -*- coding: utf-8 -*-
"""icefrag 脚手架框架包(薄项目经 wheel 引用, 不拷源码): worker/backends/hotkeys/
settings/store/console_ui/dsl/build。

ROOT = 项目根(scaffold.toml/templates/logs 所在)。默认 = 本包的上级目录;
PyInstaller exe 里 = exe 所在目录(scaffold.toml/templates 摆 exe 旁, 用户可编辑;
冻结态忽略 IMGBOT_TEMPLATE_ROOT —— 子项目入口无条件设它会静默顶掉 exe 目录回退,
settings 全默认值, 2026-11-03 moshen2「exe 变 PC 端空壳」案);
子项目(如 test/auto_farm)复用框架时, 在 import icefrag 之前设环境变量
IMGBOT_TEMPLATE_ROOT 指向自己的项目根即可。
"""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent   # 冻结态恒 exe 目录, 见模块头注释
else:
    ROOT = Path(os.environ.get(
        "IMGBOT_TEMPLATE_ROOT", Path(__file__).resolve().parents[1]))
