# Method (Draft v5 — S&P Style, aligned with ACL predecessor)

> **文件说明**: 第五稿。修正了第四稿中"编码端与 AgentMark-F 相同、只有解码端不同"的错误叙事。实际上 encoder 和 decoder 都是全新设计，encoder 的二叉树结构是 decoder 能做非对称解码的前提。同时修正了 BinEnc 描述（0 或 1 bit）、对比表 PRG sync 等技术细节。
>
> **命名体系**：
>
> - **AgentMark**: ACL 前作的 general paradigm（Huang et al. 2026）
> - **AgentMark-F**: ACL 的具体实例化（FDPSS-style, 对称方案）
> - **AsymMark**: 本文的 general paradigm（非对称 AgentMark）
> - **AsymMark-R**: 本文的具体实例化（Top-k rank-based binary splitting）
>
> **与 ACL 前作的核心区别**：
>
> - ACL (AgentMark-F): 对称方案，encoder/decoder 都需要精确概率分布 $P_t$
> - Ours (AsymMark-R): 弱非对称方案，encoder 需要 $P_t$，decoder 仅需 rank ordering $\sigma_t$
> - 新的威胁模型：adversary 可以扰动概率值（temperature/quantization/fine-tuning）

---

## 3. Problem Formulation

> **写作策略**：Section 3 的 notation 和 channel model 直接沿用 ACL，只补充新增的 rank-consistency 假设和扩展的 threat model。

We adopt the planning-time behavior channel formulation of Huang et al. (2026). At each step $t$, the agent induces a distribution $P_t$ over a finite behavior set $\mathcal{B}_t$ and selects $\hat{b}_t \leftarrow \mathsf{Enc}(P_t, r_t)$, where $r_t$ is keyed pseudorandomness derived from a shared secret $K_{\text{sh}}$ and step context. The verifier recovers the payload via $\hat{m} \leftarrow \mathsf{Dec}(\{(\hat{b}_t, \cdot)\}_{t \in I})$, where $I \subseteq \{1, \ldots, T\}$ is the observed index set.

We retain the distribution-preservation requirement (Eq. 1 of Huang et al., 2026):

$$
\Pr[\hat{b}_t = b] = P_t(b), \quad \forall b \in \mathcal{B}_t, \; \forall t.
$$

### 3.1 Extended Threat Model

AgentMark-F (Huang et al., 2026) assumes the verifier has access to the *exact* per-step distribution $P_t$ used during encoding. In practice, this assumption is fragile: the verifier may re-query the agent to reconstruct $P_t$, but temperature scaling, quantization, model updates, or API-side post-processing can shift the returned probability values. We formalize this as a **distribution-perturbation adversary**:

**Definition 1 (Distribution perturbation).** The adversary applies a per-step transformation $P_t \mapsto P_t'$ such that probability values change but the rank ordering is preserved: $\text{argsort}(P_t) = \text{argsort}(P_t')$.

This is strictly stronger than the erasure/truncation adversary of Huang et al. (2026): step erasure removes entire steps, while distribution perturbation corrupts the *content* of surviving steps. AgentMark-F's differential recombination relies on exact probability values for bin construction; under distribution perturbation, the encoder and decoder construct different bins, breaking synchronization and causing decoding failure (we verify this empirically in Section 5).

### 3.2 Rank-Consistency Assumption

We introduce the following relaxation of the exact-distribution requirement:

**Assumption 1 (Rank consistency).** The decoder observes a distribution $P_t'$ such that $\text{argsort}(P_t') = \text{argsort}(P_t)$, i.e., the relative ordering of behaviors is preserved.

This assumption is empirically well-supported: rank ordering is stable under temperature scaling ($p_i' = p_i^{1/T}/Z$ is monotonic), minor fine-tuning, and quantization, all of which predominantly scale magnitudes while preserving relative order (we validate this in Section 5, Table X).

**Goal.** Design an encoder $\mathsf{Enc}$ and decoder $\mathsf{Dec}$ such that: (1) distribution preservation holds as before, (2) the decoder requires only $\text{argsort}(P_t')$—not the exact values—enabling correct decoding under Assumption 1.

---

## 4. AsymMark: Asymmetric Behavioral Watermarking

We propose **AsymMark**, an *asymmetric* extension of the AgentMark paradigm. While both AsymMark and AgentMark-F share the distribution-preservation goal, AsymMark **redesigns both the encoder and decoder**: the encoder replaces differential recombination with a binary partition tree over rank-sorted behaviors, and the decoder exploits the tree's structural property to extract bits from rank positions alone, without probability values. This co-design is essential—AgentMark-F's differential recombination encodes bits into probability-dependent bins that cannot be recovered from rank information alone, so asymmetric decoding requires a fundamentally different encoding scheme.

We present a concrete instantiation, **AsymMark-R**, which operates on the top-$k$ ranked behaviors via recursive binary splitting. The "-T" denotes top-$k$ rank-based encoding: the encoder restricts attention to the $k$ highest-probability behaviors, embeds bits within this subset, and falls back to standard sampling for tail behaviors. This top-$k$ focus both concentrates embedding capacity on the most informative actions and aligns naturally with common inference-time truncation strategies.

**Core insight.** The binary partition tree maps each behavior to a unique leaf via interleaved splitting. The path from root to leaf is fully determined by the behavior's rank in the sorted ordering—the rank expressed in binary *is* the path. This structural correspondence is what enables asymmetric decoding: the encoder uses probability values to make distribution-preserving group selections (via $\mathsf{BinEnc}$), while the decoder reads the same path back from the rank alone.

### 4.1 Overview

> **[Figure 2 规划]**：与 ACL Figure 2 对称的布局。左侧 Agent Workflow 保持一致（沿用 ACL 的 agent loop 示意）。右侧 AsymMark-R 替换原有的 DiffRecombine + CyclicShift 模块，改为：Sort by rank → Top-k selection → Binary Partition Tree → BinEnc per level。底部新增一个对比框："Decoder requires: AgentMark-F needs $P_t$ (exact) vs. AsymMark-R needs $\sigma_t$ (rank only)"，用颜色区分。

Figure 2 illustrates AsymMark-R within the agent workflow. At each round $t$:

1. The agent elicits an explicit behavior distribution $P_t$ over $\mathcal{B}_t$ (identical to AgentMark-F).
2. The encoder sorts $\mathcal{B}_t$ by descending probability, selects the top-$k$ behaviors, and embeds bits via recursive binary splitting over this subset ($\mathsf{RankEnc}$). If the sampled action falls outside the top-$k$, no bits are embedded for that step.
3. The decoder, given only the selected behavior $\hat{b}_t$ and the rank ordering $\sigma_t$, extracts bits by decomposing the rank of $\hat{b}_t$ within the top-$k$ set into binary ($\mathsf{RankDec}$).

The keyed pseudorandomness mechanism is identical to AgentMark-F (Eq. 9 of Huang et al., 2026): $K_t \leftarrow H(K_{\text{sh}} \| t \| h_t)$, and a DRBG $\mathcal{G}$ seeded by $K_t$ produces the per-step random stream. We adopt the Meteor-style HMAC-SHA512 DRBG [Kaptchuk et al., 2021] (construction details in Appendix A).

### 4.2 Rank-Based Distribution-Preserving Encoding

AsymMark-R replaces AgentMark-F's differential recombination with a binary partition tree over the top-$k$ rank-sorted distribution. The construction has two levels: a binary/Users/local/AgentMarkBeta/docs/drafts/method-section-draft.md encoding primitive ($\mathsf{BinEnc}$) and a recursive wrapper ($\mathsf{RankEnc}$).

#### Binary Encoding Primitive

At each tree level, the encoder faces a binary choice between two groups of behaviors. $\mathsf{BinEnc}$ attempts to embed one message bit into this choice while *exactly preserving the marginal distribution*. It succeeds (embedding 1 bit) when the low-mass group is selected, and defers (embedding 0 bits) when the high-mass group is selected—in which case the same message bit is retried at the next level.

Given group masses $S_{\text{hi}} \geq S_{\text{lo}}$ (with $S = S_{\text{hi}} + S_{\text{lo}}$), a message bit $m$, and pseudorandom $r \leftarrow \mathcal{G}$:

$$
r_m = (r \cdot S + \tfrac{1}{2} S \cdot m) \bmod S
$$

The encoder selects the high-mass group if $r_m < S_{\text{hi}}$ (embedding 0 bits), or the low-mass group otherwise (embedding 1 bit). Distribution preservation follows from the uniform distribution of $r$ (proof in Appendix B).

#### Recursive Encoding with Top-$k$ Selection

> **[Figure 3 规划]**：5-action 示例，与 ACL 的 differential recombination 示例并排对比。左列标 "AgentMark-F: DiffRecombine → Bins → CyclicShift"，右列标 "AsymMark-R: Top-k → Sort → Binary Partition Tree"。底部 highlight：同一个 action 被选中后，AgentMark-F 解码需要精确概率重建 bin，AsymMark-R 解码只需 rank 位置。

**Algorithm 1: AsymMark-R $\mathsf{Encode}$ (one step)**

```
Require: P_t over B_t, context (t, h_t), shared secret K_sh,
         payload M, pointer ℓ, top-k parameter k
Ensure:  selected behavior b̂_t, embedded bits s_t, updated ℓ

1:  K_t ← H(K_sh ∥ t ∥ h_t);  G ← DRBG(K_t)
2:  σ ← argsort(P_t, descending)
3:  S_top ← Σ_{i=1}^{k} P_t(σ(i))                ▷ top-k probability mass
4:  if Uniform(0,1) ≥ S_top:                       ▷ falls into tail (independent of G)
5:      b̂_t ← sample from tail {σ(k+1), ...}; return b̂_t, ∅, ℓ
6:  D ← {(σ(i), P_t(σ(i))/S_top) : i = 1..k}     ▷ top-k normalized dist
7:  sync ← ⌈log₂ k⌉
8:  while |D| > 1 and ℓ < |M|:
9:      D_even ← {D[i] : i even};  D_odd ← {D[i] : i odd}
10:     (group, b) ← BinEnc(M[ℓ], (Σ D_even, Σ D_odd), G.next())
11:     ℓ ← ℓ + b;  sync ← sync − 1;  D ← D_group
12: for i = 1 to sync: G.next()                    ▷ PRG synchronization
13: b̂_t ← D[0];  s_t ← M[ℓ_old : ℓ]
14: return b̂_t, s_t, ℓ
```

**Top-$k$ selection (lines 3–6).** Rather than encoding over the full behavior set, AsymMark-R restricts to the $k$ highest-probability behaviors. This design is motivated by three considerations: (1) *rank stability*—the top-$k$ ranks are the most robust to probability perturbation, since the probability gap between top-ranked behaviors is typically larger than among tail behaviors; (2) *inference alignment*—many agent deployments already apply top-$k$ truncation, making this a natural fit; (3) *embedding concentration*—the top-$k$ behaviors carry the majority of probability mass, so restricting to them sacrifices little capacity while improving robustness. When $k = |\mathcal{B}_t|$, AsymMark-R reduces to full-distribution encoding.

**Interleaved partition.** At each level, we partition the sorted distribution into even-indexed and odd-indexed elements. Since the distribution is sorted descending, the even-indexed group (containing ranks 0, 2, 4, ...) always has total mass $\geq$ the odd-indexed group (ranks 1, 3, 5, ...). This interleaving ensures approximately balanced group masses, maximizing the per-level embedding opportunity. A naive top-half/bottom-half split would create a dominant high-mass group, causing $\mathsf{BinEnc}$ to almost always select it with near-zero embedding rate.

**PRG synchronization ($\mathsf{rt\_sync}$).** The DRBG advances by exactly $\lceil \log_2 k \rceil$ calls per step regardless of early termination (line 12). This fixed-budget invariant is critical: without it, the decoder cannot determine how many DRBG values were consumed, causing stream desynchronization for all subsequent steps. This mechanism also enables the decoder to operate without knowing the message length—a property not available in AgentMark-F's variable-length cyclic shift encoding.

### 4.3 Weakly Asymmetric Decoding

The central contribution of AsymMark is a **co-designed encoder–decoder pair** where the encoder's binary partition tree structure directly enables a decoder that requires strictly less information. The encoder's tree design is not incidental—it is the structural prerequisite that makes asymmetric decoding possible.

**Key observation.** The binary partition tree maps each behavior to a unique leaf. The path from root to a behavior's leaf is fully determined by the behavior's rank within the top-$k$ set: at each level, membership in the high-mass or low-mass group corresponds to whether the current index is even or odd—i.e., the parity of the rank at that level. Therefore, the rank in binary *is* the encoding path. This property is unique to the interleaved binary partition; AgentMark-F's differential bins do not admit such rank-based path recovery.

**Algorithm 2: AsymMark-R $\mathsf{Decode}$ (one step)**

```
Require: b̂_t, rank ordering σ_t, context (t, h_t), shared secret K_sh,
         top-k parameter k
Ensure:  extracted bitstring s_t

1:  K_t ← H(K_sh ∥ t ∥ h_t);  G ← DRBG(K_t)
2:  rank ← position of b̂_t in σ_t[1..k] (0-indexed)
3:  if b̂_t ∉ top-k of σ_t: return ∅           ▷ tail action, no bits
4:  sync ← ⌈log₂ k⌉
5:  R ← [G.next() for _ in range(sync)]
6:  s_t ← "";  level ← 0
7:  while rank ≠ 0:
8:      if rank mod 2 = 1:                      ▷ odd-indexed group → bit embedded
9:          s_t ← s_t ∥ ('1' if R[level] < 0.5 else '0')
10:     rank ← ⌊rank / 2⌋;  level ← level + 1
11: return s_t
```

**Note the asymmetry**: Algorithm 1 (encoder) accesses the full distribution $P_t$ to compute group masses for $\mathsf{BinEnc}$ (line 10). Algorithm 2 (decoder) accesses only the rank ordering $\sigma_t$ (line 2)—probability values never appear. The decoder only needs to know which position (rank) the selected behavior occupies within the top-$k$ set.

> **Theorem 1 (Weak asymmetry).** Let $P_t$ and $P_t'$ be distributions over $\mathcal{B}_t$ with $\text{argsort}_{k}(P_t) = \text{argsort}_{k}(P_t')$ (i.e., the top-$k$ rank ordering is preserved). For any behavior $\hat{b}_t$ and DRBG state $\mathcal{G}$:
>
> $$
> \mathsf{Decode}(\hat{b}_t, \text{sort}(P_t), \mathcal{G}) = \mathsf{Decode}(\hat{b}_t, \text{sort}(P_t'), \mathcal{G})
> $$

*Proof.* $\mathsf{Decode}$ accesses $P_t$ solely through the top-$k$ ordering $\sigma_t = \text{argsort}_k(P_t)$. Since this ordering is preserved, the rank of $\hat{b}_t$ within the top-$k$ set is identical under both distributions. The DRBG sequence depends only on $(K_{\text{sh}}, t, h_t)$, not on probability values. $\square$

### 4.4 Comparison with AgentMark-F

Both AgentMark-F and AsymMark-R are distribution-preserving instantiations of the AgentMark paradigm. They differ in the decomposition strategy, the decoder information requirement, and the resulting robustness profile:

|                         | AgentMark-F (Huang et al., 2026)           | AsymMark-R (Ours)                               |
| ----------------------- | ------------------------------------------ | ---------------------------------------------------- |
| **Decomposition** | Differential recombination → uniform bins | Top-$k$ rank-sorted binary partition tree          |
| **Encoder input** | $P_t$ (exact probabilities)              | $P_t$ (exact probabilities)                        |
| **Decoder input** | $P_t$ (exact probabilities)              | $\sigma_t$ (top-$k$ rank ordering only)          |
| **Bits/step**     | Variable, depends on bin sizes             | $\leq \lceil \log_2 k \rceil$                      |
| **PRG sync**      | Fixed 2 calls/step (implicit)              | Explicit fixed budget $\lceil \log_2 k \rceil$     |
| **Robustness**    | Erasure/truncation (via RLNC)              | Erasure + distribution perturbation                  |
| **Vulnerability** | Probability perturbation breaks bin sync   | Rank-swap attacks (within top-$k$) break rank sync |

**When to prefer which.** AgentMark-F achieves higher embedding rates in controlled environments where exact $P_t$ is available at decode time (e.g., the embedder and verifier share the same API and configuration). AsymMark-R is preferred when the verifier cannot guarantee exact $P_t$—the common case in open-world deployments where agents are re-served, fine-tuned, or accessed through different API configurations. The top-$k$ restriction further improves robustness by focusing on the most rank-stable behaviors.

**Compatibility with RLNC.** AsymMark-R is fully compatible with the RLNC erasure coding layer of AgentMark-F. The per-step embedded bits $s_t$ from $\mathsf{Encode}$ can serve as RLNC coded packets in the same way as AgentMark-F's cyclic-shift output (Section 4.3 of Huang et al., 2026).

### 4.5 Security Properties

AsymMark-R achieves the same security guarantees as AgentMark-F, through a different construction:

**Distribution preservation.** $\mathsf{BinEnc}$ with uniform message bits produces a marginal that exactly matches $P_t$ over the top-$k$ set (Proposition 1; proof in Appendix B). Combined with the probability-proportional tail fallback (Algorithm 1, line 4–5), the overall marginal matches $P_t$ across all behaviors. Both AsymMark-R and AgentMark-F satisfy the same distribution-preservation property (Eq. 1), but through entirely different mechanisms: AgentMark-F via differential recombination over probability-dependent uniform bins, AsymMark-R via recursive $\mathsf{BinEnc}$ over a rank-sorted binary partition tree.

**Undetectability.** Under the PRF assumption on HMAC-SHA512, the DRBG output is computationally indistinguishable from uniform random bits, making the watermarked behavior sequence indistinguishable from unwatermarked sampling. This follows directly from the Meteor DRBG security argument [Kaptchuk et al., 2021] and the FDPSS framework [Liao et al., 2025].

**New: Perturbation robustness.** By Theorem 1, AsymMark-R additionally guarantees correct decoding under any distribution perturbation that preserves the top-$k$ rank ordering—a property that AgentMark-F does not possess. The top-$k$ restriction strengthens this guarantee: the probability gaps among the most dominant behaviors are typically larger, making their ranks more resistant to perturbation. We quantify this boundary (i.e., the minimum probability gap required for top-$k$ rank stability under temperature scaling and quantization) in Section 5.

---

> **附录规划 (Appendix Roadmap):**
>
> - **Appendix A**: Meteor DRBG construction details (HMAC-SHA512 reseed, bit extraction)
> - **Appendix B**: Distribution preservation proof (BinEnc → RankEnc induction, including top-$k$ + tail decomposition)
> - **Appendix C**: Embedding rate analysis — $\mathbb{E}[\text{bits/step}]$ as function of $k$ and $H(P_t)$
> - **Appendix D**: Top-$k$ rank stability analysis — minimum probability gap for rank preservation under temperature scaling, quantization, and fine-tuning
> - **Appendix E**: Formal comparison with AgentMark-F under distribution perturbation (theoretical + empirical)
> - **Appendix F**: RLNC integration details (inherited from AgentMark-F)
> - **Appendix G**: Full-distribution mode ($k = |\mathcal{B}_t|$) as special case

> **TODO for next revision:**
>
> - [ ] 画 Figure 2 (System Overview, with AgentMark-F vs AsymMark-R decoder comparison)
> - [ ] 画 Figure 3 (Top-k Binary Partition Tree 示例, side-by-side with differential recombination)
> - [ ] 补充 tie-breaking 讨论（概率相等时 rank 不稳定）
> - [ ] 确认 Section 3 与 ACL paper 的 notation 完全一致
> - [ ] 与 Related Work 中的 Meteor, SWEET, DiPmark, FDPSS 做显式区分
> - [ ] 确认 RLNC 整合层的细节是否需要在正文展开
> - [ ] 讨论 $k$ 的选取策略（固定 $k$ vs. 自适应 $k$ based on probability gap）
