SHELL := /bin/bash

.PHONY: check test tools
check:
	./scripts/check.sh

test:
	python3 -m unittest discover -s tests -v

tools:
	./scripts/install-check-tools.sh
