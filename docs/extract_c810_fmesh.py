# -*- coding: utf-8 -*-
"""C810.pdf FMESHn 卡格式节 只读抽取脚本（零安装：仅用本机已装 fitz/PyMuPDF）。

用途：供有命令执行能力的环境代跑，抽取 MCNP5 卷 II Ch.3 中 FMESHn 卡格式原文，
回填 docs/qa-report-fmesh-c810.md §5 的"待人工核对清单"。

红线：不 pip install / 不写 PDF / 只读打开。fitz 本机已装（记忆：PyMuPDF 1.28.0，
2026-08-13 tester-pdf 曾全文抽取 1001 页成功）。

用法：
    python docs/extract_c810_fmesh.py [PDF路径]
    默认 PDF 路径 = D:\\MCNP\\MCNP6\\C810.pdf
输出：
    1) 页数自检（预期 1001）
    2) 526-691 页（卷 II Ch.3）所有含 "FMESH" 的页号（含打印页号换算）
    3) 打印页 3-118（PDF 页 643）全文
    4) Table 3.11 区域（PDF 页 686-689）全文
"""
import sys
import os

PDF_DEFAULT = r"D:\MCNP\MCNP6\C810.pdf"
# 卷 II Ch.3：PDF 页 526-691 = 打印页 3-1~3-166；PDF 页 = 打印页 + 525
CH3_START, CH3_END = 526, 691
FMESH_PRINT_PAGE = 118          # 打印页 3-118
FMESH_PDF_PAGE = FMESH_PRINT_PAGE + 525   # 643
TABLE311_START, TABLE311_END = 686, 689   # 打印页 3-161~3-164


def main() -> int:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        print(f"[错误] 本机未找到 fitz/PyMuPDF：{e}", file=sys.stderr)
        print("[提示] 红线禁止 pip install；请由用户确认本机 PDF 库后再跑。", file=sys.stderr)
        return 2

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else PDF_DEFAULT
    if not os.path.exists(pdf_path):
        print(f"[错误] PDF 不存在：{pdf_path}", file=sys.stderr)
        return 2

    try:
        doc = fitz.open(pdf_path)  # 默认只读
    except Exception as e:
        print(f"[错误] 打开 PDF 失败（只读）：{e}", file=sys.stderr)
        return 2

    n = doc.page_count
    print(f"[自检] 页数 = {n}（预期 1001） | fitz = {getattr(fitz, '__version__', '?')}")
    if n != 1001:
        print("[警告] 页数与记忆不符，页号换算（打印页+525）可能失效，请以实际内容定位。")

    # 1) Ch.3 内搜索 FMESH 命中页
    print("\n===== [1] 卷 II Ch.3（PDF 526-691）含 FMESH 的页 =====")
    hits = []
    for pno in range(max(CH3_START, 1), min(CH3_END, n) + 1):
        page = doc.load_page(pno - 1)
        text = page.get_text("text")
        if "FMESH" in text.upper():
            hits.append(pno)
            print(f"PDF 页 {pno} = 打印页 3-{pno - 525}（命中 FMESH）")
    if not hits:
        print("（0 命中 —— 若页数正常，说明该区域文本层可能需 OCR，请人工翻页核对）")

    # 2) 打印页 3-118 全文
    print("\n===== [2] FMESHn 主节：打印页 3-118 = PDF 页 %d 全文 =====" % FMESH_PDF_PAGE)
    if 1 <= FMESH_PDF_PAGE <= n:
        print(doc.load_page(FMESH_PDF_PAGE - 1).get_text("text"))
    else:
        print("（超出页范围）")

    # 3) Table 3.11 区域
    print("\n===== [3] Table 3.11 区域：PDF 页 %d-%d =====" % (TABLE311_START, TABLE311_END))
    for pno in range(TABLE311_START, min(TABLE311_END, n) + 1):
        print(f"\n--- PDF 页 {pno} = 打印页 3-{pno - 525} ---")
        print(doc.load_page(pno - 1).get_text("text"))

    doc.close()
    print("\n[完成] 抽取结束（只读，未写 PDF）。请将 [2] 的 FMESHn 节原文回填核验清单。")
    return 0


if __name__ == "__main__":
    # Windows 控制台 cp936 下保证 UTF-8 输出不崩
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
