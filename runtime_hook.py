"""PyInstaller runtime hook: 优先从 EXE 同级目录加载 app/ 模块，实现热更新。"""
import sys
import os

# 获取 EXE 所在目录（对打包后的程序就是 exe 所在路径）
exe_dir = os.path.dirname(sys.executable)
app_path = os.path.join(exe_dir, 'app')

if os.path.isdir(app_path):
    # 插到 sys.path 最前面，优先级高于 _internal 中的打包模块
    sys.path.insert(0, exe_dir)
