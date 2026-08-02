import React from "react";
import BasicSettings from "./BasicSettings";
import SourceTab from "./SourceTab";
import TallyTab from "./TallyTab";
import AdvancedTab from "./AdvancedTab";
import OutputTab from "./OutputTab";
import GeometryTab from "./GeometryTab";
import MaterialTab from "./MaterialTab";

const PLACEHOLDER = () => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "var(--text-tertiary)" }}>
    ??????
  </div>
);

const TAB_MAP: Record<string, React.FC> = {
  basic: BasicSettings,
  geo: GeometryTab,
  mat: MaterialTab,
  src: SourceTab,
  tally: TallyTab,
  adv: AdvancedTab,
  output: OutputTab,
};

interface Props {
  activeTab: string;
  onMaterialAdded?: (matNum: number) => void;
  pendingCellFromMaterial?: number;
}

export default function TabPanels({ activeTab, onMaterialAdded, pendingCellFromMaterial }: Props) {
  const Panel = TAB_MAP[activeTab] || PLACEHOLDER;
  // Pass known callbacks to specific panels
  const panelProps: Record<string, any> = {};
  if (activeTab === "mat") panelProps.onMaterialAdded = onMaterialAdded;
  if (activeTab === "geo") panelProps.pendingCellFromMaterial = pendingCellFromMaterial;
  return (
    <div className="content-area" key={activeTab}>
      <div className="tab-panel">
        <Panel {...panelProps} />
      </div>
    </div>
  );
}
