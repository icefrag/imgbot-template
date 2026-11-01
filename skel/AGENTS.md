# AGENTS.md · icefrag 薄项目(给 AI 开发代理的军规)

你在用户的挂机脚本项目里工作。框架叫 icefrag: 绑定/中控台/热键/异常重开/日志留痕
全是框架的, 业务只写两个文件。人看的说明书是 README.md, 命令权威表在 docs/。

## 铁律(违者必返工)

1. **只写 `task.py`(任务逻辑)与 `business.py`(业务参数)**; 素材 PNG 放 `templates/`;
   需要调通道/热键/看门狗时改 `scaffold.toml`。
   **禁改**: `console.py`/`build_exe.py`(框架薄入口)、`libs/`(框架 wheel,
   升级=作者发新文件, 换文件改 pyproject 那行 + uv sync)、`.venv/`。
2. **main_task(ctx) = 任务全程, 正常返回 = 任务完成收口**: 挂机循环自己写
   `while not stopped():`。预期内的失败(没找到怪/点击落空)在循环里
   try/except 掉——那是业务;冒泡异常框架自动重开(重绑重进, 连败 max_restarts 次
   熔断;可定义 `on_fuse(ctx) -> bool` 自救);重开也救不了的场景
   `raise FatalError("账号被封")`。
3. 命令三律: **凡时间皆毫秒**;**找不到/超时返回 None/False 不抛异常**;
   **F9 停止贯穿一切 sleep 与等待**。
4. 命令表以 `docs/DSL语法清单.md` 为权威(签名由框架实时内省生成, 与代码不漂移)。
   icefrag 命令只收组装(拟人/等待/复合); 没有现成命令的操作走逃生舱:
   `ctx.ops`(图色门面)/`ctx.dm`(DmSoft 全量接口)/`ctx.device`(adb 魔神方言)。
5. 业务参数: `business.py` 一个 dataclass, 字段带默认值 + `FIELD_META = {"字段名":
   ("中文名", "entry"|"combo:选项1|选项2")}`(bool 字段自动是/否下拉), 中控台设置
   弹窗自动生成、改值落盘 business.yaml。任务里 `ctx.cfg.字段名` 取当前值。

## 验证循环

1. `uv run console.py` 中控台(鼠标悬停目标窗口按 F9 收编, 收编几个跑几个),
   表格选行看右侧日志;
2. `logs/shots/` 是截图留痕(`shot("标签")` 与异常/看门狗自动截图都在),
   排查"画面到底长什么样"先翻这里——那是框架眼里的画面, 与屏幕截图同源;
3. 打包给最终用户: `uv run build_exe.py` → `dist/<名>-v<版本>.zip`
   (目标机零 Python; bin/ 注入件被 Defender 报毒是常态, 加排除目录)。

## 环境(不用你管, 知道即可)

Python 3.12 钉死(`.python-version`);依赖全在 `libs/` 本地 wheel + 清华镜像,
**没有 GitHub 依赖, 不要往 dependencies 里加任何东西**;
升级框架 = 作者发新 whl → 换 `libs/` 文件 → 改 pyproject 那一行 → `uv sync`。
