# -*- coding: utf-8 -*-
"""auto_farm 入口(单开): 在本目录运行, 框架包与配置指向各自目录。

用法: uv run python test/auto_farm/main.py   (在项目根执行亦可)
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE.parents[1]
os.environ["IMGBOT_TEMPLATE_ROOT"] = str(HERE)
sys.path.insert(0, str(SCAFFOLD))
sys.path.insert(0, str(HERE))

import business  # noqa: E402
from icefrag import settings  # noqa: E402
from icefrag.store import load as biz_load  # noqa: E402
from icefrag.worker import Worker  # noqa: E402


def main() -> int:
    gcfg = settings.load()
    gcfg.display = gcfg.mouse = gcfg.keypad = "normal"   # 游戏=前台单开
    hwnd = _find_game()
    if not hwnd:
        print("游戏窗口没找到(先跑 uv run python test/legend_game.py)")
        return 1
    print(f"游戏 hwnd={hwnd}, 3 秒后开始挂机(Ctrl+C 停止)")
    time.sleep(3)

    logq_queue = __import__("queue").Queue()
    biz = biz_load(business.BusinessConfig)
    w = Worker(str(hwnd), "window", gcfg, biz, logq_queue)
    w.start()
    try:
        while w.alive or not logq_queue.empty():
            try:
                _ident, text, level = logq_queue.get(timeout=0.5)
                print(f"[{level}] {text}")
            except Exception:
                pass
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n停止…")
        w.stop()
    print(f"结束: 击杀计数见上, state={w.state}")
    return 0


def _find_game() -> int:
    import ctypes
    u32 = ctypes.windll.user32
    u32.FindWindowW.restype = ctypes.c_void_p
    return int(u32.FindWindowW(None, "imgbot-legend") or 0)


if __name__ == "__main__":
    sys.exit(main())
