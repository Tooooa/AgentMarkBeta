# Data audit for the 0510 AsymMark-R results

This audit treats `/Users/local/AgentMarkBeta/output-0510` as the authoritative
experiment root. The older `output/asym_agentmark_tk/week2_postprocess` directory
is useful as draft lineage, but it should not be the primary evidence source for
new claims.

## Executive conclusion

The current data supports a scoped story:

- Rank watermarking preserves task utility on ALFWorld and ToolBench.
- Behavior-frequency divergence from Clean is comparable to AgentMark-F.
- The offline decoder proxy supports the channel-knowledge tradeoff: AgentMark-F
  is stronger with exact probabilities, while AsymMark-R retains more
  signal under Top-10 rank-only verification.
- Top-k ablation supports the direction that larger rank views carry more useful
  signal, especially on ALFWorld.
- Evidence-strength tables support strong bit-level channel evidence, but these
  are diagnostics and not positive attribution by themselves.

The current data does **not** support a stronger deployment-certification story:

- Strict single-trajectory RLNC payload recovery is materially lower for
  AsymMark-R than AgentMark-F, especially on ToolBench.
- Live cross-model Top-k re-querying, semantic prompt rewriting, empirical FPR
  trials, and the main robustness experiments are not complete in `output-0510`.
- The proxy `payload_recovery_rate` in `capacity_l0_l6_proxy.csv` and
  `topk_ablation.csv` is not strict RLNC recovery.

## Storyline fit

| Claim | Current evidence | Fit |
| --- | --- | --- |
| Utility is preserved | `utility_retention.csv`, `utility_main.csv` | Supported. ALFWorld Clean 80.04% vs AsymMark-R 78.58%; ToolBench Clean 75.65% vs AsymMark-R 77.06%. |
| Behavior distribution remains close to Clean | `behavior_jsd.csv`, `behavior_jsd_clean.csv` | Supported as a coarse JSD diagnostic. Do not claim chi-square or KS tests. |
| Exact probabilities favor AgentMark-F | `capacity_l0_l6_proxy.csv` payload-8 L0, plus strict RLNC table | Supported. Proxy: ALFWorld AgentMark-F 0.700 vs AsymMark-R 0.532. Strict global: AgentMark-F 55.58% vs AsymMark-R 24.83%. |
| Top-10 rank-only verification favors AsymMark-R over AgentMark-F | `capacity_l0_l6_proxy.csv` payload-8 L1 | Supported only as an offline proxy. ALFWorld AgentMark-F 0.014 vs AsymMark-R 0.068; ToolBench AgentMark-F 0.003 vs AsymMark-R 0.032. |
| Top-k improves recoverability | `topk_ablation.csv`, `topk_ablation_main.csv` | Supported as a proxy trend. ALFWorld payload proxy recovery rises from 0.55% at k=2 to 31.30% at k=20. ToolBench remains weak. |
| Strong statistical channel evidence exists | `evidence_strength/*`, `evidence_confidence_n50.csv` | Supported as bit-level diagnostics. At N=50: ALFWorld rank top10 match 95.50%, mean log10 p -11.850; ToolBench rank top10 match 100.00%, mean log10 p -6.556. |
| Strict payload attribution is strong | `rlnc_recovery_by_task.csv`, `strict_rlnc_recovery_global.csv` | Not supported for AsymMark-R. Global strict recovery is 24.83% overall, 34.85% on ALFWorld, and 1.94% on ToolBench. |
| Robustness experiments are complete | Not in canonical non-robust package; user says ongoing | Not supported. Keep robustness sections pending or clearly marked as old/proxy-only. |

## Data-processing findings

1. **Two payload-recovery meanings are currently in play.**
   - Strict recovery: `rlnc_recovery_by_task.csv` uses actual decoded packets and
     `DeterministicRLNC.decode(...)`; success means recovered payload exactly
     equals `11001101`.
   - Proxy recovery: `capacity_l0_l6_proxy.csv` and `topk_ablation.csv` come from
     `run_week2_postprocess.py`, where `decode_trajectory(...)` synthesizes bit
     matches using logged bit counts and channel-dependent match probabilities.
     `payload_recovered(...)` checks whether the first L synthetic decoded bits
     match the expected stream. This is useful for channel diagnostics but should
     not be described as end-to-end RLNC payload recovery.

2. **The proxy pipeline is intentionally modelled, not fully observed.**
   `step_decode_proxy(...)` uses formula-based match probabilities such as
   rank loss and noise rate. Therefore capacity proxy and top-k ablation results
   are controlled diagnostics, not direct decoder measurements under live
   verifier re-querying.

3. **Cell means and global rates answer different questions.**
   `strict_rlnc_recovery_main.csv` averages model/split cells. The sample-weighted
   global rates are in `strict_rlnc_recovery_global.csv`:
   - all A3/A4: 1901/4728 = 40.2073%
   - AgentMark-F: 1314/2364 = 55.5838%
   - AsymMark-R: 587/2364 = 24.8308%
   Use global rates when writing "overall/global recovery".

4. **The canonical artifact names changed.**
   `paper.tex` Appendix E still maps results to historical names such as
   `stage_b_1_1_capacity_proxy.csv` and `stage_c_3_1_rank_noise.csv`. The current
   canonical non-robust package uses:
   - `utility_main.csv`, `utility_by_cell.csv`
   - `behavior_jsd_clean.csv`
   - `strict_rlnc_recovery_main.csv`, `strict_rlnc_recovery_global.csv`
   - `topk_ablation_main.csv`
   - `capacity_proxy_payload8_logged_channels.csv`
   - `evidence_confidence_n50.csv`
   - `evidence_threshold_payload32_alpha01.csv`

5. **The logged L5/L6 labels are not the original design's L5/L6.**
   In `capacity_l0_l6_proxy.csv`, the channels are exact, top10, top8, top6,
   top4, top2, and selected-only. They should not be described as cross-model
   Top-k or noisy-rank experiments.

6. **Current evidence-strength claims should use current values.**
   The paper text should avoid saying rank-decoding N=50 always gives
   log10 p between -15.05 and -11.95. Current aggregated values are:
   - ALFWorld AsymMark-R top10: -11.850
   - ToolBench AsymMark-R top10: -6.556

## What likely does not need rerun

- Utility retention on ALFWorld and ToolBench.
- Behavior JSD, if framed as a coarse empirical distribution diagnostic.
- Top-k ablation as a proxy diagnostic.
- Evidence confidence/threshold analysis as a bit-level diagnostic.
- Strict RLNC recovery as a descriptive baseline of current trajectories.

## What should be rerun or completed before final submission

1. **Robustness Stage 3.1/3.2.**
   Finish ranking-noise and erasure/degraded-channel experiments in the canonical
   `output-0510` flow. Current `paper.tex` includes rank-noise and erasure tables,
   but the user has marked robustness as ongoing and the paper-ready non-robust
   package excludes them.

2. **Live cross-model Top-k re-querying.**
   This is important if the paper motivates verifier-side API/model mismatch.
   The current proxy isolates probability-vs-rank decoding but does not prove
   that DeepSeek and Gemini reconstruct each other's ranks in practice.

3. **Semantic prompt rewriting.**
   Missing from the current canonical data. Keep as future work unless completed.

4. **Empirical false-positive stress test.**
   The analytic `2^-L` claim is fine as a security threshold, but `paper.tex`
   currently says there is a postprocessed artifact using 1000 random payload
   trials per clean trajectory. That artifact is not present in the current
   `output-0510` non-robust package.

5. **End-to-end strict Top-k/RLNC recovery under verifier views.**
   If the paper wants to claim payload attribution under rank-only verification,
   rerun or implement a direct decoder table that recovers RLNC payloads under
   exact/top-k/selected-only views rather than relying on the synthetic proxy.

6. **Longer ToolBench or aggregation strategy.**
   ToolBench strict recovery is very low: AsymMark-R is 14/720 = 1.9444%.
   Most failures are insufficient packets. A deployment-style story for ToolBench
   likely needs longer audit windows, task aggregation, adaptive step selection,
   larger k, or a smaller/stronger coding configuration.

## Recommended paper rewrite direction

Frame the current evidence as:

> The 0510 corpus supports partial-channel feasibility: rank-only decoding
> preserves useful bit-level channel signal while maintaining utility and
> distributional similarity. However, strict single-trajectory payload recovery
> remains limited, especially in low-entropy/short ToolBench traces. Therefore
> the current result is a diagnostic weak-asymmetry evaluation, not deployment
> certification.

Avoid:

- claiming production-grade attribution from the proxy tables;
- calling proxy `payload_recovery_rate` strict RLNC recovery;
- presenting robustness, cross-model, semantic rewrite, or empirical FPR results
  as complete until their canonical artifacts exist.
