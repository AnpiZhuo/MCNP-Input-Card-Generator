"""PTRAC 粒子径迹可视化 —— 后端模块。

app/ptrac/ 各 seam（契约 ptrac-visualization.md v2 §2）：
  ptrac_parser   PTRAC ASCII 文件解析（纯 stdlib，L 表驱动能量/粒子类型提取）
  _ptrac_worker   子进程 worker（stdin JSON → stdout JSON，模块顶只 stdlib）
"""
