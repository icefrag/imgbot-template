# imgbot-template DSL 语法清单

> 参数表由 `scripts/build_docs.py` 从 bot/dsl.py 签名内省生成,
> 改 dsl 后重跑脚本(AGENTS.md 规则)。铁律: 凡时间皆毫秒 / 超时返
> None 不抛 / F9 贯穿 / ctx.dm·ctx.ops·ctx.device 是逃生舱。

## 键鼠

| 命令 | 原型 | 说明 |
|---|---|---|
| **click** | `click(x, y)` | 点击 (x, y)。window: 移动+左键; adb: tap。 |
| **dblclick** | `dblclick(x, y)` | 双击 (x, y)。 |
| **move** | `move(x, y)` | 悬停(不点)。adb 端无悬停概念, 报错指路。 |
| **key** | `key(s)` | 按键/组合键: key("enter") / key("ctrl+s")(修饰键 ctrl/alt/shift/win)。 |
| **sleep** | `sleep(ms)` | 可中断睡眠: F9 按下立刻醒(代替 time.sleep 的傻等)。 |

## 消息

| 命令 | 原型 | 说明 |
|---|---|---|
| **log** | `log(text, level='info')` |  |
| **shot** | `shot(tag='')` |  |

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
| **find_tap** | `find_tap(pic, region=None, timeout=0, threshold=None)` | 找到就拟人点。timeout=0 单帧试; 超时返 False。 |
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

## 读数

| 命令 | 原型 | 说明 |
|---|---|---|
| **read_text** | `read_text(region=None)` |  |

## 示例速查

**click**
```python
click(231, 347)                       # 选中怪(角色自动攻击)
```

**dblclick**
```python
dblclick(400, 300)
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
from bot.dsl import Pt
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
hit = wait_text("挑战成功")                    # OCR (x,y,相似度)|None
```

**read_text**
```python
text = read_text(region=(10, 600, 300, 640))   # 状态栏 OCR
```
