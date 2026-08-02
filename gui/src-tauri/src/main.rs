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

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_username,
            minimize_window,
            toggle_maximize_window,
            close_window,
            start_dragging_window
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
