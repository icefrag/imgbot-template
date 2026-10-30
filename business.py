# -*- coding: utf-8 -*-
"""★ 开发者写: 业务配置(你的功能参数)。

规则:
- 一个 dataclass = 全部业务参数, 字段带默认值(= business.yaml 的初始值);
- FIELD_META 声明中文名与控件类型("entry"/"combo:选项1|选项2"), 设置弹窗自动生成;
- 代码里经 ctx.cfg.字段名 直用; 弹窗改值自动落盘 business.yaml。
"""
from __future__ import annotations

from dataclasses import dataclass

FIELD_META = {
    "target_text": ("目标文字", "entry"),
    "max_rounds": ("最大轮数", "entry"),
    "click_delay": ("点击间隔秒", "entry"),
}


@dataclass
class BusinessConfig:
    target_text: str = "hello"         # 示例: 要注入的文本
    max_rounds: int = 5                # 示例: 任务最多跑几轮
    click_delay: float = 0.5           # 示例: 两次动作间隔
