# Hybrid SI/SP Distribution Interface — Design Document

> **Status**: Implemented (2026-09-09，按用户拍板落地于 `app/generator/distributions.py`)  
> **Scope**: MCNP SI/SP/SB/DS/SC distribution subsystem  
> **Goal**: Support both raw-MCNP-text editing AND structured UI editing with round-trip fidelity  
>
> **落地调整（相较本设计文档）**：
> - 双态粒度为**整条分布（DistributionGroup，按 Dn 编号）**而非逐卡 cards[]；
> - **导入文件（parse）→ editMode=raw + rawText 逐字保留**（直接形态）；**UI 新建/默认 → structured 规范形态**；
> - JSON schema 仍是 `sdef_distributions` 内数组（条目级），AI/MCP 视为不透明字符串，schema 唯一消费方
>   是 Python `distributions.py`（parse/emit）与前端 `distDual.ts`（形态切换镜像）；
> - 无字母 SI 记 type=""，发射绝不回填 L（MCNP 缺省 H）。
>  

---

## 1. Interface — Types, Invariants, Ordering, Error Modes

### 1.1 Domain Types (Python, `app/models.py`)

```python
# ── Structured-field types (what the UI reads/writes) ──

@dataclass
class SiFields:
    type: Literal["L", "H", "A", "S", "Q", "T", "F", ""]  # "" means untyped (raw "SI n  v1 v2...")
    values: list[str]

@dataclass
class SpFields:
    type: Literal["D", "C", "V", ""]          # "" = discrete probability, no prefix
    values: list[str]
    fn_code: str                               # e.g. "-3", "-31"; empty = no builtin fn
    fn_params: list[str]

@dataclass
class SbFields:
    type: Literal["D", "-21", "-31"]
    values: list[str]

@dataclass
class DsFields:
    type: Literal["H", "L", "S", "T", "Q"]
    param: str                                  # For DS T: ""; for others: the variable name
    distribution_ids: list[str]

@dataclass
class ScFields:
    text: str

# ── Dual-representation card ──

@dataclass
class SispCard:
    """One MCNP distribution card, holding BOTH raw text AND structured fields."""
    kind: Literal["SI", "SP", "SB", "DS", "SC"]
    group_id: int
    raw_text: str                               # Source of truth for round-trip
    structured: SiFields | SpFields | SbFields | DsFields | ScFields | None
    edit_mode: Literal["raw", "structured"] = "raw"
    """Invariant: when edit_mode == "raw", raw_text is authoritative.
       When edit_mode == "structured", structured is authoritative.
       sync() regenerates the non-authoritative side from the authoritative one."""

# ── One distribution group ──

@dataclass
class DistributionGroup:
    """One distribution family: SIn + SPn + SBn + DSn + SCn, by numeric id."""
    id: int
    param_ref: str                              # SDEF variable that references this (e.g. "ERG")
    auto: bool
    cards: list[SispCard]                       # Ordered: SC first, then SI, SP, SB, DS (per MCNP convention)
    raw_text: str | None = None                 # Concatenated original lines (for round-trip)
    """Invariant: raw_text is the concatenation of cards[*].raw_text.
       Invariant: len(cards) == 0 means the group is a placeholder (Dn ref without cards yet).
       Ordering: cards are kept in parse order, which is the MCNP convention."""

# ── Collection ──

@dataclass
class DistributionCollection:
    """Ordered collection of all DistributionGroups, stored as sdef_distributions JSON."""
    groups: list[DistributionGroup]
    """Invariant: groups are ordered by id (ascending), matching MCNP parse order.
       Invariant: no two groups share the same id.
       Error mode: duplicate id → merge or raise (configurable).
       Error mode: unparseable card → structured = None, raw_text preserved, warning logged."""
```

### 1.2 Module Entry Points (the seam — `app/generator/distributions.py`)

```python
# ── Parser side ──
def parse_sisp_lines(lines: list[str]) -> DistributionCollection:
    """Parse raw MCNP SI/SP/SB/DS/SC lines → DistributionCollection.
    
    Each card's raw_text is the original line (stripped, comment-stripped).
    structured is derived from raw_text. edit_mode = "raw" initially.
    Preserves the "L" default bug fix: if no SI type prefix, type = "" not "L".
    """

# ── Generator side ──
def emit_distribution_groups(col: DistributionCollection) -> list[str]:
    """DistributionCollection → MCNP card lines.
    
    For each SispCard:
      - If edit_mode == "raw": emit raw_text verbatim (exact round-trip).
      - If edit_mode == "structured": regenerate from structured fields.
    Returns the list of lines in proper MCNP order.
    """

# ── Sync (core of dual representation) ──
def sync_card(card: SispCard) -> SispCard:
    """Regenerate the non-authoritative side from the authoritative one.
    
    If edit_mode == "raw": parse structured fields from raw_text.
    If edit_mode == "structured": recompute raw_text from structured fields.
    Returns a new SispCard with both sides consistent.
    """

# ── Merge (for SSR surface source path) ──
def merge_distribution_collections(
    base: DistributionCollection, incoming: DistributionCollection
) -> DistributionCollection:
    """Merge incoming groups into base by id. Incoming fields overwrite base fields.
    Used by D-01: SSR surface source SI/SP → structured distribution.
    """

# ── Serialization ──
def collection_to_json(col: DistributionCollection) -> str:
    """Serialize to the JSON string stored in adv.sdef_distributions."""

def collection_from_json(json_str: str) -> DistributionCollection:
    """Deserialize from adv.sdef_distributions JSON string."""
```

### 1.3 Frontend Types (TypeScript, `DeckContext.tsx`)

```typescript
// Structured-field types (extended from current)
export interface SiEntry {
  type: "L" | "H" | "A" | "S" | "Q" | "T" | "F" | "";  // Added "" = untyped
  values: string[];
}
export interface SpEntry {
  type: "D" | "C" | "V" | "";
  values: string[];
  fnCode: string;
  fnParams: string[];
}
export interface SbEntry { type: "D" | "-21" | "-31"; values: string[]; }
export interface DsEntry {
  type: "H" | "L" | "S" | "T" | "Q";
  param: string;
  distributionIds: string[];
}
export interface ScEntry { text: string; }

// Dual-representation card (NEW — replaces flat fields in DistEntry)
export interface SispCard {
  kind: "SI" | "SP" | "SB" | "DS" | "SC";
  groupId: number;
  rawText: string;
  structured: SiEntry | SpEntry | SbEntry | DsEntry | ScEntry | null;
  editMode: "raw" | "structured";
}

// Richer DistEntry
export interface DistEntry {
  id: number;
  paramRef: string;
  auto: boolean;
  cards: SispCard[];              // replaces flat si/sp/sb/ds/sc fields
  rawText: string | null;         // concatenated original lines
}
```

### 1.4 Error Modes

| Error | Handling | User-visible signal |
|-------|----------|-------------------|
| Unparseable SI card | `structured = None`, `edit_mode = "raw"`, `raw_text` preserved | Warning banner + card shown in raw mode only |
| Duplicate group id | On parse: merge (last wins). On edit: reject. | Reject with message "Distribution D{n} already exists" |
| Invalid SP builtin fn code | `structured.fn_code = code`, `structured.fn_params = []`, regenerate preserves fn code | UI shows generic fn input |
| DS T with non-empty param | `structured.param = ""`, `structured.distribution_ids = []` | Warning + auto-correct |
| SB type mismatch | `structured.type = "D"`, values preserved | Warning + auto-correct type to D |
| Empty DistributionCollection | `collection_to_json` returns `""` (empty string, not `"[]"`) | No UI change |
| Card with edit_mode="structured" but missing structured fields | Falls back to regenerating from raw_text; sets edit_mode="raw" | Silent correction |

---

## 2. Usage Examples

### 2.1 Parser: `parse_inp_text` → `parse_sisp_lines`

```python
# Current: core.py lines 1203-1235
# After: calling into the new module

def parse_inp_text(text: str) -> tuple[DeckData, list[str]]:
    # ... existing code ...
    elif first == "SDEF":
        # ... parse SDEF fields ...
        sisp_lines = []
        while i < len(data):
            next_first = data[i].strip().split()[0].upper() if data[i].strip().split() else ""
            if re.match(r'^(SI|SP|SB|DS|SC)\d+', next_first):
                sisp_lines.append(data[i].strip())
                i += 1
            else:
                break
        if sisp_lines:
            result["source_mode"] = "distribution"
            # NEW: single authoritative representation
            from app.generator.distributions import parse_sisp_lines, collection_to_json
            col = parse_sisp_lines(sisp_lines)
            result["sdef_distributions"] = collection_to_json(col)
            # OLD: sdef_raw_text is NO LONGER emitted — dual representation
            # lives inside DistributionCollection. For backward compat, a
            # migration adapter reads old sdef_raw_text → DistributionCollection.
```

### 2.2 Generator: `generate_inp_from_deck` → `emit_distribution_groups`

```python
# Current: inp_generator.py lines 471-497
# After:

def _generate_sdef(adv: AdvancedSettings) -> list[str]:
    # ... SDEF header line ...
    lines = ["  ".join(parts)]
    
    dist_json = (adv.sdef_distributions or "").strip()
    if dist_json:
        from app.generator.distributions import collection_from_json, emit_distribution_groups
        col = collection_from_json(dist_json)
        dist_lines = emit_distribution_groups(col)
        lines.extend(dist_lines)
        # Re-emit multi-source comment banner (still reads SP values)
        lines.extend(_multi_source_comment_reemit(col))
    elif adv.sdef_raw_text:
        # Backward compatibility: old format → parse → emit through new path
        # (This branch can be removed after migration)
        lines.extend(_legacy_raw_text_fallback(adv.sdef_raw_text))
    
    return lines
```

### 2.3 Frontend: Reading and writing distributions

```typescript
// SourceTab.tsx — reading
const distributions = useMemo(() => {
  const raw = adv.sdef_distributions;
  if (!raw) return [];
  const parsed = JSON.parse(raw);
  // parsed is now DistributionCollection.groups — each group has cards[]
  return parsed.groups || [];
}, [adv.sdef_distributions]);

// SourceTab.tsx — writing (structured edit)
const writeDistributions = (list: DistEntry[]) => {
  // When a card is edited via structured fields, set editMode = "structured"
  // The serializer in collection_to_json will regenerate raw_text from structured
  patch({
    adv: {
      ...adv,
      sdef_distributions: serializeDistributions(list),
    },
  });
};

// DistributionEditor.tsx — editing a card
function onSiChange(newSi: SiEntry) {
  const updatedCards = entry.cards.map(c =>
    c.kind === "SI"
      ? { ...c, structured: newSi, editMode: "structured" as const }
      : c
  );
  onChange({ ...entry, cards: updatedCards });
}

// Text mode toggle: switching to raw preserves structured, switching back re-parses
function onRawTextChange(newText: string) {
  const updatedCards = entry.cards.map(c => ({
    ...c,
    rawText: newText,   // simplified; real logic maps each card's portion
    editMode: "raw" as const,
  }));
  onChange({ ...entry, cards: updatedCards, rawText: newText });
}
```

### 2.4 Surface source merge (D-01)

```python
# Current: core.py lines 1308-1318
# After:

elif first.startswith("SI") or first.startswith("SP"):
    result["other_cards"].append(raw_line)
    if result.get("source_mode") == "surface":
        from app.generator.distributions import (
            parse_sisp_lines, collection_from_json, 
            collection_to_json, merge_distribution_collections
        )
        incoming = parse_sisp_lines([line])
        base = collection_from_json(result.get("sdef_distributions", ""))
        merged = merge_distribution_collections(base, incoming)
        result["sdef_distributions"] = collection_to_json(merged)
```

---

## 3. What the Implementation Hides Behind the Seam

The module `app/generator/distributions.py` hides:

| Hidden complexity | Why it's behind the seam | Current scattered location |
|---|---|---|
| MCNP line syntax (SI L/H/A/S, SP D/C/V, builtin fn codes -2/-3/..., DS T/Q, SB -21/-31) | Callers should not need to know card syntax | `_parse_sisp_structured()` (core.py:100-161) |
| Line continuation (`&`), comment stripping (`$`/`C`) | Callers want clean structured data | `normalize_lines()` (lines.py), `strip_comment()` (lines.py) |
| "L" default bug: when SI has no type prefix, type should be `""` not `"L"` | Callers should not need to know this edge case | `_parse_sisp_structured()` line 127 (`typ = "L"`), `_generate_structured_distributions()` line 945 (`(type or "L")`) |
| Builtin function parameter tables | Callers want to just set/read fnCode and fnParams | `sourceTemplates.ts` BUILTIN_FNS (frontend), `_parse_sisp_structured()` line 134-136 |
| Dirty tracking / bidirectional sync logic | Callers should not manage consistency | New (not yet implemented) |
| SB type mapping (-21/-31 → fnCode, D → type) | Callers want uniform access | `_parse_sisp_structured()` lines 141-147, `_generate_structured_distributions()` lines 963-969 |
| DS type-dependent param handling | Callers just need param + distributionIds | `_parse_sisp_structured()` lines 148-157, `_generate_structured_distributions()` lines 971-983 |
| Collection merge (idempotent, by-id) | SSR path needs merge, not rewrite | `_merge_sisp_entry()` core.py:164-184 |
| Multi-source comment re-emit (D1 chain detection) | Callers just call `emit_distribution_groups()` without worrying about re-emit | `_multi_source_comment_reemit()` inp_generator.py:500-525 |
| Serialization format (JSON schema) | Callers interact with typed objects, not JSON strings | `parseDistributions`/`serializeDistributions` in sourceAdv.ts, `_parse_sisp_structured`/`_generate_structured_distributions` in Python |
| Old `sdef_raw_text` backward compatibility | Migration adapter hidden inside `collection_from_json` | `inp_generator.py` lines 478-495 (the raw-text fallback path) |

---

## 4. Dependency Strategy

Following DEEPENING.md categories:

### 4.1 In-process (always deepenable)

| Dependency | Category | Strategy |
|---|---|---|
| SI/SP/SB/DS/SC line parsing | In-process | Pure computation, no I/O. Test directly through `parse_sisp_lines()` → `DistributionCollection` interface. |
| Structured field generation | In-process | Pure computation. Test through `emit_distribution_groups()` → list of lines. |
| Dirty tracking / sync | In-process | Pure in-memory state. Test through `sync_card()`. |
| Multi-source comment re-emit | In-process | Pure computation. Move from `inp_generator.py` into the module. |

### 4.2 Local-substitutable

| Dependency | Category | Strategy |
|---|---|---|
| DeckData model (AdvancedSettings) | Local-substitutable | The module takes `DistributionCollection` (not `AdvancedSettings`). The adapter at the seam (`collection_from_json`/`collection_to_json`) converts between the string-stored field and the typed object. |
| Frontend serialization (JSON) | Local-substitutable | Same JSON format used by both Python and TypeScript. Shared JSON schema is the contract. |

### 4.3 No remote dependencies

This module has NO remote or external-service dependencies. It is pure computation + in-memory state.

### 4.4 Seam diagram

```
┌─────────────────────────────────────────────────────────┐
│  Seam: app/generator/distributions.py                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Interface:                                           │ │
│  │  parse_sisp_lines(lines) → DistributionCollection    │ │
│  │  emit_distribution_groups(col) → lines               │ │
│  │  sync_card(card) → SispCard                          │ │
│  │  merge_distribution_collections(a, b) → col          │ │
│  │  collection_to_json(col) → str                       │ │
│  │  collection_from_json(str) → col                     │ │
│  └─────────────────────────────────────────────────────┘ │
│  Implementation (hidden):                                │
│  · MCNP syntax parsing/regeneration                      │
│  · "L" default bug fix                                   │
│  · Builtin fn table                                      │
│  · Dirty tracking                                        │
│  · Multi-source comment re-emit                          │
│  · Old sdef_raw_text migration                           │
│  · Distribution merge (D-01)                             │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Trade-offs

### Where leverage is high (deep module pays off)

| Use case | Leverage | Why |
|---|---|---|
| Fixing the "L" default bug | **High** | Fix once in `sync_card()`. All callers benefit without changes. Currently the bug is duplicated in 3 places (parser, generator, frontend). |
| Adding new SI type (e.g. "Q" quadrature from MCNP6) | **High** | Add to type union in one place + add to regenerator. TypeScript side mirrors the union. |
| Adding new SP builtin function | **High** | Add to fn table in one file. Both parse and regenerate automatically know about it. |
| Switching between raw-text and structured editing | **High** | The dual-representation with dirty tracking handles this transparently. |
| Upgrading to new MCNP card syntax | **Medium** | Add a new kind to `SispCard` union, add parse/regenerate for it. |
| Testing | **High** | 100% of SI/SP logic tested through one seam. Module is pure computation (in-process deps). |
| SSR surface source path (D-01) | **High** | `merge_distribution_collections` replaces ad-hoc `_merge_sisp_entry` with a principled merge. |

### Where leverage is thin

| Use case | Why thin | Mitigation |
|---|---|---|
| Single SI card with no SP | Full SispCard still created, emit path knows not to emit SP | Already handled — emit only emits cards that exist in the group |
| SCn comment card with no distribution | SCn is already part of the family | Already handled |
| The `auto` flag | UI concept, doesn't affect MCNP output | Keep as metadata; module passes through without interpreting |
| Backward compatibility with `sdef_raw_text` | Migration concern, not permanent | Adapter hidden inside `collection_from_json`; remove after migration |

### Risks

| Risk | Mitigation |
|---|---|
| **Serialization overhead**: raw_text + structured doubles data per card | ~2-5 KB for typical deck; negligible |
| **Consistency drift**: both raw_text and structured edited independently | `edit_mode` flag prevents: only one side authoritative at a time |
| **Frontend migration**: flat `DistEntry.si/sp/sb/ds/sc` → `DistEntry.cards[]` | Add `cards[]` alongside flat fields (dual compatibility), migrate incrementally |

---

## Appendix: Migration Path

1. **Phase 1**: Create `app/generator/distributions.py` with the new module.
   - `parse_sisp_lines()` fixes the "L" bug (type="" instead of "L")
   - `emit_distribution_groups()` uses `edit_mode` to decide source
   - `collection_to_json`/`collection_from_json` handle serialization
   - `merge_distribution_collections` replaces `_merge_sisp_entry`

2. **Phase 2**: Update `core.py` to call `parse_sisp_lines()` + `collection_to_json()`.
   - Remove `sdef_raw_text` emission (begin migration)
   - Keep `sdef_raw_text` reading for backward compat

3. **Phase 3**: Update `inp_generator.py` to call `collection_from_json()` + `emit_distribution_groups()`.
   - Move `_multi_source_comment_reemit` into new module
   - Keep fallback for old `sdef_raw_text` format

4. **Phase 4**: Update frontend types (`DeckContext.tsx`).
   - Add `SispCard` interface and `cards[]` to `DistEntry`
   - Update `DistributionEditor.tsx` to work with `cards[]`
   - Update `serializeDistributions` to emit new format

5. **Phase 5**: Remove backward compatibility adapters.
   - Remove `sdef_raw_text` from models
   - Remove old flat field fallback in `parseDistributions`