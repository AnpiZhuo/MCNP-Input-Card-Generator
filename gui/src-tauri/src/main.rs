#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::Manager;

#[tauri::command]
fn get_username() -> String {
    std::env::var("USERNAME").unwrap_or_else(|_| "U".to_string())
}

// ── 自定义窗口命令：直接调 Rust Window API（不依赖 Cargo 的 window-* features）──
#[tauri::command]
fn minimize_window(window: tauri::Window) {
    let _ = window.minimize();
}

#[tauri::command]
fn toggle_maximize_window(window: tauri::Window) {
    match window.is_maximized() {
        Ok(true) => {
            let _ = window.unmaximize();
        }
        _ => {
            let _ = window.maximize();
        }
    }
}

#[tauri::command]
fn close_window(window: tauri::Window) {
    let _ = window.close();
}

#[tauri::command]
fn start_dragging_window(window: tauri::Window) {
    let _ = window.start_dragging();
}

// ── 独立弹出窗口（3D 预览 / 截面）──
// 主窗口点按钮 → 写 localStorage 数据桥 → 调此命令开窗。
// 若目标窗口已存在则 show + focus（不重复开），否则新建。
// URL 带 hash 片段：前端 WindowRouter 同步读取 hash 立即渲染对应组件，
// 消除「先闪主界面再切子窗口」的闪烁（P0，2026-09）。
fn create_or_focus(
    app: &tauri::AppHandle,
    label: &str,
    title: &str,
    width: f64,
    height: f64,
    hash: &str,
) -> Result<(), String> {
    if let Some(win) = app.get_window(label) {
        let _ = win.show();
        let _ = win.set_focus();
        return Ok(());
    }
    let url = format!("index.html#/{}", hash);
    tauri::WindowBuilder::new(
        app,
        label,
        tauri::WindowUrl::App(url.into()),
    )
    .title(title)
    .inner_size(width, height)
    .build()
    .map(|_| ())
    .map_err(|e| e.to_string())
}

#[tauri::command]
async fn open_preview3d_window(app: tauri::AppHandle) -> Result<(), String> {
    create_or_focus(&app, "preview3d", "3D 预览", 1300.0, 820.0, "preview3d")
}

#[tauri::command]
async fn open_cross_section_window(app: tauri::AppHandle) -> Result<(), String> {
    create_or_focus(&app, "cross_section", "截面", 1000.0, 700.0, "cross_section")
}

#[tauri::command]
async fn open_volume3d_window(app: tauri::AppHandle) -> Result<(), String> {
    // label 必须与 App.tsx WindowRouter 路由分支同值（"volume"→ResultWindow）。
    // 曾用 "volume3d"：与路由 "volume" 不匹配 → 子窗口渲染整个主应用（P0，已修）。
    create_or_focus(&app, "volume", "3D 结果", 1300.0, 820.0, "volume")
}

#[tauri::command]
async fn open_ptrac_window(app: tauri::AppHandle) -> Result<(), String> {
    // label 必须与 App.tsx WindowRouter 路由分支同值（"ptrac"→PtracWindow）。
    create_or_focus(&app, "ptrac", "3D 径迹", 1300.0, 820.0, "ptrac")
}

#[tauri::command]
async fn open_source_demo_window(app: tauri::AppHandle) -> Result<(), String> {
    // label 必须与 App.tsx WindowRouter 路由分支同值（"source-demo"→SourceDemoWindow）。
    create_or_focus(&app, "source-demo", "演示源", 1300.0, 820.0, "source-demo")
}

/// 「Tally 通量图」独立窗口。
///
/// 为什么给它独立窗口：它原本只是输出页里一个 `maxWidth:640` 的弹窗 —— 图小、不能调整大小、
/// 还和数据表挤在同一张卡片里；而本程序里凡是"要看的结果图"都已经有自己的窗口
/// （3D 预览 / 截面 / 3D 结果 / 3D 径迹 / 演示源），唯独它没有。独立后同时解决三件事：
/// 图能铺满窗口、导出按钮与其它窗口位置一致、数据表留在输出页不再被挤压。
#[tauri::command]
async fn open_tally_chart_window(app: tauri::AppHandle) -> Result<(), String> {
    create_or_focus(&app, "tally_chart", "Tally 通量图", 1000.0, 700.0, "tally_chart")
}

/// 优先使用随包分发的 WebView2「固定版运行时」，让没有 Edge 的机器也能开界面。
///
/// **背景（2026-09-29 实测）**：界面是 WebView2 渲染的，而 WebView2 平时由 Edge 附带安装。
/// 精简版 Windows 删掉了 Edge，就同时没有 WebView2 Runtime ⇒ 双击 exe 没反应/一闪就没。
/// 随包带一份固定版运行时（微软官方可再分发形态），用 WebView2 官方支持的环境变量
/// `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` 指过去，即可完全不依赖系统里有没有 Edge。
///
/// 为什么是「存在才设」而不是写进 `tauri.conf.json` 的 `webviewInstallMode=fixedRuntime`：
/// 后者会让 Tauri 在 `setup()` 里**无条件**把该变量指向 `<exe目录>\WebView2`（tauri 1.8.3
/// `src/app.rs:1696-1715`），于是只要用户漏拷了这个目录（或者只拷了 exe），
/// 连**本来能用系统运行时**的机器也一并打不开 —— 把"可选增强"变成"硬依赖"。
/// 这里做成「有则用、无则退」：目录齐全 ⇒ 完全自带；目录缺失 ⇒ 回退系统运行时，行为同旧版。
#[cfg(target_os = "windows")]
fn prefer_bundled_webview2() {
    let Ok(exe) = std::env::current_exe() else {
        return;
    };
    let Some(dir) = exe.parent() else { return };
    let runtime = dir.join("WebView2");
    // 认 msedgewebview2.exe：它必须直接躺在该目录下，这正是浏览器可执行文件目录的定义
    if runtime.join("msedgewebview2.exe").is_file() {
        std::env::set_var("WEBVIEW2_BROWSER_EXECUTABLE_FOLDER", &runtime);
    }
}

#[cfg(not(target_os = "windows"))]
fn prefer_bundled_webview2() {}

fn main() {
    // ★ 必须在任何窗口/WebView 创建之前调用：WebView2 装载器只在**创建环境时**读这个变量
    prefer_bundled_webview2();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_username,
            minimize_window,
            toggle_maximize_window,
            close_window,
            start_dragging_window,
            open_preview3d_window,
            open_cross_section_window,
            open_volume3d_window,
            open_ptrac_window,
            open_source_demo_window,
            open_tally_chart_window
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
