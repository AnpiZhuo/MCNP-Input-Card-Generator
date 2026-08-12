/**
 * api — 后端地址单一常量
 *
 * 全部前端 fetch 收敛到 127.0.0.1 直连 IPv4，规避 Chrome 对 `localhost`
 * 先试 ::1（IPv6）→ 连接拒绝 → Happy Eyeballs 回退 IPv4 的 ~300-500ms/请求
 * 惩罚（影响全部 25 端点）。后端绑定 0.0.0.0 不变，CORS 已 `*` 覆盖。
 */
export const API_BASE = "http://127.0.0.1:5001";

/** 拼后端接口路径：apiUrl("/api/preview-3d") => "http://127.0.0.1:5001/api/preview-3d" */
export const apiUrl = (p: string): string => API_BASE + p;
