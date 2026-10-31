# -*- coding: utf-8 -*-
"""脚手架层配置(scaffold.toml): 框架自己的, 固定 schema, 与业务配置(business.py)分离。

开发者可改默认值; 用户经设置弹窗改的部分启动时读、保存时写回。
"""
from __future__ import annotations

import sys
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

    # 拟人键鼠(dsl click/dblclick 的默认, 调用处可单次覆盖)
    human_mouse: bool = True           # True=贝塞尔轨迹+随机停顿; False=瞬移急点(速度优先)
    click_jitter: int = 3              # 落点抖动 ±px(0=关)
    click_settle_ms: list[int] = field(default_factory=lambda: [60, 160])   # 到位停顿区间

    # 运行策略
    max_restarts: int = 3              # 任务异常自动重开次数, 连败熔断

    # 外观
    window_size: list[int] = field(default_factory=lambda: [1280, 800])
    left_ratio: float = 0.45           # 左列(目标表)占宽比例
    theme: str = "darkly"              # ttkbootstrap 主题名
    idle_timeout: int = 0              # 无进展看门狗秒数(0=关): find/wait 命中与
                                       # 点击算进展, 超时停任务留痕(防整夜卡死)


def load() -> ScaffoldConfig:
    cfg = ScaffoldConfig()
    if PATH.exists():
        try:
            raw = tomllib.loads(PATH.read_text("utf-8"))
        except tomllib.TOMLDecodeError:            # 损坏: 备份后用默认值
            from .store import _backup_broken
            _backup_broken(PATH)
            raw = {}
        known = {f.name: f for f in fields(ScaffoldConfig)}
        for k, v in raw.items():
            if k in known:                       # 未知键忽略(向前兼容)
                setattr(cfg, k, v)
    return cfg


def save(cfg: ScaffoldConfig) -> None:
    if getattr(sys, "frozen", False):
        return          # 发布形态: 脚手架配置编译期定死, 用户侧不可改
    from .store import _atomic_write
    _atomic_write(PATH, tomli_w.dumps(
        {f.name: getattr(cfg, f.name) for f in fields(cfg)}))
