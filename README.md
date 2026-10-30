# imgbot-template · 图色脚本脚手架

imgbot 门面之上的项目模板:**拷贝本目录改名 = 新脚本项目**。开发者只写两个文件,其余(中控台/热键收编/Worker 生命周期/双层配置/异常重开/日志留痕)框架全包。

## 快速开始

```bash
uv sync                          # 依赖(含 imgbot path 引用)
uv run python test/legend_game.py   # 开测试游戏(另开终端)
uv run python test/auto_farm/main.py   # 挂机辅助(自动打怪示范, 跑 10s 后 Ctrl+C)
```

---

# 开发手册

## 目录

```
├── main.py            # 单开入口(裸跑, Ctrl+C 停)
├── console.py         # 多开中控台(ttkbootstrap, 热键收编)
├── scaffold.toml      # 脚手架层配置(框架的: 通道/热键/UI/重开策略)
├── business.py        # ★ 业务配置 dataclass + FIELD_META(弹窗自动生成)
├── task.py            # ★ main_task(ctx) 总入口 + 子任务(打字示例)
├── bot/               # 框架包(拷走不改)
│   ├── worker.py      #   生命周期: 绑定→ctx→任务→异常重开→收口
│   ├── backends.py    #   adb / window 两端(发现/绑定/ctx 组装)
│   ├── hotkeys.py     #   F9 热键收编(hover/focus 拾取)
│   ├── dsl.py         #   顶层命令表(click/key/wait_pic/..., task.py import * 直用)
│   ├── settings.py    #   scaffold.toml 读写
│   ├── store.py       #   business.yaml 读写
│   └── console_ui.py  #   中控台 UI
├── test/              # 测试辅助
│   ├── legend_game.py #   类传奇小游戏(挂机靶场, 图色色值见文件头)
│   ├── game_smoke.py  #   游戏冒烟(识别/点击/击杀/掉落)
│   ├── farm_e2e.py    #   挂机 E2E(金币增长验证)
│   ├── auto_farm/     #   挂机辅助项目(基于脚手架二开的示范)
│   ├── pick_probe.py  #   窗口拾取探测(hover/focus)
│   └── tpl_crop.py    #   模板裁剪(截窗→框选→存 templates)
├── templates/         # 图色素材 PNG
└── logs/              # 运行产物(shots 留痕, gitignore)
```

## AI 拷贝规程(基于本脚手架新建项目)

给 AI 会话的硬规程,按序执行,每步带验收。目录名可中文;`pyproject.toml` 的 `name` 用英文。

1. **整目录拷贝改名**: 复制本目录 → 新位置(如 `D:\script-workspace\龙谷助手`)。
   排除 `.git/`、`.scratch/`、`logs/`、`__pycache__/`、`.venv/`;`uv.lock` 一并拷走。
   验收: 新目录含 `bot/` `main.py` `console.py` `business.py` `task.py` `scaffold.toml` `pyproject.toml` `uv.lock` `templates/`。
2. **imgbot path 引用**: `pyproject.toml` 的 `[tool.uv.sources] imgbot = { path = "../imgbot", editable = true }`。
   新项目与 imgbot 仓同级则不改;不同级改成实际路径。改完 `uv sync`(lock 随之更新)。
   **必须 editable**: 否则 venv 里是安装快照, imgbot 仓改了代码这边静默跑旧版。
   验收: `uv sync` 无错,`uv run python -c "import imgbot"` 通过。
3. **改名**: `pyproject.toml` 的 `name`/`description` 换成新项目。
4. **写业务,只动两个 ★ 文件**: 覆写根 `task.py`(`main_task(ctx)` + 子任务函数,一律吃 ctx;
   出厂打字示例整段替换)与 `business.py`(dataclass + FIELD_META,中控台弹窗自动生成)。
   **禁止**: 改 `bot/`;写 `IMGBOT_TEMPLATE_ROOT`/sys.path 引导——那是仓内 `test/auto_farm`
   寄生上层 `bot/` 的做法,拷出的项目自带 `bot/`,不需要。
5. **清理模板自留件**: `test/` 只保留 `tpl_crop.py`(模板裁剪)与 `pick_probe.py`(窗口探测),
   其余(`legend_game.py` 靶场、`game_smoke.py`、`farm_e2e.py`、`auto_farm/` 示范)删除;
   根 `selfcheck.py` 是出厂打字示例的自检,task.py 覆写后即失效,一并删除。
6. **素材**: 模板 PNG 进 `templates/`(`uv run python test/tpl_crop.py` 截目标窗口裁剪)。
7. **验证 + 首提交**: `uv run console.py` → 开目标窗口 → 悬停按 F9 收编 → 跑通一轮
   → `git init` 首提交。

## 发布

```bash
uv run build_exe.py        # 名字/版本取自 pyproject.toml
```

产物 `dist/<名>-v<版本>.zip`(绿色包, 目标机零 python):exe + `_internal/`(依赖
全冻)+ `bin/`(潜影注入件)+ `templates/` + `scaffold.toml`——后两者摆 exe 旁,
用户可编辑;`business.yaml`/`logs/` 首次运行自动生成。**bin/ 注入件会被
Defender 报毒, 发布机与目标机都需加排除目录**(交接运维常识)。

---

# 测试手册 · 挂机辅助项目(auto_farm)

操作传奇小游戏(imgbot-legend)的挂机项目,位于 **`test/auto_farm/`** —— 基于
脚手架二开的完整示范,开发者写的东西只有 `business.py`(挂机参数)和
`task.py`(自动打怪循环)两个文件。

## 怎么跑

```bash
# 终端 1: 开游戏
uv run python test/legend_game.py

# 终端 2: 开挂机(单开模式, 3 秒后自动开始打怪)
uv run python test/auto_farm/main.py

# 或多开中控台(F9 收编游戏窗口, 表格启停)
uv run python test/auto_farm/console.py
```

## 它自动做什么

找怪(红色圆 #CC3333)→ 点击选中(角色自动攻击)→ 等击杀 →
捡金币(#FFD700)→ 循环。日志/表格实时显示"锁定怪 → 击杀 ×N → 捡金币"
完整序列; 连续失败自动重开, 超限熔断(可配)。

## 挂机参数(business.py)

| 参数 | 默认 | 说明 |
|---|---|---|
| attack_wait | 10.0 秒 | 点击怪物后等它死的超时 |
| coin_timeout | 6.0 秒 | 等金币掉落的超时 |
| max_kills | 0 | 最大击杀数(0 = 无限挂机) |

## 配套工具(test/)

| 工具 | 用途 |
|---|---|
| `pick_probe.py` | 实时显示 hover/focus 拾到的窗口(句柄/类名/标题), 定 pick_mode 用 |
| `tpl_crop.py` | 模板裁剪: 截当前鼠标下窗口 → 框选 → 存 templates/*.png |
| `game_smoke.py` | 游戏冒烟: 识别/点击/击杀/掉落自动验收 |
| `farm_e2e.py` | 挂机 E2E: 40 秒金币增长自动验收 |

### 二开流程(新脚本)

1. 拷贝本目录改名(如 `龙谷助手`)→ `uv sync`
2. `business.py` 写业务配置字段(或让 AI 写)
3. `task.py` 写 `main_task(ctx)` + 子任务(或让 AI 写)
4. `test/tpl_crop.py` / pixpick 制作素材进 `templates/`
5. `uv run main.py`(单开)或 `uv run console.py`(多开)

### DSL 顶层命令(task.py 免前缀)

task.py 顶部 `from bot.dsl import *` 后, 挂机动词直接写: `click(231, 347)`、
`key("ctrl+s")`、`sleep(500)`。速查表在 `bot/dsl.py` 模块头(权威版), 要点:

- **凡时间皆毫秒**: `sleep(500)` = 半秒, `wait_pic(..., timeout=10000)` = 10 秒(默认)
- **找不到/超时返回 None 或 False, 不抛异常**: "没找到"是挂机常态; 真故障由框架重开兜底
- **F9 停止贯穿**所有 sleep 与等待, 按下即醒即退
- 招牌复合动作: `find_tap(找到就点)` / `tap_until_gone(连点到消失)`
- 冷门动作(`wait_until/retry/swipe_find/read_number/...`)与窗口管理走
  `ctx.ops / ctx.dm / ctx.device` 逃生舱, 能力一分不少

```python
from bot.dsl import *          # 唯一的前缀

def main_task(ctx):
    hit = find_color("CC3333", tol=40)          # [(x, y), ...] 或 []
    if hit:
        click(*hit[0])
        if wait_color_gone("CC3333-282828", timeout=10000):
            log("击杀")
```

### ctx 一览(任务代码的全部世界)

| 字段 | window 端 | adb 端 |
|---|---|---|
| `ctx.ops` | ✅ Ops 门面(find_tap/wait_pic/find_color/...) | — |
| `ctx.dm` | ✅ DmSoft(MoveTo/KeyPress/FindWindow/...) | — |
| `ctx.device` | — | ✅ AdbTarget(actions.* 魔神方言) |
| `ctx.cfg` | ✅ 业务配置对象 | ✅ |
| `ctx.log` / `ctx.stop` / `ctx.shot(tag)` | ✅ | ✅ |

### 熔断恢复钩子(on_fuse)

连续异常超过 `max_restarts` 次熔断前, worker 给业务一次自愈机会——`task.py` 里定义:

```python
def on_fuse(ctx) -> bool:
    """重启游戏→重新登录→进挂机地图; 全部就绪返回 True。"""
    ...重启登录流程...
    return True
```

返回 True = 已恢复(重开计数清零继续挂);不定义/返回 False/自身抛异常 = 维持熔断
躺平(现状行为, 零侵入)。这是"挂过夜"和"挂两小时就断"的分界线。

### 中控台

- **F9 热键收编**: 鼠标悬停目标窗口按 F9 → 加入表格并启动; 再按停止。拾取方式(hover/focus)在 scaffold.toml
- 表格双击/按钮启停; 右侧日志实时流(按级别着色)
- ⚙ 设置双 Tab: 脚手架(通道/热键/重开策略/UI) / 业务(自动按 FIELD_META 生成)
- 窗体尺寸/左右比例/主题 = scaffold.toml `[ui]`, 用户不可调

