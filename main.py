# -*- coding: utf-8 -*-
"""单开入口: 裸跑一个目标, Ctrl+C 全局停止。多开用 console.py。

用法: uv run main.py
"""
import queue
import sys
import threading

import time

from bot import backends, settings
from bot.hotkeys import HotkeyListener
from bot.store import load as biz_load
from bot.worker import Worker


def main() -> int:
    gcfg = settings.load()
    if gcfg.backend == "adb":
        serials = gcfg.adb_serials or _adb_discover()
        if not serials:
            print("adb 端: 没发现模拟器(设备开着吗/adb 在 PATH 吗)")
            return 1
        ident = serials[0]
    else:
        print(f"把鼠标放到目标窗口上, {gcfg.hotkey_vk - 0x6F}s 内按 F9 收编...")
        hwnd = None
        got = threading.Event()

        def grab():
            nonlocal hwnd
            hwnd = backends.pick_window(gcfg.pick_mode, gcfg.window_class)
            got.set()

        hk = HotkeyListener(gcfg.hotkey_vk, grab)
        hk.start()
        got.wait(30)
        hk.stop()
        if not hwnd:
            print("30 秒内没等到热键收编")
            return 1
        ident = str(hwnd)

    logq: queue.Queue = queue.Queue()
    biz = biz_load(_business())
    w = Worker(ident, gcfg.backend, gcfg, biz, logq)
    w.start()
    try:
        while w.alive or not logq.empty():
            try:
                _ident, text, level = logq.get(timeout=0.5)
                print(f"[{level}] {text}")
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        print("\nCtrl+C → 停止...")
        w.stop()
    return 0


def _business():
    import business
    return business.BusinessConfig


def _adb_discover():
    from imgbot.adb import list_devices
    return [s for s, _name in list_devices()]


if __name__ == "__main__":
    sys.exit(main())
