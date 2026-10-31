# -*- coding: utf-8 -*-
"""icefrag靶场: 纯 Win32 自绘小游戏靶(独立进程), 供 test_dsl_game.py 做图色 E2E。

为什么是裸 Win32 而不是 tkinter: tkinter 过滤 PostMessage 合成点击(README 靶子
适配真相), 裸 Win32 消息泵照单全收 → 键鼠可全后台(windows 通道)。
自绘 WM_PAINT 与 WM_PRINTCLIENT 共用同一画函数 → PrintWindow(gdi 通道)后台
截屏遮挡可用。布局坐标即测试契约(LAYOUT), 改布局 = 同步改 test_dsl_game.py。

屏幕: main(主界面) / arena(竞技场) / shop(商店), 切屏过 500ms 加载页。
元件: 金币×3(点击消失+10分) 双击宝箱(+50) 滑块(拖到最右+30) 悬停区(WM_MOUSEMOVE)
打字行(WM_CHAR) 怪物(竞技场, 点3次胜利+100) 灯(进场1.5s后亮, 点灭+20)。
分数全局累计, 顶行右侧大字(OCR 数字靶)。
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
# LPARAM 是无符号 64 位, 不声明会被当 32 位 int 转换而溢出(实测 DefWindowProcW 炸)
u32.DefWindowProcW.restype = ctypes.c_longlong
u32.DefWindowProcW.argtypes = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]

WM_DESTROY, WM_PAINT, WM_TIMER = 0x0002, 0x000F, 0x0113
WM_CHAR, WM_ERASEBKGND, WM_PRINTCLIENT = 0x0102, 0x0014, 0x0318
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_LBUTTONDBLCLK = 0x0203

# ---- 布局契约(client 640x480, 与 test_dsl_game.py 共享) ----
W, H = 640, 480
TITLE = (8, 6, 150, 46)                  # 屏名锚点(模板裁剪区)
SCORE = (500, 8, 632, 42)                # "得分 N"(OCR 数字靶)
COIN_Y, COIN_R = 90, 18
COIN_XS = [80, 140, 200]                 # 金币圆心
MONSTER = (350, 60, 430, 140)            # 竞技场怪物(红体黑眼黄嘴)
EYE, MOUTH = (365, 78, 383, 96), (372, 118, 404, 130)
LAMP_C, LAMP_R = (520, 100), 15          # 竞技场灯(进场 1.5s 后亮, 洋红)
HOVER = (480, 60, 620, 100)              # 悬停区(青)
BOX = (60, 180, 160, 260)                # 双击宝箱(紫)
TRACK = (60, 300, 360, 300)              # 滑轨, 手柄起点 x=70, 拖到 >=330 成
TYPED = (60, 340, 420, 374)              # "输入: ..." 行(WM_CHAR)
BTN = {"战斗": (440, 300, 540, 340), "商店": (440, 360, 540, 400),
       "返回": (440, 360, 540, 400)}
VICTORY = (230, 190, 410, 270)
LOADING_MS, LAMP_DELAY = 500, 1.5

C_WHITE, C_BLACK = 0xFFFFFF, 0x000000
C_COIN, C_BOX, C_HOVER = 0x00BEFF, 0xC83C96, 0xC8C800       # COLORREF(BGR)
C_MON, C_EYE, C_MOUTH = 0x2828C8, 0x141414, 0x00DCFF
C_LAMP, C_GRAY = 0xFF00FF, 0xAAAAAA

st = {"screen": "main", "loading_until": 0.0, "next": None, "arena_at": 0.0,
      "score": 0, "coins": list(COIN_XS), "box_open": False, "hover": False,
      "slider_x": 70, "grab": False, "drag_ok": False, "typed": "",
      "hp": 3, "lamp_on": False, "lamp_off": False, "last_box_click": 0.0}


def _rect(hdc, x1, y1, x2, y2, color):
    br = gdi32.CreateSolidBrush(color)
    op = gdi32.SelectObject(hdc, br)
    p = gdi32.CreatePen(0, 1, color)                      # PS_NULL 边框
    op2 = gdi32.SelectObject(hdc, p)
    gdi32.Rectangle(hdc, x1, y1, x2, y2)
    gdi32.SelectObject(hdc, op2), gdi32.DeleteObject(p)
    gdi32.SelectObject(hdc, op), gdi32.DeleteObject(br)


def _text(hdc, s, x1, y1, x2, y2, h=26, color=C_BLACK, bold=False):
    f = gdi32.CreateFontW(h, 0, 0, 0, 700 if bold else 400, 0, 0, 0,
                          1, 0, 0, 0, 0, "微软雅黑")      # DEFAULT_CHARSET
    op = gdi32.SelectObject(hdc, f)
    gdi32.SetTextColor(hdc, color), gdi32.SetBkMode(hdc, 1)   # TRANSPARENT
    r = wt.RECT(x1, y1, x2, y2)
    u32.DrawTextW(hdc, s, -1, ctypes.byref(r), 0x25)      # DT_SINGLELINE|CENTER|VCENTER
    gdi32.SelectObject(hdc, op), gdi32.DeleteObject(f)


def _coin(hdc, cx):
    br = gdi32.CreateSolidBrush(C_COIN)
    op = gdi32.SelectObject(hdc, br)
    gdi32.Ellipse(hdc, cx - COIN_R, COIN_Y - COIN_R, cx + COIN_R, COIN_Y + COIN_R)
    gdi32.SelectObject(hdc, op), gdi32.DeleteObject(br)


def draw(hdc):
    """WM_PAINT 与 WM_PRINTCLIENT 共用 → 前台/后台截屏同画面。"""
    _rect(hdc, 0, 0, W, H, C_WHITE)
    if time.time() < st["loading_until"]:                 # 加载页盖全屏
        _rect(hdc, 0, 0, W, H, C_GRAY)
        _text(hdc, "加载中", 250, 200, 390, 250, 32, bold=True)
        return
    name = {"main": "主界面", "arena": "竞技场", "shop": "商店"}[st["screen"]]
    _text(hdc, name, *TITLE, 28, bold=True)               # 屏名锚点
    _text(hdc, f"得分 {st['score']}", *SCORE, 24, bold=True)
    if st["screen"] == "main":
        for cx in st["coins"]:
            _coin(hdc, cx)
        if not st["box_open"]:
            _rect(hdc, *BOX, C_BOX)
            _text(hdc, "双击", BOX[0], BOX[1], BOX[2], BOX[3], 22)
        _rect(hdc, *HOVER, C_HOVER)
        _text(hdc, "悬停区", HOVER[0], HOVER[1], HOVER[2], HOVER[3], 18)
        if st["hover"]:
            _text(hdc, "悬停OK", HOVER[0], HOVER[3] + 4, HOVER[2], HOVER[3] + 34, 20)
        _rect(hdc, TRACK[0], TRACK[1] - 3, TRACK[2], TRACK[1] + 3, C_GRAY)
        _rect(hdc, st["slider_x"] - 8, 285, st["slider_x"] + 8, 315, C_BLACK)
        _text(hdc, "拖到最右", 60, 320, 200, 340, 14)
        if st["drag_ok"]:
            _text(hdc, "拖动OK", 400, 285, 500, 315, 22, 0x008000 | 0x0000)
        _text(hdc, f"输入:{st['typed']}", *TYPED, 22)
        for label in ("战斗", "商店"):
            x1, y1, x2, y2 = BTN[label]
            _rect(hdc, x1, y1, x2, y2, 0xE8E8E8)
            gdi32.Rectangle(hdc, x1, y1, x2, y2)
            _text(hdc, label, x1, y1, x2, y2, 22)
    elif st["screen"] == "arena":
        _rect(hdc, *MONSTER, C_MON)
        _rect(hdc, *EYE, C_EYE)
        _rect(hdc, *MOUTH, C_MOUTH)
        if st["lamp_on"]:
            br = gdi32.CreateSolidBrush(C_LAMP)
            op = gdi32.SelectObject(hdc, br)
            gdi32.Ellipse(hdc, LAMP_C[0] - LAMP_R, LAMP_C[1] - LAMP_R,
                          LAMP_C[0] + LAMP_R, LAMP_C[1] + LAMP_R)
            gdi32.SelectObject(hdc, op), gdi32.DeleteObject(br)
        if st["hp"] <= 0:
            _text(hdc, "胜利", *VICTORY, 48, 0x0000C0, bold=True)
    else:                                                  # shop
        _text(hdc, "金币兑换(装饰)", 100, 150, 400, 190, 22)
    if st["screen"] in ("arena", "shop"):
        x1, y1, x2, y2 = BTN["返回"]
        _rect(hdc, x1, y1, x2, y2, 0xE8E8E8)
        gdi32.Rectangle(hdc, x1, y1, x2, y2)
        _text(hdc, "返回", x1, y1, x2, y2, 22)


def _in(x, y, r):
    return r[0] <= x < r[2] and r[1] <= y < r[3]


def _click(x, y, double=False):
    if time.time() < st["loading_until"]:
        return
    sc = st["screen"]
    if sc == "main":
        for cx in st["coins"]:
            if (x - cx) ** 2 + (y - COIN_Y) ** 2 <= (COIN_R + 6) ** 2:
                st["coins"].remove(cx), st.update(score=st["score"] + 10)
                return
        if _in(x, y, BOX) and (double or
                               time.time() - st["last_box_click"] < 0.4):
            st["box_open"] = True
            st["score"] += 50
        elif _in(x, y, BOX):
            st["last_box_click"] = time.time()
        for label in ("战斗", "商店"):
            if _in(x, y, BTN[label]):
                st.update(loading_until=time.time() + LOADING_MS / 1000,
                          next="arena" if label == "战斗" else "shop")
    elif sc == "arena":
        if _in(x, y, MONSTER) and st["hp"] > 0:
            st["hp"] -= 1
            if st["hp"] == 0:
                st["score"] += 100
        elif st["lamp_on"] and (x - LAMP_C[0]) ** 2 + (y - LAMP_C[1]) ** 2 \
                <= (LAMP_R + 8) ** 2:
            st["lamp_on"] = False
            st["lamp_off"] = True                  # 点灭后不再自动复亮
            st["score"] += 20
        if _in(x, y, BTN["返回"]):
            st.update(loading_until=time.time() + LOADING_MS / 1000, next="main")
    elif _in(x, y, BTN["返回"]):
        st.update(loading_until=time.time() + LOADING_MS / 1000, next="main")


def _move(x, y):
    st["hover"] = st["screen"] == "main" and _in(x, y, HOVER)
    if st["grab"]:
        st["slider_x"] = max(TRACK[0] + 10, min(TRACK[2] - 10, x))


def _up(x, y):
    if st["grab"]:
        st["grab"] = False
        if st["slider_x"] >= TRACK[2] - 30 and not st["drag_ok"]:
            st["drag_ok"] = True
            st["score"] += 30


def _tick():
    if st["next"] and time.time() >= st["loading_until"]:
        nxt = st["next"]
        st.update(next=None, screen=nxt)
        if nxt == "arena":
            st.update(arena_at=time.time(), hp=3, lamp_on=False, lamp_off=False)
    if st["screen"] == "arena" and not st["lamp_off"] and not st["lamp_on"] \
            and st["hp"] > 0 and time.time() - st["arena_at"] >= LAMP_DELAY:
        st["lamp_on"] = True


def wndproc(hwnd, msg, wp, lp):
    if msg == WM_PAINT:
        ps = PAINTSTRUCT()
        hdc = u32.BeginPaint(hwnd, ctypes.byref(ps))
        draw(hdc)
        u32.EndPaint(hwnd, ctypes.byref(ps))
        return 0
    if msg == WM_PRINTCLIENT:                             # PrintWindow 后台截屏入口
        draw(wp)
        return 0
    if msg == WM_ERASEBKGND:
        return 1
    if msg == WM_TIMER:
        _tick(), u32.InvalidateRect(hwnd, None, False)
        return 0
    if msg == WM_MOUSEMOVE:
        _move(lp & 0xFFFF, (lp >> 16) & 0xFFFF)
        u32.InvalidateRect(hwnd, None, False)
        return 0
    if msg == WM_LBUTTONDOWN:
        x, y = lp & 0xFFFF, (lp >> 16) & 0xFFFF
        if st["screen"] == "main" and abs(x - st["slider_x"]) <= 12 \
                and 285 <= y <= 315:
            st["grab"] = True
        _click(x, y)
        u32.InvalidateRect(hwnd, None, False)
        return 0
    if msg == WM_LBUTTONUP:
        _up(lp & 0xFFFF, (lp >> 16) & 0xFFFF)
        u32.InvalidateRect(hwnd, None, False)
        return 0
    if msg == WM_LBUTTONDBLCLK:
        _click(lp & 0xFFFF, (lp >> 16) & 0xFFFF, double=True)
        u32.InvalidateRect(hwnd, None, False)
        return 0
    if msg == WM_CHAR:
        ch = chr(wp)
        if ch.isprintable() and len(st["typed"]) < 12:
            st["typed"] += ch
            u32.InvalidateRect(hwnd, None, False)
        return 0
    if msg == WM_DESTROY:
        u32.PostQuitMessage(0)
        return 0
    return u32.DefWindowProcW(hwnd, msg, wp, lp)


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", ctypes.c_void_p), ("fErase", ctypes.c_int),
                ("rcPaint", wt.RECT), ("fRestore", ctypes.c_int),
                ("fIncUpdate", ctypes.c_int),
                ("rgbReserved", ctypes.c_byte * 32)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wt.HWND, ctypes.c_uint,
                             wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p)]


def main():
    u32.SetProcessDPIAware()
    cls = WNDCLASSW()
    cls.lpfnWndProc = _wndproc
    cls.lpszClassName = "IcefragRange"
    cls.hCursor = u32.LoadCursorW(0, 32512)
    cls.hIcon = u32.LoadIconW(0, 32512)
    if not u32.RegisterClassW(ctypes.byref(cls)):
        sys.exit("RegisterClass 失败")
    rect = wt.RECT(0, 0, W, H)
    u32.AdjustWindowRect(ctypes.byref(rect), 0x00CA0000, False)  # WS_OVERLAPPEDWINDOW
    hwnd = u32.CreateWindowExW(0, "IcefragRange", "icefrag靶场v1",
                               0x00CA0000, 50, 50,
                               rect.right - rect.left, rect.bottom - rect.top,
                               0, 0, 0, 0)
    u32.ShowWindow(hwnd, 5)                               # SW_SHOW
    u32.UpdateWindow(hwnd)
    u32.SetTimer(hwnd, 1, 100, None)
    msg = wt.MSG()
    while u32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
        u32.TranslateMessage(ctypes.byref(msg))
        u32.DispatchMessageW(ctypes.byref(msg))
    return 0


_wndproc = WNDPROC(wndproc)           # 保活: 回调对象必须持引用

if __name__ == "__main__":
    sys.exit(main())
