# -*- coding: utf-8 -*-
"""imgbot-legend: 本地类传奇小游戏(挂机脚手的靶场)。

玩法: 鼠标点怪物 → 角色自动攻击(伤害随等级) → 怪死掉落金币 → 点金币拾取
      → XP 满升级 → 新怪刷新(场上至多 3 只)。

图色约定(挂机脚本全靠这些固定色值, 改色值=同时改挂机脚本):
  - 怪物本体:   纯红圆 #CC3333, 半径 16
  - 怪物血条:   底黑 #111111, 血条绿 #22CC22(>50%) / 黄 #CCCC22(>25%) / 红 #CC2222
  - 金币掉落:   黄圆 #FFD700, 半径 8, 12 秒未拾取消失
  - 玩家:       蓝圆 #3377DD
  - 状态栏:     底部 60px, XP 条蓝 #3377FF, 底黑; 等级/金币大字白底黑框

运行: uv run python test/legend_game.py
窗口标题固定 "imgbot-legend"(挂机脚本按标题收编)。
"""
from __future__ import annotations

import random
import threading
import tkinter as tk

W, H = 900, 640
GROUND_TOP = 80          # 场景区上界(下面是状态栏)
STATUS_H = 60
MONSTER_R = 16
COIN_R = 8
COLOR_MON = "#CC3333"
COLOR_HP_FULL = "#22CC22"
COLOR_HP_MID = "#CCCC22"
COLOR_HP_LOW = "#CC2222"
COLOR_COIN = "#FFD700"
COLOR_PLAYER = "#3377DD"
COLOR_XP = "#3377FF"
BG = "#2b2b2b"
GRID = "#333333"


class Monster:
    _seq = 0

    def __init__(self, x: int, y: int, level: int):
        Monster._seq += 1
        self.mid = Monster._seq
        self.name = f"兽人{self.mid}"
        self.x, self.y = x, y
        self.max_hp = 30 + level * 10
        self.hp = self.max_hp
        self.alive = True
        self.item_id = None          # canvas 组 id

    def hp_color(self) -> str:
        ratio = self.hp / self.max_hp
        if ratio > 0.5:
            return COLOR_HP_FULL
        if ratio > 0.25:
            return COLOR_HP_MID
        return COLOR_HP_LOW


class Game:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("imgbot-legend")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.cv = tk.Canvas(self.root, width=W, height=H, bg=BG, highlightthickness=0)
        self.cv.pack()
        self._draw_grid()

        # 玩家状态
        self.px, self.py = W // 2, int(H * 0.62)
        self.level = 1
        self.xp = 0
        self.gold = 0
        self.player_item = self.cv.create_oval(
            self.px - 14, self.py - 14, self.px + 14, self.py + 14,
            fill=COLOR_PLAYER, outline="white")
        self._draw_status()

        # 世界状态
        self.monsters: dict[int, Monster] = {}
        self.coins: list[dict] = []          # {x, y, item_id, born}
        self.target: Monster | None = None
        self.attacking = False
        self._lock = threading.Lock()

        self.cv.bind("<Button-1>", self.on_click)
        self._spawn_monster()
        self._spawn_monster()
        self.root.after(600, self.tick)       # 主循环(攻击/刷新)
        self.root.after(200, self.refresh)    # 渲染循环

    # ================= 场景 =================
    def _draw_grid(self):
        for x in range(0, W, 40):
            self.cv.create_line(x, GROUND_TOP, x, H - STATUS_H, fill=GRID)
        for y in range(GROUND_TOP, H - STATUS_H, 40):
            self.cv.create_line(0, y, W, y, fill=GRID)
        self.cv.create_text(W // 2, GROUND_TOP - 30, fill="#888",
                            font=("黑体", 16),
                            text="imgbot-legend  点怪物=攻击  点金币=拾取")

    def _draw_status(self):
        self.cv.delete("status")
        y0 = H - STATUS_H + 8
        self.cv.create_rectangle(20, y0, W - 20, y0 + 20, fill="#111111",
                                 outline="#555", tags="status")
        xp_w = int((W - 44) * min(self.xp / self.xp_need(), 1.0))
        self.cv.create_rectangle(22, y0 + 2, 22 + xp_w, y0 + 18,
                                 fill=COLOR_XP, width=0, tags="status")
        self.cv.create_text(W // 2, y0 + 10, fill="white", font=("黑体", 11),
                            text=f"LV{self.level}  XP {self.xp}/{self.xp_need()}",
                            tags="status")
        self.cv.create_text(40, y0 + 40, fill="white", font=("黑体", 20, "bold"),
                            text=f"金币 {self.gold}", tags="status")
        self.cv.create_text(W - 120, y0 + 40, fill="#aaa", font=("黑体", 12),
                            text=f"伤害 {self.damage()}/击", tags="status")

    def xp_need(self) -> int:
        return self.level * 20

    def damage(self) -> int:
        return self.level * 2 + 3

    # ================= 交互 =================
    def on_click(self, ev):
        print(f"CLICK ev=({ev.x},{ev.y}) target={self.target.name if self.target else None}",
              flush=True)
        # 金币优先(拾取)
        for c in list(self.coins):
            if abs(ev.x - c["x"]) <= COIN_R + 6 and abs(ev.y - c["y"]) <= COIN_R + 6:
                self.gold += 1
                self.cv.delete(c["item_id"])
                self.coins.remove(c)
                self._draw_status()
                return
        # 怪物(点本体/血条都算选中)
        for m in self.monsters.values():
            if not m.alive:
                continue
            if (abs(ev.x - m.x) <= MONSTER_R + 8
                    and m.y - 26 <= ev.y <= m.y + MONSTER_R):
                self.target = m
                if not self.attacking:
                    self.attacking = True
                    self.root.after(400, self.attack_tick)
                return

    # ================= 战斗循环 =================
    def attack_tick(self):
        if not self.attacking:
            return
        m = self.target
        if m is None or not m.alive or m.mid not in self.monsters:
            self.attacking = False
            return
        dmg = self.damage() + random.randint(0, 3)
        m.hp -= dmg
        self.cv.create_text(m.x + random.randint(-10, 10), m.y - 30,
                            fill="#ff8866", font=("黑体", 10, "bold"),
                            text=str(dmg), tags="fx")
        if m.hp <= 0:
            self.kill_monster(m)
            self.attacking = False
        self.root.after(800, self.attack_tick)

    def kill_monster(self, m: Monster):
        m.alive = False
        self.monsters.pop(m.mid, None)
        self.cv.delete(m.item_id)
        self.xp += 5 + m.max_hp // 5
        while self.xp >= self.xp_need():
            self.xp -= self.xp_need()
            self.level += 1
            self.cv.create_text(W // 2, H // 2, fill="#FFD700",
                                font=("黑体", 32, "bold"), text="升级!",
                                tags="fx")
        # 掉落 1-2 金币
        for _ in range(random.randint(1, 2)):
            cx = m.x + random.randint(-30, 30)
            cy = m.y + random.randint(10, 30)
            cy = min(max(cy, GROUND_TOP + 20), H - STATUS_H - 10)
            item = self.cv.create_oval(cx - COIN_R, cy - COIN_R,
                                       cx + COIN_R, cy + COIN_R,
                                       fill=COLOR_COIN, outline="#aa8800")
            self.coins.append({"x": cx, "y": cy, "item_id": item,
                               "born": time.time()})
        self._draw_status()

    # ================= 刷新/渲染循环 =================
    def _spawn_monster(self):
        if len(self.monsters) >= 3:
            return
        for _ in range(30):
            x = random.randint(60, W - 60)
            y = random.randint(GROUND_TOP + 60, H - STATUS_H - 40)
            if abs(x - self.px) < 120 and abs(y - self.py) < 80:
                continue                            # 不刷在玩家脚边
            m = Monster(x, y, self.level)
            self._paint_monster(m)
            self.monsters[m.mid] = m
            return

    def _paint_monster(self, m: Monster):
        if m.item_id:
            self.cv.delete(m.item_id)
        gid = m.mid
        self.cv.create_oval(m.x - MONSTER_R, m.y - MONSTER_R,
                            m.x + MONSTER_R, m.y + MONSTER_R,
                            fill=COLOR_MON, outline="#7a1f1f", width=2,
                            tags=f"m{gid}")
        bx, bw = m.x - 24, 48
        self.cv.create_rectangle(bx, m.y - 28, bx + bw, m.y - 20,
                                 fill="#111111", width=0, tags=f"m{gid}")
        ratio = max(m.hp / m.max_hp, 0.0)
        self.cv.create_rectangle(bx, m.y - 28, bx + int(bw * ratio), m.y - 20,
                                 fill=m.hp_color(), width=0, tags=f"m{gid}")
        self.cv.create_text(m.x, m.y - 36, fill="#eee", font=("黑体", 10),
                            text=m.name, tags=f"m{gid}")
        m.item_id = f"m{gid}"

    def tick(self):
        """600ms: 清尸体特效/刷怪/攻击中的怪自动跟随刷新画面。"""
        self.cv.delete("fx")
        for m in list(self.monsters.values()):
            if m.hp != getattr(m, "_last_hp", m.max_hp):
                self._paint_monster(m)
                m._last_hp = m.hp
        self._spawn_monster()
        # 金币 12 秒过期
        now = time.time()
        for c in list(self.coins):
            if now - c["born"] > 12:
                self.cv.delete(c["item_id"])
                self.coins.remove(c)
        self.root.after(600, self.tick)

    def refresh(self):
        self._draw_status()
        self.root.after(500, self.refresh)

    def run(self):
        self.root.mainloop()


import time  # noqa: E402

if __name__ == "__main__":
    Game().run()
