TEX      := pdflatex
BIB      := bibtex
TEXFLAGS := -interaction=nonstopmode -halt-on-error

PAPERDIR := paper
TWO_PAGER := two_pager

.PHONY: all two_pager pdf clean cleanall

all: two_pager

pdf: two_pager

two_pager:
	cd $(PAPERDIR) && $(TEX) $(TEXFLAGS) $(TWO_PAGER)
	cd $(PAPERDIR) && $(BIB) $(TWO_PAGER)
	cd $(PAPERDIR) && $(TEX) $(TEXFLAGS) $(TWO_PAGER)
	cd $(PAPERDIR) && $(TEX) $(TEXFLAGS) $(TWO_PAGER)

clean:
	cd $(PAPERDIR) && rm -f *.aux *.bbl *.blg *.log *.out *.fdb_latexmk \
		*.fls *.synctex.gz *.toc *.lof *.lot *.nav *.snm *.vrb \
		*.run.xml *-blx.bib *.bcf

cleanall: clean
	cd $(PAPERDIR) && rm -f $(TWO_PAGER).pdf
