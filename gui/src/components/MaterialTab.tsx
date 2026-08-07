import React, { useState, useEffect, useRef } from "react";
import MaterialEditDialog from "./MaterialEditDialog";
import { useDeck, MaterialData } from "../utils/DeckContext";

interface MatTabProps {
  onMaterialAdded?: (matNum: number) => void;
}

export default function MaterialTab({ onMaterialAdded }: MatTabProps) {
  const [mats, setMats] = useState<MaterialData[]>([]);
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [rawMode, setRawMode] = useState(false);
  const [rawText, setRawText] = useState("");
  const { deck, patch } = useDeck();
  const matsRef = useRef(mats);
  matsRef.current = mats;
  // local → deck（仅推不拉）
  useEffect(() => { patch({ materials: mats }); }, [mats]);
  // deck → local（仅外部导入时，避免死循环）
  useEffect(() => {
    if (deck.materials?.length && JSON.stringify(deck.materials) !== JSON.stringify(matsRef.current)) {
      setMats(deck.materials);
    }
  }, [deck.materials]);
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
            <button className={"btn btn-xs " + (rawMode ? "btn-primary" : "btn-ghost")} onClick={() => setRawMode(!rawMode)} style={{whiteSpace:"nowrap"}}>
              {rawMode ? "← 回到表单" : "✎ 文本模式"}
            </button>
            <button className="btn btn-success btn-sm" onClick={addMat}>+ 添加</button>
          </div>
        
        {rawMode ? <textarea className="form-input" value={rawText} onChange={e => {setRawText(e.target.value);patch({rawOverrides:{...deck.rawOverrides,materials:e.target.value}});}} style={{width:"100%",minHeight:200,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="材料卡原始文本..." /> : <div className="table-wrap">
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
                  <td>{m.nuclides?.length || 0}</td>
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
