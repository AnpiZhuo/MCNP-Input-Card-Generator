/**
 * useFreecadStatus — FreeCAD 可用性门控 hook。
 *
 * 深度封装三条链路（检测 / 门控 / 手动指定路径），把 GeometryTab 里
 * 内联的三连 fetch 和弹窗状态收进来，调用方只需一个 require()。
 *
 * 接口：
 *   status       "checking" | "ok" | "missing"
 *   require()    状态为 missing 时弹出下载对话框并返回 false，否则 true
 *   pickPath()   弹系统文件选择框选 FreeCAD.exe → 保存 → 重新检测
 *   showDialog   是否显示「需要 FreeCAD」下载对话框
 *   closeDialog() 关闭对话框
 */
import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "./api";

const API = apiUrl("/api");

export type FreecadStatus = "checking" | "ok" | "missing";

export interface FreecadGate {
  status: FreecadStatus;
  require: () => boolean;
  pickPath: () => Promise<void>;
  showDialog: boolean;
  closeDialog: () => void;
}

export function useFreecadStatus(): FreecadGate {
  const [status, setStatus] = useState<FreecadStatus>("checking");
  const [showDialog, setShowDialog] = useState(false);

  const check = useCallback(async (): Promise<boolean> => {
    try {
      const r = await fetch(`${API}/check-freecad`, { method: "POST" });
      const j = await r.json();
      setStatus(j.status === "ok" && j.found ? "ok" : "missing");
      return true; // 拿到后端的明确答案（有/无 FreeCAD）
    } catch {
      return false; // 后端未就绪（sidecar 冷启动），需要重试
    }
  }, []);

  // 挂载后检测；后端冷启动 ~3s（Defender 扫描更久），失败则轮询重试，
  // 避免把"后端未就绪"误判成"FreeCAD 缺失"
  useEffect(() => {
    let stopped = false;
    const poll = async () => {
      for (let i = 0; i < 15 && !stopped; i++) {
        if (await check()) return;
        await new Promise((res) => setTimeout(res, 1500));
      }
    };
    poll();
    return () => { stopped = true; };
  }, [check]);

  const require = useCallback(() => {
    if (status === "missing") {
      setShowDialog(true);
      return false;
    }
    return true;
  }, [status]);

  const pickPath = useCallback(async () => {
    try {
      const r1 = await fetch(`${API}/choose-freecad-path`, { method: "POST" });
      const j1 = await r1.json();
      if (j1.cancelled || !j1.path) return;
      await fetch(`${API}/set-freecad-path`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: j1.path }),
      });
      await check();
    } catch (e) {
      alert("设置 FreeCAD 失败: " + ((e as any)?.message || ""));
    }
  }, [check]);

  return {
    status,
    require,
    pickPath,
    showDialog,
    closeDialog: () => setShowDialog(false),
  };
}
