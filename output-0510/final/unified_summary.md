# Unified Experiment Summary

## ALFWorld
| Dataset | Method | Model | Split | Complete Runs | Mean SR | Std |
|---|---|---|---:|---:|---:|---:|
| ALFWorld | vanilla | gemini-flash | ID | 3/3 | 60.9524 | 1.0911 |
| ALFWorld | vanilla | gemini-flash | OOD | 3/3 | 66.6667 | 1.5535 |
| ALFWorld | vanilla | deepseek | ID | 3/3 | 71.6667 | 1.6495 |
| ALFWorld | vanilla | deepseek | OOD | 3/3 | 77.1144 | 0.8617 |
| ALFWorld | clean | gemini-flash | ID | 3/3 | 72.6191 | 0.8247 |
| ALFWorld | clean | gemini-flash | OOD | 3/3 | 69.4030 | 0.0000 |
| ALFWorld | clean | deepseek | ID | 3/3 | 88.5714 | 0.0000 |
| ALFWorld | clean | deepseek | OOD | 3/3 | 89.5522 | 0.0000 |
| ALFWorld | rg | gemini-flash | ID | 3/3 | 63.3333 | 2.8868 |
| ALFWorld | rg | gemini-flash | OOD | 3/3 | 63.9303 | 3.0160 |
| ALFWorld | rg | deepseek | ID | 3/3 | 84.5238 | 0.4124 |
| ALFWorld | rg | deepseek | OOD | 3/3 | 87.8110 | 3.3651 |
| ALFWorld | agentmark | gemini-flash | ID | 3/3 | 72.1429 | 3.5715 |
| ALFWorld | agentmark | gemini-flash | OOD | 3/3 | 68.4080 | 1.5535 |
| ALFWorld | agentmark | deepseek | ID | 3/3 | 87.3809 | 2.8868 |
| ALFWorld | agentmark | deepseek | OOD | 3/3 | 89.8010 | 0.8617 |
| ALFWorld | rank | gemini-flash | ID | 3/3 | 70.9524 | 2.8868 |
| ALFWorld | rank | gemini-flash | OOD | 3/3 | 68.9055 | 2.3989 |
| ALFWorld | rank | deepseek | ID | 3/3 | 87.1429 | 1.4286 |
| ALFWorld | rank | deepseek | OOD | 3/3 | 87.3134 | 2.5851 |

## ToolBench
| Dataset | Method | Model | Complete Split-Runs | Mean Solve Rate | Std |
|---|---|---|---:|---:|---:|
| ToolBench | vanilla | gemini-flash | 18/18 | 83.5185 | 7.7941 |
| ToolBench | vanilla | deepseek | 18/18 | 84.6759 | 9.6725 |
| ToolBench | clean | gemini-flash | 18/18 | 73.9352 | 8.6262 |
| ToolBench | clean | deepseek | 18/18 | 77.3611 | 11.2650 |
| ToolBench | rg | gemini-flash | 18/18 | 72.8704 | 7.6067 |
| ToolBench | rg | deepseek | 18/18 | 77.4074 | 14.9315 |
| ToolBench | agentmark | gemini-flash | 18/18 | 74.8611 | 10.9896 |
| ToolBench | agentmark | deepseek | 18/18 | 74.5370 | 13.7533 |
| ToolBench | rank | gemini-flash | 18/18 | 76.7130 | 11.1675 |
| ToolBench | rank | deepseek | 18/18 | 77.4074 | 11.0402 |

## Artifacts
- Audit root: `/root/autodl-tmp/AgentMark3/AgentMark/output_supplement_0426_fix/audit`
- ToolBench summary: `output/toolbench_unified_eval_0426/summary_by_split.json`
