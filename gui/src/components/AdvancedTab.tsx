import React, { useEffect, useState } from "react";
import DocViewer from "./DocViewer";
import { useDeck } from "../utils/DeckContext";

/** PHYS 字段受控输入：id "phys_n-emax" ↔ deck.adv["phys_n_emax"] */
function AdvField({ id, className, placeholder, title }: { id: string; className?: string; placeholder?: string; title?: string }) {
  const { deck, patch } = useDeck();
  const key = id.replace("-", "_");
  const adv: Record<string, any> = deck.adv || {};
  return (
    <input id={id} className={className} value={adv[key] || ""}
      onChange={e => patch({ adv: { ...adv, [key]: e.target.value } })} placeholder={placeholder} title={title} />
  );
}

/** CUT 字段受控输入：id "cut_n-t" ↔ deck.tally["cut_n_t"] */
function CutField({ id, placeholder, style }: { id: string; placeholder?: string; style?: React.CSSProperties }) {
  const { deck, patch } = useDeck();
  const key = id.replace("-", "_");
  const tally: Record<string, any> = deck.tally || {};
  return (
    <input id={id} className="form-input" value={tally[key] || ""}
      onChange={e => patch({ tally: { ...tally, [key]: e.target.value } })} placeholder={placeholder} style={style} />
  );
}

export default function AdvancedTab() {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [xsdirStatus, setXsdirStatus] = useState("检查中...");
  const [xsdirColor, setXsdirColor] = useState("var(--text-tertiary)");
  const { deck, patch } = useDeck();

  useEffect(() => {
    fetch("http://localhost:5001/api/xsdir-check", { method: "POST" })
      .then(r => r.json())
      .then(j => {
        if (j.loaded) {
          setXsdirStatus(`✅ 已加载 ${j.count} 条`);
          setXsdirColor("#2e7d32");
          if (j.path) {
            const el = document.getElementById("xsdir-path") as HTMLInputElement | null;
            if (el && !el.value) el.value = j.path;
          }
        } else {
          setXsdirStatus("⚠ " + (j.error || "未加载"));
          setXsdirColor("#c62828");
        }
      })
      .catch(() => {
        setXsdirStatus("⚠ 后端未连接");
        setXsdirColor("var(--text-tertiary)");
      });
  }, []);

  return (
    <>
      <>
      {/* PHYS:N */}
      <div className="glass-card">

        <div className="card-header"><span className="card-title">PHYS:N 中子物理</span></div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 120 }}>
            <label className="form-label" title="中子能量上限 (MeV)，默认=极大">EMAX (MeV)</label>
            <AdvField id="phys_n-emax" className="form-input" placeholder="上限" title="中子能量上限 (MeV)，默认=极大" />
          </div>
          <div className="form-group" style={{ maxWidth: 120 }}>
            <label className="form-label" title="俘获方式转变能 (MeV)，默认=0.0">EMCNF (MeV)</label>
            <AdvField id="phys_n-emcnf" className="form-input" placeholder="俘获转变" title="俘获方式转变能 (MeV)，默认=0.0" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="未分辨共振概率表：0=打开，1=关闭">IUNR</label>
            <AdvField id="phys_n-iunr" className="form-input" placeholder="0/1" title="未分辨共振概率表：0=打开，1=关闭" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="缓发中子处理：0=常态">DNB</label>
            <AdvField id="phys_n-dnb" className="form-input" placeholder="缓发中子" title="缓发中子处理：0=常态" />
          </div>
          <div className="form-group" style={{ maxWidth: 100 }}>
            <label className="form-label" title="裂变中子谱：0=整数采样，1=高斯">FISNU</label>
            <AdvField id="phys_n-fisnu" className="form-input" placeholder="裂变谱" title="裂变中子谱：0=整数采样，1=高斯" />
          </div>
        </div>

      </div>

      {/* PHYS:P */}
      <div className="glass-card">
        <div className="card-header"><span className="card-title">PHYS:P 光子物理</span></div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 120 }}>
            <label className="form-label" title="详细/简单分界能量 (MeV)，默认=100">EMCPF (MeV)</label>
            <AdvField id="phys_p-emcpf" className="form-input" placeholder="100" title="详细/简单分界能量 (MeV)，默认=100" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=光子产生电子，1=不产生">IDES</label>
            <AdvField id="phys_p-ides" className="form-input" placeholder="0/1" title="0=光子产生电子，1=不产生" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=含相干散射，1=关闭">NOCOH</label>
            <AdvField id="phys_p-nocoh" className="form-input" placeholder="0/1" title="0=含相干散射，1=关闭" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=光核作用打开，-1=关闭">ISPN</label>
            <AdvField id="phys_p-ispn" className="form-input" placeholder="0/-1" title="0=光核作用打开，-1=关闭" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=含Doppler展宽，1=关闭">NODOP</label>
            <AdvField id="phys_p-nodop" className="form-input" placeholder="0/1" title="0=含Doppler展宽，1=关闭" />
          </div>
        </div>
      </div>

      {/* PHYS:E */}
      <div className="glass-card">
        <div className="card-header"><span className="card-title">PHYS:E 电子物理</span></div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 120 }}>
            <label className="form-label" title="电子能量上限 (MeV)，默认=100">EMAX (MeV)</label>
            <AdvField id="phys_e-emax" className="form-input" placeholder="100" title="电子能量上限 (MeV)，默认=100" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=光子产生电子，1=不产生">IDES</label>
            <AdvField id="phys_e-ides" className="form-input" placeholder="0/1" title="0=光子产生电子，1=不产生" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=电子产生光子，1=不产生">IPHOT</label>
            <AdvField id="phys_e-iphoto" className="form-input" placeholder="0/1" title="0=电子产生光子，1=不产生" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=Koch-Motz角分布，1=简单近似">IBAD</label>
            <AdvField id="phys_e-ibad" className="form-input" placeholder="0/1" title="0=Koch-Motz角分布，1=简单近似" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=连续减慢，1=大步长">ISTRG</label>
            <AdvField id="phys_e-istrg" className="form-input" placeholder="0/1" title="0=连续减慢，1=大步长" />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="轫致辐射光子数缩放因子，默认=1">BNUM</label>
            <AdvField id="phys_e-bnum" className="form-input" placeholder="缩放" title="轫致辐射光子数缩放因子，默认=1" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="电子步长缩放因子">XNUM</label>
            <AdvField id="phys_e-xnum" className="form-input" placeholder="步长" title="电子步长缩放因子" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="0=Knock-on产生光子，1=关闭">RNOK</label>
            <AdvField id="phys_e-rnok" className="form-input" placeholder="0/1" title="0=Knock-on产生光子，1=关闭" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="电子能量离散化点数">ENUM</label>
            <AdvField id="phys_e-enum" className="form-input" placeholder="离散点" title="电子能量离散化点数" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="轫致辐射每子步控制">NUMB</label>
            <AdvField id="phys_e-numb" className="form-input" placeholder="子步" title="轫致辐射每子步控制" />
          </div>
        </div>
      </div>

      {/* PHYS:H */}
      <div className="glass-card">
        <div className="card-header"><span className="card-title">PHYS:H 质子物理</span></div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 120 }}>
            <label className="form-label" title="最大能量 (MeV)">emax (MeV)</label>
            <AdvField id="phys_h-emax" className="form-input" placeholder="能量上限" title="最大能量 (MeV)" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="非弹性散射模型">ie</label>
            <AdvField id="phys_h-ie" className="form-input" placeholder="非弹性" title="非弹性散射模型" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="质子产生核反冲">ipr</label>
            <AdvField id="phys_h-ipr" className="form-input" placeholder="核反冲" title="质子产生核反冲" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="气体产生截面">rgas</label>
            <AdvField id="phys_h-rgas" className="form-input" placeholder="气体截面" title="气体产生截面" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="最小能量 (MeV)">emin (MeV)</label>
            <AdvField id="phys_h-emin" className="form-input" placeholder="能量下限" title="最小能量 (MeV)" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="能量截断 (MeV)">ecut (MeV)</label>
            <AdvField id="phys_h-ecut" className="form-input" placeholder="截断" title="能量截断 (MeV)" />
          </div>
        </div>
      </div>

      {/* PHYS:HE */}
      <div className="glass-card">
        <div className="card-header"><span className="card-title">PHYS:HE 重离子物理</span></div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 120 }}>
            <label className="form-label" title="最大能量 (MeV)">emax (MeV)</label>
            <AdvField id="phys_he-emax" className="form-input" placeholder="能量上限" title="最大能量 (MeV)" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="非弹性散射模型">ie</label>
            <AdvField id="phys_he-ie" className="form-input" placeholder="非弹性" title="非弹性散射模型" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="重离子产生核反冲">ipr</label>
            <AdvField id="phys_he-ipr" className="form-input" placeholder="核反冲" title="重离子产生核反冲" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="气体产生截面">rgas</label>
            <AdvField id="phys_he-rgas" className="form-input" placeholder="气体截面" title="气体产生截面" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="最小能量 (MeV)">emin (MeV)</label>
            <AdvField id="phys_he-emin" className="form-input" placeholder="能量下限" title="最小能量 (MeV)" />
          </div>
          <div className="form-group" style={{ maxWidth: 80 }}>
            <label className="form-label" title="能量截断 (MeV)">ecut (MeV)</label>
            <AdvField id="phys_he-ecut" className="form-input" placeholder="截断" title="能量截断 (MeV)" />
          </div>
        </div>
      </div>

      {/* CUT 卡 */}
      <div className="glass-card">
        <div className="card-header"><span className="card-title">CUT 粒子截断</span></div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 8 }}>
          留空 = 使用 MCNP 默认值
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>粒子</th>
                <th>tme 时间截断</th>
                <th>e 能量截断</th>
                <th>wc1 权重比1</th>
                <th>wc2 权重比2</th>
                <th>swtm 群标志</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["CUT:N 中子", "cut_n"],
                ["CUT:P 光子", "cut_p"],
                ["CUT:E 电子", "cut_e"],
                ["CUT:H 质子", "cut_h"],
                ["CUT:HE 重离子", "cut_he"],
                ["CUT:D 氘核", "cut_d"],
                ["CUT:T 氚核", "cut_t"],
                ["CUT:A α粒子", "cut_a"],
              ].map(([label, _k]) => (
                <tr key={_k}>
                  <td style={{ fontWeight: 600, fontSize: 12 }}>{label}</td>
                  {["t", "e", "wc1", "wc2", "swtm"].map((f) => (
                    <td key={f}>
                      <CutField id={`${_k}-${f}`} placeholder="留空" style={{ height: 28, fontSize: 11, width: 90 }} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Other cards */}
      <div className="glass-card">
        <div className="card-header"><span className="card-title" style={{ flexShrink: 0 }}>其他卡片</span>
            <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
              <button className="btn btn-ghost btn-xs" onClick={() => setDoc({path:"/docs/PRINT卡说明.md",title:"PRINT 卡说明"})}>📖 PRINT</button>
            </div></div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">
              额外卡片（每行一张）— KCODE / PRDMP / PTRAC / TOTNU / VOID / DBCN / PERT / SSW 等
            </label>
            <textarea id="adv-other"
              className="form-input"
              value={(deck.adv?.other_cards || "")}
              onChange={e => patch({ adv: { ...(deck.adv || {}), other_cards: e.target.value } })}
              style={{
                minHeight: 100,
                fontFamily: "Consolas,monospace",
                fontSize: 12,
                lineHeight: 1.6,
                resize: "vertical",
              }}
              placeholder={"KCODE  5000  1.0  50  100\nPRDMP  2J  -1\nDBCN  18J  3\nPTRAC  MAX=10000  WRITE=ALL"}
            />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 350 }}>
            <label className="form-label">xsdir 截面库路径</label>
            <input id="xsdir-path" className="form-input" placeholder="D:\\MCNP\\MCNP_DATA\\xsdir" />
          </div>
          <div className="form-group" style={{ maxWidth: 80, justifyContent: "center" }}>
            <label className="form-label">&nbsp;</label>
            <button className="btn btn-ghost btn-sm" onClick={() => { fetch("http://localhost:5001/api/xsdir-check",{method:"POST"}).then(r=>r.json()).then(j=>{alert(j.loaded?"✅ xsdir已加载 "+j.count+" 条":"⚠ "+(j.error||"未加载"))}).catch(()=>alert("需要后端服务支持")) }}>浏览</button>
          </div>
          <div className="form-group" style={{ justifyContent: "center" }}>
            <label className="form-label">&nbsp;</label>
            <span style={{ fontSize: 11, color: xsdirColor }}>{xsdirStatus}</span>
          </div>
        </div>
      </div>
      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
      </>
    </>
  );
}
