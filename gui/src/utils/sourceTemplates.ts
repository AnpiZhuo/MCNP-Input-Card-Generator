/*
 * 源类型模板 — 深度模块（codebase-design）
 * 模板数据驱动向导：加新模板 = 加一条记录，不改渲染逻辑。
 * 对照：源分布卡说明.md 第二节（SDEF 各源写法）。
 */
import type { SourceTemplateType } from "./DeckContext";

/** SDEF 变量元数据（表 3.3 对应说明.md 二） */
export interface SdefFieldMeta {
  key: string;          // sdefFields 键名（sdef_par 等）
  keyword: string;      // MCNP 关键字（PAR/ERG/...）
  label: string;        // 中文名
  placeholder: string;  // 示例
  hint: string;         // 悬停说明
  group: "main" | "extra";
}

export const SDEF_FIELD_META: SdefFieldMeta[] = [
  { key: "sdef_par", keyword: "PAR", label: "粒子类型", placeholder: "1 / D1", hint: "1=中子 2=光子 3=电子 H=质子 A=α S=裂片；可填 Dn 引用分布", group: "main" },
  { key: "sdef_erg", keyword: "ERG", label: "能量 (MeV)", placeholder: "14 / D2", hint: "粒子能量；默认 14 MeV；Dn 引用分布", group: "main" },
  { key: "sdef_pos_x", keyword: "POS X", label: "位置 X", placeholder: "0", hint: "源位置 X 坐标；Dn=分布", group: "main" },
  { key: "sdef_pos_y", keyword: "POS Y", label: "位置 Y", placeholder: "0", hint: "源位置 Y 坐标", group: "main" },
  { key: "sdef_pos_z", keyword: "POS Z", label: "位置 Z", placeholder: "0", hint: "源位置 Z 坐标", group: "main" },
  { key: "sdef_wgt", keyword: "WGT", label: "权重", placeholder: "1", hint: "初始粒子权重；默认 1", group: "main" },
  { key: "sdef_dir", keyword: "DIR", label: "方向", placeholder: "1", hint: "方向余弦；体源默认各向同性，面源默认余弦分布", group: "main" },
  { key: "sdef_tme", keyword: "TME", label: "时间", placeholder: "0", hint: "发射时间 (shakes)；默认 0", group: "main" },
  { key: "sdef_vec", keyword: "VEC", label: "参考矢量", placeholder: "0 0 1", hint: "方向参考矢量 (x y z)；面源=法线", group: "main" },
  { key: "sdef_axs", keyword: "AXS", label: "参考轴", placeholder: "0 0 1", hint: "RAD/EXT 参考轴 (x y z)", group: "extra" },
  { key: "sdef_rad", keyword: "RAD", label: "径向距离", placeholder: "0", hint: "距 AXS 径向距离；>0 体积源", group: "extra" },
  { key: "sdef_ext", keyword: "EXT", label: "轴向距离", placeholder: "0", hint: "沿 AXS 距离或夹角余弦；与 RAD 组合成柱/锥源", group: "extra" },
  { key: "sdef_cel", keyword: "CEL", label: "起始栅元", placeholder: "栅元号", hint: "源所在栅元；指定则体积均匀", group: "extra" },
  { key: "sdef_sur", keyword: "SUR", label: "曲面", placeholder: "曲面号", hint: "曲面源（POS 必须在面上）；0=体积源", group: "extra" },
  { key: "sdef_nrm", keyword: "NRM", label: "法线符号", placeholder: "+1", hint: "曲面法线方向 +1/-1", group: "extra" },
  { key: "sdef_tr", keyword: "TR", label: "变换", placeholder: "编号", hint: "源坐标变换 TRn 编号", group: "extra" },
  { key: "sdef_ccc", keyword: "CCC", label: "Cookie-cutter", placeholder: "栅元号", hint: "裁剪栅元（只在这些栅元内取样）", group: "extra" },
  { key: "sdef_ara", keyword: "ARA", label: "面积", placeholder: "面面积", hint: "平面源面积（点探测器归一化）", group: "extra" },
  { key: "sdef_eff", keyword: "EFF", label: "取样效率阈值", placeholder: "0.01", hint: "源取样效率阈值，默认 0.01（说明书 Table 3.3）", group: "extra" },
  // RATE 非 MCNP 标准 SDEF 变量（说明书 Table 3.3 无），保留兼容旧数据
  { key: "sdef_rate", keyword: "RATE", label: "源强度（非标准）", placeholder: "强度", hint: "源强度（非标准 SDEF 变量，说明书 Table 3.3 无此项）", group: "extra" },
];

/** 各模板显示的字段（对照源分布卡说明.md 二） */
export interface SourceTemplate {
  id: SourceTemplateType;
  name: string;        // 中文名
  icon: string;
  desc: string;        // 说明（给新手看）
  doc: string;         // 对照的说明书小节
  fields: string[];    // SDEF_FIELD_META 的 key（"sdef_*"）；"table" 表示多点源表格
}

export const SOURCE_TEMPLATES: SourceTemplate[] = [
  { id: "point", name: "单点源", icon: "◎", desc: "单点发射，最常用：固定位置+能量", doc: "点源", fields: ["sdef_par", "sdef_erg", "sdef_pos_x", "sdef_pos_y", "sdef_pos_z", "sdef_wgt", "sdef_dir", "sdef_tme"] },
  { id: "multi_point", name: "多点源", icon: "◉", desc: "多个位置点，各自概率（自动生成 SI/SP）", doc: "多个点源", fields: ["table"] },
  { id: "free", name: "高级自由", icon: "⚙", desc: "显示全部变量，专家模式", doc: "SDEF 全部", fields: SDEF_FIELD_META.map(f => f.key) },
];

export function templateById(id: SourceTemplateType): SourceTemplate {
  return SOURCE_TEMPLATES.find(t => t.id === id) || SOURCE_TEMPLATES[SOURCE_TEMPLATES.length - 1];
}

export function fieldsForTemplate(id: SourceTemplateType): SdefFieldMeta[] {
  const t = templateById(id);
  return SDEF_FIELD_META.filter(f => t.fields.includes(f.key));
}

/** 内置函数选择器选项（源分布卡说明.md Table 3.4） */
export interface BuiltinFn { code: string; name: string; desc: string; params: { name: string; hint: string }[] }
export const BUILTIN_FNS: BuiltinFn[] = [
  { code: "-2", name: "Maxwell 裂变谱", desc: "p(E)=C·E^½·exp(−E/a)", params: [{ name: "a", hint: "默认 1.2895" }] },
  { code: "-3", name: "Watt 裂变谱", desc: "p(E)=C·exp(−E/a)·sinh(√(bE))", params: [{ name: "a", hint: "默认 0.965" }, { name: "b", hint: "默认 2.29" }] },
  { code: "-4", name: "高斯聚变谱", desc: "p(E)=C·exp[−((E−b)/a)²]，b=-1=DT", params: [{ name: "a", hint: "宽度" }, { name: "b", hint: "-1=DT" }] },
  { code: "-5", name: "蒸发谱", desc: "p(E)=C·E·exp(−E/a)", params: [{ name: "a", hint: "默认 1.2895" }] },
  { code: "-6", name: "Muir 速度高斯", desc: "速度空间高斯", params: [{ name: "a", hint: "" }, { name: "b", hint: "" }] },
  { code: "-21", name: "幂律", desc: "p(x)=c|x|^a（DIR/RAD/EXT）", params: [{ name: "a", hint: "幂指数" }] },
  { code: "-31", name: "指数偏倚", desc: "p(μ)=c·e^(aμ)（DIR/EXT）", params: [{ name: "a", hint: "指数" }] },
  { code: "-41", name: "高斯分布", desc: "半高宽 a、均值 b（TME/X/Y/Z）", params: [{ name: "a", hint: "半高宽" }, { name: "b", hint: "均值" }] },
];

export function builtinFn(code: string): BuiltinFn | undefined {
  return BUILTIN_FNS.find(f => f.code === code);
}

/** SI 类型选项 */
export const SI_TYPES = [
  { v: "L", n: "离散列表", d: "SI L v1 v2 ...（栅元号/谱线能量等）" },
  { v: "H", n: "直方图", d: "SI H E1 E2 ...（分箱边界，单调递增）" },
  { v: "A", n: "概率密度点", d: "SI A v1 v2 ...（单调递增密度点）" },
  { v: "S", n: "分布编号", d: "SI S n1 n2 ...（先选分布再取样）" },
];

/** SP 类型选项 */
export const SP_TYPES = [
  { v: "D", n: "分箱概率", d: "SP D p1 p2 ...（默认，不需归一化）" },
  { v: "C", n: "累积概率", d: "SP C c1 c2 ..." },
  { v: "V", n: "按体积加权", d: "SP V v1 v2 ...（仅 CEL 体积源）" },
];
