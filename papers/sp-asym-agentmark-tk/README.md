# AsymMark-R S&P Paper Package

This directory contains a submission-oriented draft for an IEEE S&P-style
security paper on weakly asymmetric behavioral watermarking for LLM agents.

## Files

- `draft.md`: human-readable first draft and section narrative.
- `storyline_zh.md`: Chinese story-line analysis comparing the weak-asymmetry paper, AgentMark-F, and the rank method.
- `figure_plan_zh.md`: Chinese plan for paper figures, including each figure's narrative role, expected content, placement, and priority.
- `paper_story_bilingual.html`: bilingual English/Chinese narrative, related-work, and method writing scaffold.
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

## Repository Audit Trail

- Paper build: `paper.tex`, `references.bib`, `paper.bbl`, and `Makefile` are sufficient to rebuild or audit the PDF.
- Algorithm implementation: `agentmark/core/watermark_sampler.py` contains the rank encoder/decoder path and owner-key derivation hook; `agentmark/core/rlnc_codec.py` contains the deterministic RLNC layer.
- Method draft lineage: `docs/drafts/method-section-draft.md` records the earlier method write-up used to shape the design section.
- Result source: `output/asym_agentmark_tk/week2_postprocess/*.csv` contains the postprocessed trajectory metrics used for the utility, JSD, capacity, top-k, rank-noise, and erasure tables; `week2_postprocess_summary.json` records the corresponding aggregate summary.
- Repository checks: from the repository root, run `python3 scripts/guards/check_docs_health.py` and `python3 scripts/guards/check_architecture.py` before committing paper changes.

## Venue Notes

- The LaTeX class uses `\documentclass[conference,compsoc]{IEEEtran}`, matching the IEEE S&P CFP guidance for submissions.
- The title block intentionally omits author names for double-blind review.
- The compiled PDF keeps the main text concise and places supporting proof, synchronization, RLNC, top-k, and artifact-mapping details in appendices.
- For an anonymous artifact release, include only sanitized relative paths and exclude local drafting-material references.

## Anonymous Bundle Checklist

For an anonymous paper or artifact bundle, include only:

- `paper.tex`, `references.bib`, `paper.bbl`, `Makefile`, and the compiled `paper.pdf`.
- Sanitized result tables needed to reproduce the reported postprocessed diagnostics.
- A short artifact README that describes commands and relative paths without referring to internal drafting notes.

Do not include local drafting materials, absolute-path summaries, private notes,
or source PDFs copied from the internal reference directory. Keep unpublished
related manuscripts anonymized unless they are already public.
