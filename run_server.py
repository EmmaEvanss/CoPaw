# -*- coding: utf-8 -*-
"""FastAPI 服务启动入口."""
import os
import sys

# 添加 src 目录到 PYTHONPATH（必须在 import 之前）
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# 设置环境变量，确保 uvicorn 子进程也能找到模块
os.environ["PYTHONPATH"] = src_path

# 先安装包（如果未安装）
try:
    import swe
except ImportError:
    print("正在安装项目依赖...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"])
    print("依赖安装完成")

# 直接导入 app 对象
from swe.app._app import app

import uvicorn

if __name__ == "__main__":
    # 直接传入 app 对象，而不是字符串路径
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8088,
        log_level="info",
    )