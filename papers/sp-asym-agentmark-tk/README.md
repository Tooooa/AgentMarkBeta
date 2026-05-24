# AsymAgentMark-TK S&P Paper Package

This directory contains a submission-oriented draft for an IEEE S&P-style
security paper on weakly asymmetric behavioral watermarking for LLM agents.

## Files

- `draft.md`: human-readable first draft and section narrative.
- `paper.tex`: LaTeX submission draft.
- `references.bib`: bibliography used by `paper.tex`.
- `paper.bbl`: generated bibliography snapshot for submission systems that require the resolved reference list.
- `paper.pdf`: compiled submission PDF.
- `Makefile`: local build helper.

## Build

```bash
make
```

The default target runs `latexmk -pdf paper.tex` and produces `paper.pdf`.

## Reproducibility Trail

- Paper build: `paper.tex`, `references.bib`, `paper.bbl`, and `Makefile` are sufficient to rebuild or audit the PDF.
- Algorithm implementation: `agentmark/core/watermark_sampler.py` contains the rank encoder/decoder path; `agentmark/core/rlnc_codec.py` contains the deterministic RLNC layer.
- Method draft lineage: `docs/drafts/method-section-draft.md` records the earlier method write-up used to shape the design section.
- Result source: `output/asym_agentmark_tk/week2_postprocess/*.csv` contains the postprocessed trajectory metrics used for the utility, JSD, capacity, top-k, rank-noise, and erasure tables; `week2_postprocess_summary.json` records the corresponding aggregate summary.
- Repository checks: from the repository root, run `python3 scripts/guards/check_docs_health.py` and `python3 scripts/guards/check_architecture.py` before committing paper changes.

## Venue Notes

- The LaTeX class uses `\documentclass[conference,compsoc]{IEEEtran}`, matching the IEEE S&P CFP guidance for submissions.
- The title block intentionally omits placeholder author names for double-blind review.
- The compiled PDF is below the 13-page body limit for the main text.

## Source Material

The draft is based on:

- `论文写作经验/Huang_等_-_2026_-_AgentMark_Utility-Preserving_Behavioral_Watermarking_for_Agents.pdf`
- `论文写作经验/From_Symmetry_toward_Weak_Asymmetry__Secure_Steganography_under_the_Receiver_s_Partial_Channel_Knowledge.pdf`
- `docs/drafts/method-section-draft.md`
- `agentmark/core/watermark_sampler.py`
- `agentmark/core/rlnc_codec.py`
- `output/asym_agentmark_tk/week2_postprocess/*.csv`
