"""网格计数（FMESH/TMESH）3D 体积可视化 —— 后端模块。

app/meshtal/ 各 seam（契约 meshtal-visualization.md §4）：
  meshtal_parser     MESHTAL 文件解析（pymcnp 优先 + 轻量兜底）
  volume_builder     box-average 降采样 + 归一化 + uint8 标量帧
  colormap           天气图色阶 LUT（python/TS 双端 golden）
  downsample_plan    降采样/分辨率决策（预算、弹窗素材）
  deck_match         deck↔meshtal 匹配检测（AABB/overlap/offset）
  meshtal_cache      path+mtime 指纹 pickle 缓存
  _meshtal_worker    子进程 worker（stdin JSON → stdout JSON，模块顶只 stdlib）
  fmesh_parser       FMESH/TMESH 卡体 ↔ FmeshDefinition
"""
