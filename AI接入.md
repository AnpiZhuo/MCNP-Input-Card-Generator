# inputcard-mcp — AI 接入（MCP over HTTP）

程序**内置 AI 接入**：启动程序会自动拉起 `--mcp-http`（本机环回 **8100**），外部 agent（claude / codex / dsh 等）用下面的 **URL** 连接，即可**直接读/改程序当前全部标签页**的工作区。数据不出本机（`127.0.0.1` 环回）；程序不做 harness/聊天。

> 命名：服务名 `inputcard-mcp` 刻意避开 "MCNP" 子串（商标 + 区分 `mcnp_bridge`/`mcnp_sidecar`）。

---

## 让 agent 连上（做一次）

程序运行中时，在 agent 的 **MCP 配置**里新增一个服务，填 **URL**：

```
http://127.0.0.1:8100/mcp
```

- **Claude Code / 支持 URL 型 MCP**：在其 mcp 配置加
  ```json
  { "mcpServers": { "inputcard-mcp": { "type": "http", "url": "http://127.0.0.1:8100/mcp" } } }
  ```
- **其它支持 HTTP MCP 的客户端**：在"添加 MCP server"选 **URL / HTTP 型**，粘上面地址。

连接后 agent 自动发现工具：`read_document` / `list_section` / `patch_section` / `add_shape` / `validate_document` / `generate_document`，并**读/改的就是程序当前打开的卡**（AI 改后程序界面跟着变）。

> 前提：主程序在运行（它启动时自动拉起 `--mcp-http`）。若 8100 未就绪，请重启程序或用顶栏「🤖 AI」查看状态。

---

## 给 AI 的提示（可复制；连上后通常不需要）

> 配置好后 AI 已自动发现工具，无需这段提示；仅在不支持自动发现的客户端、或你希望第一句声明能力时使用。

### 简单版（一句话）

```
你可以使用 inputcard-mcp 这个 MCP 服务来读写 MCNP 输入卡：
read_document（读全部标签页 -> sections）、generate_document（sections -> INP）、
list_section / patch_section（按语义段读/写当前工作区）、
add_shape（rcc / rpp / sph / hex / tet）、validate_document。
请帮我处理这份 MCNP 输入卡。
```

### 详细版（System Prompt）

```
# 角色
你是一个 MCNP 输入卡助手，通过 inputcard-mcp 读写、校验、修改程序当前打开的 MCNP 输入文件（.INP）。
你**不手写 MCNP 卡文本**（避免语义错误），而是调用工具读取/修改结构化数据，再生成回 INP。

# 工具（共 6 个）
read_document           读全部标签页 -> { sections, warnings }（8 个语义段 + universe_comments）
generate_document       sections -> INP 文本（与 read_document 输出同构）
validate_document       语法 + 解析警告校验（不含几何重叠）
list_section(section)   读一个语义段（basic/surfaces/tr_cards/cells/materials/sources/tally/advanced）
patch_section(section, data)  整体替换一个语义段 -> 改当前工作区（程序界面随之变化）
add_shape(shape, params) 追加规则几何体（rcc/rpp/sph/hex/tet）

# 工作流
1. read_document 读取当前程序工作区，得到 sections。
2. list_section 看某段，或直接用 sections[section]。
3. 修改：给 sections[section] 改值，或 patch_section(section, data)。
4. validate_document 校验。
5. generate_document(sections) 输出最终 INP。

# 约束
- 修改前向用户确认关键改动（栅元编号、材料号、密度、重叠补集方向）。
- 保持既有曲面/栅元编号递增规则。
- 几何重叠（体积校验）暂由工具外提示，add_shape 默认材料真空（M0）。
- ⚠️ 管线走结构化路径，不建模 text mode / raw override：文本模式段会被结构化重写，不保留手写原文。
```

---

## 说明

- 工具清单 / 参数权威见 **`docs/inputcard-mcp.md`**。
- 主程序（5001 后端）**不依赖**此通道；仅 AI 接入用 `--mcp-http`。
- 该通道随本程序分发（已打进 `python.exe` 的 `_internal`），无需额外安装 Python 依赖。
