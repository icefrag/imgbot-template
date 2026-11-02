# -*- coding: utf-8 -*-
"""命令清单: task.py 顶层可用的一切命令。顶部一行 `from icefrag.dsl import *` 即得。

两层:
  icefrag 命令(snake_case) —— 只收"组装": 拟人键鼠/等待环/复合动作/
    OCR 识字/界面导航。大漠单命令的换皮一律不收: 单帧查询直接用大漠直通。
  大漠直通(PascalCase, DmSoft 全部公有方法) —— imgbot DmSoft 同名同参透传:
    LeftClick / FindPic / SetWindowState / SendString ... 与大漠一字不差,
    老脚本肌肉记忆零成本。仅 window 端可用(adb 端调用报错指路)。

约定(违者必踩):
  ① 凡时间皆毫秒 —— sleep(500)=半秒, timeout=10000=10 秒(默认值);
  ② 找不到/超时返回 None 或 False, 不抛异常 —— "没找到"是挂机常态, 真故障
     (窗口没了)由框架绑定层兜底重开;
  ③ 停止信号(F9)贯穿所有 sleep 与等待, 按下即醒即退;
  ④ 大漠直通仅 window 端; adb 方言与更冷门的动作走 ctx.device / ctx.ops 逃生舱。

命令速查(★ = 一步顶三步的招牌复合动作):
  键鼠  click(x, y[, jitter, human, settle])  拟人点击: 贝塞尔轨迹+随机停顿+
        落点抖动(默认在 scaffold.toml, 调用处可单次覆盖; human=False 瞬移急点)
        dblclick(x, y[, ...])  双击(同 click 参数)
        drag(x1, y1, x2, y2, ms)   按住拖拽(列表滚动/滑块)
        sleep(ms)|(lo, hi 随机)
        裸键鼠/打字走大漠直通: MoveTo/LeftClick/KeyPressChar/SendString/WheelDown
  消息  log(text)   shot(tag)   stopped() -> bool(F9 叫停了吗, 挂机循环退出条件)
  找点  find_all(pic) -> [(x, y), ...]   单帧找全部同类图(imgbot 的 dm 无
        FindPicEx, 这是真增量; 单个命中用直通 FindPic)
  ★     find_tap(pic, timeout=0, verify=None) -> bool      找到就拟人点(0=单帧;
        verify=点后必须出现的图, 没等到=失败, 防"点了没跳转")
  ★     tap_until_gone(pic, timeout) -> int 连点数          连点到消失
  等待  wait_pic(pic) -> (x, y, 分数) | None
        wait_pic_any(pics) -> (名, x, y, 分数) | None
        wait_pic_gone(pic) -> bool      wait_color(color) -> (x, y) | None
        wait_color_gone(color) -> bool  wait_text(text) -> (x, y, 相似度) | None
  识字  ocr(region) -> str                    读全文("任务名叫什么")
        ocr_numbers(region) -> [23, 456]       抠数字(等级取[0], 坐标取[:2])
  找字  find_str(text, region) -> (x, y) | None  OCR 找字位置(找到就能点;
        关键词 ≥4 字才稳; 非 dm 字库线, 是全生态唯一识字线)
  导航  go("dungeon") -> bool   界面导航图带路(task.py 声明 NAV_SCREENS/NAV_EDGES,
        迷路自动重定位自愈; 迷路且重定位失败抛 LostError → 配 on_fuse 重登)
        at("city") -> bool      期望验证: 是否在指定界面(单帧一张锚点, 便宜)
"""
from __future__ import annotations

import random
import re
import threading

_local = threading.local()


def _bind(ctx):
    """worker 每轮任务前把 ctx 挂到本线程(框架调用, 脚本侧无感)。"""
    _local.ctx = ctx


def _ctx():
    ctx = getattr(_local, "ctx", None)
    if ctx is None:
        raise RuntimeError(
            "命令要在任务里用(main_task 及其子函数), 脚手架外没有绑定")
    return ctx


# ================= 键鼠(拟人: window=dm 通道 / adb=device) =================
def _pt_jitter(x, y, j):
    """落点抖动 ±j px(0=关): 每次精确点同一处也是机器人特征。"""
    if not j:
        return x, y
    return x + random.randint(-j, j), y + random.randint(-j, j)


def _settle_s(mouse, settle):
    """dsl 毫秒 → 键鼠层秒; None 取配置区间随机(人不是节拍器)。"""
    if settle is not None:
        return settle / 1000
    lo, hi = mouse.settle_ms
    return random.uniform(lo, hi) / 1000


def click(x: int, y: int, jitter: int | None = None,
          human: bool | None = None, settle: int | None = None):
    """点击 (x, y)。默认拟人: 贝塞尔轨迹到位→随机停顿→落点抖动(默认见
    scaffold.toml 的 human_mouse/click_jitter/click_settle_ms)。
    jitter: 落点 ±px(0=精确); human=False 瞬移急点(速度优先, 停顿固定,
    不吃 settle); settle: 到位停顿 ms。adb 端=停顿前摇+抖动 tap。"""
    ctx = _ctx()
    ctx.progress()
    m = ctx.mouse
    j = m.jitter if jitter is None else jitter
    h = m.human if human is None else human
    tx, ty = _pt_jitter(x, y, j)
    ctx.click(tx, ty, h, _settle_s(m, settle))   # 端方言在绑定层臂(backends)


def dblclick(x: int, y: int, jitter: int | None = None,
             human: bool | None = None, settle: int | None = None):
    """双击 (x, y), 参数同 click; adb 端两击带 80~120ms 间隔。"""
    ctx = _ctx()
    ctx.progress()
    m = ctx.mouse
    j = m.jitter if jitter is None else jitter
    h = m.human if human is None else human
    tx, ty = _pt_jitter(x, y, j)
    ctx.dblclick(tx, ty, h, _settle_s(m, settle))


def drag(x1: int, y1: int, x2: int, y2: int, ms: int = 350):
    """按住拖拽(列表滚动/滑块): window=按住左键插值拖, adb=原生 swipe。"""
    ctx = _ctx()
    ctx.progress()
    ctx.swipe(x1, y1, x2, y2, ms)


# ================= 消息 =================
def sleep(ms):
    """可中断睡眠: F9 按下立刻醒(代替 time.sleep 的傻等)。
    ms 给区间则每次取随机: sleep((400, 900)) —— 固定间隔是检测特征。"""
    if isinstance(ms, (tuple, list)):
        ms = random.uniform(ms[0], ms[1])
    _ctx().stop.wait(ms / 1000)


def stopped() -> bool:
    """F9 停止键按下过吗 —— 挂机循环的退出条件: while not stopped(): ...
    (sleep/等待族被叫停只是提前醒/返 None, 循环真正退出靠它)。"""
    return _ctx().stop.is_set()


def log(text: str, level: str = "info"):
    """打一条日志(中控台日志面板/终端), level: info|warn|error。"""
    _ctx().log(text, level)


def shot(tag: str = ""):
    """截当前绑定目标一帧存 logs/shots/(月日_时分秒_目标_标签.png)留痕, 返回路径或 None。"""
    return _ctx().shot(tag)


# ================= 找点(单帧) =================
def find_all(pic: str, region=None, threshold: float | None = None
             ) -> list[tuple[int, int]]:
    """单帧找全部同类图(列表项/多目标), 近邻去重。单个命中用大漠直通 FindPic。"""
    hits = _ctx().ops.find_all(pic, region=region, threshold=threshold)
    if hits:
        _ctx().progress()
    return hits


# ================= 复合动作(招牌) =================
def find_tap(pic: str, region=None, timeout: int = 0,
             threshold: float | None = None,
             verify: str | None = None) -> bool:
    """找到就拟人点(贝塞尔轨迹+停顿)。timeout=0 单帧试; verify=点后必须
    出现的图(没等到=失败, 防"点了没跳转"); 超时返 False。"""
    return _ctx().ops.find_tap(pic, region=region,
                               timeout=timeout / 1000 if timeout else 0,
                               threshold=threshold, verify=verify,
                               stop=_ctx().stop)


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
    """找字(OCR 线): OCR 定位 + 按序比例匹配, 返回 (x, y) 或 None,
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


# ==================== 大漠直通(DmSoft 公有方法同名透传) ====================
def _dm_public_names() -> list[str]:
    """DmSoft 公有命令名: 下划线私有不收, keymouse 这类属性(非命令)不收。
    introspect 生成 —— imgbot 侧加命令自动跟进, 零维护零漂移。"""
    from imgbot.dmsoft import DmSoft
    return sorted(n for n in dir(DmSoft)
                  if not n.startswith("_") and callable(getattr(DmSoft, n)))


def _dm_proxy(name: str):
    """同名代理: 委托本线程绑定目标的 dm —— 签名/返回/语义与大漠一字不差,
    不加任何魔法(不打点/不换算), 原样直通。"""
    from imgbot.dmsoft import DmSoft
    brief = (getattr(DmSoft, name).__doc__ or "").strip().split("\n")[0]

    def call(*args, **kwargs):
        dm = _ctx().dm
        fn = getattr(dm, name, None)
        if fn is None:
            raise RuntimeError(f"大漠直通命令仅 window 端可用: {name}(); "
                               "adb 端走 icefrag 命令 / ctx.device")
        return fn(*args, **kwargs)

    call.__name__ = name
    call.__doc__ = f"大漠直通: {brief}" if brief else "大漠直通(与大漠同名同参)。"
    return call


DM_PASSTHROUGH = _dm_public_names()

_dm_clash = [n for n in DM_PASSTHROUGH if n in globals()]
assert not _dm_clash, f"DmSoft 命令与 icefrag 命令撞名, 透传层拒建: {_dm_clash}"
for _name in DM_PASSTHROUGH:
    globals()[_name] = _dm_proxy(_name)
del _name

__all__ = [
    "click", "dblclick", "drag", "sleep",
    "stopped", "log", "shot",
    "find_all", "find_tap", "tap_until_gone",
    "wait_pic", "wait_pic_any", "wait_pic_gone",
    "wait_color", "wait_color_gone", "wait_text",
    "ocr", "ocr_numbers", "find_str",
    "go", "at", "progress",
] + DM_PASSTHROUGH
