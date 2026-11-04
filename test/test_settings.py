# -*- coding: utf-8 -*-
"""settings.save/load 契约回归: 冻结态也必须真落盘 exe 旁 scaffold.toml。

v0.3.x 旧版 save() 在 sys.frozen 时静默 no-op("编译期定死"), exe 用户改键重开即丢
且无任何提示(2026-11-04 左列宽度比例 0.6 案定案放开, 对齐「scaffold.toml 摆 exe 旁
用户可编辑」契约)。跑法: uv run test/test_settings.py
"""
import tempfile
from pathlib import Path
from unittest import mock

import sys

from icefrag import settings


def main():
    # ① 冻结契约: save 不看 sys.frozen——若有人把冻结早退加回来, 这条必须炸
    with tempfile.TemporaryDirectory() as td:
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(settings, "PATH", Path(td) / "scaffold.toml"):
            settings.save(settings.ScaffoldConfig(backend="adb", left_ratio=0.6))
            cfg = settings.load()
            assert cfg.backend == "adb" and cfg.left_ratio == 0.6, cfg
    # ② load 基础面: 未知键忽略(向前兼容), 损坏备份后回默认, 缺文件回默认
    with tempfile.TemporaryDirectory() as td:
        with mock.patch.object(settings, "PATH", Path(td) / "scaffold.toml"):
            settings.PATH.write_text("left_ratio = 0.7\nunknown_key = 1\n", encoding="utf-8")
            assert settings.load().left_ratio == 0.7
            settings.PATH.write_text("这不是 TOML [[[", encoding="utf-8")
            assert settings.load().left_ratio == settings.ScaffoldConfig().left_ratio
            settings.PATH.unlink(missing_ok=True)  # backup_broken 可能已把坏文件挪走
            assert settings.load().left_ratio == settings.ScaffoldConfig().left_ratio
    print("test_settings ok")


if __name__ == "__main__":
    main()
