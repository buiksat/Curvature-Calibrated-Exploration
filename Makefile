# Build the active TMLR release outside the checkout.
TMLR_OUT ?= /tmp/cce-tmlr-release

.PHONY: all pdf
all: pdf
pdf:
	TMLR_OUT="$(TMLR_OUT)" bash submissions/tmlr_2026/build.sh
