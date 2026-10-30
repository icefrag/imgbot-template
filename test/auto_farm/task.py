# -*- coding: utf-8 -*-
"""★ auto_farm 任务: 类传奇自动打怪(基于脚手架 window 端二开的示范)。

循环: 多点找色锁怪 → 点击选中(角色自动攻击) → 等击杀 → 捡金币 → 重复。
找怪/找金币用 find_multi_color(大漠 FindMultiColor 对应物): 怪身取 4 点
阵全中才算 —— 同色文字天然不全中, 不用再裁状态栏区域。游戏色值见
test/legend_game.py 头注释(怪 #CC3333 半径16 / 金币 #FFD700 半径8)。
"""
import time

from bot.dsl import *  # noqa: F401,F403

RED = (51, 51, 204)      # #CC3333 的 BGR
GOLD = (0, 215, 255)     # #FFD700 的 BGR
MON_PTS = [Pt(0, 0, RED, 40), Pt(8, 0, RED, 40),
           Pt(0, 8, RED, 40), Pt(8, 8, RED, 40)]     # 半径16圆内的4点阵
COIN_PTS = [Pt(0, 0, GOLD, 40), Pt(4, 0, GOLD, 40),
            Pt(0, 4, GOLD, 40), Pt(4, 4, GOLD, 40)]  # 半径8圆内的4点阵
MON_GONE = "CC3333-282828"                           # 等消失用(0x28=tol40)
GAME_RECT = (0, 0, 900, 640)                         # 游戏客户区


def main_task(ctx):
    kills = 0
    while not ctx.stop.is_set():
        if ctx.cfg.max_kills and kills >= ctx.cfg.max_kills:
            log(f"达成目标击杀 {kills}, 任务完成")
            return
        hit = find_multi_color(GAME_RECT, MON_PTS)
        if not hit:
            log("场上无怪, 等刷新…")
            sleep(1500)
            continue
        x, y = hit
        log(f"锁定怪 ({x},{y}) → 点击")
        click(x, y)
        if wait_color_gone(MON_GONE,
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
        hit = find_multi_color(GAME_RECT, COIN_PTS)
        if hit:
            log(f"金币 ({hit[0]},{hit[1]}) → 拾取")
            click(*hit)
        sleep(600)
