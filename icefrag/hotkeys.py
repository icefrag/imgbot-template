# -*- coding: utf-8 -*-
"""热键收编: GetAsyncKeyState 轮询(50ms), 悬停目标窗口按 F9 = 拾取并回调。

不用 RegisterHotKey(注册冲突要处理, 轮询失败模式为零)。
"""
from __future__ import annotations

import ctypes
import threading

u32 = ctypes.windll.user32

# 经典启动热键表: scaffold.toml 字符串(hotkey = "f9")与设置弹窗下拉共用
HOTKEYS = {f"f{i}": 0x70 + (i - 1) for i in range(1, 13)}   # F1~F12
HOTKEYS.update({"pause": 0x13, "scrolllock": 0x91,          # 挂机两神器(游戏不占)
                "home": 0x24, "end": 0x23,
                "insert": 0x2D, "delete": 0x2E})


def hotkey_vk(name: str) -> int:
    """键名 → 虚拟键码; 未收录的名字抛 ValueError(可选项见 HOTKEYS)。"""
    try:
        return HOTKEYS[name.strip().lower()]
    except KeyError:
        raise ValueError(f"热键名未收录(可选 {list(HOTKEYS)}): {name!r}") from None


def hotkey_label(name: str) -> str:
    """键名 → 界面显示(F9 / Pause / ScrollLock...)。"""
    n = name.strip().lower()
    return {"scrolllock": "ScrollLock"}.get(
        n, n.upper() if n.startswith("f") else n.capitalize())


def hotkey_choices() -> list[str]:
    """设置弹窗下拉的显示项(HOTKEYS 顺序)。"""
    return [hotkey_label(k) for k in HOTKEYS]


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
