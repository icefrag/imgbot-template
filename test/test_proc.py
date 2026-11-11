# -*- coding: utf-8 -*-
"""进程形态(procmode)离线自检: 设备进程协议/两段停止/退出码映射/静默审计/
参数重读。假子进程=临时 py 文件(不依赖真设备真业务)。
跑法: uv run test/test_proc.py
"""
import dataclasses
import queue
import sys
import tempfile
import time
from pathlib import Path

from icefrag import store
from icefrag.procmode import DeviceProc


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
    p = DeviceProc("127.0.0.1:5555", None, None, logq, title="假·5555", cmd=child)
    p.start()
    _wait(lambda: p.state == "RUNNING", what="RUNNING")
    _wait(lambda: any("点了啥" in t for _i, t, _l in _drain(logq)), what="log行")
    assert p.alive and p.coarse == "running"
    assert p.display == "运行中"
    p.stop(join_s=10)
    _wait(lambda: not p.alive, what="优雅退出")
    assert p.state == "STOPPED" and p.coarse == "done", p.state

    # ② 退出码映射: 退 3 无 st 行 → FUSED 标红
    child = _fake_child("import sys; sys.exit(3)\n")
    p = DeviceProc("x", None, None, logq, cmd=child)
    p.start()
    _wait(lambda: not p.alive, what="退3")
    assert p.state == "FUSED" and p.coarse == "error", p.state

    # ③ 崩溃输出(非 JSON 行)按 error 转发; 未知码 → ERROR
    child = _fake_child(
        "import sys; print('Traceback (most recent call last):'); sys.exit(1)\n")
    p = DeviceProc("x", None, None, logq, cmd=child)
    p.start()
    _wait(lambda: not p.alive, what="退1")
    assert p.state == "ERROR", p.state
    assert any(lv == "error" and "Traceback" in t
               for _i, t, lv in _drain(logq)), "崩溃行没按 error 转"

    # ④ 硬杀: 不读 stdin 的赖死进程, 优雅超时后 taskkill 树杀
    child = _fake_child("import time; time.sleep(300)\n")
    p = DeviceProc("x", None, None, logq, cmd=child)
    p.start()
    _wait(lambda: p.alive, what="赖死进程活着")
    t0 = time.monotonic()
    p.stop(join_s=2)
    _wait(lambda: not p.alive, what="硬杀")
    assert time.monotonic() - t0 < 30, "硬杀拖太久"

    # ⑤ 静默审计: 活着但不说话 → 判卡死强杀标红, 不自动重拉
    child = _fake_child(
        "import sys,time\n"
        "sys.stdout.write('x\\n'); sys.stdout.flush(); time.sleep(300)\n")
    p = DeviceProc("x", None, None, logq, cmd=child)
    p.start()
    _wait(lambda: p.last_line_ts > 0, what="说过一句话")
    time.sleep(0.6)                              # 静默窗口走完才许判卡死
    p.audit_silence(silence_s=0.5)
    _wait(lambda: not p.alive, what="审计强杀")
    assert p.state == "ERROR" and "卡死" in p.last_info, p.last_info
    assert p.coarse == "error"

    # ⑥ reload_into: 文件改动原地刷进既有实例(引用不变, 字段更新)
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
    finally:
        store.PATH = old_path

    print("test_proc: 6/6 全过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
