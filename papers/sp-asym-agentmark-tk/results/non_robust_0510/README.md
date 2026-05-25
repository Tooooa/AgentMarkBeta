# Paper-ready non-robustness results for output-0510

- Source root: `/Users/local/AgentMarkBeta/output-0510`
- Scope: ALFWorld and ToolBench; OASIS is not included in the 0510 artifact.
- Excluded: ongoing robustness experiments 3.1 ranking noise, 3.2 erasure/degraded-channel payload recovery, 3.3 semantic rewriting, and 3.4 empirical FPR.
- Included: trajectory completeness, utility, behavior JSD, strict RLNC payload recovery, top-k ablation, capacity proxy, and evidence strength.

## Recommended paper usage

- Use `utility_main.csv` and `utility_by_cell.csv` for the utility-retention table.
- Use `strict_rlnc_recovery_main.csv` as the main bit-exact payload recovery result.
- Use `strict_rlnc_recovery_global.csv` when reporting sample-weighted global recovery rates.
- Use `topk_ablation_main.csv` for the Top-k ablation figure/table.
- Use `evidence_confidence_n50.csv` and `evidence_threshold_payload32_alpha01.csv` for evidence-strength claims.
- Treat `capacity_proxy_payload8_logged_channels.csv` as a logged offline proxy. The logged L5/L6 labels are not the original design's cross-model/noisy-rank channels.

## Generated tables

- `utility_main.csv`: 10 rows
- `utility_by_cell.csv`: 30 rows
- `behavior_jsd_clean.csv`: 8 rows
- `strict_rlnc_recovery_main.csv`: 4 rows
- `strict_rlnc_recovery_by_cell.csv`: 32 rows
- `strict_rlnc_recovery_global.csv`: 21 rows
- `topk_ablation_main.csv`: 12 rows
- `capacity_proxy_payload8_logged_channels.csv`: 28 rows
- `evidence_confidence_n50.csv`: 4 rows
- `evidence_threshold_payload32_alpha01.csv`: 10 rows

## Quick view

### Utility main

| Dataset | Method | Cells | SR Mean (%) | SR Cell Std | Steps Mean |
| --- | --- | --- | --- | --- | --- |
| ALFWorld | Vanilla | 4 | 69.10 | 6.91 | 16.54 |
| ALFWorld | Clean | 4 | 80.04 | 10.51 | 16.23 |
| ALFWorld | Red-Green | 4 | 74.90 | 13.08 | 17.58 |
| ALFWorld | AgentMark-F | 4 | 79.43 | 10.73 | 16.58 |
| ALFWorld | AsymAgentMark-TK | 4 | 78.58 | 10.02 | 16.40 |
| ToolBench | Vanilla | 2 | 84.10 | 0.82 | 4.06 |
| ToolBench | Clean | 2 | 75.65 | 2.42 | 5.32 |
| ToolBench | Red-Green | 2 | 75.14 | 3.21 | 4.78 |
| ToolBench | AgentMark-F | 2 | 74.70 | 0.23 | 4.54 |
| ToolBench | AsymAgentMark-TK | 2 | 77.06 | 0.49 | 5.07 |

### Strict RLNC recovery main

| Dataset | Method | Cells | Payload Recovery (%) | Recovery Cell Std (%) | Dedup Packets |
| --- | --- | --- | --- | --- | --- |
| ALFWorld | AgentMark-F | 4 | 75.75 | 7.69 | 29.21 |
| ALFWorld | AsymAgentMark-TK | 4 | 34.81 | 13.39 | 11.31 |
| ToolBench | AgentMark-F | 12 | 9.58 | 6.48 | 2.78 |
| ToolBench | AsymAgentMark-TK | 12 | 1.94 | 1.72 | 1.47 |

### Strict RLNC global recovery

| Scope | Dataset | Method | Model | OK | Tasks | Global Recovery (%) |
| --- | --- | --- | --- | --- | --- | --- |
| overall | ALL | ALL | ALL | 1901 | 4728 | 40.2073 |
| by_method | ALL | AgentMark-F | ALL | 1314 | 2364 | 55.5838 |
| by_method | ALL | AsymAgentMark-TK | ALL | 587 | 2364 | 24.8308 |
| by_dataset | ALFWorld | ALL | ALL | 1818 | 3288 | 55.2920 |
| by_dataset | ToolBench | ALL | ALL | 83 | 1440 | 5.7639 |
| by_dataset_method | ALFWorld | AgentMark-F | ALL | 1245 | 1644 | 75.7299 |
| by_dataset_method | ALFWorld | AsymAgentMark-TK | ALL | 573 | 1644 | 34.8540 |
| by_dataset_method | ToolBench | AgentMark-F | ALL | 69 | 720 | 9.5833 |
| by_dataset_method | ToolBench | AsymAgentMark-TK | ALL | 14 | 720 | 1.9444 |
| by_method_model | ALL | AgentMark-F | deepseek | 613 | 1182 | 51.8613 |
| by_method_model | ALL | AgentMark-F | gemini-flash | 701 | 1182 | 59.3063 |
| by_method_model | ALL | AsymAgentMark-TK | deepseek | 205 | 1182 | 17.3435 |
| by_method_model | ALL | AsymAgentMark-TK | gemini-flash | 382 | 1182 | 32.3181 |
| by_dataset_method_model | ALFWorld | AgentMark-F | deepseek | 570 | 822 | 69.3431 |
| by_dataset_method_model | ALFWorld | AgentMark-F | gemini-flash | 675 | 822 | 82.1168 |
| by_dataset_method_model | ALFWorld | AsymAgentMark-TK | deepseek | 195 | 822 | 23.7226 |
| by_dataset_method_model | ALFWorld | AsymAgentMark-TK | gemini-flash | 378 | 822 | 45.9854 |
| by_dataset_method_model | ToolBench | AgentMark-F | deepseek | 43 | 360 | 11.9444 |
| by_dataset_method_model | ToolBench | AgentMark-F | gemini-flash | 26 | 360 | 7.2222 |
| by_dataset_method_model | ToolBench | AsymAgentMark-TK | deepseek | 10 | 360 | 2.7778 |
| by_dataset_method_model | ToolBench | AsymAgentMark-TK | gemini-flash | 4 | 360 | 1.1111 |

### Top-k ablation main

| Dataset | Top-k | Cells | Payload Recovery (%) | Bit Match (%) | Proxy C_eff |
| --- | --- | --- | --- | --- | --- |
| ALFWorld | 2 | 4 | 0.55 | 55.76 | 0.046 |
| ALFWorld | 4 | 4 | 1.34 | 60.05 | 0.164 |
| ALFWorld | 6 | 4 | 2.84 | 64.17 | 0.372 |
| ALFWorld | 8 | 4 | 4.85 | 67.03 | 0.690 |
| ALFWorld | 10 | 4 | 6.42 | 70.73 | 0.954 |
| ALFWorld | 20 | 4 | 31.30 | 86.28 | 4.511 |
| ToolBench | 2 | 12 | 0.00 | 35.12 | 0.000 |
| ToolBench | 4 | 12 | 0.56 | 42.62 | 0.009 |
| ToolBench | 6 | 12 | 0.97 | 46.96 | 0.016 |
| ToolBench | 8 | 12 | 2.08 | 48.85 | 0.032 |
| ToolBench | 10 | 12 | 3.19 | 49.52 | 0.053 |
| ToolBench | 20 | 12 | 3.47 | 50.46 | 0.056 |

