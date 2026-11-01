# -*- coding: utf-8 -*-
"""绑定后开关组织层自检(离线, 假件): dx 缺席警告跳过 / 在场按序调用 / 全关零开销。
跑法: uv run test/test_bind_switches.py
"""
from types import SimpleNamespace

from icefrag.backends import _apply_dx_switches


class FakeDx:
    def __init__(self):
        self.calls = []

    def hook_keystate(self):
        self.calls.append("hook")

    def hide_module(self):
        self.calls.append("hide")


class FakeDm:
    def __init__(self, dx):
        self._dx = dx
        self.calls = []

    def EnableFakeActive(self, enable):
        self.calls.append(("fake", enable))


def run(scaffold, dm):
    msgs = []
    _apply_dx_switches(dm, scaffold, lambda m, k="info": msgs.append((k, m)))
    return msgs


def main():
    # 1. 开了开关但注入件不在场 → 一条 warn, 全跳过, 不碰 dm
    dm = FakeDm(None)
    msgs = run(SimpleNamespace(fake_active=True, hook_keystate=False,
                               hide_module=True), dm)
    assert dm.calls == [], dm.calls
    assert msgs and msgs[0][0] == "warn" and "跳过" in msgs[0][1], msgs

    # 2. 注入件在场 → 假激活(1)/键钩按开关调, 没开的不调
    dx = FakeDx()
    dm = FakeDm(dx)
    msgs = run(SimpleNamespace(fake_active=True, hook_keystate=True,
                               hide_module=False), dm)
    assert dm.calls == [("fake", 1)], dm.calls
    assert dx.calls == ["hook"], dx.calls
    assert msgs == [], msgs

    # 3. 开关全关 → 零调用零日志(默认路径零行为变化)
    dm = FakeDm(None)
    assert run(SimpleNamespace(fake_active=False, hook_keystate=False,
                               hide_module=False), dm) == []
    assert dm.calls == []

    print("test_bind_switches: 3 组全过")


if __name__ == "__main__":
    main()
