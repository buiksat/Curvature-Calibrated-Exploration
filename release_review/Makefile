TEX      := pdflatex
BIB      := bibtex
TEXFLAGS := -interaction=nonstopmode -halt-on-error

PAPERDIR := paper
MAIN     := main

.PHONY: all pdf clean cleanall

all: pdf

pdf:
	cd $(PAPERDIR) && $(TEX) $(TEXFLAGS) $(MAIN)
	cd $(PAPERDIR) && $(BIB) $(MAIN)
	cd $(PAPERDIR) && $(TEX) $(TEXFLAGS) $(MAIN)
	cd $(PAPERDIR) && $(TEX) $(TEXFLAGS) $(MAIN)

clean:
	cd $(PAPERDIR) && rm -f *.aux *.bbl *.blg *.log *.out *.fdb_latexmk \
		*.fls *.synctex.gz *.toc *.lof *.lot *.nav *.snm *.vrb \
		*.run.xml *-blx.bib *.bcf

cleanall: clean
	cd $(PAPERDIR) && rm -f $(MAIN).pdf
