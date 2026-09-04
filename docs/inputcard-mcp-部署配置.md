# AI 接入配置（inputcard-mcp）

本部署目录已附带 **AI 接入能力**：`python.exe --mcp-server` 是一个本地 stdio MCP 服务器，支持 MCP 的 AI 助手可直接读取、修改、生成 **MCNP 输入卡（.INP）**。**数据不出本机、不对外开放端口、无需常驻服务器**（AI 客户端按需拉起，用完即止）。

> 命名说明：服务名 `inputcard-mcp` **刻意避开 "MCNP" 子串**（MCNP® 为 Triad/LANL 注册商标，且避免与 `mcnp_bridge`/`mcnp_sidecar` 混淆）。

---

## 一、让 AI 自动发现（一次性注册）

在支持 MCP 的 AI 客户端（Claude Desktop / Claude Code / 其他 agent）里添加以下服务：

> **`<安装目录>` 占位符**：MCP 的 `command` 必须是**绝对路径**，但没人知道你把程序解压到哪——所以把 `<安装目录>` 替换成**你实际安装/解压到的地方**。最省事的就是用**本文件所在目录**（`python.exe` 就在本文件旁边）：在资源管理器地址栏复制该目录路径，或右键 `python.exe` → 属性 → 复制位置。

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

注册后，AI 会自动发现 **6 个工具**，覆盖全部 MCNP 数据段（按语义段读写）：

- `read_document` / `generate_document` / `validate_document`（文档级：INP ⇄ 按段的 sections 结构 / 校验）
- `list_section` / `patch_section`（按语义段读/写；`section` ∈ `basic / surfaces / tr_cards / cells / materials / sources / tally / advanced`，含源模式 SDEF/KCODE/SSW/SSR）
- `add_shape`（几何便捷：rcc / rpp / sph / hex / tet）

## 二、给 AI 的提示词

若你的 AI 客户端**不支持 MCP 自动发现**，或想在第一句就声明能力，打开同目录 **`AI接入提示词.md`**，复制其中的提示语（简单版 / System Prompt 版）到对话即可。

## 三、说明

- 工具清单与参数详见源码仓库 `docs/inputcard-mcp.md`。
- 主程序（`MCNP 输入卡生成器.exe`，5001 后端）**不依赖**此 MCP 能力；`--mcp-server` 是可选分派。
- 该能力随本程序分发（已打进 `python.exe` 的 `_internal`），无需额外安装 Python 依赖。
