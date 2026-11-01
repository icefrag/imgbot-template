# -*- coding: utf-8 -*-
"""★ auto_farm_adb 任务: 模拟器端自动打怪示范(adb 模式, 零素材零游戏依赖)。

"怪" = 通知栏阴影 —— 任何安卓设备都有、且生灭可确定的靶子:
  上场  ctx.device.shell("cmd","statusbar","expand-notifications")(等动画收尾)
  选怪  click(tap_x, tap_y) 点面板空白处(点位不合适在 business.py 改;
        点到通知/磁贴属目标自身行为, 无害)
  击杀  shell(...,"collapse") 收起 → wait_color_gone 验尸
怪色用**差异采样**: 展开前后各截一帧, 顶条里变化最大的像素即怪色 ——
按构造与背景不同色(治"收起后背景恰好同色"的假阴性), 顶条整体没变化
= 面板没起来(治动画竞态与不支持 cmd statusbar 的机器)。
全程真链路 = 手册四章两张表: dsl 命令(wait_color_gone/click/sleep/log/
shot/stopped) + ctx.device 方言(screenshot/shell)。
PC 端对应示范见 test/auto_farm(大漠直通 FindMultiColor 锁怪)。
"""
import numpy as np

from icefrag.dsl import *  # noqa: F401,F403


def main_task(ctx):
    dev = ctx.device
    h, w = dev.screenshot().shape[:2]        # 设备分辨率(首帧)
    tx = ctx.cfg.tap_x or w // 2
    ty = ctx.cfg.tap_y or h // 2
    strip_h = max(60, h // 9)                # 顶条: 展开面板必覆盖
    log(f"设备 {w}x{h}, 点击点位 ({tx},{ty}), 采样顶条 0~{strip_h}px")
    kills = 0
    while not stopped():
        if ctx.cfg.max_kills and kills >= ctx.cfg.max_kills:
            log(f"达成目标击杀 {kills}, 任务完成")
            return
        marker = _find_monster(dev, strip_h)
        if marker is None:
            log("面板没起来(cmd statusbar 不支持?)/顶条无变化, 1.5 秒后再试")
            sleep(1500)
            continue
        (sx, sy), color = marker
        log(f"锁怪 #{color} @({sx},{sy}) → 点击 ({tx},{ty})")
        click(tx, ty)
        dev.shell("cmd", "statusbar", "collapse")               # 出招
        if wait_color_gone(color, region=(sx - 30, sy - 20, sx + 30, sy + 20),
                           timeout=int(ctx.cfg.attack_wait * 1000)):
            kills += 1
            log(f"击杀 ×{kills}")
        else:
            log("击杀超时(面板没收起/被停止叫醒)", "warn")
            shot("kill_fail")
        sleep(400)


def _find_monster(dev, strip_h):
    """展开通知栏, 返回顶条内前后帧差异最大的像素当怪标记。

    返回 ((x, y), "RRGGBB") 或 None(顶条整体没变 = 面板没起来)。
    """
    before = dev.screenshot()
    dev.shell("cmd", "statusbar", "expand-notifications")
    sleep(800)                               # 等展开动画收尾(治竞态)
    after = dev.screenshot()
    d = np.abs(after[:strip_h].astype(int) - before[:strip_h].astype(int)
               ).sum(axis=2)
    sy, sx = np.unravel_index(d.argmax(), d.shape)
    if d.max() < 60:                         # 全条无实质变化
        return None
    b, g, r = (int(v) for v in after[sy, sx])
    return (int(sx), int(sy)), f"{r:02X}{g:02X}{b:02X}"
