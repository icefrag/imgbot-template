# -*- coding: utf-8 -*-
"""脚手架层配置(scaffold.toml): 框架自己的, 固定 schema, 与业务配置(business.py)分离。

开发者可改默认值; 用户经设置弹窗改的部分启动时读、保存时写回。
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields

import tomli_w

from . import ROOT

PATH = ROOT / "scaffold.toml"


@dataclass
class ScaffoldConfig:
    # 目标与通道
    backend: str = "window"            # "window"(PC 潜影/PrintWindow) | "adb"(模拟器)
    window_class: str = ""             # window 端: 热键收编的类名过滤(空=不过滤)
    display: str = "normal"            # 通道三件套, 见 docs/接口说明.md 通道模式
    mouse: str = "normal"
    keypad: str = "normal"
    adb_serials: list[str] = field(default_factory=list)   # adb 端: 预置序列号(空=自动发现)

    # 热键收编
    hotkey_vk: int = 0x78              # F9(VK_F1=0x70 递增)
    pick_mode: str = "hover"           # hover=鼠标下窗口 | focus=活动窗口的焦点子窗口

    # 运行策略
    max_restarts: int = 3              # 任务异常自动重开次数, 连败熔断
    loop_interval: float = 1.0         # 任务轮间隔秒

    # 外观
    window_size: list[int] = field(default_factory=lambda: [1280, 800])
    left_ratio: float = 0.45           # 左列(目标表)占宽比例
    theme: str = "darkly"              # ttkbootstrap 主题名


def load() -> ScaffoldConfig:
    cfg = ScaffoldConfig()
    if PATH.exists():
        raw = tomllib.loads(PATH.read_text("utf-8"))
        known = {f.name: f for f in fields(ScaffoldConfig)}
        for k, v in raw.items():
            if k in known:                       # 未知键忽略(向前兼容)
                setattr(cfg, k, v)
    return cfg


def save(cfg: ScaffoldConfig) -> None:
    PATH.write_text(
        tomli_w.dumps({f.name: getattr(cfg, f.name) for f in fields(cfg)}),
        encoding="utf-8")
