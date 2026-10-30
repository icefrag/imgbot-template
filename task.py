# -*- coding: utf-8 -*-
"""★ 开发者写: 任务总入口 + 子任务。绑定/解绑/异常重开/停止信号全是框架的, 这里只写过程。

顶层命令来自 `from bot.dsl import *`(速查见 bot/dsl.py 模块头):
  click(x, y) / key("ctrl+s") / sleep(500) / find_color / wait_pic / log ...
  凡时间皆毫秒; 找不到返回 None/False 不抛; ctx.dm/ctx.ops 是逃生舱。

本示例(window 端): 向记事本打字 → 读回校验 → 截图留痕, 跑 cfg.max_rounds 轮。
"""
from __future__ import annotations

import ctypes

from bot.dsl import *  # 顶层命令: click/key/sleep/find_color/wait_pic/... 速查见 bot/dsl.py


def main_task(ctx):
    """总入口: 一个函数 = 一轮任务。抛异常 = 本轮失败(框架自动重开)。"""
    for i in range(1, ctx.cfg.max_rounds + 1):
        if ctx.stop.is_set():
            return
        log(f"第 {i}/{ctx.cfg.max_rounds} 轮")
        _clear(ctx)
        _type_text(ctx)
        _wait_and_prove(ctx, i)
        log(f"第 {i} 轮完成", "info")
        sleep(300)


def _clear(ctx):
    """清场: WM_SETTEXT 打到 Edit 子控件(主窗收到只是改标题)。"""
    hwnd = ctx.dm.GetBindWindow()
    edit = ctx.dm.FindWindowEx(hwnd, "Edit")
    ctypes.windll.user32.SendMessageW(edit or hwnd, 0x000C, 0, "")


def _type_text(ctx):
    """打字走 ctx.dm.SendString(窗口消息打字, 无对应 DSL 动词)。"""
    ctx.dm.SendString(ctx.dm.GetBindWindow(), ctx.cfg.target_text)


def _wait_and_prove(ctx, i: int):
    text = read_text()
    if ctx.cfg.target_text.lower() not in text.lower():
        raise RuntimeError(f"打字未见回显: {ctx.cfg.target_text!r} (读到 {text!r})")
    log("回显命中, 留痕")
    shot(f"round{i}_ok")
