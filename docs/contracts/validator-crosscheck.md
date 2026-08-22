# 校验规则交叉核对：OWEN rules.ts ↔ 项目 validator

> 日期：2026-08-22 | 依据：OWEN `src/language/rules.ts` `validateMCNP`（MIT）↔
> 项目 `app/generator/validator.py` `validate_all`。目标：确认 MCNP 语法级规则
> 覆盖差集，把「适用于本项目表单模型」的规则补进 validator；LSP/编辑器专属
> 规则只做映射不移植（权威源仍是 C810）。

## 规则映射

| OWEN 规则（code） | 内容 | 项目覆盖 | 处置 |
| :-- | :-- | :-- | :-- |
| `mcnp.short-continuation` | 材料续行必须列 1-5 空白（缩进 ≥6） | 解析器 `normalize_lines` 处理续行；表单模型无续行概念 | 仅映射；文本模式若需可后续加行级检查 |
| `mcnp.zaid` | ZAID 必须 `ZZZAAA.NNx`（x=Table B.1 库字母） | 原仅查非空 + xsdir 存在性 | **已补**：`_ZAID_RE` 格式检查（2026-08-22） |
| `mcnp.macrobody` | CYL 非关键字 → 用 RCC；宏体参数个数 | 表单建曲面已按类型限定参数，天然覆盖 | 仅映射 |
| `mcnp.density-sign` | 密度符号约定（负=质量，正=原子）提示 | UI 占位符/说明已写 | 仅映射（information 级） |
| `mcnp.cell-imp` | 栅元缺 imp 且无 IMP/WWN 数据卡 → 警告 | **生成器 IMP 归一化天然覆盖**（V1.7.2.2：缺省补 imp=1） | 已覆盖（生成器层） |
| `mcnp.material-sign` | 材料份额正负号混用（原子/质量混合） | 未覆盖 | **已补**：份额符号一致性检查（2026-08-22） |
| `mcnp.mt-missing-material` | mtN 引用未定义材料 | 表单中 mt_card 挂在 MaterialData 上，天然绑定 | 已覆盖（模型结构） |
| `mcnp.sab-no-target` | S(α,β) 表目标核素不在材料中 → 表被忽略 | 未覆盖 | **已补**：`_check_sab_target`（2026-08-22，氢/碳/铍/氧/硼/锆/铝/铁/铀） |
| `mcnp.line-length` | 卡行超过 80/128 列 → 截断警告 | 表单生成行不超长；导入文本模式未检 | 仅映射；文本模式后续可加 |

## 已新增的实现（`app/generator/validator.py`）

1. `_ZAID_RE` + 格式检查：`\d{4,6}(\.\d{2,}[a-zA-Z])?`（裸 ZZZAAA 或 ZZZAAA.NNx）。
2. 份额符号一致性：同一材料内正负号混用报错（正=原子份额，负=质量份额）。
3. `_check_sab_target(mat)`：mt_card 表前缀（lwtr/hwtr/benz/poly/zrh/grph/be/beo/o/b/b4c/zr/al/fe/u）→
   要求材料含对应 Z 核素，缺失报错。

测试：`tests/unit/test_validator_rules.py`（7 用例）。

## 未移植（原因）

- 续行缩进 / 行长度：项目是表单生成 + 结构化模型，天然不产生此类问题；文本模式
  往返路径若有需要再补行级检查。
- 宏体参数个数 / 密度符号提示：表单 UI 已按曲面类型限定输入。

## 纪律

- 权威源仍是 `D:\MCNP\MCNP6\C810.pdf`；OWEN 规则仅作交叉核对清单。
- 新增校验必须「错误信息含材料号/行号上下文」并可单测（纯逻辑，无 FreeCAD/vtk）。
