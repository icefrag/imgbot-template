# -*- coding: utf-8 -*-
"""后端抽象: adb(模拟器)与 window(PC 窗口)两端——发现、绑定、ctx 组装。

方言差异全部隔离在本模块; worker/console 对后端无感, 只认 Worker 协议。
任务方言(imgbot AGENTS): adb=actions.*(魔神语法) / window=ops.*(大漠语法)。
"""
from __future__ import annotations

import ctypes
import time

from . import ROOT

SHOTS = ROOT / "logs" / "shots"


# ==================== 拾取(window 端热键收编) ====================
def pick_window(pick_mode: str, class_filter: str = "") -> int | None:
    """按 pick_mode 拾取目标窗口句柄; 无效/被过滤返回 None。

    hover: 鼠标当前所在的顶层窗口(用户指哪打哪);
    focus: 前台活动窗口中具有输入焦点的子窗口(模拟器渲染窗场景)。
           GetGUIThreadInfo 跨线程常返回假零(imgbot AGENTS 焦点坑), 故
           focus 模式 = 光标所在窗口, 子窗焦点回退用 AttachThreadInput 权威查。
    """
    import ctypes.wintypes as wt
    u32 = ctypes.windll.user32
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
    if class_filter:
        buf = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, buf, 256)
        if buf.value != class_filter:
            return None
    return hwnd


def window_title(hwnd: int) -> str:
    u32 = ctypes.windll.user32
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value or f"hwnd={hwnd}"


# ==================== 绑定与 ctx 组装 ====================
class Ctx:
    """任务代码的全部世界(见 spec.md ctx 字段表)。字段按端装配。"""

    def __init__(self, backend: str, name: str, cfg, log, stop,
                 dm=None, ops=None, device=None):
        self.backend = backend
        self.name = name                          # 显示名(表格行/日志前缀)
        self.cfg = cfg                            # 业务配置对象
        self.log = log
        self.stop = stop
        self.dm = dm
        self.ops = ops
        self.device = device

    def shot(self, tag: str = "") -> Path | None:
        """失败留痕: window 端存当前帧, adb 端存设备截图。"""
        SHOTS.mkdir(parents=True, exist_ok=True)
        p = SHOTS / f"{time.strftime('%m%d_%H%M%S')}_{self.name}_{tag or 'shot'}.png"
        try:
            if self.backend == "window":
                import cv2
                cv2.imwrite(str(p), self.dm._screen())
            else:
                self.device.screenshot().save_png(str(p))
            return p
        except Exception:
            return None


def bind_window_backend(hwnd: int, scaffold, business_cfg, log, stop) -> Ctx:
    """window 端绑定: DmSoft → 通道 → 模板目录 → Ops。"""
    from imgbot.dmsoft import DmSoft
    from imgbot.ops import Ops
    dm = DmSoft()
    assert dm.BindWindow(hwnd, scaffold.display, scaffold.mouse,
                         scaffold.keypad, 0) == 1, "BindWindow 失败"
    dm.SetPath(str(ROOT / "templates"))
    ops = Ops(dm)
    return Ctx("window", window_title(hwnd), business_cfg, log, stop,
               dm=dm, ops=ops)


def bind_adb_backend(serial: str, scaffold, business_cfg, log, stop) -> Ctx:
    """adb 端绑定: AdbTarget(魔神线, 天然后台)。"""
    from imgbot.target import AdbTarget
    target = AdbTarget(serial)
    return Ctx("adb", serial, business_cfg, log, stop, device=target)


def unbind(ctx: Ctx) -> None:
    """收口(永远执行, 崩溃也执行)。"""
    try:
        if ctx.backend == "window" and ctx.dm is not None:
            ctx.dm.UnBindWindow()
        elif ctx.device is not None:
            ctx.device.close()
    except Exception:
        pass
