# 图色脚本脚手架(imgbot-template)设计定稿

Status: resolved(炉问三轮, 用户逐条确认)

## 定位

imgbot 门面之上的项目模板: 拷贝改名即新脚本项目。开发者只写两个文件
(business.py 业务配置 + task.py 任务), 其余全部框架承担。

## 炉问结论(用户裁定)

1. **发现模型**: PC 窗口线 = 热键收编(悬停/点选目标窗口 → F9 拾取并启动,
   再按停止), 不做窗口枚举发现。拾取方式配置项: hover(鼠标下窗口) /
   focus(活动窗口的焦点子窗口, 模拟器渲染窗场景)。模拟器 adb 线保留
   自动发现(discovery 原样), 热键只服务 PC 窗口线。adb 天然后台不可丢。
2. **单后端**: 一个项目只支持一个端(adb 或 window), 任务按后端方言写
   (adb=actions.* 魔神语法原样保留 / window=ops.* 大漠语法), 框架层
   (中控台/热键/配置/Worker 生命周期)全共享。不做跨端任务通用。
3. **配置两层**, 不混:
   - 脚手架层 scaffold.toml(框架自己的, 固定 schema): backend/window_class/
     通道三件套/pick_mode/hotkey(F9)/max_restarts(3)/loop_interval/
     [ui] window_size/left_ratio/theme
   - 业务层 business.py(dataclass+FIELD_META) ↔ business.yaml(自动持久化),
     UI 自动生成, 代码里 ctx.cfg.* 直用
4. **线程模型**: 中控台一进程, 每窗口一 Worker 线程(魔神同款)。
5. **异常恢复**: 任务异常 → 自动重开, max_restarts 可配, 连败熔断标红。
6. **GUI**: ttkbootstrap, 左右结构(左=目标表格+启停按钮, 右=日志面板,
   按窗口着色), 窗体尺寸/左右比例/主题 = 脚手架层 [ui] 配置,
   root.resizable(False,False) 用户锁死。
7. **热键实现**: GetAsyncKeyState 轮询(50ms), 不用 RegisterHotKey。
8. **双入口**: main.py 单开(裸跑 Ctrl+C) / console.py 多开, 共享全部逻辑。
9. **发布**: PyInstaller onedir(绿色 zip 与安装器解开是同一目录),
   bin\ 潜影注入件独立发货, 源码不发货(task/business 冻结进 exe),
   安装器顺手做 Defender 排除。build_exe.py 排最后。
10. **ctx 协议**: main_task(ctx), 绑定/解绑在框架层; ctx = backend/dm/ops/
    device(按端)/cfg/log/stop/shot。

## ctx 字段

| 字段 | window 端 | adb 端 | 说明 |
|---|---|---|---|
| backend | "window" | "adb" | 方言判别 |
| dm | DmSoft | — | 大漠姿势直调 |
| ops | Ops 门面 | — | find_tap/wait_pic/... |
| device | — | AdbDevice | actions.wait_tap(ctx.device, ...) |
| cfg | ✅ | ✅ | 业务配置对象 |
| log | ✅ | ✅ | 带窗口名日志(面板+文件双写) |
| stop | ✅ | ✅ | 停止信号 |
| shot(tag) | ✅ | ✅ | 留痕 logs/shots |

## 目录

```
imgbot-template/
├── pyproject.toml       # 依赖 imgbot(path)
├── main.py              # 单开入口
├── console.py           # 多开中控台入口
├── scaffold.toml        # 脚手架层配置
├── business.py          # ★ 业务配置 dataclass+FIELD_META(示例)
├── task.py              # ★ main_task(ctx) 总入口+子任务(示例)
├── bot/                 # 框架包(拷走不改)
│   ├── worker.py        # Worker 线程(绑定包住任务/异常重开/收口)
│   ├── backends.py      # adb/window 两端: 发现+绑定+ctx 组装
│   ├── hotkeys.py       # GetAsyncKeyState 轮询+拾取
│   ├── settings.py      # scaffold.toml 读写
│   ├── store.py         # business.yaml ↔ dataclass
│   └── console_ui.py    # 中控台(ttkbootstrap, schema 驱动)
├── templates/           # PNG 素材
└── logs/                # 运行产物(gitignore)
```

## 验收

- 热键收编记事本 → 表格出行 → 启停 → 日志双写 → 异常重开熔断
- main.py 单开 Ctrl+C 全链
- 业务配置弹窗改值 → business.yaml 落盘 → ctx.cfg 读到新值
