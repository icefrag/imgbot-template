# -*- coding: utf-8 -*-
"""日志区 IDEA 式跟随回归(console_ui 2026-11-15 需求): ①贴底插入仍跟随
②离底插入不拽走+「↓最新」浮钮浮出 ③滚回底部/点按钮=恢复跟随+浮钮自藏
④2000 行裁剪: 贴底照旧拉底, 离底锚点补偿不顶跑视线。

不拉整个中控台(要真 Fleet/热键/配置), 子类跳过 ConsoleUI.__init__ 只借
真方法驱动真 widget。跑法: uv run test/test_log_follow.py
"""
import tkinter as tk

import ttkbootstrap as ttk

from icefrag.console_ui import Console as ConsoleUI


class _Harness(ConsoleUI):
    """真方法 + 真 widget, 砍掉重型 __init__。"""
    def __init__(self):
        self.root = tk.Tk()                    # 只当容器, withdraw 不闪窗
        self.root.withdraw()
        self.logbox = tk.Text(self.root, wrap="none")
        self.logbox.pack()
        self._log_sb = ttk.Scrollbar(self.root, command=self.logbox.yview)
        self._log_tail_btn = ttk.Button(self.logbox, text="↓ 最新")
        self.logbox.config(yscrollcommand=self._on_log_yscroll)
        # 撑出固定行高视口, 保证 100 行远超一屏(yview 分数才有意义)
        self.logbox.config(font=("Consolas", 9), width=40, height=10)


def _fill(lb, n, base=0):
    lb.config(state="normal")
    lb.insert("end", "".join(f"line{base + i}\n" for i in range(n)))
    lb.config(state="disabled")


def _pump_insert(ui, line="newline"):
    """复刻 _pump_log 的插入语义: 贴底才 see(end)。"""
    at_tail = ui._log_at_tail()
    lb = ui.logbox
    lb.config(state="normal")
    lb.insert("end", f"{line}\n")
    if at_tail:
        lb.yview_moveto(1.0)
    lb.config(state="disabled")


def main():
    ui = _Harness()
    lb, root, btn = ui.logbox, ui.root, ui._log_tail_btn
    upd = lambda: root.update_idletasks()

    # ① 贴底跟随: 追加后仍在底
    _fill(lb, 100)
    lb.yview_moveto(1.0); upd()
    assert ui._log_at_tail(), "满屏内容 see(end) 后应贴底"
    for _ in range(20):
        _pump_insert(ui)
    upd()
    assert ui._log_at_tail(), "贴底追加应保持跟随"

    # ② 离底冻结: 视线钉住 + 浮钮浮出
    lb.yview_moveto(0.0); upd()
    assert not ui._log_at_tail(), "滚到顶应离底"
    assert btn.place_info() != {}, "离底应浮出「↓最新」"
    before = lb.index("@0,0")
    for _ in range(20):
        _pump_insert(ui)
    upd()
    assert lb.index("@0,0") == before, "离底时插入不得拽走视线"
    assert btn.place_info() != {}, "离底期间浮钮保持可见"

    # ③ 回底自藏: 滚回底部=恢复跟随+浮钮消失(_log_jump_tail 同路径)
    lb.yview_moveto(1.0); upd()
    assert ui._log_at_tail()
    assert btn.place_info() == {}, "贴底后浮钮应自藏"
    ui._log_jump_tail(); upd()
    assert btn.place_info() == {}, "点「↓最新」跳底后浮钮自藏"

    # ④a 离底裁剪补偿: 2100 行裁掉头 100, 眼睛盯的行原地不动
    _fill(lb, 2000, base=100)                 # 追加到 2120 行, 仍贴底
    lb.yview_moveto(1.0); upd()
    _fill(lb, 80, base=2100)                  # 2200 行, 触发裁剪
    lb.yview_moveto(0.5); upd()
    assert not ui._log_at_tail()
    # index("end-1c") 比实体行数多 1(尾换行空行), 与 _log_trim 同一量具
    n_pre = int(lb.index("end-1c").split(".")[0])
    pre_line = int(lb.index("@0,0").split(".")[0])
    pre_text = lb.get(f"{pre_line}.0", f"{pre_line}.0 lineend")
    ui._log_trim()
    upd()
    post_line = int(lb.index("@0,0").split(".")[0])
    post_text = lb.get(f"{post_line}.0", f"{post_line}.0 lineend")
    total = int(lb.index("end-1c").split(".")[0])
    cut = n_pre - 2001                        # delete("1.0", f"{n-2000}.0") 实删行数
    assert total == 2001, f"裁剪后应恰 2000 实体行(量具 2001), 实际 {total}"
    assert post_text == pre_text, f"裁剪不得顶跑视线: {pre_text!r} → {post_text!r}"
    assert post_line == pre_line - cut, f"行号应随裁剪平移 {cut}: {pre_line} → {post_line}"

    # ④b 贴底裁剪照旧拉底(灌日志走泵径: 每条先判贴底, 跟随不丢)
    lb.yview_moveto(1.0); upd()
    for i in range(50):                       # 2050 行, 贴底态触发裁剪
        _pump_insert(ui, line=f"tailfill{i}")
    ui._log_trim()
    upd()
    assert ui._log_at_tail(), "贴底裁剪后应仍在底"
    root.destroy()
    print("test_log_follow ok")


if __name__ == "__main__":
    main()
