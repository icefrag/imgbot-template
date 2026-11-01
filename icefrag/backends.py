# -*- coding: utf-8 -*-
"""后端抽象: adb(模拟器)与 window(PC 窗口)两端——发现、绑定、ctx 组装。

方言差异全部隔离在本模块; worker/console 对后端无感, 只认 Worker 协议。
任务方言(imgbot AGENTS): adb=actions.*(魔神语法) / window=ops.*(大漠语法)。
"""
from __future__ import annotations

import ctypes
import random
import re
import time
from collections import namedtuple

from . import ROOT

SHOTS = ROOT / "logs" / "shots"

# dsl 拟人键鼠默认(window/adb 两端共用; settle_ms 区间每次随机取值)
MouseStyle = namedtuple("MouseStyle", "human jitter settle_ms")


# ==================== 拾取(window 端热键收编) ====================
def pick_window(pick_mode: str, class_filter: str = "") -> int | None:
    """按 pick_mode 拾取目标窗口句柄; 无效/被过滤返回 None。

    hover: 鼠标当前所在的顶层窗口(用户指哪打哪);
    focus: 前台活动窗口中具有输入焦点的子窗口(模拟器渲染窗场景)。
           GetGUIThreadInfo 跨线程常返回假零(imgbot AGENTS 焦点坑), 故
           focus 模式 = 光标所在窗口, 子窗焦点回退用 AttachThreadInput 权威查。
    """
    import ctypes.wintypes as wt
    u32 = ctypes.windll.user32
    pt = wt.POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    hwnd = u32.WindowFromPoint(pt)
    if not hwnd:
        return None
    if pick_mode == "focus":
        k32 = ctypes.windll.kernel32
        ours = k32.GetCurrentThreadId()
        tgt = u32.GetWindowThreadProcessId(hwnd, None)
        attached = u32.AttachThreadInput(ours, tgt, True)
        try:
            child = u32.GetFocus()
        finally:
            if attached:
                u32.AttachThreadInput(ours, tgt, False)
        if child and u32.IsWindow(child):
            hwnd = child
    if class_filter:
        buf = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, buf, 256)
        if buf.value != class_filter:
            return None
    return hwnd


def window_title(hwnd: int) -> str:
    u32 = ctypes.windll.user32
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value or f"hwnd={hwnd}"


# ==================== 绑定与 ctx 组装 ====================
class Ctx:
    """任务代码的全部世界(见 spec.md ctx 字段表)。字段按端装配。"""

    def __init__(self, backend: str, name: str, cfg, log, stop,
                 dm=None, ops=None, device=None, nav=None, mouse=None):
        self.backend = backend
        self.name = name                          # 显示名(表格行/日志前缀)
        self.cfg = cfg                            # 业务配置对象
        self.log = log
        self.stop = stop
        self.dm = dm
        self.ops = ops
        self.device = device
        self.nav = nav                            # 界面导航图(task 声明表时由 worker 建)
        self.mouse = mouse or MouseStyle(True, 3, (60, 160))   # dsl click 默认风格
        self._last_progress = time.monotonic()    # 看门狗打点(dsl 命中/点击自动刷新)

    def progress(self, note: str = ""):
        """打一次进展点(无进展看门狗的信号; dsl 命中已自动打, 长轮询可手动)。"""
        self._last_progress = time.monotonic()

    def shot(self, tag: str = "") -> Path | None:
        """失败留痕: window 端存当前帧, adb 端存设备截图。"""
        SHOTS.mkdir(parents=True, exist_ok=True)
        # 文件名消毒: 窗口标题/adb序列号常带 \ : 等非法字符, imwrite 不抛只返 False
        stem = re.sub(r'[\\/:*?"<>|]', "_", f"{self.name}_{tag or 'shot'}")
        p = SHOTS / f"{time.strftime('%m%d_%H%M%S')}_{stem}.png"
        try:
            ok = False
            if self.dm is not None:               # window 绑定帧 / adb 鸭子帧源
                import cv2
                ok, buf = cv2.imencode(".png", self.dm._screen())
                if ok:                            # 不走 cv2.imwrite: 中文路径它静默失败
                    p.write_bytes(buf.tobytes())
            elif self.device is not None:
                self.device.save_screenshot(str(p))
                ok = True
            if not ok:
                self.log(f"shot 写盘失败: {p.name}", "warn")
                return None
            return p
        except Exception:
            return None


def _apply_dx_switches(dm, scaffold, log) -> None:
    """绑定后能力开关(对症下药): 全部依赖注入件(dx 系通道)在场。
    注入件不在场时警告跳过——配置失配不该打断收编, 日志留痕可见。"""
    wants = [label for attr, label in (("fake_active", "假激活"),
                                       ("hook_keystate", "键状态钩子"),
                                       ("hide_module", "隐藏模块"))
             if getattr(scaffold, attr, False)]
    if not wants:
        return
    if getattr(dm, "_dx", None) is None:
        log(f"开关[{'+'.join(wants)}]需 dx 系通道(注入件不在场), 已跳过", "warn")
        return
    if scaffold.fake_active:
        dm.EnableFakeActive(1)
    if scaffold.hook_keystate:
        dm._dx.hook_keystate()
    if scaffold.hide_module:
        dm._dx.hide_module()


def bind_window_backend(hwnd: int, scaffold, business_cfg, log, stop) -> Ctx:
    """window 端绑定: DmSoft → 通道 → 对症开关 → 模板目录 → Ops。"""
    from imgbot.dmsoft import DmSoft
    from imgbot.ops import Ops
    dm = DmSoft()
    assert dm.BindWindow(hwnd, scaffold.display, scaffold.mouse,
                         scaffold.keypad, 0) == 1, "BindWindow 失败"
    dm.SetPath(str(ROOT / "templates"))
    _apply_dx_switches(dm, scaffold, log)
    ops = Ops(dm)
    return Ctx("window", window_title(hwnd), business_cfg, log, stop,
               dm=dm, ops=ops,
               mouse=MouseStyle(scaffold.human_mouse, scaffold.click_jitter,
                                tuple(scaffold.click_settle_ms)))


class _AdbMk:
    """对齐 dm.keymouse 形状的 adb 键鼠鸭子: click=到位停顿(前摇)+tap,
    double_click=两击带 80~120ms 间隔(零间隔真机不认双击)。
    落点抖动归 dsl 层算好坐标再传进来。"""

    def __init__(self, target):
        self._t = target

    def click(self, x, y, settle=None):
        if settle:
            time.sleep(settle)                    # adb 无轨迹, 到位停顿=点击前摇
        self._t.tap(int(x), int(y))

    def double_click(self, x, y, settle=None):
        self.click(x, y, settle)
        time.sleep(random.uniform(0.08, 0.12))
        self.click(x, y)


class _AdbDm:
    """喂 Ops 门面的 adb 鸭子: _screen→设备截图(BGR), keymouse→拟人点击
    (find_tap/tap_until_gone/dsl.click 的一步式点击走这条路)。"""

    def __init__(self, target):
        self._t = target
        self._pos = (0, 0)

    def _screen(self):
        return self._t.screenshot()

    @property
    def keymouse(self):
        return _AdbMk(self._t)

    def MoveTo(self, x, y):
        self._pos = (int(x), int(y))

    def LeftClick(self):
        self._t.tap(*self._pos)


def bind_adb_backend(serial: str, scaffold, business_cfg, log, stop) -> Ctx:
    """adb 端绑定: AdbTarget(魔神线, 天然后台) + Ops 鸭子帧源(图色 DSL 同构)。"""
    from imgbot.ops import Ops
    from imgbot.target import AdbTarget
    target = AdbTarget(serial)
    dm = _AdbDm(target)
    ops = Ops(dm)
    return Ctx("adb", serial, business_cfg, log, stop,
               device=target, ops=ops, dm=dm,
               mouse=MouseStyle(scaffold.human_mouse, scaffold.click_jitter,
                                tuple(scaffold.click_settle_ms)))


def build_nav(task_mod, ctx) -> "object | None":
    """按 task.py 的声明表建 Nav(imgbot.nav 界面导航图), 无表返回 None。

    三张表(全部可选, 但要 go()/at() 至少得有 NAV_SCREENS+NAV_EDGES):
      NAV_SCREENS = {"city": "nav/city_hud.png",              # 锚点图
                     "dungeon": ("nav/dg_title.png", (0,0,300,80))}  # +限矩形
      NAV_EDGES = {("city", "dungeon"): "nav/dg_btn.png",     # 模板名=找到就点
                   ("dungeon", "city"): _back_to_city}        # 或函数(组 ops 原语)
      NAV_INTERRUPTS = ["nav/reward_ok.png"]                   # 任意屏会冒的弹窗
    """
    screens = getattr(task_mod, "NAV_SCREENS", None)
    if not screens:
        return None
    from imgbot.nav import Nav
    nav = Nav(ctx.ops)
    for name, spec in screens.items():
        anchor, region = spec if isinstance(spec, tuple) else (spec, None)
        nav.screen(name, anchor, region=region)
    for (src, dst), act in getattr(task_mod, "NAV_EDGES", {}).items():
        if callable(act):
            nav.edge(src, dst, act)
        else:                                    # 模板名: 等按钮出现(8s)点了就走
            nav.edge(src, dst,
                     lambda t=act: ctx.ops.find_tap(t, timeout=8))
    nav.on_interrupt(list(getattr(task_mod, "NAV_INTERRUPTS", [])))
    return nav


def unbind(ctx: Ctx) -> None:
    """收口(永远执行, 崩溃也执行)。"""
    try:
        if ctx.backend == "window" and ctx.dm is not None:
            lock = getattr(ctx.dm, "LockInput", None)
            if lock:                             # LockInput 保险丝: 脚本锁了
                lock(0)                          # 输入没解锁, 收口强制解锁
            ctx.dm.UnBindWindow()
        elif ctx.device is not None:
            ctx.device.close()
    except Exception:
        pass
