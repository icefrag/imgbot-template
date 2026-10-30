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

from bot import backends, settings
from bot.store import load as biz_load
from bot.worker import Worker

import business


def main() -> int:
    # -- 配置层 --
    gcfg = settings.load()
    gcfg.display = gcfg.mouse = gcfg.keypad = "normal"
    biz = biz_load(business.BusinessConfig)
    biz.target_text = f"sc{int(time.time()) % 10000}"
    print(f"[1] 配置层 OK: backend={gcfg.backend} biz={biz.target_text!r}")

    # -- 目标 --
    p = subprocess.Popen(["notepad.exe"])
    time.sleep(1.2)
    hwnd = _find_notepad()
    assert hwnd, "没找到记事本"
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
        if "一轮完成" in text:
            got_round = True
            break
    print(f"[3] 绑定={'OK' if got_bind else 'FAIL'} 一轮任务={'OK' if got_round else 'FAIL'}")

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

    ok = got_bind and got_round and ok_text and w.state in ("已停止", "未运行")
    print("自检:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _find_notepad() -> int:
    import ctypes
    u32 = ctypes.windll.user32
    u32.FindWindowW.restype = ctypes.c_void_p
    return int(u32.FindWindowW("Notepad", None) or 0)


if __name__ == "__main__":
    sys.exit(main())
