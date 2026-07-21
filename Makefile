cov-xml:
	uv run coverage xml -o reports/coverage/coverage.xml


cov:
	uv run pytest --cov=request_manager tests/; rm -f .coverage
