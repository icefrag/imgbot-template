# -*- coding: utf-8 -*-
"""薄入口的运行时: 单开 run_single / 中控台 run_console。

薄项目入口只做三件事: 设 IMGBOT_TEMPLATE_ROOT → import business → 调本模块。
"""
from __future__ import annotations

import queue
import threading

from . import backends, settings
from .hotkeys import HotkeyListener
from .store import load as biz_load
from .worker import Worker


def run_single(business) -> int:
    """单开: 裸跑一个目标(热键收编/adb 发现), Ctrl+C 停。"""
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
    biz = biz_load(business.BusinessConfig)
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


def run_console(business) -> None:
    from .console_ui import Console
    Console(business).run()


def _adb_discover():
    from imgbot.adb import list_devices
    return [s for s, _name in list_devices()]
