# -*- coding: utf-8 -*-
"""骨架打包: 薄项目母版 + 双 whl + 手册 → dist/skeleton-v<版本>.zip。

用法: uv run scripts/make_skeleton.py
前置: 无 —— 本脚本自己跑两仓的 uv build(引擎仓 wheel 含潜影 bin/, 由其
pyproject 的 hatch artifacts 配置保证)。

产物(用户解压 → 改 name → uv sync → 写 task/business, 全程零 GitHub):
  skeleton/
  ├── console.py / build_exe.py             薄入口(设 IMGBOT_TEMPLATE_ROOT)
  ├── business.py / task.py                 出厂示例, 用户覆写
  ├── scaffold.toml / pyproject.toml        配置(依赖指向 libs/ 的 whl)
  ├── libs/icefrag-*.whl + imgbot-*.whl     脚手架(开源) + 引擎(现开源, ②后闭源)
  ├── tools/pick_probe.py / templates/
  ├── docs/DSL语法清单.md
  ├── AGENTS.md                       # 给对方 AI 代理的军规(根目录, 工具自动发现)
  └── README.md                       # = 使用手册(ASCII 名, 双击即读)

发版铁律: zip 发出去之前, 按用户姿势自测(干净目录解压 → uv sync → 冒烟)。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMGBOT = ROOT.parent / "imgbot"
DIST = ROOT / "dist"

# 薄项目 pyproject 模板(占位符 SCAFFOLD_WHL/ENGINE_WHL 随发版注入真实文件名)
PYPROJECT_TPL = """\
[project]
name = "my-script"            # ← 改成你的项目名(英文, 打 exe 用)
version = "0.1.0"
description = "我的挂机项目"
requires-python = ">=3.12,<3.15"   # 3.15 无 onnxruntime/opencv 轮子, 封顶防 uv 抢最新
dependencies = [
    "icefrag",
    "imgbot[ocr]",
]

[tool.uv.sources]
icefrag = { path = "libs/SCAFFOLD_WHL" }
imgbot = { path = "libs/ENGINE_WHL" }

[[tool.uv.index]]
url = "https://pypi.tuna.tsinghua.edu.cn/simple"
default = true

[dependency-groups]
dev = [
    "pyinstaller>=6.22.3",
]

[tool.uv]
python-install-mirror = "https://mirror.nju.edu.cn/github-release/astral-sh/python-build-standalone"
"""


def _build(repo: Path, label: str) -> None:
    print(f"[build] {label}: uv build…")
    r = subprocess.run(["uv", "build"], cwd=repo)
    if r.returncode != 0:
        sys.exit(f"{label} uv build 失败")


def _latest_whl(dist: Path, prefix: str) -> Path:
    hits = sorted(dist.glob(f"{prefix}-*.whl"), key=lambda p: p.stat().st_mtime)
    if not hits:
        sys.exit(f"{dist} 里没有 {prefix}-*.whl, 先跑 uv build")
    return hits[-1]


def main() -> int:
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    ver = meta["version"]
    _build(ROOT, "icefrag")
    _build(IMGBOT, "imgbot(引擎)")
    scaffold_whl = _latest_whl(DIST, "icefrag")
    engine_whl = _latest_whl(IMGBOT / "dist", "imgbot")
    print(f"[whl] {scaffold_whl.name}\n[whl] {engine_whl.name}")

    stage = DIST / "skeleton"
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "libs").mkdir(parents=True)
    (stage / "tools").mkdir()
    (stage / "docs").mkdir()
    (stage / "templates").mkdir()
    (stage / "logs").mkdir()

    for f in ("console.py", "build_exe.py", "business.py",
              "task.py", "scaffold.toml"):
        shutil.copy2(ROOT / f, stage / f)
    shutil.copy2(ROOT / "skel" / "AGENTS.md", stage / "AGENTS.md")  # AI 军规(工具自动发现)
    shutil.copy2(ROOT / "test" / "pick_probe.py", stage / "tools" / "pick_probe.py")
    shutil.copy2(ROOT / "docs" / "DSL语法清单.md", stage / "docs" / "DSL语法清单.md")
    (stage / "README.md").write_text(
        (ROOT / "docs" / "脚手架使用手册.md").read_text("utf-8"), encoding="utf-8")
    shutil.copy2(scaffold_whl, stage / "libs" / scaffold_whl.name)
    shutil.copy2(engine_whl, stage / "libs" / engine_whl.name)
    (stage / "pyproject.toml").write_text(
        PYPROJECT_TPL.replace("SCAFFOLD_WHL", scaffold_whl.name)
                     .replace("ENGINE_WHL", engine_whl.name), encoding="utf-8")
    (stage / ".python-version").write_text("3.12\n", encoding="utf-8")  # 钉作者实测版, 防抢最新
    (stage / "templates" / "素材放这里.txt").write_text(
        "图色素材 PNG 放本目录(wait_pic/find_tap 按文件名引用)。\n", encoding="utf-8")
    (stage / "logs" / "运行产物留痕.txt").write_text(
        "运行产物(日志/截图留痕)自动生成, 可删。\n", encoding="utf-8")

    zip_path = DIST / f"skeleton-v{ver}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(stage.rglob("*")):
            zf.write(p, Path("skeleton") / p.relative_to(stage))
    print(f"完成: {zip_path}")
    print("发版铁律: 干净目录解压 → uv sync → 冒烟通过 → 才发群")
    return 0


if __name__ == "__main__":
    sys.exit(main())
