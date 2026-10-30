# -*- coding: utf-8 -*-
"""多开入口: ttkbootstrap 中控台(热键收编/表格启停/日志面板/双 Tab 设置)。

用法: uv run console.py
"""
import business
from bot.console_ui import Console

if __name__ == "__main__":
    Console(business).run()
