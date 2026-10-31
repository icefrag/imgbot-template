# icefrag DSL 语法清单

> 参数表由 `scripts/build_docs.py` 从 icefrag/dsl.py 签名内省生成,
> 改 dsl 后重跑脚本(AGENTS.md 规则)。铁律: 凡时间皆毫秒 / 超时返
> None 不抛 / F9 贯穿 / ctx.dm·ctx.ops·ctx.device 是逃生舱。

## 键鼠

| 命令 | 原型 | 说明 |
|---|---|---|
| **click** | `click(x, y, jitter=None, human=None, settle=None)` | 点击 (x, y)。默认拟人: 贝塞尔轨迹到位→随机停顿→落点抖动(默认见 |
| **dblclick** | `dblclick(x, y, jitter=None, human=None, settle=None)` | 双击 (x, y), 参数同 click; adb 端两击带 80~120ms 间隔。 |
| **drag** | `drag(x1, y1, x2, y2, ms=350)` | 按住拖拽(列表滚动/滑块): window=按住左键插值拖, adb=原生 swipe。 |
| **move** | `move(x, y)` | 悬停(不点)。adb 端无悬停概念, 报错指路。 |
| **key** | `key(s)` | 按键/组合键: key("enter") / key("ctrl+s")(修饰键 ctrl/alt/shift/win)。 |
| **sleep** | `sleep(ms)` | 可中断睡眠: F9 按下立刻醒(代替 time.sleep 的傻等)。 |

## 消息

| 命令 | 原型 | 说明 |
|---|---|---|
| **log** | `log(text, level='info')` | 打一条日志(中控台日志面板/终端), level: info|warn|error。 |
| **shot** | `shot(tag='')` | 截当前绑定目标一帧存 logs/shots/(月日_时分秒_目标_标签.png)留痕, 返回路径或 None。 |
| **stopped** | `stopped()` | F9 停止键按下过吗 —— 挂机循环的退出条件: while not stopped(): ... |

## 找点(单帧)

| 命令 | 原型 | 说明 |
|---|---|---|
| **find_color** | `find_color(color, region=None, tol=0)` | 区域找全部色块。color="RRGGBB"(偏差给 tol, 或写 "RRGGBB-DRDGDB")。 |
| **find_all** | `find_all(pic, region=None, threshold=None)` | 单帧找全部同类图(列表项/多目标), 近邻去重。 |
| **find_multi_color** | `find_multi_color(rect, points, direction=0)` | 多点找色(大漠 FindMultiColor 对应物): 锚点在 rect 内搜索, 全部相对 |
| **exists** | `exists(pic, region=None, threshold=None)` |  |

## 复合动作

| 命令 | 原型 | 说明 |
|---|---|---|
| **find_tap** | `find_tap(pic, region=None, timeout=0, threshold=None, verify=None)` | 找到就拟人点(贝塞尔轨迹+停顿)。timeout=0 单帧试; verify=点后必须 |
| **tap_until_gone** | `tap_until_gone(pic, region=None, timeout=10000, threshold=None)` | 连点直到图消失(确定/领取类), 返回点击次数; 不出现返回 0。 |

## 等待(超时返 None/False)

| 命令 | 原型 | 说明 |
|---|---|---|
| **wait_pic** | `wait_pic(pic, region=None, timeout=10000, threshold=None)` | 等图出现, 返回 (中心x, 中心y, 分数); 超时自动截图留痕。 |
| **wait_pic_any** | `wait_pic_any(pics, region=None, timeout=10000, threshold=None)` | 等一组模板任一出现, 返回 (名字, x, y, 分数); 超时 None。 |
| **wait_pic_gone** | `wait_pic_gone(pic, region=None, timeout=10000, threshold=None)` | 等图消失(加载页结束判定)。 |
| **wait_color** | `wait_color(color, region=None, timeout=10000)` | 等某色出现(色比图快), 返回 (x, y) 或 None。偏差写进色串: |
| **wait_color_gone** | `wait_color_gone(color, region=None, timeout=10000)` | 等某色消失(等击杀/等加载), 消失 True / 超时 False。 |
| **wait_text** | `wait_text(text, region=None, timeout=10000)` | OCR 等文字出现("完成"提示类), 返回 (中心x, 中心y, 相似度) 或 None。 |

## 识字 / 找字(OCR)

| 命令 | 原型 | 说明 |
|---|---|---|
| **ocr** | `ocr(region=None, fast=False)` | 识字: OCR 读区域全文, 行间空格连接("任务名叫什么"用这个)。 |
| **ocr_numbers** | `ocr_numbers(region=None)` | 识数: OCR 全文后抠所有数字串(等级取 [0], 坐标取 [:2]); 没识到返回 []。 |
| **find_str** | `find_str(text, region=None, min_ratio=0.7)` | 找字(大漠 FindStr 风): OCR 定位 + 按序比例匹配, 返回 (x, y) 或 None, |

## 导航(需 task.py 声明表)

| 命令 | 原型 | 说明 |
|---|---|---|
| **go** | `go(name, timeout=120000)` | 走到目标界面, 图自动带路(BFS)+迷路重定位自愈。到达 True / 超时安静 |
| **at** | `at(name)` | 期望验证: 当前是否在指定界面(单帧一张锚点, 高频便宜; 迷路判别用 go)。 |

## 看门狗

| 命令 | 原型 | 说明 |
|---|---|---|
| **progress** | `progress(note='')` | 手动打一次进展点(看门狗信号; find/wait 命中与点击已自动打点)。 |

## 示例速查

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

**sleep**
```python
sleep(500)                            # 半秒, F9 按下立刻醒
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
while not ctx.stop.is_set():
    progress("等刷新")          # 长轮询手动打点, 防看门狗误杀
    sleep(2000)
```
