# -*- coding: utf-8 -*-
"""dsl 键鼠组织层离线自检: 假 ctx + 假键鼠/假设备, 验拟人路由/抖动界/停顿
管道/急点分支/drag 两端/sleep 区间/find_tap 透传。跑法: uv run test/test_dsl_mouse.py
"""
import threading
import time
import types

from icefrag import dsl
from icefrag.backends import MouseStyle, _AdbDm


class FakeMk:                          # 假 dm.keymouse(录制一步式调用)
    def __init__(self):
        self.calls = []

    def click(self, x, y, settle=None):
        self.calls.append(("click", x, y, settle))

    def double_click(self, x, y, settle=None):
        self.calls.append(("dbl", x, y, settle))


class FakeDm:
    def __init__(self, mk):
        self.keymouse = mk
        self.calls = []
        self.key_calls = []

    def MoveTo(self, x, y):
        self.calls.append(("move", x, y))

    def LeftClick(self):
        self.calls.append(("lclick",))

    def LeftDoubleClick(self):
        self.calls.append(("ldbl",))

    def LeftDown(self):
        self.calls.append(("ldown",))

    def LeftUp(self):
        self.calls.append(("lup",))

    def KeyDownChar(self, k):
        self.key_calls.append(("down", k))

    def KeyPressChar(self, k):
        self.key_calls.append(("press", k))

    def KeyUpChar(self, k):
        self.key_calls.append(("up", k))


class FakeOps:
    def __init__(self):
        self.kwargs = None

    def find_tap(self, pic, **kw):
        self.kwargs = {"pic": pic, **kw}
        return True


class FakeDevice:
    def __init__(self):
        self.taps = []
        self.swipes = []
        self.keys = []

    def tap(self, x, y):
        self.taps.append((x, y))

    def swipe(self, x1, y1, x2, y2, ms):
        self.swipes.append((x1, y1, x2, y2, ms))

    def keyevent(self, code):
        self.keys.append(code)


def bind(backend="window", mouse=None):
    dev = FakeDevice()
    ctx = types.SimpleNamespace(
        backend=backend,
        dm=_AdbDm(dev) if backend == "adb" else FakeDm(FakeMk()),
        device=dev, ops=FakeOps(),
        mouse=mouse or MouseStyle(True, 3, (60, 160)),
        progress=lambda *a: None, log=lambda *a: None,
        stop=threading.Event())
    dsl._bind(ctx)
    return ctx


def main():
    # 1. window 拟人默认: 一步式 keymouse.click, 抖动 ±3 内, 停顿区间内
    ctx = bind()
    dsl.click(500, 300)
    (kind, x, y, settle), = ctx.dm.keymouse.calls
    assert kind == "click" and abs(x - 500) <= 3 and abs(y - 300) <= 3
    assert 0.06 <= settle <= 0.16

    # 2. 显式覆盖: jitter=0 精确落点, settle=200 → 0.2s
    ctx = bind()
    dsl.click(100, 80, jitter=0, settle=200)
    (_kind, x, y, settle), = ctx.dm.keymouse.calls
    assert (x, y) == (100, 80) and settle == 0.2

    # 3. human=False: 老两步瞬移, keymouse 不参与
    ctx = bind()
    dsl.click(10, 20, human=False)
    assert [c[0] for c in ctx.dm.calls] == ["move", "lclick"]
    assert not ctx.dm.keymouse.calls

    # 4. 配置默认关轨迹(human_mouse=False)同样走急点
    ctx = bind(mouse=MouseStyle(False, 3, (60, 160)))
    dsl.click(1, 2)
    assert [c[0] for c in ctx.dm.calls] == ["move", "lclick"]

    # 5. dblclick: 拟人走一步式, 急点走 LeftDoubleClick
    ctx = bind()
    dsl.dblclick(50, 60)
    assert ctx.dm.keymouse.calls[0][0] == "dbl"
    ctx = bind()
    dsl.dblclick(50, 60, human=False)
    assert [c[0] for c in ctx.dm.calls] == ["move", "ldbl"]

    # 6. adb: 鸭子 keymouse → tap; 停顿=前摇真睡; 双击两 tap; 急点不吃前摇
    ctx = bind(backend="adb")
    t0 = time.monotonic()
    dsl.click(30, 40)
    (tap,) = ctx.device.taps
    assert abs(tap[0] - 30) <= 3 and abs(tap[1] - 40) <= 3
    assert time.monotonic() - t0 >= 0.05
    dsl.dblclick(30, 40)
    assert len(ctx.device.taps) == 3            # 前面 1 击 + 双击 2 击
    ctx.device.taps.clear()
    t0 = time.monotonic()
    dsl.click(30, 40, human=False)
    assert len(ctx.device.taps) == 1 and time.monotonic() - t0 < 0.05

    # 7. drag: window 按下→插值→抬起; adb swipe 直通
    ctx = bind()
    dsl.drag(0, 0, 100, 0, ms=120)
    seq = [c[0] for c in ctx.dm.calls]
    assert seq[0] == "move" and seq[1] == "ldown" and seq[-1] == "lup"
    assert ("move", 100, 0) in ctx.dm.calls
    ctx = bind(backend="adb")
    dsl.drag(10, 20, 30, 40, ms=250)
    assert ctx.device.swipes == [(10, 20, 30, 40, 250)]

    # 8. sleep 区间: (60,60) 实睡约 60ms, F9 可中断性由 stop.wait 保证
    ctx = bind()
    t0 = time.monotonic()
    dsl.sleep((60, 60))
    assert 0.05 <= time.monotonic() - t0 < 0.5

    # 9. find_tap 透传 verify
    ctx = bind()
    dsl.find_tap("x.png", verify="main.png")
    assert ctx.ops.kwargs["verify"] == "main.png"

    # 10. stopped() = ctx.stop.is_set() 的门面
    ctx = bind()
    assert dsl.stopped() is False
    ctx.stop.set()
    assert dsl.stopped() is True

    # 11. key: 组合键按下序 = 修饰逐个 down → 主键 press → 修饰逆序 up
    ctx = bind()
    dsl.key("ctrl+shift+s")
    assert ctx.dm.key_calls == [("down", "ctrl"), ("down", "shift"),
                                ("press", "s"), ("up", "shift"),
                                ("up", "ctrl")], ctx.dm.key_calls
    dsl.key("ENTER")                            # 大小写归一
    assert ctx.dm.key_calls[-1] == ("press", "enter")
    try:
        dsl.key("meta+x")
        raise AssertionError("非法修饰键应报错")
    except ValueError:
        pass

    # 12. key: adb 单键映射 keycode; 组合键/未收录键名报错
    ctx = bind(backend="adb")
    dsl.key("back")
    assert ctx.device.keys == [4]               # ADB_KEYS: back=4
    for bad in ("ctrl+s", "f13"):
        try:
            dsl.key(bad)
            raise AssertionError(f"{bad!r} 应报错")
        except ValueError:
            pass

    print("test_dsl_mouse: 全部通过")


if __name__ == "__main__":
    main()
