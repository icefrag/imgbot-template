# -*- coding: utf-8 -*-
"""★ auto_farm 任务: 类传奇自动打怪(基于脚手架 window 端二开的示范)。

循环: 找红怪(色块) → 点击选中(角色自动攻击) → 等击杀 → 捡金币 → 重复。
全部走 ctx.ops 色块接口(find_color), 无模板依赖 —— 游戏色值见
test/legend_game.py 头注释(#CC3333 怪 / #FFD700 金币)。
"""
from __future__ import annotations

import time

MON_COLOR = "CC3333"       # 怪物红(见 legend_game.py 色值约定)
COIN_COLOR = "FFD700"      # 金币黄
MON_TOL = 40               # 怪体色偏差(红圆抗锯齿边)
FIELD_BOTTOM = 570         # 场景区下界(排除底部状态栏, 那里有同色文字)


def main_task(ctx):
    kills = 0
    while not ctx.stop.is_set():
        if ctx.cfg.max_kills and kills >= ctx.cfg.max_kills:
            ctx.log(f"达成目标击杀 {kills}, 任务完成")
            return
        hit = ctx.ops.find_color(MON_COLOR, tol=MON_TOL,
                                 region=(0, 0, 2000, FIELD_BOTTOM))
        if not hit:
            ctx.log("场上无怪, 等刷新…")
            if ctx.stop.wait(1.5):
                return
            continue
        x, y = hit[0]
        ctx.log(f"锁定怪 ({x},{y}) → 点击")
        ctx.dm.MoveTo(x, y)
        ctx.dm.LeftClick()
        if _wait_kill(ctx, x, y):
            kills += 1
            ctx.log(f"击杀 ×{kills} → 捡金币")
            _pick_coins(ctx)
        else:
            ctx.log("击杀超时, 换目标")
        ctx.stop.wait(0.3)


def _wait_kill(ctx, x: int, y: int) -> bool:
    """等该位置红圆消失(怪死); 攻击伤害随等级, 超时=没选中/太肉。"""
    deadline = time.monotonic() + ctx.cfg.attack_wait
    while time.monotonic() < deadline:
        if ctx.stop.is_set():
            return False
        hits = ctx.ops.find_color(MON_COLOR, tol=MON_TOL,
                                  region=(x - 45, y - 70, x + 45, y + 70))
        if not hits:
            return True
        ctx.stop.wait(0.5)
    return False


def _pick_coins(ctx):
    deadline = time.monotonic() + ctx.cfg.coin_timeout
    while time.monotonic() < deadline:
        hits = ctx.ops.find_color(COIN_COLOR,
                                  region=(0, 0, 2000, FIELD_BOTTOM))
        if hits:
            x, y = hits[0]
            ctx.log(f"金币 ({x},{y}) → 拾取")
            ctx.dm.MoveTo(x, y)
            ctx.dm.LeftClick()
        ctx.stop.wait(0.8)
