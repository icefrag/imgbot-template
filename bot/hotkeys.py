# -*- coding: utf-8 -*-
"""热键收编: GetAsyncKeyState 轮询(50ms), 悬停目标窗口按 F9 = 拾取并回调。

不用 RegisterHotKey(注册冲突要处理, 轮询失败模式为零)。
"""
from __future__ import annotations

import ctypes
import threading

u32 = ctypes.windll.user32


class HotkeyListener:
    """后台线程轮询热键; 触发时调 on_hotkey()(在热键线程, UI 回调自行 marshal)。"""

    def __init__(self, vk: int, on_hotkey, poll_s: float = 0.05):
        self.vk = vk
        self.on_hotkey = on_hotkey
        self.poll_s = poll_s
        self._stop = threading.Event()
        self._down = False                       # 边沿检测: 按下沿才触发一次
        self.thread: threading.Thread | None = None

    def start(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self._stop.set()

    @property
    def listening(self) -> bool:
        return not self._stop.is_set()

    def _loop(self):
        while not self._stop.is_set():
            down = bool(u32.GetAsyncKeyState(self.vk) & 0x8000)
            if down and not self._down:
                try:
                    self.on_hotkey()
                except Exception:
                    pass                          # 回调炸不能带死监听线程
            self._down = down
            self._stop.wait(self.poll_s)
