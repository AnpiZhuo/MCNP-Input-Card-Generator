# inputcard-mcp — MCP 服务器包（本地 stdio，作为本程序的内置能力）
#
# 设计目标：让支持 MCP 的 AI 助手能在本地直接读写 MCNP 输入卡（.INP），
# **不**引入常驻服务器、不开放端口、数据不出本机。它复用本程序后端已有的
# parse_inp_text / generate_inp_from_deck / deck 双向转换能力。
#
# 启动（stdio，供 AI 客户端自动拉起）：python -m inputcard_mcp
# 依赖：mcp>=1,<2（FastMCP v1）
