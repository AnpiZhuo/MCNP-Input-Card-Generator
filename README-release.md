# MCNP 输入卡生成器 — 本地一键发版说明（release.bat）

> 本说明对应仓库根目录的 `release.bat`。它把原先手动的 5 步打包流程固化为一条命令，**不依赖 GitHub / CI，只在本地发放新版本**。
>
> 仓库根旧的 `build.bat` 已过时（只做前端 + PyInstaller，不含 sidecar onedir 替换、Tauri 打包、部署与自检），**建议后续废弃删除，请勿再使用**。

---

## 一、它能做什么

一条命令依次完成：

1. **门禁**：后端 `pytest` + 前端 `vitest`，有失败即中止（红字报错 + 非零退出码）。
2. **版本号**：读取 `tauri.conf.json` / `package.json` 的当前版本（当前 1.6.4），可选输入新版本号并同步更新两个文件。
3. **构建**：`vite build` → `PyInstaller` 打包 sidecar（onedir）→ sidecar 替换进 `src-tauri/binaries/` → `tauri build`（Rust）。
4. **部署**：清空 `D:\MCNP\MCNP输入卡生成器` 并复制完整产物（exe + python.exe + _internal/）。
5. **自检**：启动 exe → 5001 端口探活 → `/api/generate` 最小 deck 冒烟 → 清理进程 → 报告成功/失败与产物路径。

**关键防御（血泪教训固化进脚本）**：
- **spec 模块清单自检**：sidecar `_internal/app/` 必须包含 `preview_cache.py`（曾漏进 spec 导致打包后 exe 启动即崩），缺失即中止报错。
- **onedir 结构完整**：`python.exe` + `_internal/` 一起复制，绝不只拷 exe。
- **每步失败即中止**：打印明确错误 + 非零退出码，不静默跳过。

---

## 二、环境要求

| 依赖 | 说明 |
|------|------|
| Python 3.10+ | 含 `pytest`、`PyInstaller`（脚本用 `python -m PyInstaller`） |
| Node.js 18+ | 含 `gui/node_modules`（vite / vitest / tauri CLI） |
| Rust 工具链 | 固定位于 `D:\rust`（脚本会检查 `D:\rust\cargo\bin\cargo.exe`，并设置 `RUSTUP_HOME=D:\rust\rustup`、`CARGO_HOME=D:\rust\cargo`） |
| curl | Windows 10 1803+ 自带 `curl.exe`（自检冒烟用） |
| FreeCAD | 运行期 3D/截面用，发版流程本身不依赖 |

---

## 三、用法

### 方式一：双击
在资源管理器中双击仓库根 `release.bat`，按提示操作。

### 方式二：命令行（可传新版本号）
```bat
release.bat
release.bat 1.6.4          :: 直接指定新版本号，跳过交互输入
release.bat "1.6.4"
```

### 交互流程
- 若未传版本号参数，脚本会提示：
  `输入新版本号（直接回车沿用 1.6.4）：`
  - 直接回车：沿用当前版本号（不发新版本号时推荐）。
  - 输入如 `1.6.4`：校验格式（`主.次.修订`）后，**同步更新** `gui/package.json` 与 `gui/src-tauri/tauri.conf.json` 的 `version`，并提示发版后提交 git。

---

## 四、各步骤说明

### [1/5] 门禁
- 后端：仓库根执行 `python -m pytest tests/ -q`（当前基线 **271 全绿**）。
- 前端：`gui/` 下执行 `npx vitest run`（当前基线 **19 全绿**）。
- 任一失败：红字报错并中止。

### [2/5] 版本号
- 以 `tauri.conf.json` 的 `package.version` 为权威读取当前版本（当前 1.6.4）。
- 若与 `package.json` 不一致会打印警告，以 `tauri.conf.json` 为准。
- 版本号更新用 Python 做**精确字符串替换**（UTF-8 无 BOM，保留文件原有格式与缩进），不改动其它字段。

### [3/5] 构建
| 子步骤 | 命令 | 产物/动作 |
|--------|------|-----------|
| a | `cd gui && npm run build` | `gui/dist/`（vite） |
| b | `cd gui && python -m PyInstaller --noconfirm mcnp_sidecar.spec` | `gui/dist/python/`（onedir：python.exe + _internal/） |
| c | 替换 sidecar | `dist/python/python.exe` → `src-tauri/binaries/python-x86_64-pc-windows-msvc.exe`；`_internal/` → `src-tauri/binaries/_internal/`（整体替换） |
| c2 | **spec 模块清单自检** | 核对 `binaries/_internal/app/preview_cache.py` 在位，缺失即中止 |
| d | `RUSTUP_HOME=D:\rust\rustup CARGO_HOME=D:\rust\cargo npm run tauri build`（gui/ 下） | `src-tauri/target/release/`（exe + python.exe + _internal/） |

> PyInstaller 必须在 `gui/` 目录下执行，因为 `mcnp_sidecar.spec` 用 `os.getcwd()/..` 定位工程根。

### [4/5] 部署
- 自动关闭占用 5001 的 sidecar 与已部署主程序 exe（避免锁文件导致 `rmdir` 失败）。
- 清空 `D:\MCNP\MCNP输入卡生成器` 后复制完整 onedir：`MCNP 输入卡生成器.exe` + `python.exe` + `_internal/`。
- 复制后复验：三个产物齐全 + `_internal/app/preview_cache.py` 在位。

### [5/5] 自检
1. 启动 `D:\MCNP\MCNP输入卡生成器\MCNP 输入卡生成器.exe`。
2. 轮询 `netstat` 等待 `5001` 端口 `LISTENING`（最多 90 秒）。
3. 向 `http://127.0.0.1:5001/api/generate` 发送最小 deck，断言响应 `status == "ok"` 且 `inp` 含 `SDEF`。
4. 清理进程（kill 占用 5001 的进程 + 主 exe），打印成功/失败与产物路径。

---

## 五、常见失败排查

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| `[1/5]` 门禁红字失败 | pytest/vitest 有红用例 | 按错误修复后重跑。基线：pytest 271 / vitest 19 全绿 |
| `版本号格式无效` | 输入了非 `主.次.修订` 的值 | 改为如 `1.6.4` 重新输入 |
| `spec 模块清单自检失败：_internal\app\preview_cache.py 缺失` | `gui/mcnp_sidecar.spec` 的 `_keep_py` 漏了 `preview_cache.py` | 打开 spec 确认 `_keep_py` 含 `"preview_cache.py"`，补上后重跑 |
| `PyInstaller 打包 sidecar 出错` | 依赖缺失 / 路径异常 | 确认在 `gui/` 下执行；`python -m PyInstaller --version` 可出版本号；检查完整错误输出 |
| `tauri build 出错（Rust 编译）` | Rust 工具链缺失/损坏 | 确认 `D:\rust\cargo\bin\cargo.exe` 存在；检查 cargo 报错 |
| `无法清空 D:\MCNP\MCNP输入卡生成器` | 仍有进程占用部署目录 | 脚本已自动关闭占用 5001 与主 exe 的进程；仍失败则手动关闭相关程序后重试 |
| `exe 启动 90 秒内 5001 端口未就绪` | 部署目录不完整 / 杀软拦截 / GPU 环境异常 | 确认 `exe + python.exe + _internal/` 齐全；任务管理器查看是否有残留进程；手动双击 exe 观察能否拉起 5001 |
| `冒烟响应校验未通过（status 非 ok 或 inp 不含 SDEF）` | sidecar 启动异常 / 5001 被其它程序占用 | 检查 `_internal/app/preview_cache.py`；确认 5001 未被其它服务占用 |

---

## 六、注意事项

- 脚本每一步失败都会**红字 + 非零退出码**中止，不会静默跳过，方便定位。
- **会关闭正在运行的已部署 MCNP 程序**（占用 5001 的 sidecar 与主 exe），因为部署需清空目录。若有工作未保存，先手动关闭应用保存后再跑。
- 输入新版本号会修改 `gui/package.json` 与 `gui/src-tauri/tauri.conf.json`（git 跟踪文件），**发版后请一并提交**。
- 脚本基于脚本所在位置（仓库根）推导路径，可在任意磁盘位置复制使用；部署目标 `D:\MCNP\MCNP输入卡生成器` 为交付路径固定写入。
- 全脚本路径均已加引号，兼容中文与空格目录名。
