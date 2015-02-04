# Simple make file for IRI targets

OFTEST_PATH=submodules/oftest
OFTEST_PYTHON=${OFTEST_PATH}/src/python
PYPATH=PYTHONPATH=.:${OFTEST_PYTHON}

UNIT_TEST_LOG=unit_test.log

ifndef START_YML
START_YML=simple.yml profile_1.yml
endif

# How long should coverage 
ifndef COV_SECONDS
COV_SECONDS=5
endif

# Accumulate unit test execution here
test:
	make -C air test
	rm -f unit_test.log
	${PYPATH} iri/simple_queue.py ${UNIT_TEST_LOG}
	${PYPATH} iri/field.py ${UNIT_TEST_LOG}
	${PYPATH} iri/header.py ${UNIT_TEST_LOG}
	${PYPATH} iri/table_entry.py ${UNIT_TEST_LOG}
	${PYPATH} iri/action.py ${UNIT_TEST_LOG}
	${PYPATH} iri/table.py ${UNIT_TEST_LOG}
	${PYPATH} iri/instance.py ${UNIT_TEST_LOG}
	${PYPATH} iri/parsed_packet.py ${UNIT_TEST_LOG}
	${PYPATH} iri/parser.py ${UNIT_TEST_LOG} unit_test.yml
	${PYPATH} iri/parser.py ${UNIT_TEST_LOG} profile_1.yml simple.yml
	${PYPATH} iri/parser.py ${UNIT_TEST_LOG} profile_0.yml l3.yml
	${PYPATH} iri/pipeline.py ${UNIT_TEST_LOG}

	${PYPATH} iri/parser.py ${UNIT_TEST_LOG} vxlan/*.yml profile_1.yml

doc:
	cd doc && doxygen
	cp -r img doc/html/

submodule:
	git submodule update --init

start: submodule
	sudo ${PYPATH} ./start.py -v ${START_YML}

start-l3: submodule
	sudo ${PYPATH} ./start.py -v profile_0.yml l3.yml

start-vxlan: submodule
	sudo ${PYPATH} ./start.py -v profile_1.yml vxlan/*.yml

templates: submodule
	./templates.py simple.yml profile_1.yml

# Run some comprehensive test case and show the coverage
cov:
	sudo ${PYPATH} coverage run ./start.py --run_for=${COV_SECONDS} -v ${START_YML}
	coverage html
	@echo Point a web browser to htmlcov/index.html for converge info

clean:
	rm -rf *.pyc iri/*.pyc air/*.pyc
	rm -rf doc/html
	rm -rf doc/img

help:
	@echo "Run AIR/IRI code. Targets:"
	@echo "  test:      Run unit tests"
	@echo "  start:     Start the switch with code from START_YML env var"
	@echo "  start-l3:  Start the switch with simple L3 switch"
	@echo "  doc:       Rebuild the documentation"
	@echo "  cov:       Run coverage"


.PHONY: doc submodule clean cov doc test start start-l3 help


