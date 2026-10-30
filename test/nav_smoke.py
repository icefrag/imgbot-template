# -*- coding: utf-8 -*-
"""Nav 接入冒烟(离线, 免窗口): 声明表 → build_nav 建图 → dsl.go/at 全链。

锚点名当"画面"(FakeOps 同 imgbot selfcheck 思路): state=当前屏, popups=屏上弹窗。
用法: uv run python test/nav_smoke.py
"""
import sys
import threading
import types
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from bot import backends, dsl   # noqa: E402


class FakeOps:
    def __init__(self):
        self.state, self.popups, self.tapped = "a_city", [], []

    @contextmanager
    def same_frame(self):
        yield self

    def exists(self, pic, region=None, threshold=None):
        return pic == self.state or pic in self.popups

    def wait_pic(self, pic, region=None, timeout=30, interval=0.4,
                 threshold=None, stop=None):
        return (0, 0, 1.0) if self.exists(pic) else None

    def probe(self, *pics, region=None, threshold=None):
        return next((p for p in pics if p in self.popups), None)

    def find_tap(self, pic, region=None, timeout=0, interval=0.4,
                 threshold=None, verify=None, stop=None):
        if pic in self.popups:                 # 弹窗: 点掉, 不换屏
            self.popups.remove(pic)
            self.tapped.append(pic)
            return True
        if pic in SCREEN_BTNS.get(self.state, ()):   # 当前屏的按钮: 点=换屏
            self.state = BTN_DST[pic]
            self.tapped.append(pic)
            return True
        return False

    def shot(self, tag=""):
        return Path("logs/shots") / f"{tag}.png"


# 假游戏的图: city -菜单-> menu -进-> dungeon, 弹窗 reward 任意屏可冒
BTN_DST = {"btn_menu": "a_menu", "btn_dg": "a_dg"}
SCREEN_BTNS = {"a_city": ["btn_menu"], "a_menu": ["btn_dg"]}
FAKE_TASK = types.ModuleType("task")
FAKE_TASK.NAV_SCREENS = {"city": "a_city", "menu": "a_menu",
                         "dungeon": ("a_dg", (0, 0, 300, 80))}
FAKE_TASK.NAV_EDGES = {("city", "menu"): "btn_menu",     # 模板边(找到就点)
                       ("menu", "dungeon"): "btn_dg"}
FAKE_TASK.NAV_INTERRUPTS = ["reward_ok.png"]


def main() -> int:
    fake = FakeOps()
    ctx = backends.Ctx("window", "fake", None,
                       lambda t, lv="info": print(f"[{lv}] {t}"),
                       threading.Event(), ops=fake)
    dsl._bind(ctx)
    ctx.nav = backends.build_nav(FAKE_TASK, ctx)
    assert ctx.nav is not None, "声明表在, nav 必须建出来"
    print("[1] build_nav OK(3 屏 2 边 1 弹窗, 模板边自动 find_tap)")

    assert dsl.at("city") and not dsl.at("dungeon")
    print("[2] dsl.at 期望验证 OK")

    fake.popups.append("reward_ok.png")          # 路上冒弹窗, 走边前应被轰掉
    assert dsl.go("dungeon") and fake.state == "a_dg" and fake.tapped
    print(f"[3] dsl.go BFS 带路 OK(点了 {fake.tapped}, 弹窗已轰)")

    fake.state = "a_city"                        # 崩溃重启=迷路, go 自动重定位
    ctx.nav._cur = None
    assert dsl.go("menu")
    print("[4] 迷路重定位自愈 OK")

    try:
        dsl.go("不存在屏")
        return 1
    except ValueError:
        print("[5] 未注册屏 ValueError OK")

    from imgbot.nav import LostError
    fake.state = "a_black"                       # 黑屏=全锚点不中
    ctx.nav._cur = None
    try:
        dsl.go("city")
        return 1
    except LostError:
        print("[6] 迷路抛 LostError OK(业务 on_fuse 接重登线)")

    print("nav 接入冒烟: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
