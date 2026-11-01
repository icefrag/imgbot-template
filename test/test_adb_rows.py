# -*- coding: utf-8 -*-
"""adb 设备入表逻辑离线自检: 白名单过滤/保序/行标题拼装/端口与品牌识别。
跑法: uv run test/test_adb_rows.py
"""
from icefrag.backends import (_adb_port, _brand_from_owners,
                              adb_label, adb_rows)


def main() -> int:
    assert adb_rows(["emu-1", "emu-2"], []) == ["emu-1", "emu-2"]   # 空=全收
    assert adb_rows(["emu-1", "emu-2"], ["emu-2"]) == ["emu-2"]     # 白名单交集
    assert adb_rows(["emu-1"], ["emu-2", "emu-1", "x"]) == ["emu-1"]  # 保 preset 序, 掉线剔除
    assert adb_rows([], ["emu-1"]) == []                            # 无设备空表
    assert adb_label("MuMu12", "emulator-5554") == "MuMu12 · 5554"
    assert adb_label("LDPlayer", "127.0.0.1:7555") == "LDPlayer · 7555"
    assert adb_label("Pixel_5", "PDYTX10FKN") == "Pixel_5 · PDYTX10FKN"  # USB 串原样
    assert adb_label("", "emulator-5554") == "emulator-5554"        # 型号拿不到退 serial
    assert _adb_port("emulator-5554") == 5555      # 控制台端口+1=adb 端口
    assert _adb_port("127.0.0.1:7555") == 7555
    assert _adb_port("PDYTX10FKN") == 0            # USB 真机无本地端口
    # 品牌识别: 直命中 / VBox 底座看前端 / 双前端不确定 / 真机空
    assert _brand_from_owners({"mumuplayer.exe"}, ["MuMu模拟器"]) == "MuMu模拟器"
    assert _brand_from_owners({"vboxnetnat.exe"}, ["雷电模拟器"]) == "雷电模拟器"
    assert _brand_from_owners({"vboxnetnat.exe"}, ["MuMu模拟器", "雷电模拟器"]) == ""
    assert _brand_from_owners({"chrome.exe"}, []) == ""
    print("adb_rows/adb_label/_adb_port/_brand_from_owners: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
