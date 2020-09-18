# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    = -W -n
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = PulpAnsible
SOURCEDIR     = .
BUILDDIR      = _build
DIAGRAM_BUILD_DIR    = _diagrams
DIAGRAM_SOURCE_DIR    = diagrams_src
PULP_URL      = "http://localhost:24817"

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: clean help html Makefile


clean:
	-rm -rf $(BUILDDIR)/*


diagrams:
ifneq ($(wildcard $(DIAGRAM_SOURCE_DIR)), )
	mkdir -p $(DIAGRAM_BUILD_DIR)
	python3 -m plantuml diagrams_src/*.dot
	# cp + rm = mv  workaround https://pulp.plan.io/issues/4791#note-3
	cp diagrams_src/*.png $(DIAGRAM_BUILD_DIR)/
	rm diagrams_src/*.png
else
	@echo "Did not find diagrams_src."
endif


html:
	curl -o _static/api.json "$(PULP_URL)/pulp/api/v3/docs/api.json?plugin=pulp_ansible"
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."
