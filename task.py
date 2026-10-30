# -*- coding: utf-8 -*-
"""★ 开发者写: 任务总入口 + 子任务。绑定/解绑/异常重开/停止信号全是框架的, 这里只写过程。

window 端方言: ctx.ops(find_tap/wait_pic/wait_text/...) + ctx.dm(MoveTo/KeyPress/...)
adb 端方言:   ctx.device + actions.wait_tap(ctx.device, ...) + vision.find(...)
本示例(window 端): 向记事本打字 → 读回校验 → 截图留痕, 跑 cfg.max_rounds 轮。
"""
from __future__ import annotations


def main_task(ctx):
    """总入口: 一个函数 = 一轮任务。抛异常 = 本轮失败(框架自动重开)。"""
    for i in range(1, ctx.cfg.max_rounds + 1):
        if ctx.stop.is_set():
            return
        ctx.log(f"第 {i}/{ctx.cfg.max_rounds} 轮")
        _clear(ctx)
        _type_text(ctx)
        _wait_and_prove(ctx)
        ctx.log(f"第 {i} 轮完成", "info")


def _clear(ctx):
    """清场: WM_SETTEXT 打到 Edit 子控件(主窗收到只是改标题)。顺带示范
    GetBindWindow + FindWindowEx 的窗口 API 用法。"""
    import ctypes
    hwnd = ctx.dm.GetBindWindow()
    edit = ctx.dm.FindWindowEx(hwnd, "Edit")
    ctypes.windll.user32.SendMessageW(edit or hwnd, 0x000C, 0, "")


def _type_text(ctx):
    """子任务拆分 = 普通函数, 一律吃 ctx。"""
    ctx.dm.SendString(ctx.dm.GetBindWindow(), ctx.cfg.target_text)


def _wait_and_prove(ctx):
    text = ctx.ops.read_text()
    if ctx.cfg.target_text.lower() not in text.lower():
        raise RuntimeError(f"打字未见回显: {ctx.cfg.target_text!r} (读到 {text!r})")
    ctx.log("回显命中, 留痕")
    ctx.shot("round_ok")
