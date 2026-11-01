# -*- coding: utf-8 -*-
"""发布链(通用): PyInstaller onedir + 潜影 bin/ + templates → 绿色 zip。

薄项目根的 build_exe.py 是两行包装; ROOT = 当前项目目录(uv run 的 cwd)。
潜影 bin/ 从已安装的 imgbot 包内取(引擎 wheel 已含, 见 make_skeleton)。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path.cwd()


def _ocr_ok() -> bool:
    """子进程探针: onnxruntime 是原生 DLL 包, 缺 VC++ 运行库的机器 import 直接
    段错误(0xC0000005, PyInstaller 的 collect_all 就这么陪葬过)。探崩了降级
    不含 OCR 打包, 不让整条 build 死在这。"""
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import rapidocr_onnxruntime"],
            capture_output=True, timeout=180)
        return r.returncode == 0
    except Exception:
        return False


def main() -> int:
    import imgbot
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    name, ver = meta["name"], meta["version"]
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--name", name,
        "--hidden-import", "task", "--hidden-import", "business",
        "--collect-all", "ttkbootstrap",
        "--collect-data", "imgbot",          # 潜影 bin/ 随包进 _internal
    ]
    if _ocr_ok():
        args += ["--collect-all", "rapidocr_onnxruntime"]
    else:
        print("[warn] 本机 rapidocr_onnxruntime 导入崩溃(多半缺 VC++ 2015-2022 x64 运行库),")
        print("       exe 将不含 OCR —— 任务用到 ocr()/find_str() 需先装运行库再重打包")
    icon = ROOT / "assets" / "icon.ico"
    if icon.exists():  # 项目自带图标: exe 文件图标 + 摆进用户区(console 运行时 iconbitmap 读它)
        args += ["--icon", str(icon)]
        print(f"[0] 图标: {icon}")
    print(f"[1] 打包 {name} v{ver}(onedir, 几分钟)…")
    r = subprocess.run(args + [str(ROOT / "console.py")], cwd=ROOT)
    if r.returncode != 0:
        return r.returncode

    app = ROOT / "dist" / name
    print("[2] 摆 exe 旁的用户区(templates)…")
    shutil.copytree(ROOT / "templates", app / "templates", dirs_exist_ok=True)
    if icon.exists():
        shutil.copytree(ROOT / "assets", app / "assets", dirs_exist_ok=True)
    bin_src = Path(imgbot.__file__).parent / "dx" / "bin"
    if bin_src.exists():
        print("[3] 拷潜影注入件 bin/…")
        shutil.copytree(bin_src, app / "bin", dirs_exist_ok=True)

    print("[4] 压绿色 zip…")
    zip_path = ROOT / "dist" / f"{name}-v{ver}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(app.rglob("*")):
            zf.write(p, p.relative_to(app.parent))
    print(f"完成: {zip_path}")
    print(f"运行: {app / (name + '.exe')}(Defender 需排除 bin/ 目录)")
    return 0
