# -*- coding: utf-8 -*-
"""DSL: task.py 的顶层挂机动词表。task.py 顶部一行 `from bot.dsl import *` 即得。

约定(违者必踩):
  ① 凡时间皆毫秒 —— sleep(500)=半秒, timeout=10000=10 秒(默认值);
  ② 找不到/超时返回 None 或 False, 不抛异常 —— "没找到"是挂机常态, 真故障
     (窗口没了)由框架绑定层兜底重开;
  ③ 停止信号(F9)贯穿所有 sleep 与等待, 按下即醒即退;
  ④ 冷门动作(wait_until/retry/wait_stable/wait_change/swipe_find/read_number/
     probe/check_points...)与窗口管理走 ctx.ops / ctx.dm / ctx.device 逃生舱。

命令速查(★ = 一步顶三步的招牌复合动作):
  键鼠  click(x, y)   dblclick(x, y)   move(x, y)   key("ctrl+s")   sleep(ms)
  消息  log(text)   shot(tag)
  找点  find_color(color, region, tol) -> [(x, y), ...]    单帧找全部色块
        find_all(pic) -> [(x, y), ...]                      单帧找全部同类图
        find_multi_color(rect, pts, direction) -> (x, y)|None  多点找色(大漠
        FindMultiColor 对应物, 色块与同色文字的判别器; pts=[Pt(0,0,色,tol),...],
        pixpick 生产, 见 imgbot 仓《多点找色Pt规范.md》)
        exists(pic) -> bool
  ★     find_tap(pic, timeout=0) -> bool                    找到就点(0=单帧)
  ★     tap_until_gone(pic, timeout) -> int 连点数          连点到消失
  等待  wait_pic(pic) -> (x, y, 分数) | None
        wait_pic_any(pics) -> (名, x, y, 分数) | None
        wait_pic_gone(pic) -> bool      wait_color(color) -> (x, y) | None
        wait_color_gone(color) -> bool  wait_text(text) -> (x, y, 相似度) | None
  识字  ocr(region) -> str                    读全文("任务名叫什么")
        ocr_numbers(region) -> [23, 456]       抠数字(等级取[0], 坐标取[:2])
  找字  find_str(text, region) -> (x, y) | None  找文字位置(大漠 FindStr 风,
        找到就能点; 关键词 ≥4 字才稳)
  导航  go("dungeon") -> bool   界面导航图带路(task.py 声明 NAV_SCREENS/NAVEDGES,
        迷路自动重定位自愈; 迷路且重定位失败抛 LostError → 配 on_fuse 重登)
        at("city") -> bool      期望验证: 是否在指定界面(单帧一张锚点, 便宜)
"""
from __future__ import annotations

import re
import threading
import time

from imgbot.vision import Pt

_local = threading.local()

_MODIFIERS = ("ctrl", "alt", "shift", "win")

# 安卓键名→keycode(dsl.key 的 adb 分支; 组合键安卓无此语义, 不支持)
ADB_KEYS = {"home": 3, "back": 4, "menu": 82, "enter": 66, "search": 84,
            "del": 67, "delete": 67, "tab": 61, "space": 62, "esc": 111,
            "up": 19, "down": 20, "left": 21, "right": 22,
            "vol_up": 24, "vol_down": 25, "power": 26,
            "0": 7, "1": 8, "2": 9, "3": 10, "4": 11, "5": 12, "6": 13,
            "7": 14, "8": 15, "9": 16}


def _bind(ctx):
    """worker 每轮任务前把 ctx 挂到本线程(框架调用, 脚本侧无感)。"""
    _local.ctx = ctx


def _ctx():
    ctx = getattr(_local, "ctx", None)
    if ctx is None:
        raise RuntimeError(
            "DSL 命令要在任务里用(main_task 及其子函数), 脚手架外没有绑定")
    return ctx


__all__ = [
    "click", "dblclick", "move", "key", "sleep", "log", "shot",
    "find_color", "find_all", "find_multi_color", "exists",
    "find_tap", "tap_until_gone",
    "wait_pic", "wait_pic_any", "wait_pic_gone",
    "wait_color", "wait_color_gone", "wait_text",
    "ocr", "ocr_numbers", "find_str", "Pt",
    "go", "at", "progress",
]


# ================= 键鼠(端无关: window=dm / adb=device) =================
def click(x: int, y: int):
    """点击 (x, y)。window: 移动+左键; adb: tap。"""
    ctx = _ctx()
    ctx.progress()
    if ctx.backend == "window":
        ctx.dm.MoveTo(x, y)
        ctx.dm.LeftClick()
    else:
        ctx.device.tap(x, y)                 # adb 分支: 真机验收后校准


def dblclick(x: int, y: int):
    """双击 (x, y)。"""
    ctx = _ctx()
    if ctx.backend == "window":
        ctx.dm.MoveTo(x, y)
        ctx.dm.LeftDoubleClick()
    else:
        ctx.device.tap(x, y)                 # adb 近似: 双击≈两连点
        ctx.device.tap(x, y)


def move(x: int, y: int):
    """悬停(不点)。adb 端无悬停概念, 报错指路。"""
    ctx = _ctx()
    if ctx.backend == "window":
        ctx.dm.MoveTo(x, y)
    else:
        raise RuntimeError("adb 端无悬停, 用 click / ctx.device.swipe")


def key(s: str):
    """按键/组合键: key("enter") / key("ctrl+s")(修饰键 ctrl/alt/shift/win)。"""
    ctx = _ctx()
    parts = [p.strip().lower() for p in s.split("+")]
    mods, main = parts[:-1], parts[-1]
    bad = [m for m in mods if m not in _MODIFIERS]
    if bad:
        raise ValueError(f"修饰键只认 {_MODIFIERS}: {s!r}")
    if ctx.backend == "window":
        dm = ctx.dm
        for m in mods:
            dm.KeyDownChar(m)
        dm.KeyPressChar(main)
        for m in reversed(mods):
            dm.KeyUpChar(m)
    else:
        if mods:
            raise ValueError(f"adb 端无组合键语义, 单键用键名: {ADB_KEYS}")
        code = ADB_KEYS.get(main)
        if code is None:
            raise ValueError(f"adb 键名未收录(可加进 ADB_KEYS): {main!r}")
        ctx.device.keyevent(code)


# ================= 消息 =================
def sleep(ms: int):
    """可中断睡眠: F9 按下立刻醒(代替 time.sleep 的傻等)。"""
    _ctx().stop.wait(ms / 1000)


def log(text: str, level: str = "info"):
    _ctx().log(text, level)


def shot(tag: str = ""):
    return _ctx().shot(tag)


# ================= 找点(单帧) =================
def find_color(color: str, region=None, tol: int = 0) -> list[tuple[int, int]]:
    """区域找全部色块。color="RRGGBB"(偏差给 tol, 或写 "RRGGBB-DRDGDB")。"""
    hit = _ctx().ops.find_color(color, region=region, tol=tol)
    if hit:
        _ctx().progress()
    return hit


def find_all(pic: str, region=None, threshold: float | None = None
             ) -> list[tuple[int, int]]:
    """单帧找全部同类图(列表项/多目标), 近邻去重。"""
    hits = _ctx().ops.find_all(pic, region=region, threshold=threshold)
    if hits:
        _ctx().progress()
    return hits


def exists(pic: str, region=None, threshold: float | None = None) -> bool:
    ok = _ctx().ops.exists(pic, region=region, threshold=threshold)
    if ok:
        _ctx().progress()
    return ok


def find_multi_color(rect, points, direction: int = 0):
    """多点找色(大漠 FindMultiColor 对应物): 锚点在 rect 内搜索, 全部相对
    偏移点同时命中才返回锚点 (x, y) 或 None —— 色块与同色文字的判别器。
    points 为 Pt 列表(pixpick 生产), 也收 [(dx,dy,"RRGGBB"[,tol]), ...] 色串。
    direction: 多候选取哪个, 0 左上 1 左下 2 右上 3 右下。"""
    hit = _ctx().ops.find_multi_color(rect, points, direction)
    if hit:
        _ctx().progress()
    return hit


# ================= 复合动作(招牌) =================
def find_tap(pic: str, region=None, timeout: int = 0,
             threshold: float | None = None) -> bool:
    """找到就拟人点。timeout=0 单帧试; 超时返 False。"""
    return _ctx().ops.find_tap(pic, region=region,
                               timeout=timeout / 1000 if timeout else 0,
                               threshold=threshold, stop=_ctx().stop)


def tap_until_gone(pic: str, region=None, timeout: int = 10000,
                   threshold: float | None = None) -> int:
    """连点直到图消失(确定/领取类), 返回点击次数; 不出现返回 0。"""
    return _ctx().ops.tap_until_gone(pic, region=region, timeout=timeout / 1000,
                                     threshold=threshold, stop=_ctx().stop)


# ================= 等待(超时皆返 None/False) =================
def wait_pic(pic: str, region=None, timeout: int = 10000,
             threshold: float | None = None):
    """等图出现, 返回 (中心x, 中心y, 分数); 超时自动截图留痕。"""
    hit = _ctx().ops.wait_pic(pic, region=region, timeout=timeout / 1000,
                              threshold=threshold, stop=_ctx().stop)
    if hit:
        _ctx().progress()
    return hit


def wait_pic_any(pics: list[str], region=None, timeout: int = 10000,
                 threshold: float | None = None):
    """等一组模板任一出现, 返回 (名字, x, y, 分数); 超时 None。"""
    return _ctx().ops.wait_pic_any(pics, region=region, timeout=timeout / 1000,
                                   threshold=threshold, stop=_ctx().stop)


def wait_pic_gone(pic: str, region=None, timeout: int = 10000,
                  threshold: float | None = None) -> bool:
    """等图消失(加载页结束判定)。"""
    return _ctx().ops.wait_pic_gone(pic, region=region, timeout=timeout / 1000,
                                    threshold=threshold, stop=_ctx().stop)


def wait_color(color: str, region=None, timeout: int = 10000):
    """等某色出现(色比图快), 返回 (x, y) 或 None。偏差写进色串:
    "RRGGBB-DRDGDB"。"""
    hit = _ctx().ops.wait_color(color, region=region, timeout=timeout / 1000,
                                stop=_ctx().stop)
    if hit:
        _ctx().progress()
    return hit


def wait_color_gone(color: str, region=None, timeout: int = 10000) -> bool:
    """等某色消失(等击杀/等加载), 消失 True / 超时 False。"""
    ok = _ctx().ops.wait_color_gone(color, region=region,
                                    timeout=timeout / 1000,
                                    stop=_ctx().stop)
    if ok:
        _ctx().progress()
    return ok


def wait_text(text: str, region=None, timeout: int = 10000):
    """OCR 等文字出现("完成"提示类), 返回 (中心x, 中心y, 相似度) 或 None。"""
    return _ctx().ops.wait_text(text, region=region, timeout=timeout / 1000,
                                stop=_ctx().stop)


# ================= 识字 / 找字(OCR) =================
def ocr(region=None, fast: bool = False) -> str:
    """识字: OCR 读区域全文, 行间空格连接("任务名叫什么"用这个)。
    fast=True 走快引擎: 只给"大字窄条"场景(板面标题行), 小字会漏读。"""
    return _ctx().ops.read_text(region, fast)


def ocr_numbers(region=None) -> list[int]:
    """识数: OCR 全文后抠所有数字串(等级取 [0], 坐标取 [:2]); 没识到返回 []。
    小字体数字不准时缩 region, 或走 ctx.ops.read_number 字模重武器。"""
    return [int(n) for n in re.findall(r"\d+", ocr(region))]


def find_str(text: str, region=None, min_ratio: float = 0.7):
    """找字(大漠 FindStr 风): OCR 定位 + 按序比例匹配, 返回 (x, y) 或 None,
    找到就能点。关键词 ≥4 字才稳(实测 7 字错 1 字仍命中); 2 字短词比例上限
    低, 需缩 region 并降 min_ratio。"""
    hit = _ctx().ops.find_text(text, region, min_ratio)
    if hit:
        _ctx().progress()
    return (hit[0], hit[1]) if hit else None


# ================= 界面导航(task.py 声明表驱动, 见 backends.build_nav) =================
def go(name: str, timeout: int = 120000) -> bool:
    """走到目标界面, 图自动带路(BFS)+迷路重定位自愈。到达 True / 超时安静
    False; 迷路且重定位失败抛 LostError(交给熔断 on_fuse 走重登线)。
    需要 task.py 声明 NAV_SCREENS/NAV_EDGES(没有就只是普通脚本, 别调)。"""
    ctx = _ctx()
    if ctx.nav is None:
        raise RuntimeError("task.py 未声明 NAV_SCREENS/NAV_EDGES, 没有导航图可用")
    ok = ctx.nav.go(name, timeout=timeout / 1000, stop=ctx.stop)
    if ok:
        ctx.progress()
    return ok


def at(name: str) -> bool:
    """期望验证: 当前是否在指定界面(单帧一张锚点, 高频便宜; 迷路判别用 go)。"""
    ctx = _ctx()
    if ctx.nav is None:
        raise RuntimeError("task.py 未声明 NAV_SCREENS, 没有导航图可用")
    return ctx.nav.at(name)


def progress(note: str = ""):
    """手动打一次进展点(看门狗信号; find/wait 命中与点击已自动打点)。
    长轮询循环里打点, 防无进展看门狗误杀。"""
    _ctx().progress(note)
