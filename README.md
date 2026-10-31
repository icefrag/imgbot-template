# imgbot-scaffold · 图色脚本脚手架(框架仓)

薄项目模型的框架仓: 脚本开发者基于"骨架 zip + wheel 文件"开发自己的挂机项目,
**不拷贝本仓**;引擎机密(imgbot+潜影)闭源编译,脚手架层开源推广。
术语见 [GLOSSARY.md](GLOSSARY.md),发行模型决策见
[ADR-0001](docs/adr/0001-库化分发-引擎闭源脚手架开源文件分发.md),
给脚本开发者的文档见 [docs/脚手架使用手册.md](docs/脚手架使用手册.md)。

## 实施进度(读前必看)

本 README 与用户手册描述**目标形态**,以下步骤落地前,标注"过渡期"的章节仍按旧方式:

| 步骤 | 内容 | 状态 |
|---|---|---|
| ① | 本仓翻转+改名 `bot/`→`imgbot_scaffold/`,全量引用/文档跟进 | 待做 |
| ② | 引擎编译管线: imgbot 出 .pyd wheel(闭源)+ .pyi 桩 | 待做 |
| ③ | 骨架打包脚本 `scripts/make_skeleton.py` + 发版自测规程 | 待做 |
| ④ | auto_farm 迁移转正为第一个薄项目 | 待做 |

## 分层与通道(整套用法速览)

| 层 | 内容 | 形态 | 给谁 |
|---|---|---|---|
| 引擎层 | imgbot 库 + 潜影注入件 | 闭源编译 wheel(`imgbot-*.whl`) | 随骨架 zip 分发 |
| 脚手架层 | 本仓 `imgbot_scaffold/`(worker/中控台/DSL/设置) | 开源纯源码 wheel(`imgbot_scaffold-*.whl`) | 同上,源码上 GitHub 做门面 |
| 薄项目 | 入口四件套 + task/business + 素材 | 骨架 zip 解压即开发 | 脚本开发者 |

三类人三种吃法,同一个薄项目形态:

- **我(作者 dogfood)**: 直链——薄项目 pyproject 加 `[tool.uv.sources]` 指回本仓与 imgbot 仓
  (editable),改完即生效,无版本概念;
- **脚本开发者(国内)**: 骨架 zip 里的 `libs/*.whl` 本地文件安装,三方依赖走清华镜像,
  **全程不碰 GitHub**;文件名即版本,不领新版不被动升级;
- **脚本使用者**: 脚本开发者 `build_exe` 打出的绿色 zip,零 Python。

## 我的日常(直链开发)

```bash
# 本仓改框架 → 到任一薄项目(如 auto_farm)冒烟, 保存即生效:
cd D:\script-workspace\auto_farm && uv run console.py
```

薄项目 pyproject 长这样(路径按实际层级):

```toml
[project]
name = "auto-farm"
dependencies = ["imgbot-scaffold", "imgbot[ocr]"]

[tool.uv.sources]
imgbot-scaffold = { path = "../imgbot-template", editable = true }
imgbot = { path = "../imgbot", editable = true }
```

`tool.uv.sources` 是**消费方项目里**的覆盖项,只影响我的工作区;用户拿到的是 wheel 文件,
两条通道互不相扰。imgbot 必须 editable,否则 venv 里是快照,源仓改动这边静默跑旧版(踩过)。

## 发版流(每次对外发骨架 zip)

```bash
# 1. 版本号: 本仓 pyproject version + CHANGELOG(语义: 破坏性=大版本, DSL 加命令=小版本, 修 bug=补丁)
# 2. 脚手架 wheel(纯源码, 不编译):
uv build                                    # → dist/imgbot_scaffold-0.3.0-py3-none-any.whl
# 3. 引擎 wheel(闭源编译): 到 imgbot 仓按其 README 出 imgbot-0.x.x-cp312-win_amd64.whl
# 4. 打骨架:
uv run scripts/make_skeleton.py             # → dist/skeleton-v0.3.0.zip
#    = 四件套 + scaffold.toml + tools/(pick_probe) + libs/ 两 whl + 使用手册 + DSL语法清单
# 5. 自测(铁律): 干净目录解压 → uv sync → 跑通一轮冒烟, 按的就是用户姿势
# 6. 发群文件, 群公告记版本号与更新说明
```

## 版本策略

- wheel 文件名即版本,uv 锁哈希防偷换;用户升级 = 换 `libs/` 文件 + 改 pyproject 那一行 + `uv sync`;
- 用户各持各版互不牵连,"一损俱损"只存在于我的直链工作区;
- 将来若走收费授权: 在引擎层上锁,不惊动任何存量薄项目。

## 仓结构(目标态, ①完成后)

```
├── imgbot_scaffold/      # 框架包(开源)
│   ├── worker.py         #   生命周期: 绑定→ctx→任务→异常重开→收口
│   ├── backends.py       #   adb / window 两端(发现/绑定/ctx 组装)
│   ├── hotkeys.py        #   F9 热键收编(hover/focus 拾取)
│   ├── dsl.py            #   顶层命令表(task.py import * 直用)
│   ├── settings.py       #   scaffold.toml 读写
│   ├── store.py          #   business.yaml 读写
│   └── console_ui.py     #   中控台 UI
├── scripts/              # build_docs.py(DSL 清单生成) + make_skeleton.py
├── skel/                 # 薄项目四件套母版(骨架 zip 的料)
├── docs/                 # DSL语法清单 + 脚手架使用手册 + adr/
├── test/                 # 靶场与冒烟(legend_game/game_smoke/farm_e2e...)
└── GLOSSARY.md
```

DSL 文档纪律: 任何 `imgbot_scaffold/dsl.py` 变更必须重跑 `uv run scripts/build_docs.py`
并提交三产物(md/html/chm),详见 [AGENTS.md](AGENTS.md)。

## 框架开发手册

### DSL 要点(task.py 免前缀)

`from imgbot_scaffold.dsl import *` 后直接写: `click(x, y)` / `key("ctrl+s")` /
`sleep(500)`。速查表在 `dsl.py` 模块头,权威版 [docs/DSL语法清单.md](docs/DSL语法清单.md)。

- **凡时间皆毫秒**; **找不到/超时返回 None/False 不抛**——"没找到"是挂机常态,真故障由重开兜底
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

## 过渡期: 旧·拷贝规程(步骤①③完成前,新项目仍走这条)

1. 整目录拷贝本仓改名(排除 `.git/ .scratch/ logs/ __pycache__/ .venv/`),`uv sync`;
2. pyproject 的 imgbot path 指到实际层级,**必须 editable**;
3. 改 name/description; 写根 `task.py` + `business.py`(禁改 `bot/`,禁 sys.path 寄生);
4. `test/` 只留 `tpl_crop.py`/`pick_probe.py`, 删 `selfcheck.py` 与示范;
5. 素材进 `templates/`(任意截图工具裁);
6. `uv run console.py` 跑通 → `git init` 首提交。

## 发布 exe(薄项目 → 脚本使用者)

骨架自带薄 `build_exe.py`,名字/版本取自薄项目 pyproject:

```bash
uv run build_exe.py     # → dist/<名>-v<版本>.zip(exe + _internal/ + bin/ + templates/ + scaffold.toml)
```

bin/ 注入件会被 Defender 报毒,发布机与目标机都需加排除目录(交接常识)。
