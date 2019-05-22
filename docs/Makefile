# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    = -W -n
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = PulpAnsible
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: clean help html Makefile


clean:
	-rm -rf $(BUILDDIR)/*


html:
	curl -o _static/api.json "http://localhost:24817/pulp/api/v3/docs/api.json?plugin=pulp_ansible"
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."
