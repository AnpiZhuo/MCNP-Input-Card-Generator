import React, { useState, useEffect } from "react";
import { marked } from "marked";
import FloatingDialog from "./FloatingDialog";

interface Props {
  path: string;
  title: string;
  onClose: () => void;
}

export default function DocViewer({ path, title, onClose }: Props) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const isMd = path.endsWith(".md");

  useEffect(() => {
    setLoading(true);
    fetch(path)
      .then(r => r.text())
      .then(text => {
        setContent(text);
        setLoading(false);
      })
      .catch(() => {
        setContent("无法加载文档: " + path);
        setLoading(false);
      });
  }, [path]);

  return React.createElement(FloatingDialog, { title, onClose, width: 820, maxHeight: "85vh" },
    loading
      ? "加载中..."
      : React.createElement("div", {
          className: isMd ? "markdown-body" : undefined,
          style: isMd ? { fontSize: 14, lineHeight: 1.7 } : { fontFamily: "Consolas,'Microsoft YaHei',monospace", fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap" },
          dangerouslySetInnerHTML: isMd ? { __html: marked.parse(content) } : undefined,
        }, isMd ? undefined : content),
  );
}
