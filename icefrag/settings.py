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
    display: str = "normal"            # 通道三件套, 见 docs/icefrag开发手册.md 通道选择速查
    mouse: str = "normal"
    keypad: str = "normal"
    fake_active: bool = False          # 绑定后假激活: 治"唯独点击无反应", 需 dx 系通道
    hook_keystate: bool = False        # 键状态钩子: 治"键盘消息无反应", 需键盘 dx
    hide_module: bool = False          # 注入件模块隐身: 反作弊扫模块时, 需 dx 系通道
    adb_serials: list[str] = field(default_factory=list)   # adb 端: 预置序列号(空=自动发现)

    # 热键收编
    hotkey: str = "f9"                 # 启动热键: f1~f12/pause/scrolllock/home/end/insert/delete
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
    idle_timeout: int = 0              # 无进展看门狗秒数(0=关): find/wait 命中与
                                       # 点击算进展, 超时停任务留痕(防整夜卡死)


def load() -> ScaffoldConfig:
    cfg = ScaffoldConfig()
    if PATH.exists():
        try:
            raw = tomllib.loads(PATH.read_text("utf-8"))
        except tomllib.TOMLDecodeError:            # 损坏: 备份后用默认值
            from .store import backup_broken
            backup_broken(PATH)
            raw = {}
        known = {f.name: f for f in fields(ScaffoldConfig)}
        for k, v in raw.items():
            if k in known:                       # 未知键忽略(向前兼容)
                setattr(cfg, k, v)
    return cfg


def save(cfg: ScaffoldConfig) -> None:
    # 冻结态照写(PATH 恒 exe 目录, 见 __init__): 2026-11-04 定案对齐「scaffold.toml
    # 摆 exe 旁用户可编辑」契约——旧"编译期定死"静默 no-op 会让 exe 设置弹窗改键
    # 重开即丢(左列宽度比例 0.6 案), 且与 load() 读 exe 旁文件自相矛盾
    from .store import atomic_write
    atomic_write(PATH, tomli_w.dumps(
        {f.name: getattr(cfg, f.name) for f in fields(cfg)}))


# 设置弹窗单一来源(与 business.FIELD_META 同款思路): 字段 → (中文名, 控件, 适用端)。
# 控件: "entry" | "combo:a|b|c" | "hotkey"; 适用端: "window" | "adb" | "both";
# 不在此表的字段不进弹窗(冷门项手改 scaffold.toml)。build_docs 对账断言保
# 此表只引用真实字段——加字段改名后忘了登记, 生成手册时即报错。
FIELD_META = {
    "hotkey": ("启动热键", "hotkey", "window"),
    "display": ("图色通道", "combo:normal|gdi|gdi2|dx", "window"),
    "mouse": ("鼠标通道", "combo:normal|windows|windows2|dx", "window"),
    "keypad": ("键盘通道", "combo:normal|windows|dx", "window"),
    "fake_active": ("后台假激活", "combo:否|是", "window"),
    "hook_keystate": ("键状态钩子", "combo:否|是", "window"),
    "hide_module": ("隐藏模块", "combo:否|是", "window"),
    "window_size": ("窗体尺寸",
                    "combo:[960, 600]|[1280, 800]|[1600, 900]|[1920, 1080]",
                    "both"),
    "left_ratio": ("左列宽度比例", "entry", "both"),
}

# 绑定项悬浮讲解(? 卡片, console_ui 渲染): 通道=取值三列表(values), 开关=症状
# 处方(lines); 与 docs/icefrag开发手册.md 通道章同源, 语义大改两边同步。
# 键集断言拦"key 拼错→悬浮卡静默不出现"(30b01af 修 CLASSIC_COMBOS 的同款病)。
BIND_HELP = {
    "display": ("图色通道 —— 截图从哪来", [
        ("normal", "前台截屏裁剪", "目标必须前台可见"),
        ("gdi", "PrintWindow 后台截图", "默认首选, GDI 窗口通吃"),
        ("gdi2", "兼容模式, 慢但稳", "gdi 截图不刷新时换它"),
        ("dx", "注入件截帧(OpenGL 已通)", "GDI 截不到的游戏; D3D9 调试中, 不通会明确报错"),
    ], None),
    "mouse": ("鼠标通道 —— 点击怎么发出去", [
        ("windows", "宿主侧 PostMessage", "门槛低, 普通窗口首选"),
        ("dx", "注入件进程内合成", "消息要过游戏输入检查的目标"),
        ("windows2", "dx 消息 + 虚拟光标锁", "点击总落到真鼠标处/偏移"),
        ("normal", "SendInput 真事件", "最后手段, 动真光标且须前台"),
    ], None),
    "keypad": ("键盘通道 —— 按键怎么发出去", [
        ("windows", "PostMessage 消息键盘(带扫描码)", "默认首选; 轮询型游戏免疫→换 dx"),
        ("dx", "注入件合成", "配合键状态钩子治无反应"),
        ("normal", "SendInput 真事件", "最后手段, 动真键盘"),
    ], None),
    "fake_active": ("后台假激活 —— 治什么病", None, [
        ("说明", "让后台窗口被游戏视为激活, 绕过点击处理里的激活门槛"),
        ("症状", "移动/键盘都正常, 唯独点击全无反应"),
        ("要求", "任一 dx 系通道(注入件在场)才生效, 否则跳过并留日志"),
    ]),
    "hook_keystate": ("键状态钩子 —— 治什么病", None, [
        ("说明", "钩住 GetAsyncKeyState。游戏靠轮询按键状态、不收消息时才需要"),
        ("症状", "键盘消息全无反应(连键都打不出)"),
        ("要求", "键盘通道选 dx(注入件在场), 否则跳过并留日志"),
    ]),
    "hide_module": ("隐藏模块 —— 治什么病", None, [
        ("说明", "把注入件从目标进程的模块列表里藏起来"),
        ("场景", "反作弊扫进程模块列表时; 绑定后调一次即可"),
        ("要求", "需 dx 系通道(注入件在场), 否则跳过并留日志"),
        ("平时", "保持「否」"),
    ]),
}

assert set(BIND_HELP) <= set(FIELD_META), \
    f"BIND_HELP 引用了 FIELD_META 外的键(拼错?): {set(BIND_HELP) - set(FIELD_META)}"

# 经典组合: 症状 → 配方。设置弹窗"一键套用"与手册通道章"对症速查表"的
# 单一数据源(顺序=伤害递增, 能用上面的别用下面的)。
CLASSIC_COMBOS = [
    ("起步首选 · 普通窗口后台挂机",
     {"display": "gdi", "mouse": "windows", "keypad": "windows"}),
    ("移动/键盘正常, 唯独点击全无反应",
     {"display": "gdi", "mouse": "dx", "keypad": "windows", "fake_active": True}),
    ("键盘消息全无反应(消息免疫)",
     {"display": "gdi", "mouse": "dx", "keypad": "dx", "hook_keystate": True}),
    ("点击坐标总落到真鼠标处/偏移",
     {"display": "gdi", "mouse": "windows2", "keypad": "windows"}),
    ("GDI 截图黑屏/冻结(D3D/GL 游戏)",
     {"display": "dx", "mouse": "dx", "keypad": "windows"}),
]


def coerce(cur, text: str):
    """按当前值类型转换弹窗文本(脚手架/业务两个设置弹窗共用)。"""
    if isinstance(cur, bool):
        return text.strip().lower() in ("1", "true", "yes", "是")
    if isinstance(cur, int):
        return int(text)
    if isinstance(cur, float):
        return float(text)
    if isinstance(cur, list):
        return [int(x) for x in text.strip("[]").split(",") if x.strip()]
    return text
