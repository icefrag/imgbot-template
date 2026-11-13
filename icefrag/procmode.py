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
信号。父进程自己怎么死由作业对象兜底: 全部子进程挂进 KILL_ON_JOB_CLOSE 的
job(2026-11-13), 中控无论优雅退/崩溃/被杀, 内核立刻收割全体子孙。静默审计
(audit_silence) 由 UI 心跳驱动: 活着但 N 分钟无**协议行** = 卡死
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


# ==================== 孤儿兜底: 作业对象 ====================
# EOF 优雅停只救得了"还响应 stdin"的子进程: 父异常死后, 卡在 C 调用里的
# 子进程永远处理不到断管, 就是真孤儿, 且父死=静默审计也没了(2026-11-13
# 用户「中控退出进程不退」案)。兜底层用 Windows 作业对象: 全部子进程挂进
# KILL_ON_JOB_CLOSE 的 job, 本进程无论怎么死(优雅退/崩溃/被任务管理器杀),
# 句柄随进程关闭, 内核立刻收割 job 全体成员——子孙自动继承成员资格, 子进程
# 拉的 adb 守护进程也跑不掉。句柄刻意不 CloseHandle: 进程死=句柄关=全杀。
_JOB: int | None = None


def _supervisor_job(log=None) -> int | None:
    """中控台进程级 KILL_ON_JOB_CLOSE 作业对象(懒建, 句柄进程级复用)。

    建立失败返回 None 且经 log 记一行(排障要能区分「无兜底」与「没走到」),
    兜底层缺席不挡启动, 退回 EOF 优雅停老路; 失败也固化(0), 不许每 spawn
    重试一遍。
    """
    global _JOB
    if _JOB is None:
        if os.name != "nt":
            _JOB = 0                     # 非 Windows: 无此机制, 常驻跳过
        else:
            import ctypes

            class _BasicLimit(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", ctypes.c_uint32),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", ctypes.c_uint32),
                            ("Affinity", ctypes.c_size_t),   # ULONG_PTR
                            ("PriorityClass", ctypes.c_uint32),
                            ("SchedulingClass", ctypes.c_uint32)]

            class _IoCounters(ctypes.Structure):
                _fields_ = [(n, ctypes.c_uint64) for n in (
                    "ReadOperationCount", "WriteOperationCount",
                    "OtherOperationCount", "ReadTransferCount",
                    "WriteTransferCount", "OtherTransferCount")]

            class _ExtLimit(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", _BasicLimit),
                            ("IoInfo", _IoCounters),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t),
                            ("PeakJobMemoryUsed", ctypes.c_size_t)]
            try:
                k32 = ctypes.windll.kernel32
                k32.CreateJobObjectW.restype = ctypes.c_void_p
                k32.AssignProcessToJobObject.argtypes = (
                    ctypes.c_void_p, ctypes.c_void_p)
                k32.SetInformationJobObject.argtypes = (
                    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                    ctypes.c_size_t)
                job = k32.CreateJobObjectW(None, None)
                info = _ExtLimit()
                info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
                if not job or not k32.SetInformationJobObject(
                        job, 9,                      # 9=JobObjectExtendedLimitInformation
                        ctypes.byref(info), ctypes.sizeof(info)):
                    raise OSError(ctypes.GetLastError())
                _JOB = job
            except Exception as e:   # 非宽: 句柄超 c_int 时 ctypes 抛转换错, 非 OSError
                _JOB = 0
                if log is not None:
                    log(f"作业对象建立失败, 本机降级只靠 EOF 自停: {e!r}",
                        "error")
    return _JOB or None


def _pin_stdio_utf8() -> None:
    """子进程端钉死 stdio 编码: 冻结 noconsole exe 的 stdout/stderr 是
    bootloader 自建的 TextIOWrapper, 编码取本地码页(GBK)且**无视
    PYTHONIOENCODING**(2026-11-13 用户方日志乱码案, tools/frozen_stdio_probe
    实证: env 到位但 wrapper=gbk)——行协议按 utf-8 上线是双方契约, 子端显式
    reconfigure 钉住, 与监督者端 Popen 的 encoding="utf-8" 对齐。stderr 同管道
    合并(崩溃 traceback 里的中文串同病), 一并钉。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except AttributeError:      # 裸 writer 无 reconfigure: 维持原状
            pass


# ==================== 子进程端 ====================

def child_main(serial: str) -> int:
    """被 spawn 的自己从这进: 建 Worker(线程机制原样) → 泵日志到 stdout。

    返回值=进程退出码(_EXIT_CODES 反查)。
    """
    # 每设备一进程的 OCR 资源默认(ADR-0004 Consequences): ①慢OCR闸=并发1发, 免
    # N进程×3发 的无界叠加(全局常量默认3是单进程多worker线程形态的口径); ②ORT
    # 推理线程=1, 免 N进程×2线程 冲顶(2026-11-13 客户五开CPU 28→50%案: 5进程
    # 各一套引擎×intra2=10线程; 单发慢约1.5-2x, 调用方超时全是墙钟制不受结构性
    # 影响)。setdefault: 机况特殊的机子可在拉起中控台前自行 export 覆盖。
    os.environ.setdefault("IMGBOT_OCR_MAX_CONCURRENT", "1")
    os.environ.setdefault("IMGBOT_ORT_INTRA_THREADS", "1")
    _pin_stdio_utf8()                     # 行协议通道编码钉 utf-8(冻结 exe 无视 env)
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
        self._assign_job()
        self.state = State.RUNNING
        self.last_line_ts = time.monotonic()
        threading.Thread(target=self._pump, daemon=True).start()

    def _assign_job(self):
        """子进程挂进中控台作业对象: 本进程一死, 内核立刻收割它(含全部子孙)。

        整体不许抛(评审案 a-3: spawn 已成功, 兜底层缺位不许反过来把启动弄
        坏), 失败只记一行——EOF 优雅停仍是第一层。kernel32 签名由
        _supervisor_job 首建时统一配置, 依赖那份配置。
        """
        try:
            job = _supervisor_job(log=self.log)
            if job is None:
                return
            import ctypes
            if not ctypes.windll.kernel32.AssignProcessToJobObject(
                    job, int(self.proc._handle)):
                self.log(f"作业对象挂载失败(win error {ctypes.GetLastError()}), "
                         f"pid {self.proc.pid} 退回 EOF 自停", "info")
        except Exception as e:
            self.log(f"作业对象挂载异常, pid {getattr(self.proc, 'pid', '?')}"
                     f"退回 EOF 自停: {e!r}", "error")

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
