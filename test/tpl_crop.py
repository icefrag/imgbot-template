# -*- coding: utf-8 -*-
"""模板裁剪: 截当前鼠标下窗口 → 终端输入框选(客户区坐标 x1,y1,x2,y2) → 存 PNG。

图色素材制作的兜底工具(pixpick 的命令行平替)。
用法: uv run python test/tpl_crop.py 输出名 [窗口类名]
  交互: 输入四坐标(空格分隔) → 存 templates/输出名.png; 输入 q 退出。
"""
import ctypes
import ctypes.wintypes as wt
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from imgbot.win32.capture import capture_client  # noqa: E402
from imgbot.win32.window import GameWindow  # noqa: E402


def window_under_mouse():
    return GameWindow.from_cursor(root=False).hwnd


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "tpl"
    cls = sys.argv[2] if len(sys.argv) > 2 else None
    hwnd = window_under_mouse()
    if not hwnd:
        print("鼠标下没有窗口")
        return 1
    win = GameWindow(hwnd)
    if cls:
        win = GameWindow.find(class_name=cls) or win
    cls_name, title, _rect = win.info()
    print(f"目标: hwnd=0x{win.hwnd:X} class={cls_name!r} title={title!r}")
    out_dir = Path(__file__).resolve().parents[1] / "templates"
    out_dir.mkdir(exist_ok=True)
    while True:
        raw = input(f"框选坐标 x1 y1 x2 y2 (客户区, q 退出): ").strip()
        if raw.lower() == "q":
            return 0
        try:
            x1, y1, x2, y2 = (int(v) for v in raw.split())
        except ValueError:
            print("  格式: 四个整数空格分隔")
            continue
        img = capture_client(win)
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            print("  区域在客户区外")
            continue
        out = out_dir / f"{name}.png"
        cv2.imwrite(str(out), crop)
        print(f"  已存 {out} ({crop.shape[1]}x{crop.shape[0]})")
        return 0


def dm_cls(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


if __name__ == "__main__":
    sys.exit(main())
