import React from "react";

export default function StatusBar() {
  return (
    <footer className="statusbar">
      <div className="statusbar-left">
        <span><span className="status-dot" /> 就绪</span>
        <span>粒子数: 1276 万</span>
        <span>MCNP 6.2</span>
      </div>
      <div className="statusbar-right">
        <span>v1.5.4</span><span>咨询及委托：13789</span>
      </div>
    </footer>
  );
}
