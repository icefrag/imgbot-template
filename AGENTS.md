# imgbot-template · Agent 须知

图色脚本项目模板(imgbot 门面之上的脚手架)。拷贝本目录改名即新项目,
开发者只写 `task.py`(业务逻辑)+ `business.py`(业务配置),详见 README。

## DSL 语法清单文档(必守)

- 位置: `docs/DSL语法清单.{md,html,chm}`(md 给 AI,CHM 给人);
  生成器 `scripts/build_docs.py` —— 命令表从 `icefrag/dsl.py` 的
  `inspect.signature` 实时内省, 与代码不漂移; 示例/分类手排在生成器里。
- **规则: 任何 `icefrag/dsl.py` 变更(增删命令/改签名/改默认值/docstring)
  必须重跑 `uv run scripts/build_docs.py` 并把三产物一起提交**,
  否则文档与命令表漂移。CHM 编译依赖便携 hhc(`D:/tools/hhw/hhc.exe`,
  不存在时留工程手动编, md/html 仍有效)。

## DSL 回归测试(必守)

- **规则: `icefrag/dsl.py` 或 imgbot 键鼠/图色接口(Ops/DmSoft/键鼠类)任何变更,
  必须跑绿 `uv run test/test_dsl_game.py`(全动词 E2E, 纯 Win32 靶
  `test/dummy_game.py`, gdi+windows 全后台通道)和
  `uv run test/test_dsl_mouse.py`(离线组织层: 路由/抖动/停顿/key 序)**。
  可按名筛选定位回归: `uv run test/test_dsl_game.py find_tap nav`。
  用例→动词映射表在 `test/test_dsl_game.py` 模块头; 改靶子布局须两边同步。

## 两仓关系

- `icefrag/` 框架包属本仓; 图色/键鼠底层来自 imgbot 库(`D:\script-workspace\imgbot`,
  pyproject path 引用且 **editable** —— 源仓改动即时生效, 别退回非 editable,
  venv 旧版静默坑已踩过)。改 imgbot 接口后同步其《多点找色Pt规范.md》类契约文档。

## 命名纪律

自研注入插件叫**潜影**; "大漠"仅指反编译参考的原版商业插件。
