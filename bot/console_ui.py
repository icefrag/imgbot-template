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
from .hotkeys import HotkeyListener
from .worker import Worker

_LOG_COLORS = {"info": "#d0d0d0", "warn": "#e6b84c", "error": "#e05c5c"}
_ROW_TAGS = {"running": "green", "error": "red", "done": "blue", "idle": "gray"}
_ALIAS_PATH = ROOT / "aliases.json"


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
        self.hotkey = HotkeyListener(self.gcfg.hotkey_vk, self.on_hotkey)
        self._build()
        self.hotkey.start()
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
        self.hotkey_lbl = ttk.Label(
            top, text=f"热键: F{self.gcfg.hotkey_vk - 0x6F} 收编/停止  ●监听中")
        self.hotkey_lbl.pack(side="left", padx=12)
        self.status_lbl = ttk.Label(top, text="0 运行")
        self.status_lbl.pack(side="right")

        w, h = self.gcfg.window_size
        left = ttk.Frame(self.root, padding=(6, 0))
        left.place(x=6, y=52, width=int((w - 24) * self.gcfg.left_ratio),
                   height=h - 110)
        right = ttk.Frame(self.root, padding=(6, 0))
        right.place(x=int((w - 24) * self.gcfg.left_ratio) + 12, y=52,
                    width=int((w - 24) * (1 - self.gcfg.left_ratio)),
                    height=h - 110)

        cols = ("name", "state", "info", "preview")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=12)
        for cid, text, wd in (("name", "窗口标题", 150), ("state", "状态", 80),
                              ("info", "最近信息", 205), ("preview", "预览", 46)):
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=wd, anchor="w")
        for tag, color in _ROW_TAGS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Button-1>", self._on_cell_click)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="启动", width=8, bootstyle="success",
                   command=self._start_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="停止", width=8, bootstyle="danger-outline",
                   command=self._stop_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="移除", width=8, bootstyle="secondary-outline",
                   command=self._remove_selected).pack(side="left", padx=2)

        self.logbox = tk.Text(right, bg="#1b1f24", fg="#d0d0d0", state="disabled",
                              wrap="word", font=("Consolas", 9))
        self.logbox.pack(fill="both", expand=True)
        for level, color in _LOG_COLORS.items():
            self.logbox.tag_config(level, foreground=color)

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
        if (self.tree.identify_region(e.x, e.y) == "cell"
                and self.tree.identify_column(e.x) == "#4"):
            row = self.tree.identify_row(e.y)
            if row:
                self._open_preview(row)

    def _rename(self, ident: str):
        w = self.workers.get(ident)
        if not w:
            return
        new = simpledialog.askstring(
            "改名", "窗口别名(表格显示/通知用):", initialvalue=w.title or "")
        if new is not None and new.strip():
            w.title = new.strip()
            self.aliases[ident] = w.title
            _save_aliases(self.aliases)

    def _open_preview(self, ident: str):
        w = self.workers.get(ident)
        if w:
            _Preview(self.root, w)

    def _start_selected(self):
        sel = self.tree.selection()
        if sel:
            self._toggle(self.workers.get(sel[0]), force_on=True)

    def _stop_selected(self):
        sel = self.tree.selection()
        if sel:
            self._toggle(self.workers.get(sel[0]), force_off=True)

    def _remove_selected(self):
        sel = self.tree.selection()
        if sel:
            w = self.workers.pop(sel[0], None)
            if w:
                w.stop()
            self.tree.delete(sel[0])

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
            # Tab1: 脚手架层(固定 schema)——仅开发期可见, exe 里配置编译期定死
            f1 = ttk.Frame(nb, padding=10)
            nb.add(f1, text="脚手架")
            for row, (key, label) in enumerate([
                    ("display", "图色通道"), ("mouse", "鼠标通道"),
                    ("keypad", "键盘通道"), ("pick_mode", "拾取方式"),
                    ("max_restarts", "异常重开次数"), ("loop_interval", "轮间隔秒"),
                    ("theme", "主题"), ("window_size", "窗体尺寸[x,y]"),
                    ("left_ratio", "左列宽度比例")]):
                ttk.Label(f1, text=label).grid(row=row, column=0, sticky="w", pady=2)
                var = tk.StringVar(value=str(getattr(self.gcfg, key)))
                ttk.Entry(f1, textvariable=var, width=28).grid(
                    row=row, column=1, pady=2)
                entries[key] = var
        # Tab2: 业务层(读 FIELD_META 自动生成; kind: "entry" | "combo:a|b|c")
        f2 = ttk.Frame(nb, padding=10)
        nb.add(f2, text="业务")
        biz_vars = {}
        meta = getattr(self.business_mod, "FIELD_META", {})
        cur_biz = self.business_cfg_value
        for row, fname in enumerate(self.business_mod.BusinessConfig.__dataclass_fields__):
            label, kind = meta.get(fname, (fname, "entry"))
            ttk.Label(f2, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=str(getattr(cur_biz, fname)))
            if kind.startswith("combo:"):
                choices = kind[6:].split("|")
                ttk.Combobox(f2, textvariable=var, values=choices,
                             state="readonly", width=26).grid(row=row, column=1, pady=2)
            else:
                ttk.Entry(f2, textvariable=var, width=28).grid(row=row, column=1, pady=2)
            biz_vars[fname] = var

        def apply():
            for k, var in entries.items():
                setattr(self.gcfg, k, _coerce(getattr(self.gcfg, k), var.get()))
            settings.save(self.gcfg)
            for k, var in biz_vars.items():
                cur = getattr(self.business_cfg_value, k)
                setattr(self.business_cfg_value, k, _coerce(cur, var.get()))
            from .store import save as biz_save
            biz_save(self.business_cfg_value)
            dlg.destroy()

        ttk.Button(dlg, text="保存", bootstyle="success",
                   command=apply).pack(pady=(0, 8))

    @property
    def business_cfg_value(self):
        """当前业务配置(共享给新 Worker 的模板值)。"""
        if not hasattr(self, "_biz"):
            self._biz = self.business_mod.BusinessConfig()
        return self._biz

    def _on_close(self):
        self.hotkey.stop()
        for w in self.workers.values():
            w.stop(join_s=2.0)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


class _Preview:
    """独立实时预览窗: 1.5s 一帧纯内存(不落盘), 可同时开多个, 关窗即停。
    window 端 PrintWindow 后台截(不抢前台), adb 端设备截图。"""

    def __init__(self, root, w: Worker):
        self.worker = w
        self.top = tk.Toplevel(root)
        self.top.title(f"{w.title or w.ident} · 实时预览")
        self.lbl = tk.Label(self.top, text="加载中…", bg="#1b1f24", fg="#d0d0d0")
        self.lbl.pack(padx=2, pady=2)
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
