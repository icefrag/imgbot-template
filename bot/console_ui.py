# -*- coding: utf-8 -*-
"""中控台(ttkbootstrap): 左=目标表格+启停按钮, 右=日志面板(按窗口着色)。

尺寸/比例/主题 = 脚手架层 [ui] 配置, root.resizable(False,False) 用户锁死。
设置弹窗两 Tab: 脚手架(固定 schema) / 业务(读 business.FIELD_META 自动生成)。
"""
from __future__ import annotations

import queue
import time
import tkinter as tk
import ttkbootstrap as ttk   # 控件全走 ttkbootstrap(bootstyle 才有效)

from . import backends
from . import settings
from .hotkeys import HotkeyListener
from .worker import Worker

_LOG_COLORS = {"info": "#d0d0d0", "warn": "#e6b84c", "error": "#e05c5c"}
_ROW_TAGS = {"running": "green", "error": "red", "done": "blue", "idle": "gray"}


class Console:
    def __init__(self, business_mod):
        self.business_mod = business_mod          # business.py(配置 schema+示例)
        self.gcfg = settings.load()
        self.logq: queue.Queue = queue.Queue()
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

        cols = ("name", "backend", "state", "info")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=12)
        for cid, text, wd in (("name", "目标", 130), ("backend", "后端", 70),
                              ("state", "状态", 90), ("info", "最近信息", 200)):
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=wd, anchor="w")
        for tag, color in _ROW_TAGS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._toggle_selected())

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
        """F9: 悬停窗口未收编→拾取并启动; 已收编→切换启停。"""
        hwnd = backends.pick_window(self.gcfg.pick_mode, self.gcfg.window_class)
        if not hwnd:
            return
        ident = str(hwnd)
        w = self.workers.get(ident)
        if w is None:
            w = Worker(ident, self.gcfg.backend, self.gcfg,
                       self.business_cfg_value, self.logq)
            self.workers[ident] = w
            self.logq.put((ident, f"已收编: {backends.window_title(int(hwnd))}",
                           "info"))
            w.start()
        elif w.alive:
            w.stop()
        else:
            w.start()

    def _toggle_selected(self):
        sel = self.tree.selection()
        if sel:
            self._toggle(self.workers.get(sel[0]))

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
        elif not force_off:
            w.start()

    # ================= 刷新(表格/状态栏) =================
    def _refresh_rows(self):
        running = 0
        for ident, w in self.workers.items():
            coarse = ("running" if w.alive else
                      "error" if "异常" in w.state else
                      "done" if w.state == "已停止" else "idle")
            vals = (w.ident, w.backend, w.state, w.last_info)
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
        self.root.after(150, self._pump_log)

    # ================= 设置弹窗(两 Tab, schema 驱动) =================
    def _open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("设置")
        dlg.resizable(False, False)
        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        # Tab1: 脚手架层(固定 schema)
        f1 = ttk.Frame(nb, padding=10)
        nb.add(f1, text="脚手架")
        entries = {}
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
