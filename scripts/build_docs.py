# -*- coding: utf-8 -*-
"""icefrag 开发手册生成器 → 三产物(给脚本开发者, 骨架 zip 的 README 即 md 版)。

- docs/icefrag开发手册.md    给 AI / 骨架 README(全文: 上手+业务+PC 窗口开发+
  手机(adb)开发+配置+通道+保障+打包+FAQ)
- docs/icefrag开发手册.html  单文件版(浏览器直接开)
- docs/icefrag开发手册.chm   编译版(便携 hhc 在 D:/tools/hhw; 内部路径 ASCII, 名字 GBK)

防漂移(违者直接退出, 与代码对账):
- 命令清单: icefrag 命令签名内省 icefrag/dsl.py, 大漠直通签名内省 imgbot
  DmSoft 本尊; GROUPS/DM_GROUPS 漏命令/多命令报错;
- adb 方言表(四章): 签名内省 imgbot AdbTarget(ctx.device 本尊);
  DEVICE_DESC 少写/多写报错;
- 配置表: 默认值/类型从 ScaffoldConfig dataclass 内省; CFG_DESC 少写/多写键报错。
散文章节手排 PROSE(唯一文档源, 手写手册已退役)。

用法: uv run scripts/build_docs.py
变更 icefrag/dsl.py 或 icefrag/settings.py 后必须重跑(AGENTS.md 规则)。
"""
from __future__ import annotations

import dataclasses
import inspect
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from icefrag import dsl, settings as scfg  # noqa: E402
from imgbot.dmsoft import DmSoft  # noqa: E402
from imgbot.target import AdbTarget  # noqa: E402

DOCS = ROOT / "docs"
TITLE = "icefrag 开发手册"
CHM_NAME = "icefrag开发手册"

# ==================== icefrag 命令分组(签名内省 dsl) ====================
GROUPS = [
    ("键鼠(拟人)", ["click", "dblclick", "drag", "sleep"]),
    ("消息", ["log", "shot", "stopped"]),
    ("找点(单帧)", ["find_all"]),
    ("复合动作", ["find_tap", "tap_until_gone"]),
    ("等待(超时返 None/False)", ["wait_pic", "wait_pic_any", "wait_pic_gone",
                                "wait_color", "wait_color_gone", "wait_text"]),
    ("识字 / 找字(OCR)", ["ocr", "ocr_numbers", "find_str"]),
    ("导航(需 task.py 声明表)", ["go", "at"]),
    ("看门狗", ["progress"]),
]

# ==================== 大漠直通分组(签名内省 DmSoft 本尊) ====================
DM_GROUPS = [
    ("键鼠", ["MoveTo", "MoveR", "LeftClick", "LeftDoubleClick", "LeftDown",
            "LeftUp", "RightClick", "RightDown", "RightUp", "MiddleClick",
            "MiddleDown", "MiddleUp", "WheelDown", "WheelUp", "KeyPress",
            "KeyDown", "KeyUp", "KeyPressChar", "KeyDownChar", "KeyUpChar",
            "KeyPressStr", "SendString", "SendPaste", "GetCursorPos",
            "LockMouseRect"]),
    ("图色", ["Capture", "CapturePng", "CaptureJpg", "GetColor", "GetColorBGR",
            "CmpColor", "FindColor", "FindColorE", "FindColorEx", "FindPic",
            "FindPicE", "FindMultiColor", "GetColorNum", "IsDisplayDead"]),
    ("窗口", ["FindWindow", "FindWindowEx", "GetWindowClass", "GetWindowTitle",
            "GetWindowRect", "GetClientRect", "GetClientSize", "ClientToScreen",
            "ScreenToClient", "MoveWindow", "SetWindowState", "EnumWindow",
            "EnumWindowByProcess", "EnumWindowByProcessId",
            "GetWindowProcessId", "GetWindowProcessPath",
            "GetForegroundWindow"]),
    ("绑定与环境", ["BindWindow", "UnBindWindow", "ForceUnBindWindow",
                "GetBindWindow", "IsBind", "SwitchBindWindow", "EnableBind",
                "EnableFakeActive", "EnableRealMouse", "EnableRealKeypad",
                "EnableMouseSync", "EnableKeypadSync", "EnableSpeedDx",
                "EnableIme", "EnableKeypadMsg", "EnableMouseMsg",
                "EnableKeypadPatch", "SetDisplayDelay",
                "SetDisplayRefreshDelay"]),
    ("其他", ["LockInput", "LockDisplay", "GetFps", "HackSpeed", "SetAero",
            "DownCpu", "SetInputDm", "SetPath", "Ver", "GetLastError"]),
]

# ==================== adb 方言表(签名内省 imgbot AdbTarget = ctx.device) ====================
DEVICE_DESC = {
    "screenshot": "截当前设备帧(BGR ndarray); dsl 图色族同源, 留痕用 `shot()`",
    "save_screenshot": "截屏存文件, 返回 (宽, 高)",
    "tap": "裸点击(无拟人; 业务点击用 dsl `click`, 它管前摇+抖动)",
    "swipe": "原生滑动(x1,y1→x2,y2, ms)——dsl `drag` 的 adb 底座",
    "keyevent": "安卓键码按键(4=HOME 3=BACK 66=回车; 全表见 adb KEYCODE)",
    "shell": "adb shell 直通, 返回 str(dumpsys 类冷门事走这里)",
    "type_text": "中文注入(ADBKeyboard 广播); 首次自动装输入法, 用完自动还原",
    "start_app": "拉起应用(包名+Activity; 开局/重登线)",
    "stop_app": "强杀应用(包名; 熔断 on_fuse 重启游戏线)",
}

EXAMPLES = {
    "click": 'click(231, 347)                       # 拟人点击(轨迹+停顿+抖动), 默认见 scaffold.toml\nclick(231, 347, human=False)            # 瞬移急点(速度优先)\nclick(231, 347, jitter=0, settle=200)  # 精确落点, 到位停 200ms',
    "dblclick": 'dblclick(400, 300)',
    "drag": 'drag(450, 550, 450, 150)               # 列表上滑(按住拖)\ndrag(100, 300, 500, 300, ms=500)       # 横拖, 500ms',
    "sleep": 'sleep(500)                            # 半秒, F9 按下立刻醒\nsleep((400, 900))                    # 区间随机(固定间隔是检测特征)',
    "log": 'log(f"击杀 ×{kills}", "info")           # level: info|warn|error',
    "shot": 'shot("boss出现")                       # 留痕到 logs/shots',
    "stopped": 'while not stopped():               # F9 叫停了吗(挂机循环退出条件)\n    打怪一轮()',
    "find_all": 'for x, y in find_all("小地图图标.png"): click(x, y)',
    "find_tap": 'find_tap("领取按钮.png")                        # 单帧试\nfind_tap("每日签到.png", timeout=5000)              # 等最多 5 秒\nfind_tap("签到.png", verify="主界面.png")          # 点后必须见到确认图',
    "tap_until_gone": 'n = tap_until_gone("确定按钮.png")       # 返回点击次数',
    "wait_pic": 'hit = wait_pic("结算面板.png", timeout=8000)   # (x, y, 分) | None',
    "wait_pic_any": 'hit = wait_pic_any(["升级.png", "断线.png"])  # (名, x, y, 分) | None',
    "wait_pic_gone": 'while not wait_pic_gone("加载中.png", timeout=15000): pass',
    "wait_color": 'hit = wait_color("FFD700")                    # 金币转圈 (x,y)|None',
    "wait_color_gone": 'ok = wait_color_gone("CC3333-282828", timeout=10000)  # 等怪死',
    "wait_text": 'hit = wait_text("挑战成功")                    # OCR 等文字 (x,y,相似度)|None',
    "ocr": 'task = ocr(region=(10, 30, 400, 60))          # 识全文: "每日签到 副本"\nif "签到" in task: ...          # 任务名判断',
    "ocr_numbers": 'nums = ocr_numbers(region=(50, 580, 200, 610))\nlv = nums[0] if nums else 0          # 等级\n# 坐标场景: x, y = ocr_numbers(POS_RECT)[:2]',
    "find_str": 'hit = find_str("每日签到")                     # 找字位置 (x, y) | None\nif hit: click(*hit)                  # 找到就能点\n# 短词(2字)不稳: 缩 region + min_ratio=0.5',
    "go": 'if not go("dungeon"): return        # 图带路(声明 NAV_SCREENS/NAV_EDGES)\n# 迷路自愈; LostError=需重登(配 on_fuse)',
    "at": 'if at("city"): ...                  # 便宜的单帧"我在不在这屏"',
    "progress": 'while not stopped():\n    progress("等刷新")          # 长轮询手动打点, 防看门狗误杀\n    sleep(2000)',
}

# ==================== 配置键说明(默认值/类型从 ScaffoldConfig 内省) ====================
CFG_DESC = {
    "backend": '目标端: `"window"`(PC 窗口) | `"adb"`(模拟器/真机)',
    "window_class": 'window 端热键收编的类名过滤串(空=不过滤); 收编到子控件时用它锁定',
    "display": '截屏通道: `normal` 前台抓屏 | `gdi` 后台 PrintWindow(遮挡可截, 通用首选) | `gdi2` 兼容模式(慢但稳, gdi 截图不刷新时) | `dx` 潜影注入(3D 游戏)',
    "mouse": '鼠标通道: `normal` SendInput 真鼠标(需前台) | `windows` PostMessage 后台 | `windows2` dx 消息+虚拟光标锁(治点击坐标总偏) | `dx` 潜影',
    "keypad": '键盘通道: 同 mouse; windows=带扫描码消息按键, 只达读消息循环的窗口, 轮询型游戏免疫→换 `dx`+`hook_keystate`',
    "fake_active": '绑定后假激活(`EnableFakeActive`): 治"唯独点击无反应"的后台激活门槛, 需 dx 系通道',
    "hook_keystate": '键状态钩子: 治"键盘消息无反应"(游戏轮询键态不读消息), 需键盘 dx 通道',
    "hide_module": '注入件模块隐身: 反作弊扫进程模块时开, 需 dx 系通道',
    "adb_serials": 'adb 端预置序列号列表(空=自动发现)',
    "hotkey": '启动热键(收编/再按停止): `f1`~`f12` / `pause` / `scrolllock` / `home` / `end` / `insert` / `delete`',
    "pick_mode": '收编模式: `hover` 拾鼠标下窗口 | `focus` 拾焦点子窗口(模拟器渲染窗)',
    "human_mouse": '拟人键鼠总开关: true=贝塞尔轨迹+随机停顿+落点抖动; false=瞬移急点(速度优先)',
    "click_jitter": '点击落点抖动 ±px(0=精确落点); 防每次点同一位的机器人特征',
    "click_settle_ms": '点击到位停顿区间 ms, 每次取区间随机(人不是节拍器); 调用处可单次覆盖',
    "max_restarts": '任务异常自动重开次数上限, 连败熔断(可配 on_fuse 自救)',
    "idle_timeout": '无进展看门狗秒数(0=关): find/wait 命中与点击算进展, 超时停任务留痕',
    "window_size": '中控台窗口尺寸 [宽, 高]',
    "left_ratio": '中控台左列(目标表)占宽比例 0~1',
    "theme": 'ttkbootstrap 主题名(设置弹窗可热切)',
}
CFG_GROUPS = [
    ("目标与通道", ["backend", "window_class", "display", "mouse", "keypad",
                 "fake_active", "hook_keystate", "hide_module",
                 "adb_serials", "hotkey", "pick_mode"]),
    ("拟人键鼠(dsl click/dblclick 的默认)", ["human_mouse", "click_jitter",
                                      "click_settle_ms"]),
    ("运行策略与外观", ["max_restarts", "idle_timeout", "window_size",
                     "left_ratio", "theme"]),
]

CHANNELS_MD = """
本章仅 **window 端**适用; adb 端天然全后台(截屏=adb screencap, 输入=adb shell
input), 无通道概念——display/mouse/keypad 等配置不参与(见四章)。

| 通道 | 取值 | 前台/后台 | 占真键鼠 | 适用与坑 |
|---|---|---|---|---|
| display | `normal` | 前台 | — | 直接抓屏, 目标须可见不被遮挡, 最快最稳 |
| display | `gdi` | **后台** | — | PrintWindow 让窗口自画进内存, 遮挡/被盖都能截, 通用首选 |
| display | `gdi2` | **后台** | — | 兼容模式慢但稳; `gdi` 截图不刷新/花屏时换它 |
| display | `dx` | **后台** | — | 潜影注入截帧(OpenGL 已通, D3D9 调试中, 不通明确报错); 需 bin/ 注入件(杀毒报毒是常态) |
| mouse | `normal` | 前台 | **占** | SendInput 真鼠标, 兼容一切; 跑动时人不能碰机器 |
| mouse | `windows` | **后台** | 不占 | PostMessage 直投消息; tkinter 自绘类窗口不认(收编前先看清目标) |
| mouse | `windows2` | **后台** | 不占 | dx 消息鼠标+GetCursorPos 虚拟光标锁, 治"点击坐标总落到真鼠标处"; 需注入件 |
| mouse | `dx` | **后台** | 不占 | 潜影注入, 检测面最小, 需注入件 |
| keypad | `normal` | 前台 | **占** | SendInput 真键盘 |
| keypad | `windows` | **后台** | 不占 | 带扫描码消息按键(旧"死案"系误传, 已实现); 只达读消息循环的窗口, 轮询型游戏(GetAsyncKeyState)免疫 |
| keypad | `dx` | **后台** | 不占 | 潜影注入, 需注入件; 轮询型目标配 `hook_keystate` |

选型口诀: 能 `gdi`+`windows` 全后台就全后台(测试/挂机两不误);
目标不认 PostMessage 点击再退 `normal` 前台; 3D 游戏上 `dx`。

对症速查(设置弹窗"经典组合"同款, 点按即套用):

| 症状 | 配方(display · mouse · keypad) |
|---|---|
| 起步首选 · 普通窗口后台 | `gdi · windows · windows` |
| 移动/键盘正常, 唯独点击全无反应 | `gdi · dx · windows` + `fake_active` |
| 键盘消息全无反应(轮询型游戏) | `gdi · dx · dx` + `hook_keystate` |
| 点击坐标总落到真鼠标处/偏移 | `gdi · windows2 · windows` |
| GDI 截图黑屏/冻结(D3D/GL 渲染) | `dx · dx · windows` |
"""

# ==================== 散文章节(md 子集: ##/###/段落/-表/```/**/`) ====================
PROSE = [
    ("一、快速上手", [
        ("1. 初始化环境", """
装一次, 以后所有项目通用:

1. **uv**(包管理器): `pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple`
   (机器上有 Python 就能用它装; 没有 Python 也行, uv sync 会自动从南大镜像下载);
2. 已装 **Python 3.12+** 的话 uv 直接用它, 不再下载;
3. 解压骨架 zip 到任意目录, 比如 `D:\\scripts\\我的挂机`。
"""),
        ("2. 安装依赖", """
在骨架目录执行:

```bash
uv sync
```

骨架自带的两个 wheel 在 `libs/` 里(脚手架 + 引擎), 从本地文件安装;
其余公共依赖自动从清华镜像拉。**全程不需要访问 GitHub。**
"""),
        ("3. 测试启动", """
```bash
uv run console.py
```

中控台是**唯一入口**(单开多开都是它): 鼠标**悬停**在目标窗口上按 **F9** →
收编进表格并启动; 表格行按钮启停; 右侧日志流; 再按 F9 收编下一个即多开。
adb 端(模拟器/真机)是另一套打法: 在线设备**整表自动入列**、按行启动,
没有热键收编——模拟器/真机用户**直接跳四章**。
"""),
    ]),
    ("二、写你的业务", [
        ("4. business.py: 参数面板", """
一个 dataclass = 全部业务参数, `FIELD_META` 声明中文名与控件类型,
中控台的设置弹窗**自动生成**(用户改值自动落盘 business.yaml):

```python
from dataclasses import dataclass

FIELD_META = {
    "attack_wait": ("等击杀秒数", "entry"),
    "max_kills":   ("最大击杀数(0=无限)", "entry"),
    "pick_coin":   ("捡金币", "combo:是|否"),
}

@dataclass
class BusinessConfig:
    attack_wait: float = 10.0
    max_kills: int = 0
    pick_coin: bool = True
```

任务里 `ctx.cfg.attack_wait` 取当前值。
"""),
        ("5. task.py: 挂机逻辑", """
`main_task(ctx)` 是任务主体, 顶层命令 `from icefrag.dsl import *` 直接用 ——
两层: **icefrag 命令**(组装层: 拟人键鼠/等待环/复合动作) + **大漠直通**(DmSoft
全量同名同参, 仅 window 端):

```python
from icefrag.dsl import *

def main_task(ctx):
    while not stopped():                             # 挂机循环自己写
        hit = wait_pic("怪.png", timeout=3000)       # 等怪 (x, y, 分) | None
        if not hit:
            log("场上无怪"); sleep((1000, 2000)); continue
        click(*hit[:2])
        if wait_pic_gone("怪.png", timeout=10000):   # 等击杀
            log("击杀"); shot("kill")                # 留痕到 logs/shots
```

大漠直通与大漠一字不差, 老脚本直接搬:

```python
idx, x, y = FindPic(0, 0, 640, 480, "领取按钮.png") # 未找到 = (-1, -1, -1)
if idx >= 0:
    MoveTo(x, y); LeftClick()
SendString(GetBindWindow(), "出售红药500金")        # 打字(老ANSI窗口加 ime=True)
```

**循环自己写, 返回 = 任务完成**: main_task 只被框架调用**一次**, 正常返回即整个
任务完成收口。要挂机就自己写 `while not stopped(): ...`(F9 叫停循环即退);
预期内的失败(没找到怪/点击落空)在循环里 try/except 掉——那是业务; 冒出去的异常
框架才接管: 自动重开, 连败熔断。做一次性任务直接写直线代码, 不用任何技巧。

命令权威表: PC 窗口端见**三章**, 手机(adb)端见**四章**(签名由框架内省生成,
与代码不漂移)。更冷门的动作走逃生舱: `ctx.ops`(图色门面, 双端同构)/
`ctx.device`(adb 方言, 表见四章)。
"""),
        ("6. 图色素材", """
素材就是 PNG 和色值, 用你顺手的截图工具做, 放进 `templates/` 即可:
`wait_pic("xx.png")` / `find_tap("xx.png")` 按文件名引用。
找色类逻辑不需要素材, 直接写色值(吸管取色, 注意 BGR 序)。

**同源裁材**: 屏幕截图的像素未必等于框架截屏的像素(后台/特殊渲染窗口)。
从 `logs/shots/` 的留痕截图裁素材——那是框架眼里的画面, 同源必配。
"""),
    ]),
]
PROSE_LATE = [   # 四~九章(手机/配置章含内省表, 通道表由常量拼装, 散文在此)
    ("四、手机(adb)开发", [
        ("adb 端上手", """
**三步**:

1. `scaffold.toml` 改 `backend = "adb"`(可选: `adb_serials` 预置白名单,
   空=收所有在线设备);
2. 启动模拟器/插真机, 终端 `adb devices` 能看到它;
3. `uv run console.py` —— 在线设备**整表自动入列**(不自动启动), 表格按行
   启动/停止, 📷 开实时预览, 双击改名; 后开的模拟器点**扫描设备**按钮补捞。

热键收编(F9)是 window 端专属概念, adb 端没有也不需要。任务代码(task.py)
与 PC 端**同一套命令**——换端不改脚本, 差异全在下面两张表里。
"""),
        ("命令一览(22 个, 双端同构)", None),   # build 期由内省填充
        ("adb 方言(ctx.device)", None),       # build 期由内省填充
        ("端差异与注意", """
- **坐标 = 设备屏幕坐标**(分辨率在模拟器设置里定); 素材从 `logs/shots/`
  留痕截图裁——同源裁材在 adb 端同样必守(帧来自设备截屏, 与电脑屏幕不同源)。
- **拟人语义在 adb 端**: 无鼠标轨迹概念, `click` = 停顿前摇+落点抖动+tap;
  `drag` = 原生 swipe; `human=False` 只去掉前摇。贝塞尔轨迹是 window 端专属。
- **停止**: adb 端用中控台行按钮**停止**(`stopped()`/`sleep` 可中断同一机制,
  只是没有热键); 表里说明列写的 F9 指 window 端热键, 语义等同。
- **通道/收编/dx 开关全是 window 端配置**, adb 端天然后台不占键鼠,
  设置弹窗里也不会出现它们。
- **打字**: `ctx.device.type_text("中文")`(ADBKeyboard 广播), 对应 window 端
  的 `SendString` 直通。
- `go`/`at` 导航、OCR 识字、等待族与 PC 端完全同构, 图色帧源自动切设备截屏。
"""),
    ]),
    ("五、全局配置", [
        ("总说明", """
框架自己的配置在 `scaffold.toml`(与业务配置 business.py 分离): 通道/热键/拟人键鼠/
运行策略/外观。改完重启中控台生效; 下表**默认值与类型由框架内省生成**, 说明为人工
注释, 键位增删会触发生成器对账报错——不会漂移。"""),
    ]),
    ("六、通道选择速查(仅 window 端)", [
        ("能力矩阵", CHANNELS_MD),
    ]),
    ("七、长跑保障", [
        ("机制表", """
| 机制 | 干什么 | 哪里调 |
|---|---|---|
| 异常自动重开 | 任务抛异常自动重启, 连败超限熔断躺平 | scaffold.toml `max_restarts` |
| on_fuse 钩子 | 熔断前给你一次自愈机会(重启游戏/重登), 写 task.py 里 `def on_fuse(ctx) -> bool` | task.py |
| 无进展看门狗 | 画面卡死没异常也逃不过, 超时自动停+截图 | scaffold.toml `idle_timeout` |
| FatalError | `raise FatalError("封号")` 致命场景直接停, 不白烧重开次数 | task.py |
| 截图留痕 | `shot("标签")` 与失败自动截图, 都进 logs/shots | 自动 |
"""),
    ]),
    ("八、打包与升级", [
        ("打包 exe 发给别人", """
```bash
uv run build_exe.py
```

产出 `dist/<你的名>-v<版本>.zip`: 目标机**零 Python**, 解压即用;
`templates/` 与 `scaffold.toml` 摆 exe 旁, 用户可自行调参。
**bin/ 注入件会被 Defender 报毒**, 目标机需把解压目录加入杀毒排除——发给人时记得交代。
"""),
        ("升级脚手架", """
作者在群里发新版时:

1. 下载新的两个 whl, 替换 `libs/` 里的同名旧文件(文件名里的数字就是版本号);
2. pyproject 里 `[tool.uv.sources]` 两行 path 改成新文件名;
3. `uv sync`。

不领新版就继续用旧的, 互不影响。
"""),
    ]),
    ("九、常见问题", [
        ("FAQ", """
(本章留白, 条目随实战反馈逐条补录。)
"""),
    ]),
]

RULES_MD = ""   # 已删(用户裁定): 铁律内容留在 dsl.py 模块头与 task.py 示例里


# ==================== md 子集渲染器(给 chm/html 用) ====================
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    s = _esc(s)
    s = __import__("re").sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = __import__("re").sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s


def _md(text: str) -> str:
    """md 子集 → html: ###/## 标题, - 列表, | 表, ``` 代码块, 段落。"""
    import re

    def flush_table(rows):
        cells = [[_inline(c.strip()) for c in r.strip("|").split("|")] for r in rows]
        head = cells[0]
        body = cells[1:]
        trs = "<tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr>"
        trs += "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                       for r in body)
        return "<table border=1>" + trs + "</table>"

    out, buf, code = [], [], None
    for line in text.strip().splitlines():
        if line.strip().startswith("```"):
            if code is None:
                code = []
            else:
                out.append("<pre>" + _esc("\n".join(code)) + "</pre>")
                code = None
            continue
        if code is not None:
            code.append(line)
            continue
        t = line.strip()
        if not t:
            if buf:
                if buf[0].startswith("|"):
                    out.append(flush_table(buf))
                else:
                    out.append(f"<p>{' '.join(_inline(x) for x in buf)}</p>")
                buf = []
            continue
        if t.startswith("|"):                        # 表行(表头/数据/分隔)
            if set(t) <= {"|", "-", " ", ":"}:       # 分隔行吃掉
                continue
            if buf and not buf[0].startswith("|"):   # 段落被表打断, 先出段落
                out.append(f"<p>{' '.join(_inline(x) for x in buf)}</p>")
                buf = []
            buf.append(t)
            continue
        if buf and buf[0].startswith("|"):           # 表结束
            out.append(flush_table(buf))
            buf = []
        if t.startswith("###"):
            out.append(f"<h3>{_inline(t[3:].strip())}</h3>")
        elif t.startswith("##"):
            out.append(f"<h2>{_inline(t[2:].strip())}</h2>")
        elif t.startswith("- "):
            out.append(f"<li>{_inline(t[2:])}</li>")
        elif t[0].isdigit() and t[1:2] == ".":
            out.append(f"<li>{_inline(t[2:].strip())}</li>")
        else:
            buf.append(t)
    if buf and buf[0].startswith("|"):
        out.append(flush_table(buf))
    elif buf:
        out.append(f"<p>{' '.join(_inline(x) for x in buf)}</p>")
    if code is not None:
        out.append("<pre>" + _esc("\n".join(code)) + "</pre>")
    return "\n".join(out)


# ==================== icefrag 命令页(内省 dsl) ====================
def _sig(name: str) -> str:
    sig = inspect.signature(getattr(dsl, name))
    parts = [f"{p.name}{'' if p.default is inspect.Parameter.empty else f'={p.default!r}'}"
             for p in sig.parameters.values()]
    return f"{name}({', '.join(parts)})"


def _brief(name: str) -> str:
    return (getattr(dsl, name).__doc__ or "").strip().split("\n")[0]


def _doc_extra(name: str) -> str:
    doc = (getattr(dsl, name).__doc__ or "").strip().split("\n")
    return "<br>".join(l.strip() for l in doc[1:] if l.strip())


# ==================== 大漠直通命令表(签名内省 DmSoft 本尊) ====================
def _dm_sig(name: str) -> str:
    sig = inspect.signature(getattr(DmSoft, name))
    params = list(sig.parameters.values())[1:]     # 去 self(类方法内省带上)
    parts = [f"{p.name}{'' if p.default is inspect.Parameter.empty else f'={p.default!r}'}"
             for p in params]
    return f"{name}({', '.join(parts)})"


def _dm_brief(name: str) -> str:
    return (getattr(DmSoft, name).__doc__ or "").strip().split("\n")[0] or "—"


def dm_table_md(names) -> str:
    rows = ["| 命令 | 原型 | 说明 |", "|---|---|---|"]
    rows += [f"| **{n}** | `{_dm_sig(n)}` | {_dm_brief(n)} |" for n in names]
    return "\n".join(rows)


def dm_table_html(names) -> str:
    rows = ["<table border=1><tr><th>命令</th><th>原型</th><th>说明</th></tr>"]
    rows += [f"<tr><td><code>{n}</code></td><td><code>{_esc(_dm_sig(n))}</code></td>"
             f"<td>{_inline(_dm_brief(n))}</td></tr>" for n in names]
    rows.append("</table>")
    return "\n".join(rows)


# ==================== 手机章生成体(四章: 双视图命令表 + adb 方言表) ====================
def _dev_sig(name: str) -> str:
    sig = inspect.signature(getattr(AdbTarget, name))
    params = list(sig.parameters.values())[1:]     # 去 self(类方法内省带上)
    parts = [f"{p.name}{'' if p.default is inspect.Parameter.empty else f'={p.default!r}'}"
             for p in params]
    return f"{name}({', '.join(parts)})"


def mobile_cmd_md() -> str:
    """四章·命令一览: 同一份内省向 adb 端再发一份表(源头一处, 不漂移)。"""
    out = ["22 个 icefrag 命令 adb 端**全体可用**, 签名/返回与三章一字不差"
           "(同一处内省生成); 端行为差异已写进说明列。",
           "**大漠直通在 adb 端不可用**(调用即报错指路)。"
           "用法示例见三章示例速查——命令同一套。", ""]
    for cat, names in GROUPS:
        out += [f"**{cat}**", "", "| 命令 | 原型 | 说明 |", "|---|---|---|"]
        out += [f"| **{n}** | `{_sig(n)}` | {_brief(n)} |" for n in names]
        out.append("")
    return "\n".join(out)


def device_md() -> str:
    """四章·adb 方言表: ctx.device(=imgbot AdbTarget)公有方法, 签名内省+说明手写。"""
    head = ("`ctx.device`(= imgbot `AdbTarget`)是 adb 端独有的逃生舱: 安卓键码/"
            "拉起杀应用/shell/原生输入这些 dsl 命令面之外的事。序列号取 "
            "`ctx.device.serial`。**拟人点击别绕过 dsl `click`**(它管前摇+抖动)。")
    rows = ["| 方言 | 原型 | 说明 |", "|---|---|---|"]
    rows += [f"| **{n}** | `{_dev_sig(n)}` | {DEVICE_DESC[n]} |"
             for n in sorted(DEVICE_DESC)]
    return head + "\n\n" + "\n".join(rows)


def _head() -> str:
    return ("<html><head><meta charset='utf-8'><style>"
            "body{font-family:'Microsoft YaHei';margin:24px;line-height:1.6}"
            "pre{background:#1b1f24;color:#d0d0d0;padding:10px;border-radius:6px;"
            "overflow-x:auto}h2{border-bottom:2px solid #4a7;padding-bottom:4px}"
            "table{border-collapse:collapse}td,th{border:1px solid #ccc;"
            "padding:4px 10px;font-size:14px}</style></head><body>")


def page_html(name: str) -> str:
    ex = EXAMPLES.get(name, "")
    return "\n".join([
        _head(), f"<h1><code>{name}</code></h1>",
        f"<p>{_brief(name)}</p>",
        "<h2>原型</h2>", f"<pre>{_sig(name)}</pre>",
        f"{_doc_extra(name)}" if _doc_extra(name) else "",
        "<h2>示例</h2>", f"<pre>{ex}</pre>" if ex else "<p>—</p>",
        "</body></html>",
    ])


# ==================== 配置表(内省默认值) ====================
def _cfg_default(f) -> str:
    if f.default is not dataclasses.MISSING:
        return repr(f.default)
    return repr(f.default_factory())


def cfg_md(group_keys) -> str:
    fs = {f.name: f for f in dataclasses.fields(scfg.ScaffoldConfig)}
    rows = ["| 键 | 类型 | 默认 | 说明 |", "|---|---|---|---|"]
    for k in group_keys:
        f = fs[k]
        rows.append(f"| `{k}` | {getattr(f.type, '__name__', f.type)} "
                    f"| `{_cfg_default(f)}` | "
                    f"{_cfg_desc_plain(k).replace('|', '&#124;')} |")
    return "\n".join(rows)


def _cfg_desc_plain(k: str) -> str:
    import re
    return re.sub(r"`([^`]+)`", r"\1", CFG_DESC[k])


def cfg_table_html(group_keys) -> str:
    fs = {f.name: f for f in dataclasses.fields(scfg.ScaffoldConfig)}
    rows = ["<table border=1><tr><th>键</th><th>类型</th><th>默认</th><th>说明</th></tr>"]
    for k in group_keys:
        f = fs[k]
        rows.append(f"<tr><td><code>{k}</code></td>"
                    f"<td>{getattr(f.type, '__name__', f.type)}</td>"
                    f"<td><code>{_esc(_cfg_default(f))}</code></td>"
                    f"<td>{_inline(_cfg_desc_plain(k))}</td></tr>")
    rows.append("</table>")
    return "\n".join(rows)


# ==================== 生成 ====================
def build():
    # -- 对账断言(防漂移) --
    listed = [n for _, names in GROUPS for n in names]
    missing = set(dsl.__all__) - set(listed) - set(dsl.DM_PASSTHROUGH)
    extra = set(listed) - set(dsl.__all__)
    if missing:
        sys.exit(f"GROUPS 漏了命令: {missing}")
    if extra:
        sys.exit(f"GROUPS 多了不存在的命令: {extra}")
    dm_public = {n for n in dir(DmSoft)
                 if not n.startswith("_") and callable(getattr(DmSoft, n))}
    dm_listed = [n for _, names in DM_GROUPS for n in names]
    if set(dm_listed) != dm_public:
        sys.exit(f"DM_GROUPS 与 DmSoft 公有命令不一致: "
                 f"少写 {dm_public - set(dm_listed)} / "
                 f"多写 {set(dm_listed) - dm_public}")
    if sorted(dm_public) != dsl.DM_PASSTHROUGH:
        sys.exit("dsl.DM_PASSTHROUGH 与 DmSoft 内省不一致")
    adb_public = {n for n in dir(AdbTarget)
                  if not n.startswith("_") and callable(getattr(AdbTarget, n))}
    if set(DEVICE_DESC) != adb_public:
        sys.exit(f"DEVICE_DESC 与 AdbTarget 公有方法不一致: "
                 f"少写 {adb_public - set(DEVICE_DESC)} / "
                 f"多写 {set(DEVICE_DESC) - adb_public}")
    # 四章两节生成体回填(None 占位 → 内省表; 就地改写, 后续渲染路径通吃)
    PROSE_LATE[0] = ("四、手机(adb)开发", [
        (sec, mobile_cmd_md() if sec.startswith("命令一览")
         else device_md() if sec.startswith("adb 方言") else (body or ""))
        for sec, body in PROSE_LATE[0][1]])
    fields = {f.name for f in dataclasses.fields(scfg.ScaffoldConfig)}
    if set(CFG_DESC) != fields:
        sys.exit(f"CFG_DESC 与 ScaffoldConfig 键不一致: "
                 f"少写 {fields - set(CFG_DESC)} / 多写 {set(CFG_DESC) - fields}")
    cfg_keys = [k for _, keys in CFG_GROUPS for k in keys]
    assert sorted(cfg_keys) == sorted(fields), "CFG_GROUPS 漏配或多配键"

    chm_dir = DOCS / "chm"
    if chm_dir.exists():
        shutil.rmtree(chm_dir)
    chm_dir.mkdir(parents=True)

    # -- 目录树: (章, [ (节, 生成器) ]) ; 节生成器=None 表示该章用 CFG_GROUPS/DSL 组 --
    # 先落 prose 页
    page_no = 0
    pages, toc = {}, []          # pages: 文件名->html; toc: (章, [(节, 文件)])
    for chap, secs in PROSE + PROSE_LATE:
        kids = []
        for sec, body in secs:
            fn = f"p{page_no}.html"
            page_no += 1
            pages[fn] = _head() + f"<h1>{_inline(sec)}</h1>" + _md(body) + "</body></html>"
            kids.append((sec, fn))
        if chap == "五、全局配置":                # 配置章: 每组一节(内省表)
            for gi, (gname, keys) in enumerate(CFG_GROUPS):
                fn = f"cfg{gi}.html"
                pages[fn] = (_head() + f"<h1>{_inline(gname)}</h1>"
                             + cfg_table_html(keys) + "</body></html>")
                kids.append((gname, fn))
        toc.append((chap, kids))

    # 命令清单章: icefrag 命令每命令一页 + 大漠直通每类一页大表
    ids = {}
    dsl_kids = []
    for ci, (cat, names) in enumerate(GROUPS):
        (chm_dir / f"c{ci}").mkdir(exist_ok=True)
        grp_kids = []
        for ii, n in enumerate(names):
            ids[n] = f"c{ci}/p{ci}-{ii}"
            (chm_dir / f"{ids[n]}.html").write_text(page_html(n), encoding="utf-8")
            grp_kids.append((n, ids[n] + ".html"))
        dsl_kids.append((cat, grp_kids))
    for gi, (cat, names) in enumerate(DM_GROUPS):
        fn = f"dm{gi}.html"
        pages[fn] = (_head() + f"<h1>大漠直通 · {cat}</h1>"
                     + "<p>同名同参透传 imgbot DmSoft(仅 window 端, adb 端调用"
                       "报错指路)。签名由生成器内省生成, 与代码不漂移。</p>"
                     + dm_table_html(names) + "</body></html>")
        dsl_kids.append((f"大漠直通 · {cat}", [("命令表", fn)]))
    toc.insert(2, ("三、PC 窗口开发", None))      # 特殊: 嵌套组, 单独渲染

    # -- md 产物(骨架 README / AI 权威版) --
    md = [f"# {TITLE}", "",
          "> 上手 → 业务 → PC 窗口开发 → 手机(adb)开发 → 配置 → 通道(仅 window 端)"
          " → 保障 → 打包 → FAQ。",
          "> 命令签名与配置默认值由 `scripts/build_docs.py` 内省生成, 与代码不漂移。", ""]
    for chap, secs in PROSE:
        md.append(f"## {chap}")
        for sec, body in secs:
            md += [f"### {sec}", body.strip(), ""]
    md += ["## 三、PC 窗口开发", "",
           "22 个 icefrag 命令(双端通用; 模拟器/真机端见**四章**) + 85 个大漠直通"
           "(仅 window 端)。签名由生成器内省生成, 与代码不漂移。", ""]
    for cat, names in GROUPS:
        md += [f"### {cat}", "", "| 命令 | 原型 | 说明 |", "|---|---|---|"]
        for n in names:
            md.append(f"| **{n}** | `{_sig(n)}` | {_brief(n)} |")
        md.append("")
    md += ["### 大漠直通(与大漠同名同参, 仅 window 端)", ""]
    for cat, names in DM_GROUPS:
        md += [f"#### {cat}", "", dm_table_md(names), ""]
    md += ["### 示例速查", ""]
    for _, names in GROUPS:
        for n in names:
            if n in EXAMPLES:
                md += [f"**{n}**", "```python", EXAMPLES[n], "```", ""]
    for chap, secs in PROSE_LATE[:1]:            # 四、手机(adb)开发(含两节内省表)
        md.append(f"## {chap}")
        for sec, body in secs:
            md += [f"### {sec}", body.strip(), ""]
    md += ["## 五、全局配置(scaffold.toml)", ""]
    for gname, keys in CFG_GROUPS:
        md += [f"### {gname}", "", cfg_md(keys), ""]
    for chap, secs in PROSE_LATE[2:]:
        md.append(f"## {chap}")
        for sec, body in secs:
            md += [f"### {sec}", body.strip(), ""]
    (DOCS / f"{CHM_NAME}.md").write_text("\n".join(md), encoding="utf-8")

    # -- chm 首页(总览) --
    nav = []
    for chap, kids in toc:
        nav.append(f"<p><b>{chap}</b></p>")
        if kids:
            nav.append("<p>" + " ".join(
                f"<a href='{fn}'>{_inline(s)}</a>" for s, fn in kids) + "</p>")
        else:
            nav.append("<p>" + " ".join(
                f"<b>{cat}</b>: " + " ".join(
                    f"<a href='{f}'>{n}</a>" for n, f in gk) for cat, gk in dsl_kids) + "</p>")
    (chm_dir / "index.html").write_text("\n".join([
        _head(), f"<h1>{TITLE}</h1>",
        "<p>你拿到的是骨架 zip: 框架管绑定/中控台/热键/异常重开/看门狗/留痕, "
        "你只写 task.py(逻辑)与 business.py(参数)。全程不需要 GitHub。</p>",
        "<h2>章节导航</h2>"] + nav + ["</body></html>"]),
        encoding="utf-8")
    for fn, html in pages.items():
        (chm_dir / fn).write_text(html, encoding="utf-8")

    # -- hhc(GBK; ASCII 内部路径) --
    Q = '"'
    PARAM = "<param name={q}{k}{q} value={q}{v}{q}>"

    def li(name, local, kids_html="", depth=0):
        pad = "\t" * (depth + 1)
        return (f"{pad}<LI> <OBJECT type=\"text/sitemap\">\n{pad}"
                + PARAM.format(q=Q, k="Name", v=name)
                + (f"\n{pad}" + PARAM.format(q=Q, k="Local", v=local) if local else "")
                + f"\n{pad}</OBJECT>\n"
                + (f"{pad}<UL>\n{kids_html}{pad}</UL>\n" if kids_html else ""))

    entries = []
    for chap, kids in toc:
        if kids is None:                            # 命令清单章: 组→命令 两层
            inner = "".join(
                li(cat, "", "".join(li(n, f) for n, f in gk), 2)
                for cat, gk in dsl_kids)
            entries.append(li(chap, "index.html#dsl", inner, 1))
        else:
            entries.append(li(chap, "", "".join(li(s, f, "", 2) for s, f in kids), 1))
    (chm_dir / "toc.hhc").write_text(
        '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN">\n<HTML><HEAD></HEAD>'
        '<BODY>\n<UL>\n' + "".join(entries) + "</UL>\n</BODY></HTML>\n",
        encoding="gbk")
    # [WINDOWS] 字段序错一格=面板不创建(imgbot 同款实测坑)
    (chm_dir / "toc.hhp").write_text(
        "[OPTIONS]\nCompatibility=1.1 or later\nCompiled file=manual.chm\n"
        "Contents file=toc.hhc\nDefault topic=index.html\nDefault Window=main\n"
        f"Language=0x804\nTitle={CHM_NAME}\n\n"
        "[WINDOWS]\n"
        f'main="{CHM_NAME}","toc.hhc",,"index.html",,,,,,0x20,200,0x1006,'
        "[50,30,1000,760],0,0,1,0,0,0,0\n"
        "\n[FILES]\nindex.html\n", encoding="gbk")

    # -- 编译(便携 hhc; 无则留工程手动编) --
    hhc = Path("D:/tools/hhw/hhc.exe")
    if hhc.exists():
        subprocess.run([str(hhc), "toc.hhp"], cwd=chm_dir, capture_output=True)
        out = chm_dir / "manual.chm"
        if out.exists():
            shutil.move(str(out), DOCS / f"{CHM_NAME}.chm")
            print("  chm :", DOCS / f"{CHM_NAME}.chm")
        else:
            print("  chm 编译失败(hhc 返回非零), 工程保留在 docs/chm")

    # -- 单文件 html --
    single = [_head(), f"<h1>{TITLE}</h1>"]
    for chap, kids in toc:
        single.append(f"<h2>{chap}</h2>")
        if kids is None:
            for cat, names in GROUPS:
                single.append(f"<h3>{cat}</h3>")
                single.append("<table><tr><th>命令</th><th>原型</th><th>说明</th></tr>")
                single += [f"<tr><td><code>{n}</code></td><td><code>{_sig(n)}"
                           f"</code></td><td>{_brief(n)}</td></tr>" for n in names]
                single.append("</table>")
            for cat, names in DM_GROUPS:
                single.append(f"<h3>大漠直通 · {cat}</h3>")
                single.append(dm_table_html(names))
        else:
            for c, ss in PROSE + PROSE_LATE:
                if c != chap:
                    continue
                for sec, body in ss:
                    single += [f"<h3>{_inline(sec)}</h3>", _md(body)]
            if chap == "五、全局配置":
                for gname, keys in CFG_GROUPS:
                    single += [f"<h3>{_inline(gname)}</h3>", cfg_table_html(keys)]
    single.append("</body></html>")
    (DOCS / f"{CHM_NAME}.html").write_text("\n".join(single), encoding="utf-8")

    print("生成完毕:")
    print("  md  :", DOCS / f"{CHM_NAME}.md")
    print("  html:", DOCS / f"{CHM_NAME}.html")


if __name__ == "__main__":
    build()
