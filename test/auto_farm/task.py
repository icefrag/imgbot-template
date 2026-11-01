# -*- coding: utf-8 -*-
"""★ auto_farm 任务: 类传奇自动打怪(基于脚手架 window 端二开的示范)。

循环: 多点找色锁怪 → 点击选中(角色自动攻击) → 等击杀 → 捡金币 → 重复。
找怪/找金币用大漠直通 FindMultiColor(仅 window 端; adb 端示范见
test/auto_farm_adb): 怪身取 4 点阵全中才算 —— 同色文字天然不全中,
不用再裁状态栏区域。游戏色值见 test/legend_game.py 头注释
(怪 #CC3333 半径16 / 金币 #FFD700 半径8)。
"""
import time

from icefrag.dsl import *  # noqa: F401,F403

MON = "CC3333-282828"    # 怪身红(偏差 -28=tol40, 同旧点阵口径)
MON_OFF = "8|0|CC3333-282828,0|8|CC3333-282828,8|8|CC3333-282828"   # 4 点阵
COIN = "FFD700-282828"
COIN_OFF = "4|0|FFD700-282828,0|4|FFD700-282828,4|4|FFD700-282828"
GAME_RECT = (0, 0, 900, 640)                         # 游戏客户区


def main_task(ctx):
    kills = 0
    while not ctx.stop.is_set():
        if ctx.cfg.max_kills and kills >= ctx.cfg.max_kills:
            log(f"达成目标击杀 {kills}, 任务完成")
            return
        x, y = FindMultiColor(*GAME_RECT, MON, MON_OFF)
        if x < 0:
            log("场上无怪, 等刷新…")
            sleep(1500)
            continue
        log(f"锁定怪 ({x},{y}) → 点击")
        click(x, y)
        if wait_color_gone(MON,
                           region=(x - 45, y - 70, x + 45, y + 70),
                           timeout=int(ctx.cfg.attack_wait * 1000)):
            kills += 1
            log(f"击杀 ×{kills} → 捡金币")
            _pick_coins(ctx)
        else:
            log("击杀超时, 换目标")
        sleep(300)


def _pick_coins(ctx):
    deadline = time.monotonic() + ctx.cfg.coin_timeout
    while time.monotonic() < deadline:
        if ctx.stop.is_set():
            return
        x, y = FindMultiColor(*GAME_RECT, COIN, COIN_OFF)
        if x >= 0:
            log(f"金币 ({x},{y}) → 拾取")
            click(x, y)
        sleep(600)
