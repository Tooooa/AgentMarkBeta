# Partial-Channel Follow-up Diagnostics

## Rank-only pooled contrast

ALFWorld/DeepSeek/ID top-10 pooled recovery:

| Method/view | Pool 1 | Pool 10 | Pool 20 | Pool 50 | Pool 100 |
| --- | ---: | ---: | ---: | ---: | ---: |
| AgentMark-F exact probabilities | 0.693 | 1.000 | 1.000 | 1.000 | 1.000 |
| AgentMark-F rank-only linear top-10 surrogate | 0.013 | 0.133 | 0.167 | 0.140 | 0.067 |
| AsymAgentMark-TK top-10 rank | 0.080 | 0.613 | 0.780 | 0.807 | 0.493 |

The AgentMark-F rank-only row is a forced verifier surrogate: it keeps only the top-10 rank order and assigns monotone linear pseudo-probabilities before running the differential decoder. This is not a supported AgentMark-F verification channel; it is an intentionally favorable rank-only proxy to test whether pooling rescues the baseline.

## Unordered-set keyed partition

- Trials: 20000
- Decode success: 1.0
- Bit error rate: 0.0
- Mean bits per step: 1.50045
- Selection JSD vs source distribution: 5.1e-05
- Shuffle invariance failures: 0

This confirms a second partial-channel invariant on pseudo data: the verifier reconstructs a keyed canonical order from the unordered top-k set, not from probability rank.

## Targeted rank perturbation

The local targeted swap diagnostic is a verifier-channel stress test, not the main threat model. It perturbs the reconstructed rank order after execution and measures how much pooled recovery degrades.

| View | Pool 10 | Pool 20 | Pool 50 |
| --- | ---: | ---: | ---: |
| Clean top-10 rank | 0.613 | 0.780 | 0.807 |
| Targeted swap budget 1 | 0.007 | 0.000 | 0.000 |
