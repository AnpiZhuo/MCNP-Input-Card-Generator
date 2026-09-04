# inputcard-mcp — MCNP 输入卡的 AI 读写接入

`inputcard-mcp` 是一个 **Model Context Protocol（MCP）服务器**，让支持 MCP 的 AI 助手（Claude Desktop / Claude Code / 其他 agent）能够**直接读取、修改、生成 MCNP 输入卡（`.INP`）**，无需用户手动复制粘贴文件内容。

> **命名说明（不与 MCNP 撞名）**：MCNP® 是 Triad National Security, LLC（Los Alamos National Laboratory 运营方）的注册商标。为**避免与 MCNP 软件及本项目内已有的 `mcnp_bridge.py` / `mcnp_sidecar` / `MCNP输入卡生成器.exe` 混淆、并遵守商标惯例**，本服务的名字特意使用 `inputcard-mcp`，全程**不含 "MCNP" 子串**。它只是"读写 MCNP 输入卡"的第三方工具。

---

## 工作模型：无状态 + 完全本地化（作为程序能力）

- **无状态**：本服务不保存会话。每次调用，AI 携带完整的输入卡文档（`INP` 文本或结构化 `deck JSON`），服务返回处理结果或新文档。任何一次调用完全独立、可并行、可重放。
- **完全本地化（作为程序的内置能力）**：它采用的是 **本地 stdio** 模式，随本程序一起提供，**不是一台需要你常驻的服务器**。AI 客户端在你电脑上**按需拉起**这个进程（`python -m inputcard_mcp`），通过标准输入/输出通信，用完即止。
  - 不对外开放端口、不需要你手动挂服务、空闲时零资源占用。
  - 所有数据（MCNP 卡、解析结果）都在本机处理，**不出网**。
  - 它复用本程序后端已有的 `parse_inp_text()` / `generate_inp_from_deck()` / deck 双向转换，**依赖那个 5001 HTTP 服务吗？不需要**——只复用其背后的逻辑，那个 HTTP 服务不会因 AI 而常驻。

---

## 让 AI 知道有这个东西：两种方式

### 方式一（推荐）：MCP 自动发现 —— 注册一次，AI 永不再问

MCP 的机制就是让 AI **自动枚举工具**（`tools/list`）。用户只需把本服务**注册**到 AI 客户端，之后 AI 会自己看到 `inputcard-mcp` 能干什么，**不需要你反复告诉它**。

**Claude Desktop（`claude_desktop_config.json`）**

```json
{
  "mcpServers": {
    "inputcard-mcp": {
      "command": "python",
      "args": ["-m", "inputcard_mcp"],
      "env": { "PYTHONPATH": "<本项目根目录>" }
    }
  }
}
```

**Claude Code / 通用 `mcp.json`**

```json
{
  "mcpServers": {
    "inputcard-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "inputcard_mcp"],
      "env": { "PYTHONPATH": "<本项目根目录>" }
    }
  }
}
```

注册完成后，AI 客户端会自动拿到工具清单与描述；你在对话里正常描述需求即可。

### 方式二（兜底）：入口提示语 —— 每次会话粘贴一句

若你的 AI 客户端**不支持 MCP 自动发现**，或你希望在第一句就声明可用能力，复制项目根 **`AI接入.md`** 中的提示语（含简单版 / System Prompt 版）到对话中即可。

> 提示词不是必须的：方式一（注册）之后，AI 自己知道何时调用；提示词主要是**首次引导**或**限速用途**。

---

## 启动

inputcard-mcp 作为程序能力随程序分发，**通过 MCP over HTTP（本机环回 8100）**供外部 agent 连接，不再用 stdio。

**运行**：主程序启动时会自动拉起 `--mcp-http`；也可手动
```bash
<部署目录>\python.exe --mcp-http          # 打包版（自动探测 8100）
python -m inputcard_mcp                     # 源码开发版（默认 8100，可用 --port=<n>）
```

**连接（agent 的 MCP 配置）**：
```json
{ "mcpServers": { "inputcard-mcp": { "type": "http", "url": "http://127.0.0.1:8100/mcp" } } }
```

> ⚠️ 客户端/测试注意事项（stderr）：服务端默认把日志降到 WARNING（不刷 stderr），不易触发管道缓冲；但 MCP 传输靠 stdout 走协议，stderr 是独立通道，仍建议客户端/测试同时消费 stdout+stderr，尤其用 `INPUTCARD_MCP_LOG=DEBUG` 排查时。

---

## 工具集（已实现，共 6 个，默认操作「程序当前工作区」）

外部 agent 连接后自动发现工具。`read_document` / `list_section` / `patch_section` **不传 `inp` 即读/改「程序当前工作区」**（所有标签页，程序界面随之变化）；传 `inp` 则按该文档无状态处理。

> **设计原则（深模块）**：接口刻意保持**小而深**——用 `list_section` / `patch_section` 让 AI 针**语义段**读写，覆盖全部 INP 段；后端生成器已支持全部段，因此**一个** `patch_section` 就能整体改写任意一段，并同步写回程序工作区。

### 文档级
| 工具 | 作用 | 输入 | 返回 |
|------|------|------|------|
| `read_document` | INP → **按语义段的**结构（`{ sections, warnings }`） | `inp` | `{ sections, warnings }` |
| `generate_document` | 从 `sections` 生成 INP 文本（与 read_document 输出同构） | `sections` | `str` |
| `validate_document` | 语法 + 解析警告校验 | `inp` | `{ ok, errors, warnings }` |
| `list_section` | 读取**一个语义段**（与 read_document 的 `sections[section]` 同构） | `inp, section` | `dict`（该段） |
| `patch_section` | **整体替换一个语义段**并返回新 INP（全量覆盖） | `inp, section, data` | `str`（新 INP） |

### 几何（便捷）
| 工具 | 作用 | 关键输入 | 返回 |
|------|------|---------|------|
| `add_shape` | 追加规则几何体（rcc/rpp/sph/hex/tet） | `inp, shape, params` | `{ inp, surface_added, cells_added, cell_numbers }` |

`add_shape` 的各 `shape` 参数：
- `rcc`：`{cx,cy,cz,hx,hy,hz,radius,rings,segments}`
- `sph`：`{x,y,z,radius,shells}`
- `hex`：`{cx,cy,cz,hx,hy,hz,radius,rings,segments}`（RHP 六棱柱）
- `rpp`：`{cx,cy,cz,L,W,H,nx,ny,nz}`（轴对齐六面体）
- `tet`：`{p1,p2,p3,p4}`（4 顶点，程序算 4 面）

### 覆盖范围
- **可写（8 个语义段）**：`basic / surfaces / tr_cards / cells / materials / sources / tally / advanced`（`advanced` 对应后端 `adv`，含源模式 SDEF/KCODE/SSW/SSR、phys、other_cards）。栅元/材料等所有细粒度修改都通过 `read_section`→改→`patch_section` 完成，无需单独的 list_cells/update_cell/set_material 等工具。
- **不可写（纯前端 UI 中间态）**：`textMode` / `sourceTemplate` 编号 / `grids` / `rawOverrides`——不属 INP 内容，`patch_section` 会拒绝。

### ⚠️ 边界：text mode / raw override（不建模，会结构化重写）
`rawOverrides` 是 GUI 把某段切到**文本模式**时手打的原始卡文本，它是 `generate_inp_from_deck(deck, raw_overrides)` 的**第二个参数**（非 deck 字段，`models.DeckData` 无此字段）。
- `read_document`/`list_section`/`patch_section`/`generate_document` 这条 MCP 管线走**结构化路径**，**不接触 raw overrides**：`read_document` 的 `sections` 不含它，改写后生成也用结构化重新生成该段。
- 因此**文本模式段在 MCP 里会被结构化重写**（解析成结构化字段→可改→再生成），**不会保留你手写的 raw 原文/格式**。若某段必须保持 raw 文本原样，请改其它段时不触碰它（MCP 会整体用结构化重生成）。

详析见 [`docs/inputcard-mcp-全量覆盖.md`](inputcard-mcp-全量覆盖.md)。

---

## 与现有后端的关系

`inputcard-mcp` 是**薄包装层**，直接复用本项目的后端能力：

- `parse_inp_text()`（INP → 结构化 deck）
- `generate_inp_from_deck()` / `deck_from_json` / `deck_to_frontend_dict`（deck ⇄ INP 双向转换）
- 几何/语法校验逻辑（`validate_inp_text`）

> `add_shape` 的栅元/曲面生成在本服务内实现（公式等价于前端"快捷建栅元"），编号从当前文档顺延，材料默认真空。它不重复实现 INP 解析与生成，只把这些已有能力以 MCP 工具的形式暴露给 AI。

---

## 独立模块说明

实现位于 `inputcard_mcp/` 包（源码开发：`python -m inputcard_mcp`；打包版随 sidecar 打进 `_internal`，用 `<部署目录>\python.exe --mcp-server`）。依赖见 `inputcard_mcp/requirements.txt`（`mcp>=1,<2`）。

- 对 5001 的 `api_server` HTTP 服务零改动、零依赖——只借用其 `deck_from_json` / `deck_to_frontend_dict`（已添加公开别名）。
- 打包：`gui/mcnp_sidecar.spec` 已将 `inputcard_mcp` 与 `mcp` 打进 sidecar（`gui/backend/mcnp_bridge.py` 新增 `--mcp-server` 分派）。主程序 api_server 路径不触碰 `mcp`，故不影响 5001 后端；仅在使用 AI 接入时才需要该依赖。
