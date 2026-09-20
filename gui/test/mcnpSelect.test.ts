/**
 * 顶栏 MCNP 下拉的纯逻辑单测（`gui/src/utils/mcnpSelect.ts`）。
 *
 * 这里覆盖的都是"界面上一眼看不出来、但一定会犯"的三类错：
 *   1. 旧后端（没有 candidates 字段）→ 下拉渲染成空的，用户以为"没装 MCNP"；
 *   2. `selected` 不在候选里 → `<select value>` 与 option 对不上，浏览器**静默显示第一项**
 *      （界面在骗人：显示的和你以为选中的不是一个）；
 *   3. 同名 exe 装了两份（D:\MCNP5 与 D:\MCNP6 都叫 mcnp6.exe）→ 两个一模一样的 "MCNP6" 无从选。
 */
import { describe, expect, it } from "vitest";
import {
  BROWSE_VALUE, EMPTY_MCNP_STATE, applyMcnpSelection, mcnpOptions, mcnpTooltip,
  normalizeMcnpDetect, optionText, upsertCandidate,
} from "../src/utils/mcnpSelect";
import { classifySidecarFailure } from "../src/utils/backend";

const P5 = "D:\\MCNP5\\bin\\mcnp5.exe";
const P6 = "D:\\MCNP\\MCNP6\\MCNP_CODE\\bin\\mcnp6.exe";

describe("normalizeMcnpDetect", () => {
  it("全量响应：候选、选中、标签一次到位", () => {
    const s = normalizeMcnpDetect({
      status: "ok", found: true, exe: P6, label: "MCNP6", selected: P5,
      candidates: [
        { exe: P6, label: "MCNP6", source: "PATH", xsdir: "D:\\MCNP\\MCNP6\\MCNP_DATA\\xsdir" },
        { exe: P5, label: "MCNP5", source: "常见目录", xsdir: "" },
      ],
    });
    expect(s.candidates).toHaveLength(2);
    expect(s.exe).toBe(P5);      // 尊重后端的 selected
    expect(s.label).toBe("MCNP5");
    expect(s.found).toBe(true);
  });

  it("旧后端（只有 found/exe/label）→ 降级成单候选，而不是空下拉", () => {
    const s = normalizeMcnpDetect({ status: "ok", found: true, exe: P6, label: "MCNP6" });
    expect(s.candidates).toEqual([{ exe: P6, label: "MCNP6", source: "", xsdir: "" }]);
    expect(s.exe).toBe(P6);
  });

  it("selected 不在候选里 ⇒ 退回第一项（否则 select 会静默显示第一项）", () => {
    const s = normalizeMcnpDetect({
      found: true, exe: P6, label: "MCNP6", selected: "D:\\ghost\\mcnp6.exe",
      candidates: [{ exe: P6, label: "MCNP6" }, { exe: P5, label: "MCNP5" }],
    });
    expect(s.exe).toBe(P6);
  });

  it("没检测到 ⇒ 空候选 + MCNP?（下拉仍能用手动指定）", () => {
    const s = normalizeMcnpDetect({ status: "ok", found: false, exe: "", label: "MCNP?", candidates: [] });
    expect(s).toMatchObject({ found: false, exe: "", label: "MCNP?" });
    expect(s.candidates).toEqual([]);
  });

  it("脏数据不炸：candidates 里缺 exe 的项被丢掉", () => {
    const s = normalizeMcnpDetect({
      found: true, exe: P6, label: "MCNP6",
      candidates: [{ label: "MCNP6" }, null, { exe: P6, label: "MCNP6" }],
    });
    expect(s.candidates).toHaveLength(1);
  });
});

describe("optionText：同名多份要能区分", () => {
  it("标签唯一 ⇒ 只显示标签", () => {
    expect(optionText({ exe: P6, label: "MCNP6" }, [{ exe: P6, label: "MCNP6" }])).toBe("MCNP6");
  });

  it("同名两份 ⇒ 带上上层目录", () => {
    const all = [
      { exe: "D:\\MCNP6\\bin\\mcnp6.exe", label: "MCNP6" },
      { exe: "D:\\MCNP\\MCNP6\\MCNP_CODE\\bin\\mcnp6.exe", label: "MCNP6" },
    ];
    const t0 = optionText(all[0], all);
    const t1 = optionText(all[1], all);
    expect(t0).not.toBe(t1);          // 用户必须看得出这是两个不同的
    expect(t0).toContain("MCNP6");
    expect(t1).toContain("MCNP_CODE");
  });
});

describe("mcnpOptions：永远留着“手动指定…”", () => {
  it("有候选时：候选 + 手动指定（收尾）", () => {
    const opts = mcnpOptions({ ...EMPTY_MCNP_STATE, candidates: [
      { exe: P6, label: "MCNP6" }, { exe: P5, label: "MCNP5" },
    ] });
    expect(opts.map(o => o.value)).toEqual([P6, P5, BROWSE_VALUE]);
    expect(opts[2].text).toBe("手动指定 MCNP…");
  });

  it("**零候选时也必须有它**（自动检测不到正是最需要手动指定的时候）", () => {
    const opts = mcnpOptions(EMPTY_MCNP_STATE);
    expect(opts).toHaveLength(1);
    expect(opts[0].value).toBe(BROWSE_VALUE);
    expect(opts[0].text).toContain("未检测到");
  });
});

describe("applyMcnpSelection：exe/label/found 一起改", () => {
  it("换到 MCNP5 时，旁边的标签也要跟着变（不能下拉是 5、标签还是 6）", () => {
    const s0 = normalizeMcnpDetect({
      found: true, exe: P6, label: "MCNP6",
      candidates: [{ exe: P6, label: "MCNP6" }, { exe: P5, label: "MCNP5" }],
    });
    const s1 = applyMcnpSelection(s0, P5, "截面库已切到 X（100 条）");
    expect(s1).toMatchObject({ exe: P5, label: "MCNP5", found: true, note: "截面库已切到 X（100 条）" });
  });

  it("note 不传时保留原值（切换中的中间态不该把上一次的说明抹掉）", () => {
    const s0 = { ...EMPTY_MCNP_STATE, note: "旧说明" };
    expect(applyMcnpSelection(s0, P6).note).toBe("旧说明");
    expect(applyMcnpSelection(s0, P6, "").note).toBe("");
  });
});

describe("upsertCandidate：手动指定的那个并进列表", () => {
  it("同路径替换，不产生重复 option", () => {
    const list = [{ exe: P6, label: "MCNP6" }];
    const got = upsertCandidate(list, { exe: P6, label: "MCNP6", source: "手动指定" });
    expect(got).toHaveLength(1);
    expect(got[0].source).toBe("手动指定");
  });

  it("排序与后端同口径：MCNP6 → MCNP5 → 其它，再按路径", () => {
    const got = upsertCandidate(
      [{ exe: P5, label: "MCNP5" }, { exe: "D:\\x\\myMcnp.exe", label: "MCNP?" }],
      { exe: P6, label: "MCNP6" },
    );
    expect(got.map(c => c.label)).toEqual(["MCNP6", "MCNP5", "MCNP?"]);
  });
});

describe("mcnpTooltip：选错版本/库没切要一眼可查", () => {
  it("带上完整路径、来源与该版本自带 xsdir", () => {
    const s = normalizeMcnpDetect({
      found: true, exe: P6, label: "MCNP6", selected: P6,
      candidates: [{ exe: P6, label: "MCNP6", source: "PATH", xsdir: "D:\\d\\xsdir" }],
    });
    const tip = mcnpTooltip(s);
    expect(tip).toContain(P6);
    expect(tip).toContain("PATH");
    expect(tip).toContain("D:\\d\\xsdir");
  });

  it("一个候选都没有 ⇒ 明确指路（而不是空白 tip）", () => {
    expect(mcnpTooltip(EMPTY_MCNP_STATE)).toContain("手动指定");
  });
});

describe("classifySidecarFailure：把“一闪就没”翻译成原因", () => {
  it("PyInstaller 载入失败 ⇒ 指向 _internal / 杀软，并提示 自检.bat", () => {
    const why = classifySidecarFailure(-1,
      "[PYI-9052:ERROR] Failed to load Python DLL 'D:\\app\\_internal\\python313.dll'.");
    expect(why).toContain("_internal");
    expect(why).toContain("自检.bat");
  });

  it("脚本异常 / 缺模块 ⇒ 指向打包漏模块", () => {
    expect(classifySidecarFailure(1, "Failed to execute script 'mcnp_bridge'"))
      .toContain("模块");
    expect(classifySidecarFailure(1, "ModuleNotFoundError: No module named 'meshtal'"))
      .toContain("模块");
  });

  it("已知 NTSTATUS 退出码（无符号/有符号两种写法都认）", () => {
    expect(classifySidecarFailure(-1073741515, "")).toContain("0xC0000135");
    expect(classifySidecarFailure(3221225781, "")).toContain("0xC0000135");
    expect(classifySidecarFailure(-1073741701, "")).toContain("0xC000007B");
  });

  it("其它退出码 / 无退出码都给一句能读懂的话（不返回空串）", () => {
    expect(classifySidecarFailure(3, "")).toContain("3");
    expect(classifySidecarFailure(null, "").length).toBeGreaterThan(4);
    expect(classifySidecarFailure(undefined, "").length).toBeGreaterThan(4);
  });
});
