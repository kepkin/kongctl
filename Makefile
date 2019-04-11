###############################################################################
# See ./CONTRIBUTING.rst
###############################################################################

VERSION=$(shell grep __version__ kongctl/__init__.py)
REQUIREMENTS="requirements-dev.txt"
TAG="\n\n\033[0;32m\#\#\# "
END=" \#\#\# \033[0m\n"


all: test


init: uninstall-kongctl
	@echo $(TAG)Installing dev requirements$(END)
	pip3 install --upgrade -r $(REQUIREMENTS)

	@echo $(TAG)Installing kongctl$(END)
	pip3 install --upgrade --editable .

	@echo

clean:
	@echo $(TAG)Cleaning up$(END)
	rm -rf .tox *.egg dist build .coverage .cache .pytest_cache kongctl.egg-info
	find . -name '__pycache__' -delete -print -o -name '*.pyc' -delete -print
	@echo


###############################################################################
# Testing
###############################################################################

test: init
	@echo $(TAG)Running tests on the current Python interpreter with coverage $(END)
	echo "TODO"
	@echo
# test: init
# 	@echo $(TAG)Running tests on the current Python interpreter with coverage $(END)
# 	py.test --cov ./kongctl --cov ./tests --doctest-modules --verbose ./kongctl ./tests
# 	@echo


# test-all is meant to test everything — even this Makefile
test-all: uninstall-all clean init test-dist pycodestyle  # test test-tox
	@echo


test-dist: test-sdist test-bdist-wheel
	@echo


# test-tox: init
# 	@echo $(TAG)Running tests on all Pythons via Tox$(END)
# 	tox
# 	@echo


test-sdist: clean uninstall-kongctl
	@echo $(TAG)Testing sdist build an installation$(END)
	python setup.py sdist
	pip3 install --force-reinstall --upgrade dist/*.gz
	which kongctl
	@echo


test-bdist-wheel: clean uninstall-kongctl
	@echo $(TAG)Testing wheel build an installation$(END)
	python setup.py bdist_wheel
	pip3 install --force-reinstall --upgrade dist/*.whl
	which kongctl
	@echo


pycodestyle:
	which pycodestyle || pip install pycodestyle
	pycodestyle
	@echo


coveralls:
	which coveralls || pip install python-coveralls
	coveralls
	@echo


###############################################################################
# Publishing to PyPi
###############################################################################


publish: test-all publish-no-test


publish-no-test:
	@echo $(TAG)Testing wheel build an installation$(END)
	@echo "$(VERSION)"
	@echo "$(VERSION)" | grep -q "dev" && echo '!!!Not publishing dev version!!!' && exit 1 || echo ok
	pip install requests docutils
	twine upload dist/*
	@echo



###############################################################################
# Uninstalling
###############################################################################

uninstall-kongctl:
	@echo $(TAG)Uninstalling kongctl$(END)
	- pip uninstall --yes kongctl &2>/dev/null

	@echo "Verifying…"
	cd .. && ! python -m kongctl --version &2>/dev/null

	@echo "Done"
	@echo


uninstall-all: uninstall-kongctl

	@echo $(TAG)Uninstalling kongctl requirements$(END)
	- pip uninstall --yes termcolor requests

	@echo $(TAG)Uninstalling development requirements$(END)
	- pip uninstall --yes -r $(REQUIREMENTS)


###############################################################################
# Homebrew
###############################################################################

brew-deps:
	extras/brew-deps.py

brew-test:
	- brew uninstall kongctl
	brew install --build-from-source ./extras/kongctl.rb
	brew test kongctl
	brew audit --strict kongctl
