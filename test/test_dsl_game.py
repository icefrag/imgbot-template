# -*- coding: utf-8 -*-
"""DSL 全动词 E2E 回归: icefrag靶场(test/dummy_game.py, 纯 Win32 靶) + gdi/windows/windows
全后台通道(截屏/键鼠都不动真桌面, 可遮挡跑)。

跑法:
  uv run test/test_dsl_game.py               # 全量(约 1 分钟)
  uv run test/test_dsl_game.py find_tap nav  # 只跑名字含子串的用例(回归定位用)

模板不入库: 每轮 setup 从靶子实况截图自裁(同源裁材, 免 DPI/字体差异)。
key() 不在本集: windows 键盘通道是引擎历史死案(KeyPress 抛
NotImplementedError), dsl.key 的组织逻辑在 test/test_dsl_mouse.py 离线覆盖。

用例 → 动词映射(改哪个动词就跑哪条):
  00_smoke        sleep/stopped/log/shot/progress + 绑定 sanity
  01_click        click(坐标+参数)
  02_dblclick     dblclick + ocr_numbers(分数差)
  03_drag         drag(滑块拖到最右)
  04_move         move(悬停区)
  05_find_color   find_color(金币色, 区域限定)
  06_find_all     find_all + tap_until_gone + exists
  07_find_tap     find_tap 单帧
  08_find_tap_ver find_tap verify 正/负
  09_wait_pic     wait_pic + wait_pic_gone(切屏过场)
  10_ocr          ocr(屏名)
  11_nav          go/at(三屏导航图, BFS 两跳)
  12_multi_color  find_multi_color(怪物) + click 连点 + wait_pic_any(胜利)
  13_lamp_color   wait_color/wait_color_gone(竞技场灯) + ocr_numbers 差
  14_background   后台证明(纯蓝盖子遮死游戏: 截屏仍见游戏+遮挡点击切屏)
  15_type_text    type_text(打字行 WM_CHAR 直投 + OCR 回读; 不经 KeyPress 死案)
"""
import subprocess
import sys
import threading
import time
import traceback
import types
from pathlib import Path

import ctypes
import ctypes.wintypes as wt
import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from dummy_game import PAINTSTRUCT, WNDCLASSW, WNDPROC   # 复用靶子的 Win32 手写类型
from icefrag import dsl                                       # noqa: E402
from icefrag import ROOT                                      # noqa: E402
from icefrag.backends import build_nav, bind_window_backend, unbind  # noqa: E402
from icefrag.settings import ScaffoldConfig                   # noqa: E402
from imgbot.vision import Pt                                  # noqa: E402

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# 靶子布局契约(与 dummy_game.py 对齐, 改布局两边同步)
TITLE, SCORE = (8, 6, 150, 46), (500, 8, 632, 42)
COIN_Y, COIN_XS = 90, [80, 140, 200]
MONSTER = (350, 60, 430, 140)
LAMP_BOX = (490, 70, 550, 130)
BOX_C, TIP = (110, 220), (480, 104, 620, 136)
DRAG_OK = (390, 280, 510, 320)
TYPED = (60, 340, 420, 374)               # 打字行(WM_CHAR 显示区)
BTN_BATTLE, BTN_SHOP = (490, 320), (490, 380)
MON_PTS = None                      # setup 从实况像素采样
TG = ROOT / "templates" / "test_game"

proc, ctx = None, None
LOGS = []
CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def frame():
    return ctx.dm._screen()


def save_tpl(name, img):
    ok, buf = cv2.imencode(".png", img)
    assert ok, f"模板编码失败: {name}"
    (TG / name).write_bytes(buf.tobytes())


def crop(img, x1, y1, x2, y2):
    return img[y1:y2, x1:x2]


def wait_screen(name, timeout=6.0):
    assert dsl.wait_pic(f"test_game/anchor_{name}.png", timeout=int(timeout * 1000)), \
        f"没等到 {name} 屏"


def to_main():
    for _ in range(3):
        if dsl.exists("test_game/anchor_main.png"):
            return
        dsl.find_tap("test_game/btn_back.png", timeout=4000)
    assert dsl.exists("test_game/anchor_main.png"), "回不到主界面"


def sample_pts(fa):
    """怪物多点找色 Pt 表: 锚红/黑眼/黄嘴, 从实况像素采样(容差留给抗锯齿)。"""
    a = tuple(int(v) for v in fa[70, 400])          # 锚点(400,70) 怪物红体
    e = tuple(int(v) for v in fa[87, 374])          # 眼心(374,87) 黑
    m = tuple(int(v) for v in fa[124, 388])         # 嘴心(388,124) 黄
    return [Pt(0, 0, a, 30), Pt(-26, 17, e, 40), Pt(-12, 54, m, 40)]


def _wait_pixel(box, bgr, tol=60, timeout=6.0):
    """裸像素等待(setup 专用: 锚点模板还没裁出来时, 用特征色判到位)。"""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        reg = crop(frame(), *box).astype(int)
        if ((abs(reg[:, :, 0] - bgr[0]) <= tol) & (abs(reg[:, :, 1] - bgr[1]) <= tol)
                & (abs(reg[:, :, 2] - bgr[2]) <= tol)).any():
            return True
        time.sleep(0.2)
    return False


def gen_templates():
    """同源裁材: 亲临三屏各裁一遍(顺带打出胜利局裁结算模板)。"""
    f = frame()
    save_tpl("anchor_main.png", crop(f, *TITLE))
    save_tpl("coin.png", crop(f, 60, 70, 100, 110))
    save_tpl("box.png", crop(f, 60, 180, 160, 260))
    save_tpl("btn_battle.png", crop(f, 440, 300, 540, 340))
    save_tpl("btn_shop.png", crop(f, 440, 360, 540, 400))
    dsl.click(*BTN_BATTLE, jitter=0, settle=50)     # 进战斗(加载页 500ms)
    time.sleep(0.15)
    save_tpl("loading.png", crop(frame(), 250, 200, 390, 250))
    assert _wait_pixel(MONSTER, (40, 40, 200)), "没等到竞技场(怪物红没出现)"
    fa = frame()
    save_tpl("anchor_arena.png", crop(fa, *TITLE))
    save_tpl("btn_back.png", crop(fa, 440, 360, 540, 400))
    global MON_PTS
    MON_PTS = sample_pts(fa)
    for _ in range(3):                              # 打出胜利局裁结算模板
        dsl.click(390, 100, jitter=0, settle=50)
        time.sleep(0.25)
    save_tpl("victory.png", crop(frame(), 230, 190, 410, 270))
    to_main()
    dsl.click(*BTN_SHOP, jitter=0, settle=50)
    time.sleep(1.2)                                 # 过 500ms 加载页后裁商店锚点
    save_tpl("anchor_shop.png", crop(frame(), *TITLE))
    to_main()


def setup():
    global proc, ctx
    u32 = ctypes.windll.user32
    proc = subprocess.Popen([sys.executable, str(HERE / "dummy_game.py")],
                            cwd=str(HERE))
    hwnd = 0
    for _ in range(50):
        time.sleep(0.2)
        hwnd = u32.FindWindowW("IcefragRange", None)
        if hwnd:
            break
    assert hwnd, "游戏窗口 10s 没出现"
    time.sleep(0.7)                                 # 等首帧
    scaffold = ScaffoldConfig(display="gdi", mouse="windows", keypad="windows")
    stop = threading.Event()

    def log_rec(text, level="info"):
        LOGS.append((text, level))

    ctx = bind_window_backend(hwnd, scaffold,
                              types.SimpleNamespace(target_text=""), log_rec, stop)
    dsl._bind(ctx)
    TG.mkdir(parents=True, exist_ok=True)
    gen_templates()


def teardown():
    global proc
    if ctx is not None:
        try:
            unbind(ctx)
        except Exception:
            pass
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(5)
        except Exception:
            proc.kill()


# ==================== 用例 ====================
@case
def c00_smoke():
    """绑定 sanity + sleep/stopped/log/shot/progress。"""
    f = frame()
    assert f.shape[:2] == (480, 640), f"客户区应 640x480, 实际 {f.shape}"
    t0 = time.monotonic()
    dsl.sleep(150)
    assert 0.1 <= time.monotonic() - t0 < 1.0, "sleep 时长不对"
    assert dsl.stopped() is False
    ctx.stop.set()
    assert dsl.stopped() is True
    ctx.stop.clear()
    dsl.log("靶场冒烟", "warn")
    assert any("靶场冒烟" in t and lv == "warn" for t, lv in LOGS), "log 没落到记录器"
    p = dsl.shot("靶场冒烟")
    assert p and p.exists() and p.stat().st_size > 0, "shot 没落盘"
    dsl.progress()                                  # 无异常即过


@case
def c01_click():
    dsl.click(*BTN_BATTLE, jitter=0, settle=80)     # 拟人轨迹急停顿点按钮
    wait_screen("arena")
    to_main()


@case
def c02_dblclick():
    s0 = dsl.ocr_numbers(region=SCORE)
    assert s0, "分数没读到"
    dsl.dblclick(*BOX_C, jitter=0)
    assert dsl.wait_pic_gone("test_game/box.png", timeout=4000), "双击后宝箱没消失"
    s1 = dsl.ocr_numbers(region=SCORE)
    assert s1 == [s0[0] + 50], f"双击得分差应为 50: {s0} → {s1}"


@case
def c03_drag():
    dsl.drag(78, 300, 345, 300, ms=400)             # 手柄(70±8,300)拖到轨道右端
    time.sleep(0.4)                                 # 等"拖动OK"绿字重绘
    reg = crop(frame(), *DRAG_OK)
    assert ((reg[:, :, 1] > 90) & (reg[:, :, 0] < 90) & (reg[:, :, 2] < 90)).any(), \
        "拖到最右后没出现绿字拖动OK"


@case
def c04_move():
    dsl.move(550, 80)                               # 悬停区内
    time.sleep(0.4)
    tip = crop(frame(), *TIP)
    assert (tip.max(axis=2) < 120).any(), "悬停后没出现提示字"


@case
def c05_find_color():
    hits = dsl.find_color("FFBE00", region=(40, 60, 240, 120))
    xs = {min(COIN_XS, key=lambda cx: abs(cx - x)) for x, _y in hits}
    assert xs == set(COIN_XS), f"三枚金币应各有命中: {xs}"


@case
def c06_find_all_tap_until_gone():
    hits = dsl.find_all("test_game/coin.png")
    assert len(hits) == 3, f"应有 3 枚金币, 实得 {len(hits)}"
    n = dsl.tap_until_gone("test_game/coin.png", timeout=10000)
    assert n == 3, f"连点数应为 3, 实得 {n}"
    assert not dsl.exists("test_game/coin.png"), "金币应已点光"


@case
def c07_find_tap():
    assert dsl.find_tap("test_game/btn_battle.png")
    wait_screen("arena")
    to_main()


@case
def c08_find_tap_verify():
    assert dsl.find_tap("test_game/btn_shop.png", verify="test_game/anchor_shop.png"), \
        "verify 正例应成功(点了到商店, 锚点出现)"
    to_main()
    assert not dsl.find_tap("test_game/btn_battle.png",
                            verify="test_game/victory.png"), \
        "verify 负例应失败(到竞技场但胜利永不出现)"
    to_main()


@case
def c09_wait_pic():
    dsl.click(*BTN_BATTLE, jitter=0, settle=50)
    assert dsl.wait_pic_gone("test_game/loading.png", timeout=4000), "加载页该消失"
    hit = dsl.wait_pic("test_game/anchor_arena.png", timeout=5000)
    assert hit and TITLE[0] <= hit[0] <= TITLE[2] and TITLE[1] <= hit[1] <= TITLE[3], \
        f"竞技场锚点中心应在标题区: {hit}"
    to_main()


@case
def c10_ocr():
    text = dsl.ocr(region=TITLE)
    assert "主界面" in text, f"屏名应含『主界面』, 读到 {text!r}"
    assert "竞技" in dsl.ocr(region=TITLE) or True   # 占位: 换屏读屏名在 c11 校


def ensure_nav():
    """c11/c12/c13 共用导航图; 各自调用自备前置(按名单跑时不依赖别案)。"""
    if ctx.nav is not None:
        return
    mod = types.SimpleNamespace(
        NAV_SCREENS={"main": "test_game/anchor_main.png",
                     "arena": "test_game/anchor_arena.png",
                     "shop": "test_game/anchor_shop.png"},
        NAV_EDGES={("main", "arena"): "test_game/btn_battle.png",
                   ("arena", "main"): "test_game/btn_back.png",
                   ("main", "shop"): "test_game/btn_shop.png",
                   ("shop", "main"): "test_game/btn_back.png"},
        NAV_INTERRUPTS=[])
    ctx.nav = build_nav(mod, ctx)


@case
def c11_nav():
    ensure_nav()
    assert dsl.at("main")
    assert dsl.go("arena", timeout=20000), "go arena 失败"
    assert dsl.at("arena")
    assert "竞技" in dsl.ocr(region=TITLE), "竞技场屏名 OCR"
    assert dsl.go("shop", timeout=20000), "go shop 失败(两跳: arena→main→shop)"
    assert dsl.at("shop")
    assert dsl.go("main", timeout=20000)
    assert dsl.at("main")


@case
def c12_multi_color_victory():
    ensure_nav()
    assert dsl.go("arena", timeout=20000)
    hit = dsl.find_multi_color((340, 50, 440, 150), MON_PTS)
    assert hit and MONSTER[0] <= hit[0] <= MONSTER[2] \
        and MONSTER[1] <= hit[1] <= MONSTER[3], f"多点找色应命中怪物: {hit}"
    assert dsl.find_multi_color((0, 150, 300, 480), MON_PTS) is None, \
        "空区域不应命中"
    for _ in range(3):                              # 连点 3 次击杀
        dsl.click(*hit, jitter=0, settle=60)
        time.sleep(0.3)
    got = dsl.wait_pic_any(["test_game/victory.png"], timeout=5000)
    assert got and got[0] == "test_game/victory.png", f"胜利结算: {got}"


@case
def c13_lamp_color():
    ensure_nav()
    dsl.go("main", timeout=20000)
    assert dsl.go("arena", timeout=20000)           # 重新进场: hp 重置, 灯 1.5s 后亮
    hit = dsl.wait_color("FF00FF", region=LAMP_BOX, timeout=6000)
    assert hit, "灯该在进场 1.5s 后亮"
    s0 = dsl.ocr_numbers(region=SCORE)
    dsl.click(*hit, jitter=0, settle=60)            # 点灯
    assert dsl.wait_color_gone("FF00FF", region=LAMP_BOX, timeout=4000), "灯该熄"
    s1 = dsl.ocr_numbers(region=SCORE)
    assert s1 == [s0[0] + 20], f"点灯得分差应为 20: {s0} → {s1}"


# ==================== 遮挡后台证明 ====================
COVER_CLS = "IcefragCover"


def _pump(ms):
    """泵消息 ms 毫秒(让盖子窗口完成绘制)。"""
    msg = wt.MSG()
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        while u32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.02)


def _cover_wndproc(hwnd, msg, wp, lp):
    if msg == 0x000F:                               # WM_PAINT: 整面纯蓝
        ps = PAINTSTRUCT()
        hdc = u32.BeginPaint(hwnd, ctypes.byref(ps))
        r = wt.RECT(0, 0, 9999, 9999)
        br = gdi32.CreateSolidBrush(0xFF0000)       # RGB(0,0,255) 纯蓝
        u32.FillRect(hdc, ctypes.byref(r), br)      # FillRect 在 user32
        gdi32.DeleteObject(br)
        u32.EndPaint(hwnd, ctypes.byref(ps))
        return 0
    if msg == 0x0002:
        return 0
    return u32.DefWindowProcW(hwnd, msg, wp, lp)


_cover_cb = None


def _cover_game():
    """纯蓝置顶窗口精确盖住游戏(证明截屏不是抓屏)。返回 hwnd。"""
    global _cover_cb
    game = u32.FindWindowW("IcefragRange", None)
    assert game, "游戏窗口不在"
    r = wt.RECT()
    u32.GetWindowRect(game, ctypes.byref(r))
    cls = WNDCLASSW()
    _cover_cb = WNDPROC(_cover_wndproc)
    cls.lpfnWndProc = _cover_cb
    cls.lpszClassName = COVER_CLS
    cls.hCursor = u32.LoadCursorW(0, 32512)
    u32.RegisterClassW(ctypes.byref(cls))
    hwnd = u32.CreateWindowExW(0x8, COVER_CLS, "cover", 0x80000000,  # TOPMOST/POPUP
                               r.left, r.top, r.right - r.left, r.bottom - r.top,
                               0, 0, 0, 0)
    u32.ShowWindow(hwnd, 5)
    _pump(0.4)                                      # 等盖子画完蓝
    return hwnd


@case
def c14_background_covered():
    """后台证明: 游戏被纯蓝盖子完全盖住, 截屏仍是游戏画面, 点击照样切屏。"""
    to_main()
    cover = _cover_game()
    try:
        f = frame()                                 # 此刻屏幕上游戏位置=纯蓝
        blue = ((f[:, :, 0].astype(int) > 240) & (f[:, :, 1] < 15)
                & (f[:, :, 2] < 15)).sum()
        assert blue == 0, f"截屏混入盖子蓝 {blue} 像素 —— 不是真后台截屏!"
        assert dsl.exists("test_game/btn_battle.png"), "遮挡下模板匹配失效"
        dsl.click(*BTN_BATTLE, jitter=0, settle=60)  # 遮挡下点击切屏
        assert dsl.wait_pic("test_game/anchor_arena.png", timeout=6000), \
            "遮挡下点击没生效"
    finally:
        u32.DestroyWindow(cover)
        _pump(0.1)
    to_main()


@case
def c15_type_text():
    """type_text: windows 键盘通道 KeyPress 虽是引擎死案, 打字走 keymouse
    直投 WM_CHAR 不经该路径 —— 靶子打字行收字重绘, OCR 回读验证。
    (不用 wait_text: 打字行整行一个 token, 2 字短词比例匹配命中不了)"""
    to_main()
    dsl.type_text("你好挂机")
    got, end = "", time.monotonic() + 8.0            # 收字重绘+OCR 抖动留余量
    while time.monotonic() < end:
        got = dsl.ocr(region=TYPED)
        if "你好挂机" in got:
            break
        time.sleep(0.3)
    assert "你好挂机" in got, f"打字行没读到: {got!r}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    fails = []
    try:
        setup()
        for fn in CASES:
            if args and not any(a in fn.__name__ for a in args):
                continue
            t0 = time.monotonic()
            try:
                fn()
                print(f"[PASS] {fn.__name__} ({time.monotonic() - t0:.1f}s)")
            except Exception:
                print(f"[FAIL] {fn.__name__}")
                traceback.print_exc()
                fails.append(fn.__name__)
                try:
                    to_main()
                except Exception:
                    pass
    finally:
        teardown()
    n_ran = sum(1 for f in CASES if not args or any(a in f.__name__ for a in args))
    print(f"\n{len(CASES)} 用例, 跑 {n_ran}, 挂 {len(fails)}: {fails or '无'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
