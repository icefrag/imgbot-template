# -*- coding: utf-8 -*-
"""设备编排面(GLOSSARY「设备编排」): 中控台的非渲染半边。

设备扫描入列/启停编排/取帧(预览+📸)/行状态解读的唯一居所——console_ui
只认 Fleet 接口做渲染, 不构造 Worker、不 import imgbot 引擎;
window/adb 取帧方言分派吃在本模块(同 worker 绑定分支的单点模式)。

线程契约: 除 post_intent/scan_adb_async/snap_async 外, 方法只在主线程调
(pump 由 UI 的 after 循环驱动); 热键线程只投意图, 不碰 workers——
启停与字典变更全部收口到主线程, UI 刷新用 rows() 快照, 无跨线程竞态。
"""
from __future__ import annotations

import queue
import re
import threading
import time

from . import backends
from .worker import Worker


class Fleet:
    """ident → Worker 的编排居所。UI 持本对象, 不直接持 Worker 生命周期。"""

    def __init__(self, gcfg, business_cfg, logq, aliases: dict, notify=None):
        self.gcfg = gcfg
        self.business_cfg = business_cfg      # 共享业务配置实例(弹窗改它即改全员)
        self.logq = logq
        self.aliases = aliases                # ident→别名(改名持久化, UI 维护)
        self._notify_cb = notify              # (kind, title) UI 通知, 须线程安全
        self.workers: dict[str, Worker] = {}
        self._intents: queue.Queue = queue.Queue()

    # ---- 行与查询(主线程) ----
    def rows(self) -> list[Worker]:
        """快照迭代(UI 刷新用, 不怕启停并发改字典)。"""
        return list(self.workers.values())

    def get(self, ident: str) -> Worker | None:
        return self.workers.get(ident)

    # ---- 跨线程入口 ----
    def post_intent(self, kind: str, *args):
        """热键线程/扫描线程投递意图; 主线程 pump() 消化。"""
        self._intents.put((kind, args))

    def pump(self):
        """主线程消化意图队列(热键启停/扫描入表), 由 UI 的 after 循环驱动。"""
        while True:
            try:
                kind, args = self._intents.get_nowait()
            except queue.Empty:
                return
            if kind == "hotkey":
                self._toggle_pick(*args)
            elif kind == "scan":
                self._apply_scan(*args)

    def _notify(self, kind: str, title: str):
        if self._notify_cb:
            self._notify_cb(kind, title)

    # ---- window 端: 热键收编 ----
    def _toggle_pick(self, ident: str):
        """悬停窗口未收编→入表并启动; 已收编→切换启停。
        (hwnd 由热键线程拾取后经意图带过来, 本方法在主线程跑)"""
        if ident not in self.workers:
            title = self.aliases.get(ident) or backends.window_title(int(ident))
            w = Worker(ident, "window", self.gcfg, self.business_cfg,
                       self.logq, title)
            self.workers[ident] = w
            w.log(f"已收编: {title}")
            w.start()
            self._notify("start", title)
        else:
            self.toggle(ident)

    # ---- adb 端: 设备扫描 ----
    def scan_adb_async(self):
        """后台线程扫设备(netstat/tasklist/getprop 慢, 不冻 UI), 结果回意图队列。
        移除的行重扫会回来(设备仍在线)。"""
        def work():
            try:
                serials = backends.list_adb_serials(self.gcfg)
            except Exception as e:
                self.logq.put(("adb", f"设备扫描失败: {e}(adb 在 PATH 吗?)", "error"))
                return
            fresh = [s for s in serials if s not in self.workers]
            labels = backends.adb_labels(fresh)   # 品牌(雷电/MuMu/…)·尾号, 真机退型号
            self.post_intent("scan", fresh, labels, len(serials))
        threading.Thread(target=work, daemon=True).start()

    def _apply_scan(self, fresh, labels, total):
        added = [s for s in fresh if s not in self.workers]   # 双扫描竞态保险
        for s in added:
            self.workers[s] = Worker(s, "adb", self.gcfg, self.business_cfg,
                                     self.logq,
                                     self.aliases.get(s) or labels.get(s, s))
        self.logq.put(("adb", f"扫描: 在线 {total} 台, 新入表 {len(added)}"
                             "(表格按行启动)", "info"))

    # ---- 启停编排(主线程, 按钮/意图共用) ----
    def start(self, idents) -> list[Worker]:
        """启动选中行里未在跑的, 返回真正启动了的。"""
        started = []
        for i in idents:
            w = self.workers.get(i)
            if w and not w.alive:
                w.start()
                started.append(w)
        return started

    def stop(self, idents, join_s: float = 5.0) -> list[Worker]:
        """停止选中行里在跑的, 返回真正停了的。join_s=0: 多行停止不冻结 UI。"""
        stopped = []
        for i in idents:
            w = self.workers.get(i)
            if w and w.alive:
                w.stop(join_s=join_s)
                stopped.append(w)
        return stopped

    def remove(self, idents):
        for i in idents:
            w = self.workers.pop(i, None)
            if w:
                w.stop(join_s=0.0)

    def pending_starts(self) -> list[str]:
        """「全部启动」的计划(未在跑的行 ident); 错峰节奏由 UI 的定时链驱动。"""
        return [w.ident for w in self.workers.values() if not w.alive]

    def running(self) -> list[Worker]:
        return [w for w in self.workers.values() if w.alive]

    def stop_all(self, join_s: float = 0.0) -> list[Worker]:
        stopped = self.running()
        for w in stopped:
            w.stop(join_s=join_s)
        return stopped

    def toggle(self, ident: str):
        """单行启停(双击行)。"""
        w = self.workers.get(ident)
        if w is None:
            return
        if w.alive:
            w.stop()
            self._notify("stop", w.title)
        else:
            w.start()
            self._notify("start", w.title)

    # ---- 取帧(预览窗与行📸共用; 不依赖任务在跑) ----
    def frame(self, ident: str):
        """取一帧(BGR ndarray): window=PrintWindow 后台截, adb=设备截图。"""
        w = self.workers.get(ident)
        if w is None:
            raise KeyError(f"行不存在: {ident}")
        if w.backend == "window":
            from imgbot.win32.capture import capture_client
            from imgbot.win32.window import GameWindow
            return capture_client(GameWindow(int(ident)))
        from imgbot.target import AdbTarget
        return AdbTarget(ident).screenshot()

    def snap_async(self, ident: str):
        """行📸: 即时截设备画面存 logs/shots(独立 adb 截屏, 任务卡死也能截),
        路径进日志——发问题现场给作者看。后台线程跑, 不冻 UI。"""
        w = self.workers.get(ident)
        if w is None:
            return

        def work():
            try:
                from imgbot.target import AdbTarget
                stem = re.sub(r'[\\/:*?"<>|]', "_", ident)
                p = backends.SHOTS / (f"{time.strftime('%m%d_%H%M%S')}"
                                      f"_{stem}_snap.png")
                w_px, h_px = AdbTarget(ident).save_screenshot(p)
                w.log(f"截图已存: {p}({w_px}x{h_px})")
            except Exception as e:
                w.log(f"截图失败: {e!r}", "error")

        threading.Thread(target=work, daemon=True).start()
