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

fn main() {
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
            open_source_demo_window
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
