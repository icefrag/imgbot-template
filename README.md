# icefrag · 图色脚本脚手架(框架仓)

薄项目模型的框架仓: 脚本开发者基于"骨架 zip + wheel 文件"开发自己的挂机项目,
**不拷贝本仓**;引擎机密(imgbot+潜影)编译闭源,脚手架层开源推广。
术语见 [GLOSSARY.md](GLOSSARY.md),发行模型决策见
[ADR-0001](docs/adr/0001-库化分发-引擎闭源脚手架开源文件分发.md),
给脚本开发者的文档见 [docs/脚手架使用手册.md](docs/脚手架使用手册.md)
(随骨架 zip 分发时名 README.md)。

## 实施进度

| 步骤 | 内容 | 状态 |
|---|---|---|
| ① | 翻转+改名 `bot/`→`icefrag/`;bootstrap/build 抽进包,根入口变薄 | **完成** |
| ② | 引擎闭源编译: imgbot 出 .pyd wheel + .pyi 桩 | 待做(现发**开源** wheel, 链路等价) |
| ③ | 骨架打包 `scripts/make_skeleton.py` + 干净目录自测 | **完成(试装版)** |
| ④ | auto_farm 从 sys.path 寄生迁移为标准薄项目 | 待做(寄生方式目前仍可用) |

## 分层与通道(整套用法速览)

| 层 | 内容 | 形态 | 给谁 |
|---|---|---|---|
| 引擎层 | imgbot 库 + 潜影注入件 | wheel(`imgbot-*.whl`, bin/ 已随包; ②后闭源编译) | 随骨架 zip 分发 |
| 脚手架层 | 本仓 `icefrag/`(worker/中控台/DSL/设置/bootstrap/build) | 开源纯源码 wheel(`icefrag-*.whl`) | 同上 |
| 薄项目 | 薄入口(console/build_exe) + task/business + 素材 | 骨架 zip 解压即开发 | 脚本开发者 |

三类人三种吃法,同一个薄项目形态:

- **我(作者 dogfood)**: 直链——薄项目 pyproject 加 `[tool.uv.sources]` 指回本仓与 imgbot 仓
  (editable),改完即生效;
- **脚本开发者(国内)**: 骨架 zip 里的 `libs/*.whl` 本地文件安装,三方依赖走清华镜像,
  **全程不碰 GitHub**;文件名即版本,不领新版不被动升级;
- **脚本使用者**: 脚本开发者 `build_exe.py` 打出的绿色 zip,零 Python。

## 我的日常(直链开发)

```bash
# 本仓改框架 → 到任一薄项目冒烟(④前用 test/auto_farm, sys.path 寄生方式), 保存即生效
uv run python test/auto_farm/main.py
```

薄项目 pyproject 长这样(路径按实际层级;`tool.uv.sources` 是消费方覆盖项,
只影响我的工作区):

```toml
[project]
name = "auto-farm"
dependencies = ["icefrag", "imgbot[ocr]"]

[tool.uv.sources]
icefrag = { path = "../imgbot-template", editable = true }
imgbot = { path = "../imgbot", editable = true }
```

imgbot 必须 editable,否则 venv 里是快照,源仓改动这边静默跑旧版(踩过)。

## 回归测试(改 DSL/键鼠/图色接口必跑)

自研 Win32 靶子游戏 `test/dummy_game.py`(icefrag靶场, gdi 截屏+PostMessage
键鼠**全后台**, 遮挡可跑不动真鼠标),把 DSL 全部动词打成 14 个 E2E 用例;
模板每轮从靶子实况自裁(同源裁材),不入库。

```bash
uv run test/test_dsl_game.py               # 全量(约 1 分钟, 15 用例)
uv run test/test_dsl_game.py find_tap nav  # 按名子串筛选用例(改哪测哪)
uv run test/test_dsl_mouse.py              # 离线组织层(秒级): 路由/抖动/停顿/key 序
```

规矩(与 DSL 文档纪律同级): `icefrag/dsl.py` 或 imgbot 键鼠/图色接口(Ops/
DmSoft/键鼠类)任何变更,先跑绿再算完。用例→动词映射表在
`test/test_dsl_game.py` 模块头;改靶子布局须与用例同步。未覆盖: dx/潜影
通道(需真 D3D 游戏)、adb 真机链路(鸭子逻辑由离线矩阵覆盖)、key() 的
windows 键盘通道(引擎历史死案, 离线覆盖)。

## 新项目出生(③已通, 现在就能用)

```bash
uv run scripts/make_skeleton.py     # → dist/skeleton-v0.1.0.zip
```

zip 内容: 薄入口(console/build_exe)+ business/task 示例 + scaffold.toml +
pyproject(依赖指向 libs/ 双 whl)+ tools/pick_probe + docs/DSL语法清单 + README(使用手册)。

- **发给别人**: zip 直接发群,对方解压 → 改 pyproject 的 name → `uv sync` → 写 task/business;
- **自用新项目**: 解压后把 pyproject 的两条 sources 改成上面的直链写法,即变成 dogfood 项目。

**发版铁律**: zip 发出前,干净目录解压 → `uv sync` → 冒烟通过(自测已按此走通:
wheel 装入 venv、注入件在包内、入口可导入)。

## 发版流(每次对外发骨架 zip)

```bash
# 1. 版本号: 本仓 pyproject version(语义: 破坏性=大版本, DSL 加命令=小版本, 修 bug=补丁)
#    引擎版本随 imgbot 仓自己的 version, make_skeleton 自动取两仓最新构建
uv run scripts/make_skeleton.py     # 内含两仓 uv build + 组装 + 压 zip
# 2. 干净目录自测(铁律, 见上)
# 3. 发群文件, 群公告记版本号与更新说明
```

## 版本策略

- wheel 文件名即版本,uv 锁哈希防偷换;用户升级 = 换 `libs/` 文件 + 改 pyproject 那两行 + `uv sync`;
- 用户各持各版互不牵连,"一损俱损"只存在于我的直链工作区;
- 将来若走收费授权: 在引擎层上锁,不惊动任何存量薄项目。

## 仓结构

```
├── icefrag/             # 框架包(开源, uv build 出 wheel)
│   ├── worker.py        #   生命周期: 绑定→ctx→任务→异常重开→收口
│   ├── backends.py      #   adb / window 两端(发现/绑定/ctx 组装)
│   ├── hotkeys.py       #   F9 热键收编(hover/focus 拾取)
│   ├── dsl.py           #   顶层命令表(task.py import * 直用)
│   ├── settings.py      #   scaffold.toml 读写
│   ├── store.py         #   business.yaml 读写
│   ├── console_ui.py    #   中控台 UI
│   └── build.py         #   发布链(build_exe.py 薄包装调它)
├── scripts/             # build_docs.py(DSL 清单生成) + make_skeleton.py(骨架打包)
├── skel/                # 骨架携带文件母版(AGENTS.md: 给对方 AI 代理的军规)
├── docs/                # DSL语法清单 + 脚手架使用手册 + adr/
└── test/                # dummy_game 自研靶场 + test_dsl_game(全动词 E2E)
                         # + test_dsl_mouse(离线) + selfcheck + auto_farm...
```

DSL 文档纪律: 任何 `icefrag/dsl.py` 变更必须重跑 `uv run scripts/build_docs.py`
并提交三产物(md/html/chm);同时必须跑绿回归测试(见上节)。详见 [AGENTS.md](AGENTS.md)。

## 框架开发手册

### DSL 要点(task.py 免前缀)

`from icefrag.dsl import *` 后直接写: `click(x, y)` / `key("ctrl+s")` /
`sleep(500)`。速查表在 `dsl.py` 模块头,权威版 [docs/DSL语法清单.md](docs/DSL语法清单.md)。

- **凡时间皆毫秒**; **找不到/超时返回 None/False 不抛**——"没找到"是挂机常态,真故障由重开兜底
- **循环归业务**: main_task 只被调用一次,返回=任务完成;挂机循环自己写
  `while not stopped():`,预期内失败自行 try/except,冒泡异常框架重开
- **F9 停止贯穿**所有 sleep 与等待; 招牌复合: `find_tap` / `tap_until_gone`
- 多点找色: `Pt(x, y, (B,G,R), tol)` 组点阵,全中才算(同色文字天然不全中)
- 逃生舱: `ctx.ops / ctx.dm / ctx.device` 能力一分不少

### ctx 一览

| 字段 | window 端 | adb 端 |
|---|---|---|
| `ctx.ops` | Ops 门面(find_tap/wait_pic/find_color/...) | — |
| `ctx.dm` | DmSoft(MoveTo/KeyPress/FindWindow/...) | — |
| `ctx.device` | — | AdbTarget(actions.* 魔神方言) |
| `ctx.cfg` / `ctx.log` / `ctx.stop` / `ctx.shot(tag)` | ✅ | ✅ |

### 长跑双保险与恢复线

- **FatalError**: `raise FatalError("封号")` 致命失败不重开;普通异常照旧自动重开+熔断
- **idle_timeout 看门狗**: find/wait 命中与点击算进展,安静卡死自动停+截图留痕
- **on_fuse(ctx) -> bool**: 熔断前自愈机会(重启/重登),返回 True 清零计数,是"挂过夜"的分界线
- **Nav 声明式导航**: `NAV_SCREENS/NAV_EDGES/NAV_INTERRUPTS` 三表建图,`go()/at()` BFS 带路,
  迷路自愈失败抛 LostError 接入重开线;单主循环线性脚本用不上,别为上图上图

### 中控台

F9 收编(hover/focus 拾取)/表格启停/双击改名(别名持久化)/📷 实时预览(纯内存多开)/
右侧日志流;⚙ 设置双 Tab: 开发期脚手架+业务,exe 里只有业务;`aliases.json` 记别名。

## 发布 exe(薄项目 → 脚本使用者)

薄项目根的 `build_exe.py` 是两行包装,逻辑在 `icefrag/build.py`,名字/版本取自薄项目
pyproject:

```bash
uv run build_exe.py     # → dist/<名>-v<版本>.zip(exe + _internal/ + bin/ + templates/)
```

bin/ 注入件会被 Defender 报毒,发布机与目标机都需加排除目录(交接常识)。
