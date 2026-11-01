# imgbot-template · Agent 须知

图色脚本项目模板(imgbot 门面之上的脚手架)。拷贝本目录改名即新项目,
开发者只写 `task.py`(业务逻辑)+ `business.py`(业务配置),详见 README。

## 开发手册文档(必守)

- 位置: `docs/icefrag开发手册.{md,html,chm}`(md 给 AI/骨架 README, CHM 给人);
  生成器 `scripts/build_docs.py` —— 命令表从 `icefrag/dsl.py` 的
  `inspect.signature` 实时内省, 配置表从 `ScaffoldConfig` 内省, 与代码不漂移;
  散文章节/示例手排在生成器里。旧 `DSL语法清单`/`脚手架使用手册` 已被其取代。
- **规则: 任何 `icefrag/dsl.py` 变更(增删命令/改签名/改默认值/docstring)或
  `ScaffoldConfig` 字段增删, 必须重跑 `uv run scripts/build_docs.py` 并把
  产物一起提交**, 否则手册与命令表漂移。CHM 编译依赖便携 hhc
  (`D:/tools/hhw/hhc.exe`, 不存在时留工程手动编, md/html 仍有效)。

## 回归测试范围(必守)

- **规则: 验证本次改动只跑受影响的用例, 不必全量跑**。先判断改动波及哪些
  模块/动词, 再按名筛选; `test/test_dsl_game.py` 模块头有"用例→动词"映射表。
  全量回归只在发版或大范围重构前跑。

## DSL 回归测试(必守)

- **规则: `icefrag/dsl.py` 或 imgbot 键鼠/图色接口(Ops/DmSoft/键鼠类)任何变更,
  必须跑绿受影响的用例**(按上节"回归测试范围"挑名筛选, 不必全量):
  E2E 走 `uv run test/test_dsl_game.py <名...>`(纯 Win32 靶
  `test/dummy_game.py`, gdi+windows 全后台通道),
  组织层走 `uv run test/test_dsl_mouse.py`(离线: 路由/抖动/停顿/key 序, 秒级)。
  用例→动词映射表在 `test/test_dsl_game.py` 模块头; 改靶子布局须两边同步。

## 两仓关系

- `icefrag/` 框架包属本仓; 图色/键鼠底层来自 imgbot 库(`D:\script-workspace\imgbot`,
  pyproject path 引用且 **editable** —— 源仓改动即时生效, 别退回非 editable,
  venv 旧版静默坑已踩过)。改 imgbot 接口后同步其《多点找色Pt规范.md》类契约文档。

## 命名纪律

自研注入插件叫**潜影**; "大漠"仅指反编译参考的原版商业插件。
