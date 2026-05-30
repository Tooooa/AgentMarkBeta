# 论文手画图规划

本文的图不应该只是把算法步骤画出来，而要服务一条主线：AgentMark-F 在 exact-probability channel 下很强，但真实审计经常只有 top-k rank；AsymAgentMark-TK 的贡献是把 decoder statistic 从 probability bin 换成 rank path，从而修复 verifier-channel robustness 缺口。

## 总体建议

- 核心必画图：4 张。
- 最优组合：Fig. 1 系统图 + Fig. 2 机制失败图 + Fig. 3/4 编码解码双栏图。
- 如果版面紧张，可以把 Fig. 3 和 Fig. 4 合并为一张双栏方法图。
- 表格结果不建议全部改成图。当前数值表已经承担精确对比，手画图应承担“机制解释”和“审稿人快速理解”。

## Figure 1: Weakly Asymmetric Behavioral Watermarking System

当前位置：`fig:system`，Design Overview。  
优先级：P0，必须重画。  
建议版式：跨双栏 `figure*`。

### 作用

这张图是论文门面，回答审稿人的第一个问题：这个工作到底改了什么验证假设？

它要让人一眼看到：

- embedder 端有完整行为分布 `P_t`，所以能保持 utility/distribution preservation；
- trajectory log 只记录被选行为、上下文、claim metadata，可能有 erasure；
- verifier 端不需要 exact probability，只需要 reconstruct top-k rank order；
- RLNC 是最后的 payload recovery 层，解决的是 evidence accumulation，不是 per-step rank decoding 本身。

### 预期内容

从左到右四个模块：

1. Agent step/context
   - 输入：`h_t`, candidate behaviors `B_t`
   - 产物：probabilities `P_t`
2. Embedder full channel
   - 排序得到 `sigma_t`
   - rank encoder 选择 watermarked behavior `b_hat_t`
   - 标注：uses probabilities only to preserve policy
3. Trajectory log / audit evidence
   - logged `h_t`, `b_hat_t`, claim id, payload namespace
   - 标注：steps may be erased
4. Verifier partial channel
   - reconstructs only top-k order `sigma'_t`
   - rank decoder recovers coded bits
   - RLNC solver recovers payload when enough packets survive

### 视觉要点

- 用两种 channel 颜色区分：
  - full probability channel：深蓝或黑色实线；
  - rank-only channel：绿色或青色实线；
  - unavailable exact probability at verifier：灰色虚线并打叉。
- 在 embedder 和 verifier 之间明确写：
  - `P_t` is private/full at embed time
  - verifier observes `sigma'_t`, not calibrated `P'_t`
- 不要把 RLNC 画成主算法核心；它是右侧的 recovery layer。

### 建议 caption

`System view of weakly asymmetric behavioral watermarking. The embedder uses calibrated behavior probabilities to preserve the marginal policy, while the verifier decodes from top-k rank order and accumulates enough coded packets for RLNC payload recovery.`

## Figure 2: Probability-Bin Instability Under Rank-Preserving Perturbation

当前状态：论文里还没有这张图。  
建议新增 label：`fig:bin-instability`。  
优先级：P0，强烈建议新增。  
建议位置：Security Analysis 里 Lemma 1 附近，或 Introduction 末尾作为 motivation figure。

### 作用

这张图负责把核心理论贡献画出来：不是我们单纯把 rank 用到 AgentMark，而是发现 probability-dependent bin 在 rank-preserving perturbation 下会失稳。

它对应论文里的 Lemma 1。审稿人看到这张图后，应该立刻明白为什么“exact-channel SOTA 表现好”不等于“真实 top-k audit 表现好”。

### 预期内容

画一个 toy example，左右两列：

左列：Embedder distribution `P`

- rank order：`a > b > c > d`
- probabilities：`0.45, 0.30, 0.15, 0.10`
- cumulative threshold `1/2`
- first probability bin: `{a, b}`
- selected behavior：`b`
- decoded bin：Bin 1

右列：Verifier/proxy distribution `Q`

- rank order 仍然是：`a > b > c > d`
- probabilities：`0.55, 0.25, 0.12, 0.08`
- same threshold `1/2`
- first probability bin: `{a}`
- same selected behavior：`b`
- decoded bin：Bin 2

底部加一条 ours 对照：

- same rank path for `b`
- probability values changed, rank path unchanged
- decoded state stable under top-k rank consistency

### 视觉要点

- 两列柱状图或横条图都可以。
- threshold 用一条明显的竖线或横线表示。
- `b` 用高亮色标出，强调 same selected behavior。
- 在两列之间标注：`same rank order, different bin boundary`。
- 图底部可以用一个小的 rank path：`rank(b)=1 -> odd branch -> bit event`，说明 ours 只看 rank。

### 建议 caption

`Probability-dependent bins can change under rank-preserving probability perturbations. The same selected behavior b is assigned to different bins under P and Q even though the rank order is unchanged; a rank-path decoder remains stable because it ignores probability values at verification time.`

## Figure 3: Rank Encoder and Distribution Preservation

当前位置：`fig:enc`，现在是伪代码框。  
优先级：P1，建议重画；如果版面紧张，可和 Fig. 4 合并。  
建议版式：单栏或与 decoder 合成双栏。

### 作用

这张图回答“encoder 怎么既嵌入 bit 又不改变行为分布”。它要支撑 Proposition 1 distribution preservation。

审稿人需要看到：

- candidate behaviors 先按 probability 排序；
- top-k gate 决定是否进入可嵌入区域；
- top-k 内做 even/odd interleaved split；
- probability values 只用于 sampling group mass；
- odd branch 才 consume message bit，zero-bit branch 是为了保持分布，不是缺陷。

### 预期内容

建议用一个具体 top-8 示例：

候选列表：

`rank 0:a`, `rank 1:b`, `rank 2:c`, `rank 3:d`, `rank 4:e`, `rank 5:f`, `rank 6:g`, `rank 7:h`

第一层 split：

- even ranks：`{a, c, e, g}`
- odd ranks：`{b, d, f, h}`

第二层继续对选中组 split，例如 odd group：

- even-within-group：`{b, f}`
- odd-within-group：`{d, h}`

旁边标出：

- group mass `S_0`, `S_1`
- `BinEnc` samples group according to mass
- only odd branch consumes one coded bit
- fixed DRBG budget：`\lceil log_2 k \rceil`

### 视觉要点

- 用树形结构比流程框更好。
- 每个叶子保留 rank index，别只画行为名。
- probability mass 用小条形或括号标注，不要把公式塞满图。
- 用一个小锁或 key 标识 DRBG/keyed randomness。

### 建议 caption

`Rank encoding over the top-k behavior list. The encoder uses probability mass to sample groups with the correct marginal distribution, while interleaved rank splits create a path that can later be decoded from ranks alone.`

## Figure 4: Rank-Only Decoder Path

当前位置：`fig:dec`，现在是伪代码框。  
优先级：P1，建议重画；可与 Fig. 3 合并。  
建议版式：单栏或方法双栏的右半边。

### 作用

这张图回答“verifier 为什么不需要 probability”。它支撑 Theorem 1 rank-preserving robustness。

审稿人需要看到：

- verifier 输入只有 selected behavior `b_hat_t` 和 top-k order `sigma'_t`；
- 找到 selected behavior 的 rank index `q`；
- rank index 的 parity path 决定哪些层产生 bit event；
- DRBG 只决定 bit value，不需要概率；
- 如果 selected behavior 不在 top-k，就是 erasure/no bits。

### 预期内容

继续使用 Fig. 3 的 top-8 示例。假设 selected behavior 是 rank 5 的 `f`：

- `q=5`
- binary/parity path：`5 odd -> 2 even -> 1 odd -> 0`
- odd levels produce two coded bits；
- even level produces no bit；
- output coded bits feed RLNC packet collector。

可画一个右侧小框：

`decoded coded bits -> packet matrix -> solve payload`

但 RLNC 不要画太复杂，只要表示 accumulation。

### 视觉要点

- decoder 侧不要出现 probability bars。
- 明确写 `No numeric probability`.
- 把 `q -> floor(q/2)` 的路径画成向上回溯或树路径。
- 用灰色分支表示未选路径，用高亮路径表示 selected rank path。

### 建议 caption

`Rank-only decoding. Given the selected behavior and the reconstructed top-k order, the verifier recovers the rank path and emits coded bits at odd branches without using any numeric probability values.`

## Figure 5: Exact Channel vs Rank-Only Channel Result Summary

当前状态：论文里没有这张图，当前由 Table 4 承担。  
优先级：P2，可选。  
建议位置：Evaluation 的 Rank-Only Verification 小节。

### 作用

这张图不是机制图，而是把 Table 4 的核心结果视觉化。它适合放在 rebuttal 或 camera-ready，如果主文版面允许，也可以加入正文。

它要传达一个对比：

- AgentMark-F exact channel 强；
- AgentMark-F top-10 rank-only collapse；
- AsymAgentMark-TK exact channel 稍弱；
- AsymAgentMark-TK top-10 保留更多信号。

### 预期内容

建议画两组 dataset panel：

- ALFWorld
- ToolBench

每个 panel 画 payload recovery bars：

- AgentMark-F exact
- AgentMark-F top-10
- Ours exact
- Ours top-10

如果空间够，在 bar 上方标 bit match，或用淡线表示 bit match。

### 视觉要点

- 这张图必须来自数据脚本生成，不建议真正手画。
- 重点突出 ALFWorld 上 `0.700 -> 0.014` 和 ours `0.532 -> 0.068`。
- ToolBench 作为低容量 regime 的补充，不要让它喧宾夺主。

### 建议 caption

`Exact-channel capacity does not transfer to rank-only verification. AgentMark-F has higher exact-channel recovery on ALFWorld, but its payload recovery collapses under top-10 rank-only verification, while the rank-path decoder retains signal.`

## Figure 6: Evidence Accumulation and Packet Scarcity

当前状态：论文里没有这张图，当前由 Proposition 2、pooled robustness tables 和 false-positive段落承担。  
优先级：P2，可选。  
建议位置：Discussion 或 Evaluation 的 Pooled Robustness 前。

### 作用

这张图解释为什么 strict single-trajectory recovery 低并不等于 channel 没信号。它对应 Proposition 2 和 pooled recovery。

适合在审稿人可能质疑“payload recovery 低”的时候使用。

### 预期内容

画一个概念图即可：

- single short trajectory：少量 decoded packets，`M < L`，strict recovery inconclusive；
- audit window / pooled trajectories：packet count accumulates，`sum M_i >= L`，RLNC recovery possible；
- rank noise / erasure 会减少 packet survival；
- false-positive control 仍由 pre-registered payload length `L` 决定。

### 视觉要点

- 不要画成“我们能无限 pooling 就一定成功”的感觉。
- 明确标注 pooled evidence 是 audit-window/corpus-level，不是单任务 attribution。
- 这张图更像解释图，不一定适合主文，如果版面紧张可以放 appendix 或 slide。

### 建议 caption

`Packet scarcity separates per-step channel signal from strict payload recovery. Short trajectories may decode too few independent RLNC packets for single-trajectory attribution, while audit-window pooling accumulates enough packets under a pre-registered claim.`

## 推荐最终取舍

### 主文最小组合

1. Fig. 1 System View
2. Fig. 2 Probability-Bin Instability
3. Fig. 3 Rank Encode/Decode 双栏合并图

这样正文只有三张手画图，但覆盖完整叙事：系统假设、失败机制、方法修复。

### 主文完整组合

1. Fig. 1 System View
2. Fig. 2 Probability-Bin Instability
3. Fig. 3 Rank Encoder
4. Fig. 4 Rank-Only Decoder
5. 可选 Fig. 5 Exact vs Rank-only result summary

如果论文页数允许，这是最舒服的结构。

### Appendix/Slides 组合

- Fig. 6 Evidence Accumulation 放 appendix 或答辩 slide。
- 当前 Table 4、Top-k ablation、erasure、rewrite、FPR 表格保留在正文，避免图表过载。

## 画图风格建议

- 使用统一术语：`full channel`, `rank-only channel`, `probability bin`, `rank path`, `coded packets`。
- 所有图都要避免“概率 decoder 看起来也能用 rank”的误导。AgentMark-F 一侧必须明确依赖 calibrated probabilities/probability bins。
- 图中公式越少越好，保留关键符号：`P_t`, `sigma_t`, `sigma'_t`, `b_hat_t`, `q`, `M >= L`。
- 颜色语义固定：
  - probability/full channel：蓝色；
  - rank-only/stable path：绿色；
  - missing/unavailable probability：灰色虚线；
  - failure/collapse/bin shift：红色或橙色。
- Caption 要直接说贡献，不要只描述图中元素。

