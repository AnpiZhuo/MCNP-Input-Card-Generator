# MCNP 输入卡生成器 — Tauri + React UI

## 快速开始

```bash
# 安装前端依赖
npm install

# Web 预览（无需 Rust，仅看 UI）
npm run dev

# Tauri 桌面应用（需要 Rust 工具链）
npm run tauri dev
```

## 构建

```bash
npm run tauri build
```

## 项目结构

```
mcnp-ui/
├── src/                   # React 前端
│   ├── components/        # UI 组件
│   ├── styles/global.css  # 全局样式（深色/玻璃/霓虹）
│   ├── utils/backend.ts   # Python 后端桥接
│   ├── App.tsx            # 主布局
│   └── main.tsx           # 入口
├── src-tauri/             # Tauri 原生壳
├── backend/               # Python 后端
│   └── mcnp_bridge.py     # 生成器 sidecar
└── package.json
```

## 技术栈

- **前端**: React 18 + TypeScript + Vite
- **桌面壳**: Tauri 1.6 (Rust)
- **后端**: Python 3 (原 app/ 目录代码)
- **通信**: Tauri sidecar (stdin/stdout JSON)
- **主题**: CSS 变量深色主题
