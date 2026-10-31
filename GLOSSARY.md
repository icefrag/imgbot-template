# imgbot-scaffold 术语表

图色脚本脚手架框架仓: 脚本开发者以"薄项目"形态基于它开发,引擎机密与推广物料分层而治。

## Language

### 分层

**脚手架层(scaffold)**:
`bot/` 框架包(worker/中控台/DSL/设置),以源码形态开源分发——它是推广物料,不是机密。
_Avoid_: 模板(指旧拷贝形态)、框架(过泛)

**引擎层(engine)**:
imgbot 库与潜影注入件,以编译 wheel 闭源分发——机密与护城河所在,将来收费在此层上锁。
_Avoid_: 底层库、大漠(仅指反编译参考的原版商业插件)

**薄项目(thin project)**:
脚本开发者的项目形态: 只含入口薄文件、business/task、素材与配置;脚手架与引擎靠依赖声明引入,不含任何框架源码拷贝。
_Avoid_: 拷贝项目、子项目、寄生项目(仅指旧 test/auto_farm 的临时姿势)

### 受众

**脚本开发者**:
写 task.py/business.py 的人,消费薄项目骨架与 wheel,在 Python 环境里开发。
_Avoid_: 用户(过泛,分不清是哪类)

**脚本使用者**:
跑 build_exe 产出的 exe 的人,零 Python 环境,只见绿色包。
_Avoid_: 用户(过泛)

### 通道

**直链(editable link)**:
作者本地的依赖姿势: path + editable 指向源码仓,改完即生效,无版本解析。
_Avoid_: 安装(那是对脚本开发者而言的动作)

**文件分发(file distribution)**:
面向国内脚本开发者的发行方式: 骨架 zip(含当版 wheel)经群文件/网盘交付,全程不依赖 GitHub。
_Avoid_: 发布到 GitHub(那是面向世界的辅通道,不是主通道)

**骨架(skeleton)**:
薄项目的出生模板: 入口四件套 + pyproject(指向 libs/ 内 wheel) + scaffold.toml,随发版打成 zip。
_Avoid_: 脚手架(那是框架本身,别混)
