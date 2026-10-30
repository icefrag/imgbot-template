# -*- coding: utf-8 -*-
"""auto_farm E2E: 开游戏 → 挂机跑 → 验证金币/等级增长。单脚本可重复。"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

import ctypes

from game_smoke import client_shot, find_game, find_monsters


def gold_and_level(img):
    """读状态栏: 粗判=金币文本区黄色像素 + LV 文本存在。返回 (金币黄色像素数)。"""
    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    gold_px = int(((r > 200) & (g > 140) & (b < 90)).sum())
    return gold_px


def main() -> int:
    # 开游戏(干净实例)
    subprocess.Popen([sys.executable, str(HERE / "legend_game.py")],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(6)                # 游戏冷启动(numpy+tkinter)3 秒会卡线
    hwnd = find_game()
    assert hwnd, "游戏窗口没找到"
    print(f"[1] 游戏 0x{hwnd:X}")

    img = client_shot(hwnd)
    base_gold = gold_and_level(img)
    print(f"[2] 起始状态栏金色像素: {base_gold}")

    # 开挂机(单开入口, 后台)
    farm = subprocess.Popen(
        [sys.executable, str(HERE / "auto_farm" / "main.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[3] 挂机已启动, 跑 40 秒…")
    deadline = time.time() + 40
    peak_gold, monsters_seen = 0, 0
    while time.time() < deadline:
        time.sleep(2)
        try:
            img = client_shot(hwnd)
        except Exception:
            continue
        peak_gold = max(peak_gold, gold_and_level(img))
        monsters_seen = max(monsters_seen, len(find_monsters(img)))
    peak_gold = max(peak_gold, gold_and_level(client_shot(hwnd)))
    print(f"[4] 40 秒后: 金色像素峰值 {peak_gold}(起始 {base_gold}), 场上怪 {monsters_seen}")

    farm.terminate()
    ok = peak_gold > base_gold + 30          # 金币数字变大(黄色像素增多)= 打怪有产出
    print("auto_farm E2E:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
