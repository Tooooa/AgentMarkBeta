# AsymAgentMark-TK 论文故事线梳理

## 一句话主线

这篇论文不应被叙述成“又一个 agent 水印”，而应被叙述成“把 AgentMark 从精确概率同构的对称验证，推进到只需 top-k 排名知识的弱非对称行为溯源”。核心卖点是：在不改变 agent 行为边际分布的前提下，让验证端从“必须复现每步概率值”降级为“只需复现候选行为排名”。

## 读《From Symmetry toward Weak Asymmetry》的关键启发

佛非对称论文提出的核心概念是 weakly asymmetric steganography：发送端拥有完整条件分布，接收端只有部分信道知识。它把传统两端模型补齐成三档：

| 模型 | 发送端知识 | 接收端知识 | 典型问题 |
| --- | --- | --- | --- |
| Symmetric steganography | 完整条件分布 | 完整条件分布 | 高容量，但要求双方概率值一致 |
| Fully asymmetric steganography | 完整条件分布 | 无信道知识 | 接收端轻，但容量极低 |
| Weakly asymmetric steganography | 完整条件分布 | 部分信道知识 | 利用排名、阈值等结构信息换取容量与鲁棒性 |

论文的形式化抓手是 knowledge function `f(D)`：接收端不直接拿到分布 `D`，只拿到某个函数输出。二元字母表里可以是阈值知识，通用字母表里可以是概率排序 `rank(D)` 或 top-k 局部排序。它的 rank 构造使用按奇偶位递归划分的二叉树：发送端用概率质量保证分布保持，接收端只用符号排名恢复路径。这个结构与 AgentMark 当前 rank 方法天然对齐。

对 AgentMark 最重要的启发有三点：

1. “部分知识”不是工程上的缺失，而是可以被形式化并利用的验证接口。
2. Rank 不是 heuristic robustness trick，而是一个可证明的 weak-asymmetric decoder sufficient statistic。
3. Top-k 不是简单裁剪，而是 partial-rank knowledge 的自然实例：验证端只复现最有信号、也最稳定的候选行为排序。

## AgentMark 与 rank 方法的差异

AgentMark-F 的故事是：LLM agent 每步诱导一个行为分布 `P_t`，水印采样器必须保持 `Pr[\hat b_t=b]=P_t(b)`，否则长期任务效用会被水印扰动。它用 differential recombination 和 cyclic shift 在概率分布上切 bin，然后嵌入多 bit。这个方案的优势是 exact-channel 下容量高；弱点是 decoder 也必须重建相同的 `P_t` 和相同的 bin 边界。

Rank 方法，也就是当前 `algorithm="rank"` 的 AsymAgentMark-TK，改变的是编解码结构本身，而不是只改 decoder。代码路径是：

- `agentmark/core/watermark_sampler.py` 中的 `Dist`、`BinEncStep`、`RankEncStep`、`RankDecStep`；
- `sample_behavior_rank` 与 `rank_based_decoder` 作为 SDK 适配接口；
- `derive_contextual_watermark_key` 和 HMAC-SHA512 DRBG 提供每步伪随机流；
- `rt_sync` 固定每步 DRBG 消耗，避免 zero-bit 分支造成后续去同步。

关键技术差异如下：

| 维度 | AgentMark-F | AsymAgentMark-TK |
| --- | --- | --- |
| 编码结构 | 概率差分重组 + cyclic shift | top-k 排名排序 + 奇偶递归二叉树 |
| 发送端输入 | 完整 `P_t` | 完整 `P_t` |
| 验证端输入 | 完整且数值一致的 `P_t` | top-k ranking `σ_t` |
| 分布保持 | 由 probability-dependent bins 保证 | 由 top/tail gate + BinEnc 递归归纳保证 |
| 容量取向 | exact-channel 下更高 | 牺牲部分容量换 rank-only 可解码 |
| 鲁棒边界 | 缺步可由 RLNC 吸收；概率扰动会破坏 bin | 概率值扰动不影响；top-k rank swap 会破坏 |

因此论文不能写成“AgentMark-F encoder 不变，decoder 只看 rank”。正确说法是：rank 方法重设计了 encoder/decoder pair；encoder 的二叉树结构是 decoder 能从 rank 解码的必要条件。

## A 会叙事骨架

### 1. 问题开场：Agent provenance 需要水印行为，而不是只水印文本

LLM agent 的关键产物是 trajectory：工具调用、子目标选择、环境动作、社交行为，而不是最终文本。Token watermark 即使可靠，也可能在工具调用或结构化行动后丢失载体。AgentMark 已经提出行为水印，但它的对称解码假设太强。

### 2. Gap：真实验证端经常没有精确概率

验证端可能只能拿到 top-k API、四舍五入 logits、模型更新后的概率、低精度推理结果、代理模型重查询结果。很多情况下，概率值变了，但高概率行为的排序仍较稳定。AgentMark-F 的 differential bins 依赖概率 gap；概率值一变，bin 边界就变，bit 解释会错。

### 3. Insight：把“概率值一致”降级为“排名一致”

弱非对称隐写给出理论语言：发送端完整信道，接收端部分信道知识。Agent 行为信道里最自然的部分知识就是 top-k rank。于是本文的 research question 是：

> Can behavioral watermarking preserve attribution signal when the verifier reconstructs only the top-k rank order, not the exact behavior probabilities?

### 4. Method：co-designed rank encoder/decoder

方法段的重点顺序建议如下：

1. 先说 distribution preservation 是硬约束，因为 agent 行为漂移会影响任务成功。
2. 引入 top/tail gate：以 top-k 总质量进入可嵌入区域，否则按 tail 分布采样且不嵌 bit。
3. 在 top-k 内按概率降序排序，并递归做 even/odd interleaved split。
4. 每个节点用 `BinEnc`：进入低质量/odd 分支才消耗一个 bit，进入高质量/even 分支不消耗 bit。
5. Decoder 只拿 selected behavior 的 rank，反复看 rank parity；odd 分支对应曾经嵌入 bit，bit 值由同一 DRBG 值判定。
6. `rt_sync` 强制每步消耗 `ceil(log2 k)` 个随机数，保证编码端和解码端跨步同步。
7. RLNC 不作为新贡献，而作为继承 AgentMark 的 erasure-tolerant payload layer：rank decoder 产出 coded bits，RLNC 负责足够多独立方程后的 payload recovery。

### 5. Security/claim：三层边界要说清

- Distribution preservation：top/tail gate 和递归 BinEnc 共同保证边际分布仍是 `P_t`。
- Weak asymmetry：如果 `argsort_k(P_t)=argsort_k(P'_t)`，rank decoder 的输出完全相同。
- False positive：严格归属必须绑定预注册 key/payload，短 8-bit 表只能作为 channel diagnostic，不能宣称生产级身份认证。

### 6. Evaluation：不要过度声称，强调 tradeoff

现有结果最适合支撑“partial-channel feasibility”，而不是“最终部署认证”：

- Utility：rank 水印在 ALFWorld/ToolBench 上与 clean/AgentMark-F 接近。
- Stealth/JSD：行为分布相对 clean 没有明显异常。
- Capacity proxy：exact-channel 下 AgentMark-F 更强；rank-only 下 AgentMark-F collapse，AsymAgentMark-TK 保留信号。
- Top-k ablation：k 越大容量越高，但 rank 稳定风险也更高。
- Rank noise/erasure：明确边界是 rank swap 和短轨迹方程不足。

最强 A 会表达是：本文不是声称 rank 水印全面优于 AgentMark-F，而是提出一个新的验证知识维度，并在该维度上给出更合适的构造。

## Related Work 写法定位

推荐 related work 分成五段：

1. **Token-level LLM watermarking**：KGW、SynthID、robust distortion-free watermark 等，强调它们处理文本 token，不处理行为轨迹。
2. **Behavior-level agent watermarking**：Agent Guide、AgentMark、Sequential Behavioral Watermarking。这里要承认它们都是 agent 行为水印，但区分：Agent Guide/SeqWM 更偏检测统计或转移结构，AgentMark-F 是分布保持的直接前作，我们的贡献是 verifier channel knowledge 的降级。
3. **Provably secure steganography**：Hopper、Meteor、undetectable steganography、SparSamp 等，强调分布保持与隐写安全传统。
4. **Weakly asymmetric steganography**：佛非对称论文是理论根基；我们不是重复 token/channel 构造，而是把 partial channel knowledge 移到 agent behavior channel。
5. **Erasure coding and partial logs**：RLNC 是继承的恢复层，不是本文主要创新；本文主要创新是给 RLNC 提供 rank-only step decoder。

调研到的关键一手来源：

| 主题 | 参考 |
| --- | --- |
| Meteor | https://dl.acm.org/doi/10.1145/3460120.3484755 |
| KGW watermark | https://proceedings.mlr.press/v202/kirchenbauer23a.html |
| SynthID-Text | https://www.nature.com/articles/s41586-024-08025-4 |
| Robust distortion-free watermark | https://openreview.net/forum?id=FpaCL1MO2C |
| Agent Guide | https://arxiv.org/abs/2504.05871 |
| Sequential Behavioral Watermarking | https://arxiv.org/abs/2605.11036 |
| ToolLLM/ToolBench | https://arxiv.org/abs/2307.16789 |
| ALFWorld | https://openreview.net/forum?id=0IOX0YcCdTn |

## 推荐标题与摘要角度

标题建议保留：

> AsymAgentMark-TK: Weakly Asymmetric Behavioral Watermarking for LLM Agents

摘要第一句就要把载体讲清楚：agent provenance must cover tool calls, subgoal choices, and embodied actions, not only text. 第二段写 rank-only verifier。第三段给结果，但必须标注 current postprocessed/offline proxy，避免 reviewers 抓“8-bit payload 不够生产认证”的漏洞。

## 自查结论

按 A 会标准，目前叙事已经具备一个清晰 novelty axis：**verifier channel knowledge**。它不是简单组合 AgentMark 与 rank stego，而是将弱非对称隐写中的 partial channel knowledge 形式化迁移到 LLM agent 行为信道，并给出与 AgentMark-F 编解码结构不同、可证明分布保持且 rank-only 可解码的构造。

仍需补强的实验风险是 live end-to-end RLNC recovery 和 cross-model rank reconstruction。当前稿件应诚实定位为 postprocessed channel diagnostics + partial-channel feasibility；只要不把 proxy 表夸成生产认证，这条故事线已经接近 A 会可接收叙事。
