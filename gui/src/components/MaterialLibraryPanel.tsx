/**
 * 材料库管理面板（深化 B）—— 编辑 / 删除 / 恢复原始 / 导入导出 / ZAID 明细。
 *
 * 交互规则（用户确认）：
 * - 所有预设（内置/自定义）都不就地编辑，编辑一律弹 MaterialEditDialog（额外弹窗）。
 * - 「保存至材料库」把当前内容写库；编辑内置/已修改 → override，新建 → custom。
 * - 「恢复原始」= 删除 override，还原为内置。
 * - 编辑入口只在管理面板（MaterialEditDialog 不另设覆盖入口）。
 */
import React, { useMemo, useState } from "react";
import FloatingDialog from "./FloatingDialog";
import MaterialEditDialog from "./MaterialEditDialog";
import { useMaterialLibrary } from "../hooks/useMaterialLibrary";
import type { LibraryEntry } from "../data/materialLibrary";
import { importLibrary, exportLibrary } from "../data/materialLibrary";
import { apiUrl } from "../utils/api";

interface Props { onClose: () => void }

function download(name: string, text: string) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export default function MaterialLibraryPanel({ onClose }: Props) {
  const { entries, reload, remove, save } = useMaterialLibrary();
  const [search, setSearch] = useState("");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [zaidValid, setZaidValid] = useState<Record<string, boolean | null>>({});
  const [importPreview, setImportPreview] = useState<any>(null);
  const [conflict, setConflict] = useState<"skip" | "overwrite" | "rename">("skip");
  const [importFileText, setImportFileText] = useState<{ format: "json" | "csv"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const groups = useMemo(() => {
    const q = search.trim().toLowerCase();
    const match = (e: LibraryEntry) => !q || (e.name + " " + e.formula + " " + e.desc).toLowerCase().includes(q);
    const builtin: [string, LibraryEntry[]][] = [];
    const custom: LibraryEntry[] = [];
    const override: LibraryEntry[] = [];
    for (const e of entries) {
      if (!match(e)) continue;
      if (e.origin === "custom") custom.push(e);
      else if (e.origin === "override") override.push(e);
      else {
        let g = builtin.find((x) => x[0] === e.category);
        if (!g) { g = [e.category, []]; builtin.push(g); }
        g[1].push(e);
      }
    }
    return { builtin, custom, override };
  }, [entries, search]);

  const validateZaid = (id: string, zaid: string) => {
    const base = zaid.replace(/\..*$/, "").replace(/^0+/, "");
    if (!base) { setZaidValid((p) => ({ ...p, [id]: null })); return; }
    fetch(apiUrl("/api/validate-zaid?zaid=" + encodeURIComponent(base)))
      .then((r) => r.json())
      .then((j) => setZaidValid((p) => ({ ...p, [id]: j.in_db })))
      .catch(() => setZaidValid((p) => ({ ...p, [id]: null })));
  };

  const toggleExpand = (e: LibraryEntry) => {
    const key = e.key;
    if (expanded === key) { setExpanded(null); return; }
    setExpanded(key);
    for (const r of e.rows) {
      if (r.kind === "nuclide" && r.zaid) validateZaid(key + ":" + r.zaid, r.zaid);
    }
  };

  const doExport = async (format: "json" | "csv") => {
    setBusy(true);
    try {
      const res = await exportLibrary(format, entries);
      download("material_library." + format, res.content);
    } catch (e: any) { alert("导出失败: " + (e.message || e)); }
    finally { setBusy(false); }
  };

  const doImportPick = async (file: File) => {
    const text = await file.text();
    const format: "json" | "csv" = file.name.toLowerCase().endsWith(".csv") ? "csv" : "json";
    setImportFileText({ format, text });
    setBusy(true);
    try {
      const res = await importLibrary({ format, content: text, conflict: "skip", existingKeys: entries.map((e) => e.key), existingEntries: entries, dryRun: true });
      setImportPreview(res);
    } catch (e: any) { alert("导入解析失败: " + (e.message || e)); }
    finally { setBusy(false); }
  };

  const doImportApply = async () => {
    if (!importFileText) return;
    setBusy(true);
    try {
      const res = await importLibrary({
        format: importFileText.format, content: importFileText.text, conflict,
        existingKeys: entries.map((e) => e.key), existingEntries: entries, dryRun: false,
      });
      const r = res.result;
      alert(`导入完成：新增 ${r.imported.length}，相同跳过 ${r.identical.length}，跳过 ${r.skipped.length}，覆写 ${r.overwritten.length}，改名 ${r.renamed.length}`);
      setImportPreview(null); setImportFileText(null);
      await reload();
    } catch (e: any) { alert("导入失败: " + (e.message || e)); }
    finally { setBusy(false); }
  };

  const editing = editingKey ? entries.find((e) => e.key === editingKey) : null;

  const renderEntry = (e: LibraryEntry) => {
    const isOverride = e.origin === "override";
    const matchVal = expanded === e.key;
    return (
      <div key={e.key} style={{ borderBottom: "1px solid var(--border-glass)", padding: "6px 4px" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <code style={{ fontSize: 11, color: "var(--text-tertiary)", minWidth: 110 }}>{e.key}</code>
          <span style={{ flex: 1, fontWeight: 600, fontSize: 13, cursor: "pointer" }}
            onClick={() => toggleExpand(e)}>{e.name}{isOverride ? " ⚙" : ""}</span>
          {e.density && <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{e.density} g/cm³</span>}
          <button className="btn btn-ghost btn-xs" onClick={() => setEditingKey(e.key)}>✎ 编辑</button>
          <button
            className={"btn btn-xs " + (isOverride ? "btn-ghost" : "btn-danger")}
            title={isOverride ? "删除覆盖，还原为内置" : "删除该材料"}
            onClick={async () => {
              if (window.confirm(isOverride ? `删除 ${e.name} 的本地覆盖并还原为内置？` : `删除材料 ${e.name}？`)) {
                await remove(e.key);
              }
            }}>
            {isOverride ? "恢复原始" : "删除"}
          </button>
        </div>
        {matchVal && (
          <div style={{ marginTop: 6, paddingLeft: 8, fontSize: 11, color: "var(--text-secondary)" }}>
            <div>{e.formula ? `化学式: ${e.formula}` : ""}{e.desc ? ` · ${e.desc}` : ""}</div>
            {e.options ? <div>其他: <code>{e.options}</code></div> : null}
            {e.mtCard ? <div>MT 卡: <code>{e.mtCard}</code></div> : null}
            {(e.rows || []).map((r, i) => {
              const zaid = r.kind === "nuclide" ? r.zaid : "";
              return (
              <div key={i} style={{ display: "flex", gap: 6, alignItems: "center", fontFamily: "Consolas,monospace" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block",
                  background: zaidValid[e.key + ":" + zaid] === true ? "#4caf50"
                    : zaidValid[e.key + ":" + zaid] === false ? "#e53935" : "#555" }} />
                {r.kind === "raw" ? <span># {r.text}</span>
                  : <span>{r.zaid || "(空)"} — {r.fraction}</span>}
              </div>
            );})}
          </div>
        )}
      </div>
    );
  };

  return (
    <FloatingDialog title="📚 材料库" onClose={onClose} width={680}>
      <div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          <input className="form-input" style={{ flex: 1, minWidth: 180 }} placeholder="搜索材料（名称/化学式/描述）"
            value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => reload()}>刷新</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => doExport("json")}>导出 JSON</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => doExport("csv")}>导出 CSV</button>
          <label className="btn btn-success btn-sm" style={{ cursor: "pointer" }}>
            导入
            <input type="file" accept=".json,.csv" style={{ display: "none" }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) doImportPick(f); e.target.value = ""; }} />
          </label>
        </div>

        {importPreview && (
          <div style={{ border: "1px solid var(--border-glass)", borderRadius: 8, padding: 10, marginBottom: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
              检测到 {importPreview.preview.length} 条材料
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 8 }}>
              <span style={{ fontSize: 11 }}>冲突处理：</span>
              {(["skip", "overwrite", "rename"] as const).map((c) => (
                <button key={c} className={"btn btn-xs " + (conflict === c ? "btn-primary" : "btn-ghost")}
                  onClick={() => setConflict(c)}>{c === "skip" ? "跳过" : c === "overwrite" ? "覆盖" : "改名"}</button>
              ))}
            </div>
            {importPreview.preview.map((p: any) => (
              <div key={p.key || p.name} style={{ fontSize: 11, padding: "2px 0" }}>
                <b>{p.name}</b>
                {p.errors?.length ? <span style={{ color: "#e53935" }}> ⚠ {p.errors.join("；")}</span> : null}
                {p.xsdir?.length ? <span style={{ color: "#e6a23c" }}> ⚠ xsdir:{p.xsdir.map((x: any) => x.zaid).join(",")}</span> : null}
              </div>
            ))}
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button className="btn btn-primary btn-sm" disabled={busy} onClick={doImportApply}>确认导入</button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setImportPreview(null); setImportFileText(null); }}>取消</button>
            </div>
          </div>
        )}

        <div style={{ maxHeight: "55vh", overflow: "auto" }}>
          {groups.custom.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", margin: "6px 0" }}>我的材料</div>
              {groups.custom.map(renderEntry)}
            </div>
          )}
          {groups.override.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", margin: "6px 0" }}>已修改（覆盖内置）</div>
              {groups.override.map(renderEntry)}
            </div>
          )}
          {groups.builtin.map(([cat, items]) => (
            <div key={cat}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", margin: "6px 0" }}>{cat}</div>
              {items.map(renderEntry)}
            </div>
          ))}
        </div>
      </div>

      {editing && (
        <MaterialEditDialog
          matNum="L"
          name={editing.name}
          nuclides={editing.rows}
          density={editing.density}
          options={editing.options}
          mtCard={editing.mtCard}
          initialSourceKey={editing.key}
          hidePreset
          initialFormulaText={editing.formula}
          onSave={async (d) => {
            // 从「材料库」面板编辑：footer「保存」直接写回库（内置→override）
            await save({
              key: editing.key,
              name: d.name,
              category: editing.category,
              formula: editing.formula,
              desc: editing.desc,
              density: d.density,
              options: d.options,
              mtCard: d.mtCard,
              origin: editing.origin === "builtin" ? "override" : editing.origin,
              rows: d.nuclides,
            });
            setEditingKey(null);
          }}
          onClose={() => setEditingKey(null)}
        />
      )}
    </FloatingDialog>
  );
}
