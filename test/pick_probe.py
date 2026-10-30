# -*- coding: utf-8 -*-
"""窗口拾取探测: 实时显示 hover/focus 两种模式拾到的窗口(句柄/类名/标题/矩形)。

用于二开前确认 pick_mode 该选哪个、window_class 过滤串该填什么。
用法: uv run python test/pick_probe.py [hover|focus]   (Ctrl+C 退出)
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

u32 = ctypes.windll.user32


def probe(pick_mode: str) -> tuple[int, str, str] | None:
    pt = wt.POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    hwnd = u32.WindowFromPoint(pt)
    if not hwnd:
        return None
    if pick_mode == "focus":
        k32 = ctypes.windll.kernel32
        ours = k32.GetCurrentThreadId()
        tgt = u32.GetWindowThreadProcessId(hwnd, None)
        attached = u32.AttachThreadInput(ours, tgt, True)
        try:
            child = u32.GetFocus()
        finally:
            if attached:
                u32.AttachThreadInput(ours, tgt, False)
        if child and u32.IsWindow(child):
            hwnd = child
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    cls = buf.value
    n = u32.GetWindowTextLengthW(hwnd)
    tbuf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, tbuf, n + 1)
    return hwnd, cls, tbuf.value


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "hover"
    print(f"拾取模式: {mode}(把鼠标放到目标窗口上, Ctrl+C 退出)")
    last = None
    try:
        while True:
            r = probe(mode)
            if r != last:
                if r:
                    hwnd, cls, title = r
                    rect = wt.RECT()
                    u32.GetWindowRect(hwnd, ctypes.byref(rect))
                    print(f"  hwnd=0x{hwnd:X} class={cls!r} title={title!r} "
                          f"rect=({rect.left},{rect.top},{rect.right},{rect.bottom})")
                else:
                    print("  (无)")
                last = r
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n退出")


if __name__ == "__main__":
    main()
