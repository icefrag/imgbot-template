# -*- coding: utf-8 -*-
"""★ auto_farm 业务配置: 挂机参数。"""
from __future__ import annotations

from dataclasses import dataclass

FIELD_META = {
    "attack_wait": ("击杀等待秒", "entry"),
    "coin_timeout": ("捡币超时秒", "entry"),
    "max_kills": ("最大击杀数(0=无限)", "entry"),
}


@dataclass
class BusinessConfig:
    attack_wait: float = 10.0          # 点击怪物后等它死的超时
    coin_timeout: float = 6.0          # 等金币掉落的超时
    max_kills: int = 0                 # 0 = 无限挂机
