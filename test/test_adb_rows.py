# -*- coding: utf-8 -*-
"""adb 设备入表逻辑离线自检: 白名单过滤/保序/空配置全收。
跑法: uv run test/test_adb_rows.py
"""
from icefrag.backends import adb_rows


def main() -> int:
    assert adb_rows(["emu-1", "emu-2"], []) == ["emu-1", "emu-2"]   # 空=全收
    assert adb_rows(["emu-1", "emu-2"], ["emu-2"]) == ["emu-2"]     # 白名单交集
    assert adb_rows(["emu-1"], ["emu-2", "emu-1", "x"]) == ["emu-1"]  # 保 preset 序, 掉线剔除
    assert adb_rows([], ["emu-1"]) == []                            # 无设备空表
    print("adb_rows: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
