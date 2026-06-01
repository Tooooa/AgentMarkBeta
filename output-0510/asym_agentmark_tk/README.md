# AsymMark-R Capacity and Perception Artifacts

- Input root: `/root/autodl-tmp/output-0510`
- Output dir: `/root/autodl-tmp/output-0510/asym_agentmark_tk`
- Scope: ALFWorld + ToolBench only; OASIS is not included in this delivery.
- API usage: none. This is an offline postprocess over canonical 0510 trajectories.

## Completeness

- ALFWorld task records: 8220
- ToolBench task records: 3600
- A3/A4 watermark decode-capable trajectories: 4728
- `audit/gap_manifest.json` has empty ALFWorld and ToolBench gaps.

## Capacity Metrics

- `capacity_l0_l6_proxy.*` is a bit-level offline channel proxy for L0-L6 and Top-k trend analysis.
- `topk_ablation.*` is the AsymMark-R/rank-only Top-k ablation.
- `capacity_rlnc_exact_recovery.*` is the strict A3/A4 RLNC bit-exact payload recovery table and must not be mixed with proxy capacity claims.
- Proxy `C_eff` is reported as `c_eff_proxy_bits = c_nom_proxy_bits * payload_recovery_rate`, where `c_nom_proxy_bits` is the mean decoded proxy bits per trajectory available from logged metadata.

## Files

- `capacity_l0_l6_proxy`: `/root/autodl-tmp/output-0510/asym_agentmark_tk/capacity_l0_l6_proxy.csv`
- `capacity_rlnc_exact_recovery`: `/root/autodl-tmp/output-0510/asym_agentmark_tk/capacity_rlnc_exact_recovery.csv`
- `topk_ablation`: `/root/autodl-tmp/output-0510/asym_agentmark_tk/topk_ablation.csv`
- `utility_retention`: `/root/autodl-tmp/output-0510/asym_agentmark_tk/utility_retention.csv`
- `behavior_jsd`: `/root/autodl-tmp/output-0510/asym_agentmark_tk/behavior_jsd.csv`

## Reproduce

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
python experiments/asym_agentmark_tk/scripts/run_capacity_perception.py --overwrite
```
