# icefrag 开发手册

> 上手 → 业务 → DSL 语法 → 配置 → 通道 → 保障 → 打包 → FAQ。
> 命令签名与配置默认值由 `scripts/build_docs.py` 内省生成, 与代码不漂移。

## 一、快速上手
### 1. 初始化环境
装一次, 以后所有项目通用:

1. **uv**(包管理器): `pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple`
   (机器上有 Python 就能用它装; 没有 Python 也行, uv sync 会自动从南大镜像下载);
2. 已装 **Python 3.12+** 的话 uv 直接用它, 不再下载;
3. 解压骨架 zip 到任意目录, 比如 `D:\scripts\我的挂机`。

### 2. 安装依赖
在骨架目录执行:

```bash
uv sync
```

骨架自带的两个 wheel 在 `libs/` 里(脚手架 + 引擎), 从本地文件安装;
其余公共依赖自动从清华镜像拉。**全程不需要访问 GitHub。**

### 3. 测试启动
```bash
uv run console.py
```

中控台是**唯一入口**(单开多开都是它): 鼠标**悬停**在目标窗口上按 **F9** →
收编进表格并启动; 表格行按钮启停; 右侧日志流; 再按 F9 收编下一个即多开。
adb 端(模拟器/真机)自动发现设备, 无需收编。

## 二、写你的业务
### 4. business.py: 参数面板
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

### 5. task.py: 挂机逻辑
`main_task(ctx)` 是任务主体, 顶层命令 `from icefrag.dsl import *` 直接用:

```python
from icefrag.dsl import *

RED = (51, 51, 204)                                  # #CC3333 的 BGR
MON_PTS = [Pt(0, 0, RED, 40), Pt(8, 0, RED, 40)]     # 多点找色点阵

def main_task(ctx):
    while not stopped():                             # 挂机循环自己写
        hit = find_multi_color((0, 0, 900, 640), MON_PTS)
        if not hit:
            log("场上无怪"); sleep((1000, 2000)); continue
        click(*hit)
        if wait_color_gone("CC3333-282828", timeout=10000):
            log("击杀"); shot("kill")                # 留痕到 logs/shots
```

**循环自己写, 返回 = 任务完成**: main_task 只被框架调用**一次**, 正常返回即整个
任务完成收口。要挂机就自己写 `while not stopped(): ...`(F9 叫停循环即退);
预期内的失败(没找到怪/点击落空)在循环里 try/except 掉——那是业务; 冒出去的异常
框架才接管: 自动重开, 连败熔断。做一次性任务直接写直线代码, 不用任何技巧。

命令权威表见本手册**三章**(签名由框架内省生成, 与代码不漂移)。
冷门动作走逃生舱: `ctx.ops`(图色门面)/`ctx.dm`(DmSoft 全量)/`ctx.device`(adb 方言)。

### 6. 图色素材
素材就是 PNG 和色值, 用你顺手的截图工具做, 放进 `templates/` 即可:
`wait_pic("xx.png")` / `find_tap("xx.png")` 按文件名引用。
找色类逻辑不需要素材, 直接写色值(吸管取色, 注意 BGR 序)。

**同源裁材**: 屏幕截图的像素未必等于框架截屏的像素(后台/特殊渲染窗口)。
从 `logs/shots/` 的留痕截图裁素材——那是框架眼里的画面, 同源必配。

## 三、DSL 语法

### 键鼠

| 命令 | 原型 | 说明 |
|---|---|---|
| **click** | `click(x, y, jitter=None, human=None, settle=None)` | 点击 (x, y)。默认拟人: 贝塞尔轨迹到位→随机停顿→落点抖动(默认见 |
| **dblclick** | `dblclick(x, y, jitter=None, human=None, settle=None)` | 双击 (x, y), 参数同 click; adb 端两击带 80~120ms 间隔。 |
| **drag** | `drag(x1, y1, x2, y2, ms=350)` | 按住拖拽(列表滚动/滑块): window=按住左键插值拖, adb=原生 swipe。 |
| **move** | `move(x, y)` | 悬停(不点)。adb 端无悬停概念, 报错指路。 |
| **key** | `key(s)` | 按键/组合键: key("enter") / key("ctrl+s")(修饰键 ctrl/alt/shift/win)。 |
| **type_text** | `type_text(text)` | 打字进绑定目标(聊天/搜索/改名框), 中文可: window=当前键鼠通道逐字 |
| **sleep** | `sleep(ms)` | 可中断睡眠: F9 按下立刻醒(代替 time.sleep 的傻等)。 |

### 消息

| 命令 | 原型 | 说明 |
|---|---|---|
| **log** | `log(text, level='info')` | 打一条日志(中控台日志面板/终端), level: info|warn|error。 |
| **shot** | `shot(tag='')` | 截当前绑定目标一帧存 logs/shots/(月日_时分秒_目标_标签.png)留痕, 返回路径或 None。 |
| **stopped** | `stopped()` | F9 停止键按下过吗 —— 挂机循环的退出条件: while not stopped(): ... |

### 找点(单帧)

| 命令 | 原型 | 说明 |
|---|---|---|
| **find_color** | `find_color(color, region=None, tol=0)` | 区域找全部色块。color="RRGGBB"(偏差给 tol, 或写 "RRGGBB-DRDGDB")。 |
| **find_all** | `find_all(pic, region=None, threshold=None)` | 单帧找全部同类图(列表项/多目标), 近邻去重。 |
| **find_multi_color** | `find_multi_color(rect, points, direction=0)` | 多点找色(大漠 FindMultiColor 对应物): 锚点在 rect 内搜索, 全部相对 |
| **exists** | `exists(pic, region=None, threshold=None)` |  |

### 复合动作

| 命令 | 原型 | 说明 |
|---|---|---|
| **find_tap** | `find_tap(pic, region=None, timeout=0, threshold=None, verify=None)` | 找到就拟人点(贝塞尔轨迹+停顿)。timeout=0 单帧试; verify=点后必须 |
| **tap_until_gone** | `tap_until_gone(pic, region=None, timeout=10000, threshold=None)` | 连点直到图消失(确定/领取类), 返回点击次数; 不出现返回 0。 |

### 等待(超时返 None/False)

| 命令 | 原型 | 说明 |
|---|---|---|
| **wait_pic** | `wait_pic(pic, region=None, timeout=10000, threshold=None)` | 等图出现, 返回 (中心x, 中心y, 分数); 超时自动截图留痕。 |
| **wait_pic_any** | `wait_pic_any(pics, region=None, timeout=10000, threshold=None)` | 等一组模板任一出现, 返回 (名字, x, y, 分数); 超时 None。 |
| **wait_pic_gone** | `wait_pic_gone(pic, region=None, timeout=10000, threshold=None)` | 等图消失(加载页结束判定)。 |
| **wait_color** | `wait_color(color, region=None, timeout=10000)` | 等某色出现(色比图快), 返回 (x, y) 或 None。偏差写进色串: |
| **wait_color_gone** | `wait_color_gone(color, region=None, timeout=10000)` | 等某色消失(等击杀/等加载), 消失 True / 超时 False。 |
| **wait_text** | `wait_text(text, region=None, timeout=10000)` | OCR 等文字出现("完成"提示类), 返回 (中心x, 中心y, 相似度) 或 None。 |

### 识字 / 找字(OCR)

| 命令 | 原型 | 说明 |
|---|---|---|
| **ocr** | `ocr(region=None, fast=False)` | 识字: OCR 读区域全文, 行间空格连接("任务名叫什么"用这个)。 |
| **ocr_numbers** | `ocr_numbers(region=None)` | 识数: OCR 全文后抠所有数字串(等级取 [0], 坐标取 [:2]); 没识到返回 []。 |
| **find_str** | `find_str(text, region=None, min_ratio=0.7)` | 找字(大漠 FindStr 风): OCR 定位 + 按序比例匹配, 返回 (x, y) 或 None, |

### 导航(需 task.py 声明表)

| 命令 | 原型 | 说明 |
|---|---|---|
| **go** | `go(name, timeout=120000)` | 走到目标界面, 图自动带路(BFS)+迷路重定位自愈。到达 True / 超时安静 |
| **at** | `at(name)` | 期望验证: 当前是否在指定界面(单帧一张锚点, 高频便宜; 迷路判别用 go)。 |

### 看门狗

| 命令 | 原型 | 说明 |
|---|---|---|
| **progress** | `progress(note='')` | 手动打一次进展点(看门狗信号; find/wait 命中与点击已自动打点)。 |

### 示例速查

**click**
```python
click(231, 347)                       # 拟人点击(轨迹+停顿+抖动), 默认见 scaffold.toml
click(231, 347, human=False)            # 瞬移急点(速度优先)
click(231, 347, jitter=0, settle=200)  # 精确落点, 到位停 200ms
```

**dblclick**
```python
dblclick(400, 300)
```

**drag**
```python
drag(450, 550, 450, 150)               # 列表上滑(按住拖)
drag(100, 300, 500, 300, ms=500)       # 横拖, 500ms
```

**move**
```python
move(400, 300)                         # 悬停不点
```

**key**
```python
key("ctrl+s")
key("enter")
```

**type_text**
```python
find_tap("聊天框.png")                      # 先点开输入框
type_text("出售红药500金")               # 打字(中文可)
# 老ANSI窗口打不进字: ctx.dm.SendString(hwnd, "文字", ime=True)
```

**sleep**
```python
sleep(500)                            # 半秒, F9 按下立刻醒
sleep((400, 900))                    # 区间随机(固定间隔是检测特征)
```

**log**
```python
log(f"击杀 ×{kills}", "info")           # level: info|warn|error
```

**shot**
```python
shot("boss出现")                       # 留痕到 logs/shots
```

**stopped**
```python
while not stopped():               # F9 叫停了吗(挂机循环退出条件)
    打怪一轮()
```

**find_color**
```python
hit = find_color("CC3333", tol=40, region=(0, 0, 900, 570))
if hit: click(*hit[0])
```

**find_all**
```python
for x, y in find_all("小地图图标.png"): click(x, y)
```

**find_multi_color**
```python
from icefrag.dsl import Pt
MON = [Pt(0, 0, (51, 51, 204), 40), Pt(8, 0, (51, 51, 204), 40)]
hit = find_multi_color((0, 0, 900, 640), MON)   # (x, y) | None
```

**exists**
```python
if exists("金币满.png"): key("b")
```

**find_tap**
```python
find_tap("领取按钮.png")                        # 单帧试
find_tap("每日签到.png", timeout=5000)              # 等最多 5 秒
find_tap("签到.png", verify="主界面.png")          # 点后必须见到确认图
```

**tap_until_gone**
```python
n = tap_until_gone("确定按钮.png")       # 返回点击次数
```

**wait_pic**
```python
hit = wait_pic("结算面板.png", timeout=8000)   # (x, y, 分) | None
```

**wait_pic_any**
```python
hit = wait_pic_any(["升级.png", "断线.png"])  # (名, x, y, 分) | None
```

**wait_pic_gone**
```python
while not wait_pic_gone("加载中.png", timeout=15000): pass
```

**wait_color**
```python
hit = wait_color("FFD700")                    # 金币转圈 (x,y)|None
```

**wait_color_gone**
```python
ok = wait_color_gone("CC3333-282828", timeout=10000)  # 等怪死
```

**wait_text**
```python
hit = wait_text("挑战成功")                    # OCR 等文字 (x,y,相似度)|None
```

**ocr**
```python
task = ocr(region=(10, 30, 400, 60))          # 识全文: "每日签到 副本"
if "签到" in task: ...          # 任务名判断
```

**ocr_numbers**
```python
nums = ocr_numbers(region=(50, 580, 200, 610))
lv = nums[0] if nums else 0          # 等级
# 坐标场景: x, y = ocr_numbers(POS_RECT)[:2]
```

**find_str**
```python
hit = find_str("每日签到")                     # 找字位置 (x, y) | None
if hit: click(*hit)                  # 找到就能点
# 短词(2字)不稳: 缩 region + min_ratio=0.5
```

**go**
```python
if not go("dungeon"): return        # 图带路(声明 NAV_SCREENS/NAV_EDGES)
# 迷路自愈; LostError=需重登(配 on_fuse)
```

**at**
```python
if at("city"): ...                  # 便宜的单帧"我在不在这屏"
```

**progress**
```python
while not stopped():
    progress("等刷新")          # 长轮询手动打点, 防看门狗误杀
    sleep(2000)
```

## 四、全局配置(scaffold.toml)

### 目标与通道

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `backend` | str | `'window'` | 目标端: "window"(PC 窗口) &#124; "adb"(模拟器/真机) |
| `window_class` | str | `''` | window 端热键收编的类名过滤串(空=不过滤); 收编到子控件时用它锁定 |
| `display` | str | `'normal'` | 截屏通道: normal 前台抓屏 &#124; gdi 后台 PrintWindow(遮挡可截, 通用首选) &#124; gdi2 兼容模式(慢但稳, gdi 截图不刷新时) &#124; dx 潜影注入(3D 游戏) |
| `mouse` | str | `'normal'` | 鼠标通道: normal SendInput 真鼠标(需前台) &#124; windows PostMessage 后台 &#124; windows2 dx 消息+虚拟光标锁(治点击坐标总偏) &#124; dx 潜影 |
| `keypad` | str | `'normal'` | 键盘通道: 同 mouse; windows=带扫描码消息按键, 只达读消息循环的窗口, 轮询型游戏免疫→换 dx+hook_keystate |
| `fake_active` | bool | `False` | 绑定后假激活(EnableFakeActive): 治"唯独点击无反应"的后台激活门槛, 需 dx 系通道 |
| `hook_keystate` | bool | `False` | 键状态钩子: 治"键盘消息无反应"(游戏轮询键态不读消息), 需键盘 dx 通道 |
| `hide_module` | bool | `False` | 注入件模块隐身: 反作弊扫进程模块时开, 需 dx 系通道 |
| `adb_serials` | list[str] | `[]` | adb 端预置序列号列表(空=自动发现) |
| `hotkey` | str | `'f9'` | 启动热键(收编/再按停止): f1~f12 / pause / scrolllock / home / end / insert / delete |
| `pick_mode` | str | `'hover'` | 收编模式: hover 拾鼠标下窗口 &#124; focus 拾焦点子窗口(模拟器渲染窗) |

### 拟人键鼠(dsl click/dblclick 的默认)

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `human_mouse` | bool | `True` | 拟人键鼠总开关: true=贝塞尔轨迹+随机停顿+落点抖动; false=瞬移急点(速度优先) |
| `click_jitter` | int | `3` | 点击落点抖动 ±px(0=精确落点); 防每次点同一位的机器人特征 |
| `click_settle_ms` | list[int] | `[60, 160]` | 点击到位停顿区间 ms, 每次取区间随机(人不是节拍器); 调用处可单次覆盖 |

### 运行策略与外观

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `max_restarts` | int | `3` | 任务异常自动重开次数上限, 连败熔断(可配 on_fuse 自救) |
| `idle_timeout` | int | `0` | 无进展看门狗秒数(0=关): find/wait 命中与点击算进展, 超时停任务留痕 |
| `window_size` | list[int] | `[1280, 800]` | 中控台窗口尺寸 [宽, 高] |
| `left_ratio` | float | `0.45` | 中控台左列(目标表)占宽比例 0~1 |
| `theme` | str | `'darkly'` | ttkbootstrap 主题名(设置弹窗可热切) |

## 五、通道选择速查
### 能力矩阵
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

## 六、长跑保障
### 机制表
| 机制 | 干什么 | 哪里调 |
|---|---|---|
| 异常自动重开 | 任务抛异常自动重启, 连败超限熔断躺平 | scaffold.toml `max_restarts` |
| on_fuse 钩子 | 熔断前给你一次自愈机会(重启游戏/重登), 写 task.py 里 `def on_fuse(ctx) -> bool` | task.py |
| 无进展看门狗 | 画面卡死没异常也逃不过, 超时自动停+截图 | scaffold.toml `idle_timeout` |
| FatalError | `raise FatalError("封号")` 致命场景直接停, 不白烧重开次数 | task.py |
| 截图留痕 | `shot("标签")` 与失败自动截图, 都进 logs/shots | 自动 |

## 七、打包与升级
### 打包 exe 发给别人
```bash
uv run build_exe.py
```

产出 `dist/<你的名>-v<版本>.zip`: 目标机**零 Python**, 解压即用;
`templates/` 与 `scaffold.toml` 摆 exe 旁, 用户可自行调参。
**bin/ 注入件会被 Defender 报毒**, 目标机需把解压目录加入杀毒排除——发给人时记得交代。

### 升级脚手架
作者在群里发新版时:

1. 下载新的两个 whl, 替换 `libs/` 里的同名旧文件(文件名里的数字就是版本号);
2. pyproject 里 `[tool.uv.sources]` 两行 path 改成新文件名;
3. `uv sync`。

不领新版就继续用旧的, 互不影响。

## 八、常见问题
### FAQ
(本章留白, 条目随实战反馈逐条补录。)
