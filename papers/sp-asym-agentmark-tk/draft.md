# AsymAgentMark-TK: Weakly Asymmetric Behavioral Watermarking for LLM Agents

## Abstract

Autonomous LLM agents increasingly make consequential multi-step decisions through planning behaviors such as tool selection, subgoal choice, and embodied action selection. Existing content watermarks attribute generated text, but they do not directly attest to the planning behavior that drives an agent's execution. AgentMark introduced distribution-preserving behavioral watermarking for this setting, but its concrete symmetric construction requires the verifier to reconstruct the exact behavior distribution used by the embedder. This assumption is brittle under realistic verification: API quantization, temperature changes, model refreshes, and cross-model re-querying may preserve the order of likely behaviors while perturbing probability values enough to break symmetric decoding.

This paper proposes AsymAgentMark-TK, a weakly asymmetric behavioral watermark for LLM agents. The embedder uses full per-step behavior probabilities to preserve the agent's marginal policy, while the verifier needs only top-k rank order. The core construction replaces probability-dependent differential bins with an interleaved binary partition tree over rank-sorted behaviors. Each selected behavior's rank determines a decoding path, allowing bit recovery from rank positions alone. A fixed-budget HMAC-SHA512 DRBG schedule keeps encoder and decoder synchronized, and deterministic RLNC turns variable per-step bits into erasure-tolerant payload recovery.

We evaluate AsymAgentMark-TK on ALFWorld and ToolBench using DeepSeek and Gemini Flash. Across 11,820 trajectories, rank watermarking preserves task utility relative to a clean AgentMark pipeline: average success is 78.6% versus 80.0% on ALFWorld and 77.1% versus 75.7% on ToolBench. Behavior-distribution divergence from clean remains comparable to symmetric AgentMark (mean JSD 0.121 versus 0.122 on ALFWorld, 0.140 versus 0.174 on ToolBench). Under exact probabilities, symmetric AgentMark has higher 8-bit payload recovery on ALFWorld (0.700 versus 0.532), but under top-10 rank-only verification it collapses to 0.014 while AsymAgentMark-TK remains at 0.068. These results show that partial channel knowledge can be converted into practical behavioral provenance without requiring exact probability reconstruction.

## Paper Story

The security story is not "another agent watermark." It is a channel-knowledge story. AgentMark-F solves behavioral watermarking when the verifier shares exact probability values. S&P reviewers will ask whether that assumption survives real verification. The answer is no: the verifier often receives only top-k candidates, rounded logits, a refreshed model, or a proxy model. The paper therefore introduces weak asymmetry at the behavior layer: sender has full channel, receiver has rank-only partial channel knowledge.

The main technical hook is a co-designed encoder and decoder. AgentMark-F's differential recombination constructs bins from probability values; if those values change, bins change. AsymAgentMark-TK instead sorts actions, recursively partitions even and odd ranks, and uses probability values only to choose groups in a distribution-preserving way. Once an action is selected, its rank alone reveals which odd branches were taken and therefore which bits were embedded.

## Contributions

1. A weakly asymmetric threat model for behavioral watermarking in which verification sees partial channel knowledge rather than exact per-step behavior distributions.
2. AsymAgentMark-TK, a top-k rank-based distribution-preserving encoder/decoder for planning behaviors.
3. A synchronization and coding layer combining fixed-budget HMAC-SHA512 DRBG calls with deterministic RLNC for partial logs.
4. An empirical evaluation over ALFWorld and ToolBench, covering utility, distributional stealth, rank-only decoding, top-k ablations, rank noise, and analytic false-positive rates.

## Section Plan

1. Introduction: motivate agent provenance, explain why content watermarks and exact-probability behavioral watermarks are insufficient, and state the partial-channel gap.
2. Background: LLM agents, behavioral watermarking, distribution-preserving steganography, and weak asymmetric channel knowledge.
3. Problem formulation: define behavior distributions, exact and rank-only verification, adversaries, correctness, utility preservation, and false-positive criteria.
4. Design: present AsymAgentMark-TK, binary primitive, rank encoder, rank decoder, synchronization, and RLNC integration.
5. Security analysis: prove distribution preservation and weak asymmetry under top-k rank consistency; discuss limits under rank swaps.
6. Evaluation: report available experimental results and highlight the exact-probability versus rank-only tradeoff.
7. Discussion and limitations: top-k choice, cross-model verification, low-entropy tool traces, and adaptive adversaries.
8. Conclusion: partial channel knowledge is enough for behavioral provenance.

## Notes for Revision

The current LaTeX draft is written as an S&P-style anonymous submission using the `conference,compsoc` IEEEtran class and no fake author block. It is intentionally concise and keeps several proofs in theorem/proposition form to fit the 13-page body constraint. The available capacity artifacts are bit-level offline decoder proxies; the text avoids claiming full end-to-end RLNC recovery beyond what is present in the generated tables.

The draft now includes a tighter submission-style abstract, an introduction roadmap aligned with the final section numbering, a system-level figure that contrasts the full-channel embedder with the rank-only verifier, a positioning table that separates text watermarking, AgentMark-F, and AsymAgentMark-TK, explicit removal/framing adversary goals, a verification-protocol subsection that separates positive attribution from inconclusive audits, an evaluation-protocol subsection that explains trajectory filtering, verifier views, perturbation injection, and aggregation, a coverage table for postprocessed runs and decode-capable trajectories, a selected-only negative-control column in the capacity table, claim-binding guidance for pre-registered key/payload ownership, a candidate-canonicalization threat to validity, and README-level artifact notes tying tables back to source CSVs and implementation files. The discussion and conclusion now frame the current artifact as partial-channel feasibility rather than production certification. The false-positive section now distinguishes 8-bit diagnostic experiments from deployable attribution thresholds and adds multiple-testing accounting for many key/payload claims. The next strongest improvement would be an end-to-end RLNC recovery table from live trajectories. The present draft explicitly separates strict payload recovery from bit-level channel diagnostics so reviewers do not mistake proxy results for full-system claims.
