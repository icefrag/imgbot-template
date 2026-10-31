# -*- coding: utf-8 -*-
"""发布包装(薄): 逻辑在 icefrag/build.py。用法: uv run build_exe.py"""
import sys

from icefrag.build import main

if __name__ == "__main__":
    sys.exit(main())
