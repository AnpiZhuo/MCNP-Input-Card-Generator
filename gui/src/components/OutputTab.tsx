import React, { useState, useRef } from "react";
import { parseOutp, type ParsedOutput } from "../utils/outputParser";
import DocViewer from "./DocViewer";
import { apiUrl } from "../utils/api";

export default function OutputTab() {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [parsed, setParsed] = useState<ParsedOutput | null>(null);
  const [filePath, setFilePath] = useState("");
  const [selectedTally, setSelectedTally] = useState("1");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleBrowse = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFilePath(file.name);
    try {
      const text = await file.text();
      // 先尝试后端 pymcnp 解析
      try {
        const r = await fetch(apiUrl("/api/parse-outp"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outp: text }), signal: AbortSignal.timeout(10000) });
        const j = await r.json();
        if (j.status === "ok" && j.tallies) { setParsed(j); setSelectedTally(Object.keys(j.tallies)[0]); return; }
      } catch {}
      // Fallback: 本地解析器
      const result = parseOutp(text);
      setParsed(result);
      if (Object.keys(result.tallies).length > 0) {
        setSelectedTally(Object.keys(result.tallies)[0]);
      }
    } catch (err: any) {
      alert("解析失败: " + err.message);
    }
  };

  const handleExportCsv = () => {
    if (!parsed) return;
    const tallyNum = Number(selectedTally);
    const tally = parsed.tallies[tallyNum];
    if (!tally) return;
    let csv = "Energy (MeV),Flux,Error\n";
    for (const row of tally.rows) {
      csv += `${row.energy},${row.flux},${row.error}\n`;
    }
    const total = tally.total;
    csv += `total,${total.flux},${total.error}\n`;
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `tally_${selectedTally}.csv`;
    a.click();
  };

  return (
    <>
      <input ref={fileInputRef} type="file" accept=".outp,.o,.out" style={{ display: "none" }} onChange={handleFileSelect} />
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>输出文件</span>
          <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
            <button className="btn btn-ghost btn-xs" onClick={() => setDoc({path:"/docs/MCNP6_输出卡结构参考.md",title:"输出卡结构参考"})}>📖</button>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">MCNP 输出文件路径 (.outp/.o/.out)</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input className="form-input" style={{ flex: 1 }}
                value={filePath} readOnly placeholder="选择 MCNP 输出文件..." />
              <button className="btn btn-ghost btn-sm" onClick={handleBrowse}>浏览</button>
              <button className="btn btn-primary btn-sm" onClick={() => {
                if (!filePath) { alert("请先选择输出文件"); return; }
                // 如果文件路径有效，直接解析（通过 fileInput 触发）
                fileInputRef.current?.click();
              }}>解析</button>
            </div>
          </div>
        </div>
      </div>

      <div className="glass-card">
        <div className="card-header">
          <span className="card-title">Tally 结果</span>
          <div style={{ display: "flex", gap: 6 }}>
            <select className="form-select" style={{ height: 28, fontSize: 11, width: 120 }}
              value={selectedTally} onChange={e => setSelectedTally(e.target.value)}>
              {parsed ? Object.keys(parsed.tallies).map(k => (
                <option key={k} value={k}>Tally {k}</option>
              )) : <option>请先解析</option>}
            </select>
            <button className="btn btn-ghost btn-xs" onClick={() => {
              if (!parsed) { alert("请先解析输出文件"); return; }
              const tally = parsed.tallies[Number(selectedTally)];
              if (!tally) return;
              const labels = tally.rows.map(r => r.energy);
              const values = tally.rows.map(r => parseFloat(r.flux));
              alert(`绘图功能 (Tally ${selectedTally}): ${values.length} 个数据点\n建议使用 Excel/Matplotlib 等工具绘图`);
            }}>绘图</button>
            <button className="btn btn-ghost btn-xs" onClick={handleExportCsv}>导出 CSV</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>能量 (MeV)</th><th>通量</th><th>相对误差</th></tr></thead>
            <tbody>
              {parsed && parsed.tallies[Number(selectedTally)] ? parsed.tallies[Number(selectedTally)].rows.concat([parsed.tallies[Number(selectedTally)].total]).map((r, i) => (
                <tr key={i} className={i === parsed.tallies[Number(selectedTally)].rows.length ? "total-row" : ""}>
                  <td>{r.energy}</td><td>{r.flux}</td><td>{r.error}</td>
                </tr>
              )) : (
                <tr><td colSpan={3} style={{ textAlign: "center", color: "var(--text-tertiary)", padding: 20 }}>
                  选择 .outp 文件并点击解析
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
    </>
  );
}
