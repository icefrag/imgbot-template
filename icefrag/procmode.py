# -*- coding: utf-8 -*-
"""adb 后端进程形态(ADR 0004): 每设备一子进程, 本模块两端兼营.

子进程端(child_main): 复用 Worker 线程机制跑完整任务循环, 日志/状态经 stdout
行协议(JSON 单行)回传; stdin 收 "stop" 优雅停, **stdin 断管(父死)=孤儿自停**;
退出码携带终态(0=正常/3=熔断/4=致命/5=绑定失败, 见 _EXIT_CODES)。

监督者端(DeviceProc): Fleet 的行对象, mimic Worker 的 UI 消费面(alive/display/
coarse/last_info/log/start/stop), state 用 Worker.State 枚举(别对 state 做字符
串匹配——worker.py 契约, 行协议边界转一次即归一)。两段式停止两条路都保证收口:
join_s>0 同步等+硬杀; join_s<=0(批量停) 只发信号即返回, 后台收割线程宽限后
taskkill /F /T——卡死子进程读不到 stdin 也跑不掉。断管(EOF)=子进程死=天然存活
信号。静默审计(audit_silence) 由 UI 心跳驱动: 活着但 N 分钟无**协议行** = 卡死
(C 调用挂死铁律: 线程杀不掉, 进程才杀得掉) → 硬杀标红躺平, 不自动重拉(测试期
契约: 暴露问题而非掩盖)。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time

from .worker import State

# 子进程退出码 → Worker 终态(监督者按码上色; 码只增不改)
_EXIT_CODES = {0: State.STOPPED, 3: State.FUSED, 4: State.FATAL,
               5: State.ERROR}

# 静默审计默认阈值(秒): 子进程活着但这么久没有任何协议行 = 卡死
SILENCE_S = 600

# 批量停止(join_s<=0)的后台收割宽限(秒): 宽限后仍活 = 卡死, taskkill
REAP_GRACE_S = 5.0


# ==================== 子进程端 ====================

def child_main(serial: str) -> int:
    """被 spawn 的自己从这进: 建 Worker(线程机制原样) → 泵日志到 stdout。

    返回值=进程退出码(_EXIT_CODES 反查)。
    """
    # 每设备一进程的慢 OCR 闸默认(ADR-0004 Consequences): 一台=并发1发, 免
    # N进程×3发 的无界叠加(全局常量默认3是单进程多worker线程形态的口径)。
    # setdefault: 机况特殊的机子可在拉起中控台前自行 export 覆盖。
    os.environ.setdefault("IMGBOT_OCR_MAX_CONCURRENT", "1")
    import business  # 项目根的 business.py(与中控台同 cwd/sys.path, 冻结态同包)
    from icefrag import settings, store
    from icefrag.worker import Worker

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
            # last_info 不在此写: 全部 logq 流量经 Worker.log 入队时已自写
            send({"k": "log", "lv": level, "t": text})

    def poll_state():
        last = w.state                     # 初值不发: 监督者已乐观置 RUNNING,
        while True:                        # 首帧补发 IDLE 会把行打回"未运行"闪
            if w.state is not last:        # 变化即报(终态必达)
                last = w.state
                send({"k": "st", "st": last.name, "info": w.last_info})
            if not w.alive:
                return
            time.sleep(0.2)

    def read_stdin():
        for line in sys.stdin:            # 阻塞读
            if line.strip() == "stop":
                w.stop_event.set()
                return
        w.stop_event.set()                # 断管=父进程没了: 孤儿自停, 不许续跑

    threads = [threading.Thread(target=pump_logs, daemon=True),
               threading.Thread(target=poll_state, daemon=True),
               threading.Thread(target=read_stdin, daemon=True)]
    for t in threads:
        t.start()
    w.start()
    while w.alive:
        time.sleep(0.2)
    threads[0].join(timeout=2.0)          # 日志泵倒干净尾——队列尾恰是熔断/致命现场行,
                                          # daemon 关停即被杀, 不等就丢(2026-11-12 评审)
    for code, st in _EXIT_CODES.items():  # 终态→退出码(反向查表)
        if w.state is st:
            return code
    return 0


def maybe_child_argv() -> int | None:
    """exe/python 入口第一行调用: argv 带 --icefrag-device <serial> 则跑子进程。

    返回退出码(调用方 sys.exit), None=不是子进程模式, 照常起中控台。
    """
    idx = sys.argv.index("--icefrag-device") if "--icefrag-device" in sys.argv else -1
    if idx < 0 or idx + 1 >= len(sys.argv):
        return None                # 缺旗或旗后缺 serial: 照常起中控台, 不猜
    return child_main(sys.argv[idx + 1])


# ==================== 监督者端 ====================

class DeviceProc:
    """Fleet 的 adb 行对象(进程形态): mimic Worker 的 UI 消费面。

    cmd 可显式注入(测试用假子进程); 缺省 spawn 自己
    [sys.executable, sys.argv[0], --icefrag-device, ident]。
    """

    def __init__(self, ident, logq, title=None, cmd=None):
        self.ident = ident
        self.title = title or ident
        self.backend = "adb"
        self.logq = logq
        self.proc: subprocess.Popen | None = None
        self.state = State.IDLE
        self.last_info = "—"
        self.last_line_ts = 0.0                # 静默审计锚点(0=从未说话, IDLE 不审计)
        self._cmd = cmd
        self._stopping = False                 # 主动停止中: 退出码不上 ERROR 色

    # ---- UI 消费面(与 Worker 同形) ----
    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def display(self) -> str:
        return self.state.value

    @property
    def coarse(self) -> str:
        from .worker import coarse_of
        return coarse_of(self.alive, self.state)

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
        self._stopping = False
        try:
            self.proc = subprocess.Popen(
                self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", env=env, creationflags=flags)
        except OSError as e:              # exe 路径坏/杀软拦截(冻结态 spawn 首验面)
            self.state = State.ERROR      # 标红躺平可重试, 不许炸 UI 线程
            self.log(f"spawn 失败: {e}", "error")
            return
        self.state = State.RUNNING
        self.last_line_ts = time.monotonic()
        threading.Thread(target=self._pump, daemon=True).start()

    def stop(self, join_s: float = 5.0):
        """两段式: stdin "stop" 优雅收口; 宽限内不退 taskkill /F /T 硬杀。

        join_s>0: 同步等+硬杀(单行启停用); join_s<=0: 只发信号即返回(批量停止
        不冻 UI), 后台收割线程保证宽限后必杀——卡死子进程读不到 stdin 也跑不掉。
        """
        if not self.alive:
            return
        self._stopping = True
        try:
            self.proc.stdin.write("stop\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass                                # 管已断, 等 reap
        if join_s > 0:
            self._reap(join_s)
        else:
            threading.Thread(target=self._reap, args=(REAP_GRACE_S,),
                             daemon=True).start()

    def _reap(self, grace_s: float):
        end = time.monotonic() + grace_s
        while self.alive and time.monotonic() < end:
            time.sleep(0.1)
        if self.alive:
            self._kill("停止宽限超时, 硬杀")

    def _kill(self, why: str):
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                       capture_output=True)
        self.log(f"{why}(pid {self.proc.pid})", "error")

    def _pump(self):
        """读子进程 stdout: JSON 行上状态/日志, 非 JSON 行(崩溃 traceback)按 error 转。

        静默审计只认协议行: 非 JSON 行不刷 last_line_ts——原生库刷屏不算"活着"。
        """
        assert self.proc is not None and self.proc.stdout
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.logq.put((self.ident, line, "error"))
                continue
            self.last_line_ts = time.monotonic()
            if msg.get("k") == "log":
                self.last_info = str(msg.get("t", ""))[:40]
                self.logq.put((self.ident, msg.get("t", ""),
                               msg.get("lv", "info")))
            elif msg.get("k") == "st":
                try:
                    self.state = State[str(msg.get("st", ""))]
                except KeyError:
                    continue
                if msg.get("info"):
                    self.last_info = str(msg["info"])[:40]
        code = self.proc.wait()
        if self.state in (State.RUNNING, State.IDLE):   # 没等到终态行: 退出码反推
            if code in _EXIT_CODES:
                self.state = _EXIT_CODES[code]
            elif self._stopping:                # 主动停止途中死(含被硬杀): 不算异常
                self.state = State.STOPPED
            else:
                self.state = State.ERROR
                self.log(f"设备进程异常退出(code {code})", "error")

    def audit_silence(self, silence_s: float = SILENCE_S):
        """静默审计(UI 心跳驱动): 活着但 silence_s 无协议行 = 卡死 → 硬杀标红。

        不自动重拉(测试期契约)。IDLE(从未启动)不审计。
        """
        if not self.alive or self.state is State.IDLE:
            return
        idle = time.monotonic() - self.last_line_ts
        if idle > silence_s:
            self.state = State.ERROR
            self.last_info = f"卡死({int(idle / 60)} 分钟无输出), 已强杀"
            self.log(f"静默 {int(idle / 60)} 分钟无输出, 判卡死强杀"
                     f"(pid {self.proc.pid}), 标红躺平", "error")
            self._kill("卡死")
