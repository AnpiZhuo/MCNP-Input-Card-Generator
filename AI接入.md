# inputcard-mcp — AI 接入（配置 + 给 AI 的提示）

`inputcard-mcp` 是随本程序分发的**本地 stdio MCP 服务器**（`python.exe --mcp-server`），支持 MCP 的 AI 助手可直接读取、修改、生成 **MCNP 输入卡（.INP）**。**数据不出本机、不对外开放端口、无需常驻服务器**（AI 客户端按需拉起，用完即止）。

> **命名**：服务名 `inputcard-mcp` 刻意避开 "MCNP" 子串（MCNP® 为 Triad/LANL 注册商标，且避免与 `mcnp_bridge`/`mcnp_sidecar` 混淆）。

---

## ① 配置 —— 让 AI 能连上（**人做一次**）

### 一键自动注册（推荐）：运行同目录 `注册MCP.bat`

双击即可，无需懂配置。它会：

- **自动探测**「本脚本所在目录」的 `python.exe`（`%~dp0`，**零硬编码路径**——程序复制/解压到哪都能用）；
- 写入 **Claude Desktop 配置**（`%APPDATA%\Claude\claude_desktop_config.json`，若存在）与本目录 **`.mcp.json`**（供 Claude Code 等项目级客户端）；
- 打印写入结果。

注册后 AI 客户端**自动发现** inputcard-mcp，无需再手动填路径。

### 手动配置（备选）

若你已有某个客户端注册入口，也可手动加。MCP 的 `command` 需**绝对路径**，把 `<安装目录>` 换成你实际安装位置——最省事用**本文件所在目录**（`python.exe` 就在本文件旁边）：资源管理器地址栏复制目录路径，或右键 `python.exe` → 属性 → 复制位置。

**Claude Desktop（`claude_desktop_config.json`）**

```json
{
  "mcpServers": {
    "inputcard-mcp": {
      "command": "<安装目录>\\python.exe",
      "args": ["--mcp-server"]
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
      "command": "<安装目录>\\python.exe",
      "args": ["--mcp-server"]
    }
  }
}
```

---

## ② 给 AI 的提示 ——（**可复制**，仅当你需要时）

> 配置好后 AI 通常**已自动发现**这些工具，**无需这段提示**；仅在不支持自动发现的客户端、或你希望第一句就声明能力时使用。

### 简单版（一句话）

```
你可以使用 inputcard-mcp 这个 MCP 服务来读写 MCNP 输入卡：
read_document（INP → 按段的 sections 结构）、generate_document（sections → INP）、
list_section / patch_section（按语义段读/写，覆盖基础/曲面/TR/栅元/材料/源/计数/高级）、
add_shape（rcc / rpp / sph / hex / tet）、validate_document。
请帮我处理这份 MCNP 输入卡。
```

### 详细版（System Prompt）

```
# 角色
你是一个 MCNP 输入卡助手，通过输入卡生成器 inputcard-mcp 读写、校验、修改 MCNP 输入文件（.INP）。
你**不手写 MCNP 卡文本**（避免产生语义错误），而是调用工具读取结构化数据、修改、再生成回 INP。

# 工具（共 6 个）
文档级：
  read_document(inp)        INP → { sections, warnings }（8 个语义段 + universe_comments）
  generate_document(sections)  sections → INP 文本（与 read_document 输出同构）
  validate_document(inp)    语法 + 解析警告校验（不含几何重叠）
按段读写（核心，覆盖全部 INP 段）：
  list_section(inp, section)  读一个语义段（与 read_document 的 sections[section] 相同结构）
  patch_section(inp, section, data)  整体替换一个语义段 → 新 INP（全量覆盖）
  section ∈ basic / surfaces / tr_cards / cells / materials / sources / tally / advanced
      （advanced 含源模式 SDEF/KCODE/SSW/SSR、phys、other_cards）
几何便捷：
  add_shape(inp, shape, params)  追加规则几何体（rcc 圆柱 / rpp 六面体 / sph 球 / hex 六棱柱 / tet 四面体）

# 工作流
1. read_document 读取用户提供的 INP 文本，得到 sections。
2. list_section 查看现状（或直接用 sections[section]）。
3. 修改：给 sections[section] 改值，或 patch_section(inp, section, data)。
4. validate_document 校验语法与解析警告。
5. generate_document(sections) 输出最终 INP 文本。

# 约束
- 修改前向用户确认关键改动（栅元编号、材料号、密度、重叠补集方向）。
- 保持既有曲面编号、栅元编号递增规则。
- 几何重叠（体积校验）暂由工具外提示，add_shape 默认材料为真空（M0）。
- ⚠️ 管线走结构化路径，**不建模 text mode / raw override**：若某段原本是文本模式手写的 raw 原文，
  改写时 MCP 会按结构化重生成该段，不会保留手写原文。
```

---

## 说明

- 工具清单 / 参数权威见 **`docs/inputcard-mcp.md`**。
- 主程序（`MCNP 输入卡生成器.exe`，5001 后端）**不依赖**此 MCP 能力；`--mcp-server` 是可选分派。
- 该能力随本程序分发（已打进 `python.exe` 的 `_internal`），无需额外安装 Python 依赖。
