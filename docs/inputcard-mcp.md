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

若你的 AI 客户端**不支持 MCP 自动发现**，或你希望在第一句就声明可用能力，复制项目根 **`AI接入提示词.md`** 中的提示语（含简单版 / System Prompt 版）到对话中即可。

> 提示词不是必须的：方式一（注册）之后，AI 自己知道何时调用；提示词主要是**首次引导**或**限速用途**。

---

## 启动

inputcard-mcp 作为程序能力随程序分发，有两种运行方式：

**① 打包版（随程序 sidecar，推荐）**
```bash
# 已有部署目录里的 sidecar；AI 客户端把它当作 stdio MCP server 拉起
<部署目录>\python.exe --mcp-server
```

**② 源码开发**
```bash
pip install -r inputcard_mcp/requirements.txt
python -m inputcard_mcp
```

> 打包版无需另外装依赖（`inputcard_mcp` + `mcp` 已随 sidecar 打进 `_internal`）。用户通常在 AI 客户端配置里**一次性注册**下面任一服务，之后无需手动启动。

**打包版配置**
```json
{
  "mcpServers": {
    "inputcard-mcp": {
      "command": "<部署目录>\\python.exe",
      "args": ["--mcp-server"]
    }
  }
}
```

**源码开发版配置**
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

---

## 工具集（已实现）

无状态：每个修改型工具都「收当前 `INP` 文本 → 返回新 `INP`」。

> `list_section` / `patch_section` 提供**按语义段的全量覆盖**：后端生成器已支持全部 INP 数据段，
> 因此用**一个** `patch_section` 就能整体改写任意一段（basic/surfaces/tr_cards/cells/materials/sources/tally/advanced），
> 而不必为每类设置各写一个工具。可写 = 这些后端语义段；纯前端 UI 中间态（textMode/sourceTemplate/grids/rawOverrides）**不可写**。

### 文档级
| 工具 | 作用 | 输入 | 返回 |
|------|------|------|------|
| `read_document` | INP → 结构化 deck JSON（完整） | `inp` | `{ deck, warnings }` |
| `generate_document` | deck JSON → INP 文本 | `deck` | `str` |
| `validate_document` | 语法 + 解析警告校验 | `inp` | `{ ok, errors, warnings }` |
| `list_section` | 读取**一个语义段**的结构化值（snake_case，可改后回传 patch_section） | `inp, section` | `dict`（该段） |
| `patch_section` | **整体替换一个语义段**并返回新 INP（全量覆盖） | `inp, section, data` | `str`（新 INP） |

`section` ∈ `basic / surfaces / tr_cards / cells / materials / sources / tally / advanced`（`advanced` 对应后端 `adv`，含源模式 SDEF/KCODE/SSW/SSR、phys、other_cards）。详析见 [`docs/inputcard-mcp-全量覆盖.md`](inputcard-mcp-全量覆盖.md)。

### 栅元
| 工具 | 作用 | 关键输入 | 返回 |
|------|------|---------|------|
| `list_cells` | 列出栅元摘要 | `inp` | `[{num,mat,density,surface_expr,imp,…}]` |
| `get_cell` | 取单栅元 | `inp, num` | `cell` |
| `update_cell` | 改栅元（材料/密度/表达式/imp/注释…） | `inp, num, patch` | `str`（新 INP） |
| `set_mode` | 设粒子模式 N/P/E | `inp, mode_n/p/e` | `str`（新 INP） |

### 材料
| 工具 | 作用 | 关键输入 | 返回 |
|------|------|---------|------|
| `list_materials` | 列出材料卡 | `inp` | `[{number,comment,rows,…}]` |
| `set_material` | 改材料（注释/化学式/选项/MT 卡） | `inp, number, patch` | `str`（新 INP） |

### 几何（快捷建栅元）
| 工具 | 作用 | 关键输入 | 返回 |
|------|------|---------|------|
| `add_shape` | 追加规则几何体（rcc/rpp/sph/hex/tet） | `inp, shape, params` | `{ inp, surface_added, cells_added, cell_numbers }` |

`add_shape` 的各 `shape` 参数：
- `rcc`：`{cx,cy,cz,hx,hy,hz,radius,rings,segments}`
- `sph`：`{x,y,z,radius,shells}`
- `hex`：`{cx,cy,cz,hx,hy,hz,radius,rings,segments}`（RHP 六棱柱）
- `rpp`：`{cx,cy,cz,L,W,H,nx,ny,nz}`（轴对齐六面体）
- `tet`：`{p1,p2,p3,p4}`（4 顶点，程序算 4 面）

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
