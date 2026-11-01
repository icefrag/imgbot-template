# -*- coding: utf-8 -*-
"""★ auto_farm_adb 业务配置: 打怪参数(通知栏阴影靶)。"""
from __future__ import annotations

from dataclasses import dataclass

FIELD_META = {
    "attack_wait": ("击杀等待秒", "entry"),
    "max_kills": ("最大击杀数(0=无限)", "entry"),
    "tap_x": ("点击 X(0=屏幕中心)", "entry"),
    "tap_y": ("点击 Y(0=屏幕中心)", "entry"),
}


@dataclass
class BusinessConfig:
    attack_wait: float = 8.0          # 出招后等"怪"消失(面板收起)的超时
    max_kills: int = 0                # 0 = 无限挂机
    tap_x: int = 0                    # 点击点位(面板空白处; 0=屏幕中心)
    tap_y: int = 0
