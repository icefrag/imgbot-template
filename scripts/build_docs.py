# -*- coding: utf-8 -*-
"""DSL 语法清单生成器: icefrag/dsl.py 内省 → 三产物(给 task.py 写逻辑的开发者)。

- docs/DSL语法清单.md     给 AI 看(全部命令: 签名+说明+示例)
- docs/DSL语法清单.html   单文件版(浏览器直接开)
- docs/DSL语法清单.chm    编译版(便携 hhc 在 D:/tools/hhw, 同 imgbot 接口文档链)

参数表权威 = inspect.signature 实时内省(必传/默认值与代码不漂移);
说明取 docstring, 示例手排 EXAMPLES。

用法: uv run scripts/build_docs.py
变更 icefrag/dsl.py 后必须重跑本脚本(AGENTS.md 规则)。
"""
from __future__ import annotations

import inspect
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from icefrag import dsl  # noqa: E402

DOCS = ROOT / "docs"
TITLE = "icefrag DSL 语法清单"

# 分类页序(手排; 命令名必须与 dsl.__all__ 一致, 漏了脚本会报)
GROUPS = [
    ("键鼠", ["click", "dblclick", "drag", "move", "key", "sleep"]),
    ("消息", ["log", "shot", "stopped"]),
    ("找点(单帧)", ["find_color", "find_all", "find_multi_color", "exists"]),
    ("复合动作", ["find_tap", "tap_until_gone"]),
    ("等待(超时返 None/False)", ["wait_pic", "wait_pic_any", "wait_pic_gone",
                                "wait_color", "wait_color_gone", "wait_text"]),
    ("识字 / 找字(OCR)", ["ocr", "ocr_numbers", "find_str"]),
    ("导航(需 task.py 声明表)", ["go", "at"]),
    ("看门狗", ["progress"]),
]

EXAMPLES = {
    "click": 'click(231, 347)                       # 拟人点击(轨迹+停顿+抖动), 默认见 scaffold.toml\nclick(231, 347, human=False)            # 瞬移急点(速度优先)\nclick(231, 347, jitter=0, settle=200)  # 精确落点, 到位停 200ms',
    "dblclick": 'dblclick(400, 300)',
    "drag": 'drag(450, 550, 450, 150)               # 列表上滑(按住拖)\ndrag(100, 300, 500, 300, ms=500)       # 横拖, 500ms',
    "move": 'move(400, 300)                         # 悬停不点',
    "key": 'key("ctrl+s")\nkey("enter")',
    "sleep": 'sleep(500)                            # 半秒, F9 按下立刻醒',
    "log": 'log(f"击杀 ×{kills}", "info")           # level: info|warn|error',
    "shot": 'shot("boss出现")                       # 留痕到 logs/shots',
    "stopped": 'while not stopped():               # F9 叫停了吗(挂机循环退出条件)\n    打怪一轮()',
    "find_color": 'hit = find_color("CC3333", tol=40, region=(0, 0, 900, 570))\nif hit: click(*hit[0])',
    "find_all": 'for x, y in find_all("小地图图标.png"): click(x, y)',
    "find_multi_color": 'from icefrag.dsl import Pt\nMON = [Pt(0, 0, (51, 51, 204), 40), Pt(8, 0, (51, 51, 204), 40)]\nhit = find_multi_color((0, 0, 900, 640), MON)   # (x, y) | None',
    "exists": 'if exists("金币满.png"): key("b")',
    "find_tap": 'find_tap("领取按钮.png")                        # 单帧试\nfind_tap("每日签到.png", timeout=5000)              # 等最多 5 秒',
    "tap_until_gone": 'n = tap_until_gone("确定按钮.png")       # 返回点击次数',
    "wait_pic": 'hit = wait_pic("结算面板.png", timeout=8000)   # (x, y, 分) | None',
    "wait_pic_any": 'hit = wait_pic_any(["升级.png", "断线.png"])  # (名, x, y, 分) | None',
    "wait_pic_gone": 'while not wait_pic_gone("加载中.png", timeout=15000): pass',
    "wait_color": 'hit = wait_color("FFD700")                    # 金币转圈 (x,y)|None',
    "wait_color_gone": 'ok = wait_color_gone("CC3333-282828", timeout=10000)  # 等怪死',
    "wait_text": 'hit = wait_text("挑战成功")                    # OCR 等文字 (x,y,相似度)|None',
    "ocr": 'task = ocr(region=(10, 30, 400, 60))          # 识全文: "每日签到 副本"\nif "签到" in task: ...          # 任务名判断',
    "ocr_numbers": 'nums = ocr_numbers(region=(50, 580, 200, 610))\nlv = nums[0] if nums else 0          # 等级\n# 坐标场景: x, y = ocr_numbers(POS_RECT)[:2]',
    "find_str": 'hit = find_str("每日签到")                     # 找字位置 (x, y) | None\nif hit: click(*hit)                  # 找到就能点\n# 短词(2字)不稳: 缩 region + min_ratio=0.5',
    "go": 'if not go("dungeon"): return        # 图带路(声明 NAV_SCREENS/NAV_EDGES)\n# 迷路自愈; LostError=需重登(配 on_fuse)',
    "at": 'if at("city"): ...                  # 便宜的单帧"我在不在这屏"',
    "progress": 'while not ctx.stop.is_set():\n    progress("等刷新")          # 长轮询手动打点, 防看门狗误杀\n    sleep(2000)',
}

RULES = """<h2>四条铁律</h2>
<ol>
<li><b>凡时间皆毫秒</b> — sleep(500)=半秒, timeout=10000=10 秒(各等待命令默认)。</li>
<li><b>找不到/超时返回 None 或 False, 不抛异常</b> — "没找到"是挂机常态;
    真故障(窗口没了)由框架绑定层兜底自动重开/熔断。</li>
<li><b>F9 停止贯穿一切</b> — sleep 与所有 wait 命令按下即醒即退。</li>
<li><b>ctx 是逃生舱</b> — 冷门动作(wait_until/retry/swipe_find/read_number/
    probe/check_points...)与窗口管理走 ctx.ops / ctx.dm / ctx.device。</li>
</ol>"""

SKELETON = """<h2>task.py 骨架</h2>
<pre>from icefrag.dsl import *          # 唯一的前缀

def main_task(ctx):            # 总入口, 抛异常=本轮失败(框架自动重开)
    while not ctx.stop.is_set():
        hit = find_color("CC3333", tol=40)
        if not hit:
            sleep(1500)
            continue
        click(*hit[0])
        if wait_color_gone("CC3333-282828", timeout=10000):
            log("击杀")</pre>
<p>完整示范: test/auto_farm/task.py(多点找色版自动打怪)。</p>"""


def _sig(name: str) -> str:
    fn = getattr(dsl, name)
    sig = inspect.signature(fn)
    parts = []
    for p in sig.parameters.values():
        d = "" if p.default is inspect.Parameter.empty else f"={p.default!r}"
        parts.append(f"{p.name}{d}")
    return f"{name}({', '.join(parts)})"


def _brief(name: str) -> str:
    doc = (getattr(dsl, name).__doc__ or "").strip()
    return doc.split("\n")[0]


def _doc_extra(name: str) -> str:
    doc = (getattr(dsl, name).__doc__ or "").strip().split("\n")
    return "<br>".join(l.strip() for l in doc[1:] if l.strip())


def _head(title: str) -> str:
    return ("<html><head><meta charset='utf-8'><style>"
            "body{font-family:'Microsoft YaHei';margin:24px;line-height:1.6}"
            "pre{background:#1b1f24;color:#d0d0d0;padding:10px;border-radius:6px;"
            "overflow-x:auto}h2{border-bottom:2px solid #4a7;padding-bottom:4px}"
            "table{border-collapse:collapse}td,th{border:1px solid #ccc;"
            "padding:4px 10px;font-size:14px}</style></head><body>")


def page_html(name: str) -> str:
    ex = EXAMPLES.get(name, "")
    return "\n".join([
        _head(name), f"<h1><code>{name}</code></h1>",
        f"<p>{_brief(name)}</p>",
        "<h2>原型</h2>", f"<pre>{_sig(name)}</pre>",
        f"{_doc_extra(name)}" if _doc_extra(name) else "",
        "<h2>示例</h2>", f"<pre>{ex}</pre>" if ex else "<p>—</p>",
        "</body></html>",
    ])


def build():
    chm_dir = DOCS / "chm"
    if chm_dir.exists():
        shutil.rmtree(chm_dir)
    chm_dir.mkdir(parents=True)

    listed = [n for _, names in GROUPS for n in names]
    missing = set(dsl.__all__) - set(listed) - {"Pt"}   # Pt=类型 re-export
    if missing:
        sys.exit(f"GROUPS 漏了命令: {missing}")

    # -- md(AI 权威版) --
    md = [f"# {TITLE}", "",
          "> 参数表由 `scripts/build_docs.py` 从 icefrag/dsl.py 签名内省生成,",
          "> 改 dsl 后重跑脚本(AGENTS.md 规则)。铁律: 凡时间皆毫秒 / 超时返",
          "> None 不抛 / F9 贯穿 / ctx.dm·ctx.ops·ctx.device 是逃生舱。", ""]
    ids = {}
    for ci, (cat, names) in enumerate(GROUPS):
        md += [f"## {cat}", "", "| 命令 | 原型 | 说明 |", "|---|---|---|"]
        for ii, n in enumerate(names):
            ids[n] = f"c{ci}/p{ci}-{ii}"
            md.append(f"| **{n}** | `{_sig(n)}` | {_brief(n)} |")
        md.append("")
    md += ["## 示例速查", ""]
    for _, names in GROUPS:
        for n in names:
            if n in EXAMPLES:
                md += [f"**{n}**", "```python", EXAMPLES[n], "```", ""]
    (DOCS / "DSL语法清单.md").write_text("\n".join(md), encoding="utf-8")

    # -- chm 工程页(五段式) --
    for ci, (cat, names) in enumerate(GROUPS):
        (chm_dir / f"c{ci}").mkdir(exist_ok=True)
        for n in names:
            (chm_dir / f"{ids[n]}.html").write_text(page_html(n), encoding="utf-8")
    (chm_dir / "index.html").write_text("\n".join([
        _head(TITLE), f"<h1>{TITLE}</h1>",
        "<p>task.py 顶部 <code>from icefrag.dsl import *</code> 后的顶层命令速查。</p>",
        RULES, SKELETON,
        "<h2>命令目录</h2>"] + [
        f"<p><b>{cat}</b>: " + " ".join(
            f"<a href='{ids[n]}.html'>{n}</a>" for n in names) + "</p>"
        for cat, names in GROUPS] + ["</body></html>"]), encoding="utf-8")

    # -- hhc(GBK; OBJECT 单 '>' 收尾, ASCII 内部路径——hhc 是 ANSI 程序) --
    Q = '"'
    PARAM = "<param name={q}{k}{q} value={q}{v}{q}>"
    entries = []
    for ci, (cat, names) in enumerate(GROUPS):
        kids = "".join(
            "\t\t<LI> <OBJECT type=\"text/sitemap\">\n\t\t"
            + PARAM.format(q=Q, k="Name", v=n) + "\n\t\t"
            + PARAM.format(q=Q, k="Local", v=ids[n] + ".html") + "\n\t\t</OBJECT>\n"
            for n in names)
        entries.append(
            "\t<LI> <OBJECT type=\"text/sitemap\">\n\t\t"
            + PARAM.format(q=Q, k="Name", v=cat) + "\n\t</OBJECT>\n"
            + "\t<UL>\n" + kids + "\t</UL>\n")
    (chm_dir / "dsl.hhc").write_text(
        '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN">\n<HTML><HEAD></HEAD>'
        '<BODY>\n<UL>\n' + "".join(entries) + "</UL>\n</BODY></HTML>\n",
        encoding="gbk")
    # [WINDOWS] 字段序错一格=面板不创建(imgbot 同款实测坑)
    (chm_dir / "dsl.hhp").write_text(
        "[OPTIONS]\nCompatibility=1.1 or later\nCompiled file=dsl_doc.chm\n"
        "Contents file=dsl.hhc\nDefault topic=index.html\nDefault Window=main\n"
        "Language=0x804\nTitle=DSL syntax\n\n"
        "[WINDOWS]\n"
        'main="DSL syntax","dsl.hhc",,"index.html",,,,,,0x20,200,0x1006,'
        "[50,30,1000,760],0,0,1,0,0,0,0\n"
        "\n[FILES]\nindex.html\n", encoding="ascii")

    # -- 编译(便携 hhc; 无则留工程手动编) --
    hhc = Path("D:/tools/hhw/hhc.exe")
    if hhc.exists():
        subprocess.run([str(hhc), "dsl.hhp"], cwd=chm_dir, capture_output=True)
        out = chm_dir / "dsl_doc.chm"
        if out.exists():
            shutil.move(str(out), DOCS / "DSL语法清单.chm")
            print("  chm :", DOCS / "DSL语法清单.chm")
        else:
            print("  chm 编译失败(hhc 返回非零), 工程保留在 docs/chm")

    # -- 单文件 html --
    single = [_head(TITLE), f"<h1>{TITLE}</h1>", RULES, SKELETON]
    for cat, names in GROUPS:
        single.append(f"<h2>{cat}</h2>")
        single.append("<table><tr><th>命令</th><th>原型</th><th>说明</th></tr>")
        for n in names:
            single.append(f"<tr><td><code>{n}</code></td><td><code>{_sig(n)}"
                          f"</code></td><td>{_brief(n)}</td></tr>")
        single.append("</table>")
    single.append("</body></html>")
    (DOCS / "DSL语法清单.html").write_text("\n".join(single), encoding="utf-8")

    print("生成完毕:")
    print("  md  :", DOCS / "DSL语法清单.md")
    print("  html:", DOCS / "DSL语法清单.html")


if __name__ == "__main__":
    build()
