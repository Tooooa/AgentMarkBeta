TEX=paper.tex

.PHONY: all clean

all:
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(TEX)

clean:
	latexmk -C $(TEX)

