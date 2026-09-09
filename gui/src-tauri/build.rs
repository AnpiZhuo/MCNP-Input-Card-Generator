fn main() {
    // 6.2 坑根治：sidecar(python.exe+_internal) 变化时强制重跑 build script，
    // 让 tauri-build 重新复制 python.exe 到 target。部署时 sidecar 全程从
    // binaries/ 复制，不依赖 target 副本；但保持 target 与 binaries 一致可降低
    // 调试时跑 target/release 下 exe 的混淆风险。
    println!("cargo:rerun-if-changed=binaries");
    tauri_build::build()
}
