# -*- coding: utf-8 -*-
"""配置与用户记忆的持久化: business.yaml + aliases.json(中控台改名记忆)。

业务层: 开发者只声明 dataclass(带默认值)+FIELD_META(中文名/控件类型), 本模块
负责落盘/载入/缺字段补默认 —— business.yaml 首次运行自动生成, 用户改了就记住。

写入一律原子(临时文件+replace, 崩了不留半个文件); 损坏先备份 .bak 再用默认值
—— 绝不静默吞掉用户的参数文件(March7th 的教训)。atomic_write/backup_broken
是全包公共持久化设施(settings 的 scaffold.toml 也走它)。
"""
from __future__ import annotations

import dataclasses
import json
import os
import time

import yaml

from . import ROOT

PATH = ROOT / "business.yaml"
ALIAS_PATH = ROOT / "aliases.json"
UI_PATH = ROOT / "ui.json"


def atomic_write(path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def backup_broken(path) -> None:
    stamp = time.strftime("%m%d_%H%M%S")
    path.rename(path.with_suffix(f"{path.suffix}.{stamp}.bak"))


def load(business_cls):
    """business_cls: business.BusinessConfig(或任意带字段的 dataclass)。"""
    data = {}
    if PATH.exists():
        try:
            data = yaml.safe_load(PATH.read_text("utf-8")) or {}
        except yaml.YAMLError:
            backup_broken(PATH)               # 损坏文件留着, 用默认值继续
        if not isinstance(data, dict):         # 合法 yaml 但不是映射(手改手滑)
            backup_broken(PATH)
            data = {}
    cfg = business_cls(**{k: v for k, v in data.items()
                          if k in {f.name for f in business_cls.__dataclass_fields__.values()}})
    return cfg


def save(cfg) -> None:
    atomic_write(PATH, yaml.safe_dump(
        dataclasses.asdict(cfg), allow_unicode=True, sort_keys=True))


def reload_into(cfg) -> None:
    """business.yaml 有变化就地把字段刷进已存在的 cfg 实例(原地改, 引用方无感)。

    进程形态(ADR 0004)用: 子进程各持一份 cfg, 中控台弹窗改的是 yaml 文件,
    轮循环每轮调一次 = 弹窗改完下一轮生效(与线程版共享对象的体验对齐)。
    """
    fresh = load(type(cfg))
    for f in dataclasses.fields(cfg):
        if hasattr(fresh, f.name):
            setattr(cfg, f.name, getattr(fresh, f.name))


def load_aliases() -> dict:
    """中控台改名记忆(aliases.json): ident→别名。缺席=空表;
    损坏/非映射先备份再用空表(与 business.yaml 同款纪律)。"""
    if not ALIAS_PATH.exists():
        return {}
    try:
        data = json.loads(ALIAS_PATH.read_text("utf-8"))
    except Exception:
        backup_broken(ALIAS_PATH)
        return {}
    if not isinstance(data, dict):
        backup_broken(ALIAS_PATH)
        return {}
    return data


def save_aliases(d: dict) -> None:
    atomic_write(ALIAS_PATH, json.dumps(d, ensure_ascii=False, indent=1))


def load_ui() -> dict:
    """操作者外观偏好(ui.json, 如主题): 机器本地记忆, 摆 exe/项目旁, 不随发版
    覆盖——与项目配置(scaffold.toml)/业务配置(business.yaml)分家。缺席=空表;
    损坏/非映射先备份再用空表(与 aliases.json 同款纪律)。"""
    if not UI_PATH.exists():
        return {}
    try:
        data = json.loads(UI_PATH.read_text("utf-8"))
    except Exception:
        backup_broken(UI_PATH)
        return {}
    if not isinstance(data, dict):
        backup_broken(UI_PATH)
        return {}
    return data


def save_ui(d: dict) -> None:
    atomic_write(UI_PATH, json.dumps(d, ensure_ascii=False, indent=1))
