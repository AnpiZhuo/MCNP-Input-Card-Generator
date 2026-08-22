# OWEN 预置 MCNP 卡（测试夹具）

来源：`D:\MCNP\owen-1.4.1\prebuilt-models\*_mcnp.i`（OWEN 仓库，MIT License，
Copyright 2026 BelvoirDynamics；BEAVRS 数据源自 MIT BEAVRS Rev 2.0.2 公开规范）。

文件头自带声明：**community example deck，未做基准验证**——仅作解析器/生成器的
测试夹具，不得当作物理验证数据。

- `pincell_mcnp.i`：单棒栅元（燃料/气隙/包壳/慢化剂 4 材料，5 栅元，266 曲面）。
- `assembly_17x17_mcnp.i`：17×17 PWR 组件（264 燃料棒 + 24 导向管 + 1 仪表管，
  `lat=1`/`fill=` 格阵语法，15 栅元，275 曲面，5 材料）。
- `beavrs_fullcore_mcnp.i`：BEAVRS 全堆芯（193 组件，universe/lattice 展开，
  331 栅元，2101 曲面，13 材料）。

解析基线见 `tests/parser/test_owen_deck_fixtures.py`。
