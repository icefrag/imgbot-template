# -*- coding: utf-8 -*-
"""业务层配置读写: business.py 的 dataclass ↔ business.yaml。

开发者只声明 dataclass(带默认值)+FIELD_META(中文名/控件类型), 本模块负责
落盘/载入/缺字段补默认 —— business.yaml 首次运行自动生成, 用户改了就记住。
"""
from __future__ import annotations

import yaml

from . import ROOT

PATH = ROOT / "business.yaml"


def load(business_cls):
    """business_cls: business.BusinessConfig(或任意带字段的 dataclass)。"""
    data = {}
    if PATH.exists():
        data = yaml.safe_load(PATH.read_text("utf-8")) or {}
    cfg = business_cls(**{k: v for k, v in data.items()
                          if k in {f.name for f in business_cls.__dataclass_fields__.values()}})
    return cfg


def save(cfg) -> None:
    import dataclasses
    PATH.write_text(
        yaml.safe_dump(dataclasses.asdict(cfg), allow_unicode=True, sort_keys=True),
        encoding="utf-8")
