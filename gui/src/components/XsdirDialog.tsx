import React, { useState } from "react";
import FloatingDialog from "./FloatingDialog";

const MOCK_NUCLIDES = [
  { zaid:"1001.06c", awr:"1.008", lib:"eprdata12", loc:"20368", name:"H-1" },
  { zaid:"1002.06c", awr:"2.014", lib:"eprdata12", loc:"20395", name:"H-2" },
  { zaid:"6012.06c", awr:"12.000", lib:"eprdata12", loc:"20704", name:"C-12" },
  { zaid:"8016.06c", awr:"15.995", lib:"eprdata12", loc:"21130", name:"O-16" },
  { zaid:"92235.06c", awr:"235.043", lib:"eprdata12", loc:"24786", name:"U-235" },
  { zaid:"92238.06c", awr:"238.050", lib:"eprdata12", loc:"24901", name:"U-238" },
  { zaid:"14028.06c", awr:"27.977", lib:"eprdata12", loc:"21564", name:"Si-28" },
  { zaid:"26056.06c", awr:"55.935", lib:"eprdata12", loc:"22091", name:"Fe-56" },
  { zaid:"28058.06c", awr:"57.935", lib:"eprdata12", loc:"22289", name:"Ni-58" },
  { zaid:"5010.06c", awr:"10.013", lib:"eprdata12", loc:"20546", name:"B-10" },
];

interface Props {
  onClose: () => void;
  onSelect?: (zaid: string) => void;
}

export default function XsdirDialog({ onClose, onSelect }: Props) {
  const [search, setSearch] = useState("");
  const filtered = MOCK_NUCLIDES.filter(n => {
    const q = search.toLowerCase();
    return n.zaid.includes(q) || n.name.toLowerCase().includes(q);
  });

  return React.createElement(FloatingDialog, { title: "截面库浏览器", onClose, width: 600, maxHeight: "70vh" },
    React.createElement("div", { style: { padding: "12px 0" } },
      React.createElement("input", {
        style: { width: "100%", height: 34, padding: "0 12px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none" },
        placeholder: "搜索 ZAID 或元素名称...",
        value: search,
        onChange: (e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value),
      }),
    ),
    React.createElement("div", { style: { overflowY: "auto", flex: 1, padding: "0 20px 16px" } },
      React.createElement("div", { className: "table-wrap" },
        React.createElement("table", {},
          React.createElement("thead", {}, React.createElement("tr", {},
            ["ZAID", "AWR", "库", "位置", "名称", "操作"].map(h => React.createElement("th", { key: h }, h))
          )),
          React.createElement("tbody", {},
            filtered.map((n, i) => React.createElement("tr", { key: i },
              React.createElement("td", { style: { fontWeight: 600, color: "var(--text-primary)" } }, n.zaid),
              React.createElement("td", {}, n.awr),
              React.createElement("td", {}, n.lib),
              React.createElement("td", {}, n.loc),
              React.createElement("td", {}, n.name),
              React.createElement("td", {},
                React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => { onSelect?.(n.zaid); onClose(); } }, "选择"),
              ),
            )),
            filtered.length === 0 && React.createElement("tr", {},
              React.createElement("td", { colSpan: 6, style: { textAlign: "center", color: "var(--text-tertiary)", padding: 20 } }, "无匹配结果"),
            ),
          ),
        ),
      ),
    ),
  );
}
