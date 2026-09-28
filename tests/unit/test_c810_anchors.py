"""C810 语义锚点机检：`docs/authority/c810-sdef.md` ↔ `C810.pdf` ↔ 实现引用。

这套断言是「不许凭记忆转述手册」的闸门。背景事故：SDEF 的语义被口述成三种解释
（RHP 的 ``r``）、``fdir=d2`` 静默取默认值、注释卡被当家族终止符 —— 根因都是**没有可机检的
原文出处**。本文件把三件事钉死：

1. **md 内部一致性**：21 个冻结的锚点 id 每个都在，且都有页码行、原文块、关键短语列表。
2. **实现引用闭合**：``app/generator/source_spec.py`` 与契约里出现的每个 ``#C810-…`` id
   都必须在 md 的锚点表里（引不存在的锚点 ⇒ 红）。
3. **PDF 一致性**（有 ``C810.pdf`` 才算，缺文件就 skip）：从 PDF 重抽一遍，逐条核对
   「页码行上的印刷页号 == PDF 页 − 525」与「原文里确实含该锚点的每条关键短语」。

比较口径：PDF 抽出来的连字（``ﬁ``）、软连字符、``−``(U+2212)、引号都归一成 ASCII，短语按
**词序**匹配（空白折叠）—— 版面折行不该造成假阴性；连字符保留（``columns 1-5`` 的 ``-``
是实义标点，抹掉会与 ``15`` 混同）。
"""
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

# ── 路径 ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
ANCHOR_MD = REPO_ROOT / "docs" / "authority" / "c810-sdef.md"
CONTRACT_MD = REPO_ROOT / "docs" / "contracts" / "source-sampling-model.md"
SOURCE_SPEC = REPO_ROOT / "app" / "generator" / "source_spec.py"
EXTRACTOR = REPO_ROOT / "tools" / "c810_extract.py"
C810_PDF = Path(r"D:\MCNP\MCNP6\C810.pdf")

#: PDF 页 − 525 = 印刷页 3-x（页码就印在页面上）。
PDF_TO_PRINTED_OFFSET = 525

#: 冻结的锚点 id（与 `app/generator/source_spec.py::ANCHOR_IDS` 对齐）。
EXPECTED_ANCHOR_IDS = (
    "#C810-3-4-COMMENTS",
    "#C810-3-4-CONTINUATION",
    "#C810-3-30-TR-CARD",
    "#C810-3-31-TR-B-MATRIX",
    "#C810-3-60-CEL-PATH",
    "#C810-3-55-VAR-FORMS",
    "#C810-3-55-SAMPLING-ORDER",
    "#C810-3-55-ONE-LEVEL",
    "#C810-3-56-TABLE-3-3",
    "#C810-3-63-SI-OPTIONS",
    "#C810-3-63-SP-OPTIONS",
    "#C810-3-63-H-FIRST-ZERO",
    "#C810-3-64-BUILTIN-FORM",
    "#C810-3-64-SB-RULES",
    "#C810-3-64-SI-S",
    "#C810-3-64-SP-V",
    "#C810-3-65-TABLE-3-4",
    "#C810-3-66-BUILTIN-VARS",
    "#C810-3-66-TRUNC-WEIGHT",
    "#C810-3-66-SPECIAL-DEFAULTS",
    "#C810-3-66-DS-CARD",
)

#: 引用形状：`#C810-<印刷页>-<TAG>`。
ANCHOR_REF_RE = re.compile(r"#C810-[0-9]+-[0-9]+-[A-Z0-9-]+")


# ── 归一化与短语匹配（与 tools/c810_extract.py 同口径，这里独立实现一遍）─────

_CHAR_FIXES = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
    "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
    "\u00ad": "",
    "\u2212": "-", "\u2010": "-", "\u2011": "-", "\u2012": "-",
    "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u00a0": " ", "\u2007": " ", "\u202f": " ",
    "\u200b": "", "\ufeff": "",
}


#: 页眉页脚行（逐页重复的版式噪声）。跨页句子里夹进这些行会让短语匹配假阴性 —— 它们不是正文。
_PAGE_CHROME_RE = re.compile(
    r"^\s*(?:"
    r"\d+/\d+/\d+"                                    # 版式日期 10/3/05
    r"|EXPORT CONTROLLED INFORMATION"
    r"|CHAPTER 3 - DESCRIPTION OF MCNP INPUT"
    r"|Source Specification"
    r"|3-\d+"                                          # 印刷页码
    r")\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_page_chrome(page_text: str) -> str:
    """去掉页眉页脚行 —— 跨页句子拼起来时才不会夹进「3-64 10/3/05 CHAPTER 3 …」。"""
    return _PAGE_CHROME_RE.sub("", str(page_text or ""))


def normalize(text: str) -> str:
    """PDF 抽取文本 → 统一形态（排版字符归 ASCII + 空白折叠）。"""
    text = "".join(ch for ch in str(text or "") if ch >= " " or ch in "\n\t")
    text = unicodedata.normalize("NFC", text)
    for src, dst in _CHAR_FIXES.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip().lower()


def has_phrase(haystack: str, phrase: str) -> bool:
    """短语按**词序**匹配（空白变体不算差异）；连字符保留。"""
    tokens = [re.escape(tok) for tok in str(phrase or "").split()]
    if not tokens:
        return False
    return re.search(r"\s+".join(tokens), haystack, re.IGNORECASE) is not None


# ── md 解析 ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def md_text() -> str:
    assert ANCHOR_MD.exists(), f"锚点表不存在：{ANCHOR_MD}（先跑 python tools/c810_extract.py）"
    return ANCHOR_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def anchors(md_text: str) -> dict:
    """把 md 解析成 ``{id: {"source": str, "text": str, "phrases": [str]}}``。"""
    parsed: dict[str, dict] = {}
    blocks = re.split(r"(?m)^## ", md_text)[1:]
    for block in blocks:
        lines = block.split("\n")
        anchor_id = lines[0].strip()
        source = next((ln.strip() for ln in lines if ln.startswith("来源：")), "")
        text_match = re.search(r"```text\n(.*?)\n```", block, re.DOTALL)
        body = text_match.group(1) if text_match else ""
        phrases: list[str] = []
        in_phrases = False
        for ln in lines:
            if ln.strip().startswith("关键短语"):
                in_phrases = True
                continue
            if in_phrases:
                m = re.match(r"^-\s+`(.*)`\s*$", ln.strip())
                if m:
                    phrases.append(m.group(1))
        parsed[anchor_id] = {"source": source, "text": body, "phrases": phrases}
    return parsed


# ── 1. md 内部一致性 ────────────────────────────────────────────────────────

def test_anchor_md_has_header_warning(md_text: str):
    """文件头必须写明「由脚本生成、勿手改」——否则下一个人会去手改锚点表。"""
    head = md_text[:600]
    assert "tools/c810_extract.py" in head
    assert "勿手改" in head


def test_all_frozen_anchor_ids_present(anchors: dict):
    """21 个冻结 id 全部存在（少一个 ⇒ 有实现的语义没了出处）。"""
    missing = [aid for aid in EXPECTED_ANCHOR_IDS if aid not in anchors]
    assert not missing, f"锚点表缺 id：{missing}"


def test_no_unknown_anchor_sections(anchors: dict):
    """md 里不该冒出清单之外的锚点（防「随手加一条没冻结的锚点」）。"""
    extra = sorted(set(anchors) - set(EXPECTED_ANCHOR_IDS))
    assert not extra, f"锚点表出现未冻结的 id：{extra}"


@pytest.mark.parametrize("anchor_id", EXPECTED_ANCHOR_IDS)
def test_anchor_has_page_source_text_and_phrases(anchor_id: str, anchors: dict):
    """每条锚点：有页码行 + 有原文块 + 有关键短语列表，且页码行与 id 的印刷页自洽。"""
    assert anchor_id in anchors, f"{anchor_id} 不在锚点表里"
    item = anchors[anchor_id]

    assert item["source"], f"{anchor_id} 没有「来源：」页号行"
    m = re.match(r"#C810-(\d+)-(\d+)-", anchor_id)
    assert m, f"{anchor_id} 不符合 #C810-<页>-<序>-<TAG> 形状"
    # id 的「序」段是锚点的**主印张页**：单页锚点直接写在页号行里；跨页锚点（如 TABLE-3-3
    # 印在 3-55~3-56、编号按 3-56 冻结）只要求它落在声明的页区间内。
    assert re.search(r"PDF p\d+(?:-\d+)?", item["source"]), f"{anchor_id} 的来源行没写 PDF 页"
    declared = _pages_in_source(item["source"])
    assert declared, f"{anchor_id} 的页号行解析不出 PDF 页：{item['source']!r}"
    declared_printed = {f"3-{page - PDF_TO_PRINTED_OFFSET}" for page in declared}
    assert f"3-{m.group(2)}" in declared_printed, (
        f"{anchor_id} 的页号行 {item['source']!r} 的印刷页区间({sorted(declared_printed)})"
        f"不包含 id 声称的印刷页 3-{m.group(2)}")

    assert len(item["text"].strip()) >= 20, f"{anchor_id} 的原文块是空的"
    assert item["phrases"], f"{anchor_id} 没有关键短语（锚点就失去了机检意义）"


@pytest.mark.parametrize("anchor_id", EXPECTED_ANCHOR_IDS)
def test_phrases_appear_in_its_own_text(anchor_id: str, anchors: dict):
    """md 自洽性：每条关键短语都必须出现在**该锚点自己**的原文块里。"""
    item = anchors[anchor_id]
    haystack = normalize(item["text"])
    missing = [p for p in item["phrases"] if not has_phrase(haystack, p)]
    assert not missing, f"{anchor_id} 的原文块里找不到关键短语：{missing}"


# ── 2. 实现引用闭合 ─────────────────────────────────────────────────────────

def _refs_in(path: Path) -> set:
    if not path.exists():
        return set()
    return set(ANCHOR_REF_RE.findall(path.read_text(encoding="utf-8")))


def test_source_spec_refs_exist_in_anchor_table(anchors: dict):
    """`source_spec.py` 引用的每个 ``#C810-…`` 都必须在锚点表里。

    `source_spec.py` 还没生成（或还没接锚点）时跳过 —— 这条断言的目标是「引用了就必须存在」，
    不是「必须引用」。
    """
    if not SOURCE_SPEC.exists():
        pytest.skip("app/generator/source_spec.py 尚未生成")
    refs = _refs_in(SOURCE_SPEC)
    if not refs:
        pytest.skip("source_spec.py 里还没有 #C810-… 引用")
    unknown = sorted(refs - set(anchors))
    assert not unknown, f"source_spec.py 引用了锚点表里不存在的 id：{unknown}"


def test_contract_refs_exist_in_anchor_table(anchors: dict):
    """契约文档里如果写了 ``#C810-…``，同样必须存在（契约目前用页码文字，故可能为空）。"""
    refs = _refs_in(CONTRACT_MD)
    unknown = sorted(refs - set(anchors))
    assert not unknown, f"契约引用了锚点表里不存在的 id：{unknown}"


#: 允许「md 里有、但 `app/` + `docs/` 里暂时无人引用」的锚点（**显式白名单**，不许默默放过）。
#: 注释卡/续行卡是第 3 章卡格式的规则：模型层（`source_spec.py`）只管源变量语义，暂不引用；
#: 等解析层落锚点（`app/generator/` 的 SDEF/INP 解析路径）后从白名单里删掉。
#: 当前 21 条都已被 `app/generator/source_spec.py` 引用，故这里为空 —— 留着是给下一条
#: 新锚点一个「必须先写理由才能免检」的位置。
UNREFERENCED_ANCHOR_WHITELIST: dict[str, str] = {}


def _spec_anchor_ids() -> frozenset | None:
    """读 `app.generator.source_spec.ANCHOR_IDS`；拿不到（模块不在/没这个表）返回 None。"""
    if not SOURCE_SPEC.exists():
        return None
    try:
        from app.generator.source_spec import ANCHOR_IDS  # noqa: PLC0415 — 只在需要的用例里 import
    except Exception:  # pragma: no cover - 模块导入失败时按「拿不到」处理，由调用方 skip
        return None
    if not ANCHOR_IDS:
        return None
    return frozenset(ANCHOR_IDS)


def test_anchor_ids_are_pinned_to_the_anchor_table(anchors: dict):
    """**防漂闸门**：`source_spec.ANCHOR_IDS` == md 锚点表的 id 集合（两处写就得钉一次）。

    锚点 id 分两处写（模型层内联 frozenset + md 章节标题）最容易漂；这条用例是防漂的
    唯一闸门。任一侧拿不到（md 没生成 / 模块没这个表）都 ``skip`` 并**说明原因**，
    不写成断言通过 —— 假绿比红灯更危险。
    """
    spec_ids = _spec_anchor_ids()
    if spec_ids is None:
        pytest.skip("拿不到 app.generator.source_spec.ANCHOR_IDS（模块或该表尚未生成）")
    if not anchors:
        pytest.skip("锚点表未生成（docs/authority/c810-sdef.md 解析不到任何锚点 id）")

    md_ids = frozenset(anchors)
    only_in_spec = sorted(spec_ids - md_ids)
    only_in_md = sorted(md_ids - spec_ids)
    assert not only_in_spec, (
        f"source_spec.ANCHOR_IDS 里有锚点表没有的 id（内联集合要跟 md 一起改）：{only_in_spec}")
    assert not only_in_md, (
        f"锚点表里有 source_spec.ANCHOR_IDS 没有的 id（md 加条就得同步内联集合）：{only_in_md}")
    assert spec_ids == set(EXPECTED_ANCHOR_IDS), (
        "source_spec.ANCHOR_IDS 与本文件冻结的 21 条清单不一致；"
        f"多：{sorted(spec_ids - set(EXPECTED_ANCHOR_IDS))}，"
        f"少：{sorted(set(EXPECTED_ANCHOR_IDS) - spec_ids)}")


def test_every_anchor_is_referenced_somewhere(anchors: dict):
    """反向：md 里每条锚点都要被实现或文档引用过一次（或进显式白名单）。

    「锚点存在但没人引用」= 这条语义其实没被任何实现锚定。引用只认 ``app/`` 与 ``docs/``
    里的文件（锚点表自身不算）：测试文件里的 id 摆着不用，不构成「语义被锚定」。
    白名单是给**尚未落锚点**的锚点留的明确位置 —— 必须写理由，不许静默通过。
    """
    if not anchors:
        pytest.skip("锚点表未生成（docs/authority/c810-sdef.md 解析不到任何锚点 id）")

    referenced: set[str] = set()
    for path in _iter_reference_sources():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        referenced |= set(ANCHOR_REF_RE.findall(text))

    unknown_whitelist = sorted(set(UNREFERENCED_ANCHOR_WHITELIST) - set(anchors))
    assert not unknown_whitelist, (
        f"白名单里写了锚点表里不存在的 id（白名单本身漂了）：{unknown_whitelist}")

    unreferenced = [
        aid for aid in anchors
        if aid not in referenced and aid not in UNREFERENCED_ANCHOR_WHITELIST
    ]
    assert not unreferenced, (
        f"这些锚点没有被任何实现/文档引用，也没进白名单：{unreferenced}")


def _iter_reference_sources():
    """「算作引用」的文件：``app/`` 下的实现 + ``docs/`` 下的文档（排除锚点表自身）。"""
    suffixes = {".py", ".md"}
    for base in (REPO_ROOT / "app", REPO_ROOT / "docs"):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            if path == ANCHOR_MD:
                continue  # 锚点表自己不算「被引用」
            yield path


def test_source_spec_anchor_ids_match_anchor_table(anchors: dict):
    """`source_spec.py::ANCHOR_IDS`（内联冻结集合）里的 id 必须都能在锚点表里查到。

    注意方向：只断言「实现引用 ⊆ 锚点表」。反过来（锚点表有、实现暂时没引用）见
    :func:`test_every_anchor_is_referenced_somewhere` 的白名单。
    """
    spec_ids = _spec_anchor_ids()
    if spec_ids is None:
        pytest.skip("拿不到 app.generator.source_spec.ANCHOR_IDS（模块或该表尚未生成）")
    missing_in_md = sorted(spec_ids - set(anchors))
    assert not missing_in_md, f"ANCHOR_IDS 里有锚点表没有的 id：{missing_in_md}"


# ── 3. PDF 一致性（有 C810.pdf 才算）────────────────────────────────────────

def _pdf_or_skip():
    """返回 ``fitz`` 模块；PDF 或 PyMuPDF 不可用就 skip（别人机器上没有那份手册）。"""
    if not C810_PDF.exists():
        pytest.skip("无 C810.pdf")
    return pytest.importorskip("fitz", reason="无 PyMuPDF（import fitz）")


def test_extractor_check_mode_is_green(anchors: dict):
    """`python tools/c810_extract.py --check` 必须零退出：md 与 PDF 现算内容逐字一致。"""
    _pdf_or_skip()
    proc = subprocess.run(
        [sys.executable, str(EXTRACTOR), "--check"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, (
        f"c810_extract.py --check 非零退出（{proc.returncode}）：\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")


def _pages_in_source(source: str) -> list[int]:
    """页号行 → PDF 页列表（``PDF p580-581`` → ``[580, 581]``；单页 → ``[529]``）。"""
    match = re.search(r"PDF p(\d+)(?:-(\d+))?", source)
    if not match:
        return []
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else first
    return list(range(first, last + 1))


def test_pdf_page_numbers_match_printed_pages(anchors: dict):
    """「PDF 页 − 525 = 印刷 3-x」逐页核对：印刷页码必须真的印在该页上。"""
    fitz = _pdf_or_skip()
    doc = fitz.open(str(C810_PDF))
    try:
        checked = 0
        for anchor_id in EXPECTED_ANCHOR_IDS:
            for pdf_page in _pages_in_source(anchors[anchor_id]["source"]):
                label = f"3-{pdf_page - PDF_TO_PRINTED_OFFSET}"
                page_text = normalize(doc[pdf_page - 1].get_text())
                assert has_phrase(page_text, label), (
                    f"{anchor_id} 声称 PDF p{pdf_page} = 印刷 {label}，"
                    f"但该页上找不到页码 {label}")
                checked += 1
        assert checked >= len(EXPECTED_ANCHOR_IDS), "页号核对覆盖不足"
    finally:
        doc.close()


def test_phrases_come_from_the_real_pdf(anchors: dict):
    """**核心断言**：每条关键短语都能在 PDF 的对应页区间里抽到（不是凭记忆写下的）。"""
    fitz = _pdf_or_skip()
    doc = fitz.open(str(C810_PDF))
    try:
        for anchor_id in EXPECTED_ANCHOR_IDS:
            item = anchors[anchor_id]
            pages = _pages_in_source(item["source"])
            assert pages, f"{anchor_id} 的页号行解析不出 PDF 页：{item['source']!r}"
            haystack = normalize(
                "\n".join(strip_page_chrome(doc[i - 1].get_text()) for i in pages))
            missing = [p for p in item["phrases"] if not has_phrase(haystack, p)]
            assert not missing, (
                f"{anchor_id} 在 PDF p{pages[0]}-{pages[-1]} 里找不到关键短语：{missing}")
    finally:
        doc.close()
