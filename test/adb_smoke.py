# -*- coding: utf-8 -*-
"""adb 端冒烟: 发现设备 → bind_adb_backend → DSL 全链(截图/找色/点击/键码/
等待) → 解绑。需要模拟器或真机在线(adb devices 可见)。

用法: uv run python test/adb_smoke.py [serial]   (缺省取第一台)
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # 项目根(icefrag/ 所在)
sys.path.insert(0, str(HERE / "auto_farm"))   # 借用 auto_farm 的 business

import business                        # noqa: E402  (auto_farm 的业务配置)
from icefrag import backends, dsl, settings   # noqa: E402


def first_serial() -> str:
    out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
    for ln in out.splitlines()[1:]:
        if ln.strip().endswith("device"):
            return ln.split()[0]
    raise SystemExit("没有在线设备(adb devices 为空), 先开模拟器/插真机")


def main() -> int:
    serial = sys.argv[1] if len(sys.argv) > 1 else first_serial()
    print(f"[1] 设备: {serial}")
    gcfg = settings.load()
    stop = threading.Event()
    logs = []
    ctx = backends.bind_adb_backend(
        serial, gcfg, business.BusinessConfig(),
        lambda t, lv="info": logs.append(t) or print(f"[{lv}] {t}"), stop)
    assert ctx.backend == "adb" and ctx.device and ctx.ops and ctx.dm
    dsl._bind(ctx)                     # DSL 顶层动词挂上(模拟 worker 行为)
    print("[2] 绑定 OK(ops 鸭子帧源 + device 方言)")

    h, w = ctx.dm.screen().shape[:2]
    print(f"[3] 截图 {w}x{h} OK(BGR 帧源通)")

    # 找色自证: 取屏幕中心像素色, 全屏 find_color 必命中中心区
    frame = ctx.dm.screen()
    cy, cx = h // 2, w // 2
    b, g, r = (int(v) for v in frame[cy, cx])
    hits = ctx.ops.find_color(f"{r:02X}{g:02X}{b:02X}", tol=8)
    assert hits, "find_color 全屏没找到自己取的色"
    print(f"[4] ops.find_color OK(命中 {len(hits)} 处, 中心色 #{r:02X}{g:02X}{b:02X})")

    dsl.click(cx, cy)                  # 点桌面中心(无害)
    print("[5] click→tap OK")
    ctx.device.keyevent(4)             # KEYCODE_HOME
    print("[6] ctx.device.keyevent(HOME) OK")
    ok = dsl.wait_color(f"{r:02X}{g:02X}{b:02X}", region=(cx - 50, cy - 50,
                                                          cx + 50, cy + 50),
                        timeout=3000)
    print(f"[7] wait_color OK={ok}(等待族/停止信号贯通)")
    dsl.shot("adb_smoke")
    print("[8] shot 留痕 OK(logs/shots)")

    backends.unbind(ctx)
    print("adb 冒烟: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
