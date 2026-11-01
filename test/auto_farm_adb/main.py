# -*- coding: utf-8 -*-
"""auto_farm_adb 入口(单开): 第一台在线设备直跑打怪循环。

用法: uv run python test/auto_farm_adb/main.py [serial]   (缺省第一台)
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE.parents[1]
os.environ["IMGBOT_TEMPLATE_ROOT"] = str(HERE)
sys.path.insert(0, str(SCAFFOLD))
sys.path.insert(0, str(HERE))

import business  # noqa: E402
from icefrag import backends, settings  # noqa: E402
from icefrag.store import load as biz_load  # noqa: E402
from icefrag.worker import Worker  # noqa: E402


def main() -> int:
    gcfg = settings.load()
    serial = sys.argv[1] if len(sys.argv) > 1 else _first_serial(gcfg)
    print(f"设备 {serial}, 3 秒后开始(Ctrl+C 停止)")
    time.sleep(3)

    logq = __import__("queue").Queue()
    biz = biz_load(business.BusinessConfig)
    w = Worker(serial, "adb", gcfg, biz, logq)
    w.start()
    try:
        while w.alive or not logq.empty():
            try:
                _ident, text, level = logq.get(timeout=0.5)
                print(f"[{level}] {text}")
            except Exception:
                pass
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n停止…")
        w.stop()
    print(f"结束: state={w.state}")
    return 0


def _first_serial(gcfg) -> str:
    try:
        serials = backends.list_adb_serials(gcfg)
    except Exception as e:
        raise SystemExit(f"设备扫描失败: {e}(adb 在 PATH 吗?)")
    if not serials:
        raise SystemExit("没有在线设备(adb devices 为空), 先开模拟器/插真机")
    return serials[0]


if __name__ == "__main__":
    sys.exit(main())
