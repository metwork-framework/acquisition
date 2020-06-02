doc:
	rm -Rf html
	pdoc --html acquisition

clean:
	rm -Rf html htmlcov
	rm -Rf acquisition.egg-info
	find . -type d -name __pycache__ -exec rm -Rf {} \; 2>/dev/null || exit 0

test: clean
	pytest tests/

coverage:
	pytest --cov-report html --cov=acquisition tests/
	pytest --cov=acquisition tests/
