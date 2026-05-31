# Additional Experiments A-E Results

## A. Lemma 1 step-level counterfactual

AgentMark-F exact-probability decoding was compared with a top-k verifier view that keeps the selected top-k order but drops the tail and renormalizes probabilities. The selected behavior remains rank-stable whenever it is still in the top-k set; changes below are therefore probability-bin effects, not candidate-order effects. Bin-changed and bit-changed rates are conditional on selected-in-top-k; selected-dropped is measured over exact-decodable steps. This is a truncation-and-renormalization instance of Lemma 1, not an exhaustive test of all value perturbations.

| Dataset | Model | top-k | rank-stable steps | bin changed | bit changed | selected dropped |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| alfworld | deepseek | 2 | 3201 | 78.5% | 74.8% | 54.5% |
| alfworld | deepseek | 4 | 5119 | 56.8% | 51.3% | 27.3% |
| alfworld | deepseek | 10 | 6762 | 13.7% | 11.1% | 3.9% |
| alfworld | gemini-flash | 2 | 3129 | 72.1% | 67.9% | 67.5% |
| alfworld | gemini-flash | 4 | 4901 | 56.9% | 51.3% | 49.1% |
| alfworld | gemini-flash | 10 | 7328 | 39.6% | 34.9% | 23.9% |
| toolbench | deepseek | 2 | 257 | 68.9% | 68.1% | 50.8% |
| toolbench | deepseek | 4 | 392 | 52.6% | 43.6% | 24.9% |
| toolbench | deepseek | 10 | 518 | 4.6% | 3.7% | 0.8% |
| toolbench | gemini-flash | 2 | 299 | 59.5% | 54.5% | 45.3% |
| toolbench | gemini-flash | 4 | 417 | 35.7% | 30.9% | 23.8% |
| toolbench | gemini-flash | 10 | 542 | 11.3% | 7.7% | 0.9% |

## B. Prop. 2 fine rank-noise curve

The fine-grid rerun uses ToolBench, repeats=10, k in {3,5,10}, epsilon=0:0.05:0.5. Here the measured quantity is the one used by Prop. 2: whether a clean-decodable step changes its decoded rank path under adjacent swaps. The dashed line is an empirical envelope with c=0.404 in 1-(1-epsilon)^(c ceil(log2 n_t)), where n_t is the actual visible candidate count.

| Model | Split | Noise | k | eps=0 p_flip | eps=0.25 p_flip | eps=0.5 p_flip | eps=0.5 envelope | eps=0.5 bit flip |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deepseek | G1_instruction | adjacent_swap | 3 | 0.000 | 0.184 | 0.348 | 0.429 | 0.348 |
| deepseek | G1_instruction | adjacent_swap | 5 | 0.000 | 0.306 | 0.502 | 0.531 | 0.418 |
| deepseek | G1_instruction | adjacent_swap | 10 | 0.000 | 0.299 | 0.532 | 0.572 | 0.413 |
| gemini-flash | G1_instruction | adjacent_swap | 10 | 0.000 | 0.287 | 0.508 | 0.528 | 0.405 |

As a medium audit-window diagnostic, an 8-step DeepSeek/G1/top5 path-consistency window succeeds at 0.042 when epsilon=0.25. This avoids the all-pooled=1.0 and single-trajectory=0.0 saturation endpoints, but it is reported as path consistency rather than full RLNC payload recovery.

## C. Channel ladder

L2 top-8 and L4 top-4 were already present in the canonical non-robust artifact; the missing piece was the paper-facing ladder figure/table.

| Dataset | Method | L0 Ceff | L1 Ceff | L2 Ceff | L3 Ceff | L4 Ceff | L5 Ceff | L6 Ceff |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ALFWorld | AgentMark-F | 19.692 | 0.333 | 0.106 | 0.089 | 0.040 | 0.032 | 0.000 |
| ALFWorld | AsymAgentMark-TK | 7.707 | 1.000 | 0.606 | 0.364 | 0.131 | 0.053 | 0.000 |
| ToolBench | AgentMark-F | 0.248 | 0.009 | 0.000 | 0.000 | 0.004 | 0.000 | 0.000 |
| ToolBench | AsymAgentMark-TK | 0.053 | 0.050 | 0.032 | 0.010 | 0.009 | 0.000 | 0.000 |

## D. ALFWorld k* extension

ALFWorld rank logs contain 26963 decodable rank steps; max candidate count is 69, and steps with more than 20 candidates are 17782 (65.95%).

| top-k | Cnom | DSR | bit match | Ceff |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 8.161 | 0.006 | 0.558 | 0.046 |
| 4 | 12.113 | 0.013 | 0.601 | 0.164 |
| 6 | 12.113 | 0.028 | 0.642 | 0.372 |
| 8 | 13.276 | 0.048 | 0.670 | 0.690 |
| 10 | 13.276 | 0.064 | 0.707 | 0.954 |
| 20 | 13.469 | 0.313 | 0.863 | 4.511 |
| 30 | 13.469 | 0.464 | 0.922 | 6.712 |
| 40 | 13.486 | 0.523 | 0.939 | 7.560 |
| full | 13.486 | 0.531 | 0.942 | 7.693 |

## E. Cnom repeated-value audit

Cnom is `decoded_len_mean`: the mean proxy decoded bits per trajectory. Repeated neighboring values are expected when the actual visible candidate count saturates below the larger cutoff, because per-step decoded length is capped by the actual candidate count n rather than by the requested k. The audit found repeated settings but no Ceff arithmetic inconsistency.

- Repeated Cnom groups found: 94.
- Mechanism: if increasing k does not add visible candidates on most eligible steps, or if the selected/decodable set is unchanged, the actual-n cap keeps Cnom fixed. This matches the decoder accounting over actual candidate count n.

## Artifacts

- `lemma1_bin_instability_summary.csv`, `lemma1_bin_instability_steps.csv`
- `prop2_step_flip_summary.csv`, `prop2_step_flip_fit.json`, `prop2_medium_audit_window.csv`, `fig_prop2_rank_noise_fine.svg`
- `channel_ladder_main.csv`, `fig_channel_ladder_ceff.svg`
- `alfworld_topk_extended.csv`, `alfworld_topk_extended_audit.json`
- `cnom_repeated_value_audit.csv`, `cnom_candidate_saturation_explanation.csv`
