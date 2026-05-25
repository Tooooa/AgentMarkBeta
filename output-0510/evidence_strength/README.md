# Evidence Strength Experiment

- Input root: `/root/autodl-tmp/output-0510`
- Output dir: `/root/autodl-tmp/output-0510/evidence_strength`
- Step observations: 55475
- Audit rows: 14184

## Completed

- 4.1 解码置信度曲线：exact one-sided binomial test, H0 match probability = 0.5.
- 4.2 最小证据阈值：alpha in {0.05, 0.01, 0.001}; payload lengths {8, 16, 32, 64}.
- 4.3 鲁棒性补偿分析：基于 4.1 match 序列注入 erasure/noise 后重新求 N_attack / N_clean.

## Artifacts

- `observations_json`: `/root/autodl-tmp/output-0510/evidence_strength/evidence_step_observations.json`
- `observations_csv`: `/root/autodl-tmp/output-0510/evidence_strength/evidence_step_observations.csv`
- `audit_json`: `/root/autodl-tmp/output-0510/evidence_strength/evidence_decode_audit.json`
- `audit_csv`: `/root/autodl-tmp/output-0510/evidence_strength/evidence_decode_audit.csv`
- `stage_d_4_1_per_run_json`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_1_confidence_per_run.json`
- `stage_d_4_1_per_run_csv`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_1_confidence_per_run.csv`
- `stage_d_4_1_summary_json`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_1_confidence_summary.json`
- `stage_d_4_1_summary_csv`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_1_confidence_summary.csv`
- `stage_d_4_2_per_run_json`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_2_thresholds_per_run.json`
- `stage_d_4_2_per_run_csv`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_2_thresholds_per_run.csv`
- `stage_d_4_2_summary_json`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_2_thresholds_summary.json`
- `stage_d_4_2_summary_csv`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_2_thresholds_summary.csv`
- `stage_d_4_3_compensation_json`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_3_compensation.json`
- `stage_d_4_3_compensation_csv`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_3_compensation.csv`
- `stage_d_4_3_compensation_summary_json`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_3_compensation_summary.json`
- `stage_d_4_3_compensation_summary_csv`: `/root/autodl-tmp/output-0510/evidence_strength/stage_d_4_3_compensation_summary.csv`

## Plots

- `/root/autodl-tmp/output-0510/evidence_strength/plots/stage_d_4_1_confidence_alfworld.png`
- `/root/autodl-tmp/output-0510/evidence_strength/plots/stage_d_4_1_confidence_toolbench.png`
- `/root/autodl-tmp/output-0510/evidence_strength/plots/stage_d_4_2_threshold_alfworld_deepseek_ID.png`
- `/root/autodl-tmp/output-0510/evidence_strength/plots/stage_d_4_2_threshold_alfworld_deepseek_OOD.png`
- `/root/autodl-tmp/output-0510/evidence_strength/plots/stage_d_4_2_threshold_alfworld_gemini-flash_ID.png`
- `/root/autodl-tmp/output-0510/evidence_strength/plots/stage_d_4_2_threshold_alfworld_gemini-flash_OOD.png`

## Notes

- `agentmark` uses differential decoding at L0 exact probabilities.
- `rank` reports full-rank plus top-k decoder views for k = 10, 5, 3, 2.
- Step-level evidence counts one accepted embedding step as one Bernoulli trial; a step matches only when all decoded bits for that step match the expected RLNC coded bits.
