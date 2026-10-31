# -*- coding: utf-8 -*-
"""脚手架非 GUI 全链自检: Worker 驱动记事本(绑定→任务→日志→收口)+配置持久化。

用法: uv run selfcheck.py   (需要 imgbot 仓先跑过 build? 不需要: normal 通道零注入)
"""
import queue
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from icefrag import backends, settings
from icefrag.store import load as biz_load
from icefrag.worker import Worker

import business


def main() -> int:
    # -- 配置层 --
    gcfg = settings.load()
    gcfg.display = "gdi"        # 后台截屏: 活桌面上跑自检, 遮挡不影响 OCR(踩过)
    gcfg.mouse = gcfg.keypad = "normal"
    biz = biz_load(business.BusinessConfig)
    biz.target_text = f"sc{int(time.time()) % 10000}"
    print(f"[1] 配置层 OK: backend={gcfg.backend} biz={biz.target_text!r}")

    # -- 目标 --
    p = subprocess.Popen(["notepad.exe"])
    time.sleep(1.2)
    hwnd = _find_notepad(p.pid)
    assert hwnd, "没找到记事本"
    import ctypes
    ctypes.windll.user32.SetForegroundWindow(hwnd)   # 提到前台: 活桌面遮挡会让截屏漏窗
    print(f"[2] 目标 hwnd=0x{hwnd:X}")

    # -- Worker 全链 --
    logq: queue.Queue = queue.Queue()
    w = Worker(str(hwnd), "window", gcfg, biz, logq)
    w.start()
    deadline = time.time() + 30
    got_bind = got_round = False
    while time.time() < deadline:
        try:
            _ident, text, level = logq.get(timeout=0.5)
        except queue.Empty:
            continue
        print(f"    [{level}] {text}")
        if "已绑定" in text:
            got_bind = True
        if "任务完成" in text:
            got_round = True
            break
    print(f"[3] 绑定={'OK' if got_bind else 'FAIL'} 任务完成={'OK' if got_round else 'FAIL'}")

    # -- 回显断言(任务真的打进记事本了) --
    import ctypes
    u32 = ctypes.windll.user32
    u32.FindWindowExW.restype = ctypes.c_void_p
    edit = int(u32.FindWindowExW(hwnd, None, "Edit", None) or hwnd)
    buf = ctypes.create_unicode_buffer(256)
    u32.SendMessageW(edit, 0x000D, 256, buf)
    ok_text = biz.target_text in buf.value
    print(f"[4] 记事本回显: {buf.value!r} → {'OK' if ok_text else 'FAIL'}")

    # -- 收口 --
    w.stop()
    print(f"[5] 停止: state={w.state!r}")
    p.terminate()

    ok = got_bind and got_round and ok_text and w.state in ("已完成", "已停止", "未运行")
    print("自检:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _find_notepad(pid: int) -> int:
    """枚举可见顶层窗口, 挑属于自拉进程 pid 的 —— 按类名找会捡到桌面上
    别的记事本(踩过: 桌面留着贴旧控制台输出的记事本, 测试被劫持)。"""
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    hits: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        proc_id = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and u32.IsWindowVisible(hwnd):
            hits.append(hwnd)
        return True

    u32.EnumWindows(_cb, 0)
    return hits[0] if hits else 0


if __name__ == "__main__":
    sys.exit(main())
