# 官方算例 SDEF 夹具（`sdef_official`）

> 用途：把「**用官方 mcnp6 输出当裁判**」固化成仓库内的验收闸门。
> 消费方：`tests/integration/test_sdef_official_gate.py`（契约
> `docs/contracts/source-sampling-model.md` §5.1）。

## 三个算例

| deck | 官方输入（`MCNP6\Testing\VALIDATION_SHIELDING\Inputs`） | SDEF 关键写法 |
|---|---|---|
| `photon_kerma` | `photon_kerma.inp` | `sur=1 dir=d3 rad=d2 erg=d1`（RAD = A 型 + SB 偏倚） |
| `fns_config1_neutron_onaxis` | `fns_config1_neutron_onaxis.inp` | `pos=… dir=d1 erg=fdir=d2 rad=d3 vec=0 1 0 sur=16` |
| `lps_water` | `lps_water.inp` | `pos=0 0 0 dir=d100 erg=fdir=d200 rad=d300 vec=-1 0 0 sur=100 tme=d400` |

## 文件（每个算例三件套 + 本说明）

| 文件 | 内容 | 怎么来的 |
|---|---|---|
| `<deck>.sdef` | SDEF 卡（含 5 空格续行）+ 紧随其后的**全部** SI/SP/SB/DS/SC 行（含夹在其中的 `c` 注释行）——**逐字**，不重排、不补默认值 | `tools/extract_sdef_official_expected.py` 从官方 `.inp` 抠 |
| `<deck>.expected.json` | 官方裁判数字：`distributions`（id/var/kind/mean/wmult_range）、`freq`（打印表 170 的 expected 列）、`weight_range` | 同一个脚本从官方 `.out` 抽（**禁手改**） |
| `<deck>.deck.inp` | 能在本程序里跑起来的最小 deck：官方标题 + 只保留 SDEF 需要的几何 + 一个内部栅元 + 一个 `imp=0` 外部栅元 + `mode` + SDEF 卡片块 + `nps 3000` | 本目录手工组（几何**只要**能解析，不与官方算例一致；`sur` 指向的曲面按官方原文核对：`photon_kerma` = `pz 0`、`fns` = `py 232.02`、`lps_water` = `px 0.0`） |

官方 `.out`（`~260KB~470KB`）与官方 `mcnp6.exe` **不入库**；`.expected.json`
的 `_source` / `_notes` 记了出处，随时可以重新对账。

## 重新生成 / 对账

```
python tools\extract_sdef_official_expected.py            # 重新生成三件套里的前两件
python tools\extract_sdef_official_expected.py --check    # 只对账（与 .out 不一致即退出码 1）
```

默认路径（本机）：官方输入
`D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\VALIDATION_SHIELDING\Inputs`、
官方输出 `D:\AItool\.tmp\sdef_audit`；用 `--inp/--out` 换。

## 两个容易踩的坑（官方数据实测，闸门已编码）

1. **DS Q 表挂在 ERG 自己的分布号上**（fns `erg=fdir=d2` ⇒ `DS2`；lps_water
   `erg=fdir=d200` ⇒ `DS200`），**不是**挂在父变量 DIR 的分布号上。
2. 官方 Q 参数表是**降序**写的，且第 i 段的阈值区间对应第 **i+1** 项的子分布号。
   实测：fns 里 μ∈[-0.96593,-0.93969) 抽到的能量全落在 `[14.974,15.015]`
   = **D30** 的 SI，而阈值对里写的是 D35；lps_water 的 DIR 箱同样整体右移一格。
   不按这条查表会得到「20000/20000 全不符」的假红。

## 已知裁判缺口

* `lps_water` 官方 `.out` 用了 `print -10 -30 -110`，**整张源分布表被关掉** ⇒
  该算例的 `distributions[].var` 是脚本从 `.sdef` 卡片块推的（`kind = "from deck"`），
  均值一律 `null`；TME（S5）因此**没有裁判数字**，见闸门里
  `test_s5_tme_has_no_official_referee`。
* fns 的 39 个 erg 子分布里，官方对依赖链复杂者**不算期望值**（打印表 170 整列 0，
  正文写 `prsdft does not yet do expected values …`）⇒ 那些 `freq` 表不能用来判频率。
