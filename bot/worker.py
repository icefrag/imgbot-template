# -*- coding: utf-8 -*-
"""Worker: 一个目标一个线程。框架承担: 绑定→ctx→任务→异常重开→收口,
任务代码(main_task(ctx))对这些一无所知。

状态机: 未运行 → (启动)运行中 → 完成/异常(重开计数) → 熔断/已停止
"""
from __future__ import annotations

import threading
import time
import traceback

from . import backends, dsl, settings


class Worker:
    def __init__(self, ident: str, backend: str, gcfg: settings.ScaffoldConfig,
                 business_cfg, logq, title: str = ""):
        self.ident = ident                        # window: hwnd | adb: serial
        self.title = title                        # 展示名(窗口标题/设备名)
        self.backend = backend
        self.gcfg = gcfg
        self.business_cfg = business_cfg
        self.logq = logq
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state = "未运行"
        self.last_info = "—"
        self.restarts = 0

    # -- 给 UI 的属性 --
    @property
    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def log(self, text: str, level: str = "info"):
        self.logq.put((self.ident, text, level))

    # -- 控制 --
    def start(self):
        if self.alive:
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self, join_s: float = 5.0):
        self.stop_event.set()
        if self.thread:
            self.thread.join(join_s)

    # -- 内部 --
    def _try_fuse_hook(self, task_mod, ctx) -> bool:
        """熔断前给业务一次自愈机会: task.py 里定义 on_fuse(ctx) -> bool
        (重启游戏/重新登录等), 返回 True = 已恢复(重开计数清零继续挂);
        没定义/返回假/自身炸 = 维持熔断躺平。"""
        fuse = getattr(task_mod, "on_fuse", None)
        if fuse is None:
            return False
        self.log("熔断, 调业务恢复钩子 on_fuse…", "warn")
        try:
            if fuse(ctx):
                self.restarts = 0
                self.state = "运行中"
                self.log("on_fuse 恢复成功, 重开计数清零", "info")
                return True
            self.log("on_fuse 返回未恢复, 维持熔断", "error")
        except Exception as e:
            self.log(f"on_fuse 失败: {e!r}", "error")
        return False

    def _run(self):
        """绑定 → 任务循环(异常重开/熔断) → 收口。一次线程调用跑到底。"""
        ctx = None
        try:
            self.state = "运行中"
            if self.backend == "window":
                ctx = backends.bind_window_backend(
                    int(self.ident), self.gcfg, self.business_cfg,
                    self.log, self.stop_event)
            else:
                ctx = backends.bind_adb_backend(
                    self.ident, self.gcfg, self.business_cfg,
                    self.log, self.stop_event)
            self.log(f"已绑定({self.backend}), 任务开始")
            dsl._bind(ctx)                    # DSL 顶层动词从此线程可见

            # 任务入口(business 逻辑): 框架只负责把它跑起来
            import task as task_mod              # 项目根的 task.py
            while not self.stop_event.is_set():
                try:
                    task_mod.main_task(ctx)
                    if self.stop_event.is_set():
                        break
                    self.state = "运行中"
                    self.restarts = 0            # 正常跑完一轮, 重开计数清零
                    self.log(f"一轮完成, {self.gcfg.loop_interval}s 后重开")
                    self.stop_event.wait(self.gcfg.loop_interval)
                except Exception as e:
                    self.restarts += 1
                    ctx.shot("异常")              # 留痕(spec: 验收门槛)
                    if self.restarts > self.gcfg.max_restarts:
                        if self._try_fuse_hook(task_mod, ctx):
                            continue             # 业务自愈成功, 计数已清零
                        self.state = "异常(熔断)"
                        self.log(f"连败 {self.restarts} 次熔断: {e!r}", "error")
                        return
                    self.state = "运行中"
                    self.log(f"异常重开 {self.restarts}/{self.gcfg.max_restarts}: "
                             f"{e!r}", "warn")
                    self.stop_event.wait(2.0)
        except Exception as e:                   # 绑定阶段炸
            self.state = "异常"
            self.log(f"绑定失败: {e!r}", "error")
        finally:
            if ctx is not None:
                backends.unbind(ctx)
            if not self.state.startswith("异常"):
                self.state = "已停止"
            self.log("已收口解绑")
