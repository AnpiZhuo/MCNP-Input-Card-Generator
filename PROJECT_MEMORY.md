# 项目记忆文档（AI 速查手册）

> **★ 本批（2026-09-26）三处用户实测 bug + v1.7.7 打包部署 —— 已改 ✅ / 已提交 ✅（`83c5a20`）/ 已打包部署 ✅ · 版本 1.7.7（用户指定）**
> **三条用户原话驱动的修复**（详情见 `## S11` 与 `docs/CHANGELOG.md` 2026-09-26 三条）：
> ① 「计数卡的前缀，`*`号，解析时无法传入，自己点选后，点生成时也没有」—— 引擎侧本来是对的，漏的是**前后端缝**
>    （`_deck_to_frontend_dict`/`_tally_from_dict` 都没带 `fn_prefix`/`number_suffix`；前端 `TallyTab` 更把下拉框做成装饰品）；
> ② 「没自己打空格时解析没有出现空格；换行后第一个字符是#时会解析成#条件，应该判断数字还是字母」—— 判据改成 `#` 后**字母还是数字**，
>    并补 `-14#1` → `-14 #1`（`#` 是几何里唯一"前面必须有空白"的算子，pymcnp 缺空白直接 `TypesError` ⇒ 栅元在 3D 预览里静默消失）；
> ③ 「截面拖动时…卡死在导入时的粉色页面 / 旋转过之后拖动很怪异」—— 拖入导入覆盖层只认"真拖文件"且 leave/drop/end 一律熄；
>    截面旋转中心与平移解耦（拖动位移原为 `(I−S+S·M)Δ`，会偏方向又放大约 1.5×）。
> **门禁**：pytest **1417 passed / 0 failed / 11 skipped**；vitest **104 files / 927 passed**；tsc 两档 0；vite build 0。
> **打包部署（v1.7.7）**：版本 7 个字段齐改；`build:release` 干净工作区必失败 ⇒ 走手册手工顺序；产物 exe 6,622,208 B /
> `python.exe` 32,622,751 B（与 `binaries/` 哈希一致）/ `_internal` 7873 文件 / exe 内 bundle `index-dO5WbQoY.js`；
> 旧交付目录整卷改名备份 `D:\MCNP\_backup_1.7.6_20260926_154504`；部署版冒烟 5001 **2 s** 就绪，`parse-inp` 用户那张
> `#` 折行卡 = 1 栅元 / 54 项 / 含 `#55` / imp 在位 + 回显 `fn_prefix='*'`/`number_suffix='X'`、`generate` 回放 `*F4:N`/`F5X:N`。
> 本包同时带上 **09-23/24 那批未打包的改动（S10：GEOUNED 参数 UI / FreeCAD 自适应切分 / 退化项剔除 / 墓区过滤）**。


> **★ 本批（2026-09-20）源抽样器全量重构（仿 MCNP 模型）+ 官方裁判门禁，已提交 `8a73ea9`/`ce9eb1c`，已打包部署 ✅**
> **起因**：三个官方算例（`MCNP6\Testing\VALIDATION_SHIELDING\Inputs\{photon_kerma, fns_config1_neutron_onaxis, lps_water}.inp`）
> 用**官方 `mcnp6.exe` 输出当裁判**（print table 170 + `the mean of source distribution N is …`），暴露 6 项不符：
> **S1/S2** 数据块里的 C 注释行把 SI/SP/SB/DS 家族扫描截断（photon_kerma 丢 dist2、lps_water 丢 23 个 ⇒ 源演示报
> 「分布 D2/D300 未定义」+ 重新生成会**抹掉这些卡**；C810 p.3-4「Comment cards can be used **anywhere**」）；
> **S3** `erg=fdir=d2` 认不出 ⇒ 每颗恒 14 MeV（C810 p.3-55 `Var Fvar′ Dn` + 依赖必须在父变量之后抽）；
> **S4** `sp3 d -21 1` 被当 D 表 ⇒ RAD 均匀（C810 p.3-63 H 首项必须为 0 + 官方实测 `power law 21 k=1`）；
> **S5** TME 不抽样（登记，不进粒子记录）；**S6** A 型 SI + SB 未做偏倚密度与权重比（C810 p.3-64 SB 规则）。
> **重构**：① 模型层 `app/generator/source_spec.py`（`VAR_SPEC` 22 变量逐条挂锚点、三种形态唯一实现、
> 取消静默兜底）；② 引擎层 `source_sampler.py` 843→1374 行（分层抽样序 + 通用 `resolve` + 权重累乘；
> 删掉 `_num(v,14.0)` 等**全部**静默兜底）；③ 分布层 S6；④ 官方闸门 `tests/integration/test_sdef_official_gate.py`
> （18 例，裁判数字由脚本从 `.out` 抽）。
> **两层防幻觉（本次方法论，已写进契约 §7）**：语义必须挂 **C810 锚点 id**（`docs/authority/c810-sdef.md`
> 由 `tools/c810_extract.py` 脚本抽 PDF 生成、18 锚点 113 关键短语、篡改必红）＋ 行为必须与**官方程序输出**对账。
> 期间抓到 3 个"转述错误"（agent 说 RATE 默认 0 实际 None；agent 把 DS Q 的 off-by-one 当"官方约定"；
> S6 期间"怎么改判据都对不上"实为引擎真 bug：`_sample_A` 段内逆 CDF 误用真密度表）——**外部裁判优先于自洽**。
> **门禁**：pytest **1280 passed / 11 skipped（0 failed/0 xfail/0 xpass）** / vitest **830 passed / 98 files** /
> tsc 两档 0 / vite build 0。
> **部署**：`build:release` **320 s**（期间 `sync-sidecar` 自己逮到 6.2 时效坑：`target/release` 缺
> `app/generator/source_spec.py`、9 个文件大小不符 ⇒ 已自动覆盖）→ 备份 `_backup_1.7.6_20260920_183501`（7875 文件）
> → 部署 `D:\MCNP\MCNP输入卡生成器`（exe 6,611,456 B / python.exe 32,593,200 B / `_internal` **7871** / `自检.bat` 9282 B）。
> **冒烟（部署版真跑）**：后端 **3.35 s** 就绪；官方 photon_kerma 夹具 deck 打 `/api/source-demo-sample` ⇒
> **分布号 [1,2,3]** ✓、ERG {1.1725, 1.33} ✓、**WGT [1.25269e-4, 1169.41]**（下界=理论值、上界 ≤ 硬界 31965.69）✓；
> `xsdir-check` loaded/7925、`mcnp-detect` 2 候选、`自检.bat` → `[RESULT] BACKEND-RUNNING`；收尾无残留进程。
> ⚠️ 打包手册第 4 步的 rust 环境变量**原先写错**：`D:\rust` 下是 `cargo/`+`rustup/` 两个子目录，
> 必须 `RUSTUP_HOME=D:\rust\rustup`、`CARGO_HOME=D:\rust\cargo`（指错即 `rustup could not choose a version of cargo`，
> 已修正手册）。

> **【追加·同日晚】抽样检测（抽真实卡跑 100 颗看是否符合 MCNP 定义）又揪出 7 处，全部修完并二次打包部署**：
> 手段 = 从官方 `MCNP6\Testing\**\Inputs\*.inp`（含 SDEF 的 24 例）+ 仓库 `tests/fixtures` 抽例，
> 走 `parse-inp -> source-demo-sample`，逐项对照卡定义（位置/方向/能量/权重/粒子类型）。战果：
> ① **ARA 报错过严**（官方 6 个 duct 算例全带 `ara=` ⇒ 源演示一个都开不出来；而 ARA 只用于点探测器
> 直接贡献的归一化，与起始状态无关）⇒ 拆出 `_IGNORED_VARS`：**接受 + 记 warnings**；CCC 仍报错（真改位置）；
> ② 裸参数白名单**漏 VEC/AXS** ⇒ `vec 0 1 0` / `axs= 0 1 -1` 整段丢；③ `dir/vec fpos d2` **只吃一个 token**；
> ④ `vec=fpos=d2` 未归一化（归一化清单漏 VEC/AXS）；⑤ `pos=d1 vec fpos d2` 时 **POS 续值把 `vec`/`fpos`
> 吃成自己的第 2/3 分量**（`pos_y='vec'`）；⑥ `par = h`（粒子类型字母）被通用三形态校验判非法；
> ⑦ `vec fpos d2`（三分量变量的**依赖写法**）落到通用 resolve ⇒ 报出**指向错误**的
> 「SP 概率个数（21）与 SI 值个数不匹配（需 63）」⇒ 改为明确点名"三分量依赖写法尚未实现"（登记待办）。
> **教训**：这 7 处全部有真实卡触发，且都是"旧引擎用 `_num(...,0)` 静默吞掉、测试从未覆盖"的写法 ——
> **抽真实卡跑小样本**比再加统计断言更能抓这类缺陷（顺带实证：离散 L 抽样无偏，3×20 万次偏差 ≤0.65σ；
> `lps_water` 的 DS Q 映射按 C810 原文 0/20000 不符、按"偏移一项"解释 59/20000 不符 ⇒ 再次否掉偏移说）。
> 二次部署：`build:release` **178 s** → `_internal` **7871** + `source_spec.py` 在位 → 冒烟 **2.83 s** 就绪、
> 分布号 `[1,2,3]`、`ERG {1.1725,1.33}`、**WGT [1.25269e-4, 9137.9]**（下界=理论值、上界 ≤ 硬界 31965.69）、
> `xsdir-check` 7925、`mcnp-detect` 2 候选、`自检.bat` → `[RESULT] BACKEND-RUNNING`，收尾无残留进程。
>
> 最后更新时间：2026-09-20（**R1 + O6 收官：RHP 的 `r` 语义全仓收敛 + C810 p.3-66 截断权重补偿**
> ——上一批登记的三项「C810 有明文但未做」里 **R1、O6 已清零**，只剩 **L1**（CEL 采样区域仍用自算紧盒）。
> ① **R1（RHP/HEX 的 `r` = 面心矢量）**：grep 出**六个**消费者，原本并存**三种**互不相同的解释 ——
> 前端生成侧按面心 ✓；`voxel_csg.surface_fn`、`_freecad_csg_worker._make_hex_from_params`、
> `gui/src/volume/surfacesAABB.ts::rhpCorners` 把 `r` 当**顶点** ✗；`lattice._rhp_extent` 把面心当**极值点** ✗。
> 于是同一张卡「生成侧 vs 解释侧」差 **30° 朝向 + 13.4% 尺寸**（实测 `rhp 0 0 -4 0 0 8 0 2 0`：后端旧给
> x∈[±1.732]，C810 p.3-21 例题原文「first facet is normal to the y-axis **at y=2**」⇒ 边心距 2、外接半径
> 4/√3 ⇒ x∈[±2.3094]、y∈[±2]）。收敛为**唯一实现** `app/quadric.py::rhp_hex_vertices`（相邻两面求交
> `[1 c; c 1][α;β]=[A;B]`；与手册例题逐位吻合），六处全部改调用它；TS 侧同名规则 + 9/12 项 `rot60` 推断
> （旧 TS 代码读不存在的 `p[9..14]` ⇒ **NaN 盒**）。附带把 `freecad_preview._surface_extent_values`
> 的预览 bound 由虚胖 1.73× 收紧为真值（该处旧行为是"偏保守"而非错几何，故单独说明）。
> ② **O6（内置函数被 SI 截断 + 权重补偿）**：修前 `-2/-3/-4/-5/-6/-41` **完全不读 SI**（照完整谱抽，
> 能量可越出用户窗口）且 WGT 恒 1；现在按 `[I1,I2]` 抽**条件分布**（`-2/-5/-3` 数值逆 CDF、`-4/-41` 精确
> 截断正态、`-6` 折叠正态 `E=v²`）并乘 `P(I1≤x≤I2)`（对未截断密度算，网格与抽样**共用** ⇒ 严格自洽），
> `-21/-31` 按原文豁免；区间口径与 `_range` 同源并夹进函数自然支撑，无交集即**明确报错**。
> ③ **O6b（同源发现，已在契约显式登记）**：表格式 `SB` 偏倚的权重补偿 —— C810 p.3-64「The weight of each
> source particle is adjusted to compensate for the bias」，而 `weight_factor()` **写了零调用者** ⇒ H/L/S
> 三路按 SB 抽样却不补权重（偏倚白做），`_sample_pos_dist`（POS=Dn）更进一步**连 SB 都没读**；现统一走
> `DistributionSampler.sample_with_corrections()`（返回路径上补偿之积，按**抽中的档位**算），`_Context`
> 并进每粒子 WGT。**新登记** **O8**：`SB` 用内置函数时的**函数偏倚**（p.3-66 的"分箱近似 ≤300 段"）仍未实现
> （现按未偏倚抽 + 权重 1 ⇒ 自洽，但不是 MCNP 行为）。
> **测试**：新增 `tests/unit/test_distribution_sampler.py` 12 例（截断区间/解析 P 对账 −5 与 −41/豁免 −21−31/
> 无 SI 不截断/窗口无交集报错/SB 补偿与零真概率）、`tests/unit/test_source_sampler.py` 4 例（含 POS=Dn 的 SB）、
> `tests/integration/test_api_contract.py` 1 例（**真实 HTTP** 端到端截断+WGT）、`tests/unit/test_preview_bound.py`
> 1 例、`gui/test/volume/surfacesAABB.test.ts` 2 例；并把 RHP 的 **xfail 留档转成正例**（删 xfail）。
> 门禁 **pytest 1133 passed** / vitest **830 passed / 98 files** / tsc 两档 0。
> 此前（2026-09-20，**源演示「有时候返回失败」修复 —— 按 CCC-810 原文逐条对照后修 F1–F8**：
> **根因（最小复现）**：`SDEF CEL=n` 的栅元若用**宏体**界定 ⇒ `voxel_csg.cell_aabb` 返回 None
> （`_surface_negative_aabb` 只认 SPH/RPP，其余 8 类宏体无实现）⇒ 旧 `sample_cell` 退回 **±1e3 大盒**做拒绝采样
> ⇒ 接受率 ~1e-8 ⇒ 必报「CEL=n 拒绝采样失败（栅元包围盒可能退化）」；另一条独立病因：GQ/SQ 面源的 `_quadric_pt`
> 把 `gq_aabb()` 的**三元组**解包成 2 个 ⇒ 必抛 `too many values to unpack`。两条都是"**某些卡必失败**"
> （用户感知即"有时候"），且旧报错**指向错处**。
> **按 C810 修的 8 项**：① `voxel_csg._macrobody_aabb` 补全 **C810 p.3-21 的 10 类宏体**紧盒（含 BOX/RPP 某维无限、
> RHP 轴向无限的逐轴有界标志；参数规整复用 `quadric` 的 box/rec/rhp_params，保证"盒与 `surface_fn` 同实心"）；
> ② `sample_cell` 删掉 ±1e3 兜底，改为"算不出盒 / 有无界轴"就明确报错；③ 实现 **EFF 判据**（C810 p.3-59
> `MAX(成功数,10) < EFF×尝试数`，默认 0.01，`sdef_eff` 可覆盖）；④ 失败语义改成 C810 口径（效率过低／无界盒）；
> ⑤ GQ/SQ 面源改为**面上面积均匀**（拉伸回单位球的加权拒绝采样），且只接受**轴平行椭球**（斜置 GQ／双曲面／
> 抛物面按 p.3-58 明确报错并指路）；⑥ 球面面源 + `AXS` 时 **EXT = 夹角余弦**（p.3-58）；⑦ 内置函数↔源变量
> **配对校验**（Table 3.4；−7 spare 显式不支持）；⑧ 曲面行未解析时回传**行号 + 原因**（走既有 geometryWarnings）
> ＋ 前端兜底读 `message`（后端 500 只给 message，旧前端会把它吞成一句"源抽样失败"）。
> **测试**：新增 `tests/unit/test_voxel_csg_macrobody_aabb.py`（36 例：紧盒逐轴比对独立解析期望 + MC 体积 vs 解析
> + 紧度比 ≤5 + 正侧仍无界 + BOX 无限维）、`tests/integration/test_source_demo_matrix.py`（28 例：10 宏体 CEL
> 每颗粒子用**独立解析判据**验在体内、面源允许/禁止类型、面均匀统计检验、EFF 触发与 `sdef_eff` 覆盖、
> 未解析行点名）；并修正一处**既有用例编码了非法配对**的问题（旧 `test_builtin_single_si_ext_is_symmetric`
> 拿 −31 配 RAD，而 Table 3.4 只允许 DIR/EXT）。
> 门禁 **pytest 1118 passed + 1 xfailed** / vitest **828** / tsc 两档 0 / vite build 0；**R1 差分**（HEAD vs 现在，
> 5 张宏体卡打 `/api/preview-3d`）STL **逐字节一致** ⇒ 预览/网格零影响。
> **登记 3 处「C810 有明文但本批未做」**（已写进契约 §4.1/§4.2）：**L1** CEL 采样区域仍用自算紧盒（C810 要求用户给
> 区域，本程序为便利而扩展）；**O6** 内置函数被 SI 截断时的**权重补偿**未实现；**R1** **RHP 的 r 语义**（现行当
> 顶点矢量、C810 说边心距，波及 UI 六棱柱快捷卡与 hex 格阵预览 ⇒ 待裁决，已用 xfail 留档）。
> 另记一条环境坑：shell 里设 `PYTHONIOENCODING=utf-8` 会让 `test_meshtal_worker` 的 spawn 用例
> `subprocess.run(text=True)` 按 GBK 解码崩成 `stdout=None`（本机实测；跑 pytest 前须 unset）。
> 此前（2026-09-20，**MCNP5/6 全量检测 + 顶栏版本下拉 + 用户自助自检，已提交 ✅ / 已打包部署 ✅ · 版本仍 1.7.6**：
> 起因是用户反馈「后端没拉起来、手动点 `python.exe` 一闪就没」。**实测定位**：缺 `_internal` 时进程只活
> **263 ms**、错误只写在 stderr（`Failed to load Python DLL ...\_internal\python313.dll`）⇒ 窗口来不及画字就销毁，
> 肉眼即"空白一闪"；而健康包 **1.9 s** 绑上 5001 并常驻。**关键缺口是"静默"**：后端只由前端 JS 拉起
> （`src-tauri/src/main.rs` 无任何 spawn），失败被 `catch` 吞成一句 `console.warn` ⇒ 用户只看到"后端不可用"四个字。
> **治理三件**：① `自检.bat`（新增，随包落到 exe 同级；在**自身同目录**产出 `MCNP自检报告.txt` —— 合法 UTF-8 无 BOM、
> 含系统版本/三件套体积与 mtime/引导判定/端口/后端自述(mcnp-detect+xsdir-check)/config.json/`[RESULT]` 结论，
> **可直接转发给 AI 读**，避免来回追问；子进程输出按 ANSI 写中文，故报告内先经 PowerShell 转 UTF-8 再落盘；
> 另含 **环境变量**（关键项原样 + 全量，敏感词已滤 —— PATH/DATAPATH 正是判"版本装在哪、MCNP 吃哪套库"的关键），
> 且窗口**不显示任何内容、出报告即自动关闭**（只在报告写不出来时才出声并停住）；
> `[RESULT]` 四态分流：`PKG-INCOMPLETE-OR-BLOCKED` /
> `PKG-INCOMPLETE` / `PACKAGE-OK-BACKEND-NOT-UP` / `BACKEND-RUNNING`，且判据全走 ASCII 标记，
> 不依赖中文能否显示——实测 `PYTHONIOENCODING` 对冻结版**无效**）；② `gui/src/utils/backend.ts` 把拉起失败/秒退的
> **归因 + 退出码 + stderr 尾巴**带到界面（顶栏 ⚠ 详情，秒退后几秒可见，不再等 3 分钟轮询）；
> ③ 打包链路新增 `gui/scripts/stage-selftest.mjs`（`build:app` / `build-release` 收尾各挂一步，缺失即非零退出）
> ＋ 手册第 7 步改「四件套 + README + AI接入.md」。
> **MCNP5/6 全量检测 + 顶栏下拉**（新增 `app/mcnp_locator.py` 深模块、`app/user_config.py`）：改造前
> `_find_mcnp_exe()` 找到第一个就 `return` ⇒ 同时装 MCNP5 与 MCNP6 的用户**永远只看到一个**、版本标签还靠
> "文件名里有 5"猜；现在枚举**全部**候选（PATH／注册表 InstallPath／常见目录，去重 + 稳定排序 MCNP6 在前）、
> **逐候选推断自带 xsdir**（MCNP6 `<root>\MCNP_CODE\bin`、MCNP5 `<root>\bin`+`DATA` 两种真实布局实测支持），
> 新增 `/api/set-mcnp-exe`（选定即按该版本自带 xsdir **重载截面库**——MCNP5/6 的 xsdir 互不通用）与
> `/api/choose-mcnp-exe`（原生窗口手动指定，自动检测不到时的唯一出路）；`/api/mcnp-detect` 加性返回
> `candidates/selected`。**顺带修 3 处真缺陷**：① `freecad_locator.save()` **整份覆盖** config.json
> （再加第二个设置就互抹）⇒ 收敛到 `user_config.py` 读-改-写；② 集成测试会写到开发机**真实** config
> （`backend_proc` 的 `APPDATA` 已隔离到临时目录）；③ TD-34 白名单闸门缺**传递闭包**
> （`_keep_py` 内模块的顶层兄弟 import 未登记 ⇒ 冻结包必 ImportError、dev 永不复现；本批
> `mcnp_locator → user_config` 正是踩中它）。门禁 pytest **1049 passed** / vitest **828 passed / 98 files** /
> tsc 两档 0 / vite build 0；另：**`ded1998` 已单独在临时 worktree 验证 820 passed**。
> **打包部署（同日）**：`build:release` **428 s**（vite 7.5 s / tauri 2 m 34 s / PyInstaller 218 s）→ 部署
> `D:\MCNP\MCNP输入卡生成器`（exe **6,614,528 B** / python.exe **32,523,049 B** / `_internal` **7870** 文件 /
> 含 `自检.bat` 6006 B）；备份 `_backup_1.7.6_20260920_145504`（7875 文件）。
> **冒烟（部署版真跑）**：后端 **2072 ms** 就绪；`/api/mcnp-detect` 回 **2 个候选且各自带出 xsdir**
> （⇒ 冻结包内 `_import_app("mcnp_locator")` 与它 `import user_config` 都通，**TD-02 那条路实证打通**）；
> `xsdir-check` / `diff-inp` 均 ok；`set-mcnp-exe` 错误分支 `status=error/文件不存在` 且不落盘；
> `自检.bat` 得 `PACKAGE-OK-BACKEND-NOT-UP`（未开主程序时应如此）；收尾 5001 释放、无残留进程。
> ⚠️ 本批踩到并修掉一个**我自己引入**的顺序坑：`build-release.mjs` 里 `stage-selftest --check` 曾排在写入
> **之前** ⇒ 干净/首次构建必因"缺失"exit 1 中断整条链路（已改**先写后查** + 单测钉住顺序）。
> 详见 `docs/CHANGELOG.md`）。
> 此前（2026-09-20，**S9 全链已提交 ✅ / 已打包部署 ✅ · 版本仍 1.7.6**：
> **真实 MCNP 结果的 keff 解析**（用户「程序解析不到 keff 序列」，打包版实测 HTTP 500 同文案）：`app/mctal_parser.py`
> 原先只认 **OWEN 简化夹具**（`k eff (c) <mean> <std>` 行 + `combined keff = ...`），**真实 MCNP6 mctal 里这些字段名一个都没有** ——
> KCODE 结果在**文末** `kcode <总周期> <跳过> <每周期值数>` 之后的**裸数值块**（实测 600×19、无字段名，按列定位：
> 1-3 = 逐周期 k(coll/abs/trk)，12/13 = 活跃周期累计平均 ⇒ 最终 combined；mctal/outp **都不逐周期写 σ**）。
> 配套：`app/outp_parser.py:parse_keff_cycles`（`.o` 的 print table 175 周期表）、`app/sweep.py:scan_run_dir` / `history_keff_std`、
> `/api/parse-keff` 接受 mctal / `.o` / 目录；并顺手修掉**同族真 bug**：`sweep-run` 只解析 `proc.stdout`，
> 而 MCNP 的 keff **只写在结果文件里** ⇒ 参数扫描汇总 keff 恒 `n/a`。
> **用户追加需求（同日）**：keff 解析做成**独立玻璃卡 + 两个子按钮**（解析 mctal / 解析 .o，**mctal 默认无后缀**）
> ⇒ 新增 `KeffParseCard.tsx` + `app/file_dialog.py` + `/api/choose-file` 的 `kind`/`withContent`，`KeffDialog` 改结果窗口。
> 门禁 pytest **1019 passed / 0 failed** / vitest **799 passed / 96 files** / tsc 两档 0 / build 0，详见下方 S9）。
> 此前（2026-09-19，**S8 全链已提交 ✅ / 已打包部署 ✅（版本仍 1.7.6）**：
> **出图**：出口一律 PNG + **白底**；轴标按 GB 3100~3102 排"量名称 量符号/单位"；**图题移到图的下方居中**；
> **PNG 写入物理尺寸（pHYs）并按 600/300 dpi 反算倍率**；字号提档到期刊底线；**色表换 viridis（黑白打印可辨）**；
> **出图版面抽成单一权威 `export/figureLayout.ts`**（两个渲染器共用 ⇒ 8 个出图视图一起变）。
> **修的真 bug**：`QuickCellForm` 要 356px 而 3D 侧栏只给 271px ⇒ 输入框被裁；行标签与字段标签错半格；
> `legendMetrics` 的 `*2` 把图例上限写成 480px；图例两列排导致第二列挂在图外空白上；面板尺寸跟着窗口走；
> 长脚注单行画出边界；**截面悬停读数与图形不同源**；**截面矢量图材料边界描边过重（换算方向写反）**；
> **截面右栏横向溢出**（共享控件 274px 塞进 190px）。
> 门禁 vitest **794 passed / 95 files** / pytest **882 passed / 1（既有 GBK）** / tsc 两档 0，详见下方 S8）。
> 此前（2026-09-15，**S7 已提交 ✅ / 未重打包**：格阵编辑器"**改范围就乱序**"——`resizeLatticeCells`
> 按**扁平下标**搬运涂色，范围 -8:8 → -9:9 时格位号整体平移 ⇒ 整张图沿对角线错位；改为按**绝对格位坐标**搬运。
> **纯前端修复，不动后端/sidecar**，无需重打包链路。门禁 vitest **737 passed / 90 files** / tsc 两档 0 / build 0，详见下方 S7）。
> 此前（2026-09-17，**本批 S6 已闭环待打包**：① 计数卡"手动改动变回初始状态"**真根因**修复（回显 deck 同时带 `tally.tallies` 与顶层 `tallies` ⇒ 多轮往返下用户新增/删除计数卡被静默丢弃）；② 8100 端口守卫 + MCP 工作区归属隔离；③ **出图全链**（11 新模块：论文配色合成图 / 矢量 PDF+SVG / 自由平面切面 + 等值线 / 成叠导出 / Tally 独立窗口 / keff 导出）；④ 自审抓到并修掉 9 处真 bug。门禁 pytest **996 passed** / vitest **731 passed / 90 files** / tsc 两档 0 / build 0，详见下方 S6）。
> 此前（2026-09-17，S5.3~S5.6：源分布卡文档按 C810 重写 + 粒子源演示 8 处行为缺陷 + 2 个带外缺陷（`SDEF SUR=` 面源在真实后端全废、`CX/CY/CZ` 三项式被静默丢弃）；S5.4 打包坑 6.2（`tauri build` 不刷新 `python.exe`）**根治为构建命令的一步**；门禁 pytest 982/1（GBK 环境失败）/ vitest 644/82）。此前（2026-09-12，**STEP 导入 500 热修**：`/api/import-step` 手写 `CellRow` 字段映射 ⇒ 每次导入必 HTTP 500；已收敛到单一序列化 seam + 补回归测试 + **仅重打包 sidecar 部署（未升版）**，详见下方 S4）。此前（2026-09-10，**SDEF 源粒子演示可视化（TODO #6）落地**，已提交 `4f0798fa`：后端三深模块（`DistributionSampler` 分布抽样 / `source_sampler` 源编排 / `voxel_csg` 全宏体拆解）+ 端点 `/api/source-demo-sample` + 独立「🎬 演示源」3D 窗口；按 C810.pdf 权威语义**做全不降级**、有错就地报）。此前（2026-09-04，**后端拉起提速 + preview_cache 跨进程持久化**，已提交 commit 0a266cd；此前未提交 3D 功能已一并提交 f7fc2ed）。此前（2026-08-28，**v1.7.4**：3D 预览 MCNP 窗口裁剪修复 + U 分组侧边栏，**追加两项 Bug 修复——① disc STL 键错配（d8b6747，BEAVRS 燃料 pin 方块→真实圆柱）；② z 居中（5fafd1d，燃料棒/围板整体上移 230→位置正确，用户已复验确认），均仅重打包 sidecar 部署**；门禁后端 test_lattice(81)+test_api_contract(17) 绿 / 前端 vitest 527/527 / tsc EXIT 0）。此前（2026-08-27）：v1.7.4 上线（MCNP 窗口裁剪 + U 分组侧边栏，已打包部署 `D:\MCNP\MCNP输入卡生成器`；门禁后端 **85/85**（test_lattice+test_api_contract）/ 前端 vitest **527/527** / tsc EXIT 0）。此前（2026-08-24）：Wave 2a 后端 15 项修复**全绿**：pytest **703/0/0**（基线 686 + 新增 17）——项 2/4/5/9/13/15 + 项 14 剩余 + api.yaml cycle 契约 + R1 五夹具/kitchen_sink R4 不回退 + 契约闸门含 cycle HTTP 用例；详见 docs/backend-changes.md §AA。前端 Wave 2b 并行进行中，golden 已写盘全部可断言无 skip）。此前：格阵 fill 三阶段**最终复验全绿**：pytest **674/0** / vitest **466/0 无 skip** / tsc EXIT 0 / 契约闸门 15/15 / 空 STL 修复生效，用户指定 E2E 17/17 PASS，**建议放行统一提交**，详见 docs/qa-report-final.md —— **按人脑模型重组**（原「顶部横幅 + §8 流水混装」整理为「短期记忆 / 长期记忆」两区，完整流水外置 `docs/CHANGELOG.md`）。同日完成 **GQ/SQ 3D 预览修复 + 渲染后续增强 + OWEN 四项 + 参数扫描前端**：全部门禁绿（pytest **573/0** / vitest **358/0** / tsc EXIT 0）+ PyInstaller sidecar 重打包 + 打包版冒烟通过。
>
> **人脑模型组织说明**：
> - **◉ 短期记忆（工作记忆）**：只放"现在正在处理的事"——当前批次 / 工作区 / 待办。**容量小、变化快、随批次刷新**（人脑工作记忆约 7±2 项）。
> - **◉ 长期记忆（稳定存储）**：固化后不随批次变动的知识——**语义记忆**（是什么/为什么：身份/ADR/规则/目录）、**情景记忆**（发生过什么/经验教训：踩坑/里程碑）、**程序性记忆**（怎么操作：打包/测试手册）。
> - **记忆巩固规则**：批次结束 → 短期记忆区刷新；经验教训**固化**进长期记忆（§5 规则 / §6 踩坑 / §4 ADR）；详细流水**归档**进 `docs/CHANGELOG.md`（+ backend/frontend-changes.md + git log）。
> - **维护者**：项目经理（AgentTeams 记忆维护）。

---

# ◉ 短期记忆（工作记忆）—— 当前活跃上下文

> 只保留"正在处理"的信息。**批次完成后，本区随 CHANGELOG 归档一起刷新。**

## S11（当前批次）计数卡前缀 `*` + 栅元几何 `#` + 截面拖动两坑 + **v1.7.7 发布**（2026-09-26，**已改 ✅ / 已提交 ✅ `83c5a20` / 已打包部署 ✅ · 版本 1.7.7（用户指定）**）

> **三态**：**已改 ✅ / 已提交 ✅ / 已打包部署 ✅**（手工链：vite → PyInstaller 229 s → binaries → `npm run build:app`；
> 部署 `D:\MCNP\MCNP输入卡生成器`，7873 文件 / 214,820,150 B）。
> 详细流水：`docs/CHANGELOG.md` 2026-09-26 三条（两条修复 + 一条发布）。
> 门禁：pytest **1417 passed / 0 failed / 11 skipped**；vitest **104 files / 927 passed**；tsc 两档 0；vite build 0。

三条都是**用户实测**驱动，且**三条的共同形态一样**：引擎/算法侧本来是对的，坏在"接缝"或"判据"上——

| # | 用户原话 | 真根因 | 修法（单一实现落在哪） |
|---|---|---|---|
| 1 | 「计数卡的前缀，`*`号，解析时无法传入，自己点选后，点生成时也没有」 | **前后端缝两头都漏同一对字段**：`_deck_to_frontend_dict` 序列化不带 `fn_prefix`/`number_suffix`（导入读不到）；`_tally_from_dict` 反序列化不收（选了也传不上来）；前端 `TallyTab` 的 `deckToLocalT` 写死 `prefix:""`、`localToDeckT` 压根不写 ⇒ **下拉框是装饰品**。引擎侧 `parse_f_tally`/`_generate_tallies` 一直是对的，`test_regress_fm_prefix.py` 只测引擎侧所以缝一直是绿的 | 缝两端补齐（含 camelCase 容忍）+ 新增纯模块 `gui/src/utils/tallyBridge.ts`（键序照后端回显顺序，护 `useDeckSynced` 等价判定）+ F5 行补**可见可改的环探测器轴控件**（旧行为连导入的 `F5X` 都被吃掉） |
| 2 | 「没自己打空格时解析没有出现空格；用户换行后第一个字符是#时会解析成#条件，**你应该判断一下是数字还是英文字母**」 | `normalize_lines`/`parse_cells` 见**行首 `#`** 一律当预处理器/条件行 ⇒ 手工折行的几何续行整行抛出：栅元 5 的 `surface_expr` **截断在 `#24`（丢 31 项补集）**、`imp:n/imp:p=1` 与 `$` 注释一起丢；另 `-14#1#2` 缺空格原样进 deck，而 `#` 是几何里**唯一"前面必须有空白"**的算子（实测 pymcnp `-14#1#2#3` → `TypesError` ⇒ AST=None ⇒ 该栅元在 3D 预览/源演示/重合检测里**静默消失**；`:`/`(`/`)` 紧贴都能解析） | 判据改成 **`#` 后第一个非空白字符是字母还是数字**（字母=`#ifdef`/THTME 表头⇒断点；数字/括号=几何补集⇒接回上一张几何卡，且**不要求 `&`/缩进**、仅当上一行首 token 是数字，THTME 表头不被误并）；新增 `lines.normalize_geometry_spacing`（`-14#1`→`-14 #1`）挂**生产者**（`parse_cells`）与**消费者**（`freecad_preview.parenthesize_unions`，兜手输）两侧，已规范文本逐字不变（护 R1） |
| 3 | 「3D预览中，截面拖动时，有时候会不知道框选到什么东西，导致前端**误以为是在导入东西，而卡死在导入时的粉色页面**」「截面拖动时，如果截面**有进行过旋转，拖动行为就会变得很怪异**」 | ① `App.tsx` 拖入导入覆盖层（`inset:0; zIndex:9999`）**`dragenter` 无条件点亮**、**`dragleave`/`dragend` 从不清除** ⇒ 拖拽起点落在**已选中的文字/可拖元素**上时浏览器会起一次原生拖拽（实测 `dataTransfer.types` 只有 `text/plain`、**无 `Files`**），这种拖拽**不会落到 `drop`**（松手在窗口外/Esc/跨文档）⇒ 粉色覆盖层永久留在屏幕上（`elementFromPoint(400,300)` 命中的就是它）= 卡死。② `CrossSectionView` 旋转中心写成 `(viewBox.x - pan.x)+w/zoom/2`（**跟着平移走**）⇒ 平移量被卷进旋转矩阵：`d(screen)/d(pan)=k(I−S+S·M)`，拖 Δ 的实际位移是 `(I−S+S·M)Δ`（θ=37° 实测 63/−41 变 74.99/−87.17，长度 ×1.53、方向差 16°）；θ=0 时退化为 Δ ⇒ **只有转过角度才露头** | ① 新增 `gui/src/utils/dragImport.ts`：只有**真拖文件**才亮、`leave/drop/end` **一律熄**、`onDragStart` 也熄、`dragLeave` 只在真离开 shell 时熄；覆盖层补 `pointerEvents:none`（意外亮起也不许吃点击）。② 新增 `gui/src/utils/sectionView.ts`（viewBox/旋转中心/组变换/等比缩放/拖动→pan 单一实现，**旋转中心不含 pan**），不变量"**任意旋转角下拖 Δ ⇒ 内容正好移 Δ**"由属性测试锁死 |

### S11.1 证据（每步都留了能红的尺子）

- **真浏览器复现（修复前，构建产物 + 真 Chrome）**：内部拖拽（`types=["text/plain"]`）⇒ 粉色覆盖层亮；紧接着 `dragend`+`dragleave` ⇒ **仍在**（`body.innerText` 仍含"释放以导入 INP 文件"）、`elementFromPoint` 命中覆盖层。修复后同一串事件：**全程不亮**；真拖文件（`types=["Files"]`）仍亮（导入功能没丢）且 `pointerEvents:none`；`dragend` 后熄灭。
- **纯函数属性测试**：`gui/test/sectionView.test.ts`（14 例）—— 任意旋转角（0/15/37/−25/90/180/270）× 缩放 × 三种留白下"拖 Δ ⇒ 内容正好移 Δ"；含**旧公式反向对照**（精确断言位移 = `(I−S+S·M)Δ`、θ=0 退化为 Δ）。
- **组件 DOM 测试**：`gui/test/crossSectionPan.dom.test.tsx`（4 例）—— 渲染出的 `viewBox`/`transform` 必须与算法一致。**当场抓到本次接线的一处错**：把 `dragStart` 记录当 pan 传入 ⇒ 拖动量多 200px（纯函数全绿也照样错，说明该层测试必要）。
- **部署版端到端**：`/api/parse-inp` 喂用户那张折行卡 ⇒ 1 栅元 / 54 项 / 含 `#55` / 无 `#1#2` 粘连 / `imp:n=imp:p=1` / 注释在位；回显 `fn_prefix='*'`、`number_suffix='X'`（⇒ exe 内 PYZ 的 `api_server.py` 与松散投放的 `generator/parsers/*` 都是新版）；`/api/generate` 回放 `*F4:N 1 2` + `F5X:N 0 0 0 1`。

### S11.2 本批新增纪律（已固化进 §6）

- **字段要在"缝"上双向核对**：模型/引擎有 ≠ 前端读得到。"导入读不到 + 传不上来"两头都漏时，任何单侧测试都全绿。
- **拖拽类覆盖层：只认真文件 + 任何结束事件都熄 + 永不挡点击**（`pointerEvents:none`）——否则用户一次误拖就永久卡死。
- **旋转/平移这类视图变换，用"不变量"当测试**（"内容跟着鼠标走"），而不是断言某个 `transform` 字符串长什么样。
- **`#` 是 MCNP 几何里唯一"前面要留白"的算子**；行首 `#` 必须按后随字符判"条件行 vs 几何补集"。

### S11.3 打包链实测出的三件事（**下次打包前先看**）

1. **`npm run build:release` 在干净工作区必失败**（本轮首次即中止）：`scripts/build-release.mjs` 把 `vite build + tauri build`
   排在 PyInstaller **之前**，而 `tauri.conf.json` 的 `beforeBuildCommand` 含 `sync-sidecar`、正等着 `dist_sidecar/`。
   实测日志：`[sync-sidecar] ❌ PyInstaller 产物不存在 … 已中止` → `Error beforeBuildCommand … failed` → `build-release ❌`。
   ⇒ **干净机/首次构建走手册手工顺序**（vite → PyInstaller → binaries → `npm run build:app`），本轮即如此。**该脚本的排序缺陷未修，留待裁决。**
2. **手册第 4 步的 `--workpath build_sidecar` 与 `build-release.mjs` 清缓存清的 `build/mcnp_sidecar` 不是同一目录**
   ⇒ "坑 B 清缓存"对不上。本轮用"产物与源码**逐文件哈希对拍** + 端点**功能级冒烟**"独立证明 sidecar 是新版（不依赖清缓存纪律）。
3. **主程序关闭后 `--mcp-http` 子进程（8100）不会随之终止**（实测残留 PID 仍在跑并占 8100；文档口径写的是"跟随主程序退出"）。
   ⇒ 打包/部署/冒烟前后都先查 **8100**，按 PID 精确清理（勿 `taskkill /im python.exe` 误杀他处 python）。

## S10（上一批次）实体预分解换血 + 三个几何 bug（2026-09-24，**已改 ✅ / 已提交 ✅ / 已随 v1.7.7 再次出包部署 ✅**）

> **三态**：**已改 ✅ / 未提交 / 已打包部署 ✅**（`npm run build:release` 175–289 s → 部署 `D:\MCNP\MCNP输入卡生成器` 7878 文件 / 254.07 MB → 部署版端到端复验通过）。
> 详细流水：`docs/CHANGELOG.md` 2026-09-24 三条 + `docs/frontend-changes.md` 同名三节。
> 门禁：pytest **1381 passed / 0 failed / 11 skipped**；vitest 99 files / 877 passed；typecheck 两档 EXIT 0。

本批是**用户连续实测驱动**的四轮，每轮都是"用户说现象 → 量化 → 定位根因 → 修 → 补能红的回归"：

| 轮 | 用户原话 | 真根因 | 谁的问题 |
|---|---|---|---|
| 1 | 「能调分解等级吗？分块的面数可以大一点的其实」→「考虑到 freecad 性能，每块面数控制在 30 以下」 | MCCAD 暴露的是**过程参数**（`recurrenceDepth`），给不了"每块面数"这个**结果指标**；且它把实体面数合计从 194 涨到 1110 | 设计选型 |
| 2 | 「分解的 stp 没问题，为什么 geouned 解析这些 stp 就出问题了？」→「把这些块一个一个传进程序看体积有没有变化」 | ① `_surf_classes()` 按 keyword 覆盖掉 `P_0` ⇒ 四系数平面被转成三点 ⇒ 感度翻转；② `_plane_halfspace` 厚板盖不满包围盒 | **我们的** |
| 3 | 同上（切了仍是几百个面 / 块 003 残留） | 不切时 GEOUNED 会产出「**3 个平面的交**」——3D 里必然无界 | **GEOUNED 的**（"预分解"恰好是它的解）|
| 4 | 「我用切分后，3D 预览…看到的是一坨」→「每个栅元都是乱的」 | 墓区栅元（`Graveyard`/`Graveyard_in`，体积 = 模型 7372%/1583%）被渲染，把模型整个包住 | **我们的**（序列化口漏 imp + 判据只认 imp）|

### S10.1 定位手法（可复用，本批最值钱的部分）

1. **按用户给的办法做逐块闭环**：把多实体 STEP 拆成单文件 → 逐块量**三处体积**
   （V0 基准真值 / V1 GEOUNED 的 `Vol=` 卡 / V2 程序重建）⇒ **责任一次性分清**
   （V1 全对 + V2 爆炸 + 对照块精确 ⇒ 错在表达式，不在转换、也不在重建机制）。
2. **纯算术角点检测**（不碰几何引擎）：MCNP 的栅元是"若干交项的并"，每个交项必须落在块内
   ⇒ 把包围盒 8 个角点代进每项，命中的就是"不界定"的项。
3. **翻转对照**：把可疑约定整体取反再跑同一判据（"当前 2 项命中 / 翻转 0 项命中"）。
4. **量"前端要渲染的东西"**：调真实 `/api/preview-3d`，把返回的每个 STL 都算体积与 bbox
   ⇒ 一眼看出谁是"一坨"（墓区：体积 7372%、bbox 2927³，模型才 1042×1751×260）。
5. **自己把 STL 画出来**：不需要浏览器也能看"形状对不对"（实体块总 bbox 与模型一致 ⇒ 几何正确）。

### S10.2 本批新增纪律（已固化进 §6）

- **判据必须能红**：`正侧 + 负侧 = 盒` 是恒真式（`负侧 := bb.cut(正侧)`），回退修复后照样绿 —— **假判据比没有判据更危险**。
- **序列化口必须喂全下游判据要读的键**：判据"读不到就放行"时，漏字段 = 静默全放行。
- **同一 keyword 的多个 pymcnp 变体不能按 keyword 收成一个**；需要"迁就某个变体"的转换代码是危险信号。
- **几何覆盖类不变量（"够不够大"）不写判据就一定会漏**。

## S9（上一批次）真实 MCNP keff 解析修复 + keff 解析玻璃卡（2026-09-20，**已提交 ✅ / 已打包部署 ✅ · 版本仍 1.7.6**）

> **三态**：**已改 ✅ / 已提交 ✅（`2a18f43`）/ 已打包部署 ✅**（`node scripts/build-release.mjs` 236 s → 备份 `_backup_1.7.6_20260920_004344` → 部署 + 冒烟通过；详见 S9.7）。
> 详细流水：`docs/CHANGELOG.md` 总表 + `docs/backend-changes.md`（§真实 MCNP 结果的 keff 序列解析修复）+ `docs/frontend-changes.md`（§keff 解析：独立玻璃卡 + 两个子按钮）。

### S9.1 起因（用户两句话）

1. 用户传 ZEUS-1 算例的 `.o` + `mctal` 问「这个文件里没有 keff 吗？」
2. 随后报「**程序解析不到 keff 序列**」。实测其**打包安装版**（`D:\MCNP\MCNP输入卡生成器`，后端 5001）POST `/api/parse-keff` 返 **HTTP 500**：
   `未在 mctal 中解析到 keff 收敛序列：<mctal>` —— 与用户措辞逐字对应，症状定位到端点而非文件。

### S9.2 根因（一句话 + 列语义）

`app/mctal_parser.py` 只认 **OWEN 简化夹具**（`k eff (c) <mean> <std>` 行 + `combined keff = ...`）——
**真实 MCNP6 mctal 里这些字段名一个都没有**：

- 头部是 `mcnp       6     09/20/26 ...` / probid / `ntal     0`（旧版本探测只认 `version N` / `N mctal`，也匹配不上）；
- KCODE 结果在**文末**：`kcode  600  100   19` = 总周期数 / 跳过周期数 / **每周期值数**，其后 **600×19 个裸数值**
  （每行 5 个、共 4 行/周期），**无任何字段名** ⇒ 只能按列定位。

**19 列语义（与同一算例 `.o` 的 print table 175 逐列核验得出）**：

| 列（1-based） | 含义 | 核验方式 |
| :-- | :-- | :-- |
| 1-3 | 逐周期 `k(coll) / k(abs) / k(trk)` | 与 `.o` 周期表 600 行逐个吻合 |
| 4-5 | 逐周期 prompt removal lifetime | 第 5 列 = `.o` table 175 的 `lifetime(abs)` |
| 6-13 | 活跃周期累计平均（三估计量 + `c/a/t`，各带 σ） | 第 6 列末值 0.99269 = `.o` 平均表末行 |
| 14-15 | 组合 `k(c/a/t)` 均值/σ（"跳过前 N-1 个周期"口径） | 前 3 周期的 0.99292/0.99284/0.99283 与 `.o` 的 skip 0/1/2 行逐位吻合 |
| 16-17 | 平均寿命 ± σ | 末值 194.89 shake = `.o` 的 1.9489E-06 s |
| 18-19 | 每周期源点数 / fom | 与 `.o` 对应两列末值一致 |

> **关键事实**：mctal 与 outp **都 *不* 逐周期写 σ**（只有累计平均带 σ）⇒ 逐周期序列的 `std` 只能是空数组，
> "最终值 ± σ" 一律取 `combined`（实测 `0.992775 ± 0.000356` = `.o` 结果段 `0.99277 ± 0.00036`）。

### S9.3 修复（后端 4 文件 + 1 个同族真 bug）

- `app/mctal_parser.py`：新增 `_parse_kcode_series`（按列定位；`mean` = 第 1 列逐周期 k(collision)，
  `combined` = 第 12/13 列**最后一组非零**累计平均，`std=[]`；声明的周期数 > 实际数值个数时按可分组数截断）；
  版本探测认 `mcnp <ver>`；**tally 块扫描遇 `kcode` 头即收尾** —— 否则 kcode 的裸数值会被灌进最后一个 tally 的
  `rows`（真实文件里两者可共存，属同一族的静默污染）。
- `app/outp_parser.py`：新增 `parse_keff_cycles` —— print table 175 的
  `individual and average keff estimator results by cycle` 表（表内每 10 行一条 `---` 分隔线；必须与相邻的
  "不同跳过周期数"表区分，后者靠表头措辞不同天然排除）+ 单行式 `cycle N k(collision) X` 兜底；
  `combined` 取结果段 `final estimated combined ... keff = X with an estimated standard deviation of Y`。
- `app/sweep.py`：`parse_keff_history` 改 **mctal → outp 双来源**并带出 `combined`；新增
  `history_keff_std`（逐周期 σ 优先、回落 `combined.std`）与 `scan_run_dir`（取运行目录里第一个能解出
  keff/序列的结果文件：`mctal*` → `*mctal*` → `*.m` → `outp*` → `*.o`）。
- `gui/backend/api_server.py`：`/api/parse-keff` 接受 mctal / outp(`.o`) / 目录（目录走 `scan_run_dir`）。
- **同族真 bug（本批顺手修，与用户报的同源）**：`sweep-run` 原来 `parse_keff(proc.stdout)`，而 **MCNP 的 keff
  只写在结果文件里**（stdout 只有少量提示行）⇒ 参数扫描汇总 TSV 的 keff **恒 `n/a`**；改为 `scan_run_dir`
  读目录（stdout 仅兜底），dashboard 侧同时回填旧 manifest 缺失的 keff。

### S9.4 用户追加需求：「keff 解析做成独立玻璃卡 + 两个子按钮」

> 用户原话：「你把 keff 解析做成一个单独的玻璃卡，里面两个子按钮，一个解析 mctal，一个解析 .o，
> 解析 mctal 的，选择解析文件时，**默认无后缀**」。

- `gui/src/components/KeffParseCard.tsx`（**新**）：玻璃卡（沿用 `.glass-card`/`.card-header`/`.card-title`）
  + `📄 解析 mctal` / `🧾 解析 .o` 两个子按钮；`OutputTab` 卡头那个 `🔬 解析 keff` 小按钮**移除**，
  改为「输出文件」与「Tally 结果」之间的**独立玻璃卡**；`KeffDialog` 改**结果窗口**
  （新增 `initialPath`，挂载即解析；路径框仍可编辑 —— **运行目录**只能手输/粘贴，按钮选不了目录）。
- `app/file_dialog.py`（**新**，纯 stdlib 可单测）+ `/api/choose-file` 的 `kind`（`inp` 默认 / `mctal` / `outp`）
  与 `withContent`：**mctal 默认"无后缀"**（首项过滤 `*`；Tk 以 `filetypes[0]` 为默认选中项）——
  MCNP 的 mctal **本体没有扩展名**，加了过滤用户打开窗口就**看不见自己的文件**；`withContent:false`
  只回路径（keff 只要路径，而 outp 可能几百 MB，不该读成 JSON）。
- `gui/mcnp_sidecar.spec`：`_keep_py` 登记 `file_dialog.py`（`_import_app` 动态导入；漏登记 = 打包版端点 500，
  正是 TD-34 闸门管的那类事故）。

### S9.5 证据与门禁（实跑）

- 夹具：`tests/fixtures/real_kcode_zeus1.mctal`（141 KB）+ `real_kcode_zeus1.o`（570 KB，同一算例）。
- **交叉校验**：`.o` 与 mctal 的 **600 周期逐值相等**，最大差 **5e-6**（`.o` 只印 5 位小数、mctal 印 6 位有效数字）；
  最终值三处一致：mctal 累计平均 `0.992775 ± 0.000356`、`.o` 结果段 `0.99277 ± 0.00036`、`.o` skip=0 行 `0.99292 ± 0.00034`（= mctal 第 14/15 列首周期值）。
- 新增用例：pytest **+14**（`test_mctal_parser` 3 / `test_outp_parser` 5 / `test_sweep` 6）+ **+7**（`test_file_dialog`）、vitest **+5**（`keffParseCard.dom.test.tsx`）。
- 门禁：pytest **1019 passed / 0 failed**；vitest **799 passed / 96 files**；`tsc` 两档 EXIT 0；`vite build` EXIT 0；
  `python -m compileall -q app gui tests inputcard_mcp` EXIT 0。
- handler 级实测（进程内调 handler；tkinter 换成假弹窗、**不真弹窗**）：`/api/parse-keff` 三种入参都出
  `cycles=600, first=1.04435, last=1.00217`；`/api/choose-file` 四种入参的标题/默认过滤/响应键符合预期，
  取消返 `{path:"", cancelled:true}`。

### S9.6 部署侧发现（**可复用知识**，已固化进 §6）

打包安装版里 `mctal_parser` / `sweep` 这类 `_keep_py` 模块是**松散 `.py` 数据文件**，而 `api_server` / `outp_parser` /
`app.models` 等**冻结在 exe 的 PYZ 里**（判据：直接读 exe 内 PYZ 名字表，见 §6）。
⇒ **可以只替换 `_internal\app\*.py` 做"部分热修"**（重启生效；本批已实测 mctal 的 keff 解析恢复），
但 `.o` 入参、扫描侧 keff、前端玻璃卡**都改在冻结部分/前端 bundle 里 ⇒ 必须重新打包**。

### S9.7 提交与打包部署（2026-09-20，**版本仍 1.7.6**）

用户指令：「维护项目记忆，提交，打包」；版本按手册规则（bug 修复批不升版）**向用户确认后保持 1.7.6**，
交付口径也由用户选定：**按手册执行（停程序 → 备份 → 部署 → 冒烟），冒烟后程序留着开着**。

**提交**：`2a18f43`（21 文件 = 后端 4 + 前端 3 + spec 1 + 测试 5 + 夹具 2 + 文档 5 + 记忆 1）。

| 步 | 内容 | 结果 |
| :-- | :--- | :--- |
| 1 | 版本核对 | ✅ 六处仍 1.7.6（`tauri.conf.json` / `package.json` / `package-lock.json` 两处 / `Cargo.toml` / `Cargo.lock` / README 徽章）；用户确认不升版 |
| 2 | 门禁 | ✅ pytest **1019/0** / vitest **96 files 799 passed** / tsc 两档 0 / vite build 0 / compileall 0 |
| 3 | 打包 | ✅ `node scripts/build-release.mjs`（= `npm run build:release`）**236 s**；其中 `tauri build` `Compiling mcnp-ui v1.7.6` **29.25 s**，PyInstaller 6.21.0 / Python 3.13.14 |
| 4 | 6.2 时效校验 | ✅ 已自动化且**本次点名了本批改动**：`缺 1 个 app/file_dialog.py`、`大小不符 3 个 app/mctal_parser.py (10507←5294) / outp_parser.py (8254←4504) / sweep.py (14568←11728)` → 自动镜像 → `--require-target` ✅ **7868 文件 / python.exe 32516335 B**（"版本号新、后端旧"这次不可能发生） |
| 5 | 产物 | `MCNP 输入卡生成器.exe` **6609408 B**（MD5 `1BC2F7BD51078C8F29322E0A4005023F`）；`python.exe` **32516335 B**（MD5 `E3C2913FBD492041CAC09D596FE1F14E`） |
| 6 | 备份 | ✅ `D:\MCNP\_backup_1.7.6_20260920_004344`（7877 文件 / 242.2 MB，robocopy 8 s） |
| 7 | 部署 | ✅ `D:\MCNP\MCNP输入卡生成器` 7872 文件 / 242 MB；在位清单 10 项全 OK（`preview_cache.py`、**`file_dialog.py` 2824 B**、`mctal_parser.py` 10507 B、`outp_parser.py` 8254 B、`sweep.py` 14568 B、`vendor\geouned`、README、AI接入.md）；部署 exe MD5 **等于** `target/release` 那份 |
| 8 | 前端内嵌证据 | 旧包 bundle `index-C1-X34nn.js` → 新包 **`index-BXZQ_LUu.js`**；该 bundle（`gui/dist/assets/index-BXZQ_LUu.js`）内含 `解析 mctal` / `解析 .o` / `keff 解析` / `withContent` / `/api/choose-file`。**注**：Tauri 内嵌资源是压缩的 ⇒ 直接在 exe 里搜中文串搜不到，**只能拿 bundle 名当锚**（本次即如此） |
| 9 | 冒烟（本次加了一条比 3D 预览更硬的） | ✅ 5001 约 **4 s** 就绪 + 8100 LISTENING；`/api/xsdir-check` = `loaded:true, count:7925`；`/api/parse-keff` **三种入参全 ok** —— mctal 600 周期 `combined 0.992775±0.000356395`、**`.o` 600 周期 `0.99277±0.00036`（本批新能力 ⇒ 直接证明 exe 内 `api_server` 已是新版）**、夹具目录自动找文件；`/api/diff-inp` 回归 ok |
| 10 | 收尾 | 程序按用户要求**留着开着**（未按 §8.3 清理）；临时热修备份 `D:\MCNP\_hotfix_backup_20260920_002352` **已删**（被本次完整备份取代）；工作区 16 个 `_` 前缀历史 scratch 仍未跟踪（非本批产物） |

> **本批给手册补的一条判据**：验收"后端真的换了"最省事的做法**不是** 3D 预览，而是
> **打本批新增/新支持的那个端点**（本次 = `/api/parse-keff` 传 `.o`）。旧 `api_server` 只认 mctal ⇒
> `.o` 能出序列即为"新后端已在 exe 里"的充分证据，且一条 curl 就完成。

## S8（上一批次）排版审计 + 出图一律 PNG + 截面悬停修复（2026-09-19，**已提交 ✅ / 已打包部署 ✅ · 版本仍 1.7.6**）

> **三态**：**已改 ✅ / 已提交 ✅（`8651244` + `1d705b1`）/ 已打包部署 ✅**（`node scripts/build-release.mjs` 306 s → 备份 `_backup_1.7.6_20260919_124301` → 部署 + 冒烟通过；**主程序开窗后的界面行为待用户目视确认**）

### S8.1 起因

用户报「快捷栅元界面、3D 预览里的快捷栅元界面、以及最近加的导出图片，**排版明显非人类**」，
要求**用视觉能力审计**相关界面/导出图并顺带排查其他界面。审计方法：起真实后端（`api_server.py` 5001）
+ 静态前端（`python -m http.server 1420 --directory gui/dist`），用浏览器控制扩展实机读图 + DOM 量尺寸。

> **注**：`vite dev`（1420 dev server）**在本机沙箱里会挂起**（esbuild 子进程管道），
> 要起前端请用 `python -m http.server ... --directory gui/dist`（与 `启动MCNP输入卡生成器.bat` 同口径）。

### S8.2 六类真排版缺陷（逐条实测，全部已修）

| # | 缺陷 | 实测证据 | 修法 |
|:--|:--|:--|:--|
| 1 | **`QuickCellForm` 要 356px，3D 侧栏只给 271px** | 侧栏 `width:300` − 2×14 内边距 ⇒ `form.clientWidth=199 / scrollWidth=271`，溢出被 `overflow-x:hidden` **裁掉且无法滚到** ⇒ 输入框在视口外、"M0 — 真空"被截成"M0 — 真" | 3D 预览打开快捷建栅元时**侧栏加宽 300→400**（`Preview3D.QUICK_CELL_PANEL_W`，实测表单 371px 零溢出）；**去掉 `inset:0` 覆盖层**——它原来把整个侧栏（含 3D 图）全盖掉，用户"想看 3D 只剩一条缝" |
| 2 | **行标签与字段标签错半格** | `style.row` 是 `alignItems:"flex-end"`，而行标签列是"标签在上"的纵列 ⇒ 「底面中心」被推到与**输入框底边**对齐，比字段标签「X」低一格（y=206 vs y=177） | 改 `flex-start`；行首标签列改固定 64px + `nowrap`（「半径 / 切分」不再被压成两行贴住字段）。修后实测同行 y 一致 |
| 3 | **`legendMetrics` 的 `*2` 把图例上限写成 480px** | `figureCanvas.ts:105` 原为 `Math.max(150, Math.min(240, …) * 2)` —— 注释说 150–240，代码是 300–480 | 改成真上限 260 + 中文/ASCII 分别估宽（`estimateLabelWidth`） |
| 4 | **图例按"每行两条"排，第二列挂在图外空白上** | `rows = ceil(条目数/2)` ⇒ 7 条材料排 4 行 2 列；实测 560px 宽的 3D 导出图里第二列（x 467–543）**整个落在图像右边缘（x=337）之外**，约 35% 图宽只有小字 | 改**单列竖排**（论文图例本来的形态）。实测图例面板 **480 → 120px**，占整图 **31% → 18%** |
| 5 | **出图尺寸随人窗口变，且"2× 画布 1× 字号"** | 导出直接取当前帧：同一张卡实测导出过 560×523 与（窄窗口下）609×822 两种比例；`RASTER_SCALE=2` 只放大画布、字号仍是 1× 像素（标题实测 13px ⇒ 95mm 宽摆放时约 6.5pt） | 新增**印张基准** `PRINT_MAX_PANEL_SIDE=640`（只缩不放）+ 内容高上限 560；栅格/矢量两条出口同口径 |
| 6 | **长脚注单行画出边界** | `ctx.fillText(spec.caption, …)` 无换行；55 个中文字符就顶满 560px 图宽 | 新增 `wrapText()`（中文按字断、ASCII 按词断）+ 多行绘制，行数参与高度 |

**顺手修**：色带刻度/单位可能压出面板（刻度按可用宽度 `clip`、单位 `y` 钳在底边内）；
`figureCanvas` 里那段被截断的空 JSDoc 块删掉；材料行/IMP 行 `minWidth:0`（实测 `scrollWidth` 356 vs 331 的 25px 溢出，可见约 2px）。

### S8.3 用户裁决与落地

1. **「所有导出的图片改用 png 格式，该用透明底的用透明底」**（2026-09-19）：
   - `exportFigure` **只出 PNG**：二维图（截面/tally/keff/fmesh 切面）走「矢量合成 → 2× 栅格 → PNG」，
     三维走位图合成 → PNG；**PDF/SVG 从门面摘掉**（`figureToPdf` 实现仍在，只差格式决策）。
   - **当天先做成缺省透明底**（`renderFigure` / `buildVectorFigure` 的底色缺省从 `#ffffff` 改成 `null`；
     `KeffDialog` 硬铺的白矩形去掉）——⚠️ **此条当天晚些被用户推翻，最终口径是"白底"，见 S8.8**。
     本节保留当时的决策与理由，**以 S8.8 为准**。
   - **3D 透明底要专门做**（见 §6 新坑）：新增 `captureFrame.captureTransparent3D()`。
     ⚠️ 这一步**不受 S8.8 影响**：产物白底，但 3D 中间帧仍必须透明。
   - **该白底的仍白底**：fmesh 切面是整幅颜色填充，白底只铺在**热图范围内**（`SliceExportPanel.heatBase`）。
2. **「2D 图就算了」**（2026-09-19）：接受 PNG 失去矢量性，**不恢复 PDF/SVG 出口**。
3. **「3D 你自己看着办」** → **已做**：轴/刻度改**印刷墨色**（见 S8.4）。
4. **「其余的你该怎么改就怎么改」** → 上述 6 类缺陷全修。

### S8.4 3D 出图的"论文配色"补齐（本次自己判断要做的）

3D 场景底色与**刻度标签/轴字母**都烧在 WebGL 里，原来只有"药丸底 + 亮字"一种画法 ⇒ 透明出图会在白纸上
留一串**深色方块**、且亮绿（`0x44ff44`）几乎看不见。修法（**只发生在取图那一帧**，屏上观感不变）：

- `axisConfig` 每条轴新增 **`paperInk`**（同色相压暗：红 `0xa11212` / 绿 `0x14701f` / 蓝 `0x144a9e`）；
- `TickGrid` 新增 **`setLabelTheme("screen" | "paper")`**：paper = **透明底 + 深色字**（不再画药丸底）；
- `Preview3D.renderTransparentNow()`：切墨色 → 重建刻度 → 切轴字母的**墨色副本身**（预建两份 sprite、只切 `visible`，
  **零纹理 churn / 零闪烁**）→ 取帧 → `finally` 全部还原；
- 材料色**不动**（色相必须与屏幕一一对应，否则用户没法照着屏幕认图）。

### S8.5 门禁与验证（实跑）

- `tsc --noEmit` + `tsc -p tsconfig.test.json --noEmit` **两档 EXIT 0**；
  `vitest run` **757 passed / 92 files**（基线 737/90 + 新增 20）；`vite build` **EXIT 0**。
- 新增回归：`test/exportOutputContract.test.ts`（7 例：**一律 PNG** / 透明底能力保留 / 显式背景透传 /
  三维通路也是 PNG / 空内容报错 / `captureTransparent3D` 取帧期间置空背景+alpha=0 且**抛错也还原**）；
  `test/sectionHit.test.tsx`（7 例，见 S8.6）；
  `exportFoundation.test.ts` 补 4 条**版面不变量**（图例宽不随条目数膨胀 / 长脚注折行 / 竖长条源画布高度受限 / 无面板不返回 0）；
  `tickGrid.test.ts` 补 paper 主题**不画药丸底**；`axisConfig.test.ts` 补墨色**比屏幕色暗且色相不串**。
- **视觉复查（实机 1:1）**：快捷建栅元弹窗（标签一行一对齐、5 个形状按钮单行可读、材料/IMP 行完整）；
  3D 预览 + 快捷建栅元（表单与 3D 圆柱同屏并存，**3D 不再被挡**）；3D 预览原状态（刻度标签/药丸底/轴线无回归）；
  3D 导出实跑拿到 PNG（合成画布 597×663，证明面板确实被归一）。PNG 本体 `colorType 6`（RGBA）。
- **审计遗留（本次未做，明确记录）**：
  1. **主界面整体过缩**：`computeAppScale = min(1, w/1200, h/800)` 用**整个视口高**，1536×864 上算得 0.6775，
     设计稿缩完只需 813×542 而视口有 813×853 ⇒ **底部约 300px 空白**。属版面策略，要用户定"是否按可用高度重算"。
  2. `exportFigure` 的矢量路径现在**先落 SVG 再落 PDF**的顺序问题随 PDF 摘除而消失，但 `exportMessage` 仍走 `alert()`
     （项目 §6 有"alert 冻结渲染进程"的坑记录），未改。
  3. `FloatingDialog` 宽度是各调用方写死的 px，窄窗口下无 `maxWidth` 保护（同类隐患，未发作）。
  4. **大模型截面要等很久**：用用户那张 `q1112`（`1 cz 75` 大球 + 六个盘，10 个栅元）实测，
     X=0 截面在后端**算超过 60 s 未返回**，前端 `AbortSignal.timeout(60000)` 会中止 ⇒ 覆盖层不出现。
     不是本次改动引入（没碰后端与切片），但"点截面等一分钟"本身要治：可考虑切片前按栅元 STL
     三角形数降采样、或后端加进度/异步返回。

### S8.6 截面悬停读数与图形不同源（2026-09-19 用户实测，**同批修**）

> 用户原话："在 X=0 时，会出现 cell2 覆盖中间部分的情况" → 追问后澄清：**图形正常，是鼠标悬停的材料号不对**。

**真根因（纯前端，与后端数据无关）**：绘制按 `slices` 顺序（= 栅元卡声明顺序），**后声明者画在上面**；
而 `CrossSectionView` 的命中检测**从数组头开始找第一个包含点的多边形** ⇒ 在"盘里套盘"处报的是
**被盖住的那个**。用真后端对 `q1112` 在 X=0 平面实测（`/api/preview-3d` + `/api/cross-section`）：

```
cell 2  M1  y[-5.00,5.00] z[-90,90]   ★覆盖(0,0)   ← 图上被 cell3 盖住
cell 3  M2  y[-3.97,3.97] z[-29.8,29.8]
cell 12 M5  y[-3.44,3.44] z[-5.30,8.70] ★覆盖(0,0)
```

⇒ **数据层每层都是 MCNP 语义的正确形状**（与用户"图形正常"一致），错的只有读数。

**修法**：新增深模块 `gui/src/utils/sectionHit.ts` —— `paintOrder()`（绘制次序 = 按声明次序，后声明在上）
与 `topMostHit()`（**从绘制次序末尾往前**找第一个命中 = 视觉最上层）。组件改为调 `topMostHit`。
**没顺手反转绘制次序**：那会改图形本身（谁盖住谁），属另一个更大的决定（要让 MCNP"先声明者占有重叠区"
真正生效须做多边形布尔裁剪）；本模块只保证**读数与图形同源**，将来真做裁剪只需改 `paintOrder` 一处。

**回归 `gui/test/sectionHit.test.tsx`（7 例）**：含**红能力证明**（把旧实现原样复刻进测试：同一点旧逻辑报 `2`、
新逻辑报 `3`）与**"读数与图形同源"**（真渲染组件，从 DOM 取 `<polygon>` 的实际次序，断言"渲染在最后＝最上层"
的多边形就是悬停报出的栅元 —— 以后改绘制次序，读数会跟着变，不会再次分叉）。

### S8.7 提交与打包部署（2026-09-19，**版本仍 1.7.6**）

**提交（两个，按主题拆）**：
| commit | 主题 |
| :--- | :--- |
| `8651244` | `feat(export)` 出图出口收敛为「一律 PNG」（该提交时底色是透明，**当天晚些被 S8.8 改成白底**）+ 6 类排版缺陷 + 3D 印刷墨色（26 文件） |
| `1d705b1` | `fix(cross-section)` 悬停读数与图形不同源——命中检测改按绘制次序从后往前（+ 新增 `sectionHit.ts` 与其单测、本记忆） |

> **提交时的教训**：第一次 `git add` 把 `gui/src/volume/VolumeRenderer.ts` 漏了（它在另一批的清单里），
> 用 `git commit --amend --no-edit` 补进去。**教训：`git add` 之后要 `git status` 复核一遍暂存区**，
> 别凭记忆列文件。

**打包链路（实跑，`node scripts/build-release.mjs`，**306 s / EXIT 0**）**：
1. `vite build`（清空重建 `dist/`，7.45 s）；
2. `tauri build`（**31.34 s**；`beforeBuildCommand` 里的 `npm run build && npm run sync-sidecar` 自动跑）；
3. 清 `build/mcnp_sidecar` 缓存后 PyInstaller（`--distpath dist_sidecar`）→ sidecar `python.exe` **32,514,167 B** / `_internal` **7867 文件**；
4. 覆盖 `src-tauri/binaries/`（同步的比较源）；
5. `sync-sidecar` → **⚠️ 本次又命中增量编译坑**（`sync-sidecar` 自报"target/release 的 sidecar 陈旧 —— python.exe 大小不符"并**自动覆盖 + 复核一致**）；
6. `sync-sidecar --check --require-target` → ✅ 一致。

**6.2 校验（逐文件）**：`target/release/python.exe` 与 `binaries/` **MD5 完全一致**（`ACC4DDC6…`）；
`_internal` 逐文件清单 7867 项一致。**附带确认**：`_internal\app` **28 个文件与旧包完全一致**（本批后端逐文件未变，
符合"纯前端批"的预期）。

**备份与部署**：备份 `D:\MCNP\_backup_1.7.6_20260919_124301`（**7877 文件 / 242.4 MB**）→ 部署
`D:\MCNP\MCNP输入卡生成器`：exe **6,607,360 B** / `python.exe` **32,514,167 B** / `_internal` 7867 文件（总 7871）
/ README 13095 B / AI接入.md 3798 B；`_internal\app\preview_cache.py` 与 `_internal\vendor\geouned` 均**在位**；
三件套 MD5 与构建产物**逐一致**。

**冒烟（部署版 sidecar，真实 HTTP；用临时副本起，避免它往交付目录写缓存）**：
`xsdir-check` / `mcnp-detect` / `diff-inp` 全 **ok**；`preview-3d` **ok**（1.1 s，3 个 STL）——
球壳解析体积对拍：cell1（壁）490.0885 → **489.1858（−0.18%）**、cell2（空腔）33.5103 → **33.4486（−0.18%）**；
`/api/check-freecad` 类端点同批验证；MCP `http://127.0.0.1:8100/workspace` **200**（`writer` / `tally` 子对象字段齐）。
> ⚠️ **起 sidecar 要 `--mcp-http` 才会同时有 8100**：`mcnp_bridge.py` 里 `--mcp-http` 是**独占分支**
> （`sys.exit(0)` 之前只跑 MCP），主程序是**另起一个进程**带该参数。直接手起 sidecar 时若不带它，8100 不会监听
> —— 这不是缺陷，是冒烟时的命令姿势问题（本次实测踩到）。

**❗新踩坑（本批实证，值得记牢）：PyInstaller 产物**不是**字节可复现的**。
本次后端源码逐文件未变（`_internal\app` 28 文件清单一致、`python.exe` **大小同为 32,514,167 B**），
但新产物的 MD5（`ACC4DDC6…`）与旧包（`B690641D…`）**不同** ⇒ **"python.exe 的哈希与上一版相同"绝不能用来
判"后端没变/变了"**；判"这批改动是否进了包"要用**功能冒烟**（端点行为）或 **exe 内嵌前端 bundle 的指纹**，
不能用 sidecar 哈希。

### S8.8 出图底色改回**白底**（2026-09-19 同日，用户实机看过之后改口）

**用户原话**："算了，png 都改为白底吧。"（先说"该用透明底的用透明底"，看过实物后改了主意）

**改动（单一处口径 + 三处跟随）**：
- `exportFigure` 新增 `FIGURE_BACKGROUND = "#ffffff"`，两条通路都显式传白底
  （矢量：`buildVectorFigure({ background })` + `svgToRaster({ background })` + `capturePngBytes({ background })`；
  栅格：`renderFigure(spec, { background })` + `capturePngBytes`）；
- `renderFigure` 的缺省底色从 `null` 改回 `"#ffffff"`（`spec.background` 优先于 `opts.background`）；
- `vectorFigure`：**入口缺省仍不铺底**（保持"矢量层不自作主张"），产物白底由门面显式给 ——
  这一点与栅格版相反，已写进 `VectorFigureSpec.background` 的注释，**改之前先看清哪一层负责铺底**；
- `ExportButton` 的 tooltip 文案跟着改。

**⚠️ 关键区分（写进代码注释，别混）**：**产物是白底，3D 的中间帧仍是透明**。
`renderTransparentNow()`（`captureFrame.captureTransparent3D`）继续保留 —— 只有取到透明帧，
才能把它干净地合成到白底版面上；否则 WebGL 的深色场景底（`0x0d0d22` 等）会被一起贴上来，
表现为"白底图里有一块深蓝方块"。**"改成白底"不等于把透明取帧拆掉。**

**门禁**：tsc 两档 **0** / vitest **92 files 757 passed** / `vite build` **0**。
回归也跟着改了：`exportFoundation.test.ts` 的"底色默认"用例改成断言**默认铺白底**（用桩记账 `fillRect` 时的
`fillStyle`，并断言显式传 `null` 时一次都不铺）；`exportOutputContract.test.ts` 的透明底用例改成
"矢量合成层仍认调用方的 `background`"（门面在栅格化那步固定白底，所以不能拿它断言透明）。

**重打包与部署（同日，第二次）**：`node scripts/build-release.mjs` **157 s / EXIT 0**
（前端 bundle 指纹 `index-CDnBByYY.css` + `index-BZkpsDuI.js`，`tauri build` 13.22 s，PyInstaller 产物
`python.exe` **32,514,167 B** / `_internal` 7867）；6.2 校验 `target/release/python.exe` ↔ `binaries/`
MD5 一致（`2B47458F…`）；**`sync-sidecar` 再次自报"陈旧"并自动覆盖**（这个坑每轮必中）。
备份 `D:\MCNP\_backup_1.7.6_20260919_130256`（7877 文件 / 242.2 MB）→ 部署
`D:\MCNP\MCNP输入卡生成器`：exe **6,607,360 B**（MD5 `678CC9EE…`，与构建产物一致）/ `python.exe`
**32,514,167 B** / `_internal` 7867 / README + AI接入.md；`preview_cache.py`、`vendor\geouned` 在位。

**实机取图验证（这次做到了"看见像素"）**：起源码后端 + 新 `dist`，在 3D 预览点「导出」，
把**导出用的那张合成画布**（597×663）搬进页面、先铺品红再叠上去截图 ⇒ **图内背景是纯白**、
品红只在画布外的 padding 露出；4 条轴线与刻度、标题、**单列竖排图例**、脚注全在位 ⇒ **白底生效**。
> ❗**本次踩到的取证坑（值得记）**：本环境里 **`<img>` 加载 `blob:`/`data:` URL 不会触发 `onload`**
> （`new Image(); img.src=...` 永久 pending）。**第一版钩子用 `<img>` 显示导出结果，直接把导出挂死在
> "导出中…"**（`capturePngBytes` 之前的链路都在等它）。⇒ 在此环境做"取图判读"，要么**钩住
> `HTMLCanvasElement.prototype.toDataURL` 把画布本体搬进 DOM**（canvas→canvas `drawImage`，同步、可靠），
> 要么用 CDP 截图；**不要走 `<img>`**。这条与 §6 里"`svgToRaster` 在 jsdom 里等 img 解码"是同一个根因。

**⚠️ 待用户目视确认**：本批改了前端（`gui/dist` 内嵌进 exe）。我验的是"部署的 sidecar 行为 + 三件套一致性 +
源码版实机取图（白底）"，**部署版主程序开窗后的界面行为**（出图按钮只出 PNG 且**白底**、快捷栅元侧栏加宽、
截面悬停读数）需要用户实际点一下确认（按 S5 的旧例：部署版主程序能否正常开窗我只做了间接验证）。

### S8.9 按"中文期刊对数据图的要求"整改出图（2026-09-19 同日，用户："1.中文期刊, 2.全部改动"）

**背景**：用户要求先查国标/学术出版对数据图的要求，再照着改。搜索结果只拿到片段（细则 PDF 全被 403 挡），
结论 = **片段 + 既有知识**，其中国标条款号**未逐字核对**（已在对话里声明）。落成的改动如下。

**① 量与单位（新增深模块 `gui/src/export/quantityLabels.ts`）**
- 轴标统一成 `量名称 量符号/单位`（GB 3100~3102）：`长度 L/cm`、`通量密度 φ/(cm⁻²·MeV⁻¹)`、`有效增殖因子 k`；
- **复合/带幂单位一律加括号**（`(cm⁻²·MeV⁻¹)`、`(cm⁻²)`）—— 避免"斜线接幂"的坏写法，且**只允许一个斜线**；
- 单位幂转 Unicode 上标（canvas 不解析 `<sup>`/MathML，这是唯一画得对的写法）；
- `withUnit()`：数值与单位间留空格，但 `%`、`°` 不留；12 条单测锁格式（`test/quantityLabels.test.ts`）。
- ⚠️ **已知缺口**：GB 要求量符号**斜体**（`L`、`φ`），而 canvas `fillText` 只能整段一个风格 ⇒ 须分段测量绘制。
  **这一步没做**，当前整行正体（`quantityLabels.ITALIC_SYMBOL_PENDING` 记着）。

**② 图题/图注版式**
- **图题改到图的下方居中**（原来是标题在上）；图注（参数 + 来源）作小字排在**图题之下、左对齐**。
- **图序不印进图里**（用户裁决）：同一文稿里哪个图排第几只有作者知道，程序每次导出都写"图1"会
  **让第二张图也印成图1**；规范要求的是"图题不得省略图序"，不要求"图序必须印在图内"。
  **曾短暂实现自动加 `图N` 前缀，已撤除，别再加回来。**

**③ 分辨率与物理尺寸（本次最实的一块）**
- 新增 **`withPngDpi()`**（`captureFrame.ts`）：把物理尺寸写进 PNG 的 `pHYs` 块 ——
  **PNG 本身没有物理尺寸**，不说清"印 80 mm 还是 170 mm"，"够不够 600 dpi"就是空话；
- 倍率不再写死 2×：新增 `rasterScaleFor(逻辑宽, 成品宽mm, 目标dpi)`；**线图 600 dpi**（`PRINT_LINE_DPI`）、
  **含位图/热图 300 dpi**（`PRINT_HALFTONE_DPI`），成品宽缺省 **80 mm 单栏**（通栏 170 mm 可选），倍率上限 6×；
- 10 条单测（`test/exportPngDpi.test.ts`）：倍率算术、`pHYs` 紧跟 `IHDR`、文件仍以 `IEND` 收尾、
  **重复写入不堆两个 pHYs**、**不是 PNG 就原样返回（绝不因为想写元数据把图弄坏）**。

**④ 字号提档**：按 600 dpi 折算 `pt ≈ px × 0.423`，上一版刻度只有 **4.2 pt**、图注 4.2 pt（期刊底线 6~8 pt）⇒
改为 title 18 / label 15 / tick 13 / caption 12 ⇒ **7.6 / 6.3 / 5.5 / 5.1 pt**；刻度仍差一档（受单栏 80 mm 物理约束）。

**⑤ 色表换成 viridis（黑白打印可辨）—— 改了跨语言契约，是本次最"重"的一改**
- **问题**：原"蓝→青→黄→橙→红"在 t≈0.75 之后**亮度回落**，灰度下红与蓝几乎同灰 ⇒ 打印/复印读不出高低；
- **过程（值得记）**：第一版我自己手配的"深蓝→…→近白"色表**翻车** —— 锚点亮度单调，但 **256 项 LUT 插值后又回落 2 处**
  （8bit 量化，单步 <1 灰阶，但性质不成立）；**第二版改用 viridis 官方锚点**，判据全部通过：
  **0 处回落、粗粒度严格递增、灰阶 42→228、相对亮度 0.019→0.782**；
- **契约三处一起改**（否则跨语言闸门红）：`app/meshtal/colormap.py`、`gui/src/volume/colorize.ts`、
  `docs/contracts/meshtal-visualization.md` §4.3.1，以及**两个 golden sha256**
  （`tests/unit/test_meshtal_colormap.py` + `gui/test/volume/colorize.test.ts`）→ `44694904…`；
- 两侧都补了**性质断言**（不只是换数字）：python `test_weather_stops_luminance_monotonic`、
  TS `"★ viridis 亮度单调"` —— 谁再换回非单调色表就会红。
- ⚠️ **待目视确认**：viridis 低值端**很暗**，在**深色屏幕**上不如原来的亮蓝显眼，低值结构可能"看起来变少"；
  这是色表取舍（打印可辨 ↔ 屏幕亮底可辨）的必然，需用户实机看一眼。

**门禁（实跑）**：pytest `tests/unit tests/parser` = **882 passed / 1 failed**（既有 GBK 环境失败
`test_meshtal_worker::test_worker_spawn_dev_mode_bad_tally_error`，与本次无关）；
vitest **94 files / 781 passed**（+24）；tsc 两档 **0**。

### S8.10 S8.9 的提交与打包（2026-09-19 同日，**版本仍 1.7.6**）

**提交**：`1b78ac1 feat(export): 按中文期刊要求整改出图（量单位标注 / 图题在图下 / PNG 物理尺寸 / viridis 色表）`
（14 文件：2 个新模块/新测试 + 三处色表契约 + 两个 golden）。

**打包（`node scripts/build-release.mjs`，381 s / EXIT 0）**：
- 轮 `tauri build` 40.59 s；PyInstaller 产物 `python.exe` **32,514,579 B** / `_internal` 7867；
- **6.2 坑这次把差异点名了**（本批的价值体现）：`sync-sidecar` 报
  `大小不符 1 个，如：app/meshtal/colormap.py (src 3231 B / dst 2484 B)` 并**自动覆盖 + 复核一致**
  —— **色表改动确实进了包**（这条比"报个大小不符"有用得多，是脚本升级后的产物）；
- 备份 `D:\MCNP\_backup_1.7.6_20260919_185826`（7877 文件）→ 部署 `D:\MCNP\MCNP输入卡生成器`：
  exe **6,607,872 B** / `python.exe` **32,514,579 B** / `colormap.py` **3231 B**（= 新版大小）/ 总 7871 文件。

**部署验证（这次两条都是"文件级"硬证据，不靠猜）**：
1. **exe 内前端 bundle 指纹** = `index-BPp0bFCS.js`，且**不含**上一版的 `index-BZkpsDuI.js` ⇒ 前端改动进了交付产物；
2. **在部署目录上复算 colormap 的 golden sha256** = `44694904…`（与新 golden **逐位一致**）⇒ 色表改动进了 sidecar。

**冒烟（部署版 sidecar，临时副本起）**：`xsdir-check` / `mcnp-detect` / `diff-inp` 全 **ok**；
`meshtal-texture`（走 `_meshtal_worker` 子进程，**正是 colormap 所在的链路**）**status=ok**，
返回 `scalarRange 1.24e-5~1.52e-5` + 帧字段齐；`preview-3d` **ok**（3 个 STL）。
> 冒烟笔记：`tests/fixtures/real_meshtal_jk.meshtal` 的 tally 号是 **14**（记忆里早先记过这条），
> 用 4 会得到 `KeyError: tally number 4 不存在` —— **那是夹具的计数号不对，不是缺陷**。

**⚠️ 待用户目视确认（本批两次改动都只有实机能判）**：① 出图是否为"轴线带量名称/单位、图题在图下居中、白底、
文字明显变大"；② **viridis 低值端很暗**，在深色屏幕上看低值结构可能比原来的亮蓝"显得更少"，
这是色表取舍（打印可辨 ↔ 屏幕亮底可辨）的必然后果 —— 如果观感不能接受，可只在**出图**用 viridis、
屏幕保留亮色表（代价：屏幕与出图配色不再一一对应，需用户拍板）。

### S8.11 截面界面 + 出图版面统一（2026-09-19 同日，**纯前端 · 版本仍 1.7.6**）

> **三态**：**已改 ✅ / 已提交 ✅ `169c4aa` / 已打包部署 ✅**
> （`node scripts/build-release.mjs` **311 s / EXIT 0** → 备份 `_backup_1.7.6_20260919_235617`（7878 文件）→
> 部署 + 冒烟通过；**主程序开窗后的观感仍待用户目视确认**）
>
> **部署细节**：exe **6,608,896 B**（内嵌新 bundle `index-C1-X34nn.js`，**不含**上一版 `index-BPp0bFCS.js`）/
> `python.exe` **32,514,579 B** / `_internal` 7867（总 7871）；6.2 逐文件校验 `target/release/python.exe`
> 与 `binaries/` MD5 一致（`C4A23910…`）；**`sync-sidecar` 又自报"陈旧"并自动覆盖**（这个坑每轮必中）。
> **冒烟**：`xsdir-check` / `mcnp-detect` / `diff-inp` / `preview-3d`（3 STL）/ `cross-section`（2 层多边形）全 ok。
> **收尾**：冒烟用的临时副本起完即删；清理时发现**一个残留 sidecar 仍占着 5001**（端口守卫要防的就是这个），
> 已杀掉并确认端口释放 —— **交付前务必确认 5001/8100 空闲**，否则用户启动会被"接到旧进程"（§6 坑 1）。

> 用户连续三条实测驱动：「3D 预览中的截面界面也排版有问题」→「图标题在下，你几乎都没修，
> 把这些能导出图的抽成一个公用函数」→「各种截面的矢量图，材料边界描边还是太重了」。

**A. 出图版面抽成公用函数（用户要求，本轮最重要的一条）**

**动机是一个真实漂移**：S8.9 我只把**栅格渲染器** `figureCanvas` 改成"图题在图下"，
**矢量渲染器 `vectorFigure` 没同步** ⇒ 二维矢量图（截面 / tally / 切面 / keff）**全部还是标题在上**，
用户导出的截面图就是证据（标题压在图上，还和面板 heading 的下划线叠字）。

- 新增深模块 **`gui/src/export/figureLayout.ts`** = 出图版面的**单一权威**：
  `layoutFigure()`（总高 + 内容行/图下区 y）、`figureTextBlocks()`（"图题/图注该画在哪、多大、什么色、怎么对齐"
  的文字块清单）、`figureTitleText()`、`joinNoteParts()`；
- **两个渲染器只负责"把字画上去"**，坐标一律取自该模块 ⇒ "两份实现各写一遍"的漂移从结构上消失；
- **8 个能出图的视图**（3D 预览 / 3D 体积 / 3D 径迹 / 演示源 / 二维截面 / Tally 通量 / fmesh 切面 / keff 收敛）
  走同一条路 ⇒ **改一次，8 张图同时变**；
- 新增 `gui/test/figureLayout.test.ts`（13 例）：图题在图下 / 图注在图题下且逐行不重叠 / 图题居中图注左对齐 /
  总高公式不漏项 / 无图题图注时不凭空多留白 / **两渲染器同版式对拍**（断言矢量 SVG 的文档顺序：
  内容 → 图题 → 图注）/ 图题不带图序 / 描边换算。

**B. 矢量图补上材料色块图例**

`CrossSectionView` 原来只把材料名拼成一行 caption（`材料：M12、M1…`）—— 黑白打印后读者无法把图里的颜色
对应到材料。现在 `VectorFigureSpec` 新增 `legend`（带色块、单列竖排、上限 260，与栅格版 `legendMetrics` 同口径），
`build2dSpec` 增加 `legend` 入参，截面图传材料图例 ⇒ **"图内符号必须有说明"这条期刊硬要求才算真满足**。

**C. 材料边界描边"太重"——根因是换算方向写反了**

原实现 `strokeWidth: 1.5 / zoom` 把数值写在**用户坐标**里 ⇒ ① 默认 zoom=0.9 时线反而更粗（1.67）；
② 滚轮拉远 zoom→0.2 时粗到 7.5；③ **导出时面板再被 `panelTransform` 缩放一次 ⇒ 边界比屏幕更重**
（用户这次报的就是导出图）。修法两层：
- **屏幕**：`vector-effect="non-scaling-stroke"` + 固定 **1.2px**（线宽不再随 zoom 漂移）；
- **导出**：新增 `snapshotSvg({ strokeScale })` —— 该属性**出了文档不保证生效**（合成进版面再光栅化时会被
  当成用户坐标乘缩放比）⇒ 导出时**摘掉属性并把线宽换算成用户坐标**（`1.2 / strokeScale`），
  面板无论缩放多大，边界始终 1.2px；描边不透明度 0.9 → 0.85；
- 回归：`figureLayout.test.ts` 2 例（传 strokeScale → 摘属性 + 线宽 4.8；不传 → 原样不动）。

**D. 截面界面右栏横向溢出（用户第一条实测）**

根因：共享控件 `PlaneControls` 在 `showStepButtons` 打开时，步长行要塞 4 个按钮 + 1 个输入框
= **实测 274px**，而截面右栏 `width:220` 去掉左右 padding 只剩 ~190px ⇒ **横向溢出 + 面板底部横向滚动条 +
控件被切**。修法两条一起上：**面板 220 → 280**，并给 `PlaneControls` 新增 **`stacked`** 模式
（步长/步进拆成两行，每行 ~148px）；顺带给"旋转"行加 `minWidth:0` + 各控件 `flexShrink:0`
（实测 `复位` 右边缘 950 vs 面板右 960，**未裁切**）。
> 教训：**共享控件挪到更窄的容器里必须实测**（`scrollWidth > clientWidth` 一量就出来）；
> 我把 `PlaneControls` 放到截面栏时没量，才让它溢出了这么久。

**E. 顺带清掉的重复信息**

截面导出的面板 heading（`截面 0X+0Y+1Z=0`）与副标题（`切割平面 0X+0Y+1Z=0`）**写了同一个方程**，
而 heading 的下划线正好落在副标题基线上 ⇒ **叠字 + 多一条红线**（用户截图可见）。
现已**去掉面板 heading**，方程只留在图注一处。

**门禁（实跑）**：tsc 两档 **0**；vitest **95 files / 794 passed**（+13）；`vite build` **0**。
**实机复查**：截面面板零横向溢出、控件齐全（平面/步长/÷2/×2/步进/旋转/复位）、材料边界为细线、图例与栅元列表在位。

**⚠️ 留一个待用户拍板的口径**：截面视图**屏幕底色仍是深色**（`#0a0a1e`），而导出是白底论文配色
⇒ **屏幕看到的配色与导出图不一致**（3D 出图已统一成"印刷墨色"，截面还没）。改屏幕底色观感变化大，未擅自改。

## S7（上一批次）格阵编辑器「改范围就乱序」（2026-09-15，**纯前端 · 版本仍 1.7.6 · 未重打包**）

> **三态**：**已改 ✅ / 已提交 ✅ / 已打包部署 ❌ 不需要（无后端/无 sidecar 改动）**

### S7.1 用户报告：「fill=-8:8 -8:8 0:0 的填充是对的，改成 -9:9 -9:9 0:0 就乱顺序，是你定义有问题？」

**结论：MCNP FILL 条目序（行主序、i 最快）与生成/解析/3D 展开都没错，错的是编辑器"改尺寸时保留已涂色格位"那条 UI 逻辑。**

**真根因**（`gui/src/utils/lattice.ts` 旧 `resizeLatticeCells`）：

```ts
return fresh.map((c, i) => (prev[i] ? { ...prev[i] } : c));   // ← 扁平下标对齐
```

范围 -L:M 一变，**每格的绝对格位号整体平移**，扁平下标不再指同一格位 ⇒ 整张图被沿对角线拖走。
实测（17×17 居中同心环 → 19×17）：环心跑到偏右下，左上角出现"实心块 + 旧行残影"——**这就是"乱序"的真身**。
用户看到的第二张图（左上角一整块同色）正是索引对齐的指纹：旧图前 N 格被原样塞进新图前 N 格。

**修法**：按**绝对格位坐标**搬运。range token `"a:b"` → 起始绝对号 = a、格数 = b−a+1，
扁平 `idx = (i−start0) + nx·((j−start1) + ny·(k−start2))`；旧格位换绝对号后只搬落在新范围内的
（越界丢弃 = 缩范围裁剪；扩范围新增格位取默认涂色笔）。新增小工具 `rangeDims` / `rangeStarts`；
`resizeLatticeCells(prev, fresh, freshDims, freshRange, prevRange)`；`LatticeEditDialog` 用 `useRef` 记住上一版 range 传下去。

**跨语言口径**：与 Python `_range_count` / `_dir_counts_from_range`、后端 `expand_positions` 的 −N:M 居中公式一致；
实测 MCNP 往返（19×17 → `format_fill_cards` → `parse_fill_tokens`）条目序**逐项相等**。

### S7.2 门禁与验证

- 新增回归：`gui/test/lattice.test.ts` 3 例（居中变宽 / 单轴加宽不错行 / 缩范围裁剪）+
  `gui/test/latticeEditDialog.dom.test.tsx` 1 例端到端（涂两个对角 → 改 `x 向左` 8→9 → 断言新格位号 1 与 305）。
- **vitest 737 passed / 90 files**（基线 733 + 新增 4），`tsc --noEmit` + `tsc -p tsconfig.test.json --noEmit` 两档 **EXIT 0**，
  `vite build` EXIT 0；pytest 未跑（**无后端改动**）。
- **打包口径**：本次只改 `gui/src`（前端源码），`gui/dist` 由启动脚本每次自动构建；
  **不重打包 installer**（sidecar/后端逐字节未变，重打包是纯浪费）。

## S6（当前批次）计数卡回显根因 + 出图全链 + 自审修复（2026-09-17，**版本仍 1.7.6**）

> **三态**：**已改 ✅ / 已提交 ✅ / 已打包部署 ⏳（本次打包）**

### S6.1 用户报告：「室友打这个打包版后，发现计数卡界面手动改动后都会变回初始状态」

**排查路径（可复用的方法论）**：真 bug 只在**打包版**上出，源码版无 —— 一开始就排除了"渲染/组件 bug"，
因为两边前端代码同一份。逐一排除用 jsdom 回放（假后端 + 受控时钟）后确认：**唯一在打包版上"多出来"的
链路是 MCP `/workspace` 每 2 s 的回显**（源码版里 MCP 起不来 → 状态 off → 回显永不触发）。

**真根因（两层）**：
1. `deck_from_json` 只读 `data["tally"]`，而前端计数卡是**顶层 `deck.tallies`** ⇒ PUT 存空 → GET 回显 `tallies: []`
   → 前端 `useDeckSynced` 判定"不等价"整份采纳 ⇒ **计数卡被清空**。
2. **更隐蔽的第二层**（自审时才揪出，第一层修完**并没真修掉**）：回显 deck **同时带** `tally.tallies`
   （后端 `asdict(DeckData)` 产出）与顶层 `tallies`（手工拼的）⇒ 前端把回显并进自己 deck 后两处各说各话
   ⇒ 第一层那条"仅当 `tally.tallies` 为空才用顶层"**永远不生效** ⇒ **多轮往返下用户新增/删除计数卡被静默丢弃**
   （实证：新增 F6 后仍 `[14]`，删 F4 后仍 `[14]`）。
   **修法**：前端口径里把 `tally` 子对象的 `tallies` **摘掉** —— 一个概念只留一个位置。

**同类放大器（一并修）**：
- `startMcpHttp()` 没有 8100 端口探测（同文件里 5001 有）⇒ 残留旧进程占端口时，新 sidecar bind 失败静默退出，
  前端连到**旧进程的旧工作区**却显示"已就绪" ⇒ 界面莫名回弹且**无任何报错**。加探测：占用则复用并打日志。
- 多实例共用 8100：A 的 PUT 会把 B 的界面整份覆盖。加**归属隔离**：前端每实例一个 `CLIENT_ID`，随 PUT 上报、
  后端记成 `writer` 并在 GET 带回；**只采纳自己写上去的工作区**，被接管时 AI 面板显式提示。

### S6.2 出图全链（用户："在 3D 预览界面加按钮导出当前界面图片；截面导出矢量图；tally/fmesh/径迹都能出图"）

**用户逐条定案**：WYSIWYG 当前取景 **×2 像素**；合成图（视图+图例/元信息，**绝不截界面控件**）；
二维出 **SVG+PDF**、矢量优先、**透明底**；导出**一律论文配色**（白/透明底、黑轴）；范围含 keff；
每窗口一个导出按钮、**不弹格式对话框**；跨窗口批量导出**明确砍掉**（"哪用得到？"）；fmesh 切面要**自由平面 + 步长 + 成叠导出**并复用既有模块。

**新增 `gui/src/export/` 11 模块**（详见长期记忆模块表）：plotTheme / captureFrame / figureCanvas / vectorFigure /
contour / planeSample / cjkFont / saveFile / figureSpecs / exportFigure / useFigureExport。

**关键技术事实（写进代码注释，勿再踩）**：
- WebGL 渲染器**都没开 `preserveDrawingBuffer`** 且按需渲染 ⇒ 取图必须"**同一任务内先同步 `render()` 再取像素**"，
  异步（等 rAF）必得空白。四个渲染器各加了 `renderNow()`。
- 3D **无法矢量化**（WebGL 光栅）；坐标轴/刻度是 `CanvasTexture` sprite（在 canvas 内，自动进图）；
  材料图例/色带是**画布外 DOM**，必须自己画进图。
- 中文字体：PDF 标准字体不含中文 ⇒ 从 `C:/Windows/Fonts` 读**纯 TTF**（避 `.ttc`）；
  **实测 jsPDF 会做字体子集化**（16 MB 字体 → **0.26 MB PDF**）；仍留 6 MB 上限 + 位图降级兜底。
- `svg2pdf.js` 的 package.json **无 `exports`** ⇒ Vite 默认取 **UMD**，在 ESM 下加载即崩
  （`Cannot read properties of undefined (reading 'jsPDF')`）⇒ `vite.config.ts` alias 钉到 ES 构建。
- 等值线 marching squares：**共享边必须规范化**（同一条边从任一相邻 cell 看都是同一个插值点），
  否则浮点尾差让闭合环串不成；鞍点（case 5/10）用**格心值**消歧，否则端点点度数 > 2、贪心串链必断。
- 取样口径：体积场按**节点口径**（`min + k*(max-min)/(size-1)`）—— 与 `sliceFrame`、体积渲染一致；
  曾按"体素中心"口径改，实测末体素 210 被算成 172.9，**已撤回**。

### S6.3 自审（用户："自己调用相关 skill，review 一下有没有 bug"）

用 review skill 跑三轴并行子代理（Standards / Bug / Spec），**逐条实证核实、不照单全收**：
- Bug 轴报 11 条 → **确认 9 条、全部已修**（致命 4：多轮往返吞计数卡 / 成叠导出每片内容相同 /
  `splitSvg` 丢 viewBox 致截面导出缩成墨点 / 层号被当 `D/系数` 致滑杆跳）；**判非问题 2 条**；
  **我自己照 agent 建议改错的 1 条已撤回**（取样口径，见上）。
- Spec 轴：keff/扫描导出缺失（**keff 已补**；扫描按用户判断**不做**——它是交互分析面板、天然多图，
  正确形态是"批量导出选中组合"，不是单按钮）；切面图缺色阶刻度（**已补** `trailing` 色带面板）。
- Standards 轴：**依赖红线违规**（见长期记忆）已登记追认；色表重复**已修**（`plotTheme` 改为从契约锚点
  `colorize.WEATHER_STOPS` **派生**，`ColorLegend` 内联色一并收敛）；文档欠账已补。

**门禁**：pytest **996** / vitest **731（90 files）** / tsc 两档 **0** / vite build **0**。

### S6.4 打包（2026-09-19 凌晨，**版本仍 1.7.6**）—— 一次打包连踩三个"后端旧"的坑

**链路实录**：`npm run build:release`（新增的一步式脚本）→ PyInstaller 清缓存重建 → 覆盖
`src-tauri/binaries/` → `sync-sidecar` 镜像 + `--require-target` 自检 → 备份
`D:\MCNP\_backup_1.7.6_20260918_235527`（7877 文件）→ 部署 `D:\MCNP\MCNP输入卡生成器`
（exe **6,854,656 B** / python.exe **32,514,167 B** `F9B3A2BE…` / `_internal` 7867 文件 /
README 13095 B / AI接入.md 3798 B）→ 冒烟。

**冒烟（部署版真实 HTTP）**：`xsdir-check` 200（xsdir 7925）/ `mcnp-detect` 200 / `diff-inp` 200 /
`lattice-extent` 200 / `import-step` 200；MCP `/workspace` 往返实测
`writer=deploy-smoke · tallies=[14] · tally 子对象无 tallies · grids 在位` ✅（本次修复核心场景）。

**★ 三个坑（都表现为"版本号新、后端旧"= 修复完全不生效，且**冒烟才发现**）**：
1. **坑 6.7 落点冲突**：PyInstaller 默认写 `gui/dist/python/`，而 `vite build` **清空 `gui/dist/`**
   ⇒ "先 PyInstaller → 再 build:app"会把刚打好的 sidecar 删掉，`sync-sidecar` 随后把
   `binaries/` 里**上一次的旧 python.exe** 铺出去，还报"✅ 已是最新"。
   **根治**：PyInstaller 用 `--distpath dist_sidecar`（与 vite 的 dist 物理分开）；
   `sync-sidecar` 加守卫（产物缺失即中止并给正确顺序）。
2. **坑 6.8 PyInstaller 增量缓存**（本次最隐蔽的一个）：`gui/build/mcnp_sidecar/` 残留上次 Analysis，
   PyInstaller 据此**复用旧模块字节码** —— 实测 `inputcard_mcp/server.py` 已改，新产物的 PYZ 里
   仍是 **09-12 的旧代码**（`python.exe` 哈希与旧版**逐字节相同** `D943A87D…`）。
   **根治**：每次构建前**强制删 `build/mcnp_sidecar`**；判定手段 = 读 PYZ 归档或直接冒烟行为。
3. **坑 6.9 `binaries/` 才是同步的比较源**：`sync-sidecar` 只比对 `src-tauri/binaries/` 与
   `target/release/`，**不会自动去 `dist_sidecar/` 取新产物** —— 不先覆盖 `binaries/`，
   它比对"一致"的是两份旧货（本次实测：报了两次"已是最新"，实际全是 09-17 的旧 exe）。
   **根治**：`build-release.mjs` 第 ③ 步显式覆盖 `binaries/`。

**部署踩坑（我犯的）**：第一条 `robocopy /MIR` 把整个 `target/release` 镜像进交付目录，
把 `deps/` `.fingerprint/` `.cargo-*` `bundle/` `wix/` `mcnp_ui.pdb` 一并灌入，
还用源目录里的**同名空文件**把 `AI接入.md` 覆盖成 0 字节。已即时修正（删垃圾 + 重拷文档）。
**教训**：部署**只拷三件套 + 两个 md**（手册第 7 步），别图省事 /MIR 整个 release 目录。

**新增构建入口**：`npm run build:release`（脚本 `gui/scripts/build-release.mjs`）——把"清缓存 /
独立落点 / 覆盖 binaries / 严格自检"四件事固化，避免再次出现隐藏顺序依赖。

---

## S5（上一批次，详情见 `docs/CHANGELOG.md` 与下方归档条目）几何曲面语义全类型审计 + 11 类修复；+ S5.3 源分布卡/源演示按 C810 重核；+ S5.4 打包坑 6.2 根治（2026-09-16 ~ 09-17）

> **用户报告**：「我看几何里圆锥面解析有问题」→ 要求"先查所有面类型有没有类似问题，再修" → 提供权威源 `D:\MCNP\MCNP6\C810.pdf`。

### 方法（可复用）
真值 = C810（PyMuPDF 抽文本，逐页核对 Table 3.1 / §3-14 环面与锥例 / §3-17 三点平面 / §3-18~21 宏体）；
43 用例 × 3 路径数值对拍：体素 `voxel_csg.surface_fn` / 3D `_freecad_csg_worker.make_halfspace` / 2D 截面 `_freecad_cross_section_worker.make_halfspace`。
**教训**：① 别用成千上万次 `isInside` 采样（OCC 点分类慢，两次超时）——用"少量决定性点 + 1 次 Volume"；
② 随机点不符率**不是**严重度（ELL `Rm<0` 整块失效只命中 2/3000）；③ 真值先自证（手册例题回代、MCNP 自打印系数），否则会拿错真值去"证明"代码有 bug。

### 查出并修复的 11 类
1. **圆锥**（用户报的那类）：半径取 `1/√t²`（应 `√t²`）、顶点放轴端（应卡片顶点）、`±1` 只当整体反号（应选叶片；C810 §2.C.1"朝 +轴 延伸到无穷的那一叶" + 3-14 例2"锥外为正侧"）、**K/X 用 Y 轴 / K/Y 用 X 轴**；双叶锥（省略 ±1）pymcnp 拒收 → parse 前补 0（否则静默丢面）。
2. **三点平面 P_1**：C810 §3-17 感度规则（原点负 / D=0→C>0 / …）未实现 → 一半点序整体翻面（4000/4000、体积 40000 vs 24000）→ 新增 `quadric.plane_from_points` 供三路径共用。
3. **SQ 的 D/E/F**：C810 是 `+2D(x−x̄)+2E+2F` **线性项、无交叉项**；旧 `sq_to_gq` 当 xy/yz/zx 交叉项（D=5 时体积 45340 vs 63183 = 28%；D=E=F=0 的球/椭球恰好等价 → 长期没暴露）→ 修正展开，两处 worker 内联副本改为调用同一函数。
4. **ELL**：Rm>0 旧式 `d1+d2 ≤ 2·Rm`（半长轴当成 Rm，应 Rm/2）且与 FreeCAD 路径互相矛盾；Rm<0（中心+长轴矢量）两路径皆废 → 新增 `quadric.ellipsoid_field_fn`；FreeCAD 改**真椭圆弧**回转（"三点圆弧"其实是圆；"球+非均匀缩放"被实测否决：`isInside((2.2,0,0))=True` 而半轴只有 2）。
5. **ARB 面码**：手册"第 4 位为 0 则忽略该点"，旧 `(digit)-1` 把 0 变索引 −1 → 取第 8 角点；体心/面心用 8 角点（含未用零三元组）平均 → 远离原点翻面（3738/4000、体积 4372 vs 64000）→ 新增 `quadric.arb_face_indices` + 只用被引用角点定体心；FreeCAD 的 ARB 改**面半空间求交**（`makeShell/makeSolid` 绕向不一致时给出负体积实体 → `box.cut` 静默失效，实测 Volume=−275）。
6. **环面 TX/TY/TZ**：体素完全不支持；FreeCAD 的 TX/TY 把管心放在**轴上**（OCC 报错丢弃）、TZ 丢 C；截面 worker 连 `_make_torus_halfspace` 都没有 → 新增 `quadric.torus_field_fn/torus_aabb`；FreeCAD 按"径向偏移 A + 椭圆管（B 轴向 / C 径向）"回转（`Part.Ellipse` 要求 major ≥ minor，否则 `OCCError: Axis value is invalid` → 退化成整盒）。
7. **X/Y/Z 点定义回转面**：体素不支持；FreeCAD 折线近似且 1 点平面体积 64000 vs 24000 → 新增 `quadric.point_surface_field_fn`（1/2/3 对坐标 = 平面/柱/单叶锥/回转二次曲面，锥用**带符号** tan）+ FreeCAD 精确原语/分段回转（q<0 段必须单独成体：贴着轴的重复顶点会让 `Part.Face` 判 invalid，整块作废）。
8. **宏体可选尾项**：REC 10 项（第 10 项=短轴半径，方向 H×V1）、RHP 9/12 项（s/t 由 60° 旋转推出）、BOX 9 项（某维无限）→ 旧实现"pymcnp 少项=None → 序列化 TypeError → **整个预览 500**"或"pymcnp 拒收 → 静默丢面"；新增 `quadric.{rec_params,rhp_params,box_params}` + parse 层补零；**HEX 是 RHP 同义词但 pymcnp 无 Hex 类 → 静默丢面**，parse 层改写助记符。
9. **截面 worker 复制不全**：缺 12 个 helper（环面/SPH/REC/BOX/WED/RHP/HEX/ARB/X-Y-Z 全 `NameError` 缺块；`_plane_halfspace` 也没有 → 一般平面被做成面片）→ **删除副本，委托 `_freecad_csg_worker.make_halfspace`（单一实现）**。
10. **AABB**：`_surface_negative_aabb` 把"负号二次型"（f<0 = 无界外侧）当有界内部 → 裁剪（GQ 球负系数 172800 点越界）；`classify_gq/gq_aabb` 对斜置柱误称三轴有界；`classify_gq` 容差 1e-6 → 1e-3（手册 3-12 例3 的 `-.866` 舍入使斜置柱被判成椭球 → 假盒 y=±257、放大 2086×）→ 修 + 加"盒外探针"安全网。
11. **facet 引用（`1.1`）**：`_geometry_ast_to_json` 里 `int('1.1')` → ValueError → 整次预览 500 → 改为 `["facet",n,f]` 节点 + 跳过该栅元并在响应 `skipped_cells` 归因（几何求值仍不支持，属能力缺口）。另修 `_surface_extent_values` 环面丢 C（bound 少算；A=1000/B=100/C=500 由 1400 修正为 2050）。

### 验收（实跑）
新增 `tests/unit/test_surface_semantics.py`（31 例，逐条标 C810 出处）+ `tests/unit/test_voxel_csg_cone.py`（12 例）。
对拍：体素 44 用例 **0/4000** 不符、AABB **无问题**、TR 7 类 **0/3000**、FreeCAD 两 worker 44 用例决定性点 **全 0**；
`python -m pytest tests/unit tests/parser -q` = **853 passed / 1 failed**（唯一失败 `test_meshtal_worker::test_worker_spawn_dev_mode_bad_tally_error` 已用 `git stash` 对照确认是**既有环境问题**：Windows GBK 控制台解码 worker 输出）。
**端到端复验**（走生产解析链 `parse_surfaces` 同口径的 3 处补全 + `_pymcnp_surf_to_dict` → CSG worker `main()`）：
一个 deck 同时放 `1 KZ 0 0.25`（双叶锥）/`2 REC … 1`（10 项）/`3 RHP 0 0 -4 …`（9 项）/`4 TZ 0 0 0 3 1 1`（环面）/`5 X 5 0`（1 点平面）→
**warnings 与 cell_warnings 均为空**，5 个栅元体积全部与解析值 0.00% 相符（4188.79 / 62.83 / 83.14 / 59.22 / 40000）。
文档：`MCNP6_曲面卡格式参考.md`（环面 A/C 抄反、锥面 ±1 语义）、`C810_卡片格式详细.md`（锥面方程写反、SQ 行）及其 `gui/public/docs` 副本。
**⚠️ 未提交、未打包**；审计脚本 `_tmp_audit_*.py` / `_tmp_truth.py` 已删。

### S5.1 续：3D 预览图例读不到「材料」页注释（2026-09-16 同日，用户报）

> **用户报**：「3D预览界面会读不到材料页中定义的材料注释，顺手修复了」→ 追问后**用户给出职责边界**：「材料显示接材料页，栅元信息接栅元定义，不应该是这种逻辑吗？」

根因是**职责串源**：`MaterialLegend` 的注释槽被塞的是**栅元注释**
（`Preview3D`：`cellViews.find(cv => cv.mat === e.mat)?.comment`；`CrossSectionView`：`comment: cd.comment`），
「材料」页的 `MaterialData.comment` 从未被查过 —— 栅元一般没写注释 ⇒ 图例只显示 `M1`。
（我第一版按"材料注释优先 + 栅元注释回退"改，被用户否掉：同一材料多栅元时会随机显示某个栅元的注释，
语义错且不确定；正确边界是**两源不互串**。）

修法：新增纯模块 `gui/src/utils/materialLegend.ts`（`materialComment` / `materialLegendEntries`，**只**吃材料表）；
`Preview3D` / `CrossSectionView` 图例改走它；材料表在三处接齐（3D 主窗口 `matList = materials ?? deck.materials`、
3D 独立窗口桥本就带 `{number, comment}`、**截面窗口新增桥字段 `materials`**）。
栅元注释留在栅元列表（`CellList` 行尾）不动。

测试：`gui/test/materialLegend.test.ts`（7 例，含**调用点源码锁**：图例实参里不得出现 `cv.mat`/`cd.comment`/`c.comment`，括号配平扫描取实参）
+ `gui/test/materialLegend.dom.test.tsx`（3 例）。门禁 vitest **638/0**（81 files）+ tsc 两档 **EXIT 0**。

### S5.2 续：TRn + 锥面（及一切"先裁剪再变换"的曲面）几何错位（2026-09-16 同日，用户"k/z 解析还是不对"驱动）

> **用户的疑问其实指向两件事**：① 他看到的"不对"是我**部署前旧进程**的读数（Python 模块进程内加载、不热重载；我重启后端后同一张卡就对了 —— 这也是他问"为什么后来唤醒的程序就对了"的答案）；② 顺着这条线**真查出一个 bug**：`TRn` 引用的曲面。

**根因**：TR 曲面旧走 `T(盒 − 实体)` —— 把**已裁剪**的结果整体平移/旋转，既不是原曲面也不是原盒。
实测 `101 2 K/Z 0 0 0 0.25 1` + `TR2 5 0 0` 的 STL 包围盒是 `x[-500,10] y[-500,500]`（正确应 `x[0,10] y[-5,5]`）。
圆柱当年靠 `_make_primitive` 特例（先变换无界圆柱再裁剪）绕开了，**锥/球/平面/宏体全中**。

**修法（两 worker 同一口径）**：局部盒取 `B_loc = √3·B + max|平移|`（保证旋转后仍覆盖世界盒）
→ `make_halfspace(type, params, B_loc)` → `apply_trn` → `shape.common(世界盒)`。
等价于"先变换无界曲面再裁剪"，且**每种曲面类型内部实现都不用改**；`_make_primitive` 特例随之删除。
附带补：引用 `TRn` 但请求里没有该 TR 卡时**留告警**（旧行为静默按未变换处理 → 几何悄悄错位）。

**运行期实证**（网页端后端，真实 HTTP + STL 包围盒）：`K/Z`+平移 ✓ `x[0,10] y[-5,5] z[0,10]`；
`K/Z`+旋转90° ✓；`CZ`+平移 ✓ `x[3,7] y[-2,2]`；`PZ`+平移 ✓ `z≤25`；`S`+平移 ✓ `x[3,7] y[-2,2] z[-2,2]`；
另用生产 payload（`parse_surfaces`+`_pymcnp_surf_to_dict`+`_compute_bound_from_surfaces`）直喂 worker 复核一致。
新增源码锁回归 `tests/integration/test_preview3d_worker.py::test_worker_tr_surface_builds_in_local_box_then_transforms`。
门禁：`pytest tests/ -q` = **959 passed / 1 failed**（同一既有 GBK 环境失败）。

### S5.3 续：源分布卡文档 + 粒子源演示「按 C810 重核」（2026-09-16 同日，用户"对比 C810…有错吗"→"然后看粒子源演示是否也因用了错误的知识而设置错了"→"都修"）

> **方法上的关键一步（值得复用）**：用户要求"你要确定这是错的然后才能改"。于是把 C810 3-63 ~ 3-67 的 **41 条原文片段**当查询串，在两份派生文档里做**子串匹配**，结果 **41/41 全部缺失**——把"我觉得描述不清晰"变成"文档里确实没有这条"。**先把"错"与"缺"分开**，再动手。

**A 批（文档 + 文案）**：§三 从 64/57 行重写为 **191 行**（`app/docs/源分布卡说明.md` + `gui/public/docs/源分布卡说明.md`，两份逐字一致）。3 处**写错**被改：`A` = 概率密度**定义点**（不是"概率密度点"；点间线性插值）、`−4` 的 **a 不是半高宽**（FWHM = a·(ln 2)^½）、`−3` 公式/默认值；Table 3.4 补 −7 备用谱与全部默认值；示例 1 的 `SP1 D0` → `SP1 D 0`（H 分布首项必须是 0 占位）。代码侧：`distributions.py` 的「A 三角 / S 对数」措辞（**用户可见报错**）改成 C810 原文，并加源级锁测试。

**B 批（演示层 8 个缺陷 + 2 个带外，全部先复现后修）**：面源方向绕 +Z 而非**面法线**（`NRM` 全仓无人读、球面源 102/200 朝球心飞）；平面源位置撒在 **±1000** 的面上（POS/RAD 被忽略）；`SI x`+`SP −21/−31` 的对称默认只对了一半（EXT 负半轴整段丢失）；`SI S` 的 **D 前缀分布号**直接 `ValueError`；`SP V` 只声明不校验；`SP −21/−31` 不给参数被判错（C810 有变量默认）；`SDEF TR=n` 完全未消费；前端 `distDual.parseDs` 与后端 DS 口径不一致（前端丢一个值）。
**带外（只有"到真实后端跑一遍"才暴露，单测手写 geometry dict 全绿所以长期潜伏）**：① `_prepare_source_geometry` 里 `vc._surface_transform(d, tr_cards)` **多传一个参数** ⇒ `TypeError` 被吞 ⇒ `surfaces` 恒空 ⇒ **`SDEF SUR=` 面源在真实后端 100% 报「曲面未定义」**；② `CX/CY/CZ`（轴对齐圆柱缩写 ≡ `C/X`）pymcnp 解析不了且 except 只兜 P 系数 ⇒ **曲面被静默丢弃**（3D/截面/STEP/源演示同受影响）。两条都修了，并补 `tests/integration/test_source_demo_geometry.py`（6 例）堵住"单测接缝"。
**顺带性能**：`_inverse_cdf` 原本每次抽样重算 4096 点积分（4.2 ms/次）→ 结构化键网格缓存（**不可用 `id(pdf)`**，id 复用会串概率网格，实测均值 0.667→0.709）⇒ 后端测试 34 s → 19 s。

**原"已知未修"三项已于同日全部实现（用户追问「为什么不修？」驱动）**
| 项 | 实现 | 实测 |
|---|---|---|
| `SP V` 体积加权（C810 3-64 `Probability is proportional to cell volume (times Pi if present)`） | `voxel_csg.cell_volume()`（确定性**分层 MC**，同 seed 可复现）+ `api_server` 逐栅元 `cellVolumes` + `_resolve_v_probs()`（权重 = 体积，给了 Pi 再乘 Pi；**缺体积按 C810 的 FATAL 语义报错**，不静默等概率） | 球 33.51 / 壳 79.59 → 理论占比 0.296，抽 4000 粒子实测 **0.295** |
| `SI S` 分布号 0 = 变量默认值 | `_var_default(var, e, sdef_fields)`：优先读 SDEF 卡**字面值**（`SDEF ERG=2.5` ⇒ 2.5），读不到才退回 Table 3.3 | 单测：`ERG`→2.5、`WGT`→7、读不到→14 |
| `SDEF TR=Dn`（变换分布） | `_sdef_trn(rng)`：`SI L` 列 TR 号 + `SP` 概率 → 抽 TR 号 → 查卡 → 变换位置/方向 | 单测：两个 TR（z=100/200）都被抽到且位置确实变换 |

> **教训（写下来）**：我上一轮把这三项写成"已知未修（诚实登记）"，措辞像是在陈述客观限制，其实是我**不想扩大改动面**就收了口。**"登记"不等于"说明"**——要么真修，要么明说"成本/收益权衡后不修"。实际代价：三项合计约 1 小时，全部可测。

**门禁**：pytest **989 passed / 1 failed**（`test_meshtal_worker.py` GBK 环境失败，`git stash` 复核为既有）；vitest **644/0**（82 files）；tsc 两档 **0**；`vite build` **0**（已重建 `gui/dist`）。

**⚠️ 本批自身引入并当场修掉的回归（记下来防复犯）**：把 `CX/CY/CZ` **无条件**改写成 `C/X` 后，`CZ R` 两项式（`7 cz 0.3`）被改成 `C/Z 0.3`（少 2 个参数）→ pymcnp `InpError` → 曲面静默丢弃 → `test_api_contract.py` 的格元覆盖两例转红（其 `COV_SURF` 正是 `7 cz 0.3`）。**pymcnp 三种类的接受面各不相同**：`C/X·C/Y·C/Z` 认 4 项长式；`CX·CY` **什么都不认**；`CZ` **只认 `CZ R` 两项式**。⇒ 改写必须带条件 `len(_p) - _kw_idx >= 3`，并补回归 `test_cz_two_item_short_form_is_kept_verbatim`。

## S5.6 重打包部署（2026-09-17 第二轮，**版本仍 1.7.6**；含 S5.3 三项新实现）

**提交**：`cf0efd6`（SP V 体积加权 / SI S 分布号 0 / SDEF TR=Dn 三项实现 + 回归 + 文档）。

**链路（实跑）**：停部署版与 dev 后端 → PyInstaller **128 s / EXIT 0**（sidecar **32,512,851 B** + `_internal` 7867 文件）→ binaries 替换 → `npm run build:app` **69 s / EXIT 0**（vite 7.60 s → 构建前 sync ✅ → `Compiling mcnp-ui v1.7.6` 26.52 s → **构建后 sync 自动命中"python.exe 大小不符"并自动覆盖 + 复核一致 ✅**）→ `--check --require-target` ✅ → 备份 `D:\MCNP\_backup_1.7.6_20260917_014123`（7877 文件 / 242.2 MB）→ 部署（exe 6,627,840 B / python.exe 32,512,851 B / `_internal` 7867 文件，关键模块与文档全在位）。

> **6.2 第三次命中，且这次是"自动治愈"**：`build:app` 的收尾 `sync-sidecar --require-target` 自己发现 `target\release\python.exe` 与 `binaries\` 不一致 → 自动镜像 → 复核一致退出 0。**人工零介入**（前两轮都要我手动覆盖）。这就是把它做成构建一步的价值。

**冒烟（部署目录里的 `python.exe` 直接起 sidecar，真实 HTTP）**：`xsdir-check` 200（xsdir 7925）/ `mcnp-detect` 200 / POST `diff-inp` 200 / `lattice-extent` 200 / `preview-lattice` 200 / `validate-lattice-surfaces` 200 / `source-demo-sample` 200。
**五项运行期确认**：① 平面源 `x≡5`、`r≤3`、`dx∈[0.020,0.999]` 全正向；② `SI1 S D2 D3` ⇒ 能量 `{1,9}`；③ 球面源方向反向 **0/200**；④ `7 CX 0 0 3` 报「不能作面源」；⑤ CEL 球源 `|r|∈[0.681,4.995]`；**⑥ 新增 `SP V` 体积占比实测 0.307 vs 理论 0.296**（球 33.51 / 壳 79.59）。

**说明**：本轮冒烟用"直接起 sidecar"而不是双击 exe —— 因为第一轮我试图自动启动部署版时，用户正好手动关掉了窗口（我把 `Get-Process` 的一次报错误读成"启动即退出"，已撤回该判断）。**部署版主程序能否正常开窗需要用户目视确认**（我只验证了同一套 `_internal`/`python.exe` 的后端行为）。

## S5.5 打包部署（2026-09-17，**版本仍 1.7.6**：bug 修复批不升版）

**提交**：`e6f3a0c`（修复本体：11 类几何 + 面源/分布语义 + 带外 2 条 + 回归）、`acdc0b5`（打包链路 6.2 根治）、`<docs>(memory)`（本文件 + CHANGELOG 门禁计数与批次记录）。

**链路（用新命令，全程实跑）**：
1. 版本核对**六处**全 1.7.6（package.json / package-lock 两处 / tauri.conf / Cargo.toml / Cargo.lock / README 徽章）；
2. PyInstaller：`python -m PyInstaller --noconfirm mcnp_sidecar.spec` → **113 s / EXIT 0**；
3. binaries：sidecar **32,503,246 B** + `_internal` **7867 文件**（`preview_cache.py` / `source_sampler.py` / `vendor\geouned` 全在位）；
4. `npm run build:app` → **40 s / EXIT 0**（vite build 6.12 s → 构建前 sync ✅ → `Compiling mcnp-ui v1.7.6` 13.74 s → **构建后 sync**）；
5. 备份 `D:\MCNP\_backup_1.7.6_20260917_010859`（**7877 文件 / 242.1 MB**）；
6. 部署 `D:\MCNP\MCNP输入卡生成器`：exe 6,627,840 B / python.exe 32,503,246 B / `_internal` 7867 文件 / README + AI接入.md；文档两处都在位（`_internal\app\docs\源分布卡说明.md` 21,902 B、`gui\dist\docs\` 8 个 md 随 exe 内嵌）。

> **⚠️ 6.2 在本次打包里"又中了一次"，而且正好证明了为什么构建前同步不够**：第 1 次 `npm run build:app` 的**构建前** sync 报了 ✅，tauri build 也成功，但**构建后** `python.exe` 仍是 09/12 的 28,631,092 B（`binaries` 已是 32,503,246 B），`_internal` 却刷新了 ⇒ `tauri build` 在**编译期**用 `binaries\` 写 `target\release\`，**只写 `_internal`、不写 `python.exe`**。**修法**：`build:app` 收尾再加一次 `sync-sidecar --require-target`（同步 + 自检），`package.json` 已改并加单测断言"同步必须在 `tauri build` 之后"。

**冒烟（部署版真实 HTTP）**：主程序 29 MB + sidecar PID 25180 于 5001（**2 s 就绪**）+ MCP **8100** LISTENING；
`xsdir-check` 200（xsdir **7925** 条）/ `mcnp-detect` 200 / POST `diff-inp` **200** / `lattice-extent` 200 / `preview-lattice` 200 / `validate-lattice-surfaces` 200 / `source-demo-sample` 200；
**本批修复的运行期确认**：① 平面源 `SUR=5 PX 5` + `RAD=D1` → `x≡5`、`r≤3`、`dx∈[0.075,0.999]` **全正向**（此前该场景在真实后端必报"曲面未定义"）；② `SI1 S D2 D3` → 能量 `{1,9}`（此前 ValueError）；③ 球面源方向反向 **0/200**、min cos 0.049（此前 102/200 朝球心）；④ `7 CX 0 0 3` 报「**不能作面源**」而非"曲面未定义"；⑤ CEL 球形栅元源 `|r|∈[0.606,4.992]`。

**说明**：GET 打 `diff-inp`/`lattice-extent` 会 500 属正常（这两个端点只认 POST——按 `docs/fix-verification.md` 的冒烟脚本口径复核即 200）。

## S5.4 打包坑 6.2 根治（2026-09-17，用户"那个 6.2 坑改了吗？"驱动）

**坑的精确机理（带标记对照实验）**：`tauri build` **会刷新 `target\release\_internal\`，但不刷新 `target\release\python.exe`** —— 重建后 `python.exe` 仍是 09/12 的 28,631,092 B（我加的标记文件还在），而 `binaries\` 已是 09/17 的 32,487,958 B；`_internal` 两侧一致（7867 文件 / 214,579,036 B）。⇒ "版本号新、后端旧"= sidecar 两件套里只换了一半。

**根治**：`gui/scripts/sync-sidecar.mjs`（递归比对路径+字节数 → 陈旧则镜像 + 复核；`--check` 只查不改；无 target 则跳过）+ `gui/package.json` 的 `build:app`（vite build → sync-sidecar → tauri build）+ `tauri.conf.json` 的 `beforeBuildCommand` 串上 `sync-sidecar`（手敲 `tauri build` 也生效）+ `gui/test/syncSidecar.test.ts`（5 例）。手册 6.2 从"每次都踩"改为"已自动化"。

> **教训**：不要用"再补一个更详细的 6.2 人工核对步骤"去修流程坑——那只是把坑描述得更清楚，坑还在。要把它变成**构建命令里的一步**（且校验失败能自己纠正/报错）。

## S4（当前批次）STEP 导入 500 热修（2026-09-12，**仅重打包 sidecar 部署，未升版**）

> **用户报告**：「我导入 step 功能怎么炸了？」——部署版点「📥 导入 STEP」→ 后端 **HTTP 500**，前端弹出 `'CellRow' object has no attribute 'number'`。

### 根因（一个字段名过期，整条链路 100% 挂）

`gui/backend/api_server.py:_handle_import_step` 里**手写**了 deck 平铺序列化：

```python
[{"number": c.number, "material": str(c.material), ...} for c in (deck.cells or [])]
```

而 `deck.cells` 自 `f8f7fe6` 起已是 **`CellRow` 判别联合**（`kind` + 嵌套 `cell`），**没有** `number/material/density/surface_expr` 字段 ⇒ 每次 STEP 导入必然 `AttributeError`。2026-08 删掉 McCAD 兜底分支后只剩这一条路径，缺陷 100% 暴露；**该端点当时零测试覆盖**，所以静态审计与全量 pytest 都没抓到（pytest 908 passed 全绿也照样漏）。

### 修法（收敛到唯一序列化 seam）

- `app/step_importer.py` 新增 **`flat_cell_json(row)`**：吃 `CellRow` / `CellData` / 平铺 dict，出 `docs/contracts/api.yaml` 契约的平铺 5 字段（`number/material/density/surface_expr/comment`）；`kind=="raw"` 的 `#ifdef` 条件行 `{kind:"raw", text}` 原样透传，不丢行。
- **`geometry_deck_response()`** 内部统一走它；handler 只传 `deck.cells`，**不再手写字段映射**（同类漂移无处可藏）。
- 顺带修 `app/step_importer.py` 的 `from freecad_locator import ...`：补 `except ImportError → app.freecad_locator` 双导入（其余 app 模块都有，唯独它没有 ⇒ `import app.step_importer` 直接炸，测试无法在包路径下导入）。

### 回归测试（先红后绿，已实证）

`tests/unit/test_step_import_deck_response.py`（**8 例**）：CellRow 序列化不再炸 / 契约字段集恰好 5 键 / void 空密度 / raw 行透传保序 / 平铺 CellData+dict 兼容 / 空与 `cell=None` 不炸。
**红能力实证**：把 `geometry_deck_response` 临时回退成 `cells_list or []` → 该文件 **2 failed**（`'CellRow' object is not subscriptable`）；恢复 → **8 passed**。

### 端到端实证（HTTP 500 → 200）

自建反馈回路 `_loop_step_import.py`（仓库根，可复用）：FreeCAD 造 10×10×10 box STEP → 走前端同款 payload（`file.text()` → `data` 字段）POST `/api/import-step`。

| 目标 | 修前 | 修后 |
| :--- | :--- | :--- |
| 源码后端（dev） | HTTP 500 `'CellRow' object has no attribute 'number'` | **200** · cells=4 / surfaces 16 行 |
| **部署版 sidecar**（改前实测） | HTTP 500 同款 traceback（`api_server.py:2640`） | **200** · cells=4（1 实体 + 自动 void + Graveyard_in + Graveyard） |

### 附带修：GEOUNED 定位只在 FreeCAD 解释器里问得到

`app/step_importer_geouned.py` 的 `_resolve_geouned_path()` 原来只在**后端解释器**里 `find_spec("geouned")` —— 但 geouned 是装给 **FreeCAD 的 Python** 的（requirements.txt），开发机因此恒报「缺少 geouned 包: 」（路径还是空的）。现改为候选链：`GEOUNED_PATH` → 冻结 `_MEIPASS/vendor` → 后端解释器 → **FreeCAD 解释器子进程探测**（进程内缓存一次），且每个候选都经 **`_is_geouned_dir()`** 验证（须有 `geouned/__init__.py` + `geouned/GEOUNED/__init__.py`）——本机 FreeCAD site-packages 里那个**只含空 `GEOReverse` 的残缺 namespace 包会被正确拒掉**（旧代码只判 `isdir` 会当可用，worker 起来才炸 ImportError）。失败信息也改成可操作版（含 `GEOUNED_PATH` 用法）。**开发环境跑 STEP 导入需 `GEOUNED_PATH=D:\MCNP\GEOUNED`**。

### S4.1 续：GQ 栅元"奇形怪状/消失"+ 体积误差 4.6% → 0.3%（2026-09-12 同日，用户真实文件驱动）

**用户实测文件** `P:\dekstop\mcnp_export.step`（本程序导出的 STEP 再导入，18 栅元）。现象：**一部分栅元奇形怪状**。

**判据（可复用）**：GEOUNED 在 `csg.mcnp` 里给每个实体栅元写了 **`Vol=`**（从 STEP 算的真实体积）→ 拿它当尺子量我们 3D 预览产出的 STL 体积，误差一眼可见。修复前：7 号 **+22%**、8 号 **完全没有 STL**、9 号 **−24%**；其余栅元吻合（它们走 OCC 精确路径）。

**根因（三层，全在 `app/voxel_csg.py`）**：
1. `cell_aabb` 对**裸平面引用**（MCNP 正侧，如 `112`=PZ400 正侧）返回 None ⇒ 薄片丢下界。
2. `_aabb_intersect` **只比数值不看 `axes` 标志位** ⇒ `CZ` 无界轴占位 `(0,0)` 把 `-PZ405` 的 `z≤405` 压成 `z∈[0,0]` ⇒ 紧盒退化 ⇒ `_clip_aabb_to_bound` 兜底**整个 ±846 盒** ⇒ 体素 13.2 mm，而 8 号只有 **5 mm 厚** ⇒ 网格为空/糊块。
3. 细化盒顺序错（先取交后补 margin）⇒ 命中盒 z 只剩一个粗扫层时，margin 把盒子撑到 120 mm ⇒ 9 号厚度只剩 3.8 mm。

**修法**：① 新增 `_surface_positive_aabb`（轴对齐平面正侧=半空间，球/柱/锥仍 None）；② `_aabb_intersect`/`_aabb_union` 认标志位、无界轴统一 `±1e300` 哨兵；③ 细化盒 =「(命中盒 + 粗扫余量) ∩ 解析紧盒」（两者都是保守超集，取交才安全）。

**体积精修（−4.6% → −0.3%）**：二值 marching cubes 的顶点落在内外采样点**中点** ⇒ 曲面整体内缩半个体素，薄片受害最重且误差随分辨率**振荡**（res64→256：−4.7/+4.0/+0.5/−1.1%）。新增 `eval_cell_scalar`（min/max 组合的 CSG 标量场）+ `project_vertices_to_surface`（1~2 步牛顿沿梯度贴回真实曲面）：**MC 只负责拓扑，位置由标量场修正**。代价 +0.02 s/栅元（1M 三角的 graveyard +0.31 s）。

| 栅元 | GEOUNED Vol | 修前 | 修后（生产 res） |
| :--- | ---: | ---: | ---: |
| 7 | 78087.4 | 95425（+22%） | **77870.9（−0.28%）** |
| 8 | 38704.4 | 无 STL | **38573.0（−0.34%）** |
| 9 | 156514.1 | 119314（−24%） | **156176.9（−0.22%）** |

全模型 18 栅元（体素路径压力测试）全部 **≤0.6%**。视觉对照 `_cmp_cells.png`（前/后）、`_grid_after.png`（1–14 号逐个）：修复前 7 号是锯齿糊块、8 号空白、9 号带洞薄片；修复后均为干净圆盘。

**顺手关掉的坑**：`PreviewCache.GEOMETRY_CACHE_VERSION`（几何算法进指纹）——同一 deck 改算法后会命中**旧 STL**，用户"看不到修复"（本次实测踩到，手动清了 `D:\MCNP\memory\preview_cache`）；bump 到 2 后自动失效。

**未修（记录在案）**：① `classify_gq` 把这两个**抛物线柱面**误判成"半径 3.0 的椭圆柱"（特征值 ~1.7e-21 应视作 0），影响交叉截面路径；② void 15/16 仍不产 STL（改动前后一致，非回归）；③ 二值 MC 的剩余偏差由投影压到 <0.35%。

### 重打包/部署记录（两轮，均未升版）

**第 1 轮（15:30，sidecar-only）** —— 只改了 Python，前端没动：

- **备份**：`D:\MCNP\_backup_1.7.6_20260912_152729`（2304 files）。
- **PyInstaller**：`cd gui && python -m PyInstaller mcnp_sidecar.spec --noconfirm --distpath dist_sidecar --workpath build_sidecar`（**146 s**；产物 `python.exe` 28623682 B + `_internal` 2294 files，含 `vendor\geouned`）。
- **暂存/部署**：`dist_sidecar\python\{python.exe,_internal}` → `gui\src-tauri\binaries\`（exe 名仍带 target triple）→ `D:\MCNP\MCNP输入卡生成器\{python.exe,_internal}`（robocopy `/MIR`；部署目录多出的 6 个 `app\__pycache__\*.cpython-311.pyc` 是 FreeCAD py3.11 旧字节码缓存，被 `/MIR` 清掉，无影响）。
- **冒烟**：`/api/import-step` 200；`/api/xsdir-check`/`mcnp-detect`/`diff-inp` 均 ok。

**第 2 轮（16:32，完整链路：前端 + sidecar + tauri）** —— 本轮改了 TSX（导入即关窗），必须重出 Tauri exe：

1. **前端** `node .\node_modules\vite\bin\vite.js build` → `dist/assets/index-BIZ-a7qZ.js`（旧 `index-D8_xgTqs.js`）；构建后 grep 到新标记「STEP 转换中」确认入包。
2. **sidecar** PyInstaller **92 s**；日志明示 `Building because app\voxel_csg.py changed`；产物 `python.exe` **28631092 B**。
3. **暂存**：`dist_sidecar\python\_internal` → `binaries\_internal`；exe 同时写 `binaries\python-x86_64-pc-windows-msvc.exe` **与** `src-tauri\python-x86_64-pc-windows-msvc.exe`（后者是 `externalBin` 真正读取的位置）。
4. **tauri build**：`$env:RUSTUP_HOME='D:\rust\rustup'; $env:CARGO_HOME='D:\rust\cargo'; node .\node_modules\@tauri-apps\cli\tauri.js build` → `Finished release profile in 30.54s`；`beforeBuildCommand` 里的 `npm run build` 由 tauri 自行拉起，**不受 PowerShell 执行策略影响**。
5. **⚠️ 6.2 坑第 6 次命中**：`target\release\python.exe` 已是新版（28631092），但 `target\release\_internal` **仍是旧的**（逐文件哈希比对差 10 项：`app\voxel_csg.py`/`step_importer*.py`/`preview_cache.py`/`base_library.zip`…）—— Tauri 只拷 `externalBin` 的 exe，不拷 `_internal`。**判据升级：逐文件 MD5 比对 `target\release\_internal` 与 `dist_sidecar\python\_internal`**，比"查有没有本批新增模块"更硬（本批全是改文件、没有新增模块）。按手册强制覆盖后一致。
6. **部署**：`target\release\MCNP 输入卡生成器.exe`（6622208 B）+ `python.exe`（28631092 B）+ `_internal`（2294 files）→ `D:\MCNP\MCNP输入卡生成器`；三处 MD5 逐一比对一致。改前快照 `D:\MCNP\_backup_1.7.6_20260912_162912`（2304 files）。
7. **冒烟（`_smoke_deployed.py`，部署版实机）**：5001 **2 s** 就绪；`/api/import-step` **200**（18 栅元，6.4 s）；**`/api/preview-3d` 16 个 STL（8 号在列）且最大体积误差 0.36%**；`xsdir-check`/`mcnp-detect`/`diff-inp` 全 ok。**故意不清 `preview_cache`** ⇒ 缓存版本号（`GEOMETRY_CACHE_VERSION=2`）生效，旧网格未再被命中。

**教训固化（已入 §6）**：① 只改 Python 可以只重打 sidecar；**改了 TSX 就必须 `vite build` + `tauri build`**（前端 bundle 内嵌在 Tauri exe 里）；② 6.2 校验改用**逐文件哈希比对**；③ 部署前必须停掉 `MCNP 输入卡生成器.exe` 及其 sidecar，否则文件占用且 5001 会与 dev 后端互相劫持。

## S1（上一批次）v1.7.6 发布批次（2026-09-10 ~ 09-11，**全链路闭环，已交付用户**）

> **一句话**：技术债审计（34 条）→ 修复 → 实跑验证（抓出 **5 个静态审计看不见的编译级缺陷**）→ 打包部署；随后按**用户真实卡**（Practice3 热室）逐轮验收，又修出**源演示 4 连 bug** + 方向线/滑杆 + 粒子圆点化 + **一键运行多核 tasks** → **v1.7.6 升版打包部署 + 冒烟通过**。
> **版本**：**1.7.6**（2026-09-11 用户指定）。**完整逐条流水**：`docs/CHANGELOG.md`（「一、批次详情档案」含各子批全文）+ `docs/fix-verification.md` §7/§8 + `docs/backend-changes.md` + `docs/frontend-changes.md`。

### 📊 门禁（2026-09-11 实跑全绿）

| 门禁 | 结果 |
| :--- | :--- |
| `python -m pytest tests -q -rs` | **900 passed / 0 failed / 0 skipped**（875 基线 + 25 例 `test_mcnp_tasks.py`；`skipped=0` ⇒ "隐藏 skip"不存在） |
| `tsc --noEmit` / `tsc -p tsconfig.test.json --noEmit` | 两档 **EXIT 0**（后者首次启用时曾暴露 35 处测试类型错误，已全清 —— TD-17 盲区关闭） |
| `vitest run` | **78 files / 625 tests passed / 0 skip** |
| `vite build` | **EXIT 0** |
| spec 一致性闸门 `test_sidecar_spec_keep.py` | **绿**（`_keep_py` ↔ `_import_app` 双向；该闸门此前**从未执行过**，2026-09-10 首次跑通） |

**先决条件（实测）**：跑 pytest 前**须停 5001**（契约测试要端口空闲，§6 坑 1）；`pytest-timeout` **未装**（勿加 `--timeout` —— 否则 pytest 以 `unknown option` 直接退出，看似"全红"其实根本没跑）；`npm.ps1` 被执行策略拦 ⇒ 用 `npx.cmd` 或 `node .\node_modules\...`。**执行者能力**：**有 shell**（PowerShell + Python 3.13.14 + node v24.18.0 + cargo 1.97.1）。

### 📦 v1.7.6 发布（2026-09-11，8 步手动链路；一键打包已废弃）

- 链路：**升版六处** → vite build → PyInstaller（~160 s）→ 替换 binaries → tauri build（33 s）→ **6.2 时效校验** → 备份旧包 → 部署 → 冒烟。
- **⚠️ 6.2 坑第 5 次命中**：`target\release\python.exe` 仍是 09/10 的 **28561279 B** 旧版且**缺 `mcnp_tasks.py`** ⇒ 强制覆盖为 **28615181 B**。**最优判据（本批固化）：直接查 `target\release\_internal\app\` 有没有本批新增模块** —— 比对比 mtime/字节数更硬。
- **冒烟（部署版 vs 旧包）**：`/api/xsdir-check` 200（loaded）、`/api/diff-inp` **200**（旧包 **500**，`No module named 'diff_inp'`）、`/api/lattice-extent` 200、`/api/source-demo-sample` **200**（旧包 **404**）；5001 **3 s** 就绪 + MCP 8100 LISTENING。
- **升版六处**：`gui/package.json:4` / **`gui/package-lock.json`（顶层 + `packages[""]`；本批发现手册原先漏列）** / `tauri.conf.json:10` / `Cargo.toml:3` / `Cargo.lock`（`mcnp-ui`）/ `README.md:25` 徽章 ⇒ 全 **1.7.6**。⚠️ `Sidebar.tsx:2` 直接 `import pkg from "../../package.json"` ⇒ **版本号构建期进 bundle**，升版后**必须重新 `vite build`**。
- **备份**：`D:\MCNP\_backup_1.7.5_20260912_114743`（223.1 MB / 2303 files）；部署目录 `D:\MCNP\MCNP输入卡生成器`（`_internal` 2294 files）。用户数据在 `D:\MCNP\material`，不受覆盖影响。

### 🔴 本批次抓出的真缺陷（静态审计/单测都看不见，全部已修）

| # | 缺陷 | 症状 |
| :-- | :--- | :--- |
| 1 | `app/meshtal/meshtal_cache.py:136` **`IndentationError`**（TD-26 加锁丢了 `while` 体缩进） | 全量 pytest **收集阶段中断**，一条测试都没跑 ⇒ "全绿"是假象 |
| 2 | `gui/src/components/CellEditDialog.tsx:174` 多余三元 `: null,`（TS1135） | 该文件**无法编译**（启用 `tsconfig.test.json` 才暴露） |
| 3 | `app/generator/source_sampler.py:_summarize` 丢弃单能 δ 分布真实能量 | `[14,14]` 被改成假 `[0,1]` |
| 4 | `tests/unit/test_sidecar_spec_keep.py:_parse_hidden` 正则**静默丢内容** | 闸门自身假绿（已改显式配对扫描） |
| 5 | `gui/mcnp_sidecar.spec` `_keep_py` 误列 `_cross_section_helper.py` | TD-34 闸门报"spec 与源码漂移" |
| 6 | **源演示 4 连 bug**（见下表） | 用户实测"一坨方块、看不到栅元" |

**用户裁决 5 项已全部落实**（水密骨架删除 + 契约改名 `cell-closure-check.md`、hexCenter 旧公式 2 处、`frontend-changes:208` 核实为**审计记录有误**、SI 类型 `V` 改合法 `L`（TD-35 关闭，R1/R4 字节断言未回归）、先提交再验证）—— 详情见 `docs/CHANGELOG.md`。
**新依赖**：`@types/node@^22.20.2`（**devDependency**，已获批，不影响运行时与打包体积）。**类型放宽 3 处**（行为等价）：`CellEditDialog`/`DeckContext` 的 `CellData.fill_grid` 改可选、`CycleCellLike.fill_grid` 加 `| null`。**前端另有** TD-23 死代码修复（`sourceAdv.ts` 旧存档 SI/SP 静默丢失）+ `distDual.parseDistributionLines` 见 `frontend-changes.md`。

### 🔧 源演示修复链（S1.0c → S1.0d-3，**用户真实卡 Practice3 逐轮驱动**，4 轮全部经**浏览器端视觉复验**）

> 本项目**首次具备"看图判读"能力**：headless Edge（CDP）+ node 24 内置 `WebSocket` 自写驱动，**零新依赖**、脚本置于仓库外。方法学与三个坑（`alert` 冻结渲染进程 / 同 hash 导航不重载 / PowerShell 空串参数被丢弃）见 `docs/fix-verification.md` §8.4 与 §6。

| 轮 | commit | 根因（真 bug） | 修法 |
| :-- | :--- | :--- | :--- |
| **c** | `a255a3f` | ① 栅元只传 `{num,mat,comment}` ⇒ **`surface_expr` 丢失**（它是建外壳 STL 与判定 CEL/SUR 几何的**唯一来源**）⇒ 4 张真卡外壳栅元数**全 0**；② `resolve_cell_complements()` 返回 **pymcnp 节点**（`_Paren`/`_Union`）而 `voxel_csg` 只认 list AST ⇒ `TypeError` 被 `except Exception: continue` **静默吞掉** ⇒ 几何全丢；③ 防呆：POS 全空时后端兜底 `(0,0,0)` ⇒ 500 粒子叠原点 | 传扁平 `{number,material,surface_expr,...}`；补 `_geometry_ast_to_json`；`except` 改记录 `geometryErrors`（响应带 `geometryWarnings`，前端黄字）；POS 未配置时前端**红字拦截** |
| **d** | `48c51ed` | ④ 后端补 camelCase 别名时**漏 `mat`** + `SourceTab` 把 **snake_case** `deck.cells` **强断言**成 camelCase `LocalCellRow` ⇒ `c.cell.mat` 恒 `undefined` ⇒ `material=""` ⇒ `getMatColor("")` 返回 `"transparent"` ⇒ `buildCellMaterial` 判**真空 M0**（`opacity:0`，**13 个外壳全隐形**）；⑤ 取景**误用体积窗口**的 `computeFramingBox`（`VOLUME_FRAMING_RATIO=0.25`，源区/热室≈**0.057**）⇒ **只框粒子、外壳被挤出视野** | 补 `mat`；`SourceTab` **直读 snake_case（删类型谎言）** + 过滤 `kind:"raw"`；`getMatColor` 区分「空/非法→中性灰」与「M0→透明」；取景改 `unionBoxes`（**`PtracRenderer` 同类缺陷同批修**；`computeFramingBox` 本身**不动**，以保体积窗口语义与其 3 个测试） |
| **d-2** | `857aed1` | ⑥ 方向线长度是**世界空间固定值**（39.05×0.03=**1.17**）⇒ 被"外壳优先"取景（盒对角线 ≈914）缩成 **~1px**；⑦ **「方向线长度」滑杆完全无效**（`setDirectionLength` 只改变量 + `markDirty`，**从不重建几何**） | 改**屏幕空间恒定**（`2×相机距离×tan(fov/2)×3%×倍率`，随相机实时重算 + 0.5% 去抖）；滑杆改为驱动重建 |
| **d-3** | `b1f0043` | ⑧ 粒子是 `THREE.Points` **轴对齐方块**、永远面向摄像头（用户观感差） | 加 `getDotTexture()`（64² canvas 径向渐变圆 + `alphaTest`）⇒ **圆点**；零新依赖，且**保住屏幕空间可见性**（优于 `InstancedMesh` 小球——后者是真实尺寸，外壳取景下只有几像素） |

**视觉复验（修后）**：热室立方体 + 内部空腔 + 盖板圆盘 + 观察孔圆柱**全部可见、多材料配色正常**；500 粒子 x∈[-7.480,7.413]⊂[-7.5,7.5]、y∈[-9.973,9.930]⊂[-10,10]、z∈[50.031,79.893]⊂[50,80]，`allParticlesInsideSourceBox=true`，跨度 14.89×19.90×29.86 ≈ 源区 15×20×30；PTRAC 窗口外壳亦恢复可见。

**S1.0d-2 方向线 + 滑杆（`857aed1`）**：见上表第 3 行。**测试盲区（教训）**：`gui/test` 下**没有任何 `SourceDemoRenderer` 测试**（grep `SourceDemoRenderer|setDirectionLength|arrowLen` **零命中**）⇒ "滑杆无效"能长期存活；该渲染器目前**只有端到端视觉验证能覆盖**。

**S1.0d-3 粒子圆点化（`b1f0043`）**：见上表第 4 行（用户裁决"换成圆形贴图点"，改动最小）。

**★ 顺带定案：用户报"粒子颜色不对"** —— 其卡 `si1 -2 1` + `sp1 0 1` 按 C810 **H 直方图**语义就是**能量在 [-2, 1] MeV 内均匀抽样**（⚠️ **`sp1` 的 `0` 是强制占位符 —— 定义能量范围的只有 `si1`**）⇒ 约 **2/3 粒子为负能量**；而 `app/generator/source_sampler.py:431` 用 `if p["energy"] and p["energy"] > 0` **只把正值计入 `energyRange`** ⇒ 返回 `[0.0037, 0.9973]`（**失真**）⇒ 前端 `normalizeEnergy01` 把负能量**钳到 0** ⇒ 全落到 `trackShade` 最浅端 ⇒ **颜色层次塌成一片接近白色**。

**A/B 实证**（按用户要求把 `si1 -2 1` 改成 `si1 0 2`，**只改注入副本，用户原卡 `E:\download\Practice3 (3).TXT` 未动**）：

| 指标 | 原卡 `si1 -2 1` | 变体 `si1 0 2` |
| :--- | :--- | :--- |
| 负能量粒子数 | **约 2/3** | **0** |
| `energyRange` | `[0.0037, 0.9973]`（失真） | `[0.0002, 1.9954]`（**与真实一致**） |
| 颜色参数 t 的 10 桶分布 | 2/3 挤在第 0 桶（最浅） | **`[49,48,50,43,55,56,54,45,51,49]` 均匀铺满** |
| 观感 | 一片接近白色 | **完整浅蓝→深蓝层次** |

⇒ **程序抽样符合 C810，无 bug**。真正缺口是**缺少"SDEF 能量分布可能产生非正值"的校验/提示**（"有错就地报"原则），而 `energyRange` 的 `>0` 过滤是**症状补丁**。**待用户裁决**（加校验 / 改卡）。
> **订正一条旧记载**：早前记的"点源场景方向线长度趋近 0（`arrowLen` 依赖粒子跨度）"已随 d-2 的**屏幕空间恒定**改造而不再是问题。
> 粒子类型侧**无问题**：卡里 `sdef … par=1` ⇒ 粒子类型 1，后端实测返回 `particle:"n"`、面板"中子 500 / 光子 0 / 电子 0"，与卡一致。

**★ `C810.pdf` 已可直读（本批打通，能力级收获）**：本机 **PyMuPDF（`fitz`）已安装** ⇒ **零新依赖**即可提取这份 1001 页权威手册文本，卡格式语义不必再靠 `app/docs/` 派生 md 猜。**已提取定案**：SI/SP（页 746-747 —— SI = 自变量值、SP = 对应概率；**H 下 SI 是分箱边界、SP 首项必须为 0（占位）**，抽样 = 选分箱后**箱内均匀**；A/L/S 同页）、`tasks`（页 520/875）。**`DSn` 卡的 `param`/J 起点语义仍待核对**（两份派生文档矛盾，§4 待办 5 残余）。脚本在仓库外：`D:\MCNP\_agent_probe\{pdf_index,pdf_extract,pdf_tasks}.py`。

### ⚙️ 一键运行 MCNP 支持多核 tasks（S1.0e，`21d93d0`）

- **权威依据（C810 页 875）**：`TASKS n` 走 OpenMP 线程（*Invokes OpenMP threading on shared memory systems*）；且 **`DBCN(2,3,4)` / `SSW` / `SSR` / `PTRAC` 与 `tasks > 1` 不兼容（FATAL error）**。
- **实测：`tasks` 取物理核数而非逻辑核**（Ryzen 7 4800H，8 物理核/16 逻辑核，10M 历史）：

  | tasks | 1 | 4 | **8** | 9 | 16 |
  | :-- | :-- | :-- | :-- | :-- | :-- |
  | 墙钟 | 22.35 s | 8.38 s | **8.36 s** | 8.81 s | **15.06 s** |
  | CPU/墙钟 | 0.99 | 3.96 | 7.83 | 8.91 | 13.66 |

  ⇒ **`tasks 8` 最优；`tasks 16` 因超订反慢 80%**（烧 205 s CPU，大半自旋）。Amdahl 反推：串行 ≈6.35 s、可并行 ≈16 s ⇒ 理论上限 ≈3.5×，实测 2.67×。
  > ⚠️ 这是**极简铁球模型**（碰撞少、可并行占比低）；真实屏蔽模型收益更好 —— 建议用**自己的卡**调小 NPS 后比墙钟选优。
  > ⚠️ `tasks` **只在 OpenMP 构建上生效**；判据是输出出现 `comment.  threading will be used …`，非线程版**静默忽略**（不报错也不加速）。

- **两层防线**：**UI 前置提示**（`TasksIncompatibleHint` 挂在 **PTRAC 启用** 与 **SSW/SSR 面源** 两处 ⇒ **选模式即提示**）+ **后端兜底**（`app/mcnp_tasks.py` 扫卡强制降级并把原因回传 `tasksNote`，经「高级→额外卡片」手写进去也拦得住）。
- **复用**：抽 `gui/src/utils/detectedCores.ts`（**消除 `SweepDialog` / `PreviewDialog` 里重复的 `DETECTED_CORES`**；`DEFAULT_WORKERS` 保持既有 `min(8,核)` 行为，新增 `SUGGESTED_WORKERS` = ⌈逻辑/2⌉ 物理核估计、`clampWorkers`）。`PreviewDialog` footer 加核数滑杆并把 `tasks` 传给 `/api/run-mcnp`。
- **新模块必须登记 spec**：`app/mcnp_tasks.py` 已入 `_keep_py`（**不登记即 TD-02 那个"冻结包 import 失败"**），受 `test_sidecar_spec_keep.py` 双向闸门守护；新增 **25 例**单测（跳格展开 / 三种排他卡 / DBCN 第 2·3·4 项 / `28j 0 13j 0` **不误报** / 注释跳过 / 缺省·非法·超限夹取）。
- **为什么单列 `app/` 模块**：项目纪律禁止 pytest import `gui/backend/api_server`（pyvista/FreeCAD 污染），逻辑必须住 `app/` 才能被测 —— 与 `diff_inp`/`lattice` 同构。

**UI 复验（截图三连）**：勾选 PTRAC → 黄框提示现；切「面源 (SSW/SSR)」→ 提示现；生成预览 footer → `CPU [滑杆] 8`（= 实测最优值）。

**发布**：本批是**新功能**，按规则"升版由上级指定"当时未升版；**同日用户指定升版 1.7.6 并打包部署** —— 见上文「📦 v1.7.6 发布」。三态：**已改 ✅ / 已提交 ✅ / 已打包部署 ✅**。



### 🧹 待办（本轮**未做**，明确记录，勿当作已做）

1. **M-10**：`app/UI_ARCHITECTURE.md` 仍陈旧（`25 端点` 实际 **49**、`pytest 251 绿` 实际 **900**，共 3 处）→ 审计处置①要求"整体重锚定或标为历史快照"。
2. **TD-19**（P1）：214 处 `any` 重构 + **单一 `CellData` 定义**（现状实证：`DeckContext.CellData` snake_case `imp_n` vs `CellEditDialog.CellData` camelCase `impN` **两套并存**）。上一轮"无 tsc 可跑"的搁置理由**已消失**，可排期。**⚠️ 2026-09-11 升级为高优先**：S1.0d 的"看不见栅元"根因正是这条缝的产物（`deck.cells` 是 snake_case、`cellBridge.LocalCellRow` 是 camelCase，中间靠后端补 camelCase 别名 + `as` 断言糊住，**别名漏了 `mat` 就整条链路静默失效**）。
3. **TD-35 残项**：`gui/src/utils/distDual.ts:19` 的 `SI_LETTERS` 仍含 `V`/`Q`/`T`/`F`，与后端 `_SI_LETTERS = (L,H,A,S)` 不一致。
4. **C810.pdf 仍未逐字核对**（`DSn` 卡 `param`/J 起点语义；项目内两份派生文档互相矛盾）。

---

## S1.1 历史批次索引（2026-08-22 ~ 09-10，**详情已归档，勿在此重复展开**）

> **维护规则**：批次完成即在此表加一行「索引」；**详情写 `docs/CHANGELOG.md`**（+ `docs/backend-changes.md` / `docs/frontend-changes.md`）。
> 本区只保留**仍影响当下判断**的状态与未闭环项；已验证闭环的历史细节不再重复（正是"记忆量过大"的成因，2026-09-10 压缩）。

| 日期 | 批次 | 关键交付 | commit | 门禁（当时） | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 09-10 | **SDEF 源粒子演示（TODO #6）** | 后端三深模块（`DistributionSampler` 分布抽样 / `source_sampler` 源编排 / `voxel_csg` 全宏体拆解）+ `/api/source-demo-sample` + 独立「🎬 演示源」3D 窗口；按 C810 全不降级、有错就地报 | `4f0798fa` | 新单测 49 / tsc 0 | ✅ **已打包部署**（2026-09-10，见 S1 发布批次；实施时"未打包"状态已闭合） |
| 09-10 | **源分布 v2 双态 + 原文值网格化** | 修"无字母 `SI` 被回填 `L`"根因（`distributions.py` 权威解析/发射，raw 逐字直通）；前端 `distDual.ts` 双态 + 8 列值网格 | 随本批 | 相关 46 / vitest 587+4 | ✅ 已提交 |
| 09-04 | **AI 接入 inputcard-mcp** | `inputcard_mcp/` 6 深工具（按语义段读写）；`--mcp-http` 本机 8100；快捷建栅元 HEX/TET；IMP 数值化；深模块 `useQuickAddOverlap`；**废弃一键打包**；`AI接入.md` | 1.7.5 批次 | vitest 554 / tsc 0 | ✅ 已提交（**stdio `--mcp-server` 已移除，别再教它**） |
| 09-04 | **stderr-hang 修复** | mcp/anyio/httpx 日志降 WARNING（Windows 管道缓冲小 + 无人读 stderr → server 阻塞写 stderr → MCP 卡死）；因果实验证实 | 同上 | pytest 765/0 | ✅ 已修（**作 A 级教训见 §6**） |
| 09-04 | **后端拉起提速 + preview_cache 跨进程持久化** | `import api_server` 2546ms→299ms（惰性 `_surf_classes` + handler 内按需 import + 后台预热线程）；STL 缓存写盘到 `D:\MCNP\memory`，跨重启命中 | `0a266cd` | 654/0、preview_cache 11/0 | ✅ 已提交 |
| 09-04 | **3D 预览重合检测 fill 修复** | 前端补传 `u/fill/lat/fill_grid/trcl/render/imp`（原只传 4 字段 → 后端三道防线全失效）；17×17 假重叠 57→0；BEAVRS 331→10 真实栅元 | 随批 | overlap 15 / vitest 546 | ✅ 已提交 |
| 09-04 | **格阵 universe 覆盖完整性检测（红框预防）** | `coverage_check.py`（16³ 采样 + `EDGE_INSET_REL`）+ `/api/validate-universe-coverage`；涂色时即时提示（不阻断） | `f7fc2ed` | 随批 | ✅ 已提交 |
| 09-04 | ***fmesh 能量沉积 + 3D 可视化** | `fn_prefix` 贯通（`*FMESH14:N`→MeV/g）；`sliceExport.ts` 切面 + PNG/SVG/CSV 导出；零新依赖 | `f7fc2ed` | pytest 741 / vitest 546 | ✅ 已提交 |
| 08-30 | **材料库深化** | `material_library.py` + 5 端点；`D:\MCNP\material\material_library.json`（D 盘不可写回落 `%APPDATA%`）；custom/override；JSON/CSV 导入导出（冲突三选 + 一致自动跳过）；📚 管理面板 | 1.7.4 沿用 | pytest 737 / vitest 534 | ✅ 已打包部署 v1.7.4 |
| 08-28 | **lat=2 六棱柱 3D 预览 bug 三修** | ①容器表达式含 `#n` 补集 → FreeCAD 构建失败（**剥离 `#` token**）；②`_subpitch` 硬编码 1.26 → `None` 初值取实际 min pitch；③hex 未居中 → 统一 `(i-(nx-1)/2, j-(ny-1)/2)` | 见 CHANGELOG | 99/0 / vitest 527 | ✅ 已修（**hexCenter 权威公式未改，只改调用处偏移**） |
| 08-28 | **FILL 涂色 U 配色** | 固定 12 色 → golden-angle 色相散列（`universeColorByRank`，500 U 零撞色） | 见 CHANGELOG | vitest 528 | ✅ 已打包部署 v1.7.4 |
| 08-27 | **3D 预览 MCNP 窗口裁剪 + U 分组侧边栏** | 实体 = `universe ∩ 格元盒 ∩ 容器 cell`（MCNP 窗口机制）；BEAVRS 超壳叶 48→16；侧边栏改 U 分组 | `530ee8a`/`7de14cd`/`39772a0` | 85/85 / vitest 527 | ✅ 已打包部署 **v1.7.4**（版本五处同步） |
| 08-28 | ↳ **disc STL 键错配 + z 居中** | ①disc 按格阵引用建 STL，但叶 universe 是径向 pin → 回退 `BoxGeometry` 方块（5.5 万 pin）；改为补建叶 universe 裁剪 STL。②格元盒底锚 STL + 原点在中心 → 整体上移 height/2；`_stl_recenter_z` 平移居中 | `d8b6747`/`5fafd1d` | test_api_contract 17 | ✅ 已重打包 sidecar 部署，**用户已复验** |
| 08-25 | **用户 3D/格阵编辑器 7 项反馈** | 见 CHANGELOG | 见 CHANGELOG | vitest 516 / 后端 79 | ✅ 已提交 |
| 08-24 | **格阵 fill 15 项用户实测反馈（三阶段）** | 见 CHANGELOG（含 golden 写盘、R1 不动点） | `2e38934` | — | ✅ 已提交 |
| 08-24 | ↳ 阶段3 3D 预览实施 + 阶段2 UI 画布设计契约 | 见 CHANGELOG | 同上 | — | ✅ 已完成（曾因两 agent 被用户停止而重派） |
| 08-23 | **栅元列表批量编辑 + 会话外技术债清偿 14 项 + P0 3D 重合 bug** | 见 CHANGELOG | `c3e5c43`（未 push） | — | ✅ 已提交 |
| 08-23 | **v1.7.3 两批发布**（keff 仪表盘 / 材料搜索 / 示例库 / INP 对比；重合检测超时 + 零体积检测） | 见 CHANGELOG | 见 CHANGELOG | — | ✅ 已提交并部署 |
| 08-22 | **GQ/SQ 3D 预览修复 + 渲染增强 + OWEN 四项 + 参数扫描前端** | 纯 numpy MC 去 vtk、TR、解析切片、切线平面法、mctal 解析、校验规则交叉核对、sweep 模块 + 2 端点 + SweepDialog | 未 commit（文件恒 1.7.2） | pytest 573 / vitest 358 / tsc 0 | ⚠️ **当时未发版**；其成果已并入后续版本（如需追溯见 CHANGELOG） |

**本区仍需记住的几个「活」约束**：

1. `app/generator/inp_generator.py` 仍**模块顶层** `from pymcnp import inp` —— 这是 `tests/test_tech_debt.py` F#7 的 fail-fast 约定（pymcnp 缺失须导入期报错），**不要"顺手优化掉"**。
2. `D:\MCNP\memory` 是后端可复用内容的持久目录（STL 缓存），**不在仓库、不入 git**；打包/换机须保证可写。
3. **一键打包已废弃**（`release.bat`/`scripts\release.ps1`/`README-release.md` 已删）—— 只走 `docs/手动打包方法.md` 手动链路。
4. **AI 接入统一走 `--mcp-http`（本机 8100 `/mcp`）**；`--mcp-server`（stdio）已移除并显式 `sys.exit(2)`。
5. **5001 端口**：跑 HTTP 契约测试或起 sidecar 前先确认无人占用（`Get-NetTCPConnection -LocalPort 5001`）。历史上**多次**因打包版 sidecar 残留劫持而出现"假红/假绿"（§6）。


## S2 工作区与分支

- **分支**：`main`。**工作树**：干净（2026-09-10 三次提交后 `git status --porcelain` 无输出）。
- **当前 HEAD**：见 `.git/refs/heads/main` + `.git/logs/HEAD`（reflog 是纯文本，比 `git log` 更适合 AI 只读）。
- **2026-09-10 本批提交（三个，按主题拆分）**：
  | commit | 主题 |
  | :--- | :--- |
  | `049885b` | 技术债审计 34 条修复落盘（TD-02/03 阻塞发布项 + 门禁可信度 + 代码债），70 文件 |
  | `024278c` | 验证批次 —— 跑通全部门禁并修复 5 个真缺陷（pytest 875 / vitest 625 / tsc 0 / build 0） |
  | `198fe37` | TD-35 —— 多源 POS_VEC 改发合法 `SI L`（原发 C810 非法的 `SI V`） |
  > ⚠️ **纪律：提交即登记**（S3.1）。此后每批必须记 commit 短号或待提交清单，精确清单实跑 `git status --porcelain`。
- **版本六处**：`tauri.conf.json` / `package.json` / **`package-lock.json`** / `Cargo.toml` / `Cargo.lock` / README 徽章 恒 **1.7.6** 一致（**唯一权威 = `gui/package.json:4`；侧边栏经 `import pkg from "../../package.json"` 读它 ⇒ 升版后必须重新 `vite build`**，否则界面仍显示旧版本）。
- **部署产物**：`D:\MCNP\MCNP输入卡生成器`（**2026-09-11 重打包 v1.7.6**，含 S1 全量）。旧包备份 `D:\MCNP\_backup_1.7.5_20260912_114743`（223.1 MB / 2303 files）。
  - **2026-09-12 两轮热修覆盖**：15:30 sidecar-only（STEP 导入 500）→ **16:32 完整链路**（前端「导入即关窗」+ GQ 薄栅元修复，`vite build` + PyInstaller + `tauri build`）。部署版现为 `MCNP 输入卡生成器.exe` 6622208 B / `python.exe` 28631092 B / `_internal` 2294 files，**版本号仍 1.7.6**；改前快照 `D:\MCNP\_backup_1.7.6_20260912_162912`（2304 files）。冒烟最大体积误差 **0.36%**。
- **2026-09-11 本批提交**（按主题拆分）：`48c51ed` 源演示修复二批（material + 取景）／`857aed1` 方向线不可见 + 长度滑杆失效／`b1f0043` 粒子圆点化 + SI/SP 权威语义定案／`21d93d0` 一键运行多核 tasks + 排他卡提示／`d20726c` 升版 1.7.6 + 打包部署。

## S3 进行中任务 / 待办

- **⭐ 当前（2026-09-11）**：**v1.7.6 已升版并打包部署**（用户指定）。三态 = **已改 / 已提交 / 已打包部署 + 冒烟通过**。本批次覆盖：**源演示修复链（4 轮）**、方向线不可见 + 长度滑杆失效、粒子圆点化（附 `si1 -2 1` 诊断）、一键运行 MCNP 多核 tasks + PTRAC/SSW/SSR 排他卡提示。
- **本轮明确未做（按优先级，详见 S1「🧹 待办」）**：
  1. **M-10**：`app/UI_ARCHITECTURE.md` 重锚（3 处陈旧计数）。**成本最低，建议先做**。
  2. **TD-19**（P1）：214 处 `any` 重构 + 统一 `CellData`（现 snake_case/camelCase 两套并存）。搁置理由已消失（tsc 现 EXIT 0）。
  3. **TD-35 残项**：`distDual.ts` 的 `SI_LETTERS` 仍含 `V`/`Q`/`T`/`F`，与后端 `(L,H,A,S)` 不一致。
  4. **C810.pdf 人工核对**：`DSn` 卡 `param`/J 起点语义（项目内两份派生文档互相矛盾）。
- **已交付（近期，全部已打包部署）**：SDEF 源粒子演示（**2026-09-10 首次真正交付**）／AI 接入 MCP over HTTP（1.7.5）／格阵 fill 三阶段 + 覆盖完整性检测／`*fmesh` 能量沉积可视化／材料库深化／栅元封闭性自检／校验规则补全／参数扫描改造／源项 adv 权威化。
- **讨论过未做（可排期）**：`MCNP输入卡生成器_功能待办清单.md` P1#2「3D 预览悬停读数 + 栅元编号标签」（点选高亮已做）；审计遗留 P2/P3 子项（见 `docs/audit/t4-consolidated.md`）。
- **已知阻塞**：无（**唯一环境类风险**：5001 端口劫持——跑 HTTP 契约测试/起 sidecar 前必须确认无人占用；见 §6）。
- **其余**：按用户新反馈排队。

### S3.1 两条新增纪律（2026-09-10 技术债审计输出，**必须遵守**）

1. **提交即登记**：每批改动结束**必须**记「commit 短号 **或** 待提交文件清单」。**依据**：审计发现 08-22~09-10 有约 20 条真实提交（含 1.7.5 升版、封闭性自检、参数扫描改造、源项 adv+appScale）在记忆里**零记录**（`M-16`，记忆外改动），是本次所有记忆债的根因放大器。
2. **三态表述**：凡记录已完成的功能，**必须写清「已提交 commit / 已打包版本 / 部署校验」三态**，不得只写"已完成"。**依据**：SDEF 演示批次的"已实现/已提交/未打包"三态在记忆里曾自相矛盾（`M-15`），并导致"用户安装版有没有该功能"无法回答（实测：**没有**）。

---

# ◉ 长期记忆（稳定存储）—— 固化知识

> 固化后不随批次变动；更新只在"经验固化"时进行。

## §1 项目身份（语义记忆）

- **名称**：MCNP 输入卡生成器（MCNP Input Card Generator）
- **版本**：**1.7.6**（**六处**一致：`gui/package.json:4` / `gui/package-lock.json`（顶层 `version` + `packages[""]` 两处，**本批新纳入清单**）/ `gui/src-tauri/tauri.conf.json:10` / `gui/src-tauri/Cargo.toml:3` / `gui/src-tauri/Cargo.lock`（`name="mcnp-ui"`）/ `README.md:25` 徽章；2026-09-11 **用户指定升版**，因源演示修复二批 + 粒子圆点化 + 一键运行 MCNP 多核 tasks 等新功能上线）。**历史演进**：1.7.2（2026-08-18 快捷建栅元）→ V1.7.2.2 批次（文件恒 1.7.2）→ 1.7.3（2026-08-22 GQ/SQ+重合检测）→ 1.7.4（2026-08-27 MCNP 窗口裁剪+U 分组）→ 1.7.5（2026-09-04 AI inputcard-mcp + 六棱柱/四面体）→ **1.7.6（2026-09-11）**。**规则不变：bug 修复批严禁升版；升版由上级另行指定**。⚠️ 打包手册原先只列"五处（四处+锁文件）"，**`gui/package-lock.json` 也带项目版本号**，本批已补进手册。
- **技术栈**：
  - 前端 UI：React 18 + TypeScript + Vite（端口 1420，表单化标签页界面）
  - 3D 渲染：Three.js（3D 预览 + 体积可视化）/ SVG（平面截面 / OUTP 折线图）
  - 窗口外壳：Tauri 1.x（Rust，无边框自定义窗口；Electron 备用壳已于依赖清理中删除）
  - 后端：Python 标准库 `http.server`（端口 5001，**不用 Flask**），PyInstaller 打包 sidecar
  - 核心引擎：pymcnp（BSD-3-Clause）+ 自研 generator/parsers
  - CSG 几何：FreeCAD（LGPL）；STEP→MCNP：GEOUNED（EUPL-1.2，随程序 vendor 打包）
- **核心业务**：用可视化表单 GUI 替代手工编辑 MCNP `.INP` 输入文件；覆盖生成/导入/校验/3D 预览/截面/材料库/源/计数/输出分析全流程
- **许可**：本项目自有代码 MIT License（2026-08-28 由自定义限制许可改为 MIT，放弃商用/再分发限制）；开源组件各按自身许可

## §2 当前状态快照（语义记忆）

- **开发阶段**：**v1.7.7 已打包部署**（2026-09-26，**用户指定升版**）—— 本包含 **S11 三条修复（计数卡前缀 / 栅元 `#` / 截面拖动）+ S10 全量（GEOUNED 参数 UI · FreeCAD 自适应切分 · `P A B C D` 感度 · slab 覆盖 · 墓区过滤）+ 09-23 各批**。
  **部署版冒烟实测（2026-09-26，真跑 exe）**：5001 **2 s** 就绪；`/api/xsdir-check` `loaded=true`；`/api/parse-inp` 喂用户那张"手工折行、续行行首 `#`"的栅元卡 ⇒ **1 栅元 / 54 项 / 含 `#55` / 无 `#1#2` 粘连 / `imp:n=imp:p=1` / 注释在位**，回显 `F4.fn_prefix='*'`、`F5.number_suffix='X'`；`/api/generate` 回放 `*F4:N 1 2` + `F5X:N 0 0 0 1`；收尾 5001/8100/1420 全释放。
  **产物核对**：exe **6,622,208 B**、`python.exe` **32,622,751 B**（与 `src-tauri/binaries/` **哈希一致**）、`_internal` **7873 文件 / 214,820,150 B**、exe 内 bundle **`index-dO5WbQoY.js`**（旧包 `index-DA8CoYHE.js`）、PE 资源版本 **1.7.7**（UTF-16）；部署目录 `_internal\app\generator\parsers\lines.py` 与源码**哈希一致**。旧包已备份 `D:\MCNP\_backup_1.7.6_20260926_154504`（**整卷改名移动**，秒级可回滚）。
  > 旧状态（已作废）：**v1.7.6 已打包部署**（2026-09-11，`D:\MCNP\MCNP输入卡生成器`）——含 **S1 全量**（源演示修复链 4 轮 + 粒子圆点化 + 方向线/长度滑杆 + 一键运行多核 tasks）。**部署版冒烟实测**：`/api/xsdir-check` **200**（`loaded=true`）、`/api/diff-inp` **200**（旧包 500）、`/api/lattice-extent` **200**、`/api/source-demo-sample` **200**（旧包 404）；5001 与 MCP 8100 均 LISTENING；`_internal\app\{mcnp_tasks,preview_cache,lattice,diff_inp}.py` 与 `_internal\vendor\geouned` 全部在位。旧包已备份 `D:\MCNP\_backup_1.7.5_20260912_114743`（223.1 MB / 2303 files）。
  > 旧状态（已作废）：v1.7.5（2026-09-10 部署）只含技术债修复全量 + SDEF 源粒子演示，**不含** 09-11 的源演示二批 / 圆点化 / 多核 tasks。
  > **2026-09-23 同版本重出包（版本恒 1.7.6，用户指定不升版）**：GEOUNED STEP 导入参数 UI 进包。
  > 链路 vite → PyInstaller（190 s）→ binaries 替换 → `npm run build:app` → 部署
  > `D:\MCNP\MCNP输入卡生成器`（7876 文件 / 242.3 MB）。**冒烟**：3 秒后端就绪、
  > `xsdir-check loaded=true count=7925`。**证据链**：部署包内 `step_importer_geouned.py` /
  > `geouned_worker.py` **sha256 与源码逐字节一致**、新映射在包内跑通、exe 内搜到本批前端
  > bundle 名 `index-Dlg3rafp.js`（旧包 `index--y8mVlhU.js`）。**未备份旧包**（用户明确指示
  > 「不必进行备份」）；首次部署后按真机反馈又改了两处子弹框行为并**只重出前端**（未重跑
  > PyInstaller —— 后端未变，`python.exe`/`_internal` 逐字节相同）。
  > **2026-09-23 同日后半批（版本仍 1.7.6）**：**MCCAD 实体预分解**（基本页开关）+ 导入设置持久化。
  > 动因是用户模型（`厂房建模.step`，3 实体 / 270 面）经 GEOUNED 直转后**栅元 3 引用 146 个面**，
  > 而 `simplify` 两档对它**逐位相同**（25/23/146）⇒ 实体分解无档位是根因。**实测结论**：
  > 备份里的 `McCAD.exe` 可用（**FreeCAD 的 bin 补 OCC DLL 即可**，无需打包 47 MB）；
  > McCAD 只分解 → 3 实体变 **188 实体**；交给 GEOUNED → **186 个实体栅元、单栅元最大面数
  > 146 → 9（平均 6）、体积守恒 0.0002%**；而 **MCCAD 自己的转换器在 `decompose=true` 时
  > 拒绝该模型**（无 `MCFile.i`，mm/cm 都拒）⇒ **McCad 切、GEOUNED 转**。
  > 详见 `docs/frontend-changes.md` 同名章节与 CHANGELOG 同日两条。
  > **2026-09-24（版本仍 1.7.6）：MCCAD 整条链路被 FreeCAD 自适应切分替换掉。**
  > 三条实测判死外部程序路线：① MCCAD 的 188 块里 186 个实体块**每个 ≤8 面**，但实体面数
  > **合计从 194 涨到 1110**（块数换复杂度做亏了）；② 它切出**退化块**（栅元 80/134 表达式
  > 同为 `-208 211`，`Vol≈6.7e-07`/`3.6e-06` cm³，3 位小数显示成 `Vol=0.000`），
  > `minSolidVolume=1.0e-3` 拦不住；③ **它暴露的是过程参数**（`recurrenceDepth`），而用户要的是
  > **结果指标**（每块面数）—— 同样深度在不同模型上得到的块复杂度完全不同，加多少档都给不了。
  > **新机制**：`app/adaptive_cut_freecad.py`（FreeCAD 子进程）+ `app/adaptive_decompose.py`
  > （父侧深模块），**按结果收敛的最长边二分** —— `Faces <= 上限` 就留，否则沿最长边中分，
  > 某轴切不出 ≥2 块就换轴，三轴都切不动或到深度上限就**原样保留并计数**。
  > 实测 274 m³ 模型：上限 30 → **18 块（19–30 面，0 块超限）**、上限 50 → 9 块、上限 20 → 41 块
  > （2 块切不动，如实上报）；体积比均 **1.0000000**、碎屑 0、1–2 s。
  > 最终栅元：**47 个 / 实体面数合计 367 / 最大 48**（不切是 30 / 194 / 146；MCCAD 是 205 / 1110 / 52）。
  > **如实记下的局限**：**真空栅元不受块切分控制**（28 个真空栅元最大 48 面）—— 真空是实体
  > **之间**的空隙，把实体切碎只会让它更零碎，不会更简单。用户"≤30 面"的要求在**实体块**侧全达成。
  > **两个真 bug**：`import FreeCAD` **必须先于** `import Part`（否则 `ModuleNotFoundError`，
  > 后果不是报错而是**静默跳过切割**）；同一 bug 让 `geouned_worker._bbox_of()` 恒返回 None ⇒
  > 分解自证**退化成恒真空检查**。详见 `docs/frontend-changes.md` 2026-09-24 节。
  > **2026-09-24 同日第二批（版本仍 1.7.6）：`P A B C D` 感度翻转 + `_plane_halfspace` 覆盖不足。**
  > 用户驱动：「分解的 stp 没问题，为什么 geouned 解析这些 stp 就出问题了？」→「把这些 stp 中的块
  > 拆出来、一个一个传进程序，看体积有没有变化」→「检查出 bug 在哪里」。**按此方法定位**：
  > 18 块逐块量三处体积 —— **V1（GEOUNED 的 `Vol=` 卡）17/17 全对**、**V2（程序重建）16/18 爆炸
  > （+494%…+11389%）**、对照块 000/001 偏差 +0.0004%/−0.0000% ⇒ 责任在**表达式**不在重建机制。
  > **① `_surf_classes()` 按 keyword 收成一个类**：pymcnp 的 `P_0`（四系数）/`P_1`（三点）
  > **`_KEYWORD` 都是 `p`**，`_d[_kw] = _obj` 让 `P_1` 覆盖 `P_0` ⇒ 四系数卡解析失败 ⇒ 落进
  > "系数→三点"兜底 ⇒ 下游按 C810 §3-17「原点负感度」重算法向 ⇒ **D<0 的平面整体翻面**
  > （GEOUNED 写的一般平面 D 大量为负）。**C810 §3-17 原文（PDF 541 页）**：那条规则**只管三点形式**，
  > 四系数形式的正侧就是写下的符号 ⇒ `plane_from_points` 本身没错，错的是"不该走三点"。
  > **② `_plane_halfspace` 厚板盖不满包围盒**：横向需 ≥`√3B`（要求参考点 ∥ 法向，而 `P_0` 分支取
  > `(D/A,0,0)`）、沿法向厚度需 ≥`√3B−n·p`（只伸 2B 时要求 `n·p ≥ −0.268B`）。修法：参考点**投影成
  > 最近点** + 厚度取 **4B**。**效果（18 块最坏偏差）**：+11389% → 修感度 +0.5128% → 再修厚板 **+0.0897%**；
  > 块 003 三级台阶 +249% → +0.49% → **−0.0049%（closed）**。**③ 第三处是 GEOUNED 的**：不切时那个
  > 202 面实体的栅元表达式有 229 个交项，**唯一一个 3 面项由三个平面构成**——**3 个平面半空间的交在
  > 3D 里必然无界** ⇒ 溢出（`infinite`、体积 = 真值 2.7 倍）。我们改不了 GEOUNED，**但"实体预分解"
  > 恰好是它的解**：`cut=ON` 时 18/18 实体栅元 `closed`、体积合计 +0.0048%。
  > **2026-09-24 同日第三批（版本仍 1.7.6）：GEOUNED 墓区被渲染进 3D 预览（"一坨"的真根因）。**
  > 用户：「我用切分后，3D 预览…看到的是一坨」→「每个栅元都是乱的」→「你用视图能力，截图查看」。
  > **量化**：预览返回 **47 个 STL**，其中栅元 47（注释 `Graveyard`、半径 1049 球外）体积 =
  > 模型 **7372%**、bbox **2927³**；栅元 46（`Graveyard_in`）**1583%**、2097³ ⇒ 把模型
  > （1042×1751×260）整个包住、相机被撑到 **±2000**。**根因两处**：① `flat_cell_json`（这条路上
  > **唯一的序列化口**）只输出 5 键，丢了 `imp_n/imp_p/imp_e`、`render`、`fill`、`fill_grid`、`u`；
  > ② `build_cells_data` 的 graveyard 判据要读 `imp_*`，**而上游 `flat_cell_json` 把 `imp_*` 丢了**（实测 GEOUNED 的 deck **是带 imp 的**：`47 0 277 Vol=1.000 imp:n=0 imp:p=0 `）⇒
  > 取不到值 ⇒ **恒不成立**。**修法**：判据加第二条「**注释含 graveyard**」（GEOUNED 官方标记，
  > `void.py:201/208`；`mcnp_format.py:256` 也这么认）+ 序列化口补齐 7 键（同步 `api.yaml` 契约）。
  > **效果**：预览 STL **47 → 45**、全部 STL 总 bbox **2927³ → 1043.9×1752.8×262**。
  > **部署（2026-09-24 23:05/23:07，版本仍 1.7.6）**：`npm run build:release` → 部署
  > `D:\MCNP\MCNP输入卡生成器`（**7878 文件 / 254.07 MB**）；`_internal` 与构建产物**7873 项
  > 逐项一致**、顶层三件套 sha256 一致、`_internal\app\step_importer.py` sha256 与源码一致。
  > **部署版端到端复验**：47 栅元 → 预览 **45 个 STL**、46/47 排除、总 bbox 1043.9×1752.8×262。
  > 三批详见 `docs/frontend-changes.md` 与 `docs/CHANGELOG.md` 2026-09-24 三条。
- **技术债状态**：2026-09-10 完成全量审计（**34 条**，详见 `docs/tech-debt-report.md` + `docs/audit/`，后者被 `.gitignore` 忽略）→ **已完成修复 + 实跑验证 + 打包部署**（见 S1）。审计结论"已证实 P0 = 0"经实机**修正为：至少 1 条实际已坏**（部署版 `/api/diff-inp` 500）。剩余待办见 S1「🧹 待办」（M-10 / TD-19 / TD-35 残项 / C810 核对）。
- **待排期**：无（#7 重合检查已于 2026-08-22 交付；`MCNP输入卡生成器_功能待办清单.md` 的 P1#2「3D 预览悬停/编号标签」仍未做）
- **已完成功能**：
  - 8 标签页表单编辑（基本/材料/几何/源/计数/高级/输出）
  - INP 生成/导入（含拖拽）、工作区自动保存/恢复、4 套主题
  - 材料库（**97 种预设**：49 内置 + 48 PNNL-15870 精选同位素级；xsdir 校验 + 下拉自动填充密度）+ **用户可编辑持久材料库**（材料库深化，2026-08-30：custom/override、导入导出 JSON·CSV、xsdir 反向索引 + 组成自洽校验、「📚材料库」管理面板、MT卡/其他随预设贯通，存 `D:\MCNP\material\material_library.json`）
  - 3D 预览（FreeCAD CSG，`#n` 栅元补集支持）+ 平面截面（STL numpy 切）+ STEP/GEOUNED 导入
  - **GEOUNED STEP 导入参数 UI**（2026-09-23，**已打包部署 ✅**）：导入对话框改 **4 个子页签**（基本 / 常用调节 / 进阶与少见 / 高危 ⚠），共 **40 项 GEOUNED 参数**可调 —— 真空栅元切割三件套 `maxSurf`/`maxBracket`/`minVoidSize`（第 2 页「常用调节」）、`simplify`、`spline_surfaces`、`voidMat`、`skipSolids`、`sort_enclosure`、`debug`、Options 9 项、Tolerances 全 15 项、`export_csg` 5 项。核心语义：**留空 = 该键不发送 = 用 GEOUNED 自己的默认值**（与 GEOUNED config.json"省略键即默认"同构）；全部控件配中文悬停释义（子弹框含作用/默认/怎么调/开与关/逐选项释义/风险 + `对应 GEOUNED 参数：` 英文行），**触发器只有参数右侧的 `?` 图标、鼠标移开立即消失**；颜色零硬编码（4 套主题自动正确，暗色主题正文近白）。后端 `_map_app_settings_to_geouned` 改**表驱动白名单**（44 行，缺省/非法即不发送）+ worker 五区段接线。**导入设置会记住**（独立键 `mcnp_step_import_v1`，主界面「清空」不影响；材料名/密度/TMP 不记忆）。详见 `docs/frontend-changes.md` 与 `docs/CHANGELOG.md` 2026-09-23 条
  - **实体预分解（每块面数上限可调）**（2026-09-24）：基本页开关「启用实体预分解」+ 下拉「每块面数上限」（较粗 50 / **适中 30（默认）** / 较细 20 面）。纯 FreeCAD/OCC 实现，**不依赖任何外部程序**（MCCAD 链路已整体移除）：`app/adaptive_decompose.py`（父侧深模块）+ `app/adaptive_cut_freecad.py`（FreeCAD 子进程），**按结果收敛的最长边二分**，切不动就如实计数上报。实测 274 m³ 模型：上限 30 → **18 块（19–30 面，0 块超限）**、体积比 1.0000000、1.4 s；最终 47 栅元。**它同时规避了 GEOUNED 的退化分解**（见 §6「3 个平面的交必然无界」）。失败一律回退原文件、原因经 warnings 传到界面
  - **3D 预览不再渲染 GEOUNED 墓区**（2026-09-24）：graveyard 判据加「注释含 graveyard」+ `flat_cell_json` 补齐下游判据键。此前两个墓区（体积 = 模型 7372% / 1583%、bbox 2927³）被渲染，把模型整个包住、相机撑到 ±2000 —— 用户报的"3D 预览是一坨/每个栅元都是乱的"就是它
  - **GQ/SQ 曲面 3D 预览**（2026-08-22）：含任意 GQ/SQ 的栅元走纯 numpy 体素 CSG（`app/mc.py`/`voxel_csg.py`/`quadric.py`），TR 变换正确、水密、无 vtk 依赖、打包可用
  - **GQ/SQ 精确截面（2D 解析切片）**（2026-08-22）：`app/analytic_slice.py` 在切割平面上解析求值 + marching squares 提取轮廓；**切线平面法快路径**（椭球/圆柱平滑水密网格，~600 三角形）
  - **mctal 解析 + 参数扫描**（2026-08-22）：`app/mctal_parser.py`（k-eff/收敛/tally，纯 stdlib）+ `app/sweep.py` + `/api/sweep-plan`（规划）/`/api/sweep-run`（执行，上限 50 组合）+ 前端 `SweepDialog.tsx`（参数编辑/组合预览/结果表/TSV 下载，OutputTab 入口）
  - **校验规则交叉核对**（2026-08-22）：`docs/contracts/validator-crosscheck.md`（OWEN rules.ts 映射）+ validator 新增 ZAID 格式/份额符号/S(α,β) 目标 3 条材料级规则
  - **BEAVRS/17×17/单棒卡进测试夹具**（2026-08-22）：`tests/fixtures/owen/` 解析基线回归
  - **快捷建栅元**（几何标签页「曲面卡 & TR 变换」⚡）：RCC/RPP/SPH 一键生成曲面+TR+栅元（编号顺延/材料密度带出/imp 勾选/实时线框预览，轴固定世界原点 Z 朝上）
  - **栅元列表批量编辑**（几何标签页栅元列表 ⚡，2026-08-23）：勾选多栅元 → 批量改材料号/密度/IMP/高级参数；曲面表达式**只能追加**（锁死提示 + 后缀输入，确认后回填到栅元表达式末尾；留空字段=不改）
  - **格阵 fill 阶段1：数据层（解析+生成+模型+wire）**（2026-08-24）：`app/lattice.py` 深模块（纯 stdlib）结构化解析 prob41c/inp24/17×17/BEAVRS 格阵（FillGrid JSON：range/dims/cells/raw，`17r` 简写 + `(x y z)` 偏移 + 翻译单填充）+ `format_fill_cards` raw 优先回放（R1 字节稳定）；`CellData.fill_grid` + FILL=/FILL 解析收束 + `_generate_cells` 格阵分派 + `_cells_from_list` wire 透传；伴生修复 `_wrap_long_lines` 注释保护与 `parse_data_cards` 连续 C 行丢失；**前端 wire 透传**：`cellBridge.ts` 深模块统一 local↔deck 双向桥接 + 三处类型桥接 + quickCell 透传；parse→deck→localStorage→generate 全链路 `fill_grid` 不丢（含旧数据兜底 `""`）
  - **格阵 fill 阶段2 后端：validate 预检测 + 端点 + golden 配套**（2026-08-24）：`app/lattice.py` 增 `validate_lattice_surfaces(surface_expr,lat,surfaces_text="")->(ok,msg)`（只认带符号整数交集，拒绝 #/:/括号；lat=1 单 RPP/BOX 或 6 PX/PY/PZ 每轴一对± 或 4 平面 2D；lat=2 单 RHP/HEX 或 6 竖直 P 均布 60°+2 PZ 一正一负；自带曲面卡正则解析，纯 stdlib 不依赖 freecad/parsers）+ 新端点 `/api/validate-lattice-surfaces`（api.yaml operationId=validateLatticeSurfaces + 契约闸门 HTTP 用例）+ 跨语言 golden 断言（读 `gui/src/utils/__golden__/latticeGolden.json`，前端未产出 skip）+ **QA 建议落地** `MAX_EXPANDED_ENTRIES=1_000_000` 封顶 nR 展开/补 0（raw 兜底 R1 不回退）；门禁 pytest **650/0（1 skip golden）**
  - **格阵 fill 阶段2 前端：UI 画布**（2026-08-24）：`gui/src/utils/lattice.ts`（TS 镜像 app/lattice.py 深模块，键名逐字一致）+ `LatticeEditDialog.tsx`（6 步状态机：0 类型尺寸→1 材料锁死0+曲面失焦校验 validate-lattice-surfaces+自动生成平面→2 延伸方向 2D/3D→3 宇宙调色板→4 画布涂色+3D 子预览→5 保存，保存 cells 反算覆盖 raw）+ `LatticeCanvas.tsx`（矩形 CSS grid / 六棱柱 hexGrid 蜂窝涂色）+ `LatticePreview3D.tsx`（useThreeCanvas+hexPrism+computeCameraParams 跟手重建）+ `three/useThreeCanvas.ts`+`three/hexPrism.ts` + `universeGroups.ts`+`useDragToGroup.ts`（按 U 分组显示 + 拖组头改 u）+ GeometryTab（格阵徽标列/⬚ 栅格编辑按钮/按 U 分组 toggle）+ CellEditDialog（格阵字段分组入口）+ 跨语言 golden `__golden__/latticeGolden.json`（backend schema 产出，Python/TS 同断言）；门禁 vitest **449/0**（基线 412 + 新增 37）+ tsc EXIT 0 + vite build EXIT 0；**画布不匹配提示已加**（QA 建议3：条目流≠dims 乘积 → 非阻塞横幅）
  - **网格计数（FMESH/TMESH）3D 体积可视化**（独立「3D 结果」窗口）：体积渲染（`glslVersion:GLSL3`）+ 相机 offset 居中 + 图层级半透明 + 自适应色阶下限 + 不相交并集取景 + A1.2 不匹配警告横幅
  - **PTRAC 粒子径迹可视化**（独立「3D 径迹」窗口）：类型三色 × 能量渐变 + 密度抽样 + NPS 高亮 + 自动探测
  - **OUTP 输出解析/绘图/导出 CSV**（`app/outp_parser.py` 纯 stdlib 容错 + `tallyChart.ts` SVG 折线图 + BOM CSV；MCNP6.1 紧凑布局 + F1/F2/F5 泛化）
  - 条件编译行（#ifdef/#else/#endif）、全行拖拽排序
  - E0/En/T0/Tn 网格（线性/对数/自定义）、三种源模式（固定/SDEF/KCODE）、SSW/SSR 面源
  - **文本↔表单双向互转**：材料/几何/计数三标签页（深模块 `useSectionTextMode`）
  - MCNP 检测与一键运行、内联参考文档
  - **AI 接入（MCP over HTTP）**（2026-09-04，1.7.5）：主程序启动时自动拉起 `--mcp-http`（本机环回 **8100** `/mcp` + `/workspace`），外部 AI agent 可直读直改程序当前工作区；前端「🤖 AI」面板给"给 AI 的自配置提示词"。**stdio 接入（`--mcp-server` / 注册MCP.bat）已于 09-04 移除**（reflog `:267`）——`mcnp_bridge.py` 对 `--mcp-server` 现为显式 `sys.exit(2)`（防止 fallthrough 起第二个 5001）。契约见 `inputcard_mcp/`、`AI接入.md`、`docs/inputcard-mcp.md`。
  - **栅元封闭性自检**（2026-09-09）：`/api/check-cell-closure` 判定 6 状态（closed / infinite / semi_infinite / empty / voxel / unresolvable），结果标在栅元列表「封闭」列；3D 预览顺带检测；深模块 `gui/src/utils/{cellClosure.ts,useCellClosure.ts}`。**展示语义（用户 2026-09-10 裁决）**：外无限 = 允许存在、仅提示**感叹号**；**唯有曲面不封闭 = 禁止**。⚠️ 触界判定依赖 bound（`app/_freecad_csg_worker.py:1122-1175`，tol = B×0.005）。
  - **校验规则补全 + 几何水密自检**（2026-09-09）：validator 6 条语法规则（ZAID 格式 / 份额正负号 / S(α,β) 目标核素 / 宏体参数个数 / 80-128 列 / 未定义引用）；几何页「🩺 几何自检」+ 栅元保存/生成 INP 自动触发（FreeCAD BRep 缝隙 + 重叠）。
  - **参数扫描改造**（2026-09-09）：免正则选中即参数 + 多核并行 + 彩色行标记。
  - **源项编辑器权威化 + 主窗口等比缩放**（2026-09-09）：深模块 `sourceAdv.ts`（adv 权威）/ `useDeckSynced.ts` / `appScale.tsx`；源类型模板精简为单点源 / 多点源 / 高级自由（删除七种冗余模板与自动分布预设）。
  - **格阵 fill 三阶段 + 覆盖完整性检测**（2026-08-24~09-04）：`app/lattice.py` 深模块 + 编辑器 UI 画布 + 3D universe 实例化 + `/api/validate-universe-coverage`（红框预防）+ 切面导出（PNG/SVG + CSV，`gui/src/volume/sliceExport.ts`）。
  - ***fmesh 能量沉积可视化**（2026-09-04）：`*FMESH` 卡（MeV/g）解析 + 3D 可视化 + 单位标签。
  - **SDEF 源粒子演示可视化**（2026-09-10，TODO #6，**已提交未打包**）：`DistributionSampler` + `source_sampler.py` + 全宏体拆解 + `/api/source-demo-sample` + 独立「🎬 演示源」3D 窗口。
  - **部署提速 + preview_cache 跨进程持久化**（2026-09-04）：`_surf_classes()` 惰性导入 + 后台预热（`import api_server` 2546ms→299ms）；STL 缓存落盘 `D:\MCNP\memory`（跨后端重启命中）。
- **用户真实数据档案**：`D:\MCNP\new\claude\meshtal`（tally14/p；旧卡=点探测器周围 1×2×2 网格，新卡=±2000 全域 20×20×10）；模型=原点钨板（rpp -1 1 -1 1 0 1）+ 真空 so 1000/2000；输出样本 `tests/fixtures/simple_tally.outp`、`tests/fixtures/real_meshtal_jk.meshtal`
- **已知阻塞**：无

## §3 项目目录结构速查（语义记忆 · AI 定位代码用）

> 修改功能时先查此表定位文件，避免全盘扫描。

| 目录路径 | 功能说明 | 涉及 Agent |
| :--- | :--- | :--- |
| **Python 核心引擎（app/）** | | |
| `app/models.py` | 数据模型：DeckData/CellData/MaterialData/SourceData/BasicSettings/TallySettings/AdvancedSettings 等 dataclass | 后端 |
| `app/generator/inp_generator.py` | INP 生成主引擎（**已知技术债集中地，见 §4 末尾**） | 后端 |
| `app/generator/inp_parser.py` | INP 解析入口 | 后端 |
| `app/generator/parsers/{core,lines,sections,validator}.py` | 解析管线（行/分段/校验） | 后端 |
| `app/generator/validator.py` | 校验逻辑 | 后端 |
| `app/freecad_preview.py` / `_freecad_csg_worker.py` | FreeCAD 3D CSG 求值（子进程） | 后端 |
| `app/stl_cross_section.py` / `_freecad_cross_section_worker.py` | 截面（numpy 切 STL，不依赖 FreeCAD） | 后端 |
| `app/step_importer_geouned.py` / `geouned_worker.py` | GEOUNED STEP→MCNP 转换封装 | 后端 |
| `app/step_importer.py` / `freecad_locator.py` | STEP 导入 / FreeCAD 定位唯一入口 | 后端 |
| `app/xsdir_db.py` / `material_presets.py` / `material_library.py` | xsdir 截面数据库 / 预设材料库 / **用户材料库持久化（深化，custom/override、导入导出、xsdir 反向索引、组成自洽）** | 后端 |
| `app/outp_parser.py` | **OUTP 输出解析（纯 stdlib 容错，V1.7.2.2 新增）** | 后端 |
| `app/mctal_parser.py` / `app/sweep.py` | **mctal 输出解析（k-eff/收敛/tally）** / **参数扫描纯函数（对齐 OWEN sweepCore）** | 后端 |
| `app/meshtal/` | 网格计数解析/体积构建/配色/cache/deck_match/worker（8 模块） | 后端 |
| `app/ptrac/` | PTRAC 粒子径迹解析 + worker | 后端 |
| `inputcard_mcp/` | **AI 接入 MCP server（本地 stdio，6 工具：read/generate/validate/list_section/patch_section/add_shape，按语义段全量读写；打包用 `mcnp_bridge --mcp-server` 分派）** | 后端 |
| | | |
| **前端（gui/src/）** | | |
| `gui/src/App.tsx` | 主界面（顶栏/导入/生成/保存恢复/主题） | 前端 |
| `gui/src/components/` | 标签页组件：BasicSettings/MaterialTab/GeometryTab/SourceTab/TallyTab/AdvancedTab/OutputTab。**TallyTab 的"前缀/环探测器轴"必须经 `utils/tallyBridge.ts` 落 deck**（2026-09-26 起，见 §6 接缝那条） | 前端 |
| `gui/src/components/Preview3D.tsx` / `Preview3DWindow.tsx` | Three.js 3D 预览（独立窗口） | 前端 |
| `gui/src/components/CrossSectionView.tsx` / `CrossSectionWindow.tsx` | 平面截面（独立窗口）；**视图变换/拖动换算一律走 `utils/sectionView.ts`**（2026-09-26 起：旋转中心不得含 `pan`） | 前端 |
| `gui/src/three/` | 3D 深模块：cameraParams/renderGate/cellMaterial/TickGrid（`setLabelTheme` 屏幕·纸质两种标签底）/axisConfig（轴单一事实来源；**`color` 屏幕色 + `paperInk` 出图墨色**）/planeOffset（截面平面坐标换算）/quickCellPreview（快捷建栅元线框） | 前端 |
| `gui/src/volume/` | 体积可视化 11 模块（volumeShader/VolumeRenderer/colorize/alignWorld/downsampleRequest/fmeshState/ColorLegend/FMeshForm/VolumeControlPanel/ResultWindow/surfacesAABB） | 前端 |
| `gui/src/ptrac/` | PTRAC 径迹 3D 窗口模块（trackColors/PtracRenderer/PtracWindow 等） | 前端 |
| `gui/src/utils/quickCell.ts` / `gui/src/components/QuickCellDialog.tsx` / `QuickCellForm.tsx` | 快捷建栅元：纯函数生成（编号/校验/RCC/RPP/SPH/**HEX/TET**）+ 弹窗；**表单是固定像素排版，宿主宽度必须 ≥360px**（见 §5）；重合检测**恒开**（勾选框已按用户裁决删除） | 前端 |
| `gui/src/utils/useQuickAddOverlap.ts` | **快捷建栅元重合检测+补集决策深模块（GeometryTab/Preview3D 共用）** | 前端 |
| `gui/src/utils/batchCellEdit.ts` / `gui/src/components/BatchCellEditDialog.tsx` | 栅元列表批量编辑：纯函数应用（空字段=不改、曲面只追加）+ 弹窗 | 前端 |
| `gui/src/utils/rawOverrides.ts` | **raw_overrides 纯函数构造（V1.7.2.2 新增，含 sdef）** | 前端 |
| `gui/src/utils/tallyChart.ts` | **OUTP 结果 SVG 折线图纯函数（V1.7.2.2 新增）**（2026-09-17 起：屏幕弹窗已由 `TallyChartWindow` 取代，此函数仅供单测/历史） | 前端 |
| `gui/src/utils/tallyChartPaper.ts` | **出图版 tally 曲线**（论文配色、透明底、尺寸自适应、对数能量轴、误差棒、图例） | 前端 |
| `gui/src/export/` | **出图链 12 模块（2026-09-17 新增；2026-09-19 出口收敛为「一律 PNG、白底」——当天先做成透明底、实机看过之后用户改口，见 S8.8；同日抽出版面权威 `figureLayout`，见 S8.11）**：plotTheme（屏幕/论文两套配色的单一权威 + `hexToInt`/`clearColorFor`）/captureFrame（WebGL 帧捕获 + **`captureTransparent3D` 透明取帧**（供合成用，与产物底色是两件事）+ `snapshotSvg`（含 **`strokeScale` 描边换算**）+ **`withPngDpi` 物理尺寸元数据**）/figureCanvas（栅格合成图版面）/vectorFigure（矢量合成；`background`/`maxPanelSide`/`legend`；`figureToPdf` 保留但门面已不调）/**figureLayout（出图版面单一权威：图题在图下居中、图注在左下；两个渲染器共用 ⇒ 8 个出图视图一起变）**/quantityLabels（量的名称/符号/单位字典，GB 3100 口径）/contour（marching squares 等值线）/planeSample（任意平面切取样）/cjkFont（中文字体探测；**现仅供矢量 PDF 出口**）/saveFile（落盘）/figureSpecs（各视图的"图由哪些块组成"）/exportFigure（门面：**只出 PNG、固定白底、按目标 dpi 反算倍率**）/useFigureExport（窗口接线按钮） | 前端 |
| `gui/src/three/planeEquation.ts` | **切割平面方程单一权威**：解析/格式化/步长折半加倍/成叠平面序列（3D 预览截面、截面窗口、fmesh 切面三处共用） | 前端 |
| `gui/src/components/PlaneControls.tsx` | **平面方程 + 步长 + 步进共享控件**（上条那三处共用，避免步长语义分叉） | 前端 |
| `gui/src/components/TallyChartWindow.tsx` | **「Tally 通量图」独立窗口**（原为输出页弹窗，图小/与数据表互挤/不可导出） | 前端 |
| `gui/src/utils/DeckContext.tsx` | **单一权威表单状态**（localStorage 键 `mcnp_workspace_v1`）；`TallyDef` 含**卡片身份字段** `fn_prefix`/`number_suffix`（漏传即换卡，见 §6） | 前端 |
| `gui/src/utils/tallyBridge.ts` | **计数卡行双向桥接纯函数（2026-09-26 新增）**：`deckTalliesToRows`/`rowsToDeckTallies`/`splitTallyNumber` —— 前缀 `*`/`+`/`FIP|FIR|FIC` 与 F5 环探测器轴 `X|Y|Z` 全靠它过缝（键序照后端回显顺序，护 `useDeckSynced` 等价判定） | 前端 |
| `gui/src/utils/dragImport.ts` | **拖入导入覆盖层判定纯函数（2026-09-26 新增）**：只有**真拖文件**（`types` 含 `Files`）才亮；`leave`/`drop`/`end` 一律熄 —— 旧实现让"内部拖拽 + 没有 drop"永久卡在粉色页面（见 §6） | 前端 |
| `gui/src/utils/sectionView.ts` | **二维截面视口/变换纯函数（2026-09-26 新增）**：viewBox / 旋转中心（**不含 pan**）/ 组变换 / 等比缩放（`preserveAspectRatio` 留白）/ "拖动 Δpx → 新 pan" —— 不变量"任意旋转角下拖 Δ ⇒ 内容正好移 Δ"由属性测试锁死 | 前端 |
| `gui/src/utils/useSectionTextMode.ts` / `sectionConvert.ts` | 文本↔表单互转深模块 + API 封装 | 前端 |
| `gui/src/utils/gridState.ts` | E0/En/T0/Tn 网格解析/序列化深模块 | 前端 |
| `gui/src/utils/backend.ts` / `dataCollector.ts` / `contract.ts` | 后端生命周期 / 表单收集 / 数据类型 | 前端 |
| | | |
| **后端（gui/backend/）** | | |
| `gui/backend/api_server.py` | **HTTP 后端总入口**（路由表见 api.yaml，端口 5001） | 后端 |
| `gui/backend/mcnp_bridge.py` | 打包后 sidecar 启动器（含 `--meshtal-worker` 分派） | 后端 |
| `gui/backend/generate_step.py` | STEP 生成（备用） | 后端 |
| | | |
| **窗口外壳（gui/src-tauri/）** | | |
| `gui/src-tauri/tauri.conf.json` | 无边框窗口、sidecar 配置（externalBin: python） | 后端 |
| `gui/src-tauri/src/main.rs` | Tauri Rust 入口（close_window / open_volume3d_window 等） | 后端 |
| | | |
| **文档** | | |
| `README.md` | 项目总览（技术栈/功能/打包说明/项目结构） | — |
| `app/docs/` | MCNP 参考文档（曲面卡/FN 卡/输出卡/PRINT/C810/源分布/sample_format） | — |
| `app/UI_ARCHITECTURE.md` | UI 架构说明：三层边界/启动链路/deck JSON 契约/raw_overrides/往返保真/技术债地图 | 架构师 |
| `docs/contracts/api.yaml` | **OpenAPI 3.0 契约**（**49 path / 49 operationId**，每 path 带 operationId，防漂移闸门验证） | 架构师 |
| `docs/CHANGELOG.md` | **完整变更流水档案（2026-08-22 起，历史 §8 外置于此）** | 项目经理 |
| `docs/backend-changes.md` / `frontend-changes.md` | 后端/前端逐批改动清单 | 架构师 |
| | | |
| **测试** | | |
| `tests/` | **测试网**：unit + parser + integration（含契约闸门/真实 HTTP）；`gui/test/` vitest（含 jsdom DOM 交互测试）。**计数基线见 §9——历史数字多为各批当时快照，勿直接引用** | 测试 |

## §4 关键架构决策 ADR（语义记忆）

> ⚠️ 本 § 编号被 docs/contracts/* 引用，**不得改名**。

| 决策 | 理由 | 日期 |
| :--- | :--- | :--- |
| 后端用 Python 标准库 http.server，不用 Flask | 减少依赖，PyInstaller 打包 sidecar 更简单 | — |
| 前端单一权威状态在 DeckContext（localStorage 工作区） | 8 个标签页共享一份数据，避免多源状态冲突 | — |
| 文本↔表单互转按 section 维度做深模块（useSectionTextMode） | 材料/几何/计数三处共用一套进出文本模式逻辑 | 近期 |
| 3D 预览用 FreeCAD 子进程 CSG 求值输出 STL | FreeCAD 精确几何；STL 保留供截面复用（numpy 切），不重复调 FreeCAD | — |
| 截面不依赖 FreeCAD，直接 numpy 切 STL | 独立窗口即时响应，无需 CAD 内核 | — |
| GEOUNED 随程序 vendor 打包，用户只装 FreeCAD | STEP 导入开箱即用；FreeCAD 经 locator 检测/手动指定 | — |
| 全部代码遵循**深模块原则**（用户全局记忆 codebase-design-always） | 小接口覆盖复杂行为，AI 友好、可测试 | — |
| **P1 多源/分布 SDEF 表示统一**（`SDEF_FIELD_SPECS` 表驱动 + 字段序 POS 首位 + D-index 由 `dist_params` 位置决定） | kitchen-sink R1/R4 字节不动点要求多源生成与分布回放逐字节一致 | 2026-08-12 |
| **P1 分布注释作为生成器横幅词汇**（`multi_source_comment_banner` 进 `is_generator_banner`） | 复用 F-A 方案 C 的词汇冻结机制，注释不漂移不重复 | 2026-08-12 |
| **P1 raw_overrides 收敛为 `_apply_raw_override` 助手**（1145 raw_tally 门控保留） | 消除 8 处复制粘贴 | 2026-08-12 |
| **3D 预览 deck 指纹缓存**（`app/preview_cache.py`，LRU 上限 3） | 打开卡真凶=全量重建 3.30s；缓存命中 ≤1s | 2026-08-12 |
| **前端 3D 拆深模块**：TickGrid/renderGate/cellMaterial/computeCameraParams | 交互卡真凶=纹理泄漏+无条件渲染+透明 overdraw；大坐标深度超 2^24 | 2026-08-12 |
| **前端后端地址收敛 `127.0.0.1:5001`** | 规避 Chrome Happy Eyeballs 每请求 300-500ms 延迟 | 2026-08-12 |
| **重合栅元几何检查走方案 A（FreeCAD 精确布尔 + AABB 预过滤）**，独立 `/api/check-overlap`；纯分类下沉 `app/overlap_classify.py`；结果同指纹落 preview_cache | 反馈 #7（参考 VISED，P2）；弃 B（STL 不封闭）/C（AABB 伪报率高）；独立端点不污染 preview-3d 契约；**本轮不施工仅存档** | 2026-08-13 |
| **MCNP 卡类型唯一权威源=官方 C810.pdf**；`docs/contracts/card-lexicon.md`（词条目录+解析器清单+差异表）与 `app/docs/` 蒸馏 md 均为**派生**，须随 PDF 更新 | 反馈 #1 FM 漏识别暴露系统性缺陷=解析器卡类型清单未与知识库对齐 | 2026-08-13 |
| **网格计数（FMESH/TMESH）3D 体积可视化契约**（`docs/contracts/meshtal-visualization.md`，16 节） | 对标 VISED；用户拷问敲定全部澄清项；测试先行 + 零新依赖红线 | 2026-08-14 |
| **meshtal-texture 返回标量帧 Uint8，前端 colorize CPU 上色**（python/TS 双端 golden sha256 对照） | 改色阶只重跑本地 colorize；Uint8+CPU 上色避开 float 纹理坑；双端 golden 防漂移 | 2026-08-14 |
| **体积窗口独立场景，不改 Preview3D.tsx 主组件**（复用纯模块）；几何外壳与体积盒共享 offset 对齐；关闭不清 preview-3d STL 会话 | 复用会污染 preview3d-performance 契约 | 2026-08-14 |
| **meshtal 后端落地细节**：数据行列序按实际 MCNP `[Energy] [Time] X Y Z Result RelError`；colormap golden = t-space 插值 round-half-even；worker 模块顶只 stdlib；大文件走子进程 + cache 不阻塞 5001 | golden 是 §4.3.1 跨语言防漂移强契约；"Total" 汇总行跳过 | 2026-08-14 |
| **3D 预览截面坐标双修**：后端 on-plane 顶点作交点 + 共面三角面贡献外轮廓边 + `_join_loops` 容差走环；前端 `planeOffset.ts` 换算 D_raw=D_disp+n·center | 面重合切割旧实现返回 0 环/错环 + 多环被贪心串接；预览归一化平移与后端原始坐标不一致 | 2026-08-18 |
| **快捷建栅元模块化**：纯函数 `quickCell.ts` 集中编号/校验/生成；斜向用 6 局部平面 + TRn（行=局部轴方向余弦）而非 RPP+TR | 规避 worker 对带 Placement 宏体半空间补集布尔缺陷；编号/密度带出/文本模式禁用集中，vitest 可测 | 2026-08-18 |
| **OUTP 解析：pymcnp 正确 API（`Outp.from_mcnp(text).to_dataframe()`）优先 + `app/outp_parser.py` 纯 stdlib 容错兜底**；前端 `tallyChart.ts` 纯函数 SVG 绘图 + CSV 加 BOM | pymcnp 0.9.1 只认 MCNP6.2 布局、MCNP6.1 紧凑布局解析为空；兜底支持 energy 列/total 行可有可无、F1/F2/F5 泛化 | 2026-08-19 |
| **IMP 归一化在生成器层（`_generate_cells`）单一权威**：任一结构化栅元写 imp_n/p/e → 全部补齐，缺省补默认重要性 1 | 部分栅元有 IMP、部分没有 → MCNP 硬规则 fatal；表单/导入/快捷建栅元全路径生效 | 2026-08-19 |
| **SDEF 表单模式回退分支**（`_sdef_dispatch`）：distribution/sdef 无分布时 sources 优先（保 R1 不动点）→ 表单字段有值合成单源 → 全空 `[]` | 表单字段写 `adv.sdef_*` 但无分布时旧逻辑返回空 → INP 无 SDEF | 2026-08-19 |
| **含 GQ/SQ 栅元走纯 numpy 体素 CSG（`app/mc.py` + `app/voxel_csg.py`），去掉 vtk 依赖**；`mesh_cell_polydata(ast, surfaces_by_num, tr_cards, B, res)` 返回 (vertices, triangles)；TR 求值前 `p_local=rotate⁻¹·(p_global−o)`；**带 TR 的有界曲面 AABB 经 8 角点变换求全局紧盒（`_transform_aabb`），无界才保守全盒**；**margin 按实际扫描盒间距（勿用全局 B）**；失败降级包围盒 + `栅元 N: GQ/SQ 网格化失败` 告警 | worker 跑在 FreeCAD 自带 Python（无 vtk）→ GQ/SQ 兜底必失败；OCC 对网格化二次曲面半空间布尔不可靠；实测 TR 被完全忽略 + B=500 下全盒/margin 坑致小栅元空网格 | 2026-08-22 |
| **GQ/SQ 渲染后续增强（同日）**：① **2D 解析切片**（`app/analytic_slice.py`）——切割平面逐点解析求值 + 2D marching squares 轮廓，preview-3d 会话存 deck 快照、cross-section 对 GQ/SQ 栅元自动走解析切片；② **切线平面法快路径**（`voxel_csg._tangent_plane_mesh`）——单个内侧椭球/球/圆柱 + 平面封口 → 切线半空间 + 凸裁剪（Sutherland–Hodgman + 盖面极角排序），水密；椭球 162 方向 + 绕中心体积校正（无封口）/642 方向（有封口），圆柱 48 段；union/补集/多二次曲面/锥回退 MC | 截面轮廓位置精度只取决于解析求值（STL 受网格分辨率限制）；切线路径三角形数 ~600 vs MC ~10 万；OWEN csgScene 的做法（金螺旋方向分布不均 + 边链盖面在贴面顶点退化）不能直接照搬 | 2026-08-22 |

## §5 核心业务规则（语义记忆 · 必读）

- **⭐ 3D 预览「渲染哪些栅元」的分类规则（项14，2026-08-24 用户确认；2026-09-24 补第二条判据）**：
  唯一实现 = `gui/backend/api_server.py::build_cells_data`，按序：
  1. **fill 装配容器**（`fill` 非空 或 `fill_grid` 非空，含 `fill="0"`）→ 跳过自身 STL（内容由 FILL 装配走 preview-lattice）；
  2. **graveyard → 不渲染**，判据**两条并列、各管一段**：
     · `imp_n/imp_p/imp_e` 任一为 `0`（MCNP 语义：该粒子重要性 0 = 杀粒子）；
     · **注释含 `graveyard`**（大小写不敏感）—— **GEOUNED 的官方标记**，`void.py:201/208` 写死
       `MatInfo = "Graveyard_in"/"Graveyard"`，GEOUNED 自己的 `mcnp_format.py:256` 也这么认。
  3. `render:false` → 跳过；
  4. 其余实体（`material≠0`）与纯 void（`material=0`，无 fill 无 u）→ 参与 STL（`include_void=True` 时）。

  **⚠️ 两条判据的分工（2026-09-24 实测查准，别记错）**：GEOUNED 生成的 deck **是带 imp 的**，
  实测 `47 0 277 Vol=1.000 imp:n=0 imp:p=0 $Graveyard`、`46 0 -277 (...) imp:n=1.000 $Graveyard_in`：
  | 栅元 | imp 判据 | 注释判据 | `imp:n` | 说明 |
  |---|---|---|---|---|
  | 47 | **命中** | 命中 | **0** | 真墓地（半径 1049 球**外**）—— imp 本该就拦住它 |
  | 46 | 不命中 | **命中** | **1.000** | `Graveyard_in`（球**内**、enclosure 盒外）—— **GEOUNED 有意给 imp=1**（粒子可在其中飞行，按 MCNP 语义不是墓地），但它是 GEOUNED 的边界结构、体积达模型 1583%，同样不该画 |
  ⇒ **imp 判据失效的原因是上游丢字段**（`flat_cell_json` 没输出 `imp_*`），**不是 GEOUNED 没写 imp**。
  ⇒ **为什么必须拦这两个**：它们的 bbox 是 **2927³ / 2097³**，而模型只有 1042×1751×260 ——
  一旦渲染就把模型整个包住、相机被撑到 ±2000 ⇒ 用户看到"一坨"（2026-09-24 实证，见 S10 与 §6）。
  ⇒ **改这条规则前先读**：这些键**全部**由 `app/step_importer.flat_cell_json` 供给（STEP 导入 → 前端
  → preview-3d 的唯一序列化口，契约见 `docs/contracts/api.yaml` 的 `deck.cells`）——
  **判据"读不到就放行"，所以序列化口漏一个键就等于该条规则静默失效。**

- **⭐ hexCenter 权威公式（单一事实，2026-09-10 立此条目以防误用）**：
  ```
  x = col * pitch + row * pitch / 2
  y = row * pitch * √3 / 2
  ```
  代码权威在**两处且必须逐位一致**：`gui/src/utils/lattice.ts:130-137` ↔ `app/lattice.py:604-616`。
  **⛔ 历史记录里的旧公式不要照抄**：本项目 2026-08-25 之前用的是"pointy-top 顶点+X"式
  `x = i·p·√3/2, y = j·p + (i%2)·p/2`（差 30° 旋转），已全部替换。**本记忆文件 §1~§3 与 S1/S2 历史条目里、
  以及 `docs/frontend-changes.md` / `docs/qa-report*.md` / `docs/backend-changes.md` / **`docs/contracts/lattice-fix15-design.md`（含 L1 锁死表）**
  中出现的旧式写法均为历史残留**。⚠️ **L1 锁死表曾写错公式 —— 它是跨语言实现依据，写错会污染实现**（审计 TD-29）。
  被反复"根因修复"过的高危公式，改前先查本节。

- **⭐ RHP/HEX 的 `r/s/t` = 面心矢量（边心距），不是顶点矢量（2026-09-20 立此条目，改六棱柱几何前先读）**：
  C810 p.3-21 原文「`r1 r2 r3` = vector from the axis to the **middle of the first facet**」，
  例题 `RHP 0 0 -4  0 0 8  0 2 0` 亦写「first facet is normal to the y-axis **at y=2**」。
  ⇒ 边心距 = `|r|`；六个侧顶点 = **相邻两面（法向 ±r,±s,±t，相邻 60°）的交点**，
  外接半径 = 边心距 / cos30° = `2|r|/√3`；顶点在 30°+k·60°、面法向在 0°/60°/120°（`r` 沿 +x 时）。
  **唯一实现** = `app/quadric.py::rhp_hex_vertices(r1, r2, r3)`（`[1 c; c 1][α;β]=[A;B]` 解交点，
  `(r1,r2) (r2,r3) (r3,−r1)` 三对 + 反号，返回**绕轴循环序**）。**六个消费者必须都调它**：
  `voxel_csg.surface_fn` / `voxel_csg._macrobody_aabb` / `_freecad_csg_worker._make_hex_from_params` /
  `lattice._rhp_extent` / `freecad_preview._surface_extent_values`（bound）/
  `gui/src/volume/surfacesAABB.ts::rhpCorners`（TS 侧同名规则；9/12 项要按 `rot60` 推 s/t）。
  ⛔ 别再写 `v = base ± r1 ± r2 ± r3`（那是"把面心当顶点"，六棱柱转 30° 且小 13.4%），
  也别把 `±r1,±r2,±(r1−r2)` 当极值点（那是面心本身）。`HEX` 是 `RHP` 同义词，两条路必须同源。
- **⭐ 源粒子的 WGT 有两类补偿，缺一即错（2026-09-20 立此条目）**：
  ① **SB 表偏倚**（C810 p.3-64「The weight of each source particle is adjusted to compensate for the
  bias.」）⇒ 抽样按**偏倚**概率、权重 ×(真概率/偏倚概率)，按**抽中的档位**算（不是按值反查）；
  ② **内置函数被 SI 截断**（C810 p.3-66「**Unless the function is −21 or −31**, the weight … adjusted to
  compensate for truncation of the function by the entries on the SI card.」）⇒ 按 `[I1,I2]` 抽条件分布
  并 × `P(I1≤x≤I2)`（对未截断密度算），`−21/−31` **豁免**。
  两条都由 `DistributionSampler.sample_with_corrections(eid, rng, …) -> (值, 因子)` 统一产出
  （`SI S` 递归时沿路径相乘），`source_sampler._Context._smp` 把它并进 `_w_corr` → `sample_one` 末尾并入 WGT。
  ⚠️ **加新的抽样路径时别再绕过 `_smp`**（历史教训：`_default_power_law` / `_sample_pos_dist` 各自直连
  sampler，导致补偿在那两条路上被静默丢弃）。


  每一行是「行首标签列 **64px** + N 个字段列 **70px** + `gap:10`」的**固定像素**排版；
  最宽一行（切面类的"切分 X 份/Y 份/Z 份"）实测需要 **356px** ⇒
  **宿主给它的宽度必须 ≥360px**。当前两个宿主的实测可用宽度：
  `QuickCellDialog` 左列 `width:380` → 376px ✅ ／ `Preview3D` 右侧栏默认 300 → **271px ❌**，
  所以**打开快捷建栅元时侧栏必须加宽**（`Preview3D.QUICK_CELL_PANEL_W = 400` → 371px ✅）。
  ⚠️ 行容器 `alignItems` 必须是 **`flex-start`**：行首标签列是"标签在上"的纵列，
  用 `flex-end` 会让行标签跟**输入框底边**对齐、比字段标签低一整格（实测 y 差 29px）。
  ⛔ 往更窄的容器里塞之前，先把表单改成自适应排版，**别只调宿主宽度**（那样只会把输入框裁掉且无从察觉：
  父级是 `overflow-x:hidden`，用户滚也滚不到）。

- **版本号规则（上级硬规则）**：**任何 bug 修复批次严禁提升版本号**（改多少轮 bug，文件版本号恒为当前版本）。仅**实际新功能**上线才由上级重新指定版本号——快捷建栅元用户指定 **1.7.2**（2026-08-18）；AI inputcard-mcp + 六棱柱/四面体 **1.7.5**（2026-09-04）；**当前版本为 1.7.6**（2026-09-11 用户指定：源演示修复二批 + 粒子圆点化 + 一键运行 MCNP 多核 tasks）。打包时版本**六处**（`tauri.conf.json` / `package.json` / **`package-lock.json`** / `Cargo.toml` / `Cargo.lock` / README 徽章）必须一致；**Cargo/tauri 只接受 `主.次.修订`**，四段号（如 1.7.2.2）会构建失败，仅可作批次号。
- **依赖红线（上级 2026-08-14 更新）**：**新依赖一律须用户批准，且由用户指定安装位置**（2026-08-23 更新：不再默认零新依赖；评估时列出依赖名/用途/体积/许可/替代方案，批准后按用户指定位置安装，如 node_modules 常规位置或 vendored 目录）；**严禁自动运行 npm install / npm ci / pip install**（用户高度敏感，违反即打回）；测试不得 import gui.backend.api_server（模块级 pyvista/FreeCAD 探测污染）。**2026-08-22 用户批准的唯一例外**：`jsdom` / `@testing-library/react` / `@testing-library/dom`（devDeps，用于 SweepDialog DOM 组件测试，已写入 package.json）。
- **⚠️ 违规记录（2026-09-17，已追认）**：出图功能实现时**未经批准先跑了 `npm install --save jspdf svg2pdf.js`**（违反上条"严禁自动运行 npm install"）。事后向用户补报清单并**获追认为 dependencies**。教训：先把评估清单给用户，再动手装——这次是"先装后报"，顺序错了。
- **出图依赖（2026-09-17 用户追认，写入 `gui/package.json` 的 dependencies）**：
  | 依赖 | 用途 | 体积 | 许可 | 替代方案 | 备注 |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | `jspdf@^4.2.1` | 生成 PDF（矢量/位图两条路）；含 `html2canvas`/`fflate`/`fast-png` 传递依赖 | 打进 bundle **390 KB**（npm 包 30.3 MB 含全部构建与文档） | MIT | 自写 PDF writer（要自己处理字体子集，成本高）；或只出 SVG | **动态 import**，只在点导出时才加载，不影响启动。⚠️ **2026-09-19 起门面只出 PNG ⇒ 这两个依赖当前无调用方**（`figureToPdf` 实现保留）。是否清掉待用户裁决：清掉可减 477 KB bundle，但会一并失去"将来一键恢复矢量 PDF"的能力 |
  | `svg2pdf.js@^2.8.1` | 把 SVG 矢量图转成 PDF（内联 `<path>`/`<text>`） | 打进 bundle **87 KB**（npm 包 2.4 MB） | MIT | 无成熟替代 | ⚠️ 必须走 **ES 构建**（`vite.config.ts` 里 alias 钉住）：其 package.json 无 `exports`，Vite 默认取 UMD，而 UMD 在 ESM 下加载即崩 `Cannot read properties of undefined (reading 'jsPDF')` |
- **权威源**：MCNP 卡类型唯一权威 = `D:\MCNP\MCNP6\C810.pdf`（实际 = MCNP5 卷 I+II 全文 + 发布说明；卡格式权威章 = MCNP5 卷 II Ch.3，PDF 页 526-691）；`app/docs/` 蒸馏 md 与 `docs/contracts/card-lexicon.md` 均为**派生**，须随 PDF 更新。
- **DeckData 是聚合根**：前端 DeckContext ↔ 后端 generate/parse 全走 DeckData 单对象，避免参数膨胀。
- **密度写在栅元卡（CELL）上**，材料卡（Mm）只含 ZAID+份额，不含密度。
- **栅元/材料/计数行支持判别联合**：`kind=="cell"|"raw"`（栅元）、`kind=="nuclide"|"raw"`（材料）——`raw` 行承载 `#ifdef/#else/#endif` 原样条件行。
- **文本模式状态存在 deck.textMode[section] + deck.rawOverrides[section]**；进文本模式前必须由后端先生成当前表单的文本（section-to-text），防数据丢失。
- **STL 会话**：3D 预览生成的 STL 保留在 `_STL_SESSION`，供截面复用；只在关预览窗口/清空时 `/api/clear-stl` 删除。
- **曲面文本解析**：GEOUNED 常见 `*TRn` 后缀或 `100*` 前缀的 TR 引用，均需提取 transform；P 卡 `A B C D` 系数形式需转三点定义（注意法向同向性）。
- **SDEF 三种模式**：`fixed`（固定点源）/ `distribution`（SDEF 分布源，SI/SP/DS 结构化 JSON 优先于 sdef_raw_text）/ `kcode`（KCODE/KSRC/HSRC）。
- **前端契约层**：`sectionConvert.ts` 只认 `{status:"ok"}` 成功响应，`/api/text-to-section` 返回 `{data}`，`/api/section-to-text` 返回 `{text}`。
- **测试时间限制（上级 2026-08-22）**：所有测试/构建命令必须加**硬性时间限制**——探活/HTTP 请求/PyInstaller 等长命令用 `Start-Process` + `WaitForExit(超时)` + `Kill`，超时即杀并明确报错，严禁无限挂起。

## §6 踩坑与排雷指南（情景记忆 · 经验教训）

- **❗拖入导入覆盖层：内部拖拽也会触发，且"没有 drop"就永久卡死（2026-09-26 真 Chrome 实测 + 用户报"卡死在导入时的粉色页面"）**：
  `dragenter` 是**任何** HTML5 拖拽都会触发的 —— 拖拽起点落在**已选中的文字/可拖元素**上时，浏览器起的是原生拖拽，
  其 `dataTransfer.types` 只有 `text/plain`、**没有 `Files`**。旧 `App.tsx` 对任何 `dragenter` 都点亮全屏覆盖层
  （`inset:0; zIndex:9999`），而 `dragleave`/`dragend` 只 `preventDefault()`、**从不清除** ⇒ 松手在窗口外/Esc/跨文档拖动
  （`dragend` 只在**源文档**触发）时覆盖层永久留在屏幕上，`elementFromPoint` 命中的就是它 ⇒ 点击全被吃掉 = "卡死"。
  **三条铁律**：① 只认**真拖文件**（`types` 含 `"Files"`）才亮；② `leave`/`drop`/`end` **一律熄灭**（覆盖层不保留"等一个 drop"的记忆）；
  ③ 覆盖层加 **`pointerEvents:"none"`**（就算意外亮起也绝不吃点击）。实现收敛在 `gui/src/utils/dragImport.ts`，回归 `gui/test/dragImport.test.ts`。
- **❗"拖动/旋转"这类视图变换必须用不变量当测试，而且要当心"中心点含平移"（2026-09-26 用户报"截面旋转后拖动很怪异"）**：
  `<g transform="scale(1,-1) rotate(θ cx cy)">` 里 **cx 一旦含 `pan`，平移量就被卷进旋转矩阵** ——
  `d(screen)/d(pan) = k(I − S + S·M)`，于是拖 Δ 的真实位移是 `(I − S + S·M)Δ`：**既偏方向又放大**（θ=37° 实测 63/−41 变 74.99/−87.17，长度 ×1.53、方向差 16°）；
  **θ=0 时 M=I ⇒ 退化为 Δ（正确）**，所以"平时看不出来、转过才怪"。另：像素↔用户单位必须用**等比缩放** `min(rw/w, rh/h)`
  （SVG 默认 `preserveAspectRatio="xMidYMid meet"` 会留白），"X 用宽、Y 用高各算一套"在长宽比不匹配时拖动跟不上鼠标（实测只走 66.7%）。
  **纪律**：把变换抽成纯函数（`utils/sectionView.ts`）+ 断言**不变量**"任意旋转角下拖 Δ ⇒ 内容正好移 Δ"，别去断言 transform 字符串；
  另加**组件 DOM 测试**锁"渲染出的 `viewBox`/`transform` 与算法一致"—— 本轮就是靠它抓到"把 `dragStart` 记录当 pan 传入"（纯函数全绿照样错）。
- **❗模型/引擎里有字段 ≠ 前端拿得到：接缝必须双向核对（2026-09-26 用户报"计数卡前缀 `*` 解析传不进来、点选后生成也没有"）**：
  `_deck_to_frontend_dict`（序列化）与 `_tally_from_dict`（反序列化）**两头都漏** `fn_prefix`/`number_suffix`，
  前端 `TallyTab` 更把下拉框做成装饰品（`deckToLocalT` 写死 `prefix:""`、`localToDeckT` 不写 `prefix`）——
  而引擎侧 `parse_f_tally`/`_generate_tallies` 一直是对的，`test_regress_fm_prefix.py` **只测引擎侧**所以这条缝永远绿。
  **纪律**：卡片"身份字段"（前缀/后缀/粒子/编号）在**导入（后端→前端）与生成（前端→后端）两个方向**都要有断言；
  新增字段时同步四处（后端两处映射 + `DeckContext` 类型 + 桥接纯函数），否则"界面上选了、INP 里没有"且**全程无报错**。
- **`#` 是 MCNP 几何里唯一"前面必须有空白"的算子；行首 `#` 必须按**后随字符**判性质（2026-09-26 用户实测）**：
  ① **缺空格**：`-14#1#2#3` → pymcnp `TypesError: MCNP data type not recognized` ⇒ AST=None ⇒ 该栅元在 3D 预览/源演示/重合检测里**静默消失**；
  `-14 #1 #2 #3` 正常；而 `:`/`(`/`)` 紧贴都能解析（实测 `1 -2:3`、`(1 -2):(3)` 均 OK）⇒ **只补 `#` 前那一个空格**（`lines.normalize_geometry_spacing`，挂 `parse_cells` 与 `parenthesize_unions` 两侧；已规范文本逐字不变，护 R1）。
  ② **行首判性质**：`#` 后是**字母** = MCNP 预处理器 / THTME 表头（`#ifdef`、`#    tmp1 …`）⇒ 续行断点、单独成行；
  `#` 后是**数字/括号** = 几何**补集算子**（`#25`、`#(1 2)`）⇒ **接回上一张几何卡**（用户手工折行时行首正好是 `#`，旧实现整行抛成"条件行"⇒
  栅元 5 的 `surface_expr` 截断在 `#24`、**丢 31 项补集**、`imp` 与 `$` 注释一起丢）。边界：仅当上一行首 token 是**数字**时才强制接回（THTME 表头才不会被误并）。
- **打包链三个新增实测坑（2026-09-26，打包 v1.7.7 时踩到）**：
  ① **`npm run build:release` 在干净工作区（无 `dist_sidecar/`）必失败** —— 它把 `vite build + tauri build` 排在 PyInstaller **之前**，
  而 `tauri.conf.json` 的 `beforeBuildCommand` 含 `sync-sidecar`、正等着 `dist_sidecar/`（实测 `[sync-sidecar] ❌ PyInstaller 产物不存在 … 已中止`
  → `Error beforeBuildCommand … failed` → `build-release ❌ tauri build`）⇒ **干净机/首次构建走手册手工顺序**（vite → PyInstaller → binaries → `npm run build:app`）。
  ② 手册第 4 步的 `--workpath build_sidecar` 与 `build-release.mjs` 清缓存清的 `build/mcnp_sidecar` **不是同一个目录** ⇒ "坑 B 清缓存"对不上；
  可信的新版判据是**哈希对拍 + 端点功能级冒烟**（本轮即用：`_internal\app\**` 松散 `.py` 与源码 sha256 一致 + 部署版打 `/api/parse-inp` 验本批修复）。
  ③ **主程序关闭后 `--mcp-http` 子进程（8100）不会随之终止**（实测残留 PID 仍跑并占 8100，文档口径写的是"跟随主程序退出"）⇒ 打包/部署/冒烟前后先查 8100，**按 PID 精确清理**（勿 `taskkill /im python.exe` 误杀他处 python）。
- **Windows 不能把目录改名到一个**已存在**的目录（EPERM）——测试里的"探测名"会因此把门禁变成永久红（2026-09-26 实测）**：
  `gui/test/syncSidecar.test.ts` 靠"把 `dist_sidecar/python` 改名成 `python_guard_test`"制造"产物缺失"场景，
  但 `finally` 还原一旦失败/进程被杀，探测名就留在盘上 ⇒ 之后**每次运行必 EPERM 红**（实测残留目录 mtime 是**前一天 15:42**，跨会话一路红，
  表现成"vitest 1 failed"却与改动无关）。**修法**：进用例先 `rmSync(探测名)` 清残留 + `finally` 兜底还原且**不覆盖真实断言失败**；
  **通用纪律**：任何"改名/删除"式测试夹具都必须**幂等**（先清残留），否则一次意外会把门禁永久染红。
- **vite dev 在本机挂死（2026-08-15 实测）**：node 24.18 + vite 5.4.21 + @vitejs/plugin-react 4.7.0 组合下 vite dev 接收请求后零响应（最小空项目正常，加载项目配置即挂）→ 浏览器白屏/转圈。**启动 bat 已改为 vite build + python http.server 静态服务 dist**，不再依赖 vite dev。
- **5001 端口劫持（2026-08-15 实测；2026-08-24 阶段2 验收复现；2026-08-24 Wave 2a 再复现）**：Windows SO_REUSEADDR 允许多进程同绑 5001——打包版 sidecar 与 bat 起的 api_server 可同时"监听"，请求被劫持分流。bat 已加 netstat 占用检测（有后端就复用）；诊断用 `Get-NetTCPConnection -LocalPort 5001` 查 OwningProcess。**阶段2 复现实证（QA 独立验收）**：运行中的旧打包版 `D:\MCNP\MCNP输入卡生成器\python.exe -u backend/mcnp_bridge.py`（无新端点）劫持契约闸门 HTTP 用例 → 新端点 `test_http_validate_lattice_surfaces` 404；其余旧端点用例由劫持端也能通过，**只有新增端点才暴露劫持**。**Wave 2a 再复现**：残留旧 server（PID 4776，跑旧代码无 cycle 判环）劫持 5001 → cycle 端点 500 递归错误（新端点/新逻辑才暴露）；杀 PID 复绿。教训：验收新端点/新逻辑前先清 5001（杀旧 sidecar/旧 server/关主程序），或契约闸门 fixture 起子进程前检测端口占用并明确报错；**浏览器复验前必须确认 5001 跑的是新代码**。**Wave 2a 复发（2026-08-24）**：pytest 残留的旧 api_server 子进程（PID 4776，跑**旧代码**）劫持 5001 → 新 cycle 端点 500（maximum recursion depth exceeded，traceback 行号与当前文件不符=老代码跑 cycle 无判环）。杀 PID 后复绿。诊断要点：HTTP 500 且 traceback 行号对不上当前文件 → 先查 `netstat -ano | grep 5001` 占位进程，别先改代码。
- **P0 体积层渲染两弹（2026-08-15 实测，真实渲染复现）**：① three r160 WebGLProgram 对 RawShaderMaterial **前置 `#define SHADER_TYPE` 块** → shader 首行 `#version 300 es` 不再首位 → GLSL 编译失败 → **体积层自引入从未渲染**（静默，快照测试只锁字符串不编译一路绿灯）。修复：shader 去首行 `#version` + `glslVersion: THREE.GLSL3`。② 相机未 offset：物体按 offset 平移到原点但相机用未 offset 世界盒 → target 对空、画面错位。修复：`applyOffsetToBox` 纯函数。**教训：WebGL 类问题必须 headless 真渲染验证，不能只靠快照测试**。
- **3D 预览截面"部分实体切错"（2026-08-18 实测）**：① 切割平面恰与实体面重合（模型底面 z=0、相邻栅元共享面）时旧 `slice_stl_segments` 对 on-plane 顶点 continue → 0 环/错环；共面三角面须贡献出现 1 次的外轮廓边。② 预览归一化平移与后端原始 STL 系不一致 → 切位偏移；2026-08-18 起主预览**已去归一化**（显示系=原始系，modelCenter 恒 0，`planeOffset` 换算恒等但保留防回归）。③ 坐标轴单一事实来源 `axisConfig.ts`（X 红/Y 绿/Z 蓝），不要再内联写 dirs。
- **FreeCAD 对「旋转宏体半空间」补集布尔失效（2026-08-18 实测）**：`RPP ... *TRn` 正侧 = bound.cut(内盒) 再 apply_trn（带 Placement 复合体），对 `-曲面` 求补集返回垃圾体积（1.7e8 > 整盒 1.25e8）。斜向六面体一律改用 6 个局部 PX/PY/PZ + `*TRn`（普通平面布尔可靠）；轴对齐 RPP 宏体无 TR 正常。quickCell.ts 已按此实现。
- **大网格零通量背景涂蓝（2026-08-15 用户实测）**：色阶下限=0 时精确 0 值也被涂蓝遮模型。已修：色阶下限**自适应** = `minPositive×0.5`（曾用 sqrt 规则切太狠致"只显示一个面"，已按用户反馈改）；注意纹理是线性归一化 u8，微小值会被量化成 0（minPositive 从 u8 字节重建，勿用原始文件最小值）。
- **GQ/SQ 3D 预览 3 连坑（2026-08-22 实测，静态审查发现不了）**：① `app/mc.py` 邻接索引 `t_ids`/`slots` 的 repeat/tile 与「先全部 (0,1)、再 (1,2)、再 (2,0) 的块状边数组」错位 → 朝向传播全乱（signed volume≈0、假碎片/假冲突）；必须 `t_ids=tile`、`slots=repeat`。② BFS 波前同波重复三角形未去重 → 指数膨胀到 4 千万+（内存炸）；用一次性 bool 数组去重。③ 带 TR 小栅元在大 bound（B=500）下：TR 曲面 AABB 必须经 8 角点变换（`p_global=o+p_local@R`）求全局紧盒，保守全盒会让 32³ 粗扫漏检 → 空网格降级包围盒；margin 必须按**实际扫描盒**间距 `(scan_hi−scan_lo).max()/(coarse−1)×1.1`，用全局 `2B/(coarse-1)` 在 B=500 时达 35cm 把细化盒撑爆。水密断言必须用「每条无向边恰被 2 个三角形使用」的边计数法（**vtkFeatureEdges 对 marching cubes 网格误报边界边**）；`*TRn` 求值前必须 `p_local = rotate⁻¹·(p_global − o)`。
- **GQ/SQ 后续增强 3 连坑（2026-08-22 实测）**：① **凸裁剪盖面**：顶点恰落在裁剪面上（dist≈0）时跨边条件会漏掉该交点 → 盖面缺顶点被丢弃 → 三角形破洞（228 条开放边）；`cut()` 端点贴面返回 `keep()`、盖面收集贴面顶点本身。OWEN 的边链盖面法在细密切线平面下会退化丢面（162 面球只出 35 面），改用 Sutherland–Hodgman + 盖面绕质心极角排序。② **金螺旋方向分布不均**：外接多面体顶点半径到 1.08r+、体积误差 8%+，改二十面体细分（162/642 方向）；162 方向外接误差仍 ~2.1% → 无封口时绕中心体积校正 λ=(V_true/V_mesh)^(1/3)（体积精确）、有封口时用 642 方向（区域体积无法解析）。③ **解析切片 marching squares 16 格表 case 12（{2,3} 上边在内）应为 (1,3) 而非 (0,1)**；`_plane_halfspace` 的 pos/neg sgn 与 surface_fn 正侧约定相反（pos 侧要取 −法向）。
- **材料库深化 3 坑（2026-08-30 实测）**：① **嵌套浮窗被 `backdrop-filter` 裁剪**——`FloatingDialog` 用 `backdrop-filter: blur(16px)` 会创建 containing block，使嵌套其中 `position:fixed` 的子弹窗相对父定位、被父 `overflow:hidden` 裁剪。修法=子弹窗用 `createPortal` 渲染到 `document.body`（ExamplesDialog/GeometryTab 同法）。② **模块级缓存被 `useMemo` 冻结不刷新**——`useMaterialLibrary` 用 `useMemo(()=>entries,_cache…,[loaded])`，但 `entries` 依赖模块级 `_cache`（不在 deps），save/remove 后 `_cache` 更新 + notify 触发重渲染，`useMemo` 仍返回旧缓存 → 面板不刷新。修法=去掉 `useMemo` 每次读最新 `_cache`。③ **edit 改写 `.ps1` 丢 UTF-8 BOM**——Windows PowerShell 5.1 按 GBK 读无 BOM 的 UTF-8 中文就乱码解析崩溃；修法=用 `[System.Text.UTF8Encoding]::new($true)` 重存为带 BOM。

- **「一个语义、三种解释」+「写了函数没人调用」（2026-09-20 R1+O6 实测，两条通用教训）**：
  ① **审计"某字段怎么解释"时，不能只查自己以为的那一处，要 grep 语义载体本身**。R1 只 grep 了
  `rhp / p[6:9] / ±r±s±t` 就翻出 **6 个消费者、3 种互不相同的解释**（前端生成侧一直是对的，后端
  **解释侧全错**：转 30° 且小 13.4%）——其中 `freecad_preview._surface_extent_values` 连审计清单都没有，
  是 grep 出来的。**收敛动作**：先立**唯一实现**（`quadric.rhp_hex_vertices`）再逐处改调用，
  并给"改前/改后"各留一条**数值锚点**测试（手册例题的坐标），否则下次又会漂。
  ② **"写了函数没人调用" = 功能不存在**。`DistributionSampler.weight_factor()` 有实现、有 docstring、
  语义正确 —— 但全仓 **0 个调用者**（`grep -rn weight_factor` 只有定义那行），于是"SB 偏倚"在界面上
  **看起来生效、WGT 恒 1**。⇒ 纪律：**新增"补偿/换算"类函数时必须同时交出调用点**，
  否则它只是让人以为功能已实现的死代码。
  ③ 接缝设计推论：`sample()` 只返回**值** ⇒ 抽样的**副产品**（权重补偿）在接缝上必然被丢弃。
  改成 `sample_with_corrections() -> (值, 因子)` 后，"绕过接缝直连 sampler"变成**显式可见的坏味道**
  （本次即抓到 2 处：`_default_power_law`、`_sample_pos_dist`）。
- **❗`MEMORY_DIR` 是硬编码绝对路径 ⇒ preview_cache 跨树/跨版本共享（2026-09-20 R1 差分实测）**：
  `gui/backend/api_server.py` 里 `MEMORY_DIR = r"D:\MCNP\memory"`（**绝对路径**，不是相对仓库），
  所以源码树、`git worktree`、装机版**共用同一份 `preview_cache`**（LRU 上限 3）。
  后果 ①：**做"改前 vs 改后"几何差分时，第二个后端会命中第一个后端写的 STL** ——
  实测表现为"4 张卡里只有第 1 张看起来变了"（后 3 张被 LRU 里的旧条目命中），
  必须先清 `D:\MCNP\memory\preview_cache` 再换树，否则结论完全错。
  后果 ②：**凡改动几何生成算法，必须同时 `PreviewCache.GEOMETRY_CACHE_VERSION += 1`**
  （`app/preview_cache.py`，注释已写明这条纪律；R1 批从 2 → 3），
  否则用户装了新包仍看到旧网格，会以为"修复没生效"。
- **OUTP 解析误用 pymcnp 构造函数（2026-08-19 实测）**：`pymcnp.Outp(text)` 是构造函数非解析入口，恒报 TypeError；正确入口 `Outp.from_mcnp(text).to_dataframe()`。且内置 pymcnp 0.9.1 Tally_4 只认 MCNP6.2 布局，MCNP6.1 紧凑两列解析为空 → 需 `app/outp_parser.py` 兜底。
- **测试笔误陷阱（fixtures 实测）**：① valid_39.meshtal 的 tally number 是 **4 不是 1**（须取自 parse 响应 `tallies[].number`）；② preview-3d 单栅元 material="0" 是 void → `include_void=False` 跳过 → 空 stl_files（冒烟 deck 须用非 0 material）。
- **❗❗ 编译级缺陷只有"真的跑一次"才能发现（2026-09-10 实证，本项为最高优先级教训）**：一个"97% 修复完成、静态自检全过"的批次里，实测藏着 2 个**编译级**缺陷 ——
  - `app/meshtal/meshtal_cache.py` 的 `IndentationError`（加锁改动丢了 `while` 循环体缩进）⇒ **全量 pytest 在收集阶段就中断，一条测试都没跑**（`1 error during collection`）。若不真跑，会以为"门禁全绿"。
  - `gui/src/components/CellEditDialog.tsx` 多余的三元分支 `: null,`（TS1135）⇒ **该文件根本无法编译**，只有启用 `tsc -p tsconfig.test.json` 才暴露。
  **推论（本项目纪律）**：① **"没有 shell 的修复批次"其交付状态必须标注为「未验证」，不得计入完成**；② 任何"改了很多文件"的批次，第一件事是**全量跑一次**（含 `python -m compileall -q app gui tests` 扫语法 + `tsc` 两档），再谈别的；③ 静态审计（哪怕再仔细）**发现不了"文件根本跑不起来/编不过"**。
- **`/api/diff-inp` 在部署版 1.7.5 是坏的（2026-09-10 实机实证）**：`_import_app("diff_inp")` 走**顶层名** `__import__("diff_inp")`，而 spec `_keep_py` 没登记该文件 ⇒ 冻结包 `ModuleNotFoundError` ⇒ 端点 **HTTP 500**（traceback 落到 `api_server.py` 的 `_import_app`）。**同类模块（`material_library.py`/`gpu_pref.py`）都在 `_keep_py` 里，唯独漏了 `diff_inp.py`**。修法：加进 `_keep_py` 并重打包。**注意**：`lattice` 也走 `_import_app`，但实测**可导入**（未 500）—— 故"有动态导入就必须登记"是**保守且正确**的经验，但"它一定 500"要实机验证；`gui/mcnp_sidecar.spec` 的 `_keep_py` 与 `api_server._import_app` 的**双向一致性**已由 `tests/unit/test_sidecar_spec_keep.py` 自动闸门守住（该闸门此前**从未执行过**，2026-09-10 首次跑通）。
- **"无 shell"会连带污染测试本身的可靠性（2026-09-10 实证）**：`tests/unit/test_sidecar_spec_keep.py` 的 `_parse_hidden` 用 `re.findall(r'"([^"]+)"', spec_text)` 取"全 spec 字符串字面量"，实测**静默丢内容**（同一份文本上返回 74 项且**丢** `models.py`/`meshtal`/`generator`/`docs`；改用**逐引号配对扫描**返回 76 对且四者俱全；`[^"]+` 与 `\x22([^\x22]+)\x22` 两种写法**均复现**）。⇒ 教训：**闸门自身的解析逻辑也要有"内容非空/数量合理"的自检**，否则闸门会假红或假绿。该函数已改为显式配对扫描。
- **打包链路「6.2 时效坑」每次必中（2026-09-10 再次命中，第 4 次以上）**：`tauri build` 是增量编译，**不会刷新** `target\release\` 里的 sidecar（`python.exe` + `_internal\`）——本次实测 `target\release\python.exe` 仍是**上一次**的（mtime 10/9、28561279 B），而新 sidecar 是 11/9、28614639 B，且 `target\release\_internal\app\` **没有**本次新增的 `lattice.py`/`diff_inp.py`。**不校验就会"版本号新、后端旧"**（用户装了新版但仍缺修复）。→ 部署前**必须**按 `docs/手动打包方法.md` §6.2 比对 mtime/大小，不匹配就手动覆盖 `python.exe` + `_internal`。
- **本机命令环境三坑（2026-09-10 实测）**：① **PowerShell 下 `npm`/`npx` 被执行策略拦截**（`npm.ps1 cannot be loaded because running scripts is disabled`）→ 改用 **`npm.cmd` / `npx.cmd`**，或直接 `node .\node_modules\vite\bin\vite.js build`（手册正文即用后者，天然规避）；② **`pytest --timeout` 需要 `pytest-timeout`**，未安装时 pytest 会以 `unknown option` **直接退出**——看起来像"全红"，其实是**没跑**（先 `python -c "import pytest_timeout"` 确认）；③ **Windows 终端默认 GBK**，直接 `print()` 中文可能 `UnicodeEncodeError` 或乱码（PowerShell `Get-Content` 读含 CJK 的 UTF-8 也会乱码）→ 让脚本 `PYTHONIOENCODING=utf-8`，或**把结果写文件再用读文件工具看**（比在终端里读可靠）。
- **meshtal-parse 元数据缓存**：已闭环（`_mode_parse` 先 `get_manifest` 命中即返回，实测二次 0.23s）；`meshtal_cache._MANIFEST_VERSION=2` 使旧磁盘缓存失效。
- **P0/P1 技术债全清偿（2026-08-12）**：引擎缺陷 F-A~F-H + F#1~F#7 全修，R1-R4 不动点成立；`inp_generator.py` 仍为**技术债集中地**（见 docs/backend-changes.md + UI_ARCHITECTURE.md 技术债地图）。
- **FreeCAD 对「圆柱 ∩ 平行于轴平面」布尔恒空（2026-08-24 三阶段验收实测，QA 独立复现）**：`_build_one_universe` 把格元盒裁剪平面追加进 universe cell 表达式做 CSG 交集（`-1 -61 +62 ...`），圆柱（C/CZ 半空间）∩ 任一 PX/PY（平行轴平面）→ **空 STL（84B/0 三角形）**；圆柱 ∩ PZ（垂直轴）正常（4884B/96 三角）、纯 box ∩ 盒正常。现有 preview-3d 走 worker post-hoc bound 盒裁剪（solid-solid boolean）对同 deck 全部非空——**裁剪必须走 solid-solid，不得把平面塞进 cell 表达式**。影响：格阵 universe 实例化详细模式对燃料棒等圆柱格元不渲染。
- **QA API 直验两个易错点（2026-08-24 最终复验实测）**：① `/api/generate` 期望 **deck 字段在 body 顶层**（`deck_from_json(data)` 直接吃 body），不是 `{"deck": deck}` 包裹——包错层会静默生成空 INP（实测 67B）；`/api/section-to-text` 才是 `data.get("deck")`。② 生成器把关键字**大写**输出（`LAT=1`/`U=10`/`FILL=`/`IMP:N`），断言匹配须大小写不敏感（`inp.upper().replace(" ","")`）。
- **FreeCAD 圆柱∩盒平面恒空已闭环修复**：`_build_one_universe` 不再把 6 平面塞进 cell 表达式，改合成单 RPP 宏体 `-<num>` 做 cell solid ∩ RPP 盒实体 solid-solid common（与 preview-3d bound 同机制）；0 三角 STL 显式丢弃（前端回退占位盒）。复验 17×17 全部 12 个 universe cell STL 非空、cell1=96 三角与 preview-3d 基线一致。
- **契约文档**：docs/contracts/api.yaml 覆盖全部端点；漂移闸门 `tests/integration/test_api_contract.py` AST 断言 handlers ↔ api.yaml 双向一致（含真实 HTTP）。
- **Cargo.toml 版本隐患**：v1.6.4 曾漏改（停在 1.6.3）；Tauri 以 tauri.conf.json 为权威不影响出包，但**版本四处+锁文件**必须一致。
- **打包注意（详见 §9）**：Tauri build 需要 `RUSTUP_HOME/CARGO_HOME` 指向 D:\rust；sidecar 用 PyInstaller（spec：`gui/mcnp_sidecar.spec`，产物名 "python"）；**6.2 时效校验**（tauri 增量编译不刷新 target/release 的 sidecar，必须手动核对 mtime/覆盖）；后端窗口关闭时经 Rust `close_window` 命令一起退出。
- **❗「后端返回对」≠「前端拿到对」——跨层缝上的字段丢失（2026-09-11 实证，源演示"看不见栅元"根因）**：后端 `parse-inp` 的 `material` 完全正确（`"1"/"2"/"3"`），但前端经 `SourceTab.demoCellsForBackend()` → `localToDeckCells` 后 `material` 恒为 `""`。**两个成因叠加**：① `api_server.py:1439-1443` 给 cell 补 camelCase 前端别名（`num`/`surfaces`/`impN`/`impP`/`impE`）时**漏了 `mat`**；② `SourceTab` 把 **snake_case** 的 `deck.cells` **强断言**成 camelCase 的 `LocalCellRow`（`as` 类型谎言）—— 而它"看起来能用"恰恰是因为后端补了 `num`/`surfaces` 同名别名，**别名补得越全，类型谎言藏得越深**。⇒ **纪律：跨 snake_case/camelCase 边界禁止 `as` 断言**，要么显式走 `deckToLocalCells`、要么直读本侧字段名。**pytest（后端对）+ vitest（渲染器对）都覆盖不到这条缝**，只有端到端实跑能暴露。
- **❗`!n` 这类"值域重载"会把「缺失」与「特定值」混为一谈（2026-09-11 实证）**：`getMatColor` 原实现 `const n = parseInt(mat); if (!n) return "transparent";` 本意是"M0 = 真空"，但 `parseInt("")` 是 NaN、`!NaN` 为真 ⇒ **空材料号也被当成真空**，下游 `buildCellMaterial` 直接给 `opacity: 0` ⇒ 整个几何不可见。⇒ **纪律：判"特定值"用 `n === 0`，"缺失/非法"单独一条分支**（本次改为返回中性灰 `#888888`）。凡"0 是合法值"的场合，`!x` / `x || 默认` 都要警惕。
- **❗跨模块复用"为别的场景调过的取景/布局启发式"会静默失效（2026-09-11 实证）**：`computeFramingBox` 的 `VOLUME_FRAMING_RATIO=0.25` 是**为体积窗口**设计的（网格层 ≪ 模型时聚焦网格层），被 `SourceDemoRenderer`/`PtracRenderer` 复用后，遇到"源/径迹在屏蔽体内部"（**演示源与径迹窗口的常态**，实测 ratio≈0.057）就把几何外壳挤出视野，且**不报任何错**。⇒ **纪律：复用带阈值/启发式的几何工具前，先问"这条启发式对**本**场景语义是否成立"**；本次两处调用点改为 `unionBoxes`（外壳优先），**共用函数本身与其 3 个测试文件保持不动**。
- **headless Edge + CDP 端到端取证三坑（2026-09-11 实测，本项目首次具备"看图判读"能力）**：① **`alert()` 在 headless 里永久冻结渲染进程**（本程序"导入成功"必弹 `alert`）⇒ CDP `Runtime.evaluate` 永不返回、看起来像"页面卡死"；必须在**同一 CDP 会话内**监听 `Page.javascriptDialogOpening` 并 `Page.handleJavaScriptDialog({accept:true})`。② **导航到"含相同 hash 的同一 URL"不会重新加载文档** ⇒ 是假"重载"（两次截图 sha256 完全相同，一度被误判为"渲染确定性"）⇒ 真重载须用 `Page.reload`；要在加载**前**注入钩子须用 `Page.addScriptToEvaluateOnNewDocument`。③ **PowerShell 调原生程序时空字符串参数会被丢弃** ⇒ 位置参数错位（`run ... "" 8000` 把等待时长当成输出文件名，**在仓库根生成了垃圾截图 `3000`/`8000`**，已删）⇒ 占位参数用 `-` 而非 `""`。**另**：headless SwiftShader 下主界面 `Page.captureScreenshot` 会超时、子窗口正常 ⇒ 只在子窗口截图。
- **MCNP 多核（`tasks N`）知识（2026-09-11 实测 + C810 页 875 定案）**：① 语法 = 命令行**末尾** `tasks N`（**无等号**）；② **只在 OpenMP 构建上生效**（判据：输出出现 `comment.  threading will be used …`；非线程版**静默忽略** —— 不报错、也不加速）；③ **`tasks` 取物理核数**，不是逻辑核数 —— 本机 8 物理核/16 逻辑核：`tasks 8` 8.36s 最优，`tasks 16` 反而 **15.06s**（烧 205s CPU，大半自旋）；④ **`DBCN(2,3,4)` / `SSW` / `SSR` / `PTRAC` 与 `tasks > 1` 不兼容（FATAL error）** ⇒ 程序必须扫卡拦截（见 S1.0e，`app/mcnp_tasks.py`）；⑤ 判据：**`CPU时间 / 墙钟 ≈ N`** 即 N 个核在跑。**本机 MCNP 路径 = `D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe`**（下划线、少一层），与用户 bat 里写的 `D:\MCNP6\MCNP6\MCNP CODE\…`（带空格）**不是同一路径**。
- **❗deck.cells 是「改过型的判别联合」，任何手写字段映射都会静默过期（2026-09-12 实证，用户报"导入 STEP 炸了"）**：`/api/import-step` 里手写 `c.number/c.material/c.surface_expr`，而 `deck.cells` 自 `f8f7fe6` 起是 `CellRow`（`kind` + 嵌套 `cell`）⇒ 每次导入必 `AttributeError` → HTTP 500。**该端点当时零测试覆盖**，且 2026-08 删掉 McCAD 兜底分支后 100% 暴露却一直没人踩到（全量 pytest 908 passed 也照样漏）。修法＝把序列化收敛到 `app/step_importer.flat_cell_json` 一处（handler 只传 `deck.cells`）+ `tests/unit/test_step_import_deck_response.py`（先证红后转绿）。⇒ **纪律：类型改造（dataclass → 判别联合 / 改名）后必须 grep 该字段的全部字面读取点**，跨模块手写映射一律改走单一序列化函数。
- **geouned 的安装位置只能在 FreeCAD 的 Python 里问（2026-09-12 实证）**：`_resolve_geouned_path()` 原来在**后端解释器**里 `find_spec("geouned")` ⇒ 开发机恒报「缺少 geouned 包: 」（路径为空，用户看不出该做什么）。现为候选链（`GEOUNED_PATH` → 冻结 `_MEIPASS/vendor` → 后端解释器 → **FreeCAD 解释器子进程探测**）+ **`_is_geouned_dir()` 验证**（须有 `geouned/__init__.py` + `geouned/GEOUNED/__init__.py`）。**本机 FreeCAD site-packages 里那个只含空 `GEOReverse`、没有 `__init__.py` 的残缺 namespace 包证明：光判 `isdir` 会把残缺安装当可用**，worker 起来才炸 `ImportError: cannot import name 'CadToCsg'`。开发环境跑 STEP 导入须 `set GEOUNED_PATH=D:\MCNP\GEOUNED`。
- **❗发布链路的三个"必中坑"（2026-09-12 两轮热修实证）**：① **改了 TSX 就必须重出 Tauri exe** —— 前端 bundle 内嵌在 `MCNP 输入卡生成器.exe` 里，只重打 sidecar 用户**看不到前端修复**（本轮「导入即关窗」只有重跑 `vite build` + `tauri build` 才生效）；只改 Python 才可以 sidecar-only。② **6.2 时效校验升级为逐文件哈希比对**：`target\release\python.exe` 可能已是新版而 `_internal` 仍是旧的（Tauri 只拷 `externalBin` 的 exe，**不拷 `_internal`**）—— 本批用 `Get-FileHash` + `Compare-Object` 比出 **10 项差异**（`app\voxel_csg.py`/`step_importer*.py`/`preview_cache.py`/`base_library.zip`…）；"查有没有本批新增模块"的旧判据在**全是改文件**时查不出来。③ **部署前必须停掉 `MCNP 输入卡生成器.exe` 与其 sidecar**：否则文件被占用，且残留旧 sidecar 会与新起的 dev 后端**互相劫持 5001**（本轮实测：预览请求落到旧代码，数字看起来像"没修好"，白排查一轮）。
- **`C810.pdf` 已可直读（2026-09-11 打通，重要能力）**：本机 **PyMuPDF（`fitz`）已安装** ⇒ **零新依赖**即可提取这份 1001 页权威手册的文本，卡格式语义不必再靠 `app/docs/` 派生 md 猜（§4 待办 5 的 `DSn` 语义亦可照此核对）。范例脚本在仓库外：`D:\MCNP\_agent_probe\{pdf_index.py,pdf_extract.py,pdf_tasks.py}`。**已提取定案**：SI/SP（页 746-747）、tasks（页 520/875）。
- **❗"改尺寸保留原内容"必须按绝对坐标搬，不能按扁平下标（2026-09-15 实证，用户报"fill 改成 -9:9 就乱顺序"）**：`resizeLatticeCells` 旧实现 `fresh.map((c,i) => prev[i] ?? c)` —— 范围 -L:M 一变，**每格的绝对格位号整体平移**，扁平下标不再指同一格位 ⇒ 17×17 居中同心环改 19×17 时整张图沿对角线拖走（图面"左上角一整块同色 + 旧行残影"就是这种错位的指纹）。**规律：凡是"编号区间可平移"的序列（格阵 FILL / 网格 / 分箱），索引空间与格位空间不是一回事**；搬运/合并/删除都要先换算成绝对格位号（`start` 本轴 -L、`idx=(i-start0)+nx·((j-start1)+ny·(k-start2))`），越界即丢弃。⇒ 同时提防**"用户说乱序，就以为卡写错了"**：先分清是「生成/解析的条目序」还是「编辑器状态搬运」——本次 **FILL 条目序、3D 展开全对**，实测 MCNP 往返逐项相等，错的只有编辑器那段。
- **❗透明底 3D 出图有三道独立关卡，缺一道就"看起来像坏了"（2026-09-19 实证）**：
  1. **`scene.background` 置空**（不画背景色）—— 只做这一步，深蓝场景色仍会被取进图；
  2. **`setClearColor(_, 0)` 显式清屏** —— `preserveDrawingBuffer:false` 的 WebGL 画布**未清屏的像素是未定义值**；
  3. **`new THREE.WebGLRenderer({ alpha: true })`** —— drawing buffer 没有 alpha 通道时，第 2 步只会得到**黑底 PNG**（不是透明）。
  **判据**：出图后看 PNG 的 corners alpha；`colorType 6`（RGBA）只是"能带 alpha"，不代表像素真透明。
  修法收在 `export/captureFrame.captureTransparent3D()`（一次同步 render 窗口内切/还原，`finally` 保证还原），
  五个渲染器（`useThreeCanvas`/`Preview3D`/`VolumeRenderer`/`PtracRenderer`/`SourceDemoRenderer`）都补了 `alpha:true`。
- **❗"烧进纹理的颜色"改不动，只能出两份（2026-09-19 实证）**：3D 的刻度标签/轴字母是 `THREE.CanvasTexture`
  （底色与字色一起烧进画布），想换印刷色就得重建纹理 ⇒ **屏幕上会闪一下**。做法：**预先建两份 sprite，出图时只切 `visible`**（零纹理 churn、零闪烁、可逆）。凡"纹理即状态"的显示件（刻度/标签/图标）都适用这一条。
- **排版类缺陷的判据是"量出来的数"，不是"看着别扭"（2026-09-19 排版审计方法）**：六类缺陷全部靠 DOM 量尺寸定位
  （`form.clientWidth/scrollWidth`、`getBoundingClientRect().y` 同行对比、`page.evaluate` 量图例面板宽），
  而不是靠截图审美。**可复用的三条量法**：① `scrollWidth > clientWidth` ⇒ 内容被裁（且要再确认父级是不是 `overflow:hidden`，
  那样就**无法滚到**）；② 同一行内各元素的 `rect.y` 是否相等（对不齐就会被量出来）；③ 出图版面用**离屏 canvas 单测**
  量"面板宽/总宽/占比"（jsdom 里 `getContext` 返回 null，要么补最小 2D 桩、要么用 `drawImage` 参数记账，见 `test/exportFoundation.test.ts`）。
- **jsdom 里量 canvas 版面要自己搭桩（2026-09-19 实测）**：项目**没有装 `canvas` npm 包** ⇒ `getContext("2d")` 返回 null，
  直接 `toDataURL`/`getImageData` 全废；而 `captureCanvas` 拿不到 ctx 会**提前 return null**（`renderNow` 回调根本不执行，
  测"取帧窗口内改了什么"会变成测一个永不运行的函数）。**做法**：在用例里替换 `HTMLCanvasElement.prototype.getContext`
  返回最小桩（`fillRect`/`fillText`/`drawImage` 记账即可），用完 `finally` 还原。

- **❗同一件事有两个实现时，改一个必漏另一个——"两个渲染器"就是活样本（2026-09-19 实证）**：
  出图有**两条出口**（栅格 `figureCanvas` / 矢量 `vectorFigure`），版面规则各写一份。
  我把栅格版改成"图题在图下"之后，**矢量版没同步** ⇒ 二维矢量图（截面/tally/切面/keff）**全部还是标题在上**，
  用户导出截面图一眼就看到了（标题压在图上）。**用户的话是**："图标题在下，你几乎都没修"。
  ⇒ **纪律**：① 凡"同一规则要在 N 处生效"的逻辑，**先抽成一个模块再改**（本次抽出 `export/figureLayout.ts`，
  两个渲染器只负责画字）；② 改完要**用一条能覆盖全部出口的断言**（本次：`figureLayout.test.ts` 的
  "两渲染器同版式对拍" —— 断言矢量 SVG 的文档顺序是 内容 → 图题 → 图注）。改一处、验一处，剩下的必漏。
- **❗共享控件挪进更窄的容器必须实测宽度（2026-09-19 实证）**：`PlaneControls` 在 3D 预览侧栏（300px）放得下，
  但塞进截面右栏（原 220px）时，`showStepButtons` 打开后步长行需要**实测 274px**，可用只有 ~190px
  ⇒ **横向溢出 + 面板底部横向滚动条 + 控件被切**，而且**它不报错、不崩**（只是"排版有问题"）。
  **判据**：`el.scrollWidth > el.clientWidth` 一量就出（注意还要看父级的 `overflow-x`：若为 `hidden`，
  用户**滚也滚不到**，只能看到被切）。**修法两条一起**：容器加宽 + 控件加"堆叠模式"（拆行）。
- **❗描边宽度的"屏幕像素 vs 用户坐标"是两个坐标系（2026-09-19 实证，用户两次报同一处）**：
  `strokeWidth: 1.5 / zoom` 把线宽写在**用户坐标**里 ⇒ 缩放时线宽自己变（zoom 0.2 时粗到 7.5）、
  且**导出再缩放一次更粗**。正解：屏幕用 `vector-effect="non-scaling-stroke"` 锚在屏幕像素（缩放不漂移），
  **导出时摘掉该属性并把线宽换算成用户坐标**（`1.2 / strokeScale`）—— 因为该属性出了文档
  在光栅化路径里**不保证生效**。凡"线宽/点大小/文字大小"这类显示量，都要先问一句：
  **它写在哪个坐标系里，导出时还会被缩放几次**。
- **❗解析器只对着"自家合成夹具"写正则 ⇒ 对真实文件必然失效（2026-09-20 实证，用户"程序解析不到 keff 序列"）**：
  `app/mctal_parser.py` 的 keff 路径只认 `k eff (c) <mean> <std>` 行与 `combined keff = ...` —— 那是
  **OWEN 简化夹具**（`tests/fixtures/kcode_realistic.mctal`）的形态。真实 MCNP6 mctal 里 **这些字段名一个都没有**：
  KCODE 结果在文末 `kcode <总周期> <跳过> <每周期值数>` 之后是 **600×19 个裸数值**（每行 5 个、4 行一周期）。
  **教训**：① 夹具是"我造的"，不能当接口规范 —— 每类解析器都要有**至少一份真实产物**做回归（本批补
  `tests/fixtures/real_kcode_zeus1.{mctal,o}` 并做 `.o`↔mctal 600 周期逐值对拍，最大差 5e-6）；
  ② 位置型（无字段名）记录必须**与另一条独立来源交叉核验**后才能下结论（本次列语义逐列对 `.o` 的 print table 175 核出）；
  ③ **MCNP 的 mctal/outp 都不逐周期写 σ**（只写累计平均的 σ）⇒ 逐周期序列的 `std` 只能为空，"最终值 ± σ"取 `combined`。
- **❗MCNP 的 keff 只在结果文件里，stdout 只有少量提示行（2026-09-20 实证，同一族真 bug）**：
  `sweep-run` 原实现 `parse_keff(proc.stdout + stderr)` ⇒ 参数扫描汇总 TSV 的 keff **恒 `n/a`**（不报错、不崩，
  只是"永远没有数"）。凡"从子进程抓 MCNP 结果"的代码，一律**读运行目录的 `mctal` / outp(`name=` 前缀下的 `*.o`)**
  （本批收敛到 `app/sweep.py:scan_run_dir`），stdout 只能当兜底。
- **❗打包版"热修"的边界：`_keep_py` 松散 `.py` 能换，冻结在 exe 里的 handler 不能换（2026-09-20 实测）**：
  安装版 `_internal\app\*.py` 是 spec `_keep_py` 投放的**数据文件**，但 `api_server.py` / `mcnp_bridge.py` 与
  被静态分析的模块（如 `outp_parser.py`、`app.models`、`app.meshtal.*`）**编译进 exe 的 PYZ**。
  **判据（可复跑）**：把 exe 当 Latin1 文本搜模块名 —— PYZ 的名字表是**明文**（形如 `...app.freecad_locator).r...`）；
  本批实测 `mctal_parser` / `sweep` / `diff_inp` / `material_library` **不在表里**（= 走松散文件，可热替换），
  而 `api_server` / `outp_parser` / `app.models` / `meshtal` / `ptrac` **在表里**（= 冻结，改不了）。
  ⇒ 只改 `app/` 松散模块的修复可以"换文件 + 重启"应急（**进程内 `sys.modules` 已缓存旧模块 ⇒ 必须重启**），
  改到 handler 或前端的修复**必须重新打包**。
- **❗契约闸门固定用 5001 端口 ⇒ 装机版常驻时会静默测到"已部署的旧后端"（2026-09-20 发现，**未修，待办**）**：
  `tests/integration/test_api_contract.py::backend_base_url` 起源码 `api_server.py` 子进程并固定连
  `http://127.0.0.1:5001`。若用户机器上打包版正占着 5001（常态），源码子进程 bind 失败即死，而探活那一步
  `socket.create_connection(("127.0.0.1", 5001))` 会**连上已部署的旧后端**并 `break`（此时 `proc.poll()` 还可能
  仍是 `None`）⇒ 那批"真实 HTTP 往返"用例**测的是安装版旧代码**，还报绿。§6 的"5001 端口劫持"条目早有记载，
  本条把它推进到**测试闸门自身的假绿**。修法（待做）：fixture 用**空闲随机端口**（或先检测占用即 skip/fail），
  并在探活成功后**断言监听者就是刚起的子进程**。
  **❗2026-09-23 再次命中（且证明"占位者不一定是装机版"）**：GEOUNED 参数 UI 批全量 pytest
  = 1298/1/11，唯一失败恒定是 `test_http_mcnp_detect_lists_all_candidates`（socket 读超时）。
  首次跑时占位者是**用户运行中的部署版**（`D:\MCNP\MCNP输入卡生成器\python.exe -u
  backend/mcnp_bridge.py`）；用户关闭后复跑，占位者换成**另一会话的临时脚本**
  （`D:\AItool\.tmp\__geo2.py`，用部署版 python.exe 起）⇒ 同一用例**照样**超时，同文件其余 29 例全过。
  **判据（可复跑）**：`Get-NetTCPConnection -LocalPort 5001 -State Listen` 查 OwningProcess →
  `Get-CimInstance Win32_Process -Filter "ProcessId = <pid>"` 看 CmdLine 判断是谁；
  **排除 `test_api_contract.py` 后全量 1269/0/11** ⇒ 与业务代码无关。
  **纪律**：占位者若是**用户程序或他人会话的进程**，不得直接杀 —— 只能如实在结论里标注"环境所致"，
  并推动 fixture 改随机端口（本批即如此处理）。
- **❗跑在"非冻结子进程"里的代码看不到随包目录 —— 路径发现必须在知道环境的那一侧做（2026-09-23 端到端实测踩到）**：
  MCCAD 实体切割上线后用户实测「还是几百个面」。**端到端复现**（POST `/api/import-step`，
  `mccadCut=true`）拿到真因：`warnings` 里明写 `MCCAD 切割已跳过：未找到 McCAD.exe…`，
  而曲面卡与开关关闭时**完全一样**（171 张、栅元 3 仍 146 面）。
  **根因**：worker 跑在 **FreeCAD 的 python.exe** 里 —— 它**不是** PyInstaller 冻结进程 ⇒
  `sys.frozen`/`sys._MEIPASS` 都不存在 ⇒ `find_mccad()` 里"随包 `_MEIPASS/mccad/McCAD.exe`"
  那条候选**永远命不中**，只能回落 PATH ⇒ 打包版**静默跳过**。
  **我的局部探针为什么没抓到**：探针里我手动设了 `MCCAD_PATH` 环境变量，**正好绕过了这个洞** ——
  局部测试把环境依赖偷偷满足了，等于没测。
  **修法（可复用原则）**：**谁的进程知道环境，谁负责解析路径** —— 冻结的转换器
  （`GeoUnedConverter._resolve_mccad_exe()`：`_MEIPASS` → `MCCAD_PATH` → 仓库 `vendor/mccad/`）
  解析出**绝对路径**，经 payload 的 `mccad.exe` 传给 worker；`find_mccad(mccad_exe="")` 把
  "显式路径"放第一优先级，env/随包/PATH 只作回落。
  **修复后同一端到端实测**：`off` = 171 曲面卡 / 30 栅元 / 最大 146 面 / 平均 43.2；
  `on` = 167 曲面卡 / **205 栅元** / 最大 53 面 / **平均 9.1**，并给出"切割已生效"提示。
  **连带纪律**：① 涉及"随包资源 + 子进程"的功能，**验收必须走真实入口端到端**（局部探针不算），
  且**不许在探针里预置本该由程序自己解析的环境变量**；② **静默降级必须回传到用户可见处** ——
  本次正是靠 `warnings` 一路回传到 API 响应，才一眼分清"跳过"与"没生效"。
- **GEOUNED 的"切"只有一个方向：真空可调、实体不可调（2026-09-23 源码级普查）**：
  `maxSurf`/`maxBracket`/`minVoidSize` 全仓**只在 `void/void.py:108-110`** 被读 ⇒ **只对真空栅元生效**；
  实体侧 `_decompose_solids`（`core.py:614`）是**必经步骤**，用户只能影响"怎么切"
  （`nPlaneReverse`/`splitTolerance`/`scaleUp`/`enlargeBox`/`forceCylinder`），**不能影响"切多少"**；
  且 `decom_one.SplitSolid` 末尾 `return Part.makeCompound(...)` ⇒ 切出来的块**合并回同一个
  `GeounedSolid`**，只是**同一个栅元**表达式里的辅助面，**不会各自成栅元**。
  **三个可复用的判据**：① 实体 → 栅元的映射是 **1:1**（`core.py:441` 每实体建一个栅元）；
  ② 想"一变多"只有一条路 —— CAD 侧切分（`compSolids=False` 时每个 sub-solid 各成一个栅元，
  见 `load_step.py:149-162`；`compSolids=True` 走 `LF.fuse_meta_obj` 合成一个）；③ `enclosure`/
  `envelope` 节点**永远**融合，不受 `compSolids` 影响。
  ⚠️ **纪律**：参数"有没有文档"**不能**当作"要不要暴露"的依据（`maxSurf` 官方只写 `#TODO` 但在用；
  `newSplitPlane` 有 changelog 描述却**零消费者**= 死参数）。**暴露任何第三方参数前必须 grep 消费者。**
- **PyInstaller：`datas` 里的 `.exe` 会被"二进制重分类"，顺着导入表收进一大堆 DLL（2026-09-23 实测）**：
  把 `McCAD.exe` 放进 `Analysis(datas=…)` 后，run 日志出现 `binary vs. data reclassification`，
  它顺着 McCAD.exe 的导入表把 **FreeCAD 的 49 个 OCC/MSVC DLL**（`TK*.dll`/`MSVCP140`/`FreeImage`/
  `freetype`/`OpenEXR*` …共约 **46 MB**）收进 `_internal\` **根**目录 —— 而 McCad.exe 在
  `_internal\mccad\`，**Windows 的 DLL 搜索顺序不含上级目录**，它**照样找不到**这些 DLL
  （运行时真正管用的是把 FreeCAD 的 `bin` 前置进子进程 PATH）⇒ 纯涨体积（251.1 → 205.4 MB）。
  **修法**：**Analysis 之后晚注入** `a.datas += [...]`（按普通数据文件拷贝，不做依赖扫描）。
  ⚠️ 两个易错点：① 规范化 TOC 是 **3 元组且顺序为 `(目标名, 源路径, "DATA")`**，与
  `Analysis(datas=)` 的 2 元组 `(源, 目标)` **相反** —— 写错会
  `ValueError: not enough values to unpack (expected 3, got 2)`；② 判断"有没有被误收"时别用
  `^TK`/`^zlib` 这种粗正则 —— `tk86t.dll`（Tcl/Tk，原生文件对话框用）与 `zlib1.dll`（Python 自带）
  **本来就在包里**，是长期存在的正常成员。
- **同一个事实写两处，搬家时必漏一处（2026-09-23 实测）**：`StepImportDialog` 原先在**参数元数据**
  里写 `page: "basic"`、又在 `PAGE_LAYOUT` 的 row 里列一遍归属。把真空三件套从「基本」搬到
  「常用调节」时只改了 `PAGE_LAYOUT` ⇒ 症状是"**校验报错跳到错的页**、**改动计数记到错的页签**"，
  且因为元数据骗人，测试里"在常用调节页找该字段"直接找不到。**修法**：页归属**只由 `PAGE_LAYOUT`
  派生**（启动时建一张 `PAGE_OF_KEY` 索引，元数据不再有 `page` 字段）。
  ⇒ 纪律：**同一事实（键属于哪一页/哪一层）只能有一个来源，另一个方向一律派生。**
- **❗打包：PyInstaller 必须带 `--distpath dist_sidecar`；手册与 spec 互相矛盾（2026-09-23 踩到）**：
  `mcnp_sidecar.spec:130-139` 明令"**必须**用命令行 `--distpath dist_sidecar` 指定独立目录，
  不要手敲裸 PyInstaller"，理由是 **`vite build` 会清空 `gui\dist\`**：若 sidecar 落在
  `dist\python\`，则"先 PyInstaller → 再 `npm run build:app`"会把刚打好的 sidecar **删掉**，
  同步脚本随后把 `binaries\` 里**上一次的旧 python.exe** 铺进 `target\release` 并报"✅ 已是最新"
  ⇒ **"版本号新、后端旧"的包**（spec 点名 = 坑 6.7）。**但**：① `docs/手动打包方法.md` 第 4/5 步
  写的恰是"裸 `python -m PyInstaller mcnp_sidecar.spec`" + `gui\dist\python\`（**错的**）；
  ② spec 注释让走的 `npm run build:sidecar` **在 `package.json` 里不存在**（scripts 只有
  `sync-sidecar`/`check-sidecar`/`verify-sidecar`/`build:app`）；③ `coll.distpath = ...` 也不行
  —— COLLECT 对象没有该属性，赋值被静默忽略。**正确命令**：
  `python -m PyInstaller mcnp_sidecar.spec --noconfirm --distpath dist_sidecar --workpath build_sidecar`
  （**手册已按此修正**）。**教训**：规格说明与操作手册不一致时，**以能解释"为什么"的那份为准**
  （spec 写清了失败模式，手册只是漏了参数），并把两边都改齐。
- **子弹框的"触发器绑在哪儿 + 文案跟谁走"是产品决策，不是实现细节（2026-09-23 用户两轮反馈）**：
  第 1 版把 `onMouseEnter/Leave` 绑在**整行**（label+控件+`?`），用户真机反馈两条：
  ①「鼠标移开时就立即消失」⇒ 删掉 140ms 缓冲（原意是"指针能移进子弹框继续读"，用户不需要，
  连 `TipBubble` 的 mouse 处理一起删，否则是死代码）；②「我看你留了很多问号，把程序改为，
  鼠标停在问号上的时候再出弹窗」⇒ 触发器**收到 `?` 图标上**，划过输入框/下拉/按钮**都不弹窗**。
  **连带纪律**：页签下方那行提示原文是"鼠标悬停任意输入框 / 下拉 / 按钮…"，触发器一改它就**变成
  错误指引**，必须同步改成"鼠标停在参数右侧的 ? 上…" —— **提示文案必须与触发器同一处定义**。
  两条都补了专属用例：`划过输入框/下拉/按钮都不弹窗`（**等过 200ms 再断言**，区分"根本不出现"
  与"延迟出现"）+ `鼠标移开 ? 立即消失`（**同步断言**，留着旧缓冲必红）。
- **GEOUNED 自身没有 UI；它的"设置"= 一个 config.json（2026-09-23 源码级确证，§4 ADR 相关）**：
  **判据（可复跑）**：包内文件只有 `.py/.txt/.exe`；`bin\` 仅 `geouned_cadtocsg.exe` /
  `geouned_csgtocad.exe`（对应 `dist-info\entry_points.txt` 两条 `console_scripts`）；
  `grep -r "PyQt\|PySide\|tkinter\|wx\|QApplication"` **零命中**；两个脚本各只有 `-i/--input`
  一个参数。配置入口 `CadToCsg.from_json()` **只认 6 个键**（`Settings`/`Options`/`Tolerances`/
  `NumericFormat`/`load_step_file`/`export_csg`），执行顺序写死「构造四对象 → `load_step_file()`
  → `start()` → `export_csg()`」。**两个坑**：`config["load_step_file"]` 是**硬索引**（缺键 = `KeyError`）；
  `core.py:259` 的报错文案列出 `'Parameters'` 但**代码里没有这个分支**（文档幽灵键）。
  **语义同构**：config.json 省略某键 = 用构造默认值 ⇒ 与本程序前端「留空 = 不发送」完全一致。
  **参数面**：Settings 15 / Options 11 / Tolerances 15 / NumericFormat 14 / `load_step_file` 3 /
  `export_csg` 9。**判断更正**：`Settings.maxSurf` 官方只写 `#TODO`，但它实为**真空栅元切割的触发阈值**
  （`void/void.py:137`；全仓**仅** `void.py:108` 一处使用），与 `maxBracket` 是 **AND** 关系、
  `minVoidSize` 是尺寸地板、`while iloop < 50` 是内建上限（不可配）。
  ⇒ **纪律：参数"有没有文档"不能当作"要不要暴露"的依据，要 grep 它的使用点。**
- **GEOUNED 的 setter 是严格类型 ⇒ 映射层必须表驱动白名单 + 精确落型（2026-09-23 实测）**：
  `minVoidSize` 必须是 `float`（传 `int` 直接 `TypeError`）、`maxSurf`/`maxBracket`/`startCell`/
  `startSurf`/`nPlaneReverse`/`UCARD` 必须 `int`、各 bool 项必须 `bool`、`voidMat` 必须长度 3 的
  `(int, int|float, str)` 或空 list。落地方针：**缺省 / 类型不符 / 越界 → 该键不进 payload**
  （= 用 GEOUNED 默认），**不回落成本程序的默认值**（否则 GEOUNED 升版改默认值会被钉死）。
  **反向坑（必须专项测试锁死）**：GEOUNED 默认是**开**的项（`newSplitPlane`/`scaleUp`/
  `cellSummaryFile`），用户点成"关"时必须真的传出去，不能被"留空"逻辑顺手吞掉。
  **兼容性技巧**：payload 的 `settings` 区段键名与**旧 worker** 读的扁平键名逐字相同
  ⇒ 新旧 worker/转换器交叉搭配都不会"静默用错编号"。
- **悬停子弹框两条硬规则：颜色全走主题变量 + portal 到缩放容器（2026-09-23 实测）**：
  ① **`--accent-glow` 不可作文字颜色** —— 多巴胺主题里它是 `#FF8FAB`（粉），压在
  `--dialog-bg = rgba(255,222,240,.96)`（浅粉）上对比度约 **1.6:1，等于看不见** ⇒ 只作装饰色条；
  同理 `--red` 在多巴胺是 `#FF2D78`（粉）⇒ 高危警告用「⚠ + 红左条 + 12% 淡红底
  （`color-mix`）」，**文字一律 `--text-primary`**。② 气泡底用 **`--bg-surface`**（4 套主题均
  **不透明**），不能用 `--dialog-bg`（alpha .95~.97，会透出背后内容致对比度漂移）；阴影也用
  `--dialog-overlay`（原先写 `rgba(0,0,0,.45)` 会被"零硬编码色值"断言抓住）。
  ③ **必须 `createPortal` 到 `getAppPortalRoot()`**：`FloatingDialog` 的 `backdrop-filter` 会创建
  containing block，使其中 `position:fixed` 的子孙相对父定位并被 `overflow:hidden` 裁剪；
  挂到 `#root` 内的 `#app-portal-root` 才既逃裁剪又随 `--app-scale` 的 zoom 缩放。
  ⚠️ 挂 `document.body` **主题变量不会丢**（`data-theme` 设在 `<html>`，变量沿 DOM 继承），
  丢的是**缩放** ⇒ 位置与字号与控件错位。**测试锁法**：断言子弹框内联样式为 `var(...)`
  且 `outerHTML` 里没有 `#RRGGBB` / `rgb(`/`rgba(`。
- **列表类输入必须用 `<textarea>`：`<input>` 会吞掉换行（2026-09-23 DOM 测试抓出）**：
  实测向 `<input>` 写入 `"3，7\n12"` 得到 `[3, 712]` —— 浏览器对 `input[type=text]` 做值净化时
  删掉 `\n`，而该控件的释义里承诺"逗号或换行分隔"。⇒ 凡"多行/换行分隔"的输入一律 `textarea`。
  **这类问题静态审查看不见**，DOM 测试一次抓到 —— 与 §6「WebGL 类问题必须真渲染验证」同一纪律：
  浏览器行为相关的假设必须用真实 DOM/渲染验证。
- **同一种卡的多种「卡项形式」在 pymcnp 里是多个类、但 `_KEYWORD` 相同 ⇒ 按 keyword 建表会互相覆盖（2026-09-24 实测，3D 预览"体积爆炸"的真根因）**：
  pymcnp 把 `P` 拆成 `P_0`（四系数 `P A B C D`）/`P_1`（三点），**两者 `_KEYWORD` 都是 `p`**。
  `api_server._surf_classes()` 写的是 `_d[_kw] = _obj` ⇒ `dir()` 里靠后的 `P_1` **覆盖** `P_0`。
  于是四系数卡解析失败（两变体实测**互斥**：`P_0` 只认 4 项、`P_1` 只认 9 项），落进
  `parse_surfaces` 的 `except` 兜底 —— 而那条兜底的注释写着"pymcnp 的 P 只支持三点定义"
  （**误判**，因为 `P_0` 被自己的建表逻辑挤掉了）⇒ 把系数**转成三个点**。
  **致命处**：三点形式下游要走 C810 §3-17「**原点负感度**」规则，该规则**无视点序**、
  按 D 的符号重新定侧 ⇒ **`D < 0` 的平面正负侧整体翻转**。GEOUNED 生成的一般平面
  **全是四系数且 D 大量为负**（−197.99 / −32.509 / −19.799 …）⇒ 含这些面的栅元不再被
  界定、一路漏到包围盒 ⇒ 用户看到的"体积爆炸、形状全变"（块 002 重建体积达真值 **71 倍**）。
  ⚠️ 兜底里"校正三点法向与 (A,B,C) 同向"那几行**毫无作用** —— 下游 `plane_from_points`
  会无视点序。**作者防住了点序，没防住规则本身。**
  ⇒ **纪律：① 按 keyword 建 pymcnp 类表时必须保留全部变体（值用列表）+ "逐个 try、
  第一个成功即用"；② 需要"迁就某个变体"的转换代码是危险信号 —— 先查是不是建表丢了变体；
  ③ 认不出来就如实报错，绝不静默出错几何。**
  同类 keyword 冲突共 11 组（`P/DF/DS/F/M/SB/SI/SP/T/TF/TR`），曲面里只有 `P` 会中招。
- **C810 §3-17 的「原点负感度」只适用于三点形式；四系数形式的正侧就是写下来的符号（2026-09-24 查证 PDF 第 541 页）**：
  手册原文 "If there are four entries on a P card, they are assumed to be the general plane
  equation coefficients… **The sense of the plane is determined by requiring the origin to
  have negative sense.**" ⇒ 那条规则属于"三点定义平面"这一节，**不能**套到四系数卡上。
  ⇒ 排查"平面朝反了"时，先分清**卡是哪种形式**，再谈规则 —— 本轮一开始我误判成
  `quadric.plane_from_points`（§3-17 实现）写错了，实际它是对的，错的是"不该走三点"。
- **`_plane_halfspace` 的厚板「横向 4B + 沿法向 2B」盖不满包围盒（2026-09-24 实测，同轮第二个 bug）**：
  厚板底面过参考点、沿法向伸出、横向 4B（半宽 2B）。要盖满 `[-B,B]³` **两个尺寸都要够**：
  ① 横向半宽 ≥ 盒角到「过参考点沿法向的直线」的垂直距离（**参考点 ∥ 法向**时 = √3·B）；
  ② 沿法向厚度 ≥ `√3·B − n·p`（只伸 2B 时要求 `n·p ≥ −0.268B`）。
  `P_1` 分支取"平面上离原点最近的点"（∥ 法向）因而安全；**`P_0` 分支取 `(D/A, 0, 0)`**，
  A 只是小分量时严重偏离法向；块 003 的平面 `n·p = −462.8 < −0.268×1242` 则中招第二条。
  两者都让 **`bb.cut(正侧)`（负侧）在没盖到的区域多留一块 ⇒ 交集漏出包围盒**。
  **修法**：参考点**投影成最近点**（不变量下沉到唯一构造点）+ **厚度也取 4B**（恒够）。
  块 003 实测三级台阶：**+249% → +0.49% → −0.0049%（`closed`）**。
  ⇒ **纪律：「够不够大」这类几何覆盖从来不写判据的东西，一定会漏。**
- **GEOUNED 的凸分解会产出「3 个平面的交」这种**必然无界**的退化项（2026-09-24 实测，第三方缺陷）**：
  原模型（不切）那个 202 面实体的栅元表达式有 **229 个交项**，面数分布
  `{3: 1, 4: 3, 5: 57, 6: 101, 7: 47, 8: 9, 9: 6}` —— **唯一的 3 面项**由三个平面构成
  （`+144 P 0.707 0 -0.707 -19.799` / `−190 PY −553.067` / `−220 P 0.556 −0.831 0 549.767`），
  而 **3 个平面半空间的交在 3D 里必然无界**（围出有界区域至少要 4 个平面；`PY −553.067`
  连模型 y 范围 −180~220 都在外）⇒ 该栅元溢出到包围盒（实测 `infinite`、体积 ≈ 真值 2.7 倍）。
  **我们改不了 GEOUNED，但本程序的「实体预分解」恰好是它的解**：先把实体切成 ≤30 面的
  简单块，每块表达式都良定义 ⇒ 部署版端到端实测 **`cut=ON` 时 18/18 实体栅元 `closed`、
  体积合计 +0.0048%**；而 `cut=OFF` 为 +282%、1 个 `infinite`。
  ⇒ **遇到复杂厂房模型要建议用户开「启用实体预分解」**；也说明"把大实体先切小"这个
  产品决策不只是性能优化，**它还顺手规避了 GEOUNED 的退化分解**。
  ⚠️ **但它规避不干净**（同日第四批实测）：用户把档位调到**较粗（50 面）**时，
  9 块里的**栅元 4** 又出现一个 3 面退化项（`144(P_0) -190(P_0) -180(PY)`）
  ⇒ 体积 5.36e8（模型的 **195%**）、`infinite`、渲染成一块巨大的**异形三角锥**（用户原话）。
  **所以消费侧必须自己容错**：`app/freecad_preview.prune_unbounded_union_branches()`
  剔除并集里「**纯平面且约束数 ≤3**」的分支 —— 数学上必然无界的分支**不可能**属于
  有界的 CAD 实体，剔掉只会更接近真值。三条安全边界见该函数 docstring（只处理顶层并集 /
  只剔纯平面 / 剔完为空则原样返回）。**效果：栅元 4 → `closed`、3.49e7（+1.2%），9 块合计 100.005%。**
- **⚠️ 预览缓存落盘 + 指纹只含 deck ⇒ 改了几何引擎"用户看不到修复"（2026-09-12 与 09-24 **两次**踩到，已改为自动失效）**：
  `preview_cache` 不只是内存缓存 —— `get()` 在内存 miss 时从 `meta.json` **恢复**，
  **跨进程重启仍命中**（实测 `D:\MCNP\memory\preview_cache` 下积了 **18 个**指纹目录；
  LRU 上限 3 只管内存索引，重启后旧目录不会被驱逐）。
  而指纹原本只含 `(surfaces, cells, tr_cards)` + **人工** `GEOMETRY_CACHE_VERSION`
  ⇒ 改了几何引擎但**忘了 bump** ⇒ 旧 STL 被复用。2026-09-24 实测：改完退化项剔除后重跑，
  栅元 4 仍是旧的 5.36e8，**连重启后端都救不回来**，直到手动清 `preview_cache` 才生效。
  ⇒ **修法**：在人工版本号之外，把**几何引擎源码的内容摘要**
  （`_freecad_csg_worker.py` / `freecad_preview.py` / `quadric.py` / `voxel_csg.py` 的 sha256）
  并入指纹 ⇒ **引擎文件一改，旧缓存自动全失效**，不再依赖"记得 bump"这条纪律；
  `GEOMETRY_CACHE_VERSION` 升到 4 记录语义。
  ⇒ **纪律：凡是"靠人记得做某事"的缓存失效开关，都该加一个自动兜底。**
- **⚠️ 判据必须能"红"：`正侧 + 负侧 = 盒` 是恒真式，抓不到任何覆盖缺陷（2026-09-24 现场踩到）**：
  我第一版回归判据就是它 —— 但 `负侧 := bb.cut(正侧)`，两者按定义恒等于盒体积，
  所以**回退修复后照样绿**（典型假判据，比没有判据更危险：它给人"有保护"的错觉）。
  改成「OCC 的 `isInside` 必须与解析式 `n·x > n·p` **逐点一致**」后才真正能红
  （回退后 `P0_A_small` 7/27、`P0_A_tiny` 18/27、`P0_neg_far` 4/27 个采样点不一致）。
  ⇒ **纪律：写完判据先问"它在 bug 存在时会不会绿？"—— 不会红就当场废掉重写。**
  同族教训：`test_preview_bound.py` 为了不 import `api_server` 而**镜像**了一份解析逻辑，
  镜像里没有 `_surf_classes()` 的覆盖问题 ⇒ 对这类缺陷**天生看不见**（假 seam）。
- **序列化口漏字段 ⇒ 下游"读不到就放行"的判据会**静默全放行**（2026-09-24 实测，3D 预览"一坨"的真根因）**：
  `app/step_importer.flat_cell_json` 是 STEP 导入 → 前端 → `preview-3d` 这条路上
  **唯一的序列化口**，原先只输出 5 个键；而 `api_server.build_cells_data` 的
  「项14 cell 分类规则」要读 `imp_n/imp_p/imp_e`（graveyard → 不渲染）、`render`、
  `fill`、`fill_grid`、`u` —— 前端只是原样转发，**这些键没有任何环节能补回来**。
  更要命的是 graveyard 判据要读 `imp_*`，**而上游序列化口把它们丢了** ⇒ 取不到值
  ⇒ 判据**恒不成立**（与"自证判据退化成恒真"同族）。
  ⚠️ **别记反（2026-09-24 当场更正过一版）**：GEOUNED 生成的 deck **是带 imp 的** ——
  实测 `47 0 277 Vol=1.000 imp:n=0 imp:p=0 $Graveyard`。**失效是我们丢字段，不是 GEOUNED 没写。**
  另有一个反例必须记住：栅元 46（`Graveyard_in`，球内盒外真空区）GEOUNED **有意给 `imp:n=1.000`**
  （粒子可在其中飞行，按 MCNP 语义**不是**墓地）⇒ **imp 判据天然拦不住它**，只能靠注释判据。
  ⇒ 两条判据**各管一段、缺一不可**：imp 管"重要性 0"，注释管"GEOUNED 的边界结构"。
  后果：GEOUNED 的两个墓区被当普通栅元渲染 —— 栅元 47（`Graveyard`，半径 1049 球外）
  体积 = 模型的 **7372%**、bbox 2927³；栅元 46（`Graveyard_in`）**1583%**、2097³；
  把模型（1042×1751×260）整个包住、相机被撑到 ±2000 ⇒ 预览里只有"一坨"。
  **修法**：① graveyard 判定加第二条「**注释含 graveyard**」—— 这是 GEOUNED 的官方标记
  （`void.py:201/208` 写死 `MatInfo = "Graveyard_in"/"Graveyard"`，
  `mcnp_format.py:256` 也这么认），比 imp 可靠得多；② 序列化口补齐全部判据键。
  ⇒ **纪律：判据"读不到就放行"时，必须回头查序列化口喂了没有；跨层传数据的字段
  要在契约里显式列全（本轮同步了 `api.yaml` 的 deck.cells schema）。**
- **`import FreeCAD` 必须先于 `import Part`，否则**静默**退化（2026-09-24 实测，同族两处）**：  FreeCAD 的 `python.exe` 裸跑 `import Part` 必 `ModuleNotFoundError: No module named 'Part'`；
  只有先 `import FreeCAD` 才把它自己的 `bin` 挂上模块搜索路径（同一解释器实测：
  `-c "import FreeCAD, Part"` ✓ / `-c "import Part"` ✗）。**这个错不会报出来**，只会让：
  ① 可用性探测判"解释器里没有 FreeCAD 模块" ⇒ **静默跳过实体预分解**（用户表现："开了跟没开
  一样" —— 与 `_MEIPASS` 那次故障**表现一模一样、根因完全不同**，排查时别被表象带偏）；
  ② `geouned_worker._bbox_of()` **恒返回 None** ⇒ 分解自证**退化成恒真的空检查**
  （"看起来有保护、其实什么都没拦"，比没有检查更危险）。
  ⇒ **纪律：凡是"探测/校验"类函数，先证明它在可用环境下真能返回非空/非恒真值**，再拿它下结论；
  测试里锁住 import 顺序（`test_probe_imports_freecad_before_part` /
  `test_worker_bbox_reader_imports_freecad_first`）。
- **自证判据的不对称是刻意的：按"哪一边读不到"分别定（2026-09-24 决议）**：
  分解自证比对前后包围盒时，**原文件都读不出来 → 放行**（没有可比对象，FreeCAD 读取失败
  不该阻断导入）；**原文件读得出、产物读不出来 → 判定产物坏了、回退**。
  上一版写成"任一边 None 就放行" ⇒ 在 `_bbox_of` 恒 None 的那个 bug 下**退化成恒真**。
  ⇒ 纪律：**"读不到"不等于"没问题"**，降级路径必须逐边定义，且要为它写用例
  （现存 4 例：只产物读不到 / 只原文件读不到 / 包围盒不一致 / 一致）。
- **外部程序暴露「过程参数」，用户要的往往是「结果指标」（2026-09-24 决议）**：
  MCCAD 只给 `recurrenceDepth`（递归深度）—— 同样深度在不同模型上得到的块复杂度完全不同，
  所以"加档位"解决不了用户"每块面数控制在 30 以下"的诉求；改由 FreeCAD/OCC 侧自己实现
  **按面数上限收敛的二分**（最长边中分 + 切不动就换轴 + 切不动如实计数上报）直接给出结果指标。
  ⇒ **选依赖时先问"它暴露的是过程还是结果"**；过程参数再多档也不等于可控。
  配套判据：网格切 K 档只能得 3^K 块（3/27/81/192…），**无法对准面数目标** ——
  "看起来能调"和"真的能对准目标"是两件事。
- **切实体能压实体侧面数，压不动真空侧（2026-09-24 实测，别向用户许诺过头）**：
  274 m³ 厂房模型切到每块 ≤30 面后，**实体块**面数合计 194→367（18 块，最大 25 面），
  但 **28 个真空栅元最大仍有 48 面**。真空是实体**之间**的空隙，把实体切碎只会让空隙更零碎。
  ⇒ 用户提"每块 ≤N 面"时，**先问清是块还是最终栅元**，并如实报告没做到的那一侧。


## §7 技术争议与决议（语义记忆）

| 争议点 | 方案 A | 方案 B | 最终裁决 | 裁决理由 |
| :--- | :--- | :--- | :--- | :--- |
| F-A R1 不动点：生成器 C 注释头泄漏，解析器吸收 vs 生成器改头 | 解析器吸收防护（仅节头词汇精确剥离） | 生成器改头为不可吸收形式 | **方案 C，以 A 为主、B 为辅**（2026-08-12） | MCNP 注释只有 C 一种形式，现有解析器对任意 C 行都会在栅元注释/曲面 verbatim/other_cards 三路吞掉，不存在合法且三阶段天然惰性的注释形式。方案 C 把节头冻结为 banners.py 单一事实来源，生成器与解析器共享，R1 测试为漂移兜底；用户可见 INP 输出风格保留 |
| **出图产物：矢量 PDF+SVG vs 一律 PNG** | 二维出矢量 PDF+SVG（放大不糊、可编辑、投稿友好），三维出 PNG | **一律 PNG**（透明底；整幅颜色填充的图铺白底） | **方案 B**（用户 2026-09-19 裁决，2026-09-19 复述"2D 图就算了"） | 用户要的是"拿到的永远是同一类文件、另存为只问一次、不用纠结格式"。**代价明确接受**：2D 失去矢量性（放大到海报尺寸会糊、不能进 Illustrator 改线）。`buildVectorFigure` → `figureToPdf` 实现**保留**，将来要恢复只差"格式决策的口径"，不缺渲染能力 |
| **出图底色的默认值** | 白底（贴进 Word/论文最省事） | **透明底**（PNG alpha；颜色填充图自行铺白） | **方案 B**（用户 2026-09-19"该用透明底的用透明底"） | 透明底叠在任意底色上都干净；需要白底的场合（fmesh 热图）由调用方显式给，**不再有"忘了铺底导致白块"这种默认** |

## §8 变更日志（情景记忆 · 里程碑纲要，完整流水已外置）

> ⚠️ 本 § 编号被 docs/contracts/* 引用，**不得改名**。完整逐条流水（2026-08-11 起）见 **`docs/CHANGELOG.md`** + `docs/backend-changes.md` + `docs/frontend-changes.md` + git log。
>
> **维护规则**：每次批次完成后，在 `docs/CHANGELOG.md` 追加新条目；本 § 只在里程碑定型时更新一行。

### 版本里程碑

> ⚠️ **v1.7.6 之后有一长串「同版本重出包」批次**（纪律：bug 修复批严禁升版，故版本号恒 1.7.6）：
> 2026-09-12 STEP 导入 500 热修 → 09-16/17 几何曲面语义全类型审计（11 类）+ 打包坑 6.2 根治 →
> 09-19 排版审计/出图 PNG → 09-20 keff 解析 + 任务扫描 → 09-20 R1+O6 →
> 09-23 GEOUNED STEP 导入参数 UI → 09-23 MCCAD 实体预分解 → 09-23/24 子弹框两轮反馈 →
> **09-24 实体预分解换血（MCCAD → FreeCAD 自适应）+ P 卡感度 + slab 覆盖 + 墓区过滤（S10）**。
> **这条"同版本重出包"长链在 2026-09-26 终结：用户指定升版 v1.7.7**（含 S11 三条修复 + S10 全量）。

| 版本 | 时间 | 内容 |
| :--- | :--- | :--- |
| **v1.7.7** | 2026-09-26 | **计数卡前缀 `*` 全链贯通 + 栅元几何 `#` 判定 + 截面拖动两坑**（**用户指定升版**；本包同时带上 S10 那批未打包改动）：① 缝两端补 `fn_prefix`/`number_suffix` + 新增 `gui/src/utils/tallyBridge.ts` + F5 行环探测器轴控件；② 行首 `#` 按"字母/数字"判性质 + `normalize_geometry_spacing`（`-14#1`→`-14 #1`，挂解析侧与 pymcnp 消费侧）；③ 新增 `dragImport.ts`（只认真拖文件、leave/drop/end 一律熄、`pointerEvents:none`）与 `sectionView.ts`（旋转中心不含 pan，"拖 Δ ⇒ 内容正好移 Δ"由属性测试锁死）。门禁 pytest **1417/0/11**、vitest **104 files / 927 passed**、tsc 两档 0、build 0。手工链打包部署 + 部署版冒烟（见 §2 / S11）。**未 push** |
| **v1.7.6** | 2026-09-11 | **源演示修复二批 + 粒子圆点化 + 一键运行 MCNP 多核 tasks**（**用户指定升版**）：① 源演示"看不见栅元"根因二批 —— 后端补 camelCase 别名时**漏 `mat`** + `SourceTab` 把 **snake_case** `deck.cells` 强断言成 camelCase `LocalCellRow` ⇒ `material=""` ⇒ `getMatColor("")` 返回 `transparent` ⇒ `buildCellMaterial` 判为**真空 M0**（`opacity:0`，13 个外壳全不可见）；且取景误用体积窗口的 `computeFramingBox`（`VOLUME_FRAMING_RATIO=0.25`，源区/热室≈0.057）把外壳挤出视野。② 方向线不可见（世界空间固定长度 1.17 被取景缩成 ~1px）+「方向线长度」滑杆失效（`setDirectionLength` 从不重建几何）⇒ 改**屏幕空间恒定**。③ 粒子圆点化（`Points` 贴图 + `alphaTest`）。④ **一键运行 MCNP 支持多核 `tasks N`**：UI（`PreviewDialog` footer 核数滑杆 + PTRAC/SSW/SSR **选模式即提示**）+ 后端 `app/mcnp_tasks.py` 扫卡强制降级（C810 页 875 排他卡）。**实测 `tasks` 取物理核数而非逻辑核**（8 物理核机上 tasks 8 = 8.36s vs tasks 16 = 15.06s）。门禁 pytest **900** / vitest **625** / tsc 两档 0 / build 0。**已打包部署 + 冒烟通过**（部署版 `diff-inp` 200、`source-demo-sample` 200、5001 + MCP 8100 LISTENING）。commits `48c51ed` / `857aed1` / `b1f0043` / `21d93d0` |
| **v1.7.5** | 2026-09-04 | **AI 接入 inputcard-mcp（MCP over HTTP）+ 快捷建栅元六棱柱(RHP)/四面体 + 深模块化 + 废弃一键打包**（新功能上线，用户指定/确认升版）：`inputcard_mcp/` 包（6 深工具，统一按语义段读写）；主程序启动自动拉起 `--mcp-http`（本机 8100 `/mcp` + `/workspace`，含「当前工作区」会话 + 前端 AI 面板）；**移除 stdio 旧接入**（`--mcp-server`/注册MCP.bat 删除）；快捷建栅元扩到 HEX/TET + IMP 改数值默认 0；抽出深模块 `useQuickAddOverlap`；删除 `release.bat`/`release.ps1`（一键打包废弃，仅手动）；新增 `AI接入.md`。门禁 vitest 554/0 + tsc EXIT 0。reflog: `.git/logs/HEAD:250-251` |
| **v1.7.4** | 2026-08-27 | **3D 预览 MCNP 窗口裁剪修复 + U 分组侧边栏**（用户指定新功能上线升版）：① 实体=universe∩格元盒∩容器cell，修超壳/重叠外壳 + 无限水虚假水块（BEAVRS 超壳叶 48→16）；② 3D 预览侧边栏改 U 分组 + 保留未分组栅元；disc 改用容器裁剪 STL、subPitch 半径；版本五处同步。**18-28 追加**：disc STL 键错配修复（燃料 pin 方块→真实圆柱）+ z 居中（燃料棒/围板位置）|
| **v1.7.4（材料库深化，沿用版本待上级指定）** | 2026-08-30 | **材料库深化**（新功能）：用户可编辑持久材料库（custom/override、`D:\MCNP\material\material_library.json`、D盘回落 `%APPDATA%`）、导入导出 JSON·CSV（冲突三选 + 内容一致自动跳过）、xsdir 反向索引 + 组成自洽校验、📚 材料库管理面板、MT卡/其他随预设贯通；修复：编辑弹窗 `backdrop-filter` 裁剪（`createPortal`）、编辑保存后列表不刷新（去 useMemo）、材料库内编辑隐藏预设区、生成 INP 的 MODE+NPS 卡移数据卡段末尾；README 与 exe 同级放入；spec `_keep_py` 加 `material_library.py`。门禁 pytest **737/0** + vitest 534/535（flaky 隔离绿）+ tsc/build 过 |
| **GQ/SQ 预览修复 + 渲染增强 + OWEN 四项 + 参数扫描前端**（未 commit/发版，文件恒 1.7.2） | 2026-08-22 | 纯 numpy MC 去 vtk + TR + 解析切片 + 切线平面法 + BEAVRS/17×17 夹具 + mctal 解析 + 校验规则交叉核对（validator +3 规则）+ 参数扫描（sweep 模块 + 2 端点 + SweepDialog 前端 + DOM 交互测试）；门禁 pytest **573/0** / vitest **358/0** / tsc EXIT 0；打包冒烟通过；待 tauri build/部署 |
| **V1.7.2.2 批次**（文件恒 1.7.2） | 2026-08-19 | 4 修复进包：源卡文本模式漏生成 / SDEF 表单模式漏生成 + sdef_extra 往返 / IMP 归一化 / OUTP 解析+绘图+CSV（含 F1/F2/F5 泛化）；终版重打包部署，冒烟全过 |
| **v1.7.2** | 2026-08-18 | 新功能**快捷建栅元**（RCC/RPP/SPH 一键生成曲面+TR+栅元，8 次迭代打包）；3D 预览坐标轴/截面/取景修复批 |
| **v1.7.1** | 2026-08-15~16 | **PTRAC 粒子径迹可视化**交付 + 网格计数 3D 结果批（图层级透明/自适应色阶/并集取景）+ P0 体积层渲染两弹 + inp02 解析修复批 |
| **v1.7.0** | 2026-08-14 | 网格计数（FMESH/TMESH）3D 体积可视化大功能（meshtal/ 8 模块 + volume/ 11 模块 + 3 端点 25→28） |
| **v1.6.x** | 2026-08-11~12 | 文本↔表单双向互转 + P0/P1/P2 技术债清偿（F-A~F-H + F#1~F#7）+ 3D 预览性能（preview_cache/TickGrid 深模块）+ 词条专项 D-01~D-13 + 反馈 #1~#7 |

### 关键历史结论（压缩自 08-11~08-15 流水，细节见 CHANGELOG）

- 发布：**手动打包**（docs/手动打包方法.md）；release.bat 已停用（Git Bash MSYS 坑 + 自检失败）。
- 网格计数可视化 v1.7.0（FMESH/TMESH 体积渲染）；P0/P1 技术债清偿（251 绿）；3D 预览性能（preview3d-performance）；文本↔表单互转；用户 7 条反馈 + 词条专项 D-01~D-13（08-13）。

## §9 程序性记忆（操作手册 · 怎么做事）

### 打包链路（每次发布走此流程，详见 `docs/手动打包方法.md`）

> **打包唯一流程为手动**（`docs/手动打包方法.md`）。曾有一键脚本 `release.bat` / `scripts\release.ps1` 均已**废弃删除**（一键脚本曾解决第 ② 项 npm/npx 被 ExecutionPolicy 禁与 6.2 sidecar 时效坑，但整套一键能力已弃用）。当前**每次发布**按下面分步手动执行，**尤其 6.2 时效校验不可跳过**。

```
1. vite build                       （前端产物，~3-4s；node .\node_modules\vite\bin\vite.js build）
2. PyInstaller sidecar              （在 gui\ 下跑 gui/mcnp_sidecar.spec，产物名 "python"；
                                     ★ 必须带 --distpath dist_sidecar（默认落 dist/ 会被 vite 清掉）；
                                     ⚠️ --workpath 用 build_sidecar 时，build-release.mjs 清的
                                     build/mcnp_sidecar 并不是同一目录（"清缓存"对不上，见 §6）；
                                     核对 _keep_py / _keep_dirs 清单，如 outp_parser.py/meshtal/ 等新增模块）
3. 替换 binaries                    （把新 sidecar 的 python.exe + _internal 换进 target\release\；
                                     复制完**双向比对文件数与总字节**——只比 exe 大小不够）
4. tauri build                      （⚠️ rust 环境变量必须指到**子目录**：`RUSTUP_HOME=D:\rust\rustup`、
                                    `CARGO_HOME=D:\rust\cargo`、`PATH` 前置 `D:\rust\cargo\bin`
                                    —— `D:\rust` 下是 `cargo/` + `rustup/` 两个目录，**根目录不是 home**；
                                    指错会报 `rustup could not choose a version of cargo to run … no default
                                    is configured`（2026-09-20 实测，构建在 tauri 阶段中止、不产出半成品）。
                                    ★ 首选 `npm run build:app`（vite → 预同步 → tauri → 后同步+自检）。
                                    ⚠️ **别在干净工作区跑 `npm run build:release`**：它把 tauri build 排在
                                    PyInstaller 前，而 beforeBuildCommand 含 sync-sidecar ⇒ 无 dist_sidecar/
                                    时必中止（2026-09-26 实测，见 §6/S11.3））
5. ⚠️ 6.2 时效校验（必做）           （tauri 增量编译不刷新 target\release 的 sidecar！
                                    ★ 最快判据：查 target\release\_internal\app\ 里**有没有本批新增模块**
                                      —— 2026-09-11 实测缺 mcnp_tasks.py，一眼看穿"版本号新、后端旧"；
                                      ★ 更硬：松散 .py 与源码 **sha256 对拍** + 部署版打**本批相关端点**做功能级冒烟
                                      （2026-09-26 用 `/api/parse-inp` 那张 `#` 折行卡一次验穿 PYZ 与解析模块）；
                                      亦可对比 python.exe 的 mtime/体积，不一致就按手册强制覆盖）
6. 备份 + 部署 D:\MCNP\MCNP输入卡生成器（⚠️ 先杀运行中的旧主程序 + 占 5001 的 sidecar，**还要查 8100**
                                      —— `--mcp-http` 子进程不随主程序退出（2026-09-26 实测）；否则文件锁目录致
                                      _internal 残缺；备份可用**整卷改名移动**（秒级、可回滚）到 D:\MCNP\_backup_<旧版本>_<时间戳>）
7. 冒烟                             （起部署版 → 5001 探活 → 打端点；⚠️ 先确认 5001 空闲，被占则请求被劫持
                                      产生假象；收尾杀掉主 exe + 其 sidecar **按路径精确匹配**，勿误杀他处 python）
```

**关键坑提醒**：① 6.2 时效坑**每次都命中**，不可跳过；② 部署前杀进程（锁目录）；③ 冒烟前先清 5001（否则劫持出假象）；④ 版本**六处**必须一致（`tauri.conf.json` / `package.json` / **`package-lock.json`** / `Cargo.toml` / `Cargo.lock` / README 徽章；Cargo 不接受四段号）；⑤ **升版后必须重新 `vite build`** —— 侧边栏版本号由 `Sidebar.tsx` 直接 `import package.json`，**构建期打进 bundle**（不从磁盘读）。

### 测试门禁（发布前必须全绿）

| 门禁 | 命令/位置 | 基线 |
| :--- | :--- | :--- |
| pytest | `tests/`（unit + parser + integration，含契约漂移闸门 test_api_contract.py 与真实 HTTP） | **最新实跑（2026-09-26，v1.7.7 发布批）：1417 passed / 0 failed / 11 skipped**（`python -m pytest tests/ -q`，**独占跑**）。沿革：… → 1298+1F(09-23 GEOUNED 参数 UI) → 1332(09-23 MCCAD) → 1366(09-24 自适应切分) → 1376(09-24 P 卡感度/slab) → 1381(09-24 墓区过滤) → **1417(09-26 S11：栅元 `#` 17 例 + 计数卡身份字段 5 例 + 既有批次累计)**。**重跑后请覆盖本行**；⚠️ 跑前 **unset `PYTHONIOENCODING`**（见 §6 环境坑 —— 设成 utf-8 会让 `test_meshtal_worker.py` 的 GBK 子进程读取炸掉），并**先确认 5001 空闲**（否则契约 HTTP 用例测的是别人）。**2026-09-26 补记（两次实测复现）**：`test_http_mcnp_detect_lists_all_candidates` 在**与 vitest 全量并发**时 120 s 超时（该用例要扫全盘找 MCNP 安装），**隔离单跑 5 s 通过** ⇒ 门禁别与别的重活并发跑 |
| vitest | `gui/test/`（**104 个测试文件**；含 jsdom DOM 交互） | **最新实跑（2026-09-26，v1.7.7 发布批）：104 files / 927 passed / 0 skip**。沿革：… → 877(09-24 自适应切分) → **903(09-26 上午：tallyBridge 19 + tallyPrefix.dom 7)** → **927(09-26 S11：dragImport 6 + sectionView 14 + crossSectionPan.dom 4)**。**重跑后请覆盖本行**。⚠️ **侧车产物存在时**（跑过 PyInstaller 的机器）会走 `syncSidecar.test.ts` 的"改名探测"分支 —— 该用例已加**前置清残留 + 兜底还原**（见 §6 那条 EPERM 坑），若它红了先看 `gui/dist_sidecar/python_guard_test` 是否被别的会话留下 |
| tsc | `gui/` 下 `npm run typecheck`（= `tsc --noEmit && tsc -p tsconfig.test.json --noEmit`） | 两档 **EXIT 0**。**2026-09-10 扩容**：此前只查 `src/`，测试文件不在类型检查内（审计 TD-17） |
| 漂移闸门 | handlers dict ↔ `docs/contracts/api.yaml` 双向一致；spec `_keep_py` ↔ `_import_app` 双向一致 | **49 端点**；spec 闸门（`test_sidecar_spec_keep.py`）**绿** |

**已知 flaky（2026-09-10 已修）**：colorize 128³ 计时用例负载偶发 >50ms —— 该断言属"单样本墙钟阈值"反模式，已改为多次取中位数 + 宽松上限（或移出默认门禁）。**不再以"隔离单跑即绿"作为放行理由**（审计 TD-18）。

### 版本发布纪律

- bug 修复批**默认严禁升版**；升版仅限**上级（用户）指定**——**2026-09-26 例外经用户明确指定升到 1.7.7**（此前 09-12~09-24 一长串 bug 修复批全部恒 1.7.6，纪律不变）。
- 版本**六处同步、实为 7 个字段**：`tauri.conf.json`（`package.version`）/ `package.json` / **`package-lock.json`（顶层 `version` + `packages[""].version` 两处）** / `Cargo.toml` / `Cargo.lock`（`name="mcnp-ui"`）/ README 徽章；改完**复查零个旧版本号残留**（`Select-String -Pattern '1\.7\.6'` 那六个文件）。
- 侧边栏版本号来自 `Sidebar.tsx` 直接 `import pkg from "../../package.json"`（单一来源，升版不再破）—— ⚠️ **构建期打进 bundle**，故**升版后必须重新 `vite build`**，否则界面仍显示旧版本。


