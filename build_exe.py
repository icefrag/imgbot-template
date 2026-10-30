# -*- coding: utf-8 -*-
"""发布链: PyInstaller onedir(源码冻结) + 潜影 bin/ + templates → 绿色 zip。

用法: uv run build_exe.py            (名字/版本取自 pyproject.toml)

产物:
  dist/<name>/            <name>.exe + _internal/(py 依赖全冻)
                          + templates/ + scaffold.toml   ← exe 旁, 用户可编辑
                          + bin/                          ← 潜影注入件(有则拷)
  dist/<name>-v<版本>.zip 绿色包, 目标机零 python

注意: bin/ 注入件会被 Defender 报毒, 发布机与目标机都需加排除目录。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMGBOT = ROOT.parent / "imgbot"


def main() -> int:
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    name, ver = meta["name"], meta["version"]
    print(f"[1] 打包 {name} v{ver}(onedir, 几分钟)…")
    r = subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--name", name,
        "--hidden-import", "task", "--hidden-import", "business",
        "--collect-all", "ttkbootstrap",
        "--collect-all", "rapidocr_onnxruntime",
        str(ROOT / "console.py"),
    ], cwd=ROOT)
    if r.returncode != 0:
        return r.returncode

    app = ROOT / "dist" / name
    print("[2] 摆 exe 旁的用户区(templates/scaffold.toml)…")
    shutil.copytree(ROOT / "templates", app / "templates", dirs_exist_ok=True)
    src_toml = ROOT / "scaffold.toml"               # 源配置(开发者默认值)进包;
    if src_toml.exists():                            # 不能 settings.save —— 它写源 ROOT
        shutil.copy(src_toml, app / "scaffold.toml")
    bin_src = IMGBOT / "imgbot" / "dx" / "bin"
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


if __name__ == "__main__":
    sys.exit(main())
