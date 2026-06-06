# AsymAgentMark-TK 论文章节规划（中文版）

<aside>
🎯

**整体定位（先定调，再逐章写）**

- **范式选择**：明确走解释 / 机制范式，不与对称 AgentMark 比 capacity 数字。核心卖点是「揭示对称行为水印的一个结构性失效模式 + 给出能在该模式下存活的最小修复」。
- **一句话故事**：行为水印不该要求验证方复现精确逐步概率；当概率不可信、而 top-k 排序仍可信时，应当 *decode from the invariant that survives*——排序。
- **核心 Insight（必须提到 Abstract / Intro 的卖点位）**：rank 是一个比 calibrated probability 更稳、比 selected-action 更有信息量的「中间信道」。
- **核心度量（统一全文的标尺）**：有效容量 C_eff = 名义容量 C_nom × 解码成功率。一句话点破「AgentMark-F 名义容量高，但验证方信道一降级、实际容量就归零」——比定性说「rank 更鲁棒」有力得多。
- **caveat 策略**：全文防御性措辞统一收拢。正文每个边界只声明一次，并立刻用 contribution 对冲；论证细节下沉附录。避免「整篇都在忏悔」。
</aside>

<aside>
🧭

**写作顺序（由内而外）**：Method（已稳）→ Experiment（重排，强化 pooled）→ Introduction（按解释范式重写定位）→ Related Work → Abstract + Conclusion → Limitation。

</aside>

<aside>
📊

**实验数据主线策略（本次重点）**

- **把 pooled / audit-window recovery 抬成头号证据**，strict single-trajectory recovery 退为「受 packet scarcity 限制的诚实下界」，不再当主卖点。
- **新增核心图：恢复率 vs. pooled 轨迹数曲线**。x 轴 = 池内轨迹数 n，y 轴 = payload recovery rate；分线条画 k∈{3,5,10} / 数据集 / 跨模型方向。
- 这条曲线是 **Proposition 2（packet scarcity，E[M_pool] 可加）的经验实例化**——理论↔实验直接对位，是全文最强的 Claim→Evidence 闭环。
- 同时给出「达到目标恢复率所需的最小池大小」这个可部署读数（如 pool=20 时 ≈1.00），把弱 strict 结果转成强 audit 结论。
</aside>

---

## 1. Introduction

- **定战场**：LLM agent 已从「出文本」转向「走轨迹」，provenance 的对象是 trajectory（工具调用 / 子目标 / 动作），而非最终文本。
- **制造冲突（Gap）**：现有行为水印（AgentMark-F）是对称的——解码要求验证方复现 embedder 的精确逐步概率。但真实审计接口常只给 rounded top-k / 换了模型 / 代理模型，概率会变、排序常不变。
- **拔高到结构性失效**：这不只是工程不便，而是 verifier-channel 失效模式（概率 bin 会因为累积边界跨越 rank 而错位）——SOTA 在原生指标下很强，在 rank-only 审计下可能直接崩。
- **亮武器 + 立旗**：提出 AsymAgentMark-TK，用 rank-path 解码替换 probability-bin 解码。第一屏就把唯一不可被说成「缝合」的概念贡献焊死：把 verifier-channel robustness 确立为一个独立失效维度。
- **Contribution 列表**（垂直列表；每条都写「新在哪 + 所以重要」，别只罗列做了什么）：
    1. **失效模式（诊断贡献）**：首次指出并形式化 verifier-channel 失效——对称行为水印默认验证方能复现精确逐步概率，我们证明 probability-bin 解码在真实信道降级下结构性失稳（Lemma 1），并把它确立为独立于容量 / 隐蔽性的鲁棒性维度。
    2. **度量框架（C_eff，本文标尺）**：引入有效容量 C_eff = C_nom × Decode Success Rate，拆开「名义容量」与「实际可用容量」；用它揭示 AgentMark-F 的容量优势在信道降级后归零、而我方名义容量虽低却几乎不掉。这是组织整个评估的 yardstick。
    3. **方法（迁移 + 耦合）**：把弱非对称 rank 构造实例化到 agent 行为信道（rank-path 解码不碰任何概率值），并接确定性 RLNC，区分 per-trajectory 归属与 pooled 审计证据。
    4. **评估框架（信道知识分级 + 四轴）**：提出 L0→L6 验证方信道知识分级（精确 / 同模型 top-k / 跨模型 / 含噪），沿容量(C_eff)·隐蔽性·鲁棒性·证据强度四轴，系统测量行为水印随验证方信道知识的退化——据我们所知是首个这样的系统刻画。
    5. **可部署读数**：给出达到目标显著性 / 恢复率所需的最小观测步数 N_min 与最小池大小，把可行性结果转成运营可用结论。
- **注意**：Intro 是推销不是综述，把 Insight 一句话提上来。

## 2. Background & Motivation

- **2.1 行为水印**：解释 agent 在每步从行为分布 Pt 采样，AgentMark 用分布保持编码替代普通采样；强调长程、有状态，per-step 偏移会累积成 task drift——这是「为什么必须分布保持」。
- **2.2 对称瓶颈**：差分重组 + 循环移位在双方共享精确概率时高效；一旦验证方重建的 P′t 偏离 Pt，bin 结构变化→选中行为被错误 bin 解读。补充：很多接口故意不给 calibrated 概率，但常保留高概率行为的相对顺序。
- **2.3 弱非对称**：在 symmetric / asymmetric 之间引入中间地带——sender 有全信道，receiver 只有部分但非平凡的信道知识（top-k 排序）。这是全文的理论支点。
- **配 Table 1**（定位表）保留：Token WM / AgentMark-F / AsymAgentMark-TK 三行，对比 carrier、preserved object、verifier channel。

## 3. Problem Formulation

- **3.1 行为信道**：定义轨迹、Bt、Pt、key 与 per-step 伪随机；定义三种验证方视角——exact（上界）/ rank（部署目标）/ selected-only（负对照）。给出 top-k rank consistency 定义 argsortk(Pt)=argsortk(P′t)。
- **3.2 对手与需求**：三类扰动（step erasure / distribution perturbation / rank noise）；secret-key provenance 设定；removal vs. framing 两类对手；明确审计边界（日志完整性 + 候选规范化是部署前提）。列四条需求：utility preservation / weak-asymmetric correctness / low false positives (2^-L) / erasure tolerance。
- **3.3 Non-Goals**：不是通用去水印防御；不假设能复跑原模型；对抗任意改写需外部 root of trust。把「能做 / 不能做」一次讲清，省得后面反复打补丁。

## 4. Design

- **4.1 概览**：四组件（估计 Pt → 按概率排序取 top-k → interleaved rank split → 确定性 RLNC），配 Fig.1 系统图（embedder 全信道 / log / verifier 部分信道）。
- **4.2 二元分布保持原语 BinEnc**：给出 rm=(rS+½Sm) mod S，证明选组概率恰为 Sj/S；解释「zero-bit 分支是有意为之」——容量机会性、cover 分布不变，在 agent 场景比文本风格扰动更不易被察觉。
- **4.3 Rank 编码器**：top/tail gate → 归一化 top-k → 偶/奇 rank 递归切分 + BinEnc。强调 interleaving 的必要性（平衡质量、保留可恢复 rank path）。
- **4.4 Rank 解码器**：只用选中行为的 rank q，按奇偶反推路径（q←⌊q/2⌋），奇分支出 1 bit；解码器**不碰任何概率值**，每步固定消耗 ⌈log2 k⌉ 个 DRBG 值。
- **4.5 编码层（RLNC）**：GF(2) 上确定性 RLNC，ci=⟨ai,m⟩；强调它把两个常被混淆的问题分开——「单步能否产出可靠 coded bit」vs.「是否攒够独立 bit 解出 payload」。这正是后面 pooled 曲线的理论铺垫。
- **4.6 验证协议**：输入预注册 key/payload + 规范化日志 + top-k 重建；输出 positive / inconclusive / negative 三态；强调 rank-quality gate 与水印统计量分离（避免把「重建不可靠」误判成「轨迹干净」）。
- **4.7 实现注记**：SDK 包装、HMAC-SHA512 DRBG、rt_sync 固定预算、tie 处理。
- **4.8 参数选择**：k 的可靠性—容量权衡；报 k∈{2,4,6,8,10,20} 的 sweep，不调单一最优。

## 5. Security Analysis

- **Prop 1 分布保持**：归纳证明每个 top-k 叶概率 = 归一化质量，乘 top-k mass 还原 Pt(b)。
- **Lemma 1 概率-bin 不稳定性（重点抬升）**：四行为玩具反例——同 rank 序、不同概率值导致 prefix bin 错位。这是全文最有价值的负结果，应在 Intro/机制诊断里反复呼应。
- **Theorem 1 保序鲁棒性（弱化篇幅）**：rank 解码器只读 rank，故保序扰动不改解码结果。诚实标注：这条接近定义级真命题，是「正确性边界」而非主要贡献，别给它太多版面。
- **Cor 1 / Prop 2**：Cor 1 给 bit-match 期望与 Hoeffding 尾界；**Prop 2（packet scarcity，E[M_pool] 可加）要重点写**——它直接解释「短 ToolBench strict 弱、pooled 强」，并为 §6 的轨迹数曲线提供理论。
- **False positives**：2^-L 解析阈值 + 多重检验 union bound（N·2^-L）；给 L=32/64 的数量级。
- **Key privacy / Claim binding / Limits**：明确预注册、域分隔、轮换；明确对任意 rank 操纵不鲁棒（弱非对称的预期边界）。

### 5.7 理论分析（新增：回答「top-k 取几最好」与「鲁棒边界」）

- **Prop 3 — `C_eff` 的 top-k 最优性（回答 top 几最好）**：设 `C_nom(k)` 随 k 单调不减（更多 rank 信息，上限 `H(D)`），`DSR(k)` 随 k 单调不增（验证方要复现更深 top-k 序，含噪下更易错位）。则 `C_eff(k)=C_nom(k)·DSR(k)` 在弱条件下单峰，存在内部最优 `k*`，满足「边际容量增益 = 边际可靠性损失」。直觉：低熵任务（ToolBench）`DSR` 掉得快 → `k*` 小；高熵任务（ALFWorld）→ `k*` 大。把实验 1.2 从「试了 k 挑了一个」升级成「理论预测内部最优、实验证实」。
- **Lemma 2 — rank-noise 鲁棒边界（回答鲁棒边界）**：相邻交换噪声率 ε 下，解码器每步读 `⌈log2 k⌉` 个 parity bit，被选 rank 错位概率上界 `p_flip ≤ 1−(1−ε)^(c·⌈log2 k⌉)`；每个 coded bit 错误率 ≤ `p_flip`，经 Cor 1 的 Hoeffding 尾界推出可容忍噪声阈值 `ε_max(k,L,α)`。预测 k 越大每步信息多但 `p_flip` 升——鲁棒性与容量的二次权衡。实验 3.1 验证。
- **Prop 2 强化 — 恢复阈值闭式**：GF(2) 上解 L-bit payload 需 ≥ L 个线性无关 coded bit（留 `L+δ` 余量克服秩亏）。单轨迹 `E[M_traj]=N·(1−r)·DSR(k,ε)`，pooled n 条 `E[M_pool]≈n·E[M_traj]`（Prop 2 可加）。恢复阈值 `n ≥ (L+δ)/E[M_traj]`，给出「达到 ≈1.0 所需最小池 / 最小步」的可部署闭式。实验 1.3 + 3.2 验证。
- **`N_min` 显著性边界**：单侧二项下 `N_min ∝ z_α² /(q−0.5)²`，每步命中率 `q−0.5` 随 `log2 k` 增 → `N_min` 随 k 降。实验 4.1 / 4.2 验证。
- **诚实边界**：除 Prop 2 外均为「给定噪声模型下的期望级刻画」，非最坏情况保证；对任意 rank 操纵仍不鲁棒（与 §3.3 Non-Goals 一致）。每条标注「紧 / 启发式」，不写实验撑不起的 bound。

## 6. Evaluation（按新主线重排）

- **6.1 Setup**：ALFWorld + ToolBench；DeepSeek Chat / Gemini 2.0 Flash；五方法（vanilla / clean / RG / AgentMark-F / AsymAgentMark-TK）；语料与 decode-capable 计数；说明 8-bit 是 capacity 诊断 proxy，非部署标识。
- **6.2 协议**：三视角 + rank-noise（ϵ 代理）+ erasure；声明聚合而非挑最优。
- **6.3 复现轨迹**：脚本↔表对应（watermark_[sampler.py](http://sampler.py) / rlnc_[codec.py](http://codec.py) / 各 summary.csv）。
- **组织标尺 = 有效容量 C_eff = C_nom × Decode Success Rate**：整章按《实验设计》的四轴组织——轴1 容量(C_eff)·轴2 隐蔽性·轴3 鲁棒性·轴4 证据强度，而非按 Table 5–10 罗列。
- **两张头号图**：① C_eff vs 信道知识等级（L0→L6）——AgentMark-F 从 L1 起崩、我方守住，是 story 成立与否的图（实验 1.1）；② payload recovery vs pooled 轨迹数——把 strict 弱转成 audit 强（对应 Prop 2）。
- **RQ 重排**：核心 RQ = 行为水印的实际可用容量如何随验证方信道知识退化，以及 pooled 审计窗能否补偿 packet scarcity。

### 轴 1 容量（Capacity）——全文 story 主轴

- **实验 1.1 ⭐ `C_eff` vs 信道知识等级（L0→L6）**（核心图，并入旧 Table 5 的 rank-only 证据）：Clean / RG / AgentMark-F / Ours 四方法，画 `C_eff` 从 L0（精确 `P_t`）→L6（含噪）的退化曲线。预期 AgentMark-F 在 L0 最高、L1 起急降、L3–L6 趋零；Ours 名义略低但 L1 起稳住。selected-only 作 0 比特负对照。明确这是 Lemma 1 的经验对应，不是 capacity 竞赛。
- **实验 1.2 Top-k 消融 + `k*` 验证**（对应 Prop 3）：`k∈{2,3,5,10,full}`，同图叠 `C_nom`（虚线）与 `C_eff`（实线），定位内部最优 `k*`；分 ALFWorld / ToolBench 展示「高熵任务 `k*` 大、低熵任务 `k*` 小」。
- **实验 1.3 ⭐ pooled 恢复 vs 轨迹数（审计窗有效容量）**（对应 Prop 2）：payload recovery vs pooled 轨迹数 n 的曲线，分 `k∈{3,5,10}` / 数据集 / 跨模型方向画线；标注达到 ≈1.0 所需最小 n。把 per-trajectory `C_eff` 提升为 audit-window 有效容量；strict 弱 = packet scarcity 的必然，pooled 即补偿。跨模型 live rerank 作最强 deployment 证据，但只声明 ToolBench、不外推 ALFWorld。

### 轴 2 隐蔽性（Undetectability）

- **实验 2.1 效用保持**：SR + 平均步数，五方法 × 模型 × 数据集；分别比 AgentMark-F / Ours 相对 Clean / Vanilla，结论保守表述（小差异不显著）。
- **实验 2.2 行为分布统计检验**：复用 2.1 轨迹，算 `JSD(Clean‖method)`；预期 Clean≈AgentMark-F≈Ours≈0、RG≫0。

### 轴 3 鲁棒性（Robustness）

- **实验 3.1 ⭐ 排名噪声注入**（对应 Lemma 2）：`ε∈{0,0.05,…,0.5}`，相邻交换 + Kendall-tau 两种噪声模型分别画线；叠理论 `ε_max` 阈值线。
- **实验 3.2 步骤擦除 + 信道降级联合**：擦除率 r × k 热力图，对比 AgentMark-F+RLNC / Ours+RLNC，验证 RLNC 与弱非对称解码叠加鲁棒（接恢复阈值闭式）；满分（≈1.0）单元下沉附录，正文只留能支撑「pooled 越过 packet scarcity」的关键行。
- **实验 3.3 语义改写**（P3，视时间）：轻/中/重改写，报排名保持率 + 解码率，附 ROUGE-L / Jaccard 客观量化。
- **实验 3.4 假阳性**：Clean 轨迹 × 1000 随机 payload，`FPR≈2^−L`；k 对 FPR 几乎无影响。

### 轴 4 证据强度（Evidence Significance）

- **实验 4.1 ⭐ 解码置信度曲线**：单侧二项，p-value vs 观测步数 N 的对数折线，标 `α=0.05/0.01/0.001`；k 越大同 N 下 p 越小。
- **实验 4.2 最小证据阈值 `N_min`**（对应 `N_min` 边界）：从 4.1 取首次 `p<α` 的 N，画 k×L 热力图。
- **实验 4.3 鲁棒性补偿分析**：攻击下维持 `p<0.01` 的额外步数倍率 `N_attack/N_clean`，对照理论补偿线（如 `≈1/(1−ε)²`，若数据支持即 Lemma 级）。

## 7. Discussion

- Exact probability is a luxury（有精确概率时 AgentMark-F 更省，rank-only 时才轮到我们）；ToolBench 低熵 regime；rank consistency 可观测（Kendall tau / adjacent-swap）；为什么不全非对称；自适应对手；运营审计流（低置信≠干净，应判 inconclusive）；从可行性到部署的三项工程检查。
- **结尾点睛**：把 *decode from the invariant that survives* 放在这里收束，并与 Abstract 呼应。

## 8. Related Work

- 四块精准对位：① Token/LLM 水印（互补，文本信号在编译成动作后丢失）；② Agent 行为级 provenance（Agent Guide / AgentMark / Sequential——我们问的是「验证方需重建什么信道」而非又一个检测统计量）；③ 隐写与分布保持采样（Meteor / 弱非对称[7]——明说 rank 原语非原创，贡献在迁移+耦合+评估）；④ RLNC 纠删 + agent benchmarks。每块末尾一句「与我们的区别」。

## 9. Threats to Validity & Ethics

- 把全文散落的 caveat 收到这里集中讲：offline 后处理 proxy、verifier 扰动覆盖不全（L5/matched-top-k 仅 ToolBench）、benchmark 覆盖、统计不确定性、候选规范化、分布 elicitation。
- **9.1 伦理**：限于 provenance / 授权审计；不得用于隐蔽监控；误归属的治理风险（公布阈值、报告 inconclusive、留审计日志）。

## 10. Conclusion

- 重述失效模式（probability-bin instability）+ 修复（rank-decodable 分区树）+ 权衡（让出 exact-channel 容量换部分信道鲁棒）。
- 明确这是 partial-channel 可行性证据，非生产认证；收口三件待办：更长 live 轨迹、端到端 coded-payload 恢复、跨模型 rank 校准。

## 附录 A–E

- **A** 分布保持完整证明；**B** DRBG 固定预算同步；**C** RLNC payload 恢复；**D** rank 稳定性与 top-k 选择（温度重标定保序等）；**E** artifact 映射（表↔CSV）。
- 把正文收拢下来的论证细节、满分鲁棒性表、完整 prompt/超参都放这里。

---

<aside>
✅

**下一步推进顺序建议**：先定 §1 + Abstract 的新定位（解释范式 + Insight 上扬）→ 再重排 §6 把 pooled 曲线做出来 → 最后统一收拢 caveat。

</aside>