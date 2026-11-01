# -*- coding: utf-8 -*-
"""中控台(ttkbootstrap): 左=目标表格+启停按钮, 右=日志面板(按窗口着色)。

尺寸/比例/主题 = 脚手架层 [ui] 配置, root.resizable(False,False) 用户锁死。
设置弹窗两 Tab: 脚手架(固定 schema) / 业务(读 business.FIELD_META 自动生成)。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import simpledialog
import ttkbootstrap as ttk   # 控件全走 ttkbootstrap(bootstyle 才有效)
import winsound

from . import ROOT
from . import backends
from . import settings
from .hotkeys import HotkeyListener, hotkey_choices, hotkey_label, hotkey_vk
from .worker import Worker

_LOG_COLORS = {"info": "#d0d0d0", "warn": "#e6b84c", "error": "#e05c5c"}
_ROW_TAGS = {"running": "green", "error": "red", "done": "blue", "idle": "gray"}
_ALIAS_PATH = ROOT / "aliases.json"

# 绑定项悬浮讲解(? 卡片): 通道=取值三列表(values), 开关=症状处方(lines);
# 与 docs/icefrag开发手册.md 通道章同源, 改动两边同步
_BIND_HELP = {
    "display": ("图色通道 —— 截图从哪来", [
        ("normal", "前台截屏裁剪", "目标必须前台可见"),
        ("gdi", "PrintWindow 后台截图", "默认首选, GDI 窗口通吃"),
        ("gdi2", "兼容模式, 慢但稳", "gdi 截图不刷新时换它"),
        ("dx", "注入件截帧(OpenGL 已通)", "GDI 截不到的游戏; D3D9 调试中, 不通会明确报错"),
    ], None),
    "mouse": ("鼠标通道 —— 点击怎么发出去", [
        ("windows", "宿主侧 PostMessage", "门槛低, 普通窗口首选"),
        ("dx", "注入件进程内合成", "消息要过游戏输入检查的目标"),
        ("windows2", "dx 消息 + 虚拟光标锁", "点击总落到真鼠标处/偏移"),
        ("normal", "SendInput 真事件", "最后手段, 动真光标且须前台"),
    ], None),
    "keypad": ("键盘通道 —— 按键怎么发出去", [
        ("windows", "PostMessage 消息键盘(带扫描码)", "默认首选; 轮询型游戏免疫→换 dx"),
        ("dx", "注入件合成", "配合键状态钩子治无反应"),
        ("normal", "SendInput 真事件", "最后手段, 动真键盘"),
    ], None),
    "fake_active": ("后台假激活 —— 治什么病", None, [
        ("说明", "让后台窗口被游戏视为激活, 绕过点击处理里的激活门槛"),
        ("症状", "移动/键盘都正常, 唯独点击全无反应"),
        ("要求", "任一 dx 系通道(注入件在场)才生效, 否则跳过并留日志"),
    ]),
    "hook_keystate": ("键状态钩子 —— 治什么病", None, [
        ("说明", "钩住 GetAsyncKeyState。游戏靠轮询按键状态、不收消息时才需要"),
        ("症状", "键盘消息全无反应(连键都打不出)"),
        ("要求", "键盘通道选 dx(注入件在场), 否则跳过并留日志"),
    ]),
    "hide_module": ("隐藏模块 —— 治什么病", None, [
        ("说明", "把注入件从目标进程的模块列表里藏起来"),
        ("场景", "反作弊扫进程模块列表时; 绑定后调一次即可"),
        ("要求", "需 dx 系通道(注入件在场), 否则跳过并留日志"),
        ("平时", "保持「否」"),
    ]),
}

# 经典组合: 症状 → 配方(设置弹窗一键套用; 顺序=伤害递增, 能用上面的别用下面的)
_CLASSIC_COMBOS = [
    ("起步首选 · 普通窗口后台挂机",
     {"display": "gdi", "mouse": "windows", "keypad": "windows"}),
    ("移动/键盘正常, 唯独点击全无反应",
     {"display": "gdi", "mouse": "dx", "keypad": "windows", "fake_active": True}),
    ("键盘消息全无反应(消息免疫)",
     {"display": "gdi", "mouse": "dx", "keypad": "dx", "hook_keystate": True}),
    ("点击坐标总落到真鼠标处/偏移",
     {"display": "gdi", "mouse": "windows2", "keypad": "windows"}),
    ("GDI 截图黑屏/冻结(D3D/GL 游戏)",
     {"display": "dx", "mouse": "dx", "keypad": "windows"}),
]

_SWITCH_NAMES = {"fake_active": "假激活", "hook_keystate": "键状态钩子"}


def _combo_recipe(combo: dict) -> str:
    """组合的配方串: 通道三件套 + 点名的开关。"""
    parts = [combo["display"], combo["mouse"], combo["keypad"]]
    parts += [n for k, n in _SWITCH_NAMES.items() if combo.get(k)]
    return " · ".join(parts)


class _HoverCard:
    """? 号悬浮讲解卡: 悬停弹出, 移入可细读, 移开收起。"""

    def __init__(self, anchor, title, values=None, lines=None):
        self._anchor = anchor
        self._title, self._values, self._lines = title, values, lines
        self._tip = None
        self._after = None
        anchor.bind("<Enter>", self._schedule)
        anchor.bind("<Leave>", self._hide)

    def _schedule(self, _=None):
        if self._after:
            self._anchor.after_cancel(self._after)
        if self._tip is None:
            self._after = self._anchor.after(300, self._show)

    def _show(self):
        self._after = None
        if self._tip is not None:
            return
        tip = tk.Toplevel(self._anchor)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        f = ttk.Frame(tip, padding=10)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=self._title, font=("Microsoft YaHei UI", 10, "bold")
                  ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        r = 1
        for v, d, s in self._values or []:
            ttk.Label(f, text=v, bootstyle="success").grid(
                row=r, column=0, sticky="w", padx=(0, 12))
            ttk.Label(f, text=d).grid(row=r, column=1, sticky="w", padx=(0, 12))
            ttk.Label(f, text=s, bootstyle="secondary").grid(
                row=r, column=2, sticky="w")
            r += 1
        for k, text in self._lines or []:
            ttk.Label(f, text=k, bootstyle="success").grid(
                row=r, column=0, sticky="w", padx=(0, 12))
            ttk.Label(f, text=text).grid(
                row=r, column=1, columnspan=2, sticky="w")
            r += 1
        tip.update_idletasks()
        x = self._anchor.winfo_rootx() - 8
        y = self._anchor.winfo_rooty() + self._anchor.winfo_height() + 6
        tip.geometry(f"+{x}+{y}")
        self._tip = tip
        tip.bind("<Enter>", self._keep)
        tip.bind("<Leave>", self._hide)

    def _keep(self, _=None):               # 移入卡片: 取消退隐, 容许细读
        if self._after:
            self._anchor.after_cancel(self._after)
            self._after = None

    def _hide(self, _=None):
        self._keep()
        if self._tip is not None:
            self._after = self._anchor.after(200, self._destroy)

    def _destroy(self):
        self._after = None
        if self._tip is not None:
            tip, self._tip = self._tip, None
            tip.destroy()


def _load_aliases() -> dict:
    try:
        return json.loads(_ALIAS_PATH.read_text("utf-8"))
    except Exception:
        return {}


def _save_aliases(d: dict) -> None:
    _ALIAS_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                           encoding="utf-8")


class Console:
    def __init__(self, business_mod):
        self.business_mod = business_mod          # business.py(配置 schema+示例)
        self.gcfg = settings.load()
        self.logq: queue.Queue = queue.Queue()
        self.notifyq: queue.Queue = queue.Queue()  # (kind, title) UI 通知
        self._toast_win: tk.Toplevel | None = None
        self.aliases: dict = _load_aliases()        # hwnd→别名(改名持久化)
        self.workers: dict[str, Worker] = {}      # ident → Worker
        self.hotkey = None                        # adb 端无热键(设备按行启动)
        if self.gcfg.backend == "window":
            self.hotkey = HotkeyListener(hotkey_vk(self.gcfg.hotkey),
                                         self.on_hotkey)
        self._build()
        if self.hotkey:
            self.hotkey.start()
        if self.gcfg.backend == "adb":
            self.scan_adb_devices()
        self.root.after(100, self._pump_log)
        self.root.after(500, self._refresh_rows)

    # ================= UI 构建 =================
    def _build(self):
        import ttkbootstrap as ttkb
        self.root = ttkb.Window(title="imgbot 中控台", themename=self.gcfg.theme,
                                size=tuple(self.gcfg.window_size))
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="⚙ 设置", command=self._open_settings,
                   bootstyle="secondary-outline").pack(side="left")
        if self.gcfg.backend == "window":
            self.hotkey_lbl = ttk.Label(
                top, text=f"热键: {hotkey_label(self.gcfg.hotkey)} 收编/停止  ●监听中")
        else:
            self.hotkey_lbl = ttk.Label(top, text="adb 模式 · 设备按行启动")
        self.hotkey_lbl.pack(side="left", padx=12)
        self.status_lbl = ttk.Label(top, text="0 运行")
        self.status_lbl.pack(side="right")

        self.left_f = ttk.Frame(self.root, padding=(6, 0))
        self.right_f = ttk.Frame(self.root, padding=(6, 0))
        self._relayout()

        cols = ("name", "state", "info", "preview")
        self._snap_col = self.gcfg.backend == "adb"   # 行📸: 存盘截图(发问题现场)
        col_specs = [("name", "窗口标题", 150), ("state", "状态", 80),
                     ("info", "最近信息", 205), ("preview", "预览", 46)]
        if self._snap_col:
            cols += ("snap",)
            col_specs.append(("snap", "截图", 46))
        self.tree = ttk.Treeview(self.left_f, columns=cols, show="headings", height=12)
        for cid, text, wd in col_specs:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=wd, anchor="w")
        for tag, color in _ROW_TAGS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Button-1>", self._on_cell_click)
        self.tree.bind("<Control-a>", self._select_all)

        btns = ttk.Frame(self.left_f)              # 行操作: 吃全部选中行
        btns.pack(fill="x", pady=(4, 0))
        ttk.Button(btns, text="启动", width=8, bootstyle="success",
                   command=self._start_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="停止", width=8, bootstyle="danger-outline",
                   command=self._stop_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="移除", width=8, bootstyle="secondary-outline",
                   command=self._remove_selected).pack(side="left", padx=2)
        ttk.Label(btns, text="Ctrl/Shift 多选 · Ctrl+A 全选",
                  bootstyle="secondary").pack(side="right")
        btns2 = ttk.Frame(self.left_f)             # 全量操作
        btns2.pack(fill="x", pady=(4, 4))
        ttk.Button(btns2, text="全部启动", width=10, bootstyle="success-outline",
                   command=self._start_all).pack(side="left", padx=2)
        ttk.Button(btns2, text="全部停止", width=10, bootstyle="danger-outline",
                   command=self._stop_all).pack(side="left", padx=2)
        if self.gcfg.backend == "adb":           # 补捞后开的模拟器(不占热键)
            ttk.Button(btns2, text="扫描设备", width=10, bootstyle="info-outline",
                       command=self.scan_adb_devices).pack(side="left", padx=2)

        self.logbox = tk.Text(self.right_f, bg="#1b1f24", fg="#d0d0d0", state="disabled",
                              wrap="word", font=("Consolas", 9))
        self.logbox.pack(fill="both", expand=True)
        for level, color in _LOG_COLORS.items():
            self.logbox.tag_config(level, foreground=color)

    def _relayout(self):
        """按当前 gcfg 摆窗体尺寸与左右分栏(建窗与设置保存后共用)。"""
        w, h = self.gcfg.window_size
        self.root.geometry(f"{w}x{h}")
        lw = int((w - 24) * self.gcfg.left_ratio)
        self.left_f.place(x=6, y=52, width=lw, height=h - 110)
        self.right_f.place(x=lw + 12, y=52, width=w - 24 - lw, height=h - 110)

    # ================= Worker 管理(热键/按钮共用) =================
    def on_hotkey(self):
        """F9(热键线程): 悬停窗口未收编→拾取并启动; 已收编→切换启停。"""
        hwnd = backends.pick_window(self.gcfg.pick_mode, self.gcfg.window_class)
        if not hwnd:
            return
        ident = str(hwnd)
        w = self.workers.get(ident)
        if w is None:
            title = self.aliases.get(ident) or backends.window_title(int(hwnd))
            w = Worker(ident, self.gcfg.backend, self.gcfg,
                       self.business_cfg_value, self.logq, title)
            self.workers[ident] = w
            self.logq.put((ident, f"已收编: {title}", "info"))
            w.start()
            self.notifyq.put(("start", title))
        elif w.alive:
            w.stop()
            self.notifyq.put(("stop", w.title))
        else:
            w.start()
            self.notifyq.put(("start", w.title))

    def scan_adb_devices(self):
        """adb 端设备扫描: 在线设备建行入表(不启动), 已入表跳过。
        启动期与"扫描设备"按钮共用; 移除的行重扫会回来(设备仍在线)。"""
        try:
            serials = backends.list_adb_serials(self.gcfg)
        except Exception as e:
            self.logq.put(("adb", f"设备扫描失败: {e}(adb 在 PATH 吗?)", "error"))
            return
        fresh = [s for s in serials if s not in self.workers]
        labels = backends.adb_labels(fresh)     # 品牌(雷电/MuMu/…)·尾号, 真机退型号
        for s in fresh:
            self.workers[s] = Worker(s, "adb", self.gcfg,
                                     self.business_cfg_value, self.logq,
                                     self.aliases.get(s) or labels.get(s, s))
        self.logq.put(("adb", f"扫描: 在线 {len(serials)} 台, 新入表 {len(fresh)}"
                             "(表格按行启动)", "info"))

    def _toggle_selected(self):
        sel = self.tree.selection()
        if sel:
            self._toggle(self.workers.get(sel[0]))

    # ---- 表格交互: 双击标题列=改名, 双击其余=启停, 点📷=开预览窗 ----
    def _on_double(self, e):
        row = self.tree.identify_row(e.y)
        if not row:
            return
        if self.tree.identify_column(e.x) == "#1":
            self._rename(row)
        else:
            self._toggle(self.workers.get(row))

    def _on_cell_click(self, e):
        if (self.tree.identify_region(e.x, e.y) == "cell"):
            col = self.tree.identify_column(e.x)
            row = self.tree.identify_row(e.y)
            if not row:
                return
            if col == "#4":
                self._open_preview(row)
            elif col == "#5" and self._snap_col:
                self._snap_row(row)

    def _rename(self, ident: str):
        w = self.workers.get(ident)
        if not w:
            return
        new = simpledialog.askstring(
            "改名", "窗口别名(表格显示/通知用):", initialvalue=w.title or "",
            parent=self.root)
        if new is not None and new.strip():
            w.title = new.strip()
            self.aliases[ident] = w.title
            _save_aliases(self.aliases)

    def _open_preview(self, ident: str):
        w = self.workers.get(ident)
        if w:
            _Preview(self.root, w)

    def _snap_row(self, ident: str):
        """行📸: 即时截设备画面存 logs/shots(独立 adb 截屏, 任务卡死也能截),
        路径进日志——发问题现场给作者看。后台线程跑, 不冻 UI。"""
        if not self.workers.get(ident):
            return

        def work():
            try:
                from imgbot.target import AdbTarget
                stem = re.sub(r'[\\/:*?"<>|]', "_", ident)
                p = backends.SHOTS / (f"{time.strftime('%m%d_%H%M%S')}"
                                      f"_{stem}_snap.png")
                w_px, h_px = AdbTarget(ident).save_screenshot(p)
                self.logq.put((ident, f"截图已存: {p}({w_px}x{h_px})", "info"))
            except Exception as e:
                self.logq.put((ident, f"截图失败: {e!r}", "error"))

        threading.Thread(target=work, daemon=True).start()

    def _start_selected(self):
        ws = [w for w in (self.workers.get(i) for i in self.tree.selection()) if w]
        for w in ws:
            if not w.alive:
                w.start()
        self._batch_notify("start", "启动", ws)

    def _stop_selected(self):
        ws = [w for w in (self.workers.get(i) for i in self.tree.selection()) if w]
        for w in ws:
            if w.alive:
                w.stop(join_s=0.0)       # 不 join: 多行停止不冻结 UI
        self._batch_notify("stop", "停止", ws)

    def _remove_selected(self):
        for ident in self.tree.selection():
            w = self.workers.pop(ident, None)
            if w:
                w.stop(join_s=0.0)
            self.tree.delete(ident)

    def _select_all(self, _e=None):
        """Ctrl+A 全选(配合 启动/停止/移除 吃全部选中行)。"""
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _start_all(self):
        """全部启动: 逐台错峰 1.5s(root.after 链, 防冷启动并发打满机器)。"""
        todo = [w for w in self.workers.values() if not w.alive]
        if not todo:
            return
        n = 0

        def one(i):
            nonlocal n
            if i >= len(todo):
                self._show_notify("start", f"全部启动完成: {n} 台")
                self.logq.put(("中控台", f"全部启动完成: {n} 台", "info"))
                return
            w = todo[i]
            if not w.alive:
                w.start()
                n += 1
            self.root.after(1500, lambda: one(i + 1))

        one(0)

    def _stop_all(self):
        """全部停止: 立即发停止信号(线程各自收口), 汇总一条通知。"""
        running = [w for w in self.workers.values() if w.alive]
        if not running:
            return
        for w in running:
            w.stop(join_s=0.0)
        self._batch_notify("stop", "停止", running)
        self.logq.put(("中控台", f"全部停止: {len(running)} 台", "info"))

    def _batch_notify(self, kind: str, verb: str, ws):
        """批量操作只弹一条汇总(单台照旧逐台弹)。"""
        if not ws:
            return
        if len(ws) == 1:
            self._show_notify(kind, ws[0].title or ws[0].ident)
        else:
            self._show_notify(kind, f"已{verb} {len(ws)} 台")

    def _toggle(self, w: Worker, force_on=False, force_off=False):
        if w is None:
            return
        if w.alive and not force_on:
            w.stop()
            self._show_notify("stop", w.title)
        elif not force_off:
            w.start()
            self._show_notify("start", w.title)

    # ================= 刷新(表格/状态栏) =================
    def _refresh_rows(self):
        running = 0
        for ident, w in self.workers.items():
            coarse = ("running" if w.alive else
                      "error" if "异常" in w.state else
                      "done" if w.state == "已停止" else "idle")
            vals = (w.title or w.ident, w.state, w.last_info, "📷")
            if self._snap_col:
                vals += ("📸",)
            if self.tree.exists(ident):
                self.tree.item(ident, values=vals, tags=(coarse,))
            else:
                self.tree.insert("", "end", iid=ident, values=vals, tags=(coarse,))
            if w.alive:
                running += 1
        self.status_lbl.config(text=f"{running} 运行")
        self.root.after(500, self._refresh_rows)

    def _pump_log(self):
        while True:
            try:
                ident, text, level = self.logq.get_nowait()
            except queue.Empty:
                break
            ts = time.strftime("%H:%M:%S")
            self.logbox.config(state="normal")
            self.logbox.insert("end", f"[{ts}] [{ident}] {text}\n", level)
            self.logbox.see("end")
            self.logbox.config(state="disabled")
            if ident in self.workers:
                self.workers[ident].last_info = text[:40]
        while True:                                # UI 通知(热键线程投递来的)
            try:
                kind, title = self.notifyq.get_nowait()
            except queue.Empty:
                break
            self._show_notify(kind, title)
        self.root.after(150, self._pump_log)

    # ================= 启停反馈(音效 + 屏幕右下角置顶卡片) =================
    def _show_notify(self, kind: str, title: str):
        """主线程调用: kind="start"|"stop"。中控台可能被目标窗口挡住,
        所以卡片弹在屏幕工作区右下角并置顶, 配音效——不看中控台也有感知。"""
        beeps = ((880, 120), (1318, 140)) if kind == "start" else ((830, 140), (587, 160))
        threading.Thread(                          # Beep 同步阻塞, 别冻 UI
            target=lambda: [winsound.Beep(f, d) for f, d in beeps],
            daemon=True).start()
        self._toast(kind, title)

    def _toast(self, kind: str, title: str):
        if self._toast_win is not None:            # 新通知替换旧卡片
            try:
                self._toast_win.destroy()
            except tk.TclError:
                pass
        bg = "#1f6b37" if kind == "start" else "#8a3030"
        mark = "▶" if kind == "start" else "■"
        word = "已启动" if kind == "start" else "已停止"
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        tk.Label(t, text=f" {mark} {word} · {title or '目标'} ", bg=bg, fg="white",
                 font=("Microsoft YaHei UI", 10, "bold"), padx=14, pady=9).pack()
        t.update_idletasks()
        w, h = t.winfo_reqwidth(), t.winfo_reqheight()
        wa = ctypes.wintypes.RECT()                # 工作区右下角(避开任务栏)
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(wa), 0)
        t.geometry(f"+{wa.right - w - 16}+{wa.bottom - h - 16}")
        self._toast_win = t
        t.after(2500, lambda: self._close_toast(t))

    def _close_toast(self, t: tk.Toplevel):
        try:
            t.destroy()
        except tk.TclError:
            pass
        if self._toast_win is t:
            self._toast_win = None

    # ================= 设置弹窗(两 Tab, schema 驱动) =================
    def _open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("设置")
        dlg.resizable(False, False)
        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        entries = {}
        if not getattr(sys, "frozen", False):
            # Tab1: 脚手架层——弹窗只留常用项; 通道/开关全下拉 + ? 悬浮讲解,
            # 冷门项(pick_mode/max_restarts)直接改 scaffold.toml
            f1 = ttk.Frame(nb, padding=10)
            nb.add(f1, text="脚手架")
            disp_chans = ["normal", "gdi", "gdi2", "dx"]     # gdi 族仅图色
            mouse_chans = ["normal", "windows", "windows2", "dx"]
            kp_chans = ["normal", "windows", "dx"]           # 键盘无 windows2(鼠标光标锁专属)
            yn = ["否", "是"]
            sizes = ["[960, 600]", "[1280, 800]", "[1600, 900]", "[1920, 1080]"]
            themes = ["darkly", "superhero", "cyborg", "solar",
                      "cosmo", "flatly", "litera", "minty"]
            if self.gcfg.backend == "window":    # 通道/热键/经典组合皆 window 专属
                rows = [
                    ("hotkey", "启动热键", hotkey_choices()),
                    ("display", "图色通道", disp_chans),
                    ("mouse", "鼠标通道", mouse_chans),
                    ("keypad", "键盘通道", kp_chans),
                    ("fake_active", "后台假激活", yn),
                    ("hook_keystate", "键状态钩子", yn),
                    ("hide_module", "隐藏模块", yn),
                    ("theme", "主题", themes), ("window_size", "窗体尺寸", sizes),
                    ("left_ratio", "左列宽度比例", None)]
            else:
                rows = [("theme", "主题", themes),
                        ("window_size", "窗体尺寸", sizes),
                        ("left_ratio", "左列宽度比例", None)]
            for row, (key, label, choices) in enumerate(rows):
                cell = ttk.Frame(f1)
                cell.grid(row=row, column=0, sticky="w", pady=2)
                ttk.Label(cell, text=label).pack(side="left")
                if key in _BIND_HELP:
                    q = ttk.Label(cell, text="?", cursor="question_arrow",
                                  bootstyle="info")
                    q.pack(side="left", padx=(4, 0))
                    _HoverCard(q, *_BIND_HELP[key])
                cur = getattr(self.gcfg, key)
                if isinstance(cur, bool):
                    init = "是" if cur else "否"
                elif key == "hotkey":
                    init = hotkey_label(cur)
                else:
                    init = str(cur)
                var = tk.StringVar(value=init)
                if choices:
                    ttk.Combobox(f1, textvariable=var, values=choices,
                                 state="readonly", width=26).grid(
                        row=row, column=1, pady=2)
                else:
                    ttk.Entry(f1, textvariable=var, width=28).grid(
                        row=row, column=1, pady=2)
                entries[key] = var
            # 经典组合: 症状对号入座, 点一条即把上方下拉调成该配方(保存才写回)
            # (仅 window 端——adb 端无通道概念, 无组合可套)
            if self.gcfg.backend == "window":
                box = ttk.Labelframe(f1, text="经典组合 · 点一条即套用", padding=(8, 6))
                box.grid(row=len(rows), column=0, columnspan=2, sticky="we", pady=(10, 0))
                status = ttk.Label(box, text="对号入座: 症状在哪条, 点哪条",
                                   bootstyle="secondary")

                def _apply_combo(name, combo):
                    entries["display"].set(combo["display"])
                    entries["mouse"].set(combo["mouse"])
                    entries["keypad"].set(combo["keypad"])
                    entries["fake_active"].set("是" if combo.get("fake_active") else "否")
                    entries["hook_keystate"].set("是" if combo.get("hook_keystate") else "否")
                    entries["hide_module"].set("否")
                    status.configure(text=f"已套用: {name} · 点保存才写回")

                for i, (name, combo) in enumerate(_CLASSIC_COMBOS):
                    ttk.Button(box, text=f"{name}   →   {_combo_recipe(combo)}",
                               bootstyle="secondary-outline",
                               command=lambda n=name, c=combo: _apply_combo(n, c)
                               ).grid(row=i, column=0, sticky="we", pady=1)
                status.grid(row=len(_CLASSIC_COMBOS), column=0, sticky="w", pady=(4, 0))
        # Tab2: 业务层(读 FIELD_META 自动生成; kind: "entry" | "combo:a|b|c";
        # bool 字段自动转"是/否"下拉, 不让用户输 true/false)
        f2 = ttk.Frame(nb, padding=10)
        nb.add(f2, text="业务")
        biz_vars = {}
        meta = getattr(self.business_mod, "FIELD_META", {})
        cur_biz = self.business_cfg_value
        for row, fname in enumerate(self.business_mod.BusinessConfig.__dataclass_fields__):
            label, kind = meta.get(fname, (fname, "entry"))
            ttk.Label(f2, text=label).grid(row=row, column=0, sticky="w", pady=2)
            cur_val = getattr(cur_biz, fname)
            if kind.startswith("combo:"):
                choices = kind[6:].split("|")
            elif isinstance(cur_val, bool):
                choices = ["是", "否"]
            else:
                choices = None
            var = tk.StringVar(value=("是" if cur_val else "否")
                               if choices == ["是", "否"] else str(cur_val))
            if choices:
                ttk.Combobox(f2, textvariable=var, values=choices,
                             state="readonly", width=26).grid(
                    row=row, column=1, pady=2)
            else:
                ttk.Entry(f2, textvariable=var, width=28).grid(
                    row=row, column=1, pady=2)
            biz_vars[fname] = var

        def apply():
            for k, var in entries.items():
                v = var.get().lower() if k == "hotkey" else var.get()
                setattr(self.gcfg, k, _coerce(getattr(self.gcfg, k), v))
            settings.save(self.gcfg)
            try:                          # 热应用: 主题/尺寸/比例立即生效
                self.root.style.theme_use(self.gcfg.theme)
                self._relayout()
                if self.hotkey is not None:  # 热重绑: 停旧监听, 新键立刻上岗
                    self.hotkey.stop()
                    self.hotkey = HotkeyListener(hotkey_vk(self.gcfg.hotkey),
                                                 self.on_hotkey)
                    self.hotkey.start()
                    self.hotkey_lbl.config(
                        text=f"热键: {hotkey_label(self.gcfg.hotkey)} "
                             f"收编/停止  ●监听中")
            except Exception:
                pass
            for k, var in biz_vars.items():
                cur = getattr(self.business_cfg_value, k)
                setattr(self.business_cfg_value, k, _coerce(cur, var.get()))
            from .store import save as biz_save
            biz_save(self.business_cfg_value)
            dlg.destroy()

        ttk.Button(dlg, text="保存", bootstyle="success",
                   command=apply).pack(pady=(0, 8))
        _center_over(self.root, dlg)

    @property
    def business_cfg_value(self):
        """当前业务配置(共享给新 Worker 的模板值)。

        从 business.yaml 载入: 不读盘则每次启动都是默认值——设置弹窗显示"丢配置",
        且一次保存会把没动的字段连带写回默认值。"""
        if not hasattr(self, "_biz"):
            from .store import load as biz_load
            self._biz = biz_load(self.business_mod.BusinessConfig)
        return self._biz

    def _on_close(self):
        if self.hotkey is not None:
            self.hotkey.stop()
        for w in self.workers.values():
            w.stop(join_s=2.0)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def _center_over(parent, win) -> None:
    """弹窗永远跟主窗: 居中于 parent 当前位置(主窗挪了再开也跟着)。"""
    parent.update_idletasks()
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = parent.winfo_x() + (parent.winfo_width() - w) // 2
    y = parent.winfo_y() + (parent.winfo_height() - h) // 2
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


class _Preview:
    """独立实时预览窗: 1.5s 一帧纯内存(不落盘), 可同时开多个, 关窗即停。
    window 端 PrintWindow 后台截(不抢前台), adb 端设备截图。"""

    def __init__(self, root, w: Worker):
        self.worker = w
        self.top = tk.Toplevel(root)
        self.top.title(f"{w.title or w.ident} · 实时预览")
        self.lbl = tk.Label(self.top, text="加载中…", bg="#1b1f24", fg="#d0d0d0")
        self.lbl.pack(padx=2, pady=2)
        _center_over(root, self.top)
        self.top.protocol("WM_DELETE_WINDOW", self._close)
        self._alive = True
        self._tick()

    def _grab(self):
        if self.worker.backend == "window":
            from imgbot.win32.capture import capture_client
            from imgbot.win32.window import GameWindow
            return capture_client(GameWindow(int(self.worker.ident)))
        from imgbot.target import AdbTarget
        return AdbTarget(self.worker.ident).screenshot()

    def _tick(self):
        if not self._alive:
            return
        try:
            import cv2
            from PIL import Image, ImageTk
            rgb = cv2.cvtColor(self._grab(), cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            if w > 800:                            # 等比缩, 大屏不至于爆
                rgb = cv2.resize(rgb, (800, int(h * 800 / w)))
            self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.lbl.configure(image=self._photo, text="")
        except Exception:
            self.lbl.configure(image="", text="窗口已失效")
        if self._alive:
            self.top.after(1500, self._tick)

    def _close(self):
        self._alive = False
        self.top.destroy()


def _coerce(cur, text: str):
    """按当前值类型转换字符串(配置弹窗全部文本框)。"""
    if isinstance(cur, bool):
        return text.strip().lower() in ("1", "true", "yes", "是")
    if isinstance(cur, int):
        return int(text)
    if isinstance(cur, float):
        return float(text)
    if isinstance(cur, list):
        return [int(x) for x in text.strip("[]").split(",") if x.strip()]
    return text
