# -*- coding: utf-8 -*-
"""业务层配置读写: business.py 的 dataclass ↔ business.yaml。

开发者只声明 dataclass(带默认值)+FIELD_META(中文名/控件类型), 本模块负责
落盘/载入/缺字段补默认 —— business.yaml 首次运行自动生成, 用户改了就记住。

写入原子(临时文件+replace, 崩了不留半个文件); 损坏先备份 .bak 再用默认值
—— 绝不静默吞掉用户的参数文件(March7th 的教训)。
"""
from __future__ import annotations

import dataclasses
import os
import time

import yaml

from . import ROOT

PATH = ROOT / "business.yaml"


def _atomic_write(path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _backup_broken(path) -> None:
    stamp = time.strftime("%m%d_%H%M%S")
    path.rename(path.with_suffix(f"{path.suffix}.{stamp}.bak"))


def load(business_cls):
    """business_cls: business.BusinessConfig(或任意带字段的 dataclass)。"""
    data = {}
    if PATH.exists():
        try:
            data = yaml.safe_load(PATH.read_text("utf-8")) or {}
        except yaml.YAMLError:
            _backup_broken(PATH)               # 损坏文件留着, 用默认值继续
        if not isinstance(data, dict):         # 合法 yaml 但不是映射(手改手滑)
            _backup_broken(PATH)
            data = {}
    cfg = business_cls(**{k: v for k, v in data.items()
                          if k in {f.name for f in business_cls.__dataclass_fields__.values()}})
    return cfg


def save(cfg) -> None:
    _atomic_write(PATH, yaml.safe_dump(
        dataclasses.asdict(cfg), allow_unicode=True, sort_keys=True))
