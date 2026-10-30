# -*- coding: utf-8 -*-
"""游戏冒烟驱动: 找窗口→截屏找红怪→SendInput 点击→验血条/击杀/掉落。"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2
import numpy as np

u32 = ctypes.windll.user32
u32.SetProcessDPIAware()


def find_game() -> int:
    u32.FindWindowW.restype = ctypes.c_void_p
    hwnd = u32.FindWindowW(None, "imgbot-legend")
    return int(hwnd or 0)


def client_shot(hwnd: int) -> np.ndarray:
    from imgbot.win32.capture import capture_client
    from imgbot.win32.window import GameWindow
    return capture_client(GameWindow(hwnd))


def find_monsters(img: np.ndarray) -> list[tuple[int, int]]:
    """红色圆形本体: BGR 掩码 #CC3333=(51,51,204)。"""
    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    mask = ((r > 170) & (r < 230) & (g > 30) & (g < 80)
            & (b > 30) & (b < 80)).astype(np.uint8)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    # 聚簇(半径 40 归并)
    pts: list[tuple[int, int]] = []
    for x, y in zip(xs, ys):
        for px, py in pts:
            if abs(px - x) < 40 and abs(py - y) < 40:
                break
        else:
            pts.append((int(x), int(y)))
    return pts


def click(x: int, y: int, hwnd: int | None = None):
    if hwnd:
        u32.SwitchToThisWindow(hwnd, True)   # 置前(前台锁兜底, 见 imgbot GA_ROOT 修复)
        time.sleep(0.15)
    u32.SetCursorPos(x, y)
    time.sleep(0.08)
    u32.mouse_event(2, 0, 0, 0, 0)      # LEFTDOWN
    time.sleep(0.05)
    u32.mouse_event(4, 0, 0, 0, 0)      # LEFTUP


def e2e():
    """一体化: 开游戏 → 点击怪物 → 验证击杀/掉落。"""
    subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "legend_game.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    hwnd = find_game()
    assert hwnd, "游戏窗口没找到"
    print(f"[1] 游戏 0x{hwnd:X}")
    img = client_shot(hwnd)
    mons = find_monsters(img)
    assert mons, "没识别到怪"
    print(f"[2] 怪 {len(mons)} 只 @ {mons}")
    mx, my = mons[0]
    ox, oy = client_origin(hwnd)
    click(ox + mx, oy + my, hwnd)
    print(f"[3] 点击 ({mx},{my})")
    killed, deadline = False, time.time() + 15
    while time.time() < deadline:
        time.sleep(1.0)
        mons_now = find_monsters(client_shot(hwnd))
        if not any(abs(x - mx) < 45 and abs(y - my) < 70 for x, y in mons_now):
            killed = True
            break
    print(f"[4] 击杀: {'OK' if killed else 'FAIL'}")
    time.sleep(1.0)
    img = client_shot(hwnd)
    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    coin_px = int(((r > 200) & (g > 170) & (b < 90)).sum())
    print(f"[5] 金币黄色像素: {coin_px} {'(有掉落)' if coin_px > 20 else '(无)'}")
    ok = killed and coin_px > 20
    print("E2E:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def client_origin(hwnd: int) -> tuple[int, int]:
    rect = wt.RECT()
    u32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = wt.POINT(0, 0)
    u32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def main() -> int:
    hwnd = find_game()
    if not hwnd:
        print("FAIL: 游戏窗口没找到")
        return 1
    print(f"[1] 游戏窗口 0x{hwnd:X}")
    time.sleep(0.5)

    img = client_shot(hwnd)
    print(f"[2] 截图 {img.shape[1]}x{img.shape[0]}")
    mons = find_monsters(img)
    print(f"[3] 红怪识别: {len(mons)} 只 @ {mons}")
    if not mons:
        print("FAIL: 没识别到怪")
        return 1

    ox, oy = client_origin(hwnd)
    mx, my = mons[0]
    click(ox + mx, oy + my)
    print(f"[4] 点击怪 ({mx},{my}) → 攻击启动")

    # 等击杀(伤害 ~5-7/0.8s, 怪 40HP → ~6 击 ≈ 5s; 放 12s)
    deadline = time.time() + 12
    killed = False
    while time.time() < deadline:
        time.sleep(1.0)
        img = client_shot(hwnd)
        mons2 = find_monsters(img)
        if not any(abs(x - mx) < 40 and abs(y - my) < 60 for x, y in mons2):
            killed = True
            break
    print(f"[5] 怪被击杀: {'OK' if killed else 'FAIL'}")

    # 金币拾取: 找黄色圆点击
    time.sleep(1.0)
    img = client_shot(hwnd)
    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    mask = ((r > 200) & (g > 170) & (b < 90)).astype(np.uint8)
    ys, xs = np.nonzero(mask)
    got_coin = False
    if len(xs):
        cx, cy = int(np.median(xs)), int(np.median(ys))
        click(ox + cx, oy + cy)
        time.sleep(0.5)
        got_coin = True
    print(f"[6] 金币拾取点击: {'OK' if got_coin else 'SKIP(没找到金币)'}")

    ok = killed
    print("游戏冒烟:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(e2e())
