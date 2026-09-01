"""
材料库深化 —— 用户材料库持久化与自检（后端）。

职责（后端只负责"文件读写 + 校验 + 导入导出"，内置 55+48 预设仍在
前端代码里，不落盘）：
- 库文件路径：MCNP_MATERIAL_DIR 环境变量 > D:\\MCNP\\material > %APPDATA%\\MCNP\\material > temp
- 库文件：{version, materials: {key: entry}}，entry 带 origin=custom|override
- CRUD（save/list/get/delete）、JSON/CSV import/export
- 校验智能：validate_entry（组成自洽）+ check_zaids_xsdir（反向索引）

约定：库条目为前端 camelCase 字段（mtCard / options / rows），rows 复用
MaterialRow 判别联合（nuclide|raw）。内置与文件合并逻辑在前端完成，
后端只负责文件侧。
"""
import hashlib
import json
import os
import re
import tempfile

from app.generator.validator import _ZAID_RE, _SAB_Z_REQUIRED, _zaid_z
from app.xsdir_db import DB as xsdir_db

# 可测试点：None 时走默认搜索链（env > D:\\MCNP\\material > %APPDATA% > temp）
_custom_dir: str | None = None

# 材料级密度正则（与 validator 校验栅元密度一致）
_DENSITY_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


# ── 路径 ──
def _ensure_writable(dirpath: str) -> None:
    os.makedirs(dirpath, exist_ok=True)
    probe = os.path.join(dirpath, ".mcnp_material_probe")
    with open(probe, "w", encoding="utf-8"):
        pass
    os.remove(probe)


def material_dir() -> str:
    if _custom_dir:
        return _custom_dir
    env = os.environ.get("MCNP_MATERIAL_DIR")
    if env:
        return env
    if os.path.exists("D:\\"):
        try:
            _ensure_writable(r"D:\MCNP\material")
            return r"D:\MCNP\material"
        except OSError:
            pass
    appdata = os.environ.get("APPDATA")
    fallback = os.path.join(appdata, "MCNP", "material") if appdata else ""
    if fallback:
        try:
            _ensure_writable(fallback)
            return fallback
        except OSError:
            pass
    last = os.path.join(tempfile.gettempdir(), "MCNP", "material")
    _ensure_writable(last)
    return last


def library_path() -> str:
    return os.path.join(material_dir(), "material_library.json")


# ── 读写（原子写、防半写、损坏备份重置） ──
def _read_library() -> dict:
    path = library_path()
    if not os.path.isfile(path):
        return {"version": 1, "materials": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        try:
            os.replace(path, path + ".bak")
        except OSError:
            pass
        return {"version": 1, "materials": {}}
    if not isinstance(data, dict) or not isinstance(data.get("materials"), dict):
        return {"version": 1, "materials": {}}
    return data


def _write_library(data: dict) -> None:
    path = library_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ── 条目归一化 ──
def _gen_key(name: str) -> str:
    if not name:
        return "m_" + hashlib.md5(str(id(name)).encode()).hexdigest()[:8]
    slug = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    if slug:
        return slug
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return "m_" + digest


def normalize_entry(entry: dict) -> dict:
    e = dict(entry or {})
    e["key"] = str(e.get("key", "")).strip() or (_gen_key(str(e.get("name", ""))))
    for fld in ("name", "category", "formula", "desc", "density", "options", "mtCard"):
        e.setdefault(fld, "")
    e.setdefault("origin", "custom")
    rows = e.get("rows") or []
    norm = []
    for r in rows:
        if isinstance(r, dict) and r.get("kind") == "raw":
            norm.append({"kind": "raw", "text": str(r.get("text", ""))})
        else:
            norm.append({"kind": "nuclide",
                         "zaid": str(r.get("zaid", "")),
                         "fraction": str(r.get("fraction", ""))})
    e["rows"] = norm
    return e


# ── CRUD ──
def list_materials() -> dict:
    return dict(_read_library().get("materials", {}))


def get_material(key: str) -> dict | None:
    return _read_library().get("materials", {}).get(key)


def save_material(entry: dict) -> dict:
    e = normalize_entry(entry)
    data = _read_library()
    data["materials"][e["key"]] = e
    _write_library(data)
    return e


def delete_material(key: str) -> bool:
    data = _read_library()
    if key in data["materials"]:
        del data["materials"][key]
        _write_library(data)
        return True
    return False


# ── 校验智能 ──
def validate_entry(entry: dict) -> list[str]:
    """组成自洽校验。返回错误信息列表（空 = 通过）。"""
    e = normalize_entry(entry)
    errs: list[str] = []
    rows = [r for r in e["rows"] if r["kind"] == "nuclide"]
    formula = e.get("formula", "").strip()
    if not rows and not formula:
        errs.append("材料缺少数组成：既无核素行也无化学式")
    signs: set[str] = set()
    for i, r in enumerate(rows):
        zaid = r["zaid"].strip()
        frac = r["fraction"].strip()
        if not zaid and not frac:
            continue
        if not zaid or not frac:
            errs.append(f"核素行 {i + 1}：ZAID 和份额不能为空")
            continue
        if not _ZAID_RE.match(zaid):
            errs.append(f"核素行 {i + 1}：ZAID '{zaid}' 格式不正确"
                        "（应为 ZZZAAA 或 ZZZAAA.NNx，如 92235.80c）")
        try:
            fv = float(frac)
            if fv < 0:
                signs.add("-")
            elif fv > 0:
                signs.add("+")
        except ValueError:
            errs.append(f"核素行 {i + 1}：份额 '{frac}' 格式不正确（应为数字）")
    if len(signs) == 2:
        errs.append("份额正负号混用（正=原子份额，负=质量份额），请保持一致")
    d = e.get("density", "").strip()
    if d and not _DENSITY_RE.match(d):
        errs.append("密度格式不正确（应为数字，如 -1.0）")
    mt = e.get("mtCard", "").strip()
    if mt:
        present_z: set[int] = set()
        for r in rows:
            z = _zaid_z(r["zaid"].strip())
            if z is not None:
                present_z.add(z)
        for tok in mt.split():
            sab = re.sub(r"\d+$", "", tok.lower().split(".")[0])
            z_req = _SAB_Z_REQUIRED.get(sab)
            if z_req is not None and z_req not in present_z:
                errs.append(f"S(α,β) 表 {tok} 需要 Z={z_req} 核素，但材料中不存在")
    return errs


def check_zaids_xsdir(entry: dict) -> list[dict]:
    """xsdir 反向索引：核素缺库 / 后缀不匹配预警。xsdir 未加载返回 []。"""
    e = normalize_entry(entry)
    if not getattr(xsdir_db, "loaded", False):
        return []
    issues: list[dict] = []
    keys = list(xsdir_db.zaids.keys())
    for r in e["rows"]:
        if r["kind"] != "nuclide":
            continue
        z = r["zaid"].strip()
        if not z:
            continue
        base = z.split(".")[0]
        has_base = any(k.lower().startswith(base.lower() + ".") for k in keys)
        if not has_base:
            issues.append({"type": "missing", "zaid": z})
            continue
        if "." in z:
            suffix = z.split(".", 1)[1]
            exact = base + "." + suffix
            if any(k.lower() == exact.lower() for k in keys):
                continue
            available = [k for k in keys if k.lower().startswith(base.lower() + ".")]
            issues.append({"type": "suffix", "zaid": z, "available": available})
    return issues


# ── 导入导出 ──
def parse_import(text: str, fmt: str) -> list[dict]:
    if fmt == "json":
        return _parse_json(text)
    if fmt == "csv":
        return _parse_csv(text)
    raise ValueError("不支持的导入格式: " + str(fmt))


def _parse_json(text: str) -> list[dict]:
    data = json.loads(text)
    if isinstance(data, dict):
        if "materials" in data:
            raw = data["materials"]
            if isinstance(raw, dict):
                return [normalize_entry(v) for v in raw.values()]
            return [normalize_entry(x) for x in raw]
        return [normalize_entry(data)]
    if isinstance(data, list):
        return [normalize_entry(x) for x in data]
    raise ValueError("JSON 格式不正确")


def _parse_csv(text: str) -> list[dict]:
    import csv
    import io
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 缺少表头")
    groups: dict[str, dict] = {}
    order: list[str] = []
    for row in reader:
        key = (row.get("key") or "").strip()
        name = (row.get("name") or "").strip()
        identity = key or name
        if not identity:
            continue
        if identity not in groups:
            groups[identity] = {
                "key": key, "name": name, "category": "", "formula": "",
                "desc": "", "density": "", "options": "", "mtCard": "",
                "rows": [], "origin": "custom",
            }
            order.append(identity)
        g = groups[identity]
        # 标量字段取首个非空（不改写已填）
        for fld in ("name", "category", "formula", "desc", "density", "options", "mtCard"):
            v = (row.get(fld) or "").strip()
            if v:
                g[fld] = v
        zaid = (row.get("zaid") or "").strip()
        frac = (row.get("fraction") or "").strip()
        if zaid or frac:
            g["rows"].append({"kind": "nuclide", "zaid": zaid, "fraction": frac})
    return [normalize_entry(groups[identity]) for identity in order]


def export_json(entries: list[dict]) -> str:
    mats = {normalize_entry(e)["key"]: normalize_entry(e) for e in entries}
    return json.dumps({"version": 1, "materials": mats}, ensure_ascii=False, indent=2)


def export_csv(entries: list[dict]) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["key", "name", "category", "formula", "desc", "density",
                "options", "mtCard", "zaid", "fraction"])
    for e in entries:
        ne = normalize_entry(e)
        rows = ne["rows"] or [{"kind": "nuclide", "zaid": "", "fraction": ""}]
        for r in rows:
            if r["kind"] != "nuclide":
                continue  # raw 条件行不进 CSV（CSV 为便捷格式）
            w.writerow([ne["key"], ne["name"], ne["category"], ne["formula"],
                        ne["desc"], ne["density"], ne["options"], ne["mtCard"],
                        r["zaid"], r["fraction"]])
    return buf.getvalue()


def _dedupe_key(key: str, existing: set[str]) -> str:
    base = key
    i = 2
    while key in existing:
        key = f"{base}_{i}"
        i += 1
    return key


def _row_key(r: dict):
    """把一行 MaterialRow 归一化为可比较 key（含 raw 条件行）。"""
    if r.get("kind") == "raw":
        return ("raw", r.get("text", ""))
    return ("nuclide", r.get("zaid", ""), r.get("fraction", ""))


def _same_material(a: dict, b: dict) -> bool:
    """判断两个材料条目是否「内容完全一致」（名称/化学式/密度/其他/MT卡 + 核素组成）。"""
    for f in ("name", "formula", "density", "options", "mtCard"):
        if (a.get(f) or "") != (b.get(f) or ""):
            return False
    return sorted(_row_key(r) for r in a["rows"]) == sorted(_row_key(r) for r in b["rows"])


def _index_entries(entries: list[dict] | dict | None) -> dict:
    """已有库条目 → {key: entry}（用于内容比对）。支持 list 或 dict。"""
    if not entries:
        return {}
    if isinstance(entries, dict):
        return {k: normalize_entry(v) for k, v in entries.items()}
    return {normalize_entry(e)["key"]: normalize_entry(e) for e in entries}


def _has_identical(ne: dict, existing_map: dict) -> bool:
    for _, ex in existing_map.items():
        if _same_material(ne, ex):
            return True
    return False


def apply_import(entries: list[dict], conflict: str = "skip",
                 existing_keys: list[str] | None = None,
                 existing_entries: list[dict] | dict | None = None,
                 dry_run: bool = False) -> dict:
    """按冲突策略合并 entries 进库（dry_run=True 只返回计划不写库）。

    existing_entries 提供时：材料与已有条目「内容完全一致」→ 自动跳过（identical），
    不再走同名冲突三选；同名但内容不同才按 conflict 处理。
    未提供 existing_entries 时退化为只看 existing_keys（无内容去重，向后兼容）。
    """
    existing = set(existing_keys or [])
    existing_map = _index_entries(existing_entries)
    imported: list[str] = []
    skipped: list[str] = []
    overwritten: list[str] = []
    renamed: list[str] = []
    identical: list[str] = []
    plan: list[tuple[str, dict]] = []
    for e in entries:
        ne = normalize_entry(e)
        key = ne["key"]
        # 内容完全一致 → 自动跳过（无论是否同名）
        if existing_map and _has_identical(ne, existing_map):
            identical.append(key)
            plan.append(("skip", ne))
            continue
        if key in existing:
            if conflict == "skip":
                skipped.append(key)
                plan.append(("skip", ne))
            elif conflict == "overwrite":
                overwritten.append(key)
                plan.append(("write", ne))
            elif conflict == "rename":
                new_key = _dedupe_key(key, existing)
                ne["key"] = new_key
                renamed.append(key)
                plan.append(("write", ne))
                existing.add(new_key)
            else:
                raise ValueError("未知冲突策略: " + str(conflict))
        else:
            imported.append(key)
            plan.append(("write", ne))
            existing.add(key)
    if not dry_run:
        data = _read_library()
        for action, ne in plan:
            if action == "write":
                data["materials"][ne["key"]] = ne
        _write_library(data)
    return {"imported": imported, "skipped": skipped, "overwritten": overwritten,
            "renamed": renamed, "identical": identical, "dry_run": bool(dry_run)}
