import React, { useState } from "react";
import MaterialEditDialog from "./MaterialEditDialog";
import MaterialLibraryPanel from "./MaterialLibraryPanel";
import { useDeck, MaterialData } from "../utils/DeckContext";
import { useSectionTextMode } from "../utils/useSectionTextMode";
import { useDeckSynced } from "../utils/useDeckSynced";

interface MatTabProps {
  onMaterialAdded?: (matNum: number) => void;
}

export default function MaterialTab({ onMaterialAdded }: MatTabProps) {
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [showLibrary, setShowLibrary] = useState(false);
  const { deck, patch } = useDeck();
  // 材料列表：deck.materials 单一权威，本地工作副本经共享 hook 推/拉（收敛 ad-hoc 守卫）
  const [mats, setMats] = useDeckSynced<MaterialData[], MaterialData[]>({
    deck, patch, key: "materials",
    fromDeck: (v) => (Array.isArray(v) ? v : []),
    toDeck: (v) => v,
  });

  // 文本↔表单互转（深模块：逻辑在 useSectionTextMode 一处，这里只传回填回调）
  const text = useSectionTextMode("materials", {
    deck,
    patch,
    overrideKey: "materials",
    onBackToForm: (data) => { if (data.materials) setMats(data.materials); },
  });
  const { rawMode, rawText, busy, toggleRawMode } = text;
  const addMat = () => {
    const maxNum = mats.length > 0 ? Math.max(...mats.map((m) => m.number)) : 0;
    const newNum = maxNum + 1;
    const newMats = [...mats, { number: newNum, comment: "新材料", nuclides: [], density: "", options: "", mt_card: "" }];
    setMats(newMats);
    setEditIdx(newMats.length - 1);
    onMaterialAdded?.(newNum);
  };

  const delMat = (idx: number) => {
    if (mats.length <= 1) return;
    setMats(mats.filter((_, i) => i !== idx));
  };

  return (
    <>
      {showLibrary && <MaterialLibraryPanel onClose={() => setShowLibrary(false)} />}
      {editIdx !== null && (
        <MaterialEditDialog
          matNum={String(mats[editIdx].number)}
          name={mats[editIdx].comment}
          nuclides={mats[editIdx].nuclides}
          density={mats[editIdx].density}
          options={mats[editIdx].options}
          mtCard={mats[editIdx].mt_card}
          onSave={(d) => {
            const c = [...mats];
            c[editIdx] = {
              number: c[editIdx].number,
              comment: d.name,
              nuclides: d.nuclides,
              options: d.options,
              mt_card: d.mtCard,
              density: d.density,
            };
            setMats(c);
            setEditIdx(null);
          }}
          onClose={() => setEditIdx(null)}
        />
      )}
      <div className="glass-card">
        
          <div style={{display:"flex",gap:8,marginBottom:8,alignItems:"center"}}>
            <span style={{fontSize:12,fontWeight:600,color:"var(--text-secondary)",flex:1}}>材料定义（密度在栅元卡中设置）</span>
            <button className={"btn btn-xs " + (rawMode ? "btn-primary" : "btn-ghost")} onClick={toggleRawMode} style={{whiteSpace:"nowrap"}} disabled={busy}>
              {busy ? "转换中..." : (rawMode ? "← 回到表单" : "✎ 文本模式")}
            </button>
            <button className="btn btn-success btn-sm" onClick={addMat}>+ 添加</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowLibrary(true)}>📚 材料库</button>
          </div>

        {rawMode ? <textarea className="form-input" value={rawText} onChange={e => patch({rawOverrides:{...deck.rawOverrides,materials:e.target.value}})} style={{width:"100%",minHeight:200,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="材料卡原始文本..." /> : <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>材料号</th>
                <th>注释/名称</th>
                <th>核素数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {mats.map((m, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>M{m.number}</td>
                  <td>{m.comment}</td>
                  <td>{(m.nuclides || []).filter(n => n.kind !== "raw").length}</td>
                  <td>
                    <button className="btn btn-ghost btn-xs" onClick={() => setEditIdx(i)}>✎</button>
                    <button className="btn btn-danger btn-xs" onClick={() => delMat(i)}>×</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>}
      </div>
    </>
  );
}
