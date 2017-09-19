# Override this as necessary

# https://www.mercurial-scm.org/repo/hg/file/tip/tests/run-tests.py
# adjust the below path as it looks to be using a fork of the canonical mecurial repository

RUNTESTS=../../mercurial-crew/tests/run-tests.py
TESTFLAGS=

.PHONY: tests
tests:
	cd tests && $(RUNTESTS) $(TESTFLAGS) *.t

test-%:
	cd tests && $(RUNTESTS) $(TESTFLAGS) $@

.PHONY: clean
clean:
	rm -f $$(hg status --no-status --ignore)
