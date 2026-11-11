# -*- coding: utf-8 -*-
"""adb 后端进程形态(ADR 0004): 每设备一子进程, 本模块两端兼营.

子进程端(child_main): 复用 Worker 线程机制跑完整任务循环, 日志/状态经 stdout
行协议(JSON 单行)回传; stdin 收 "stop" 优雅停; 退出码携带终态(0=正常/3=熔断/
4=致命/5=绑定失败, 见 _EXIT_CODES)。

监督者端(DeviceProc): Fleet 的行对象, mimic Worker 的 UI 消费面(alive/display/
coarse/last_info/log/start/stop)。两段式停止: 先 stdin "stop" 优雅收口, join_s
内不退 taskkill /F /T 硬杀; 断管(EOF)=子进程死=天然存活信号。静默审计
(audit_silence) 由 UI 心跳驱动: 活着但 N 分钟无任何输出 = 卡死(C 调用挂死铁律:
线程杀不掉, 进程才杀得掉) → 硬杀标红躺平, 不自动重拉(测试期契约: 暴露问题
而非掩盖)。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time

# 子进程退出码 → Worker 终态语义(监督者按码上色; 码只增不改)
_EXIT_CODES = {0: "STOPPED", 3: "FUSED", 4: "FATAL", 5: "ERROR"}

# 静默审计默认阈值(秒): 子进程活着但这么久没有任何 stdout = 卡死
SILENCE_S = 600


# ==================== 子进程端 ====================

def child_main(serial: str) -> int:
    """被 spawn 的自己从这进: 建 Worker(线程机制原样) → 泵日志到 stdout。

    返回值=进程退出码(_EXIT_CODES 反查)。
    """
    import business  # 项目根的 business.py(与中控台同 cwd/sys.path, 冻结态同包)
    from icefrag import settings, store
    from icefrag.worker import State, Worker

    def send(obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    logq: queue.Queue = queue.Queue()
    biz = store.load(business.BusinessConfig)
    w = Worker(serial, "adb", settings.load(), biz, logq)

    def pump_logs():
        while True:
            try:
                _ident, text, level = logq.get(timeout=0.3)
            except queue.Empty:
                if not w.alive and logq.empty():
                    return
                continue
            w.last_info = text[:40]
            send({"k": "log", "lv": level, "t": text})

    def poll_state():
        last = None
        while True:
            if w.state is not last:                # 变化即报(终态必达)
                last = w.state
                send({"k": "st", "st": last.name, "info": w.last_info})
            if not w.alive:
                return
            time.sleep(0.2)

    def read_stdin():
        for line in sys.stdin:                       # 阻塞读; 断管即返回
            if line.strip() == "stop":
                w.stop_event.set()
                return

    for t in (threading.Thread(target=pump_logs, daemon=True),
              threading.Thread(target=poll_state, daemon=True),
              threading.Thread(target=read_stdin, daemon=True)):
        t.start()
    w.start()
    while w.alive:
        time.sleep(0.2)
    for code, name in _EXIT_CODES.items():           # 终态→退出码(反向查表)
        if w.state.name == name:
            return code
    return 0


def maybe_child_argv() -> int | None:
    """exe/python 入口第一行调用: argv 带 --icefrag-device <serial> 则跑子进程。

    返回退出码(调用方 sys.exit), None=不是子进程模式, 照常起中控台。
    """
    if "--icefrag-device" not in sys.argv:
        return None
    serial = sys.argv[sys.argv.index("--icefrag-device") + 1]
    return child_main(serial)


# ==================== 监督者端 ====================

class DeviceProc:
    """Fleet 的 adb 行对象(进程形态): mimic Worker 的 UI 消费面。

    cmd 可显式注入(测试用假子进程); 缺省 spawn 自己
    [sys.executable, sys.argv[0], --icefrag-device, ident]。
    """

    def __init__(self, ident, gcfg, business_cfg, logq, title=None, cmd=None):
        self.ident = ident
        self.title = title or ident
        self.backend = "adb"
        self.gcfg = gcfg                       # 兼容 Fleet/frame 消费面
        self.business_cfg = business_cfg       # 同上(参数经文件每轮重读, 不走此引用)
        self.logq = logq
        self.proc: subprocess.Popen | None = None
        self.state = "IDLE"                    # Worker.State 名(string)
        self.last_info = "—"
        self.last_line_ts = 0.0                # 静默审计锚点(0=从未说话, 不审计 IDLE)
        self._cmd = cmd

    # ---- UI 消费面(与 Worker 同形) ----
    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def display(self) -> str:
        from icefrag.worker import State
        try:
            return State[self.state].value
        except KeyError:
            return self.state

    @property
    def coarse(self) -> str:
        if self.alive:
            return "running"
        if self.state in ("ERROR", "FATAL", "FUSED"):
            return "error"
        if self.state == "STOPPED":
            return "done"
        return "idle"

    def log(self, text: str, level: str = "info"):
        """监督者自己的话(截图已存/强杀通知等)走中控台日志面板。"""
        self.last_info = text[:40]
        self.logq.put((self.ident, text, level))

    # ---- 生命周期 ----
    def start(self):
        if self.alive:
            return
        if self._cmd is None:
            self._cmd = [sys.executable, os.path.abspath(sys.argv[0]),
                         "--icefrag-device", self.ident]
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", env=env, creationflags=flags)
        self.state = "RUNNING"
        self.last_line_ts = time.monotonic()
        threading.Thread(target=self._pump, daemon=True).start()

    def stop(self, join_s: float = 5.0, announce=True):
        """两段式: stdin "stop" 优雅收口; join_s 内不退 taskkill /F /T 硬杀。

        join_s<=0: 只发优雅信号不等待(批量停止用), 死活交给审计/EOF。
        """
        if not self.alive:
            return
        try:
            self.proc.stdin.write("stop\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass                                # 管已断, 等 reap
        if join_s > 0:
            end = time.monotonic() + join_s
            while self.alive and time.monotonic() < end:
                time.sleep(0.1)
            if self.alive:
                self._kill("优雅停止超时, 硬杀")

    def _kill(self, why: str):
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                       capture_output=True)
        self.log(f"{why}(pid {self.proc.pid})", "error")

    def _pump(self):
        """读子进程 stdout: JSON 行上状态/日志, 非 JSON 行(崩溃 traceback)按 error 转。"""
        assert self.proc is not None and self.proc.stdout
        for line in self.proc.stdout:
            self.last_line_ts = time.monotonic()
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.logq.put((self.ident, line, "error"))
                continue
            if msg.get("k") == "log":
                self.last_info = str(msg.get("t", ""))[:40]
                self.logq.put((self.ident, msg.get("t", ""),
                               msg.get("lv", "info")))
            elif msg.get("k") == "st":
                self.state = str(msg.get("st", self.state))
                if msg.get("info"):
                    self.last_info = str(msg["info"])[:40]
        code = self.proc.wait()
        if self.state in ("RUNNING", "IDLE"):    # 没等到终态行: 退出码反推
            self.state = _EXIT_CODES.get(code, "ERROR")
            if code not in _EXIT_CODES:
                self.log(f"设备进程异常退出(code {code})", "error")

    def audit_silence(self, silence_s: float = SILENCE_S):
        """静默审计(UI 心跳驱动): 活着但 silence_s 无任何输出 = 卡死 → 硬杀标红。

        不自动重拉(测试期契约)。IDLE(从未启动)不审计。
        """
        if not self.alive or self.state == "IDLE":
            return
        idle = time.monotonic() - self.last_line_ts
        if idle > silence_s:
            self.state = "ERROR"
            self.last_info = f"卡死({int(idle / 60)} 分钟无输出), 已强杀"
            self.log(f"静默 {int(idle / 60)} 分钟无输出, 判卡死强杀"
                     f"(pid {self.proc.pid}), 标红躺平", "error")
            self._kill("卡死")
