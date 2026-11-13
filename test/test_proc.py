# -*- coding: utf-8 -*-
"""进程形态(procmode)离线自检: 设备进程协议/两段停止/退出码映射/静默审计/
参数重读/stdio 编码钉死/作业对象孤儿陪葬。假子进程=临时 py 文件(不依赖真
设备真业务)。跑法: uv run test/test_proc.py
"""
import dataclasses
import os
import queue
import sys
import tempfile
import time
from pathlib import Path

from icefrag import store
from icefrag.procmode import REAP_GRACE_S, DeviceProc
from icefrag.worker import State


def _fake_child(code: str) -> list[str]:
    p = Path(tempfile.mkstemp(suffix=".py")[1])
    p.write_text(code, encoding="utf-8")
    return [sys.executable, str(p)]


def _wait(cond, timeout=15.0, what=""):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.1)
    raise AssertionError(f"等不到: {what}")


def _drain(logq) -> list[tuple]:
    out = []
    while True:
        try:
            out.append(logq.get_nowait())
        except queue.Empty:
            return out


def main() -> int:
    logq: queue.Queue = queue.Queue()

    # ① 协议+优雅停: st/log 行回传, stdin stop → STOPPED 退 0
    child = _fake_child(
        "import json,sys,time\n"
        "def send(o): sys.stdout.write(json.dumps(o)+'\\n'); sys.stdout.flush()\n"
        "send({'k':'st','st':'RUNNING','info':'任务开始'})\n"
        "send({'k':'log','lv':'info','t':'点了啥'})\n"
        "for line in sys.stdin:\n"
        "    if line.strip()=='stop': break\n"
        "send({'k':'st','st':'STOPPED','info':'任务被停止'})\n")
    p = DeviceProc("127.0.0.1:5555", logq, title="假·5555", cmd=child)
    p.start()
    _wait(lambda: p.state is State.RUNNING, what="RUNNING")
    _wait(lambda: any("点了啥" in t for _i, t, _l in _drain(logq)), what="log行")
    assert p.alive and p.coarse == "running"
    assert p.display == "运行中"
    p.stop(join_s=10)
    _wait(lambda: not p.alive, what="优雅退出")
    assert p.state is State.STOPPED and p.coarse == "done", p.state

    # ② 退出码映射: 退 3 无 st 行 → FUSED 标红
    child = _fake_child("import sys; sys.exit(3)\n")
    p = DeviceProc("x", logq, cmd=child)
    p.start()
    _wait(lambda: not p.alive, what="退3")
    assert p.state is State.FUSED and p.coarse == "error", p.state

    # ③ 崩溃输出(非 JSON 行)按 error 转发; 未知码 → ERROR
    child = _fake_child(
        "import sys; print('Traceback (most recent call last):'); sys.exit(1)\n")
    p = DeviceProc("x", logq, cmd=child)
    p.start()
    _wait(lambda: not p.alive, what="退1")
    assert p.state is State.ERROR, p.state
    assert any(lv == "error" and "Traceback" in t
               for _i, t, lv in _drain(logq)), "崩溃行没按 error 转"

    # ④ 硬杀: 不读 stdin 的赖死进程, 优雅超时后 taskkill 树杀;
    #    主动停止途中被硬杀 → STOPPED, 不许误标红「异常」(评审案 c1)
    child = _fake_child("import time; time.sleep(300)\n")
    p = DeviceProc("x", logq, cmd=child)
    p.start()
    _wait(lambda: p.alive, what="赖死进程活着")
    t0 = time.monotonic()
    p.stop(join_s=2)
    _wait(lambda: not p.alive, what="硬杀")
    assert time.monotonic() - t0 < 30, "硬杀拖太久"
    assert p.state is State.STOPPED and p.coarse == "done", p.state

    # ⑤ 静默审计: 活着但不说话 → 判卡死强杀标红, 不自动重拉
    child = _fake_child(
        "import sys,time\n"
        "sys.stdout.write('x\\n'); sys.stdout.flush(); time.sleep(300)\n")
    p = DeviceProc("x", logq, cmd=child)
    p.start()
    _wait(lambda: p.last_line_ts > 0, what="说过一句话")
    time.sleep(0.6)                              # 静默窗口走完才许判卡死
    p.audit_silence(silence_s=0.5)
    _wait(lambda: not p.alive, what="审计强杀")
    assert p.state is State.ERROR and "卡死" in p.last_info, p.last_info
    assert p.coarse == "error"

    # ⑥ 批量停止(join_s=0)不冻 UI 也不留孤儿: 后台收割宽限后必杀(评审案 a1)
    child = _fake_child("import time; time.sleep(300)\n")
    p = DeviceProc("x", logq, cmd=child)
    p.start()
    _wait(lambda: p.alive, what="赖死进程活着")
    t0 = time.monotonic()
    p.stop(join_s=0)                             # 即刻返回
    assert time.monotonic() - t0 < 1, "批量停止不该同步等"
    _wait(lambda: not p.alive, timeout=REAP_GRACE_S + 20, what="后台收割")
    assert p.state is State.STOPPED, p.state

    # ⑦ reload_into: 文件改动原地刷进既有实例(引用不变); yaml 坏/缺席不动 cfg
    @dataclasses.dataclass
    class _Cfg:
        mode: str = "a"
        star: int = 1
    old_path = store.PATH
    try:
        with tempfile.TemporaryDirectory() as td:
            store.PATH = Path(td) / "business.yaml"
            cfg = _Cfg()
            store.save(cfg)                       # mode=a star=1
            store.PATH.write_text("mode: b\nstar: 9\n", encoding="utf-8")
            ref = cfg
            store.reload_into(cfg)
            assert cfg is ref and cfg.mode == "b" and cfg.star == 9, cfg
            store.PATH.write_text("mode: [坏yaml\n", encoding="utf-8")
            store.reload_into(cfg)                # 坏文件: 不动
            assert cfg.mode == "b" and cfg.star == 9, "坏yaml不得重置运行中参数"
            store.PATH.unlink()
            store.reload_into(cfg)                # 缺席: 不动
            assert cfg.mode == "b"
    finally:
        store.PATH = old_path

    # ⑧ spawn 失败(exe 路径坏/杀软拦截): start 不炸调用线程, 标红躺平可重试
    p = DeviceProc("x", logq, cmd=[sys.executable + ".坏", "x"])
    p.start()                                   # 不许抛
    assert p.state is State.ERROR and p.coarse == "error", p.state
    assert any("spawn 失败" in t for _i, t, _l in _drain(logq)), "spawn 失败没上报"

    # ⑨ 入口路由 maybe_child_argv: 旗+值→child_main(serial) 返回退出码;
    #    缺旗/旗后无值→None 照常起中控台(旗悬空不许 IndexError, 2026-11-13 评审)
    import icefrag.procmode as pm
    seen, orig_cm, orig_argv = [], pm.child_main, sys.argv
    pm.child_main = lambda serial: (seen.append(serial), 7)[1]
    try:
        sys.argv = ["console.py"]
        assert pm.maybe_child_argv() is None
        sys.argv = ["console.py", "--icefrag-device", "127.0.0.1:5555"]
        assert pm.maybe_child_argv() == 7 and seen == ["127.0.0.1:5555"], seen
        sys.argv = ["console.py", "--icefrag-device"]
        assert pm.maybe_child_argv() is None, "旗后无值不该 IndexError"
    finally:
        pm.child_main, sys.argv = orig_cm, orig_argv

    # ⑩ 行协议编码钉死 _pin_stdio_utf8(2026-11-13 用户方日志乱码案): 冻结
    #    noconsole exe 的 stdout 是 bootloader 自建 TextIOWrapper, 编码=本地
    #    码页(GBK)且无视 PYTHONIOENCODING——子进程中文按 GBK 上线, 监督者按
    #    utf-8 replace 解码成满屏菱形。回归: helper 必须把 gbk wrapper 翻成
    #    utf-8 且字节真按 utf-8 落管; 无 reconfigure 的裸 writer 不许炸。
    import io
    from icefrag.procmode import _pin_stdio_utf8
    buf = io.BytesIO()
    fake_out = io.TextIOWrapper(buf, encoding="gbk")   # 复刻冻结子进程现场
    orig = (sys.stdout, sys.stderr)
    sys.stdout, sys.stderr = fake_out, object()        # stderr=无 reconfigure 裸对象
    try:
        _pin_stdio_utf8()
        sys.stdout.write("中文协议行\n")
        sys.stdout.flush()
    finally:
        sys.stdout, sys.stderr = orig
    wire = buf.getvalue()
    assert fake_out.encoding == "utf-8", fake_out.encoding
    assert "中文协议行".encode("utf-8") in wire, wire
    assert "中文协议行".encode("gbk") not in wire, "还在按 GBK 上线"

    # ⑪ 中控台硬死→子进程内核级陪葬(作业对象 KILL_ON_JOB_CLOSE, 2026-11-13
    #    「中控退出进程不退」案): 监督者 os._exit 硬退(不走优雅停/不关 stdin,
    #    复刻被任务管理器杀的现场), 孙进程不许活——EOF 自停救不了卡死进程,
    #    这例锁的是内核兜底层。非 Windows 无作业对象机制, 跳过。
    if os.name == "nt":
        import ctypes
        import subprocess as sp
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "sleeper.py").write_text(
                "import os, subprocess, sys, time\n"
                "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
                "sub = subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(300)'])\n"
                "open(sys.argv[2], 'w').write(str(sub.pid))\n"   # 孙孙: 验继承成员资格
                "time.sleep(300)\n", encoding="utf-8")
            (td / "supervisor.py").write_text(
                "import os, queue, sys, time\n"
                "from pathlib import Path\n"
                "from icefrag.procmode import DeviceProc\n"
                f"p = DeviceProc('x', queue.Queue(), cmd=[sys.executable, "
                f"{str(td / 'sleeper.py')!r}, {str(td / 'grand.pid')!r}, "
                f"{str(td / 'sub.pid')!r}])\n"
                "p.start()\n"
                "time.sleep(1)\n"                    # 等 spawn+挂作业落定
                f"Path({str(td / 'assigned.flag')!r}).write_text('1')\n"  # A 由此开始验活
                "time.sleep(3)\n"                    # 留窗口给 A 验「孙进程活着」
                "os._exit(0)\n", encoding="utf-8")   # 硬死: 跳过一切清理
            root = Path(__file__).resolve().parent.parent
            err_f = open(td / "sup.err", "wb")       # stderr 走文件: 父端不阻塞
            sup = sp.Popen([sys.executable, str(td / "supervisor.py")],
                           cwd=root,
                           env=dict(os.environ, PYTHONPATH=str(root)),
                           stdout=sp.DEVNULL, stderr=err_f)
            err_f.close()

            def _pid_alive(pid: int) -> bool:
                k32 = ctypes.windll.kernel32
                h = k32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFO
                if not h:
                    return False
                code = ctypes.c_uint32()
                k32.GetExitCodeProcess(h, ctypes.byref(code))
                k32.CloseHandle(h)
                return code.value == 259             # STILL_ACTIVE

            def _sup_err() -> str:
                return (td / "sup.err").read_text(errors="replace")[-800:]

            end = time.monotonic() + 10
            while not (td / "grand.pid").exists():
                if time.monotonic() > end or sup.poll() is not None:
                    raise AssertionError(f"监督者没拉起孙进程(stderr 尾): "
                                         f"{_sup_err()}")
                time.sleep(0.1)
            grand_pid = int((td / "grand.pid").read_text())
            end = time.monotonic() + 10
            while not (td / "sub.pid").exists():
                if time.monotonic() > end:
                    raise AssertionError("孙孙进程没起(pid 文件缺席)")
                time.sleep(0.1)
            sub_pid = int((td / "sub.pid").read_text())
            end = time.monotonic() + 10
            while not (td / "assigned.flag").exists():
                if time.monotonic() > end or sup.poll() is not None:
                    raise AssertionError(
                        f"B 没写标记就没了(returncode={sup.poll()}, "
                        f"stderr 尾): {_sup_err()}")
                time.sleep(0.1)
            _wait(lambda: _pid_alive(grand_pid) and _pid_alive(sub_pid),
                  timeout=3, what="硬死前两代孙进程都活着(提前死=挂作业误杀)")
            sup.wait(timeout=30)
            _wait(lambda: not _pid_alive(grand_pid) and not _pid_alive(sub_pid),
                  timeout=10, what="监督者硬死后两代孙进程都陪葬")

    print("test_proc: 11/11 全过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
